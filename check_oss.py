import sys
sys.path.insert(0, 'scripts')
from oss_utils import get_oss_client_from_config

client = get_oss_client_from_config()

print('=== OSS 存储概览 ===')
print()

# 列出一级目录
print('一级目录:')
dirs = client.list_dirs('')
for d in dirs:
    print(f'  📁 {d}/')

print()
print('根目录文件:')
files = client.list_files('', max_keys=20)
for f in files:
    size_kb = f['size'] / 1024
    if size_kb >= 1024:
        size_str = f'{size_kb/1024:.2f} MB'
    else:
        size_str = f'{size_kb:.2f} KB'
    print(f'  📄 {f["key"]} ({size_str})')

print()
print(f'总计: {len(files)} 个文件, {len(dirs)} 个目录')
print()

# 如果有data目录，列出内容
if 'data/' in [d + '/' for d in dirs] or 'data' in dirs:
    print('=== data/ 目录内容 ===')
    data_dirs = client.list_dirs('data/')
    for d in data_dirs:
        name = d.replace('data/', '')
        # 统计该目录下文件数
        sub_files = client.list_files(d + '/', max_keys=5)
        total = len(sub_files)
        # 尝试获取更多
        if total == 5:
            # 估算
            all_sub = client.list_files(d + '/', max_pages=10)
            total = len(all_sub)
        print(f'  📁 {name}/ ({total} 个文件)')

    # 检查是否有daily_price目录
    print()
    print('检查是否有 daily_price/ 目录...')
    daily_dirs = client.list_dirs('data/daily_price/')
    if daily_dirs:
        print(f'  找到 daily_price/ 目录，包含 {len(daily_dirs)} 个子项')
        sample_files = client.list_files('data/daily_price/', max_keys=5)
        print('  示例文件:')
        for f in sample_files[:5]:
            name = f['key'].replace('data/daily_price/', '')
            print(f'    {name}')
    else:
        print('  未找到 daily_price/ 目录')

    # 检查csv文件
    print()
    print('检查根目录CSV文件:')
    all_files = client.list_files('data/')
    csv_files = [f for f in all_files if f['key'].endswith('.csv')]
    for f in csv_files:
        name = f['key'].replace('data/', '')
        size_kb = f['size'] / 1024
        print(f'  📄 {name} ({size_kb:.1f} KB)')

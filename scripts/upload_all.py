import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oss_utils import get_oss_client_from_config

SOURCE_DIR = r'D:\cxdownload\data\data'

def format_size(size_bytes):
    if size_bytes >= 1024 * 1024 * 1024:
        return f'{size_bytes / 1024 / 1024 / 1024:.2f} GB'
    elif size_bytes >= 1024 * 1024:
        return f'{size_bytes / 1024 / 1024:.2f} MB'
    elif size_bytes >= 1024:
        return f'{size_bytes / 1024:.2f} KB'
    return f'{size_bytes} B'

def main():
    print('=' * 60)
    print('数据上传到OSS')
    print('=' * 60)

    oss = get_oss_client_from_config()
    print('测试连接...')
    ok, msg = oss.test_connection()
    if not ok:
        print(f'连接失败: {msg}')
        return
    print('  ✓ 连接成功')

    # 1. 上传维度表
    print('\n[1/2] 上传维度表...')

    dim_files = [
        ('products.csv', 'data/dim/products.csv'),
        ('categories.csv', 'data/dim/categories.csv'),
    ]

    for filename, oss_key in dim_files:
        local_path = os.path.join(SOURCE_DIR, filename)
        if os.path.exists(local_path):
            size = os.path.getsize(local_path)
            print(f'  上传: {filename} ({format_size(size)})...', end=' ', flush=True)
            try:
                oss.upload_file(local_path, oss_key)
                print('✓')
            except Exception as e:
                print(f'✗ {e}')
        else:
            print(f'  跳过: {filename} (文件不存在)')

    # 2. 上传ODS数据
    print('\n[2/2] 上传ODS每日价格数据...')

    daily_price_dir = os.path.join(SOURCE_DIR, 'daily_price')
    files = sorted([f for f in os.listdir(daily_price_dir)
                   if f.startswith('daily_prices_') and f.endswith('.csv')])

    total = len(files)
    print(f'  共 {total} 个文件待上传')

    total_size = sum(os.path.getsize(os.path.join(daily_price_dir, f)) for f in files)
    print(f'  总大小: {format_size(total_size)}')

    uploaded = 0
    uploaded_size = 0
    start_time = time.time()
    skip_count = 0

    for i, filename in enumerate(files):
        local_path = os.path.join(daily_price_dir, filename)
        date_str = filename.replace('daily_prices_', '').replace('.csv', '')
        formatted_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
        oss_key = f'data/ods/dt={formatted_date}/daily_prices.csv'
        file_size = os.path.getsize(local_path)

        # 检查是否已存在
        if oss.file_exists(oss_key):
            skip_count += 1
            uploaded += 1
            uploaded_size += file_size
            if (i + 1) % 50 == 0 or i == total - 1:
                elapsed = time.time() - start_time
                speed = uploaded_size / elapsed if elapsed > 0 else 0
                print(f'  进度: {uploaded}/{total} ({uploaded/total*100:.1f}%) - 已跳过{skip_count}个 - {format_size(speed)}/s')
            continue

        try:
            oss.upload_file(local_path, oss_key)
            uploaded += 1
            uploaded_size += file_size
        except Exception as e:
            print(f'  ✗ {filename}: {e}')

        if (i + 1) % 50 == 0 or i == total - 1:
            elapsed = time.time() - start_time
            speed = uploaded_size / elapsed if elapsed > 0 else 0
            remaining = (total_size - uploaded_size) / speed if speed > 0 else 0
            if remaining > 3600:
                remaining_str = f'{remaining/3600:.1f}小时'
            elif remaining > 60:
                remaining_str = f'{remaining/60:.1f}分钟'
            else:
                remaining_str = f'{remaining:.0f}秒'
            print(f'  进度: {uploaded}/{total} ({uploaded/total*100:.1f}%) - {format_size(speed)}/s - 约剩{remaining_str}')

    elapsed = time.time() - start_time
    print('\n' + '=' * 60)
    print('上传完成!')
    print(f'  总文件数: {total}')
    print(f'  成功: {uploaded}')
    print(f'  跳过: {skip_count}')
    print(f'  总大小: {format_size(uploaded_size)}')
    if elapsed > 3600:
        print(f'  总耗时: {elapsed/3600:.1f}小时')
    elif elapsed > 60:
        print(f'  总耗时: {elapsed/60:.1f}分钟')
    else:
        print(f'  总耗时: {elapsed:.1f}秒')
    print('=' * 60)

if __name__ == '__main__':
    main()

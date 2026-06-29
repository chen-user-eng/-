import sys
sys.path.insert(0, 'scripts')
from config import OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET
import oss2
import io
import pandas as pd

print('=== OSS数据读取测试 ===')
print()

auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)

# 测试1: 列出数据目录
print('1. 列出OSS数据目录:')
try:
    result = bucket.list_objects(prefix='data/', max_keys=30)
    files_found = 0
    dirs_found = 0
    for obj in result.object_list:
        size_kb = obj.size / 1024
        if size_kb >= 1024:
            size_str = f'{size_kb/1024:.1f} MB'
        else:
            size_str = f'{size_kb:.1f} KB'
        print(f'   FILE: {obj.key} ({size_str})')
        files_found += 1
    for prefix in result.prefix_list:
        print(f'   DIR: {prefix}')
        dirs_found += 1
    print(f'   总计: {files_found} 个文件, {dirs_found} 个目录')
except Exception as e:
    print(f'   ERROR: {e}')

print()
print('2. 读取维度表:')

# 测试2: 读取商品维度表
try:
    result = bucket.get_object('data/dim/products.csv')
    content = result.read()
    df = pd.read_csv(io.BytesIO(content), encoding='gbk')
    print(f'   OK: products.csv 共 {len(df)} 条记录')
    print(f'   字段: {", ".join(df.columns)}')
    print(f'   前2条:')
    for _, row in df.head(2).iterrows():
        print(f'     product_id={row.product_id}, name={row.name[:20]}..., price={row.price}')
except Exception as e:
    print(f'   ERROR products.csv: {e}')

# 测试3: 读取类目维度表
try:
    result = bucket.get_object('data/dim/categories.csv')
    content = result.read()
    df = pd.read_csv(io.BytesIO(content), encoding='gbk')
    print(f'   OK: categories.csv 共 {len(df)} 条记录')
    print(f'   字段: {", ".join(df.columns)}')
    print(f'   前2条:')
    for _, row in df.head(2).iterrows():
        print(f'     category_id={row.category_id}, name={row.category}, hierarchy={row.hierarchy}')
except Exception as e:
    print(f'   ERROR categories.csv: {e}')

print()
print('3. 读取ODS数据:')

# 测试4: 读取某一天的ODS数据
try:
    result = bucket.list_objects(prefix='data/ods/', max_keys=10)
    if result.object_list:
        first_file = result.object_list[0]
        print(f'   找到文件: {first_file.key}')
        result_data = bucket.get_object(first_file.key)
        content = result_data.read()
        df = pd.read_csv(io.BytesIO(content), encoding='gbk')
        print(f'   OK: 读取到 {len(df)} 条记录')
        print(f'   字段: {", ".join(df.columns)}')
    else:
        print('   INFO: 还没有ODS文件上传完成')
except Exception as e:
    print(f'   ERROR: {e}')

print()
print('=== 测试完成 ===')

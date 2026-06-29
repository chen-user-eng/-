import sys
sys.path.insert(0, 'scripts')
from oss_utils import get_oss_client_from_config

oss = get_oss_client_from_config()

print('=== OSS数据统计 ===')
print()

dim_files = oss.list_files('data/dim/')
print('维度表文件:', len(dim_files), '个')
for f in dim_files:
    size = f['size'] / 1024 / 1024
    print('  -', f['key'], '({:.2f} MB)'.format(size))

print()
ods_files = oss.list_files('data/ods/')
print('ODS数据文件:', len(ods_files), '个')
total_size = sum(f['size'] for f in ods_files)
print('总大小: {:.2f} MB ({:.2f} GB)'.format(total_size/1024/1024, total_size/1024/1024/1024))

dates = set()
for f in ods_files:
    parts = f['key'].split('/')
    for p in parts:
        if p.startswith('dt='):
            dates.add(p.replace('dt=', ''))
print('覆盖天数:', len(dates), '天')
print('日期范围:', min(dates), '~', max(dates))

print()
ads_files = oss.list_files('data/ads/')
print('ADS数据文件:', len(ads_files), '个')

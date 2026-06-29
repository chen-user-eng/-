import pandas as pd

print('=== 全量数据处理结果验证 ===')
print()

df = pd.read_csv('data/ads/all_index.csv', low_memory=False)

print('数据概览:')
print('  总记录数:', len(df))
print('  日期范围:', df['dt'].min(), '~', df['dt'].max())
print('  覆盖天数:', df['dt'].nunique(), '天')
print()

print('指数类型统计:')
print(df['index_type'].value_counts().to_string())
print()

print('最新一天概览:')
latest = df['dt'].max()
overall = df[(df['index_type'] == 'OVERALL') & (df['dt'] == latest)]
fisher = df[(df['index_type'] == 'FISHER') & (df['dt'] == latest)]
cat_l1 = df[(df['index_type'] == 'CATEGORY_L1') & (df['dt'] == latest)]
sku = df[(df['index_type'] == 'SKU') & (df['dt'] == latest)]

print('  最新日期:', latest)
print('  全网加权指数:', overall['price_index'].values[0])
print('  全网费雪指数:', fisher['price_index'].values[0])
print('  一级类目数:', len(cat_l1))
print('  SKU数:', len(sku))
print()

print('近30天全网指数趋势:')
trend = df[df['index_type'] == 'OVERALL'].tail(30)
for i, row in trend.iterrows():
    print(' ', row['dt'], ':', row['price_index'], '(环比:', row['mom_change_rate'], '%)')

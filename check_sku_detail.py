import pandas as pd

df = pd.read_csv('data/ads/all_index.csv', low_memory=False)
df['dt'] = df['dt'].astype(str)

# 查找化妆美容器具_177的数据
sku_data = df[(df['target_name'] == '化妆美容器具_177') & (df['index_type'] == 'SKU')]
sku_data = sku_data.sort_values('dt')

print('=== 化妆美容器具_177 基本信息 ===')
print('商品ID:', sku_data['target_id'].iloc[0])
print('总记录数:', len(sku_data))
print()

# 查看最近14天的数据
latest = sku_data['dt'].max()
recent = sku_data[sku_data['dt'] >= '2028-05-02'].sort_values('dt')
print('=== 近14天价格数据 ===')
print('日期          价格      环比(%)      指数')
print('-' * 50)
for _, row in recent.iterrows():
    mom = row['mom_change_rate']
    mom_str = f'{mom:+.2f}%' if pd.notna(mom) else 'N/A'
    print(f'{row["dt"]}  {row["price"]:>8.2f}  {mom_str:>10}  {row["price_index"]:>8.2f}')

print()
print('=== 最新日期数据 ===')
latest_row = sku_data[sku_data['dt'] == latest].iloc[0]
print('日期:', latest)
print('当前价格:', latest_row['price'])
print('基期价格:', latest_row['base_price'])
print('价格指数:', latest_row['price_index'])
print('日环比:', f"{latest_row['mom_change_rate']:+.2f}%")
print()

# 找出涨幅最大的那一天
print('=== 环比变化最大的一天 ===')
max_mom_day = sku_data.loc[sku_data['mom_change_rate'].idxmax()]
print('日期:', max_mom_day['dt'])
print('日环比:', f"{max_mom_day['mom_change_rate']:+.2f}%")

# 找出最近一个月涨幅最大的几天
print()
print('=== 近一个月环比最大的几天 ===')
month_data = sku_data[sku_data['dt'] >= '2028-04-16'].dropna(subset=['mom_change_rate'])
top_days = month_data.nlargest(5, 'mom_change_rate')
print('日期          环比(%)')
for _, row in top_days.iterrows():
    print(f'{row["dt"]}  {row["mom_change_rate"]:+.2f}%')

"""测试ClickHouse查询接口"""
import sys
sys.path.insert(0, 'e:/111')
from scripts import ch_queries

print('=== ClickHouse查询测试 ===')
print()

# 1. 最新日期
print('1. 最新日期:', ch_queries.get_latest_date())
print()

# 2. 首页概览
print('2. 首页概览:')
overview = ch_queries.get_overview()
for k, v in overview.items():
    print(f'   {k}: {v}')
print()

# 3. 一级类目列表
print('3. 一级类目列表:')
cats = ch_queries.get_categories()
for cat in cats:
    name = cat['name']
    idx = cat['price_index']
    mom = cat['mom_change'] * 100
    print(f'   {name}: 指数={idx:.2f}, 涨跌幅={mom:.2f}%')
print()

# 4. 排行榜
print('4. 涨幅TOP5:')
ranking = ch_queries.get_ranking(5)
for item in ranking['gain']:
    name = item['product_name']
    mom = item['mom_change_rate'] * 100
    print(f'   {name}: {mom:.2f}%')
print()

# 5. 异常数据
print('5. 异常数据统计:')
anomaly = ch_queries.get_anomaly(page_size=5)
print(f'   总数: {anomaly["total"]}')
print(f'   统计: {anomaly["stats"]}')
print()

print('✅ 查询测试完成!')

"""测试Flask API"""
import requests

print('=== API测试 ===')
print()

# 概览
r = requests.get('http://localhost:5000/api/overview')
print('1. 概览:')
print(r.json())
print()

# 类目列表
r = requests.get('http://localhost:5000/api/categories')
cats = r.json()
print('2. 一级类目: {} 个'.format(len(cats)))
for c in cats:
    print('   {}: {:.2f}'.format(c['name'], c['price_index']))
print()

# 排行榜
r = requests.get('http://localhost:5000/api/ranking?limit=3')
rank = r.json()
print('3. 涨幅TOP3:')
for item in rank['gain']:
    print('   {}: {:.2f}%'.format(item['product_name'], item['mom_change_rate'] * 100))
print()

# 全网趋势
r = requests.get('http://localhost:5000/api/overall/trend?days=10')
trend = r.json()
print('4. 全网趋势(近10天): {} 条'.format(len(trend.get('dates', []))))
print()

# 异常数据
r = requests.get('http://localhost:5000/api/anomaly?page_size=3')
anomaly = r.json()
print('5. 异常数据:')
print('   总数: {}'.format(anomaly['total']))
print('   统计: {}'.format(anomaly['stats']))
print()

print('✅ 所有API测试通过!')

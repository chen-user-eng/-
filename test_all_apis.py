import urllib.request
import json

def fetch(url):
    return json.loads(urllib.request.urlopen(url).read())

print('=== 1. overview ===')
data = fetch('http://localhost:5000/api/overview')
print('日期:', data['date'])
print('全网指数:', data['overall_index'])
print('SKU数:', data['product_count'])
print('类目数:', data['category_count'])
print()

print('=== 2. categories (一级类目) ===')
data = fetch('http://localhost:5000/api/categories')
print('类目数量:', len(data))
for cat in data:
    print(' ', cat['id'], '-', cat['name'], ':', cat['price_index'])
print()

print('=== 3. ranking gain (涨幅TOP10) ===')
data = fetch('http://localhost:5000/api/ranking?type=gain&n=10')
print('SKU数量:', len(data))
for i, item in enumerate(data[:3]):
    print(' ', i+1, '.', item['name'], '-', item['mom_change'], '% -', item['category'])
print()

print('=== 4. ranking loss (跌幅TOP10) ===')
data = fetch('http://localhost:5000/api/ranking?type=loss&n=10')
print('SKU数量:', len(data))
for i, item in enumerate(data[:3]):
    print(' ', i+1, '.', item['name'], '-', item['mom_change'], '% -', item['category'])
print()

print('=== 5. ranking vol (波动TOP50) ===')
data = fetch('http://localhost:5000/api/ranking?type=vol&n=50')
print('SKU数量:', len(data))
print()

print('=== 6. category/trend (用数字ID) ===')
data = fetch('http://localhost:5000/api/category/trend?id=1101000000&days=30')
print('日期数:', len(data.get('dates', [])))
print('类目名称:', data.get('category_name', ''))
print()

print('=== 7. category/skus (用数字ID) ===')
data = fetch('http://localhost:5000/api/category/skus?id=1101000000')
print('SKU数量:', len(data))
if data:
    print('第一个:', data[0]['name'])
print()

print('=== 8. anomaly ===')
data = fetch('http://localhost:5000/api/anomaly')
print('总数:', data['total'])
print()

print('=== 9. sku/search ===')
data = fetch('http://localhost:5000/api/sku/search?q=猪肉')
print('搜索结果:', len(data))
if data:
    print('第一个:', data[0]['name'], '-', data[0]['category'])
print()

print('=== 所有API测试完成 ===')

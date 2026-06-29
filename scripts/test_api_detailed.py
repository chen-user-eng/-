"""详细测试API"""
import requests

print('=== 详细API测试 ===')
print()

tests = [
    ('概览', '/api/overview'),
    ('全网趋势', '/api/overall/trend?days=30'),
    ('类目列表', '/api/categories'),
    ('类目趋势', '/api/category/trend?id=食品&days=30'),
    ('所有类目趋势', '/api/categories/trend?days=90'),
    ('类目SKU', '/api/category/skus?id=食品'),
    ('涨幅排行', '/api/ranking?type=gain&n=10'),
    ('跌幅排行', '/api/ranking?type=loss&n=10'),
    ('异常数据', '/api/anomaly?type=价格突变&page_size=5'),
    ('SKU搜索', '/api/sku/search?q=大米'),
]

for name, url in tests:
    try:
        r = requests.get('http://localhost:5000' + url, timeout=30)
        status = r.status_code
        if status == 200:
            try:
                data = r.json()
                if isinstance(data, list):
                    info = 'list: {} 条'.format(len(data))
                elif isinstance(data, dict):
                    keys = list(data.keys())[:5]
                    info = 'dict keys: {}'.format(keys)
                else:
                    info = str(type(data))
                print('✅ {}: {} - {}'.format(name, status, info))
            except Exception as e:
                print('⚠️  {}: {} - JSON解析失败: {}'.format(name, status, e))
        else:
            print('❌ {}: {} - {}'.format(name, status, r.text[:100]))
    except Exception as e:
        print('❌ {}: 错误 - {}'.format(name, e))

print()
print('测试完成!')

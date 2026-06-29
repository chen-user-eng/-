import urllib.request
import json

# 测试异常数据API
url = 'http://localhost:5000/api/anomaly?date=2028-05-15&page_size=10'
try:
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read())
        print('=== 异常数据API测试 ===')
        print('总数:', data['total'])
        print('当前页:', data['page'])
        print('页大小:', data['page_size'])
        print()
        if data['list']:
            print('最新异常数据（前5条）:')
            for i, item in enumerate(data['list'][:5]):
                print(f"{i+1}. {item.get('product_name', '')} - {item.get('anomaly_type', '')}")
                print(f"   描述: {item.get('anomaly_desc', '')}")
                print(f"   当前价格: {item.get('current_price', '')}, 基础价格: {item.get('base_price', '')}")
                print()
        else:
            print('没有异常数据')
except Exception as e:
    print('请求失败:', e)

# 测试overview中的异常数量
url2 = 'http://localhost:5000/api/overview'
try:
    with urllib.request.urlopen(url2, timeout=10) as response:
        data = json.loads(response.read())
        print('=== Overview API ===')
        print('日期:', data['date'])
        print('异常商品数量:', data['anomaly_count'])
except Exception as e:
    print('请求失败:', e)

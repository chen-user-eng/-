import urllib.request
import json

# 测试异常数据API（最新日期）
url = 'http://localhost:5000/api/anomaly?date=2028-05-15&page_size=3'
try:
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read())
        print('=== 异常数据API测试（2028-05-15）===')
        print('总数:', data['total'])
        print('统计:', data.get('stats', {}))
        print()
        print('前3条数据:')
        for i, item in enumerate(data['list'][:3]):
            pname = item.get('product_name', '')
            atype = item.get('anomaly_type', '')
            adesc = item.get('anomaly_desc', '')
            cprice = item.get('current_price', '')
            cat = item.get('category_l1', '')
            print(str(i+1) + '. ' + pname)
            print('   类型: ' + atype)
            print('   描述: ' + str(adesc))
            print('   当前价格: ' + str(cprice))
            print('   类目: ' + str(cat))
            print()
except Exception as e:
    print('请求失败:', e)
    import traceback
    traceback.print_exc()

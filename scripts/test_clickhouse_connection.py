"""
测试ClickHouse连接
"""
import sys
sys.path.append('e:/111')

from config import CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD
import requests

def test_connection():
    """测试ClickHouse连接"""
    print(f"正在测试连接: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    print(f"用户: {CLICKHOUSE_USER}")
    print("-" * 60)
    
    # 测试基本连接
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/"
    
    try:
        # 测试连接（不指定数据库）
        params = {
            'user': CLICKHOUSE_USER,
            'password': CLICKHOUSE_PASSWORD,
            'query': 'SELECT 1'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            print("✓ 连接成功！")
            print(f"  响应: {response.text.strip()}")
        else:
            print(f"✗ 连接失败，状态码: {response.status_code}")
            print(f"  错误信息: {response.text}")
            return False
            
        # 查询版本
        print("\n正在查询ClickHouse版本...")
        params['query'] = 'SELECT version()'
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            print(f"✓ ClickHouse版本: {response.text.strip()}")
        
        # 查询现有数据库
        print("\n正在查询现有数据库...")
        params['query'] = 'SHOW DATABASES'
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            databases = [db.strip() for db in response.text.strip().split('\n') if db.strip()]
            print(f"✓ 现有数据库: {databases}")
        
        return True
        
    except requests.exceptions.Timeout:
        print("✗ 连接超时")
        print("  可能原因:")
        print("  1. 网络不通（请检查安全组白名单是否包含你的IP）")
        print("  2. 端口错误（默认HTTP端口是8123）")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ 连接错误: {e}")
        print("  可能原因:")
        print("  1. 域名解析失败")
        print("  2. 网络不通")
        return False
    except Exception as e:
        print(f"✗ 未知错误: {e}")
        return False

if __name__ == "__main__":
    test_connection()
"""
初始化ClickHouse：创建数据库和表结构
"""
import sys
sys.path.append('e:/111')

from scripts.clickhouse_utils import ClickHouseClient

def main():
    print("=" * 60)
    print("初始化 ClickHouse 数据库和表结构")
    print("=" * 60)
    
    client = ClickHouseClient()
    if not client.is_connected():
        print("❌ 连接失败，退出")
        return
    
    print("\n📦 创建数据库...")
    client.create_database()
    
    print("\n📋 创建数据表...")
    client.create_tables()
    
    print("\n📊 检查表结构...")
    tables = ['dim_categories', 'dim_products', 'ads_price_index', 'ads_anomaly']
    for table in tables:
        cnt = client.get_table_count(table)
        print(f"  {table}: {cnt} 条记录")
    
    print("\n✅ 初始化完成！")
    client.close()

if __name__ == "__main__":
    main()
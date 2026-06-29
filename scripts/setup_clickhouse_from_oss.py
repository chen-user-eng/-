"""
从 OSS 导入数据到 ClickHouse 本地表
一键执行：建库 -> 建 OSS 外表 -> 建本地表 -> 导入数据
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scripts.clickhouse_utils import get_ch_client


OSS_ENDPOINT = config.OSS_ENDPOINT.replace('https://', '').replace('http://', '')
# 使用内网地址（更快更稳定）
OSS_ENDPOINT_INTERNAL = 'oss-cn-hangzhou-internal.aliyuncs.com'
OSS_ACCESS_ID = config.OSS_ACCESS_KEY_ID
OSS_SECRET = config.OSS_ACCESS_KEY_SECRET
OSS_BUCKET = config.OSS_BUCKET


def create_oss_tables(client):
    """创建 OSS 外部表"""
    print("\n========== 创建 OSS 外部表 ==========")

    # 使用内网地址（更快更稳定）
    endpoint = OSS_ENDPOINT_INTERNAL

    # 先删掉可能存在的旧表
    client.query("DROP TABLE IF EXISTS dim_categories_oss")
    client.query(f"""
        CREATE TABLE dim_categories_oss (
            category_id String,
            category_name String,
            hierarchy Nullable(UInt8),
            parent_id String,
            weight Nullable(Float64),
            base_price Nullable(Float64)
        ) ENGINE = S3(
            'https://{OSS_BUCKET}.{endpoint}/data/dim/categories.csv',
            '{OSS_ACCESS_ID}',
            '{OSS_SECRET}',
            'CSVWithNames'
        )
    """)
    print("  ✅ dim_categories_oss")

    client.query("DROP TABLE IF EXISTS dim_products_oss")
    client.query(f"""
        CREATE TABLE dim_products_oss (
            product_id String,
            category_id String,
            category_id_l2 String,
            category_id_l1 String,
            name String,
            weight Nullable(Float64),
            base_price Nullable(Float64)
        ) ENGINE = S3(
            'https://{OSS_BUCKET}.{endpoint}/data/dim/products.csv',
            '{OSS_ACCESS_ID}',
            '{OSS_SECRET}',
            'CSVWithNames'
        )
    """)
    print("  ✅ dim_products_oss")

    client.query("DROP TABLE IF EXISTS ads_anomaly_oss")
    client.query(f"""
        CREATE TABLE ads_anomaly_oss (
            dt String,
            product_id String,
            product_name String,
            category_l1 String,
            current_price Nullable(Float64),
            base_price Nullable(Float64),
            anomaly_type String,
            anomaly_desc String,
            change_rate Nullable(Float64),
            z_score Nullable(Float64),
            price_ratio Nullable(Float64)
        ) ENGINE = S3(
            'https://{OSS_BUCKET}.{endpoint}/data/ads/anomaly/*.csv',
            '{OSS_ACCESS_ID}',
            '{OSS_SECRET}',
            'CSVWithNames'
        )
    """)
    print("  ✅ ads_anomaly_oss")

    client.query("DROP TABLE IF EXISTS ads_price_index_oss")
    client.query(f"""
        CREATE TABLE ads_price_index_oss (
            dt String,
            index_type String,
            target_id String,
            target_name String,
            price Nullable(Float64),
            base_price Nullable(Float64),
            price_index Nullable(Float64),
            mom_change_rate Nullable(Float64),
            category_id String,
            category_id_l2 String,
            category_id_l1 String,
            category_name String,
            category_l1 String
        ) ENGINE = S3(
            'https://{OSS_BUCKET}.{endpoint}/data/ads/all_index.csv',
            '{OSS_ACCESS_ID}',
            '{OSS_SECRET}',
            'CSVWithNames'
        )
    """)
    print("  ✅ ads_price_index_oss")


def create_local_tables(client):
    """创建本地表"""
    print("\n========== 创建本地表 ==========")

    client.query("""
        CREATE TABLE IF NOT EXISTS dim_categories (
            category_id String,
            category_name String,
            hierarchy UInt8,
            parent_id String,
            weight Float64,
            base_price Float64,
            create_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY category_id
    """)
    print("  ✅ dim_categories")

    client.query("""
        CREATE TABLE IF NOT EXISTS dim_products (
            product_id String,
            category_id String,
            category_id_l2 String,
            category_id_l1 String,
            name String,
            weight Float64,
            base_price Float64,
            create_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY product_id
    """)
    print("  ✅ dim_products")

    client.query("""
        CREATE TABLE IF NOT EXISTS ads_price_index (
            dt String,
            index_type String,
            target_id String,
            target_name String,
            price Float64,
            base_price Float64,
            price_index Float64,
            mom_change_rate Float64,
            category_id String,
            category_id_l2 String,
            category_id_l1 String,
            category_name String,
            category_l1 String,
            create_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (index_type, target_id, dt)
        PARTITION BY index_type
    """)
    print("  ✅ ads_price_index")

    client.query("""
        CREATE TABLE IF NOT EXISTS ads_anomaly (
            dt String,
            product_id String,
            product_name String,
            category_l1 String,
            current_price Float64,
            base_price Float64,
            anomaly_type String,
            anomaly_desc String,
            change_rate Float64,
            z_score Float64,
            price_ratio Float64,
            create_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (dt, product_id)
        PARTITION BY anomaly_type
    """)
    print("  ✅ ads_anomaly")


def import_data(client):
    """从 OSS 外表导入到本地表"""
    print("\n========== 导入数据 ==========")

    import time

    t0 = time.time()
    client.query("INSERT INTO dim_categories SELECT *, now() FROM dim_categories_oss")
    cnt = client.query("SELECT count() as cnt FROM dim_categories")['cnt'].iloc[0]
    print(f"  ✅ dim_categories: {cnt:,} 条 ({time.time()-t0:.1f}s)")

    t0 = time.time()
    client.query("INSERT INTO dim_products SELECT *, now() FROM dim_products_oss")
    cnt = client.query("SELECT count() as cnt FROM dim_products")['cnt'].iloc[0]
    print(f"  ✅ dim_products: {cnt:,} 条 ({time.time()-t0:.1f}s)")

    t0 = time.time()
    client.query("INSERT INTO ads_anomaly SELECT *, now() FROM ads_anomaly_oss")
    cnt = client.query("SELECT count() as cnt FROM ads_anomaly")['cnt'].iloc[0]
    print(f"  ✅ ads_anomaly: {cnt:,} 条 ({time.time()-t0:.1f}s)")

    t0 = time.time()
    client.query("INSERT INTO ads_price_index SELECT *, now() FROM ads_price_index_oss")
    cnt = client.query("SELECT count() as cnt FROM ads_price_index")['cnt'].iloc[0]
    print(f"  ✅ ads_price_index: {cnt:,} 条 ({time.time()-t0:.1f}s)")


def main():
    print("=" * 60)
    print("  ClickHouse 数据初始化（从 OSS 导入）")
    print("=" * 60)

    client = get_ch_client()
    if not client.is_connected():
        print("\n❌ ClickHouse 连接失败，请检查：")
        print("   1. 白名单是否配置")
        print("   2. 用户名密码是否正确")
        print("   3. 网络是否通畅")
        return

    print(f"\n✅ 连接成功，数据库: {config.CLICKHOUSE_DATABASE}")

    client.create_database()

    create_oss_tables(client)
    create_local_tables(client)
    import_data(client)

    print("\n" + "=" * 60)
    print("  ✅ 全部完成！")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    main()

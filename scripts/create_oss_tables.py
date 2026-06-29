"""
创建ClickHouse OSS外部表
使用阿里云OSS引擎读取OSS上的CSV数据
"""
import sys
sys.path.insert(0, 'e:/111')

from scripts.clickhouse_utils import get_ch_client
import config

def main():
    print('=' * 60)
    print('创建 ClickHouse OSS 外部表（阿里云OSS引擎）')
    print('=' * 60)
    
    client = get_ch_client()
    
    # OSS内网endpoint（VPC内访问，更快更免费）
    # 正确格式: oss-cn-hangzhou-internal.aliyuncs.com
    oss_internal_endpoint = config.OSS_ENDPOINT.replace('oss-cn-', 'oss-cn-').replace('.aliyuncs.com', '-internal.aliyuncs.com')
    # 简单直接的方式:
    region = config.OSS_ENDPOINT.split('.')[0].replace('oss-', '')
    oss_internal_endpoint = f'oss-{region}-internal.aliyuncs.com'
    
    print(f'\nOSS Endpoint: {oss_internal_endpoint}')
    print(f'Bucket: {config.OSS_BUCKET}')
    print()
    
    # 先删除旧的表
    print('清理旧的OSS外部表...')
    for table in ['dim_categories_oss', 'dim_products_oss', 'ads_price_index_oss', 'ads_anomaly_oss']:
        try:
            client.client.command(f'DROP TABLE IF EXISTS {table}')
            print(f'  已删除 {table}')
        except:
            pass
    
    print()
    
    # 1. 创建类目维度表
    print('1. 创建 dim_categories_oss 外部表...')
    sql = f"""
    CREATE TABLE dim_categories_oss
    (
        category_id String,
        category String,
        hierarchy Int32,
        parent String,
        weight Float64,
        price Float64
    )
    ENGINE = OSS(
        'https://{config.OSS_BUCKET}.{oss_internal_endpoint}/data/dim/categories.csv',
        '{config.OSS_ACCESS_KEY_ID}',
        '{config.OSS_ACCESS_KEY_SECRET}',
        'CSVWithNames'
    )
    """
    try:
        client.client.command(sql)
        print('   ✅ 创建成功')
        result = client.client.query_df('SELECT count() as cnt FROM dim_categories_oss')
        print(f'   记录数: {int(result["cnt"].iloc[0])}')
    except Exception as e:
        print(f'   ❌ 失败: {e}')
    
    # 2. 创建商品维度表
    print('\n2. 创建 dim_products_oss 外部表...')
    sql = f"""
    CREATE TABLE dim_products_oss
    (
        product_id String,
        category_id String,
        name String,
        weight Float64,
        price Float64
    )
    ENGINE = OSS(
        'https://{config.OSS_BUCKET}.{oss_internal_endpoint}/data/dim/products.csv',
        '{config.OSS_ACCESS_KEY_ID}',
        '{config.OSS_ACCESS_KEY_SECRET}',
        'CSVWithNames'
    )
    """
    try:
        client.client.command(sql)
        print('   ✅ 创建成功')
        result = client.client.query_df('SELECT count() as cnt FROM dim_products_oss')
        print(f'   记录数: {int(result["cnt"].iloc[0])}')
    except Exception as e:
        print(f'   ❌ 失败: {e}')
    
    # 3. 创建价格指数表
    print('\n3. 创建 ads_price_index_oss 外部表...')
    sql = f"""
    CREATE TABLE ads_price_index_oss
    (
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
        category_l1 String
    )
    ENGINE = OSS(
        'https://{config.OSS_BUCKET}.{oss_internal_endpoint}/data/ads/all_index.csv',
        '{config.OSS_ACCESS_KEY_ID}',
        '{config.OSS_ACCESS_KEY_SECRET}',
        'CSVWithNames'
    )
    """
    try:
        client.client.command(sql)
        print('   ✅ 创建成功')
        # 尝试查询（可能因为文件未上传完而失败）
        try:
            result = client.client.query_df('SELECT count() as cnt FROM ads_price_index_oss LIMIT 1')
            print(f'   记录数: {int(result["cnt"].iloc[0])}')
        except Exception as e:
            print(f'   ⚠️  查询失败（可能文件未上传完）: {str(e)[:80]}')
    except Exception as e:
        print(f'   ❌ 失败: {e}')
    
    # 4. 创建异常数据表
    print('\n4. 创建 ads_anomaly_oss 外部表...')
    sql = f"""
    CREATE TABLE ads_anomaly_oss
    (
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
        dt String
    )
    ENGINE = OSS(
        'https://{config.OSS_BUCKET}.{oss_internal_endpoint}/data/ads/anomaly/*.csv',
        '{config.OSS_ACCESS_KEY_ID}',
        '{config.OSS_ACCESS_KEY_SECRET}',
        'CSVWithNames'
    )
    """
    try:
        client.client.command(sql)
        print('   ✅ 创建成功')
        result = client.client.query_df('SELECT count() as cnt FROM ads_anomaly_oss')
        print(f'   记录数: {int(result["cnt"].iloc[0])}')
    except Exception as e:
        print(f'   ❌ 失败: {e}')
    
    print('\n' + '=' * 60)
    print('OSS外部表创建完成!')
    print('=' * 60)
    
    client.close()

if __name__ == "__main__":
    main()

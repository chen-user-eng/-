"""
数据导入脚本
将本地CSV数据导入到ClickHouse
"""
import os
import sys
import pandas as pd
import time
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scripts.clickhouse_utils import get_ch_client, init_clickhouse


def detect_encoding(filepath):
    """检测文件编码"""
    try:
        pd.read_csv(filepath, nrows=5, encoding='utf-8')
        return 'utf-8'
    except:
        try:
            pd.read_csv(filepath, nrows=5, encoding='gbk')
            return 'gbk'
        except:
            return 'utf-8'


def import_dim_tables():
    """导入维度表到ClickHouse"""
    print("\n" + "="*60)
    print("导入维度表")
    print("="*60)

    client = get_ch_client()
    dim_dir = os.path.join(config.LOCAL_DATA_DIR, 'dim')

    # 导入类目维度表
    cat_file = os.path.join(dim_dir, 'categories.csv')
    if os.path.exists(cat_file):
        print(f"\n导入 categories.csv ...")
        encoding = detect_encoding(cat_file)
        print(f"  编码: {encoding}")
        df = pd.read_csv(cat_file, low_memory=False, encoding=encoding)
        print(f"  原始列: {df.columns.tolist()}")
        print(f"  记录数: {len(df):,}")

        # 列名映射
        df_mapped = pd.DataFrame()
        df_mapped['category_id'] = df['category_id'].astype(str)
        df_mapped['category_name'] = df['category'].astype(str)
        df_mapped['hierarchy'] = df['hierarchy'].astype(int)
        df_mapped['parent_id'] = df['parent'].fillna('').astype(str)
        df_mapped['weight'] = df['weight'].fillna(0).astype(float)
        df_mapped['base_price'] = df['price'].fillna(0).astype(float)

        client.truncate_table('dim_categories')
        client.insert_dataframe('dim_categories', df_mapped)
        print("  ✅ 完成")

    # 导入商品维度表
    prod_file = os.path.join(dim_dir, 'products.csv')
    if os.path.exists(prod_file):
        print(f"\n导入 products.csv ...")
        encoding = detect_encoding(prod_file)
        print(f"  编码: {encoding}")
        df = pd.read_csv(prod_file, low_memory=False, encoding=encoding)
        print(f"  原始列: {df.columns.tolist()}")
        print(f"  记录数: {len(df):,}")

        # 列名映射
        df_mapped = pd.DataFrame()
        df_mapped['product_id'] = df['product_id'].astype(str)
        df_mapped['category_id'] = df['category_id'].astype(str)
        df_mapped['category_id_l2'] = ''
        df_mapped['category_id_l1'] = ''
        df_mapped['name'] = df['name'].astype(str)
        df_mapped['weight'] = df['weight'].fillna(0).astype(float)
        df_mapped['base_price'] = df['price'].fillna(0).astype(float)

        client.truncate_table('dim_products')
        client.insert_dataframe('dim_products', df_mapped)
        print("  ✅ 完成")


def import_ads_data():
    """导入ADS层数据到ClickHouse"""
    print("\n" + "="*60)
    print("导入ADS层价格指数数据")
    print("="*60)

    client = get_ch_client()
    ads_dir = os.path.join(config.LOCAL_DATA_DIR, 'ads')

    index_file = os.path.join(ads_dir, 'all_index.csv')
    if os.path.exists(index_file):
        print(f"\n导入 all_index.csv ...")
        encoding = detect_encoding(index_file)
        print(f"  编码: {encoding}")
        print("  正在读取CSV...")
        df = pd.read_csv(index_file, low_memory=False, encoding=encoding)
        print(f"  原始列: {df.columns.tolist()}")
        print(f"  记录数: {len(df):,}")

        # 列名映射
        df_mapped = pd.DataFrame()
        df_mapped['dt'] = df['dt'].astype(str)
        df_mapped['index_type'] = df['index_type'].astype(str)
        df_mapped['target_id'] = df['target_id'].astype(str)
        df_mapped['target_name'] = df['target_name'].astype(str)
        df_mapped['price'] = df['price'].fillna(0).astype(float)
        df_mapped['base_price'] = df['base_price'].fillna(0).astype(float)
        df_mapped['price_index'] = df['price_index'].fillna(0).astype(float)
        df_mapped['mom_change_rate'] = df['mom_change_rate'].fillna(0).astype(float)
        df_mapped['category_id'] = df['category_id'].fillna('').astype(str)
        df_mapped['category_id_l2'] = df['category_id_l2'].fillna('').astype(str)
        df_mapped['category_id_l1'] = df['category_id_l1'].fillna('').astype(str)
        df_mapped['category_name'] = df['category_name'].fillna('').astype(str)
        df_mapped['category_l1'] = df['category_l1'].fillna('').astype(str)

        client.truncate_table('ads_price_index')

        print("  正在导入ClickHouse...")
        start_time = time.time()
        client.insert_dataframe('ads_price_index', df_mapped, batch_size=200000)
        elapsed = time.time() - start_time

        count = client.get_table_count('ads_price_index')
        print(f"  ✅ 完成! 共 {count:,} 条, 耗时 {elapsed:.1f}秒")


def import_anomaly_data():
    """导入异常数据到ClickHouse"""
    print("\n" + "="*60)
    print("导入异常数据")
    print("="*60)

    client = get_ch_client()
    anomaly_dir = os.path.join(config.LOCAL_DATA_DIR, 'ads', 'anomaly')

    if not os.path.exists(anomaly_dir):
        print("  异常数据目录不存在，跳过")
        return

    all_anomaly = []
    files = sorted([f for f in os.listdir(anomaly_dir) if f.endswith('.csv')])
    print(f"  发现 {len(files)} 个异常数据文件")

    for i, f in enumerate(files):
        filepath = os.path.join(anomaly_dir, f)
        encoding = detect_encoding(filepath)
        
        # 从文件名提取日期
        match = re.search(r'anomaly_(\d{4}-\d{2}-\d{2})', f)
        dt = match.group(1) if match else ''
        
        df = pd.read_csv(filepath, low_memory=False, encoding=encoding)
        df['dt'] = dt
        all_anomaly.append(df)
        
        if (i + 1) % 10 == 0:
            print(f"  已读取 {i+1}/{len(files)} 个文件")

    if all_anomaly:
        combined = pd.concat(all_anomaly, ignore_index=True)
        print(f"  总记录数: {len(combined):,}")
        print(f"  原始列: {combined.columns.tolist()}")

        # 列名映射
        df_mapped = pd.DataFrame()
        df_mapped['dt'] = combined['dt'].astype(str)
        df_mapped['product_id'] = combined['product_id'].astype(str)
        df_mapped['product_name'] = combined['product_name'].astype(str)
        df_mapped['category_l1'] = combined['category_l1'].fillna('').astype(str)
        df_mapped['current_price'] = combined['current_price'].fillna(0).astype(float)
        df_mapped['base_price'] = combined['base_price'].fillna(0).astype(float)
        df_mapped['anomaly_type'] = combined['anomaly_type'].fillna('').astype(str)
        df_mapped['anomaly_desc'] = combined['anomaly_desc'].fillna('').astype(str)
        df_mapped['change_rate'] = combined['change_rate'].fillna(0).astype(float)
        df_mapped['z_score'] = combined['z_score'].fillna(0).astype(float)
        df_mapped['price_ratio'] = combined['price_ratio'].fillna(0).astype(float)

        client.truncate_table('ads_anomaly')
        client.insert_dataframe('ads_anomaly', df_mapped, batch_size=200000)
        print("  ✅ 完成")


def main():
    print("\n" + "="*60)
    print("ClickHouse数据导入工具")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n连接ClickHouse...")
    if not init_clickhouse():
        print("❌ ClickHouse连接失败，请检查配置")
        return

    import_dim_tables()
    import_ads_data()
    import_anomaly_data()

    client = get_ch_client()
    print("\n" + "="*60)
    print("导入完成! 当前数据量:")
    print("="*60)
    print(f"  dim_categories:   {client.get_table_count('dim_categories'):>12,} 条")
    print(f"  dim_products:      {client.get_table_count('dim_products'):>12,} 条")
    print(f"  ads_price_index:  {client.get_table_count('ads_price_index'):>12,} 条")
    print(f"  ads_anomaly:      {client.get_table_count('ads_anomaly'):>12,} 条")
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    client.close()


if __name__ == "__main__":
    main()

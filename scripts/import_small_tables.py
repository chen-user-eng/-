"""导入维度表和异常数据（小表）"""
import sys
sys.path.insert(0, 'e:/111')

from scripts.clickhouse_utils import get_ch_client
import pandas as pd
import os
import config
import re

def main():
    client = get_ch_client()

    # 导入categories
    print('\n=== 导入 dim_categories ===')
    cat_file = os.path.join(config.LOCAL_DATA_DIR, 'dim', 'categories.csv')
    df = pd.read_csv(cat_file, low_memory=False, encoding='gbk')
    print(f'记录数: {len(df)}')
    df_mapped = pd.DataFrame()
    df_mapped['category_id'] = df['category_id'].astype(str)
    df_mapped['category_name'] = df['category'].astype(str)
    df_mapped['hierarchy'] = df['hierarchy'].astype(int)
    df_mapped['parent_id'] = df['parent'].fillna('').astype(str)
    df_mapped['weight'] = df['weight'].fillna(0).astype(float)
    df_mapped['base_price'] = df['price'].fillna(0).astype(float)
    client.truncate_table('dim_categories')
    client.insert_dataframe('dim_categories', df_mapped)
    cnt = client.get_table_count('dim_categories')
    print(f'dim_categories 最终行数: {cnt}')

    # 导入products
    print('\n=== 导入 dim_products ===')
    prod_file = os.path.join(config.LOCAL_DATA_DIR, 'dim', 'products.csv')
    df = pd.read_csv(prod_file, low_memory=False, encoding='gbk')
    print(f'记录数: {len(df)}')
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
    cnt = client.get_table_count('dim_products')
    print(f'dim_products 最终行数: {cnt}')

    # 导入异常数据
    print('\n=== 导入 ads_anomaly ===')
    anomaly_dir = os.path.join(config.LOCAL_DATA_DIR, 'ads', 'anomaly')
    files = sorted([f for f in os.listdir(anomaly_dir) if f.endswith('.csv')])
    print(f'发现 {len(files)} 个异常数据文件')
    all_anomaly = []
    for f in files:
        filepath = os.path.join(anomaly_dir, f)
        match = re.search(r'anomaly_(\d{4}-\d{2}-\d{2})', f)
        dt = match.group(1) if match else ''
        df = pd.read_csv(filepath, low_memory=False)
        df['dt'] = dt
        all_anomaly.append(df)

    combined = pd.concat(all_anomaly, ignore_index=True)
    print(f'总记录数: {len(combined)}')
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
    client.insert_dataframe('ads_anomaly', df_mapped, batch_size=50000)
    cnt = client.get_table_count('ads_anomaly')
    print(f'ads_anomaly 最终行数: {cnt}')

    client.close()
    print('\n✅ 维度表和异常数据导入完成!')

if __name__ == '__main__':
    main()

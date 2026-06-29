"""测试价格指数导入速度"""
import sys
sys.path.insert(0, 'e:/111')

from scripts.clickhouse_utils import get_ch_client
import pandas as pd
import os
import config
import time

def main():
    client = get_ch_client()

    # 先读取前100万条测试速度
    index_file = os.path.join(config.LOCAL_DATA_DIR, 'ads', 'all_index.csv')
    print(f'读取前100万条数据...')
    start_read = time.time()
    df = pd.read_csv(index_file, nrows=1000000, low_memory=False)
    read_time = time.time() - start_read
    print(f'读取完成，耗时: {read_time:.1f}秒, 记录数: {len(df):,}')

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

    print(f'\n开始导入100万条到ClickHouse...')
    start_import = time.time()
    client.insert_dataframe('ads_price_index', df_mapped, batch_size=200000)
    import_time = time.time() - start_import

    cnt = client.get_table_count('ads_price_index')
    print(f'\n导入完成!')
    print(f'  导入耗时: {import_time:.1f}秒')
    print(f'  导入速度: {1000000/import_time:,.0f} 条/秒')
    print(f'  当前表行数: {cnt:,}')
    
    total_records = 26287457
    est_time = total_records / (1000000 / import_time)
    print(f'  预计全部2628万条耗时: {est_time/60:.1f} 分钟')

    client.close()

if __name__ == '__main__':
    main()

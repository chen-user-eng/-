"""完整导入价格指数数据 - 小批量重试版"""
import sys
sys.path.insert(0, 'e:/111')

from scripts.clickhouse_utils import get_ch_client
import pandas as pd
import os
import config
import time

def insert_with_retry(client, table, df, max_retries=3):
    """带重试的插入"""
    for attempt in range(max_retries):
        try:
            client.insert_df(table, df)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f'    插入失败 (尝试 {attempt+1}/{max_retries}): {e}')
                print(f'    2秒后重试...')
                time.sleep(2)
            else:
                print(f'    插入失败，已重试 {max_retries} 次: {e}')
                return False
    return False

def main():
    client = get_ch_client()

    index_file = os.path.join(config.LOCAL_DATA_DIR, 'ads', 'all_index.csv')
    
    # 清空表
    print('清空 ads_price_index 表...')
    client.truncate_table('ads_price_index')
    
    total = 26287457
    print(f'总记录数: {total:,}')
    
    # 分批读取和导入 - 每批50万条
    batch_size = 500000
    start_time = time.time()
    processed = 0
    
    print(f'\n开始导入，每批 {batch_size:,} 条...')
    
    for chunk in pd.read_csv(index_file, chunksize=batch_size, low_memory=False):
        # 列名映射
        df_mapped = pd.DataFrame()
        df_mapped['dt'] = chunk['dt'].astype(str)
        df_mapped['index_type'] = chunk['index_type'].astype(str)
        df_mapped['target_id'] = chunk['target_id'].astype(str)
        df_mapped['target_name'] = chunk['target_name'].astype(str)
        df_mapped['price'] = chunk['price'].fillna(0).astype(float)
        df_mapped['base_price'] = chunk['base_price'].fillna(0).astype(float)
        df_mapped['price_index'] = chunk['price_index'].fillna(0).astype(float)
        df_mapped['mom_change_rate'] = chunk['mom_change_rate'].fillna(0).astype(float)
        df_mapped['category_id'] = chunk['category_id'].fillna('').astype(str)
        df_mapped['category_id_l2'] = chunk['category_id_l2'].fillna('').astype(str)
        df_mapped['category_id_l1'] = chunk['category_id_l1'].fillna('').astype(str)
        df_mapped['category_name'] = chunk['category_name'].fillna('').astype(str)
        df_mapped['category_l1'] = chunk['category_l1'].fillna('').astype(str)
        
        # 导入（带重试）
        batch_start = time.time()
        success = insert_with_retry(client.client, 'ads_price_index', df_mapped)
        batch_time = time.time() - batch_start
        
        if not success:
            print(f'  ❌ 批次导入失败，已处理 {processed:,} 条')
            break
        
        processed += len(chunk)
        elapsed = time.time() - start_time
        speed = processed / elapsed
        remaining = (total - processed) / speed
        
        print(f'  已导入 {processed:,}/{total:,} ({processed/total*100:.1f}%) '
              f'| 速度: {speed:,.0f}条/秒 '
              f'| 剩余: {remaining/60:.1f}分钟')
    
    total_time = time.time() - start_time
    cnt = client.get_table_count('ads_price_index')
    
    print(f'\n✅ 导入完成!')
    print(f'  总记录数: {cnt:,}')
    print(f'  总耗时: {total_time/60:.1f} 分钟')
    if total_time > 0:
        print(f'  平均速度: {total/total_time:,.0f} 条/秒')

    client.close()

if __name__ == '__main__':
    main()

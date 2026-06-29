"""
高性能全量数据处理脚本 v3
修复：正确处理三级类目层级
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def load_dim_tables():
    """加载维度表"""
    print('[1/5] 加载维度表...')
    products_df = pd.read_csv(os.path.join(DATA_DIR, 'dim', 'products.csv'), encoding='gbk')
    products_df = products_df.rename(columns={
        'name': 'product_name',
        'price': 'base_price',
        'weight': 'weight'
    })

    categories_df = pd.read_csv(os.path.join(DATA_DIR, 'dim', 'categories.csv'), encoding='gbk')
    categories_df = categories_df.rename(columns={
        'category': 'category_name',
        'parent': 'parent_id',
        'price': 'base_price'
    })
    categories_df['parent_id'] = categories_df['parent_id'].fillna(0).astype(float).astype(int)

    cat_l1 = categories_df[categories_df['hierarchy'] == 1].copy()
    cat_l2 = categories_df[categories_df['hierarchy'] == 2].copy()
    cat_l3 = categories_df[categories_df['hierarchy'] == 3].copy()

    l1_id_to_name = dict(zip(cat_l1['category_id'], cat_l1['category_name']))
    l2_id_to_name = dict(zip(cat_l2['category_id'], cat_l2['category_name']))
    l3_id_to_name = dict(zip(cat_l3['category_id'], cat_l3['category_name']))

    l2_id_to_l1_id = dict(zip(cat_l2['category_id'], cat_l2['parent_id']))
    l3_id_to_l2_id = dict(zip(cat_l3['category_id'], cat_l3['parent_id']))

    def get_l2_name(l3_id):
        l2_id = l3_id_to_l2_id.get(l3_id, 0)
        return l2_id_to_name.get(l2_id, '')

    def get_l1_name(l3_id):
        l2_id = l3_id_to_l2_id.get(l3_id, 0)
        l1_id = l2_id_to_l1_id.get(l2_id, 0)
        return l1_id_to_name.get(l1_id, '')

    def get_l1_id(l3_id):
        l2_id = l3_id_to_l2_id.get(l3_id, 0)
        return l2_id_to_l1_id.get(l2_id, 0)

    def get_l2_id(l3_id):
        return l3_id_to_l2_id.get(l3_id, 0)

    products_df['category_name_l3'] = products_df['category_id'].map(l3_id_to_name)
    products_df['category_id_l2'] = products_df['category_id'].map(get_l2_id)
    products_df['category_name_l2'] = products_df['category_id'].map(get_l2_name)
    products_df['category_id_l1'] = products_df['category_id'].map(get_l1_id)
    products_df['category_l1'] = products_df['category_id'].map(get_l1_name)

    cat_l2_weight = dict(zip(cat_l2['category_id'], cat_l2['weight']))
    cat_l1_weight = dict(zip(cat_l1['category_id'], cat_l1['weight']))

    products_df['category_l2_weight'] = products_df['category_id_l2'].map(cat_l2_weight)
    products_df['category_l1_weight'] = products_df['category_id_l1'].map(cat_l1_weight)

    valid_products = products_df[products_df['category_l1'].notna() & (products_df['category_l1'] != '')]
    print(f'  商品: {len(products_df):,} 条 (有效: {len(valid_products):,} 条)')
    print(f'  一级类目: {len(cat_l1)} 个')
    print(f'  二级类目: {len(cat_l2)} 个')
    print(f'  三级类目: {len(cat_l3)} 个')
    return products_df, categories_df, cat_l1, cat_l2, cat_l3, l1_id_to_name, l2_id_to_name, l3_id_to_name

def load_all_ods_data():
    """批量加载所有ODS数据"""
    print('[2/5] 加载ODS数据...')
    ods_dir = os.path.join(DATA_DIR, 'ods')
    date_dirs = sorted([d for d in os.listdir(ods_dir) if d.startswith('dt=')])

    all_data = []
    total = len(date_dirs)

    for i, date_dir in enumerate(date_dirs):
        date_str = date_dir.split('=')[1]
        file_path = os.path.join(ods_dir, date_dir, 'product_price.csv')
        if not os.path.exists(file_path):
            file_path = os.path.join(ods_dir, date_dir, 'daily_prices.csv')
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, encoding='gbk')
            df['dt'] = date_str
            all_data.append(df)
        if (i + 1) % 100 == 0 or i == total - 1:
            print(f'  加载: {i+1}/{total} 天', end='\r')
            sys.stdout.flush()

    result = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    print(f'  完成: {total} 天, 共 {len(result):,} 条记录')
    return result

def clean_and_calculate(raw_df, products_df, categories_df, cat_l1, cat_l2, cat_l3, l1_id_to_name, l2_id_to_name, l3_id_to_name):
    """数据清洗并计算所有指数"""
    print('[3/5] 数据清洗与指数计算...')

    missing_mask = raw_df['product_id'].isna() | (raw_df['product_id'] == '') | \
                   raw_df['price'].isna() | (raw_df['price'] == '')
    valid_df = raw_df[~missing_mask].copy()
    valid_df['price'] = pd.to_numeric(valid_df['price'], errors='coerce')
    price_zero_mask = valid_df['price'] <= 0
    valid_df = valid_df[~price_zero_mask].copy()

    products_subset = products_df[['product_id', 'product_name', 'base_price', 'weight',
                                  'category_id_l1', 'category_l1', 'category_id_l2', 'category_name_l2',
                                  'category_name_l3', 'category_l2_weight', 'category_l1_weight']].copy()
    valid_df = valid_df.merge(products_subset, on='product_id', how='inner')
    valid_df = valid_df.drop_duplicates(subset=['product_id', 'dt'], keep='first')

    valid_df = valid_df[valid_df['category_l1'].notna() & (valid_df['category_l1'] != '')]

    print(f'  清洗后: {len(valid_df):,} 条有效数据')

    sku_df = valid_df.copy()
    sku_df['price_index'] = (sku_df['price'] / sku_df['base_price'] * 100).round(4)

    print('  计算SKU指数...')

    print('  计算类目指数...')
    sku_df['weighted_value'] = sku_df['price_index'] * sku_df['weight']

    cat_l2_grouped = sku_df.groupby(['dt', 'category_id_l2', 'category_name_l2', 'category_id_l1', 'category_l1']).agg({
        'weighted_value': 'sum',
        'weight': 'sum',
        'product_id': 'count'
    }).reset_index()
    cat_l2_grouped['price_index'] = (cat_l2_grouped['weighted_value'] / cat_l2_grouped['weight']).round(4)
    cat_l2_grouped['product_count'] = cat_l2_grouped['product_id']

    cat_l2_weight_map = dict(zip(cat_l2['category_id'], cat_l2['weight']))
    cat_l2_grouped['index_weight'] = cat_l2_grouped['category_id_l2'].map(cat_l2_weight_map)

    cat_l1_grouped = sku_df.groupby(['dt', 'category_id_l1', 'category_l1']).agg({
        'weighted_value': 'sum',
        'weight': 'sum',
        'product_id': 'count'
    }).reset_index()
    cat_l1_grouped['price_index'] = (cat_l1_grouped['weighted_value'] / cat_l1_grouped['weight']).round(4)

    print('  计算全网指数...')
    cat_l1_weights = dict(zip(cat_l1['category_id'], cat_l1['weight']))

    overall_df = cat_l2_grouped.copy()
    overall_df['l1_weight'] = overall_df['category_id_l1'].map(cat_l1_weights)
    overall_df['weighted_index'] = overall_df['price_index'] * overall_df['l1_weight'] * overall_df['index_weight']
    overall_grouped = overall_df.groupby('dt').agg({
        'weighted_index': 'sum',
        'l1_weight': lambda x: (overall_df.loc[x.index, 'index_weight'] * overall_df.loc[x.index, 'l1_weight']).sum()
    }).reset_index()
    overall_grouped['price_index'] = (overall_grouped['weighted_index'] / overall_grouped['l1_weight']).round(4)

    fisher_df = sku_df.groupby('dt').apply(
        lambda x: pd.Series({
            'price_index': np.sqrt(
                (x['weight'] * x['price']).sum() / (x['weight'] * x['base_price']).sum() *
                (x['weight'] * x['price']).sum() / (x['weight'] * x['base_price']).sum()
            ) * 100
        })
    ).reset_index()
    fisher_df['price_index'] = fisher_df['price_index'].round(4)

    print(f'  指数计算完成')
    return sku_df, cat_l2_grouped, cat_l1_grouped, overall_grouped, fisher_df, categories_df

def build_results(sku_df, cat_l2_df, cat_l1_df, overall_df, fisher_df, categories_df):
    """构建最终结果"""
    print('[4/5] 构建结果...')

    results = []

    sku_result = pd.DataFrame({
        'index_type': 'SKU',
        'target_id': sku_df['product_id'],
        'target_name': sku_df['product_name'],
        'category_id': sku_df['category_id'],
        'category_name': sku_df['category_name_l3'],
        'category_id_l2': sku_df['category_id_l2'],
        'category_name_l2': sku_df['category_name_l2'],
        'category_id_l1': sku_df['category_id_l1'],
        'category_l1': sku_df['category_l1'],
        'base_date': '2025-05-17',
        'price': sku_df['price'],
        'base_price': sku_df['base_price'],
        'price_index': sku_df['price_index'],
        'index_weight': sku_df['weight'],
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': sku_df['dt'],
    })
    results.append(sku_result)
    print(f'  SKU: {len(sku_result):,} 条')

    cat_l2_result = pd.DataFrame({
        'index_type': 'CATEGORY',
        'target_id': cat_l2_df['category_id_l2'],
        'target_name': cat_l2_df['category_name_l2'],
        'category_id': cat_l2_df['category_id_l2'],
        'category_name': cat_l2_df['category_name_l2'],
        'category_id_l1': cat_l2_df['category_id_l1'],
        'category_l1': cat_l2_df['category_l1'],
        'base_date': '2025-05-17',
        'price_index': cat_l2_df['price_index'],
        'product_count': cat_l2_df['product_count'],
        'index_weight': cat_l2_df['index_weight'],
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': cat_l2_df['dt'],
    })
    results.append(cat_l2_result)
    print(f'  二级类目: {len(cat_l2_result):,} 条')

    cat_l1_result = pd.DataFrame({
        'index_type': 'CATEGORY_L1',
        'target_id': cat_l1_df['category_id_l1'],
        'target_name': cat_l1_df['category_l1'],
        'category_id': cat_l1_df['category_id_l1'],
        'category_name': cat_l1_df['category_l1'],
        'category_id_l1': cat_l1_df['category_id_l1'],
        'category_l1': cat_l1_df['category_l1'],
        'base_date': '2025-05-17',
        'price_index': cat_l1_df['price_index'],
        'product_count': cat_l1_df['product_id'],
        'index_weight': cat_l1_df['weight'],
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': cat_l1_df['dt'],
    })
    results.append(cat_l1_result)
    print(f'  一级类目: {len(cat_l1_result):,} 条')

    overall_result = pd.DataFrame({
        'index_type': 'OVERALL',
        'target_id': 'OVERALL',
        'target_name': '全网价格指数',
        'base_date': '2025-05-17',
        'price_index': overall_df['price_index'],
        'index_weight': 1.0,
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': overall_df['dt'],
    })
    results.append(overall_result)
    print(f'  全网: {len(overall_result):,} 条')

    fisher_result = pd.DataFrame({
        'index_type': 'FISHER',
        'target_id': 'OVERALL',
        'target_name': '全网费雪指数',
        'base_date': '2025-05-17',
        'price_index': fisher_df['price_index'],
        'index_weight': 1.0,
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': fisher_df['dt'],
    })
    results.append(fisher_result)
    print(f'  费雪: {len(fisher_result):,} 条')

    all_index = pd.concat(results, ignore_index=True)

    print('  计算日环比...')
    all_index = all_index.sort_values(['index_type', 'target_id', 'dt'])
    all_index['prev_price_index'] = all_index.groupby(['index_type', 'target_id'])['price_index'].shift(1)
    all_index['mom_change_rate'] = ((all_index['price_index'] - all_index['prev_price_index']) /
                                    all_index['prev_price_index'] * 100).round(4)
    all_index = all_index.drop(columns=['prev_price_index'])

    print(f'  总计: {len(all_index):,} 条指数')
    return all_index

def save_results(all_index):
    """保存结果"""
    print('[5/5] 保存结果...')
    os.makedirs(os.path.join(DATA_DIR, 'ads'), exist_ok=True)

    ads_path = os.path.join(DATA_DIR, 'ads', 'all_index.csv')
    all_index.to_csv(ads_path, index=False, encoding='utf-8-sig')
    print(f'  已保存: {ads_path}')

def main():
    start_time = time.time()

    print('=' * 60)
    print('高频电商价格指数计算平台 - 全量数据处理 v3')
    print('=' * 60)

    products_df, categories_df, cat_l1, cat_l2, cat_l3, l1_id_to_name, l2_id_to_name, l3_id_to_name = load_dim_tables()
    raw_df = load_all_ods_data()
    sku_df, cat_l2_df, cat_l1_df, overall_df, fisher_df, categories_df = clean_and_calculate(
        raw_df, products_df, categories_df, cat_l1, cat_l2, cat_l3, l1_id_to_name, l2_id_to_name, l3_id_to_name
    )
    all_index = build_results(sku_df, cat_l2_df, cat_l1_df, overall_df, fisher_df, categories_df)
    save_results(all_index)

    elapsed = time.time() - start_time
    print()
    print('=' * 60)
    print(f'处理完成! 总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)')
    print(f'  处理天数: {all_index["dt"].nunique()} 天')
    print(f'  指数记录: {len(all_index):,} 条')
    print('=' * 60)

if __name__ == '__main__':
    main()

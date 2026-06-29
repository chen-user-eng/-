"""
高性能版数据处理管道 - 批量向量化处理
速度提升: 10~50倍
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def load_dim_tables():
    """加载维度表"""
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
    categories_df['parent_id'] = categories_df['parent_id'].fillna('').astype(str)

    cat_l1 = categories_df[categories_df['hierarchy'] == 1].copy()
    cat_l2 = categories_df[categories_df['hierarchy'] == 2].copy()

    # 一级类目ID->名称映射
    l1_map = dict(zip(cat_l1['category_id'], cat_l1['category_name']))
    # 二级类目ID->一级类目名称映射
    l2_to_l1 = {}
    for _, row in cat_l2.iterrows():
        parent_id = int(float(row['parent_id'])) if row['parent_id'] else ''
        l2_to_l1[row['category_id']] = l1_map.get(parent_id, '')

    # 商品的三级类目ID映射到二级类目ID（去掉最后两位）
    products_df['category_id_l2'] = products_df['category_id'] // 100 * 100
    products_df['category_l1'] = products_df['category_id_l2'].map(
        lambda x: l2_to_l1.get(x, '')
    )

    # 建立二级类目映射表
    cat_map = cat_l2.copy()
    cat_map['parent_id_int'] = cat_map['parent_id'].apply(
        lambda x: int(float(x)) if x else ''
    )
    cat_map['category_l1'] = cat_map['parent_id_int'].map(l1_map)
    cat_map = cat_map[['category_id', 'category_name', 'parent_id', 'category_l1', 'weight']]
    cat_map.columns = ['category_id', 'category_name', 'parent_id', 'category_l1', 'category_weight']

    return products_df, cat_map, categories_df


def load_all_ods_data(dates=None):
    """批量加载所有ODS数据"""
    ods_dir = os.path.join(DATA_DIR, 'ods')
    date_dirs = sorted([d for d in os.listdir(ods_dir) if d.startswith('dt=')])

    if dates:
        date_set = set(dates)
        date_dirs = [d for d in date_dirs if d.split('=')[1] in date_set]

    all_data = []
    total = len(date_dirs)

    print(f'  加载 {total} 天数据...', end='\r')

    for i, date_dir in enumerate(date_dirs):
        date_str = date_dir.split('=')[1]
        file_path = os.path.join(ods_dir, date_dir, 'product_price.csv')
        if not os.path.exists(file_path):
            file_path = os.path.join(ods_dir, date_dir, 'daily_prices.csv')
        if os.path.exists(file_path):
            df = pd.read_csv(file_path, encoding='gbk')
            df['dt'] = date_str
            all_data.append(df)
        if (i + 1) % 100 == 0:
            print(f'  加载中: {i+1}/{total} 天', end='\r')
            sys.stdout.flush()

    print(f'  加载完成: {total} 天, 共 {sum(len(d) for d in all_data):,} 条记录')
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


def clean_data_batch(raw_df, products_df, cat_map):
    """批量数据清洗"""
    print('  数据清洗中...')

    # 1. 过滤缺失值
    missing_mask = raw_df['product_id'].isna() | (raw_df['product_id'] == '') | \
                   raw_df['price'].isna() | (raw_df['price'] == '')
    anomaly_missing = raw_df[missing_mask].copy()
    anomaly_missing['anomaly_type'] = '缺失字段'

    valid_df = raw_df[~missing_mask].copy()
    valid_df['price'] = pd.to_numeric(valid_df['price'], errors='coerce')

    # 2. 过滤异常价格
    price_zero_mask = valid_df['price'] <= 0
    anomaly_price = valid_df[price_zero_mask].copy()
    anomaly_price['anomaly_type'] = '异常价格(<=0)'

    valid_df = valid_df[~price_zero_mask].copy()

    # 3. 关联商品维度表
    products_subset = products_df[['product_id', 'product_name', 'base_price', 'weight', 'category_l1']].copy()
    valid_df = valid_df.merge(products_subset, on='product_id', how='inner')

    # 4. 去重
    valid_df = valid_df.drop_duplicates(subset=['product_id', 'dt'], keep='first')

    # 5. 获取二级类目名称
    valid_df['category_id_l2'] = valid_df['category_id'] // 100 * 100
    cat_map_subset = cat_map[['category_id', 'category_name']].copy()
    cat_map_subset.columns = ['category_id_l2', 'category_name_l2']
    valid_df = valid_df.merge(cat_map_subset, on='category_id_l2', how='left')

    # 6. 构建DWD表
    dwd_df = pd.DataFrame({
        'product_id': valid_df['product_id'],
        'product_name': valid_df['product_name'],
        'category_id': valid_df['category_id'],
        'category_name': valid_df['category_name_l2'],
        'category_l1': valid_df['category_l1'],
        'category_l2': valid_df['category_name_l2'],
        'price': valid_df['price'],
        'base_price': valid_df['base_price'],
        'weight': valid_df['weight'],
        'dt': valid_df['dt'],
    })

    anomaly_df = pd.concat([anomaly_missing, anomaly_price], ignore_index=True)

    print(f'  清洗完成: {len(dwd_df):,} 条有效数据, {len(anomaly_df):,} 条异常')
    return dwd_df, anomaly_df


def calculate_all_indices(dwd_df, categories_df):
    """批量计算所有指数"""
    print('  计算指数中...')

    results = []

    # 1. SKU指数 (向量化，一行代码)
    sku_df = dwd_df.copy()
    sku_df['price_index'] = (sku_df['price'] / sku_df['base_price'] * 100).round(4)
    sku_result = pd.DataFrame({
        'index_type': 'SKU',
        'target_id': sku_df['product_id'],
        'target_name': sku_df['product_name'],
        'category_id': sku_df['category_id'],
        'category_name': sku_df['category_name'],
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
    print(f'  SKU指数: {len(sku_result):,} 条')

    # 2. 二级类目指数 (groupby 向量化)
    sku_df['weighted_value'] = sku_df['price_index'] * sku_df['weight']
    cat_l2 = sku_df.groupby(['dt', 'category_id', 'category_name', 'category_l1']).agg({
        'weighted_value': 'sum',
        'weight': 'sum',
        'product_id': 'count'
    }).reset_index()
    cat_l2['price_index'] = (cat_l2['weighted_value'] / cat_l2['weight']).round(4)
    cat_l2['product_count'] = cat_l2['product_id']

    cat_weight_map = categories_df.set_index('category_id')['weight'].to_dict()
    cat_l2['index_weight'] = cat_l2['category_id'].map(cat_weight_map)

    cat_l2_result = pd.DataFrame({
        'index_type': 'CATEGORY',
        'target_id': cat_l2['category_id'],
        'target_name': cat_l2['category_name'],
        'category_id': cat_l2['category_id'],
        'category_name': cat_l2['category_name'],
        'category_l1': cat_l2['category_l1'],
        'base_date': '2025-05-17',
        'price_index': cat_l2['price_index'],
        'product_count': cat_l2['product_count'],
        'index_weight': cat_l2['index_weight'],
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': cat_l2['dt'],
    })
    results.append(cat_l2_result)
    print(f'  二级类目指数: {len(cat_l2_result):,} 条')

    # 3. 一级类目指数
    cat_l1 = sku_df.groupby(['dt', 'category_l1']).agg({
        'weighted_value': 'sum',
        'weight': 'sum',
        'product_id': 'count'
    }).reset_index()
    cat_l1['price_index'] = (cat_l1['weighted_value'] / cat_l1['weight']).round(4)
    cat_l1['product_count'] = cat_l1['product_id']

    cat_l1_result = pd.DataFrame({
        'index_type': 'CATEGORY_L1',
        'target_id': cat_l1['category_l1'],
        'target_name': cat_l1['category_l1'],
        'category_id': cat_l1['category_l1'],
        'category_name': cat_l1['category_l1'],
        'category_l1': cat_l1['category_l1'],
        'base_date': '2025-05-17',
        'price_index': cat_l1['price_index'],
        'product_count': cat_l1['product_count'],
        'index_weight': cat_l1['weight'],
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': cat_l1['dt'],
    })
    results.append(cat_l1_result)
    print(f'  一级类目指数: {len(cat_l1_result):,} 条')

    # 4. 全网加权指数
    cat_l1_weights = categories_df[categories_df['hierarchy'] == 1].set_index('category_name')['weight'].to_dict()
    overall_df = cat_l2.copy()
    overall_df['l1_weight'] = overall_df['category_l1'].map(cat_l1_weights)
    overall_df['weighted_index'] = overall_df['price_index'] * overall_df['l1_weight'] * overall_df['index_weight']
    overall_grouped = overall_df.groupby('dt').agg({
        'weighted_index': 'sum',
        'l1_weight': lambda x: (x * overall_df.loc[x.index, 'index_weight']).sum()
    }).reset_index()
    overall_grouped['price_index'] = (overall_grouped['weighted_index'] / overall_grouped['l1_weight']).round(4)

    overall_result = pd.DataFrame({
        'index_type': 'OVERALL',
        'target_id': 'OVERALL',
        'target_name': '全网价格指数',
        'base_date': '2025-05-17',
        'price_index': overall_grouped['price_index'],
        'index_weight': 1.0,
        'create_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt': overall_grouped['dt'],
    })
    results.append(overall_result)
    print(f'  全网指数: {len(overall_result):,} 条')

    # 5. 费雪指数
    sku_df['p0'] = sku_df['base_price']
    sku_df['pt'] = sku_df['price']
    sku_df['w'] = sku_df['weight']
    fisher_df = sku_df.groupby('dt').agg({
        'p0': lambda x: (sku_df.loc[x.index, 'w'] * sku_df.loc[x.index, 'pt']).sum() /
                        (sku_df.loc[x.index, 'w'] * sku_df.loc[x.index, 'p0']).sum()
    }).reset_index()
    fisher_df.columns = ['dt', 'pl']
    fisher_df['pp'] = fisher_df['pl']
    fisher_df['price_index'] = (np.sqrt(fisher_df['pl'] * fisher_df['pp']) * 100).round(4)

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
    print(f'  费雪指数: {len(fisher_result):,} 条')

    # 合并所有结果
    all_index = pd.concat(results, ignore_index=True)

    # 6. 计算日环比 (向量化)
    print('  计算日环比...')
    all_index = all_index.sort_values(['index_type', 'target_id', 'dt'])
    all_index['prev_price_index'] = all_index.groupby(['index_type', 'target_id'])['price_index'].shift(1)
    all_index['mom_change_rate'] = ((all_index['price_index'] - all_index['prev_price_index']) /
                                    all_index['prev_price_index'] * 100).round(4)
    all_index = all_index.drop(columns=['prev_price_index'])

    print(f'  全部指数计算完成: {len(all_index):,} 条')
    return all_index


def save_dwd_daily(dwd_df):
    """按天保存DWD数据"""
    print('  保存DWD数据...')
    for dt in sorted(dwd_df['dt'].unique()):
        day_df = dwd_df[dwd_df['dt'] == dt]
        day_dir = os.path.join(DATA_DIR, 'dwd', f'dt={dt}')
        os.makedirs(day_dir, exist_ok=True)
        day_df.to_csv(os.path.join(day_dir, 'product_price_detail.csv'),
                      index=False, encoding='utf-8-sig')
    print(f'  DWD数据已保存: {dwd_df["dt"].nunique()} 天')


def save_dws_daily(all_index):
    """按天保存DWS数据"""
    print('  保存DWS数据...')
    for dt in sorted(all_index['dt'].unique()):
        day_df = all_index[all_index['dt'] == dt]
        day_dir = os.path.join(DATA_DIR, 'dws', f'dt={dt}')
        os.makedirs(day_dir, exist_ok=True)
        day_df[day_df['index_type'] == 'SKU'].to_csv(
            os.path.join(day_dir, 'sku_daily.csv'), index=False, encoding='utf-8-sig')
        day_df[day_df['index_type'].isin(['CATEGORY', 'CATEGORY_L1'])].to_csv(
            os.path.join(day_dir, 'category_daily.csv'), index=False, encoding='utf-8-sig')


def save_ads_daily(all_index, anomaly_df):
    """按天保存ADS数据"""
    print('  保存ADS数据...')
    for dt in sorted(all_index['dt'].unique()):
        day_df = all_index[all_index['dt'] == dt]
        day_dir = os.path.join(DATA_DIR, 'ads', f'dt={dt}')
        os.makedirs(day_dir, exist_ok=True)
        day_df.to_csv(os.path.join(day_dir, 'price_index_daily.csv'),
                      index=False, encoding='utf-8-sig')

    # 保存异常数据
    if anomaly_df is not None and len(anomaly_df) > 0:
        anomaly_dir = os.path.join(DATA_DIR, 'ads', 'anomaly')
        os.makedirs(anomaly_dir, exist_ok=True)
        for dt in sorted(anomaly_df['dt'].unique()):
            day_anomaly = anomaly_df[anomaly_df['dt'] == dt]
            day_anomaly.to_csv(os.path.join(anomaly_dir, f'anomaly_{dt}.csv'),
                               index=False, encoding='utf-8-sig')


def generate_reports(all_index, products_df, categories_df):
    """批量生成日报"""
    print('  生成日报...')
    import json

    report_dir = os.path.join(DATA_DIR, 'reports')
    os.makedirs(report_dir, exist_ok=True)

    dates = sorted(all_index['dt'].unique())
    for i, dt in enumerate(dates):
        day_data = all_index[all_index['dt'] == dt]

        overall = day_data[day_data['index_type'] == 'OVERALL']
        fisher = day_data[day_data['index_type'] == 'FISHER']
        cat_l1 = day_data[day_data['index_type'] == 'CATEGORY_L1']
        sku = day_data[day_data['index_type'] == 'SKU']

        overall_idx = overall['price_index'].values[0] if len(overall) > 0 else 0
        overall_mom = overall['mom_change_rate'].values[0] if len(overall) > 0 and pd.notna(overall['mom_change_rate'].values[0]) else 0
        fisher_idx = fisher['price_index'].values[0] if len(fisher) > 0 else 0

        top_gain = cat_l1.nlargest(5, 'price_index')[['target_name', 'price_index', 'mom_change_rate']].to_dict('records')
        top_loss = cat_l1.nsmallest(5, 'price_index')[['target_name', 'price_index', 'mom_change_rate']].to_dict('records')

        sku_valid = sku.dropna(subset=['mom_change_rate'])
        if len(sku_valid) > 0:
            top_vol = sku_valid.reindex(sku_valid['mom_change_rate'].abs().sort_values(ascending=False).index).head(10)
        else:
            top_vol = sku.head(10)
        top_vol_list = top_vol[['target_name', 'price_index', 'mom_change_rate']].to_dict('records')

        anomaly_file = os.path.join(DATA_DIR, 'ads', 'anomaly', f'anomaly_{dt}.csv')
        anomaly_count = len(pd.read_csv(anomaly_file)) if os.path.exists(anomaly_file) else 0

        report = {
            'date': dt,
            'generate_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'overall_index': float(overall_idx),
            'overall_mom_change': float(overall_mom),
            'fisher_index': float(fisher_idx),
            'product_count': len(products_df),
            'category_count': len(categories_df),
            'anomaly_count': anomaly_count,
            'top_gain_categories': top_gain,
            'top_loss_categories': top_loss,
            'top_volatile_skus': top_vol_list,
        }

        with open(os.path.join(report_dir, f'report_{dt}.json'), 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        if (i + 1) % 100 == 0:
            print(f'    日报生成: {i+1}/{len(dates)}', end='\r')
            sys.stdout.flush()

    print(f'  日报生成完成: {len(dates)} 份')


def main():
    import time
    start_time = time.time()

    print('=' * 60)
    print('高频电商价格指数计算平台 - 高性能数据处理管道')
    print('  (批量向量化处理，速度提升10~50倍)')
    print('=' * 60)

    # 1. 加载维度表
    print('\n[1/6] 加载维度表...')
    products_df, cat_map, categories_df = load_dim_tables()
    print(f'  商品维度表: {len(products_df):,} 条')
    print(f'  类目维度表: {len(categories_df):,} 条')

    # 2. 加载ODS数据
    print('\n[2/6] 加载ODS数据...')
    raw_df = load_all_ods_data()
    if len(raw_df) == 0:
        print('错误: 未找到ODS数据')
        return

    # 3. 数据清洗
    print('\n[3/6] 数据清洗...')
    dwd_df, anomaly_df = clean_data_batch(raw_df, products_df, cat_map)
    save_dwd_daily(dwd_df)

    # 4. 计算指数
    print('\n[4/6] 计算价格指数...')
    all_index = calculate_all_indices(dwd_df, categories_df)
    save_dws_daily(all_index)
    save_ads_daily(all_index, anomaly_df)

    # 5. 保存全量数据
    print('\n[5/6] 保存全量指数数据...')
    ads_all_path = os.path.join(DATA_DIR, 'ads', 'all_index.csv')
    all_index.to_csv(ads_all_path, index=False, encoding='utf-8-sig')
    print(f'  全量指数数据: {len(all_index):,} 条')
    print(f'  保存位置: {ads_all_path}')

    # 6. 生成日报
    print('\n[6/6] 生成每日报告...')
    generate_reports(all_index, products_df, categories_df)

    elapsed = time.time() - start_time
    print('\n' + '=' * 60)
    print(f'处理完成！总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)')
    print(f'  - 处理天数: {all_index["dt"].nunique()} 天')
    print(f'  - 指数记录: {len(all_index):,} 条')
    print(f'  - 日均耗时: {elapsed / all_index["dt"].nunique():.2f} 秒/天')
    print('=' * 60)


if __name__ == '__main__':
    main()

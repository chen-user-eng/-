import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def load_dim_tables():
    products_df = pd.read_csv(os.path.join(DATA_DIR, 'dim', 'products.csv'))
    products_df = products_df.rename(columns={
        'name': 'product_name',
        'price': 'base_price',
        'weight': 'weight'
    })
    categories_df = pd.read_csv(os.path.join(DATA_DIR, 'dim', 'categories.csv'))
    cat_l1 = categories_df[categories_df['hierarchy'] == 1].copy()
    cat_l2 = categories_df[categories_df['hierarchy'] == 2].copy()
    cat_l3 = categories_df[categories_df['hierarchy'] == 3].copy()

    # 建立一级->二级映射
    l1_map = dict(zip(cat_l1['category_id'], cat_l1['category_name']))

    # 建立二级->一级映射
    l2_to_l1 = {}
    for _, row in cat_l2.iterrows():
        l2_to_l1[row['category_id']] = l1_map.get(row['parent_id'], '')

    # 商品的三级类目ID映射到二级类目ID（把最后一位变成0）
    products_df['category_id_l2'] = products_df['category_id'] // 10 * 10
    products_df['category_l1'] = products_df['category_id_l2'].map(
        lambda x: l2_to_l1.get(x, '')
    )

    # 建立二级类目映射表
    cat_map = cat_l2.copy()
    cat_map['category_l1'] = cat_map['parent_id'].map(l1_map)
    cat_map = cat_map[['category_id', 'category_name', 'parent_id', 'category_l1', 'weight']]
    cat_map.columns = ['category_id_l2', 'category_name', 'parent_id', 'category_l1', 'category_weight']

    # 建立三级类目映射表（如果存在的话）
    cat_l3_map = cat_l3.copy()
    if len(cat_l3_map) > 0:
        cat_l3_map['category_l1'] = cat_l3_map['parent_id'].map(l1_map)
        cat_l3_map = cat_l3_map[['category_id', 'category_name', 'parent_id', 'category_l1', 'weight']]
        cat_l3_map.columns = ['category_id_l3', 'category_name', 'parent_id', 'category_l1', 'category_weight']
        # 合并到cat_map
        cat_map = pd.concat([
            cat_map.rename(columns={'category_id_l2': 'category_id'}),
            cat_l3_map.rename(columns={'category_id_l3': 'category_id'})
        ], ignore_index=True)

    return products_df, cat_map, categories_df


def clean_daily_data(date_str, products_df, cat_map):
    ods_file = os.path.join(DATA_DIR, 'ods', f'dt={date_str}', 'product_price.csv')
    if not os.path.exists(ods_file):
        return None, None
    raw_df = pd.read_csv(ods_file)
    total_count = len(raw_df)
    anomaly_records = []
    missing_mask = raw_df['product_id'].isna() | (raw_df['product_id'] == '') | \
                   raw_df['price'].isna() | (raw_df['price'] == '')
    anomaly_records.append(raw_df[missing_mask].copy())
    anomaly_records[-1]['anomaly_type'] = '缺失字段'
    valid_df = raw_df[~missing_mask].copy()
    valid_df['price'] = pd.to_numeric(valid_df['price'], errors='coerce')
    price_zero_mask = valid_df['price'] <= 0
    anomaly_records.append(valid_df[price_zero_mask].copy())
    anomaly_records[-1]['anomaly_type'] = '异常价格(<=0)'
    valid_df = valid_df[~price_zero_mask].copy()
    # 关联products_df获取商品维度信息，重命名冲突列
    products_subset = products_df[['product_id', 'product_name', 'base_price', 'weight', 'category_l1']].copy()
    merged = valid_df.merge(products_subset, on='product_id', how='inner')
    # 使用ODS的category_id（商品的三级类目ID）来计算二级类目ID，然后关联获取二级类目名称
    merged['category_id_l2'] = merged['category_id'] // 10 * 10
    cat_map_subset = cat_map[['category_id', 'category_name', 'category_l1']].copy()
    cat_map_subset.columns = ['category_id_l2', 'category_name_l2', 'category_l1_cat']
    merged = merged.merge(cat_map_subset, on='category_id_l2', how='left')
    # 优先使用cat_map的一级类目名称，如果没有则用products_df的
    merged['category_l1'] = merged['category_l1_cat'].fillna(merged['category_l1'])
    dwd_df = pd.DataFrame({
        'product_id': merged['product_id'],
        'product_name': merged['product_name'],
        'category_id': merged['category_id'],
        'category_name': merged['category_name_l2'],
        'category_l1': merged['category_l1'],
        'category_l2': merged['category_name_l2'],
        'price': merged['price'],
        'base_price': merged['base_price'],
        'weight': merged['weight'],
        'dt': date_str,
    })
    anomaly_df = pd.concat(anomaly_records, ignore_index=True)
    return dwd_df, anomaly_df


def calculate_sku_index(dwd_df, date_str):
    sku_df = dwd_df.copy()
    sku_df['price_index'] = round(sku_df['price'] / sku_df['base_price'] * 100, 4)
    return pd.DataFrame({
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
        'dt': date_str,
    })


def calculate_category_index(sku_index_df, date_str, categories_df):
    sku_index_df = sku_index_df.copy()
    sku_index_df['weighted_value'] = sku_index_df['price_index'] * sku_index_df['index_weight']
    cat_l2 = sku_index_df.groupby(['category_id', 'category_name', 'category_l1'], as_index=False).agg({
        'weighted_value': 'sum',
        'index_weight': 'sum',
        'target_id': 'count'
    })
    cat_l2['price_index'] = round(cat_l2['weighted_value'] / cat_l2['index_weight'], 4)
    cat_l2['product_count'] = cat_l2['target_id']
    cat_l2['index_type'] = 'CATEGORY'
    cat_l2['target_id'] = cat_l2['category_id']
    cat_l2['target_name'] = cat_l2['category_name']
    cat_l2['base_date'] = '2025-05-17'
    cat_l2['create_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cat_l2['dt'] = date_str
    cat_l2 = cat_l2.drop(columns=['weighted_value'])

    cat_l1 = sku_index_df.groupby('category_l1', as_index=False).agg({
        'weighted_value': 'sum',
        'index_weight': 'sum',
        'target_id': 'count'
    })
    cat_l1['price_index'] = round(cat_l1['weighted_value'] / cat_l1['index_weight'], 4)
    cat_l1['product_count'] = cat_l1['target_id']
    cat_l1['index_type'] = 'CATEGORY_L1'
    cat_l1['target_id'] = cat_l1['category_l1']
    cat_l1['target_name'] = cat_l1['category_l1']
    cat_l1['category_id'] = cat_l1['category_l1']
    cat_l1['category_name'] = cat_l1['category_l1']
    cat_l1['base_date'] = '2025-05-17'
    cat_l1['create_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cat_l1['dt'] = date_str
    cat_l1 = cat_l1.drop(columns=['weighted_value'])

    return pd.concat([cat_l2, cat_l1], ignore_index=True)


def calculate_overall_index(cat_index_df, date_str, categories_df):
    cat_l2 = cat_index_df[cat_index_df['index_type'] == 'CATEGORY'].copy()
    cat_l1_weights = categories_df[categories_df['hierarchy'] == 1].set_index('category_name')['weight'].to_dict()
    cat_l2['l1_weight'] = cat_l2['category_l1'].map(cat_l1_weights)
    cat_l2_valid = cat_l2.dropna(subset=['l1_weight', 'index_weight'])
    overall_weighted = (cat_l2_valid['price_index'] * cat_l2_valid['l1_weight'] * cat_l2_valid['index_weight']).sum()
    overall_weight_sum = (cat_l2_valid['l1_weight'] * cat_l2_valid['index_weight']).sum()
    overall_index = round(overall_weighted / overall_weight_sum, 4) if overall_weight_sum > 0 else 100.0
    return pd.DataFrame({
        'index_type': ['OVERALL'],
        'target_id': ['OVERALL'],
        'target_name': ['全网价格指数'],
        'base_date': ['2025-05-17'],
        'price_index': [overall_index],
        'index_weight': [1.0],
        'create_time': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        'dt': [date_str],
    })


def calculate_fisher_index(dwd_df, date_str):
    df = dwd_df.copy()
    p0 = df['base_price']
    pt = df['price']
    w = df['weight']
    pl = (w * pt).sum() / (w * p0).sum()
    pp = (w * pt).sum() / (w * p0).sum()
    pf = np.sqrt(pl * pp) * 100
    return pd.DataFrame({
        'index_type': ['FISHER'],
        'target_id': ['OVERALL'],
        'target_name': ['全网费雪指数'],
        'base_date': ['2025-05-17'],
        'price_index': [round(pf, 4)],
        'index_weight': [1.0],
        'create_time': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        'dt': [date_str],
    })


def calculate_mom_change(ads_all_df, date_str):
    current = ads_all_df[ads_all_df['dt'] == date_str].copy()
    prev_date = (datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    prev = ads_all_df[ads_all_df['dt'] == prev_date].copy()
    if len(prev) == 0:
        current['mom_change_rate'] = None
        return current
    merged = current.merge(
        prev[['index_type', 'target_id', 'price_index']],
        on=['index_type', 'target_id'],
        how='left',
        suffixes=('', '_prev')
    )
    merged['mom_change_rate'] = round(
        (merged['price_index'] - merged['price_index_prev']) / merged['price_index_prev'] * 100, 4
    )
    merged = merged.drop(columns=['price_index_prev'])
    return merged


def process_date(date_str, products_df, cat_map, categories_df, ads_all_df):
    dwd_df, anomaly_df = clean_daily_data(date_str, products_df, cat_map)
    if dwd_df is None or len(dwd_df) == 0:
        return None, None, None
    dwd_dir = os.path.join(DATA_DIR, 'dwd', f'dt={date_str}')
    os.makedirs(dwd_dir, exist_ok=True)
    dwd_df.to_csv(os.path.join(dwd_dir, 'product_price_detail.csv'), index=False, encoding='utf-8-sig')
    if anomaly_df is not None and len(anomaly_df) > 0:
        anomaly_dir = os.path.join(DATA_DIR, 'ads', 'anomaly')
        os.makedirs(anomaly_dir, exist_ok=True)
        anomaly_df.to_csv(os.path.join(anomaly_dir, f'anomaly_{date_str}.csv'),
                          index=False, encoding='utf-8-sig')
    sku_index_df = calculate_sku_index(dwd_df, date_str)
    cat_index_df = calculate_category_index(sku_index_df, date_str, categories_df)
    overall_df = calculate_overall_index(cat_index_df, date_str, categories_df)
    fisher_df = calculate_fisher_index(dwd_df, date_str)
    all_index_df = pd.concat([
        sku_index_df.assign(index_type='SKU'),
        cat_index_df,
        overall_df,
        fisher_df
    ], ignore_index=True)
    ads_all_df = pd.concat([ads_all_df, all_index_df], ignore_index=True)
    current_with_mom = calculate_mom_change(ads_all_df, date_str)
    non_current = ads_all_df[ads_all_df['dt'] != date_str].copy()
    if 'mom_change_rate' not in non_current.columns:
        non_current['mom_change_rate'] = None
    ads_all_df = pd.concat([non_current, current_with_mom], ignore_index=True)
    all_index_with_mom = current_with_mom.copy()
    ads_dir = os.path.join(DATA_DIR, 'ads', f'dt={date_str}')
    os.makedirs(ads_dir, exist_ok=True)
    all_index_with_mom.to_csv(os.path.join(ads_dir, 'price_index_daily.csv'),
                              index=False, encoding='utf-8-sig')
    dws_dir = os.path.join(DATA_DIR, 'dws', f'dt={date_str}')
    os.makedirs(dws_dir, exist_ok=True)
    sku_index_df.to_csv(os.path.join(dws_dir, 'sku_daily.csv'),
                        index=False, encoding='utf-8-sig')
    cat_index_df.to_csv(os.path.join(dws_dir, 'category_daily.csv'),
                        index=False, encoding='utf-8-sig')
    return dwd_df, all_index_with_mom, ads_all_df


def generate_daily_report(date_str, ads_df, anomaly_count, product_count, category_count):
    overall = ads_df[(ads_df['index_type'] == 'OVERALL') & (ads_df['dt'] == date_str)]
    fisher = ads_df[(ads_df['index_type'] == 'FISHER') & (ads_df['dt'] == date_str)]
    cat_l1 = ads_df[(ads_df['index_type'] == 'CATEGORY_L1') & (ads_df['dt'] == date_str)]
    sku = ads_df[(ads_df['index_type'] == 'SKU') & (ads_df['dt'] == date_str)]
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
    report = {
        'date': date_str,
        'generate_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'overall_index': overall_idx,
        'overall_mom_change': overall_mom,
        'fisher_index': fisher_idx,
        'product_count': product_count,
        'category_count': category_count,
        'anomaly_count': anomaly_count,
        'top_gain_categories': top_gain,
        'top_loss_categories': top_loss,
        'top_volatile_skus': top_vol_list,
    }
    import json
    report_dir = os.path.join(DATA_DIR, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, f'report_{date_str}.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main():
    import sys
    print('=' * 60)
    print('高频电商价格指数计算平台 - 数据处理管道')
    print('=' * 60)
    products_df, cat_map, categories_df = load_dim_tables()
    print(f'商品维度表: {len(products_df)} 条')
    print(f'类目维度表: {len(categories_df)} 条')
    ods_dir = os.path.join(DATA_DIR, 'ods')
    date_dirs = sorted([d for d in os.listdir(ods_dir) if d.startswith('dt=')])
    dates = [d.split('=')[1] for d in date_dirs]
    print(f'待处理日期: {len(dates)} 天 ({dates[0]} ~ {dates[-1]})')
    ads_all_df = pd.DataFrame()
    print('\n开始处理...')
    print('(提示: 由于数据量大(70000商品×1095天)，完整处理可能需要较长时间)')
    print()
    for i, date_str in enumerate(dates):
        dwd_df, ads_df, ads_all_df = process_date(
            date_str, products_df, cat_map, categories_df, ads_all_df
        )
        if dwd_df is None:
            print(f'  [{i+1}/{len(dates)}] {date_str} - 无数据，跳过')
            sys.stdout.flush()
            continue
        anomaly_file = os.path.join(DATA_DIR, 'ads', 'anomaly', f'anomaly_{date_str}.csv')
        anomaly_count = len(pd.read_csv(anomaly_file)) if os.path.exists(anomaly_file) else 0
        generate_daily_report(
            date_str, ads_all_df, anomaly_count,
            len(products_df), len(categories_df)
        )
        if (i + 1) % 50 == 0 or (i + 1) == len(dates):
            print(f'  进度: {i+1}/{len(dates)} ({date_str}) - 累计指数{len(ads_all_df)}条')
            sys.stdout.flush()
        elif (i + 1) % 10 == 0:
            print(f'  已处理: {i+1}/{len(dates)}', end='\r')
            sys.stdout.flush()
    ads_all_path = os.path.join(DATA_DIR, 'ads', 'all_index.csv')
    ads_all_df.to_csv(ads_all_path, index=False, encoding='utf-8-sig')
    print(f'\n全量指数数据已保存: {ads_all_path}')
    print(f'总指数记录: {len(ads_all_df)} 条')
    print(f'\n处理完成！共处理 {len(dates)} 天数据')
    print('=' * 60)


if __name__ == '__main__':
    main()

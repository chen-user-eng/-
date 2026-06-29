"""
异常检测脚本
检测价格突变、历史偏离等异常情况
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# 异常检测阈值
MOM_THRESHOLD = 20.0  # 单日涨跌幅阈值（%）
ZSCORE_THRESHOLD = 3.0  # Z-score阈值（标准差倍数）
MIN_HISTORY_DAYS = 7  # 最少历史数据天数
PRICE_MIN_RATIO = 0.01  # 价格最低为基础价的1%
PRICE_MAX_RATIO = 10.0  # 价格最高为基础价的10倍

def detect_anomalies():
    """检测所有异常"""
    print('=' * 60)
    print('异常检测系统')
    print('=' * 60)

    ads_path = os.path.join(DATA_DIR, 'ads', 'all_index.csv')

    if not os.path.exists(ads_path):
        print('错误：ADS数据文件不存在，请先运行数据处理脚本')
        return

    print('[1/4] 加载ADS数据...')
    df = pd.read_csv(ads_path, low_memory=False)
    df['dt'] = df['dt'].astype(str)

    # 只分析SKU级别的数据
    sku_df = df[df['index_type'] == 'SKU'].copy()
    # 重命名字段
    sku_df = sku_df.rename(columns={
        'target_id': 'product_id',
        'target_name': 'product_name'
    })
    sku_df = sku_df.sort_values(['product_id', 'dt'])

    print(f'  SKU数据: {len(sku_df):,} 条')
    print(f'  日期范围: {sku_df["dt"].min()} ~ {sku_df["dt"].max()}')

    # 保存原始字段用于最终输出
    sku_df['orig_product_name'] = sku_df['product_name']
    sku_df['orig_category_l1'] = sku_df['category_l1']
    sku_df['orig_base_price'] = sku_df['base_price']

    # 1. 计算日环比
    print('[2/4] 计算日环比变化...')
    sku_df['prev_price'] = sku_df.groupby('product_id')['price'].shift(1)
    sku_df['prev_price_index'] = sku_df.groupby('product_id')['price_index'].shift(1)
    sku_df['mom_rate'] = ((sku_df['price'] - sku_df['prev_price']) / sku_df['prev_price'] * 100).round(4)

    # 2. 计算历史统计
    print('[3/4] 计算历史统计特征...')
    stats = sku_df.groupby('product_id').agg({
        'price': ['mean', 'std', 'min', 'max', 'count'],
        'price_index': ['mean', 'std'],
        'base_price': 'first',
        'product_name': 'first',
        'category_l1': 'first'
    })
    stats.columns = ['price_mean', 'price_std', 'price_min', 'price_max', 'data_days',
                     'index_mean', 'index_std', 'base_price', 'product_name', 'category_l1']
    stats['price_std'] = stats['price_std'].fillna(0)
    stats = stats.reset_index()

    # 合并统计信息
    sku_df = sku_df.merge(stats[['product_id', 'price_mean', 'price_std', 'data_days']],
                         on='product_id', how='left', suffixes=('', '_stat'))

    # 初始化异常列表
    all_anomalies = []
    anomaly_count = 0

    # 异常检测1：价格突变（日环比超过阈值）
    print('[4/4] 异常检测中...')

    print('  检测1: 价格突变（日环比>±20%）...')
    mom_anomaly = sku_df[
        (abs(sku_df['mom_rate']) > MOM_THRESHOLD) &
        (sku_df['mom_rate'].notna())
    ].copy()
    if len(mom_anomaly) > 0:
        mom_anomaly['anomaly_type'] = '价格突变'
        mom_anomaly['anomaly_desc'] = mom_anomaly['mom_rate'].apply(
            lambda x: f"日环比{x:+.2f}%"
        )
        mom_record = mom_anomaly[['dt', 'product_id', 'orig_product_name', 'orig_category_l1',
                                  'price', 'prev_price', 'orig_base_price', 'mom_rate',
                                  'anomaly_type', 'anomaly_desc']].copy()
        mom_record.columns = ['dt', 'product_id', 'product_name', 'category_l1',
                             'current_price', 'prev_price', 'base_price', 'change_rate',
                             'anomaly_type', 'anomaly_desc']
        all_anomalies.append(mom_record)
        print(f'    发现 {len(mom_record):,} 条价格突变异常')
        anomaly_count += len(mom_record)

    # 异常检测2：价格偏离历史（Z-score > 3）
    print('  检测2: 价格偏离历史均值（Z-score>3）...')
    sku_df['z_score'] = (sku_df['price'] - sku_df['price_mean']) / (sku_df['price_std'] + 0.001)
    zscore_anomaly = sku_df[
        (abs(sku_df['z_score']) > ZSCORE_THRESHOLD) &
        (sku_df['price_std'] > 0) &
        (sku_df['data_days'] >= MIN_HISTORY_DAYS)
    ].copy()
    if len(zscore_anomaly) > 0:
        zscore_anomaly['anomaly_type'] = '价格偏离'
        zscore_anomaly['anomaly_desc'] = zscore_anomaly.apply(
            lambda x: f"偏离均值{x['z_score']:+.1f}σ (均值:{x['price_mean']:.2f})", axis=1
        )
        zscore_record = zscore_anomaly[['dt', 'product_id', 'orig_product_name', 'orig_category_l1',
                                        'price', 'orig_base_price', 'price_mean', 'price_std',
                                        'z_score', 'anomaly_type', 'anomaly_desc']].copy()
        zscore_record.columns = ['dt', 'product_id', 'product_name', 'category_l1',
                                'current_price', 'base_price', 'hist_avg', 'hist_std',
                                'z_score', 'anomaly_type', 'anomaly_desc']
        all_anomalies.append(zscore_record)
        print(f'    发现 {len(zscore_record):,} 条价格偏离异常')
        anomaly_count += len(zscore_record)

    # 异常检测3：价格超出合理范围
    print('  检测3: 价格超出合理范围...')
    sku_df['price_ratio'] = sku_df['price'] / sku_df['base_price']
    range_anomaly = sku_df[
        (sku_df['price_ratio'] < PRICE_MIN_RATIO) |
        (sku_df['price_ratio'] > PRICE_MAX_RATIO)
    ].copy()
    if len(range_anomaly) > 0:
        range_anomaly['anomaly_type'] = '价格超限'
        range_anomaly['anomaly_desc'] = range_anomaly['price_ratio'].apply(
            lambda x: f"价格为基础价的{x:.1f}倍" if x > 1 else f"价格为基础价的{x*100:.1f}%"
        )
        range_record = range_anomaly[['dt', 'product_id', 'orig_product_name', 'orig_category_l1',
                                      'price', 'orig_base_price', 'price_ratio',
                                      'anomaly_type', 'anomaly_desc']].copy()
        range_record.columns = ['dt', 'product_id', 'product_name', 'category_l1',
                               'current_price', 'base_price', 'price_ratio',
                               'anomaly_type', 'anomaly_desc']
        all_anomalies.append(range_record)
        print(f'    发现 {len(range_record):,} 条价格超限异常')
        anomaly_count += len(range_record)

    # 异常检测4：价格为零或负数
    print('  检测4: 价格为零或负数...')
    zero_anomaly = sku_df[sku_df['price'] <= 0].copy()
    if len(zero_anomaly) > 0:
        zero_anomaly['anomaly_type'] = '价格异常'
        zero_anomaly['anomaly_desc'] = '价格为零或负数'
        zero_record = zero_anomaly[['dt', 'product_id', 'orig_product_name', 'orig_category_l1',
                                    'price', 'orig_base_price', 'anomaly_type', 'anomaly_desc']].copy()
        zero_record.columns = ['dt', 'product_id', 'product_name', 'category_l1',
                              'current_price', 'base_price', 'anomaly_type', 'anomaly_desc']
        all_anomalies.append(zero_record)
        print(f'    发现 {len(zero_record):,} 条价格异常记录')
        anomaly_count += len(zero_record)

    # 保存异常数据
    print()
    print('=' * 60)
    print('保存异常数据...')

    anomaly_dir = os.path.join(DATA_DIR, 'ads', 'anomaly')
    os.makedirs(anomaly_dir, exist_ok=True)

    if all_anomalies:
        anomaly_df = pd.concat(all_anomalies, ignore_index=True)
        anomaly_df = anomaly_df.sort_values(['dt', 'product_id'])

        # 按日期保存
        for dt in sorted(anomaly_df['dt'].unique()):
            day_anomaly = anomaly_df[anomaly_df['dt'] == dt]
            day_anomaly = day_anomaly.drop(columns=['dt'])
            day_anomaly.to_csv(
                os.path.join(anomaly_dir, f'anomaly_{dt}.csv'),
                index=False,
                encoding='utf-8-sig'
            )

        print(f'  总异常数: {len(anomaly_df):,} 条')
        print(f'  异常类型分布:')
        print(anomaly_df['anomaly_type'].value_counts().to_string().replace('\n', '\n    '))

        # 生成汇总报告
        summary = {
            'total_anomalies': len(anomaly_df),
            'anomaly_by_type': anomaly_df['anomaly_type'].value_counts().to_dict(),
            'anomaly_by_category': anomaly_df.groupby('category_l1').size().to_dict(),
            'anomaly_dates': len(anomaly_df['dt'].unique()),
            'generate_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        print()
        print('Top 10 异常商品:')
        top_anomalies = anomaly_df.groupby(['product_id', 'product_name']).size().sort_values(ascending=False).head(10)
        for (pid, name), count in top_anomalies.items():
            print(f'  {name}: {count} 次')

    else:
        print('  未发现异常数据')

    print('=' * 60)
    print('异常检测完成！')

    return len(anomaly_df) if all_anomalies else 0

if __name__ == '__main__':
    detect_anomalies()

"""
从本地 CSV 文件导入数据到 ClickHouse 本地表
"""
import sys
import os
import pandas as pd
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scripts.clickhouse_utils import get_ch_client


def import_local_data():
    client = get_ch_client()
    if not client.is_connected():
        print("❌ ClickHouse 连接失败")
        return

    print("=" * 60)
    print("  ClickHouse 数据初始化（从本地 CSV 导入）")
    print("=" * 60)

    # 先清空旧数据
    print("\n========== 清空旧数据 ==========")
    tables = ['dim_categories', 'dim_products', 'ads_anomaly', 'ads_price_index']
    for t in tables:
        try:
            client.query(f"TRUNCATE TABLE {t}")
            print(f"  ✅ {t} 已清空")
        except:
            pass

    # 导入 dim_categories
    print("\n========== 导入 dim_categories ==========")
    t0 = time.time()
    df = pd.read_csv(r"e:\111\data\dim\categories.csv", encoding='gbk')
    if not df.empty:
        df.columns = df.columns.str.strip()
        # 列名映射
        df = df.rename(columns={
            'category': 'category_name',
            'price': 'base_price',
            'parent': 'parent_id'
        })
        # 补齐字段
        if 'create_time' not in df.columns:
            df['create_time'] = pd.Timestamp.now()
        # 转换为字符串类型，处理空值
        for col in ['category_id', 'parent_id']:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str)
        for col in ['weight', 'base_price']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        client.insert_dataframe('dim_categories', df)
        cnt = len(df)
        print(f"  ✅ dim_categories: {cnt:,} 条 ({time.time()-t0:.1f}s)")
    else:
        print("  ⚠️ categories.csv 为空")

    # 导入 dim_products
    print("\n========== 导入 dim_products ==========")
    t0 = time.time()
    df = pd.read_csv(r"e:\111\data\dim\products.csv", encoding='gbk')
    if not df.empty:
        df.columns = df.columns.str.strip()
        # 列名映射
        df = df.rename(columns={'price': 'base_price'})
        # 补齐字段
        if 'category_id_l2' not in df.columns:
            df['category_id_l2'] = ''
        if 'category_id_l1' not in df.columns:
            df['category_id_l1'] = df['category_id'].astype(str)
        if 'create_time' not in df.columns:
            df['create_time'] = pd.Timestamp.now()
        # 转换为字符串类型
        for col in ['product_id', 'category_id', 'category_id_l2', 'category_id_l1']:
            if col in df.columns:
                df[col] = df[col].astype(str)
        client.insert_dataframe('dim_products', df)
        cnt = len(df)
        print(f"  ✅ dim_products: {cnt:,} 条 ({time.time()-t0:.1f}s)")
    else:
        print("  ⚠️ products.csv 为空")

    # 导入 ads_anomaly
    print("\n========== 导入 ads_anomaly ==========")
    t0 = time.time()
    anomaly_dir = r"e:\111\data\ads\anomaly"
    if os.path.exists(anomaly_dir):
        dfs = []
        for f in sorted(os.listdir(anomaly_dir)):
            if f.endswith('.csv'):
                # 从文件名提取日期，如 anomaly_2025-05-17.csv -> 2025-05-17
                dt = f.replace('anomaly_', '').replace('.csv', '')
                try:
                    df = pd.read_csv(os.path.join(anomaly_dir, f), encoding='utf-8')
                except:
                    try:
                        df = pd.read_csv(os.path.join(anomaly_dir, f), encoding='gbk')
                    except:
                        df = pd.read_csv(os.path.join(anomaly_dir, f), encoding='latin1')
                df.columns = df.columns.str.strip()
                # 添加日期字段
                df['dt'] = dt
                # 补齐字段
                if 'create_time' not in df.columns:
                    df['create_time'] = pd.Timestamp.now()
                dfs.append(df)
        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            # 确保列顺序匹配
            target_cols = ['dt', 'product_id', 'product_name', 'category_l1', 'current_price',
                          'base_price', 'anomaly_type', 'anomaly_desc', 'change_rate',
                          'z_score', 'price_ratio', 'create_time']
            # 只选择存在的列
            cols = [c for c in target_cols if c in df.columns]
            df = df[cols]
            client.insert_dataframe('ads_anomaly', df)
            cnt = len(df)
            print(f"  ✅ ads_anomaly: {cnt:,} 条 ({time.time()-t0:.1f}s)")
    else:
        print("  ⚠️ anomaly 目录不存在")

    # 导入 ads_price_index (核心大表)
    print("\n========== 导入 ads_price_index ==========")
    t0 = time.time()
    csv_path = r"e:\111\data\ads\all_index.csv"
    if os.path.exists(csv_path):
        # 分块读取，避免内存溢出
        chunk_size = 500000
        total_rows = 0
        for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False, encoding='utf-8')):
            chunk.columns = chunk.columns.str.strip()
            # 补齐字段
            if 'create_time' not in chunk.columns:
                chunk['create_time'] = pd.Timestamp.now()
            client.insert_dataframe('ads_price_index', chunk)
            total_rows += len(chunk)
            print(f"  已导入 {total_rows:,} 条...")
        print(f"  ✅ ads_price_index: {total_rows:,} 条 ({time.time()-t0:.1f}s)")
    else:
        print("  ⚠️ all_index.csv 不存在")

    print("\n" + "=" * 60)
    print("  ✅ 导入完成！")
    print("=" * 60)

    # 验证数据
    print("\n========== 数据验证 ==========")
    for t in tables:
        try:
            cnt = client.get_table_count(t)
            print(f"  {t}: {cnt:,} 条")
        except:
            print(f"  {t}: 查询失败")

    client.close()


if __name__ == "__main__":
    import_local_data()

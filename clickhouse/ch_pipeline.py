"""
ClickHouse数据处理管道 - 从OSS加载数据并计算价格指数
高性能：利用ClickHouse向量化计算，速度比pandas快10~100倍
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from ch_client import ClickHouseClient, get_client_from_config
from oss_utils import OSSClient, get_oss_client_from_config


class ClickHousePipeline:
    """ClickHouse数据处理管道"""

    def __init__(self, ch_client=None, oss_client=None):
        self.ch = ch_client or get_client_from_config()
        self.oss = oss_client or get_oss_client_from_config()

    def init_tables(self):
        """初始化所有表结构"""
        print('初始化ClickHouse表结构...')

        sql_files = [
            'clickhouse/sql/01_create_tables.sql',
        ]

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for sql_file in sql_files:
            full_path = os.path.join(base_dir, sql_file)
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    sql = f.read()
                statements = [s.strip() for s in sql.split(';') if s.strip()]
                for stmt in statements:
                    if stmt.upper().startswith('CREATE'):
                        try:
                            self.ch.execute(stmt)
                        except Exception as e:
                            if 'already exists' not in str(e).lower():
                                print(f'  警告: {e}')
        print('  ✓ 表结构初始化完成')

    def load_dim_data(self):
        """加载维度数据"""
        print('\n加载维度数据...')

        print('  加载商品维度表...')
        products_df = self.oss.read_csv('data/dim/products.csv', encoding='gbk')
        products_df = products_df.rename(columns={
            'name': 'product_name',
            'price': 'base_price'
        })
        products_df['create_time'] = int(time.time())
        products_df['update_time'] = int(time.time())

        products_df = products_df[['product_id', 'product_name', 'category_id',
                                   'base_price', 'weight', 'change_count',
                                   'create_time', 'update_time']]
        self.ch.insert_dataframe('dim_products', products_df)
        print(f'    ✓ 商品维度: {len(products_df):,} 条')

        print('  加载类目维度表...')
        categories_df = self.oss.read_csv('data/dim/categories.csv', encoding='gbk')
        categories_df = categories_df.rename(columns={
            'category': 'category_name',
            'parent': 'parent_id',
            'price': 'base_price'
        })
        categories_df['parent_id'] = categories_df['parent_id'].fillna(0).astype(int)
        categories_df['create_time'] = int(time.time())
        categories_df = categories_df[['category_id', 'category_name', 'hierarchy',
                                       'weight', 'base_price', 'parent_id',
                                       'create_time']]
        self.ch.insert_dataframe('dim_categories', categories_df)
        print(f'    ✓ 类目维度: {len(categories_df):,} 条')

    def load_ods_data(self, start_date=None, end_date=None):
        """
        加载ODS数据（从OSS到ClickHouse）

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        """
        print('\n加载ODS数据...')

        oss_files = self.oss.list_files('data/ods/')
        date_dirs = set()
        for f in oss_files:
            parts = f['key'].split('/')
            for p in parts:
                if p.startswith('dt='):
                    date_dirs.add(p.replace('dt=', ''))

        dates = sorted(date_dirs)
        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]

        print(f'  待加载日期: {len(dates)} 天')

        total_rows = 0
        for i, dt in enumerate(dates):
            oss_key = f'data/ods/dt={dt}/daily_prices.csv'
            try:
                df = self.oss.read_csv(oss_key, encoding='gbk')
                df = df.rename(columns={'name': 'product_name', 'change_date': 'dt'})
                df['dt'] = pd.to_datetime(df['dt']).dt.date

                df = df[['product_id', 'category_id', 'product_name', 'price', 'dt']]
                self.ch.insert_dataframe('ods_product_price', df)
                total_rows += len(df)

                if (i + 1) % 100 == 0 or i == len(dates) - 1:
                    print(f'    进度: {i+1}/{len(dates)} 天, 共 {total_rows:,} 条')
            except Exception as e:
                print(f'    ✗ {dt}: {e}')

        print(f'  ✓ 加载完成: {total_rows:,} 条记录')

    def build_dwd(self, dt=None):
        """构建DWD层数据"""
        print('\n构建DWD层数据...')

        date_cond = f"AND o.dt = '{dt}'" if dt else ''

        sql = f"""
        INSERT INTO dwd_product_price_detail
        WITH
            cat_l2 AS (
                SELECT category_id, category_name, parent_id, weight
                FROM dim_categories WHERE hierarchy = 2
            ),
            cat_l1 AS (
                SELECT category_id, category_name, weight AS l1_weight
                FROM dim_categories WHERE hierarchy = 1
            )
        SELECT
            p.product_id,
            p.product_name,
            o.category_id,
            c2.category_name,
            c1.category_id AS category_l1_id,
            c1.category_name AS category_l1,
            c2.category_id AS category_l2_id,
            c2.category_name AS category_l2,
            o.price,
            p.base_price,
            p.weight,
            o.dt
        FROM ods_product_price o
        INNER JOIN dim_products p ON o.product_id = p.product_id
        LEFT JOIN cat_l2 c2 ON intDiv(o.category_id, 100) * 100 = c2.category_id
        LEFT JOIN cat_l1 c1 ON c2.parent_id = c1.category_id
        WHERE o.price > 0
          AND p.base_price > 0
          AND c1.category_name IS NOT NULL
          {date_cond}
        """
        self.ch.execute(sql)
        count = self.ch.get_table_count('dwd_product_price_detail')
        print(f'  ✓ DWD层数据: {count:,} 条')

    def calculate_sku_index(self, dt=None):
        """计算SKU价格指数"""
        print('\n计算SKU价格指数...')

        date_cond = f"WHERE dt = '{dt}'" if dt else ''

        sql = f"""
        INSERT INTO dws_sku_price_index_daily
        SELECT
            product_id,
            product_name,
            category_id,
            category_name,
            category_l1,
            toDate('2025-05-17') AS base_date,
            price,
            base_price,
            round(price / base_price * 100, 4) AS price_index,
            weight AS index_weight,
            0 AS mom_change_rate,
            dt,
            now() AS create_time
        FROM dwd_product_price_detail
        {date_cond}
        """
        self.ch.execute(sql)
        count = self.ch.get_table_count('dws_sku_price_index_daily')
        print(f'  ✓ SKU指数: {count:,} 条')

    def calculate_category_index(self, dt=None):
        """计算类目价格指数"""
        print('\n计算类目价格指数...')

        date_cond = f"AND dt = '{dt}'" if dt else ''

        sql = f"""
        INSERT INTO dws_category_price_index_daily
        SELECT
            intDiv(category_id, 100) * 100 AS category_id,
            category_l2 AS category_name,
            category_l1,
            2 AS category_level,
            toDate('2025-05-17') AS base_date,
            round(sum(price_index * weight) / sum(weight), 4) AS price_index,
            count(DISTINCT product_id) AS product_count,
            max(c2_weight) AS index_weight,
            0 AS mom_change_rate,
            dt,
            now() AS create_time
        FROM (
            SELECT
                d.category_id,
                d.category_l2,
                d.category_l1,
                d.product_id,
                d.price_index,
                d.weight,
                c.weight AS c2_weight,
                d.dt
            FROM dws_sku_price_index_daily d
            LEFT JOIN dim_categories c
                ON intDiv(d.category_id, 100) * 100 = c.category_id
                AND c.hierarchy = 2
            WHERE 1=1 {date_cond}
        )
        GROUP BY dt, category_id, category_l2, category_l1
        """
        self.ch.execute(sql)

        sql_l1 = f"""
        INSERT INTO dws_category_price_index_daily
        SELECT
            c.parent_id AS category_id,
            c1.category_name AS category_name,
            c1.category_name AS category_l1,
            1 AS category_level,
            toDate('2025-05-17') AS base_date,
            round(sum(d.price_index * d.index_weight) / sum(d.index_weight), 4) AS price_index,
            sum(d.product_count) AS product_count,
            max(c1.weight) AS index_weight,
            0 AS mom_change_rate,
            d.dt,
            now() AS create_time
        FROM dws_category_price_index_daily d
        INNER JOIN dim_categories c ON d.category_id = c.category_id AND c.hierarchy = 2
        INNER JOIN dim_categories c1 ON c.parent_id = c1.category_id AND c1.hierarchy = 1
        WHERE d.category_level = 2
          {date_cond}
        GROUP BY d.dt, c.parent_id, c1.category_name
        """
        self.ch.execute(sql_l1)

        count = self.ch.get_table_count('dws_category_price_index_daily')
        print(f'  ✓ 类目指数: {count:,} 条')

    def calculate_overall_index(self, dt=None):
        """计算全网价格指数"""
        print('\n计算全网价格指数...')

        date_cond = f"AND d.dt = '{dt}'" if dt else ''

        sql = f"""
        INSERT INTO ads_overall_price_index
        SELECT
            'OVERALL' AS index_type,
            '全网价格指数' AS index_name,
            toDate('2025-05-17') AS base_date,
            round(sum(d.price_index * c1.weight * d.index_weight) / sum(c1.weight * d.index_weight), 4) AS price_index,
            0 AS mom_change_rate,
            d.dt,
            now() AS create_time
        FROM dws_category_price_index_daily d
        INNER JOIN dim_categories c ON d.category_id = c.category_id AND c.hierarchy = 2
        INNER JOIN dim_categories c1 ON c.parent_id = c1.category_id AND c1.hierarchy = 1
        WHERE d.category_level = 2
          {date_cond}
        GROUP BY d.dt
        """
        self.ch.execute(sql)

        sql_fisher = f"""
        INSERT INTO ads_overall_price_index
        SELECT
            'FISHER' AS index_type,
            '全网费雪指数' AS index_name,
            toDate('2025-05-17') AS base_date,
            round(sqrt(sum(weight * price) / sum(weight * base_price) *
                       sum(weight * price) / sum(weight * base_price)) * 100, 4) AS price_index,
            0 AS mom_change_rate,
            dt,
            now() AS create_time
        FROM dwd_product_price_detail
        WHERE 1=1 {date_cond}
        GROUP BY dt
        """
        self.ch.execute(sql_fisher)

        count = self.ch.get_table_count('ads_overall_price_index')
        print(f'  ✓ 全网指数: {count:,} 条')

    def calculate_mom(self):
        """计算日环比"""
        print('\n计算日环比...')

        # SKU指数日环比（使用窗口函数的替代方案）
        self.ch.execute("""
        ALTER TABLE dws_sku_price_index_daily
        UPDATE mom_change_rate = round(
            (price_index - prev_index) / prev_index * 100, 4
        )
        WHERE 1=1
        FROM (
            SELECT
                product_id,
                dt,
                price_index,
                any(price_index) OVER (
                    PARTITION BY product_id ORDER BY dt
                    ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING
                ) AS prev_index
            FROM dws_sku_price_index_daily
        ) AS t
        WHERE dws_sku_price_index_daily.product_id = t.product_id
          AND dws_sku_price_index_daily.dt = t.dt
          AND t.prev_index > 0
        """)

        count = self.ch.execute(
            "SELECT count() FROM dws_sku_price_index_daily WHERE mom_change_rate != 0"
        )[0][0]
        print(f'  ✓ SKU环比: {count:,} 条已更新')

    def run_full_pipeline(self):
        """运行完整数据管道"""
        start_time = time.time()
        print('=' * 60)
        print('ClickHouse价格指数计算 - 完整管道')
        print('=' * 60)

        self.init_tables()
        self.load_dim_data()
        self.load_ods_data()
        self.build_dwd()
        self.calculate_sku_index()
        self.calculate_category_index()
        self.calculate_overall_index()
        self.calculate_mom()

        elapsed = time.time() - start_time
        print('\n' + '=' * 60)
        print(f'处理完成！总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)')
        print('=' * 60)

    def run_daily_pipeline(self, dt):
        """运行单天数据管道（T+1调度用）"""
        print(f'处理日期: {dt}')
        self.build_dwd(dt)
        self.calculate_sku_index(dt)
        self.calculate_category_index(dt)
        self.calculate_overall_index(dt)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='ClickHouse数据处理管道')
    parser.add_argument('--init', action='store_true', help='初始化表结构')
    parser.add_argument('--load-dim', action='store_true', help='加载维度数据')
    parser.add_argument('--load-ods', action='store_true', help='加载ODS数据')
    parser.add_argument('--dwd', action='store_true', help='构建DWD层')
    parser.add_argument('--sku', action='store_true', help='计算SKU指数')
    parser.add_argument('--category', action='store_true', help='计算类目指数')
    parser.add_argument('--overall', action='store_true', help='计算全网指数')
    parser.add_argument('--mom', action='store_true', help='计算日环比')
    parser.add_argument('--full', action='store_true', help='运行完整管道')
    parser.add_argument('--date', help='指定处理日期 (YYYY-MM-DD)')
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--test', action='store_true', help='测试连接')

    args = parser.parse_args()

    pipeline = ClickHousePipeline()

    if args.test:
        print('测试ClickHouse连接...')
        if pipeline.ch.test_connection():
            print('  ✓ 连接成功')
        else:
            print('  ✗ 连接失败')
            return

    if args.init:
        pipeline.init_tables()

    if args.load_dim:
        pipeline.load_dim_data()

    if args.load_ods:
        pipeline.load_ods_data(args.start_date, args.end_date)

    if args.dwd:
        pipeline.build_dwd(args.date)

    if args.sku:
        pipeline.calculate_sku_index(args.date)

    if args.category:
        pipeline.calculate_category_index(args.date)

    if args.overall:
        pipeline.calculate_overall_index(args.date)

    if args.mom:
        pipeline.calculate_mom()

    if args.full:
        pipeline.run_full_pipeline()


if __name__ == '__main__':
    import pandas as pd
    main()

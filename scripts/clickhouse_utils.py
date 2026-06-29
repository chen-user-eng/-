"""
ClickHouse 工具类
用于连接ClickHouse、创建表、数据写入和查询
"""
import clickhouse_connect
import pandas as pd
from typing import Optional, List, Dict, Any
import threading
import config

# 线程本地存储
_local = threading.local()


class ClickHouseClient:
    """ClickHouse客户端封装"""

    def __init__(self):
        self.client = None
        self._connect()

    def _connect(self):
        """建立连接"""
        try:
            self.client = clickhouse_connect.get_client(
                host=config.CLICKHOUSE_HOST,
                port=config.CLICKHOUSE_PORT,
                username=config.CLICKHOUSE_USER,
                password=config.CLICKHOUSE_PASSWORD
            )
            try:
                self.client.command(f"USE {config.CLICKHOUSE_DATABASE}")
            except:
                pass
        except Exception as e:
            print(f"❌ ClickHouse连接失败: {e}")
            self.client = None

    def is_connected(self) -> bool:
        """检查连接状态"""
        if self.client is None:
            return False
        try:
            self.client.query("SELECT 1")
            return True
        except:
            return False

    def create_database(self):
        """创建数据库"""
        if not self.client:
            return
        self.client.command(f"CREATE DATABASE IF NOT EXISTS {config.CLICKHOUSE_DATABASE}")
        print(f"✅ 数据库 {config.CLICKHOUSE_DATABASE} 就绪")

    def create_tables(self):
        """创建所有表"""
        if not self.client:
            return

        # 类目维度表
        self.client.command("""
            CREATE TABLE IF NOT EXISTS dim_categories (
                category_id String,
                category_name String,
                hierarchy UInt8,
                parent_id String,
                weight Float64,
                base_price Float64,
                create_time DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY category_id
        """)

        # 商品维度表
        self.client.command("""
            CREATE TABLE IF NOT EXISTS dim_products (
                product_id String,
                category_id String,
                category_id_l2 String,
                category_id_l1 String,
                name String,
                weight Float64,
                base_price Float64,
                create_time DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY product_id
        """)

        # ADS层价格指数表（核心表）
        self.client.command("""
            CREATE TABLE IF NOT EXISTS ads_price_index (
                dt String,
                index_type String,
                target_id String,
                target_name String,
                price Float64,
                base_price Float64,
                price_index Float64,
                mom_change_rate Float64,
                category_id String,
                category_id_l2 String,
                category_id_l1 String,
                category_name String,
                category_l1 String,
                create_time DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY (index_type, target_id, dt)
            PARTITION BY index_type
        """)

        # 异常数据表
        self.client.command("""
            CREATE TABLE IF NOT EXISTS ads_anomaly (
                dt String,
                product_id String,
                product_name String,
                category_l1 String,
                current_price Float64,
                base_price Float64,
                anomaly_type String,
                anomaly_desc String,
                change_rate Float64,
                z_score Float64,
                price_ratio Float64,
                create_time DateTime DEFAULT now()
            ) ENGINE = MergeTree()
            ORDER BY (dt, product_id)
            PARTITION BY anomaly_type
        """)

        print("✅ 所有表创建完成")

    def insert_dataframe(self, table: str, df: pd.DataFrame, batch_size: int = 100000):
        """批量写入DataFrame"""
        if not self.client or df.empty:
            return

        total = len(df)
        for i in range(0, total, batch_size):
            batch_df = df.iloc[i:i+batch_size]
            try:
                self.client.insert_df(table, batch_df)
                print(f"  已插入 {min(i+batch_size, total)}/{total} 条")
            except Exception as e:
                print(f"  插入失败: {e}")

    def query(self, sql: str) -> pd.DataFrame:
        """执行查询并返回DataFrame"""
        if not self.client:
            return pd.DataFrame()

        try:
            return self.client.query_df(sql)
        except Exception as e:
            print(f"查询失败: {e}")
            return pd.DataFrame()

    def truncate_table(self, table: str):
        """清空表"""
        if not self.client:
            return
        self.client.command(f"TRUNCATE TABLE {table}")
        print(f"✅ 表 {table} 已清空")

    def drop_table(self, table: str):
        """删除表"""
        if not self.client:
            return
        self.client.command(f"DROP TABLE IF EXISTS {table}")
        print(f"✅ 表 {table} 已删除")

    def get_table_count(self, table: str) -> int:
        """获取表记录数"""
        if not self.client:
            return 0
        try:
            df = self.client.query_df(f"SELECT count() as cnt FROM {table}")
            return int(df['cnt'].iloc[0])
        except:
            return 0

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            self.client = None


def get_ch_client() -> ClickHouseClient:
    """获取ClickHouse客户端（每个线程独立实例）"""
    client = getattr(_local, 'ch_client', None)
    if client is None or not client.is_connected():
        client = ClickHouseClient()
        _local.ch_client = client
    return client


def init_clickhouse():
    """初始化ClickHouse（创建数据库和表）"""
    client = ClickHouseClient()
    if client.is_connected():
        client.create_database()
        client.create_tables()
        client.close()
        return True
    return False


if __name__ == "__main__":
    # 测试连接
    client = ClickHouseClient()
    if client.is_connected():
        print("\n点击任意键初始化表结构...")
        input()
        client.create_database()
        client.create_tables()

        print(f"\n当前数据量:")
        print(f"  ads_price_index: {client.get_table_count('ads_price_index')} 条")
        print(f"  ads_anomaly: {client.get_table_count('ads_anomaly')} 条")
    client.close()

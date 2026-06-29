"""
ClickHouse客户端工具
封装ClickHouse连接和常用操作
"""
import time
from clickhouse_driver import Client


class ClickHouseClient:
    """ClickHouse客户端封装"""

    def __init__(self, host, port=9000, username='default', password='',
                 database='default', connect_timeout=30):
        """
        初始化ClickHouse客户端

        Args:
            host: ClickHouse主机地址
            port: 端口（默认9000）
            username: 用户名
            password: 密码
            database: 数据库名
            connect_timeout: 连接超时时间（秒）
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.client = Client(
            host=host,
            port=port,
            user=username,
            password=password,
            database=database,
            connect_timeout=connect_timeout
        )

    def test_connection(self):
        """测试连接"""
        try:
            result = self.client.execute('SELECT 1')
            return result[0][0] == 1
        except Exception as e:
            print(f'连接失败: {e}')
            return False

    def execute(self, sql, params=None):
        """执行SQL语句"""
        return self.client.execute(sql, params)

    def query_df(self, sql, params=None):
        """查询并返回DataFrame"""
        return self.client.query_dataframe(sql, params)

    def insert_dataframe(self, table, df):
        """插入DataFrame到表中"""
        return self.client.insert_dataframe(
            f'INSERT INTO {table} VALUES',
            df
        )

    def get_table_count(self, table):
        """获取表记录数"""
        result = self.client.execute(f'SELECT count() FROM {table}')
        return result[0][0]

    def get_table_size(self, table):
        """获取表大小（字节）"""
        result = self.client.execute(
            f"SELECT sum(bytes) FROM system.parts WHERE table = '{table}' AND active"
        )
        return result[0][0] if result[0][0] else 0

    def optimize_table(self, table):
        """优化表（合并分区）"""
        self.client.execute(f'OPTIMIZE TABLE {table} FINAL')


def get_client_from_config(config=None):
    """
    从配置创建ClickHouse客户端

    Args:
        config: 配置对象，包含CH_HOST, CH_PORT, CH_USER, CH_PASSWORD, CH_DATABASE
    """
    if config is None:
        try:
            from config import (
                CH_HOST, CH_PORT, CH_USER, CH_PASSWORD, CH_DATABASE
            )
            config = type('Config', (), {
                'CH_HOST': CH_HOST,
                'CH_PORT': CH_PORT,
                'CH_USER': CH_USER,
                'CH_PASSWORD': CH_PASSWORD,
                'CH_DATABASE': CH_DATABASE
            })()
        except ImportError:
            raise ValueError('未找到ClickHouse配置，请在config.py中配置')

    return ClickHouseClient(
        host=config.CH_HOST,
        port=config.CH_PORT,
        username=config.CH_USER,
        password=config.CH_PASSWORD,
        database=config.CH_DATABASE
    )

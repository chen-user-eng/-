"""
OSS + ClickHouse ETL流水线
从OSS下载数据并导入到ClickHouse
支持增量同步和全量同步
"""
import os
import sys
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scripts.oss_utils import OSSUtils
from scripts.clickhouse_utils import get_ch_client, init_clickhouse
from scripts.import_to_clickhouse import import_dim_tables, import_ads_data, import_anomaly_data


def download_from_oss(force: bool = False):
    """从OSS下载数据到本地"""
    print("\n" + "="*60)
    print("从OSS下载数据")
    print("="*60)

    oss = OSSUtils()
    local_data = config.LOCAL_DATA_DIR
    oss_prefix = config.OSS_DATA_PREFIX

    # 检查OSS连接
    if not oss.test_connection():
        print("❌ OSS连接失败")
        return False

    # 下载所有数据
    print(f"\n从 OSS {config.OSS_BUCKET}/{oss_prefix} 下载到 {local_data}")

    success, failed = oss.download_directory(
        oss_prefix,
        local_data,
        force=force
    )

    print(f"\n下载完成:")
    print(f"  ✅ 成功: {success} 个文件")
    print(f"  ❌ 失败: {failed} 个文件")

    return failed == 0


def sync_to_clickhouse():
    """同步数据到ClickHouse"""
    print("\n" + "="*60)
    print("同步数据到ClickHouse")
    print("="*60)

    # 初始化ClickHouse
    if not init_clickhouse():
        print("❌ ClickHouse连接失败")
        return False

    # 导入数据
    import_dim_tables()
    import_ads_data()
    import_anomaly_data()

    return True


def full_sync():
    """全量同步：OSS → 本地 → ClickHouse"""
    print("\n" + "="*60)
    print("全量同步模式")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start_time = time.time()

    # 1. 从OSS下载
    if not download_from_oss(force=True):
        print("❌ OSS下载失败")
        return False

    # 2. 同步到ClickHouse
    if not sync_to_clickhouse():
        print("❌ ClickHouse同步失败")
        return False

    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print(f"全量同步完成! 耗时: {elapsed/60:.1f} 分钟")
    print("="*60)

    # 输出统计
    client = get_ch_client()
    if client.is_connected():
        print("\nClickHouse当前数据量:")
        print(f"  ads_price_index: {client.get_table_count('ads_price_index'):,} 条")
        print(f"  ads_anomaly:     {client.get_table_count('ads_anomaly'):,} 条")
        client.close()

    return True


def incremental_sync():
    """增量同步：只同步最新日期的数据"""
    print("\n" + "="*60)
    print("增量同步模式")
    print("="*60)

    # 获取最新日期
    client = get_ch_client()
    if not client.is_connected():
        print("❌ ClickHouse连接失败")
        return False

    # 查询最新日期
    result = client.query("""
        SELECT max(dt) as latest_date
        FROM ads_price_index
    """)
    latest_date = result['latest_date'].iloc[0] if len(result) > 0 else None

    if latest_date:
        print(f"当前最新日期: {latest_date}")
        print("增量同步需要下载新数据文件...")
        print("提示: 请将新日期的数据文件上传到OSS后再运行全量同步")
    else:
        print("ClickHouse为空，将执行全量同步")
        return full_sync()

    client.close()
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description='OSS + ClickHouse ETL流水线')
    parser.add_argument('mode', choices=['full', 'incremental', 'download', 'ck'],
                       help='模式: full(全量同步), incremental(增量同步), download(只下载), ck(只同步到ClickHouse)')
    parser.add_argument('--force', action='store_true',
                       help='强制下载（覆盖本地文件）')

    args = parser.parse_args()

    print("\n" + "="*60)
    print("OSS + ClickHouse ETL流水线")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.mode == 'full':
        full_sync()
    elif args.mode == 'incremental':
        incremental_sync()
    elif args.mode == 'download':
        download_from_oss(force=args.force)
    elif args.mode == 'ck':
        sync_to_clickhouse()


if __name__ == "__main__":
    main()

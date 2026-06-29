"""
OSS数据处理管道 - 从阿里云OSS读取数据并处理
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 尝试导入配置
try:
    from config import (
        OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET,
        OSS_ENDPOINT, OSS_BUCKET,
        OSS_DATA_PREFIX, OSS_ODS_PREFIX, OSS_DIM_PREFIX, OSS_ADS_PREFIX,
        LOCAL_DATA_DIR
    )
    DATA_DIR = LOCAL_DATA_DIR
except ImportError:
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    print('警告: 未找到config.py，使用默认配置')

sys.path.insert(0, os.path.join(BASE_DIR, 'scripts'))
from oss_utils import OSSClient
from process_fast import (
    load_dim_tables, clean_data_batch, calculate_all_indices,
    save_dwd_daily, save_dws_daily, save_ads_daily, generate_reports
)


class OSSDataPipeline:
    """基于OSS的数据处理管道"""

    def __init__(self, access_key_id=None, access_key_secret=None,
                 endpoint=None, bucket_name=None):
        """初始化OSS管道"""
        # 优先使用参数，其次使用配置文件
        if not access_key_id:
            try:
                from config import (OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET,
                                    OSS_ENDPOINT, OSS_BUCKET)
                access_key_id = OSS_ACCESS_KEY_ID
                access_key_secret = OSS_ACCESS_KEY_SECRET
                endpoint = OSS_ENDPOINT
                bucket_name = OSS_BUCKET
            except ImportError:
                raise ValueError('请提供OSS配置或创建config.py文件')

        self.oss = OSSClient(access_key_id, access_key_secret, endpoint, bucket_name)
        self.data_dir = DATA_DIR

    def download_dim_data(self, oss_prefix='data/dim/'):
        """从OSS下载维度表"""
        print('  从OSS下载维度表...')
        files = self.oss.list_files(oss_prefix)
        downloaded = 0
        for f in files:
            if f['key'].endswith('.csv'):
                filename = os.path.basename(f['key'])
                local_path = os.path.join(self.data_dir, 'dim', filename)
                self.oss.download_file(f['key'], local_path)
                downloaded += 1
        print(f'  下载了 {downloaded} 个维度表文件')
        return downloaded

    def download_ods_data(self, oss_prefix='data/ods/', start_date=None, end_date=None):
        """
        从OSS下载ODS数据

        Args:
            oss_prefix: OSS中ODS数据的前缀
            start_date: 开始日期 (YYYY-MM-DD)，可选
            end_date: 结束日期 (YYYY-MM-DD)，可选
        """
        print('  从OSS下载ODS数据...')
        files = self.oss.list_files(oss_prefix)

        # 过滤日期范围
        if start_date or end_date:
            filtered = []
            for f in files:
                # 从路径中提取日期，如 data/ods/dt=2025-05-17/product_price.csv
                parts = f['key'].split('/')
                for part in parts:
                    if part.startswith('dt='):
                        date_str = part.split('=')[1]
                        if start_date and date_str < start_date:
                            break
                        if end_date and date_str > end_date:
                            break
                        filtered.append(f)
                        break
            files = filtered

        downloaded = 0
        total = len(files)
        for i, f in enumerate(files):
            if f['key'].endswith('.csv'):
                # 保持目录结构
                rel_path = f['key'][len(oss_prefix):].lstrip('/')
                local_path = os.path.join(self.data_dir, 'ods', rel_path)
                self.oss.download_file(f['key'], local_path)
                downloaded += 1
            if (i + 1) % 100 == 0:
                print(f'    下载进度: {i+1}/{total}', end='\r')
                sys.stdout.flush()

        print(f'  下载了 {downloaded} 个ODS数据文件')
        return downloaded

    def read_dim_from_oss(self, oss_prefix='data/dim/'):
        """直接从OSS读取维度表（不落地）"""
        print('  从OSS读取维度表...')
        products_df = self.oss.read_csv(
            os.path.join(oss_prefix, 'products.csv'),
            encoding='utf-8-sig'
        )
        categories_df = self.oss.read_csv(
            os.path.join(oss_prefix, 'categories.csv'),
            encoding='utf-8-sig'
        )
        print(f'    商品表: {len(products_df)} 条')
        print(f'    类目表: {len(categories_df)} 条')
        return products_df, categories_df

    def read_ods_from_oss(self, oss_prefix='data/ods/', dates=None):
        """直接从OSS读取ODS数据（不落地，内存处理）"""
        print(f'  从OSS读取ODS数据...')
        files = self.oss.list_files(oss_prefix)

        if dates:
            date_set = set(dates)
            files = [f for f in files if any(
                f'dt={d}' in f['key'] for d in date_set
            )]

        all_data = []
        total = len(files)

        for i, f in enumerate(files):
            if f['key'].endswith('.csv'):
                df = self.oss.read_csv(f['key'], encoding='utf-8-sig')
                # 从路径提取日期
                parts = f['key'].split('/')
                for part in parts:
                    if part.startswith('dt='):
                        df['dt'] = part.split('=')[1]
                        break
                all_data.append(df)
            if (i + 1) % 50 == 0:
                print(f'    读取进度: {i+1}/{total}', end='\r')
                sys.stdout.flush()

        result = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
        print(f'    读取完成: {len(result):,} 条记录')
        return result

    def upload_results(self, local_data_dir=None, oss_prefix='data/'):
        """上传处理结果到OSS"""
        if not local_data_dir:
            local_data_dir = self.data_dir

        print('  上传处理结果到OSS...')
        uploaded = self.oss.upload_dir(local_data_dir, oss_prefix)
        print(f'  上传了 {uploaded} 个文件')
        return uploaded

    def run_full_pipeline(self, oss_prefix='data/', download=True, upload=True):
        """
        运行完整数据处理管道

        Args:
            oss_prefix: OSS中数据的前缀
            download: 是否从OSS下载数据
            upload: 是否上传结果到OSS
        """
        import time
        start_time = time.time()

        print('=' * 60)
        print('OSS数据处理管道 - 全流程')
        print('=' * 60)

        # 1. 加载维度表
        print('\n[1/6] 加载维度表...')
        if download:
            self.download_dim_data(oss_prefix + 'dim/')
        products_df, cat_map, categories_df = load_dim_tables()
        print(f'  商品维度表: {len(products_df):,} 条')
        print(f'  类目维度表: {len(categories_df):,} 条')

        # 2. 加载ODS数据
        print('\n[2/6] 加载ODS数据...')
        if download:
            self.download_ods_data(oss_prefix + 'ods/')

        # 从本地加载
        from process_fast import load_all_ods_data
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
        ads_all_path = os.path.join(self.data_dir, 'ads', 'all_index.csv')
        all_index.to_csv(ads_all_path, index=False, encoding='utf-8-sig')
        print(f'  全量指数数据: {len(all_index):,} 条')

        # 6. 生成日报
        print('\n[6/6] 生成每日报告...')
        generate_reports(all_index, products_df, categories_df)

        # 上传结果
        if upload:
            print('\n上传结果到OSS...')
            self.upload_results(self.data_dir, oss_prefix)

        elapsed = time.time() - start_time
        print('\n' + '=' * 60)
        print(f'处理完成！总耗时: {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)')
        print(f'  - 处理天数: {all_index["dt"].nunique()} 天')
        print(f'  - 指数记录: {len(all_index):,} 条')
        print('=' * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='OSS数据处理管道')
    parser.add_argument('--upload', action='store_true', help='上传本地数据到OSS')
    parser.add_argument('--download', action='store_true', help='从OSS下载数据')
    parser.add_argument('--run', action='store_true', help='运行完整管道')
    parser.add_argument('--list', action='store_true', help='列出OSS文件')
    parser.add_argument('--prefix', default='data/', help='OSS数据前缀')
    parser.add_argument('--local-dir', default=None, help='本地数据目录')

    args = parser.parse_args()

    try:
        from config import (OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET,
                            OSS_ENDPOINT, OSS_BUCKET)
        pipeline = OSSDataPipeline(
            OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET,
            OSS_ENDPOINT, OSS_BUCKET
        )
    except ImportError:
        print('错误: 请先创建config.py并配置OSS信息')
        print('  cp config.example.py config.py')
        return

    if args.list:
        print(f'列出OSS中 {args.prefix} 下的文件:')
        files = pipeline.oss.list_files(args.prefix)
        for f in files[:50]:
            print(f'  {f["key"]} ({f["size"]} bytes)')
        if len(files) > 50:
            print(f'  ... 共 {len(files)} 个文件')
    elif args.upload:
        local_dir = args.local_dir or DATA_DIR
        print(f'上传 {local_dir} 到 OSS:{args.prefix}')
        count = pipeline.oss.upload_dir(local_dir, args.prefix)
        print(f'上传完成: {count} 个文件')
    elif args.download:
        local_dir = args.local_dir or DATA_DIR
        print(f'从 OSS:{args.prefix} 下载到 {local_dir}')
        count = pipeline.oss.download_dir(args.prefix, local_dir)
        print(f'下载完成: {count} 个文件')
    elif args.run:
        pipeline.run_full_pipeline(oss_prefix=args.prefix, download=True, upload=True)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

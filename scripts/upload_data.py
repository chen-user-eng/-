"""
批量数据上传到OSS工具
支持：进度显示、断点续传、多线程上传
"""
import os
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oss_utils import OSSClient, get_oss_client_from_config


class DataUploader:
    """数据上传器"""

    def __init__(self, oss_client=None, max_workers=5):
        self.oss = oss_client or get_oss_client_from_config()
        self.max_workers = max_workers
        self.uploaded_count = 0
        self.total_count = 0
        self.total_size = 0
        self.uploaded_size = 0
        self.start_time = 0
        self.lock = __import__('threading').Lock()

    def get_file_size(self, filepath):
        """获取文件大小"""
        try:
            return os.path.getsize(filepath)
        except:
            return 0

    def format_size(self, size_bytes):
        """格式化大小显示"""
        if size_bytes >= 1024 * 1024 * 1024:
            return f'{size_bytes / 1024 / 1024 / 1024:.2f} GB'
        elif size_bytes >= 1024 * 1024:
            return f'{size_bytes / 1024 / 1024:.2f} MB'
        elif size_bytes >= 1024:
            return f'{size_bytes / 1024:.2f} KB'
        else:
            return f'{size_bytes} B'

    def format_time(self, seconds):
        """格式化时间显示"""
        if seconds < 60:
            return f'{seconds:.1f}秒'
        elif seconds < 3600:
            return f'{seconds / 60:.1f}分钟'
        else:
            return f'{seconds / 3600:.1f}小时'

    def print_progress(self, filename=''):
        """打印进度"""
        with self.lock:
            elapsed = time.time() - self.start_time
            if self.uploaded_count > 0:
                speed = self.uploaded_size / elapsed if elapsed > 0 else 0
                remaining = (self.total_size - self.uploaded_size) / speed if speed > 0 else 0
            else:
                speed = 0
                remaining = 0

            percent = self.uploaded_count / self.total_count * 100 if self.total_count > 0 else 0

            progress_bar = '=' * int(percent / 2) + '-' * (50 - int(percent / 2))
            sys.stdout.write(f'\r[{progress_bar}] {percent:.1f}%  '
                           f'{self.uploaded_count}/{self.total_count} 文件  '
                           f'{self.format_size(self.uploaded_size)}/{self.format_size(self.total_size)}  '
                           f'速度: {self.format_size(speed)}/s  '
                           f'剩余: {self.format_time(remaining)}')
            sys.stdout.flush()

    def upload_single_file(self, local_path, oss_key, skip_existing=True):
        """上传单个文件"""
        try:
            # 检查是否已存在（断点续传）
            if skip_existing and self.oss.file_exists(oss_key):
                file_size = self.get_file_size(local_path)
                with self.lock:
                    self.uploaded_count += 1
                    self.uploaded_size += file_size
                    self.print_progress()
                return True, 'skip'

            file_size = self.get_file_size(local_path)
            self.oss.upload_file(local_path, oss_key)

            with self.lock:
                self.uploaded_count += 1
                self.uploaded_size += file_size
                self.print_progress()

            return True, 'upload'
        except Exception as e:
            return False, str(e)

    def upload_dim_files(self, source_dir, skip_existing=True):
        """上传维度表文件"""
        print('\n' + '=' * 60)
        print('上传维度表数据')
        print('=' * 60)

        files = []

        # products.csv
        products_file = os.path.join(source_dir, 'products.csv')
        if os.path.exists(products_file):
            files.append((products_file, 'data/dim/products.csv'))

        # categories.csv
        categories_file = os.path.join(source_dir, 'categories.csv')
        if os.path.exists(categories_file):
            files.append((categories_file, 'data/dim/categories.csv'))

        self.total_count = len(files)
        self.total_size = sum(self.get_file_size(f[0]) for f in files)
        self.uploaded_count = 0
        self.uploaded_size = 0
        self.start_time = time.time()

        print(f'待上传文件: {self.total_count} 个, 总计: {self.format_size(self.total_size)}')
        print()

        for local_path, oss_key in files:
            success, status = self.upload_single_file(local_path, oss_key, skip_existing)
            filename = os.path.basename(local_path)
            if status == 'skip':
                print(f'  ✓ [跳过] {filename} (已存在)')
            elif success:
                print(f'  ✓ [上传] {filename}')
            else:
                print(f'  ✗ [失败] {filename}: {status}')

        elapsed = time.time() - self.start_time
        print(f'\n完成! 耗时: {self.format_time(elapsed)}')
        return self.uploaded_count

    def upload_ods_files(self, source_dir, skip_existing=True, max_workers=None):
        """上传ODS每日价格数据"""
        print('\n' + '=' * 60)
        print('上传ODS每日价格数据')
        print('=' * 60)

        daily_price_dir = os.path.join(source_dir, 'daily_price')
        if not os.path.exists(daily_price_dir):
            print(f'错误: 目录不存在: {daily_price_dir}')
            return 0

        # 收集所有文件
        files = []
        for filename in sorted(os.listdir(daily_price_dir)):
            if filename.startswith('daily_prices_') and filename.endswith('.csv'):
                local_path = os.path.join(daily_price_dir, filename)
                # 从文件名提取日期：daily_prices_20250517.csv -> 2025-05-17
                date_str = filename.replace('daily_prices_', '').replace('.csv', '')
                formatted_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
                oss_key = f'data/ods/dt={formatted_date}/daily_prices.csv'
                files.append((local_path, oss_key))

        self.total_count = len(files)
        self.total_size = sum(self.get_file_size(f[0]) for f in files)
        self.uploaded_count = 0
        self.uploaded_size = 0
        self.start_time = time.time()

        workers = max_workers or self.max_workers
        print(f'待上传文件: {self.total_count} 个, 总计: {self.format_size(self.total_size)}')
        print(f'上传线程数: {workers}')
        print()

        # 多线程上传
        success_count = 0
        skip_count = 0
        fail_count = 0
        fail_files = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.upload_single_file, local_path, oss_key, skip_existing): (local_path, oss_key)
                for local_path, oss_key in files
            }

            for future in as_completed(futures):
                local_path, oss_key = futures[future]
                try:
                    success, status = future.result()
                    if success:
                        if status == 'skip':
                            skip_count += 1
                        else:
                            success_count += 1
                    else:
                        fail_count += 1
                        fail_files.append((local_path, status))
                except Exception as e:
                    fail_count += 1
                    fail_files.append((local_path, str(e)))

        print()
        print()
        elapsed = time.time() - self.start_time
        print(f'上传完成! 总耗时: {self.format_time(elapsed)}')
        print(f'  成功上传: {success_count} 个')
        print(f'  跳过(已存在): {skip_count} 个')
        print(f'  失败: {fail_count} 个')

        if fail_files:
            print(f'\n失败文件列表 (前10个):')
            for f, err in fail_files[:10]:
                print(f'  - {os.path.basename(f)}: {err}')

        return success_count + skip_count

    def upload_all(self, source_dir, skip_existing=True, max_workers=None):
        """上传所有数据"""
        total_start = time.time()

        print('=' * 60)
        print('高频电商价格指数平台 - 数据上传工具')
        print('=' * 60)
        print(f'数据源目录: {source_dir}')
        print(f'断点续传: {"开启" if skip_existing else "关闭"}')

        # 测试连接
        print('\n测试OSS连接...')
        ok, msg = self.oss.test_connection()
        if not ok:
            print(f'连接失败: {msg}')
            return False
        print(f'  ✓ 连接成功')

        # 上传维度表
        dim_count = self.upload_dim_files(source_dir, skip_existing)

        # 上传ODS数据
        ods_count = self.upload_ods_files(source_dir, skip_existing, max_workers)

        total_elapsed = time.time() - total_start
        print('\n' + '=' * 60)
        print(f'全部上传完成! 总耗时: {self.format_time(total_elapsed)}')
        print(f'  维度表: {dim_count} 个文件')
        print(f'  ODS数据: {ods_count} 个文件')
        print('=' * 60)

        return True


def main():
    parser = argparse.ArgumentParser(description='数据上传到OSS工具')
    parser.add_argument('--source', '-s',
                       default=r'D:\cxdownload\data\data',
                       help='数据源目录 (默认: D:\\cxdownload\\data\\data)')
    parser.add_argument('--dim-only', action='store_true', help='只上传维度表')
    parser.add_argument('--ods-only', action='store_true', help='只上传ODS数据')
    parser.add_argument('--workers', '-w', type=int, default=5,
                       help='上传线程数 (默认: 5)')
    parser.add_argument('--no-skip', action='store_true',
                       help='不跳过已存在的文件（覆盖上传）')
    parser.add_argument('--test', action='store_true', help='只测试连接')

    args = parser.parse_args()

    uploader = DataUploader(max_workers=args.workers)

    if args.test:
        print('测试OSS连接...')
        ok, msg = uploader.oss.test_connection()
        print(f'结果: {msg}')
        return

    skip_existing = not args.no_skip

    if args.dim_only:
        uploader.upload_dim_files(args.source, skip_existing)
    elif args.ods_only:
        uploader.upload_ods_files(args.source, skip_existing)
    else:
        uploader.upload_all(args.source, skip_existing, args.workers)


if __name__ == '__main__':
    main()

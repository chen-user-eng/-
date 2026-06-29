"""
阿里云OSS工具模块 - 增强版
提供文件上传、下载、列出等功能，优化异常处理和分页策略
"""
import os
import io
import time
import pandas as pd
import oss2
from oss2.exceptions import NoSuchKey, RequestError


class OSSClient:
    """阿里云OSS客户端封装 - 增强版"""

    def __init__(self, access_key_id, access_key_secret, endpoint, bucket_name,
                 connect_timeout=30):
        """
        初始化OSS客户端

        Args:
            access_key_id: 阿里云AccessKey ID
            access_key_secret: 阿里云AccessKey Secret
            endpoint: OSS地域节点，如 'oss-cn-hangzhou.aliyuncs.com'
            bucket_name: Bucket名称
            connect_timeout: 连接超时时间（秒）
        """
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.connect_timeout = connect_timeout
        self.auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(self.auth, endpoint, bucket_name)

    def test_connection(self):
        """测试OSS连接是否正常"""
        try:
            self.bucket.get_bucket_info()
            return True, '连接成功'
        except RequestError as e:
            return False, f'连接失败: {str(e)}'
        except Exception as e:
            return False, f'连接异常: {type(e).__name__}: {str(e)}'

    def upload_file(self, local_file, oss_key):
        """
        上传本地文件到OSS

        Args:
            local_file: 本地文件路径
            oss_key: OSS中的对象键（即文件路径）
        """
        try:
            self.bucket.put_object_from_file(oss_key, local_file)
            return f'oss://{self.bucket_name}/{oss_key}'
        except RequestError as e:
            raise RuntimeError(f'上传失败: {str(e)}')

    def download_file(self, oss_key, local_file):
        """
        从OSS下载文件到本地

        Args:
            oss_key: OSS中的对象键
            local_file: 本地保存路径
        """
        os.makedirs(os.path.dirname(local_file), exist_ok=True)
        try:
            self.bucket.get_object_to_file(oss_key, local_file)
            return local_file
        except NoSuchKey:
            raise FileNotFoundError(f'OSS文件不存在: {oss_key}')
        except RequestError as e:
            raise RuntimeError(f'下载失败: {str(e)}')

    def read_csv(self, oss_key, **kwargs):
        """
        直接读取OSS中的CSV文件为DataFrame（不落地到本地）

        Args:
            oss_key: OSS中的CSV文件路径
            **kwargs: pandas.read_csv的参数
        """
        try:
            result = self.bucket.get_object(oss_key)
            content = result.read()
            return pd.read_csv(io.BytesIO(content), **kwargs)
        except NoSuchKey:
            raise FileNotFoundError(f'OSS文件不存在: {oss_key}')
        except RequestError as e:
            raise RuntimeError(f'读取失败: {str(e)}')

    def write_csv(self, df, oss_key, **kwargs):
        """
        将DataFrame直接写入OSS中的CSV文件（不落地到本地）

        Args:
            df: pandas DataFrame
            oss_key: OSS中的CSV文件路径
            **kwargs: pandas.to_csv的参数
        """
        try:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False, **kwargs)
            self.bucket.put_object(oss_key, csv_buffer.getvalue().encode('utf-8-sig'))
            return f'oss://{self.bucket_name}/{oss_key}'
        except RequestError as e:
            raise RuntimeError(f'写入失败: {str(e)}')

    def list_files(self, prefix='', max_keys=1000, max_pages=100):
        """
        列出OSS中指定前缀的文件

        Args:
            prefix: 文件前缀（相当于目录路径）
            max_keys: 每页最大数量
            max_pages: 最大页数（防止无限循环）

        Returns:
            list: 文件列表，每个元素包含 key, size, last_modified
        """
        files = []

        try:
            for obj in oss2.ObjectIteratorV2(self.bucket, prefix=prefix, max_keys=max_keys):
                files.append({
                    'key': obj.key,
                    'size': obj.size,
                    'last_modified': obj.last_modified,
                })
                if len(files) >= max_keys * max_pages:
                    break

        except RequestError as e:
            raise RuntimeError(f'列出文件失败: {str(e)}')
        except KeyboardInterrupt:
            print(f'\n用户中断，已列出 {len(files)} 个文件')

        return files

    def list_dirs(self, prefix=''):
        """
        列出OSS中指定前缀下的子目录（一级目录）
        """
        dirs = []
        try:
            result = self.bucket.list_objects_v2(prefix=prefix, delimiter='/')
            for prefix_dir in result.prefix_list:
                dirs.append(prefix_dir.rstrip('/'))
        except RequestError as e:
            raise RuntimeError(f'列出目录失败: {str(e)}')
        return dirs

    def file_exists(self, oss_key):
        """检查OSS文件是否存在"""
        try:
            self.bucket.get_object_meta(oss_key)
            return True
        except NoSuchKey:
            return False
        except RequestError:
            return False

    def upload_dir(self, local_dir, oss_prefix='', progress_callback=None):
        """
        上传整个本地目录到OSS

        Args:
            local_dir: 本地目录路径
            oss_prefix: OSS中的前缀（相当于目标目录）
            progress_callback: 进度回调函数(uploaded_count, total_count, current_file)
        """
        # 先统计文件总数
        all_files = []
        for root, dirs, files in os.walk(local_dir):
            for filename in files:
                local_path = os.path.join(root, filename)
                rel_path = os.path.relpath(local_path, local_dir)
                oss_key = os.path.join(oss_prefix, rel_path).replace('\\', '/')
                all_files.append((local_path, oss_key))

        total = len(all_files)
        uploaded = 0

        for local_path, oss_key in all_files:
            try:
                self.bucket.put_object_from_file(oss_key, local_path)
                uploaded += 1
                if progress_callback:
                    progress_callback(uploaded, total, local_path)
            except RequestError as e:
                print(f'  警告: 上传失败 {local_path}: {str(e)}')

        return uploaded

    def download_dir(self, oss_prefix, local_dir, max_files=None,
                     progress_callback=None):
        """
        下载OSS中整个目录到本地

        Args:
            oss_prefix: OSS中的前缀（目录路径）
            local_dir: 本地保存目录
            max_files: 最大下载文件数（可选，用于测试）
            progress_callback: 进度回调函数(downloaded_count, total_count, current_key)
        """
        # 先列出所有文件
        files = self.list_files(oss_prefix)
        if max_files:
            files = files[:max_files]

        total = len(files)
        downloaded = 0

        for f in files:
            rel_path = f['key'][len(oss_prefix):].lstrip('/')
            local_path = os.path.join(local_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            try:
                self.bucket.get_object_to_file(f['key'], local_path)
                downloaded += 1
                if progress_callback:
                    progress_callback(downloaded, total, f['key'])
            except RequestError as e:
                print(f'  警告: 下载失败 {f["key"]}: {str(e)}')

        return downloaded

    def get_bucket_info(self):
        """获取Bucket信息"""
        try:
            info = self.bucket.get_bucket_info()
            return {
                'name': info.name,
                'location': info.location,
                'creation_date': info.creation_date,
                'storage_class': info.storage_class,
            }
        except RequestError as e:
            raise RuntimeError(f'获取Bucket信息失败: {str(e)}')


def get_oss_client_from_config(config_file=None):
    """
    从配置文件创建OSS客户端

    Args:
        config_file: 配置文件路径，默认从项目根目录的config.py读取
    """
    import sys
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if config_file is None:
        config_file = os.path.join(base_dir, 'config.py')

    if not os.path.exists(config_file):
        raise FileNotFoundError(
            f'配置文件不存在: {config_file}\n'
            f'请复制 config.example.py 为 config.py 并填入OSS配置信息'
        )

    # 动态导入配置
    sys.path.insert(0, os.path.dirname(config_file))
    import importlib.util
    spec = importlib.util.spec_from_file_location('config', config_file)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    return OSSClient(
        access_key_id=config.OSS_ACCESS_KEY_ID,
        access_key_secret=config.OSS_ACCESS_KEY_SECRET,
        endpoint=config.OSS_ENDPOINT,
        bucket_name=config.OSS_BUCKET,
    )


def main():
    """命令行测试工具"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description='阿里云OSS工具')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--test', action='store_true', help='测试连接')
    parser.add_argument('--list', '-l', help='列出指定前缀的文件')
    parser.add_argument('--info', action='store_true', help='获取Bucket信息')
    parser.add_argument('--upload', nargs=2, metavar=('LOCAL', 'OSS'),
                        help='上传本地文件/目录到OSS')
    parser.add_argument('--download', nargs=2, metavar=('OSS', 'LOCAL'),
                        help='从OSS下载文件/目录到本地')

    args = parser.parse_args()

    if not any([args.test, args.list, args.info, args.upload, args.download]):
        parser.print_help()
        print('\n示例:')
        print('  python oss_utils.py --test              # 测试连接')
        print('  python oss_utils.py --list data/        # 列出data/下的文件')
        print('  python oss_utils.py --info              # 获取Bucket信息')
        return

    try:
        client = get_oss_client_from_config(args.config)
    except Exception as e:
        print(f'错误: {e}')
        sys.exit(1)

    if args.test:
        print('正在测试OSS连接...')
        success, msg = client.test_connection()
        print(msg)
        if success:
            info = client.get_bucket_info()
            print(f'Bucket名称: {info["name"]}')
            print(f'地域: {info["location"]}')
            print(f'创建时间: {info["creation_date"]}')

    elif args.info:
        info = client.get_bucket_info()
        print(f'Bucket名称: {info["name"]}')
        print(f'地域: {info["location"]}')
        print(f'创建时间: {info["creation_date"]}')
        print(f'存储类型: {info["storage_class"]}')

    elif args.list is not None:
        print(f'列出 {args.list} 下的文件:')
        files = client.list_files(args.list)
        if len(files) == 0:
            print('  (空)')
        else:
            for f in files[:50]:
                size_mb = f['size'] / 1024 / 1024
                if size_mb >= 1:
                    size_str = f'{size_mb:.2f} MB'
                else:
                    size_str = f'{f["size"]/1024:.2f} KB'
                print(f'  {f["key"]} ({size_str})')
            if len(files) > 50:
                print(f'  ... 共 {len(files)} 个文件')

    elif args.upload:
        local_path, oss_path = args.upload
        if os.path.isdir(local_path):
            print(f'上传目录: {local_path} -> {oss_path}')
            count = client.upload_dir(local_path, oss_path)
            print(f'上传完成: {count} 个文件')
        else:
            print(f'上传文件: {local_path} -> {oss_path}')
            result = client.upload_file(local_path, oss_path)
            print(f'上传完成: {result}')

    elif args.download:
        oss_path, local_path = args.download
        print(f'下载: {oss_path} -> {local_path}')
        # 判断是文件还是目录
        if oss_path.endswith('/') or '/' not in oss_path.split('/')[-1]:
            count = client.download_dir(oss_path, local_path)
            print(f'下载完成: {count} 个文件')
        else:
            result = client.download_file(oss_path, local_path)
            print(f'下载完成: {result}')


if __name__ == '__main__':
    main()

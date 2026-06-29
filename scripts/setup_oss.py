"""
阿里云OSS配置向导
交互式配置OSS连接信息
"""
import os
import sys
import getpass


def main():
    print('=' * 60)
    print('阿里云OSS 配置向导')
    print('=' * 60)
    print()
    print('请准备以下信息（可在阿里云控制台获取）：')
    print('  1. AccessKey ID')
    print('  2. AccessKey Secret')
    print('  3. OSS Endpoint（地域节点，如 oss-cn-hangzhou.aliyuncs.com）')
    print('  4. Bucket 名称')
    print()

    # 检查配置文件是否已存在
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')
    if os.path.exists(config_path):
        print(f'注意: 配置文件已存在: {config_path}')
        choice = input('是否覆盖? (y/N): ').strip().lower()
        if choice != 'y':
            print('已取消配置')
            return

    # 获取用户输入
    print('\n请输入配置信息：')
    print('-' * 40)

    access_key_id = input('AccessKey ID: ').strip()
    while not access_key_id:
        print('  错误: AccessKey ID 不能为空')
        access_key_id = input('AccessKey ID: ').strip()

    access_key_secret = getpass.getpass('AccessKey Secret: ').strip()
    while not access_key_secret:
        print('  错误: AccessKey Secret 不能为空')
        access_key_secret = getpass.getpass('AccessKey Secret: ').strip()

    endpoint = input('Endpoint (如 oss-cn-hangzhou.aliyuncs.com): ').strip()
    while not endpoint:
        print('  错误: Endpoint 不能为空')
        print('  提示: 可在OSS控制台Bucket概览页找到"地域节点"')
        endpoint = input('Endpoint: ').strip()

    # 如果endpoint没有http前缀，自动添加https
    if endpoint.startswith('http://') or endpoint.startswith('https://'):
        print('  提示: Endpoint不需要http/https前缀，将自动去除')
        endpoint = endpoint.replace('https://', '').replace('http://', '')

    bucket_name = input('Bucket名称: ').strip()
    while not bucket_name:
        print('  错误: Bucket名称不能为空')
        bucket_name = input('Bucket名称: ').strip()

    # 数据路径配置
    print()
    use_default = input('是否使用默认数据路径 (data/)? (Y/n): ').strip().lower()
    if use_default in ('n', 'no'):
        oss_data_prefix = input('OSS数据路径前缀 (如 ecommerce-price-index/data/): ').strip()
        if not oss_data_prefix.endswith('/'):
            oss_data_prefix += '/'
    else:
        oss_data_prefix = 'data/'

    local_data_dir = input('本地数据目录 (默认 e:/111/data): ').strip()
    if not local_data_dir:
        local_data_dir = 'e:/111/data'

    # 生成配置文件
    config_content = f'''# 阿里云OSS配置
# 由配置向导生成，请勿将此文件提交到代码仓库

# 阿里云访问密钥
OSS_ACCESS_KEY_ID = "{access_key_id}"
OSS_ACCESS_KEY_SECRET = "{access_key_secret}"

# OSS配置
OSS_ENDPOINT = "{endpoint}"
OSS_BUCKET = "{bucket_name}"

# OSS数据路径
OSS_DATA_PREFIX = "{oss_data_prefix}"
OSS_ODS_PREFIX = "{oss_data_prefix}ods/"
OSS_DIM_PREFIX = "{oss_data_prefix}dim/"
OSS_ADS_PREFIX = "{oss_data_prefix}ads/"

# 本地数据路径
LOCAL_DATA_DIR = r"{local_data_dir}"
'''

    # 写入配置文件
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)

    print()
    print('=' * 60)
    print(f'配置文件已保存: {config_path}')
    print('=' * 60)

    # 测试连接
    print()
    test = input('是否测试连接? (Y/n): ').strip().lower()
    if test in ('', 'y', 'yes'):
        print()
        print('正在测试连接...')
        try:
            sys.path.insert(0, os.path.dirname(config_path))
            from oss_utils import OSSClient

            client = OSSClient(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                endpoint=endpoint,
                bucket_name=bucket_name
            )

            success, msg = client.test_connection()
            if success:
                print(f'✅ {msg}')
                info = client.get_bucket_info()
                print(f'   Bucket名称: {info["name"]}')
                print(f'   地域: {info["location"]}')
                print(f'   创建时间: {info["creation_date"]}')
                print()
                print('配置成功！可以开始使用OSS功能了。')
            else:
                print(f'❌ {msg}')
                print()
                print('请检查配置信息是否正确，然后重新运行配置向导。')
        except ImportError as e:
            print(f'❌ 导入失败: {e}')
            print('请先安装 oss2: pip install oss2')
        except Exception as e:
            print(f'❌ 连接测试失败: {type(e).__name__}: {e}')

    # .gitignore 提示
    print()
    print('⚠️  安全提示:')
    print('   请确保 config.py 已加入 .gitignore，避免密钥泄露！')


if __name__ == '__main__':
    main()

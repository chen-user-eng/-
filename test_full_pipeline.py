import sys
sys.path.insert(0, 'scripts')
import os
import shutil
from oss_utils import OSSClient
from config import OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def clean_local_data():
    for folder in ['dim', 'ods', 'dwd', 'dws', 'ads', 'reports']:
        path = os.path.join(DATA_DIR, folder)
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)
    print('  ✓ 已清理本地数据目录')

def download_from_oss():
    client = OSSClient(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET)
    
    print('  下载维度表...')
    client.download_file('data/dim/products.csv', os.path.join(DATA_DIR, 'dim', 'products.csv'))
    client.download_file('data/dim/categories.csv', os.path.join(DATA_DIR, 'dim', 'categories.csv'))
    print('    ✓ products.csv')
    print('    ✓ categories.csv')
    
    print('  下载ODS数据...')
    files = client.list_files('data/ods/')
    for f in files:
        rel_path = f['key'][len('data/ods/'):]
        local_path = os.path.join(DATA_DIR, 'ods', rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        client.download_file(f['key'], local_path)
        print(f'    ✓ {rel_path}')
    
    print(f'  ✓ 共下载 {len(files)} 个ODS文件')

def run_processing():
    print('\n[3/3] 运行数据处理管道...')
    import subprocess
    result = subprocess.run(
        [sys.executable, 'scripts/process_fast.py'],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    print(result.stdout)
    if result.stderr:
        print('STDERR:', result.stderr)
    return result.returncode == 0

if __name__ == '__main__':
    print('=' * 60)
    print('高频电商价格指数计算平台 - 完整测试流程')
    print('=' * 60)
    
    print('\n[1/3] 清理本地数据目录...')
    clean_local_data()
    
    print('\n[2/3] 从OSS下载测试数据...')
    download_from_oss()
    
    success = run_processing()
    
    print('\n' + '=' * 60)
    if success:
        print('测试完成！数据处理成功！')
        print('接下来可以启动可视化服务: python app.py')
    else:
        print('测试失败！')
    print('=' * 60)

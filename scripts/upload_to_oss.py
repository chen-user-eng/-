"""上传本地数据到OSS"""
import sys
sys.path.insert(0, 'e:/111')
from scripts.oss_utils import get_oss_client_from_config
import os
import time

def main():
    client = get_oss_client_from_config()

    local_dir = 'e:/111/data'
    oss_prefix = 'data/'

    # 统计文件
    all_files = []
    for root, dirs, files in os.walk(local_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_dir)
            oss_key = os.path.join(oss_prefix, rel_path).replace('\\', '/')
            all_files.append((local_path, oss_key))

    total = len(all_files)
    total_size = sum(os.path.getsize(f[0]) for f in all_files)
    print('待上传文件: {} 个, 总大小: {:.2f} MB'.format(total, total_size/1024/1024))
    print()

    uploaded = 0
    uploaded_size = 0
    start_time = time.time()

    for local_path, oss_key in all_files:
        fsize = os.path.getsize(local_path)
        client.bucket.put_object_from_file(oss_key, local_path)
        uploaded += 1
        uploaded_size += fsize
        elapsed = time.time() - start_time
        speed = uploaded_size / elapsed if elapsed > 0 else 0
        
        if uploaded % 10 == 0 or uploaded == total:
            print('  进度: {}/{} ({:.1f}%) | 已上传: {:.1f}MB | 速度: {:.1f}KB/s'.format(
                uploaded, total, uploaded/total*100,
                uploaded_size/1024/1024,
                speed/1024
            ))

    total_time = time.time() - start_time
    print()
    print('✅ 上传完成!')
    print('  文件数: {}'.format(uploaded))
    print('  总大小: {:.2f} MB'.format(uploaded_size/1024/1024))
    print('  总耗时: {:.1f} 分钟'.format(total_time/60))
    print('  平均速度: {:.1f} KB/s'.format(uploaded_size/total_time/1024))

if __name__ == '__main__':
    main()

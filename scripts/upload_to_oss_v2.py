"""上传本地数据到OSS - 增强版"""
import sys
sys.path.insert(0, 'e:/111')
import config
import oss2
import os
import time
import traceback

def main():
    print('=== OSS上传工具 ===')
    print()
    
    # 初始化OSS客户端
    auth = oss2.Auth(config.OSS_ACCESS_KEY_ID, config.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, config.OSS_ENDPOINT, config.OSS_BUCKET)
    
    # 测试连接
    try:
        bucket.get_bucket_info()
        print('✅ OSS连接成功')
    except Exception as e:
        print('❌ OSS连接失败:', e)
        return
    
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
    
    # 获取已上传的文件列表
    existing_files = set()
    for obj in oss2.ObjectIteratorV2(bucket, prefix=oss_prefix):
        existing_files.add(obj.key)
    print('OSS上已存在: {} 个文件'.format(len(existing_files)))
    
    # 过滤已存在的文件
    new_files = []
    for local_path, oss_key in all_files:
        if oss_key not in existing_files:
            new_files.append((local_path, oss_key))
    
    print('需要新上传: {} 个文件'.format(len(new_files)))
    if len(new_files) == 0:
        print('✅ 所有文件已在OSS上，无需上传')
        return
    
    # 开始上传
    uploaded = 0
    uploaded_size = 0
    failed = 0
    start_time = time.time()
    
    print()
    print('开始上传...')
    print('='*60)
    
    for i, (local_path, oss_key) in enumerate(new_files):
        try:
            fsize = os.path.getsize(local_path)
            
            # 上传
            bucket.put_object_from_file(oss_key, local_path)
            
            uploaded += 1
            uploaded_size += fsize
            elapsed = time.time() - start_time
            speed = uploaded_size / elapsed if elapsed > 0 else 0
            
            # 输出进度
            if uploaded % 10 == 0 or uploaded == len(new_files):
                progress = uploaded / len(new_files) * 100
                print('[{:.1f}%] {}/{} | {:.1f}MB | {:.1f}KB/s | {}'.format(
                    progress, uploaded, len(new_files),
                    uploaded_size/1024/1024,
                    speed/1024,
                    oss_key.split('/')[-1]
                ))
            
        except Exception as e:
            failed += 1
            print('❌ 上传失败 [{}]: {}'.format(local_path, str(e)[:100]))
    
    total_time = time.time() - start_time
    print('='*60)
    print()
    print('✅ 上传完成!')
    print('  成功: {} 个文件'.format(uploaded))
    print('  失败: {} 个文件'.format(failed))
    print('  总大小: {:.2f} MB'.format(uploaded_size/1024/1024))
    print('  总耗时: {:.1f} 分钟'.format(total_time/60))
    print('  平均速度: {:.1f} KB/s'.format(uploaded_size/total_time/1024))
    
    # 验证
    final_count = 0
    for obj in oss2.ObjectIteratorV2(bucket, prefix=oss_prefix):
        final_count += 1
    print()
    print('验证: OSS上共有 {} 个文件'.format(final_count))

if __name__ == '__main__':
    main()

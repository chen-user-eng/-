"""上传本地数据到OSS - 快速版"""
import sys
sys.path.insert(0, 'e:/111')
import config
import oss2
import os
import time

def main():
    print('=== OSS上传工具 - 快速版 ===')
    print()
    
    auth = oss2.Auth(config.OSS_ACCESS_KEY_ID, config.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, config.OSS_ENDPOINT, config.OSS_BUCKET)
    
    # 测试连接
    bucket.get_bucket_info()
    print('✅ OSS连接成功')
    
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
    
    # 开始上传（先跳过已存在的大文件，上传小文件测试）
    uploaded = 0
    uploaded_size = 0
    skipped = 0
    failed = 0
    start_time = time.time()
    
    print('开始上传...')
    print('='*60)
    
    for i, (local_path, oss_key) in enumerate(all_files):
        fsize = os.path.getsize(local_path)
        
        # 跳过已存在的文件
        try:
            bucket.get_object_meta(oss_key)
            skipped += 1
            continue
        except:
            pass
        
        try:
            # 上传
            bucket.put_object_from_file(oss_key, local_path)
            
            uploaded += 1
            uploaded_size += fsize
            elapsed = time.time() - start_time
            speed = uploaded_size / elapsed if elapsed > 0 else 0
            
            # 输出进度（每上传1个文件或每10秒）
            if uploaded % 5 == 0:
                progress = (uploaded + skipped) / total * 100
                print('[{:.1f}%] 已上传:{}, 已跳过:{}, {:.1f}MB, {:.1f}KB/s, 文件:{}'.format(
                    progress, uploaded, skipped,
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
    print('  跳过(已存在): {} 个文件'.format(skipped))
    print('  失败: {} 个文件'.format(failed))
    print('  总大小: {:.2f} MB'.format(uploaded_size/1024/1024))
    print('  总耗时: {:.1f} 分钟'.format(total_time/60))
    
    # 最终验证
    final_count = 0
    for obj in oss2.ObjectIteratorV2(bucket, prefix=oss_prefix):
        final_count += 1
    print()
    print('验证: OSS上共有 {} 个文件'.format(final_count))

if __name__ == '__main__':
    main()

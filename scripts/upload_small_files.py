"""上传本地数据到OSS - 跳过大文件版"""
import sys
sys.path.insert(0, 'e:/111')
import config
import oss2
import os
import time

def main():
    print('=== OSS上传工具 - 跳过大文件版 ===')
    print()
    
    auth = oss2.Auth(config.OSS_ACCESS_KEY_ID, config.OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, config.OSS_ENDPOINT, config.OSS_BUCKET)
    
    bucket.get_bucket_info()
    print('✅ OSS连接成功')
    
    local_dir = 'e:/111/data'
    oss_prefix = 'data/'
    
    all_files = []
    for root, dirs, files in os.walk(local_dir):
        for filename in files:
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_dir)
            oss_key = os.path.join(oss_prefix, rel_path).replace('\\', '/')
            fsize = os.path.getsize(local_path)
            all_files.append((local_path, oss_key, fsize))
    
    total = len(all_files)
    total_size = sum(f[2] for f in all_files)
    print('总文件数: {} 个, 总大小: {:.2f} MB'.format(total, total_size/1024/1024))
    
    # 跳过大于500MB的文件
    skip_size = 500 * 1024 * 1024
    big_files = [f for f in all_files if f[2] > skip_size]
    small_files = [f for f in all_files if f[2] <= skip_size]
    
    print('跳过的大文件(>500MB):')
    for lp, ok, sz in big_files:
        print('  {} ({:.1f} MB)'.format(ok.split('/')[-1], sz/1024/1024))
    
    print()
    print('待上传小文件: {} 个, 大小: {:.2f} MB'.format(
        len(small_files), sum(f[2] for f in small_files)/1024/1024))
    print()
    
    # 统计已存在的
    existing = set()
    for obj in oss2.ObjectIteratorV2(bucket, prefix=oss_prefix):
        existing.add(obj.key)
    print('OSS上已存在: {} 个文件'.format(len(existing)))
    print()
    
    # 开始上传
    uploaded = 0
    uploaded_size = 0
    skipped = 0
    failed = 0
    start_time = time.time()
    
    print('开始上传小文件...')
    print('='*60)
    
    for i, (local_path, oss_key, fsize) in enumerate(small_files):
        filename = oss_key.split('/')[-1]
        
        # 跳过已存在的
        if oss_key in existing:
            skipped += 1
            continue
        
        try:
            bucket.put_object_from_file(oss_key, local_path)
            
            uploaded += 1
            uploaded_size += fsize
            
            if uploaded % 50 == 0:
                elapsed = time.time() - start_time
                speed = uploaded_size / elapsed if elapsed > 0 else 0
                progress = uploaded / len(small_files) * 100
                print('[{:.1f}%] 已上传:{}, 跳过:{}, {:.1f}MB, {:.1f}KB/s'.format(
                    progress, uploaded, skipped,
                    uploaded_size/1024/1024, speed/1024))
            
        except Exception as e:
            failed += 1
            print('❌ 失败: {} - {}'.format(filename, str(e)[:80]))
    
    total_time = time.time() - start_time
    print('='*60)
    print()
    print('✅ 小文件上传完成!')
    print('  成功: {} 个'.format(uploaded))
    print('  跳过(已存在): {} 个'.format(skipped))
    print('  失败: {} 个'.format(failed))
    print('  总大小: {:.2f} MB'.format(uploaded_size/1024/1024))
    print('  总耗时: {:.1f} 分钟'.format(total_time/60))
    
    # 最终统计
    final_count = 0
    for obj in oss2.ObjectIteratorV2(bucket, prefix=oss_prefix):
        final_count += 1
    print()
    print('OSS上当前共有 {} 个文件'.format(final_count))

if __name__ == '__main__':
    main()

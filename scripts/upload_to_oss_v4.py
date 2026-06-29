"""上传本地数据到OSS - 分片上传版"""
import sys
sys.path.insert(0, 'e:/111')
import config
import oss2
import os
import time

def upload_file(bucket, local_path, oss_key):
    """上传单个文件，大文件自动分片上传"""
    fsize = os.path.getsize(local_path)
    
    # 超过100MB使用分片上传
    if fsize > 100 * 1024 * 1024:
        return upload_large_file(bucket, local_path, oss_key)
    else:
        bucket.put_object_from_file(oss_key, local_path)
        return fsize

def upload_large_file(bucket, local_path, oss_key):
    """分片上传大文件"""
    fsize = os.path.getsize(local_path)
    
    # 分片大小：2MB
    part_size = 2 * 1024 * 1024
    total_parts = (fsize + part_size - 1) // part_size
    
    # 初始化分片上传
    upload_id = bucket.init_multipart_upload(oss_key).upload_id
    
    try:
        # 分片上传
        parts = []
        with open(local_path, 'rb') as f:
            for i in range(total_parts):
                offset = i * part_size
                size = min(part_size, fsize - offset)
                f.seek(offset)
                data = f.read(size)
                
                result = bucket.upload_part(oss_key, upload_id, i + 1, data)
                parts.append(oss2.models.PartInfo(i + 1, result.etag))
                
                if (i + 1) % 50 == 0 or (i + 1) == total_parts:
                    progress = (i + 1) / total_parts * 100
                    print('    分片: {}/{} ({:.1f}%)'.format(i + 1, total_parts, progress))
        
        # 完成分片上传
        bucket.complete_multipart_upload(oss_key, upload_id, parts)
        return fsize
        
    except Exception as e:
        # 失败则取消分片上传
        bucket.abort_multipart_upload(oss_key, upload_id)
        raise e

def main():
    print('=== OSS上传工具 - 分片上传版 ===')
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
            all_files.append((local_path, oss_key))
    
    total = len(all_files)
    total_size = sum(os.path.getsize(f[0]) for f in all_files)
    print('待上传文件: {} 个, 总大小: {:.2f} MB'.format(total, total_size/1024/1024))
    print()
    
    uploaded = 0
    uploaded_size = 0
    skipped = 0
    failed = 0
    start_time = time.time()
    
    print('开始上传...')
    print('='*60)
    
    for i, (local_path, oss_key) in enumerate(all_files):
        fsize = os.path.getsize(local_path)
        filename = oss_key.split('/')[-1]
        
        # 跳过已存在的文件
        try:
            bucket.get_object_meta(oss_key)
            skipped += 1
            continue
        except:
            pass
        
        try:
            print('[{}/{}] 上传: {} ({:.1f} MB)'.format(i+1, total, filename, fsize/1024/1024))
            
            start = time.time()
            upload_file(bucket, local_path, oss_key)
            elapsed = time.time() - start
            
            uploaded += 1
            uploaded_size += fsize
            
            print('    ✅ 完成, 耗时 {:.1f}秒, 速度 {:.1f}KB/s'.format(
                elapsed, fsize/1024/elapsed))
            
            total_elapsed = time.time() - start_time
            avg_speed = uploaded_size / total_elapsed if total_elapsed > 0 else 0
            print('    累计: {}/{} 文件, {:.1f}MB, 平均 {:.1f}KB/s'.format(
                uploaded, total, uploaded_size/1024/1024, avg_speed/1024))
            print()
            
        except Exception as e:
            failed += 1
            print('    ❌ 上传失败: {}'.format(str(e)[:100]))
            print()
    
    total_time = time.time() - start_time
    print('='*60)
    print()
    print('✅ 上传完成!')
    print('  成功: {} 个文件'.format(uploaded))
    print('  跳过(已存在): {} 个文件'.format(skipped))
    print('  失败: {} 个文件'.format(failed))
    print('  总大小: {:.2f} MB'.format(uploaded_size/1024/1024))
    print('  总耗时: {:.1f} 分钟'.format(total_time/60))

if __name__ == '__main__':
    main()

"""
CI/CD - 上传测试数据到OSS
"""
import oss2
import os
import sys

def main():
    access_id = os.environ.get('OSS_ACCESS_KEY_ID')
    access_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
    
    if not access_id or not access_secret:
        print('Warning: OSS credentials not set, skipping upload')
        return

    auth = oss2.Auth(access_id, access_secret)
    bucket = oss2.Bucket(auth, 'oss-cn-hangzhou.aliyuncs.com', 'dashujujishu')

    files = [
        ('tests/test_data/test_all_index.csv', 'data/test/test_all_index.csv'),
        ('tests/test_data/test_categories.csv', 'data/test/test_categories.csv'),
        ('tests/test_data/test_products.csv', 'data/test/test_products.csv'),
    ]

    for local_path, oss_path in files:
        if os.path.exists(local_path):
            result = bucket.put_object(oss_path, open(local_path, 'rb'))
            print(f'Uploaded {local_path} -> {oss_path}, status: {result.status}')
        else:
            print(f'Skipped (not found): {local_path}')

    print('Upload completed.')


if __name__ == '__main__':
    main()

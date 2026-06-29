"""
准备本地ODS目录 - 复制原始数据到分区目录
"""
import os
import shutil
import time

SOURCE_DIR = r'D:\cxdownload\data\data\daily_price'
TARGET_DIR = r'e:\111\data\ods'

def main():
    start_time = time.time()

    print('=' * 60)
    print('准备本地ODS目录')
    print('=' * 60)
    print(f'源目录: {SOURCE_DIR}')
    print(f'目标目录: {TARGET_DIR}')
    print()

    # 获取所有文件
    files = sorted([f for f in os.listdir(SOURCE_DIR)
                   if f.startswith('daily_prices_') and f.endswith('.csv')])

    total = len(files)
    print(f'待处理文件: {total} 个')

    copied = 0
    skipped = 0

    for i, filename in enumerate(files):
        # 从文件名提取日期
        date_str = filename.replace('daily_prices_', '').replace('.csv', '')
        formatted_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'

        # 创建分区目录
        partition_dir = os.path.join(TARGET_DIR, f'dt={formatted_date}')
        os.makedirs(partition_dir, exist_ok=True)

        # 目标文件
        target_file = os.path.join(partition_dir, 'product_price.csv')

        # 检查是否已存在
        if os.path.exists(target_file):
            skipped += 1
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                print(f'  进度: {i+1}/{total} (跳过{skipped}个) - {elapsed:.1f}秒')
            continue

        # 复制文件
        source_file = os.path.join(SOURCE_DIR, filename)
        shutil.copy2(source_file, target_file)
        copied += 1

        if (i + 1) % 100 == 0 or i == total - 1:
            elapsed = time.time() - start_time
            speed = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - i - 1) / speed if speed > 0 else 0
            print(f'  进度: {i+1}/{total} (复制{copied}个, 跳过{skipped}个) - {speed:.0f}个/秒 - 约剩{remaining:.0f}秒')

    elapsed = time.time() - start_time
    print()
    print('=' * 60)
    print(f'完成! 耗时: {elapsed:.1f}秒')
    print(f'  复制: {copied} 个')
    print(f'  跳过: {skipped} 个')
    print('=' * 60)

if __name__ == '__main__':
    main()

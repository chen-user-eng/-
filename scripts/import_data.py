"""
数据导入脚本 - 将原始CSV数据转换为平台所需格式
"""
import os
import pandas as pd
import shutil
from datetime import datetime

# 数据源路径
SOURCE_DIR = r'D:\cxdownload\data\data'
DAILY_PRICE_DIR = os.path.join(SOURCE_DIR, 'daily_price')
CATEGORIES_FILE = os.path.join(SOURCE_DIR, 'categories.csv')
PRODUCTS_FILE = os.path.join(SOURCE_DIR, 'products.csv')

# 目标路径 - 修正为项目根目录的data文件夹
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DIM_DIR = os.path.join(DATA_DIR, 'dim')
ODS_DIR = os.path.join(DATA_DIR, 'ods')


def import_categories():
    """导入并转换类目维度表"""
    print('=' * 60)
    print('导入类目维度表...')
    df = pd.read_csv(CATEGORIES_FILE, encoding='gbk')
    df = df.rename(columns={'category': 'category_name'})
    df['parent_id'] = df['parent'].apply(lambda x: str(int(x)) if pd.notna(x) else '')
    df['base_price'] = 0.0
    df = df[['category_id', 'category_name', 'hierarchy', 'weight', 'base_price', 'parent_id']]
    output_file = os.path.join(DIM_DIR, 'categories.csv')
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f'  ✓ 已导入 {len(df)} 个类目')
    print(f'  ✓ 一级类目: {len(df[df["hierarchy"]==1])} 个')
    print(f'  ✓ 二级类目: {len(df[df["hierarchy"]==2])} 个')
    print(f'  → 保存至: {output_file}')
    return df


def import_products():
    """导入并转换商品维度表"""
    print('\n导入商品维度表...')
    df = pd.read_csv(PRODUCTS_FILE, encoding='gbk')
    df = df.rename(columns={'name': 'product_name', 'price': 'base_price'})
    df['base_price'] = df['base_price'].fillna(0)
    df['change_count'] = df['change_count'].fillna(0)
    output_file = os.path.join(DIM_DIR, 'products.csv')
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f'  ✓ 已导入 {len(df)} 个商品')
    print(f'  → 保存至: {output_file}')
    return df


def import_daily_prices():
    """批量导入每日价格数据"""
    print('\n导入每日价格数据...')
    print('  (这可能需要几分钟...)')

    # 获取所有日度价格文件
    files = sorted([f for f in os.listdir(DAILY_PRICE_DIR)
                   if f.startswith('daily_prices_') and f.endswith('.csv')])

    print(f'  找到 {len(files)} 个价格文件')

    count = 0
    errors = []

    for i, filename in enumerate(files):
        try:
            # 从文件名提取日期：daily_prices_20250517.csv → 2025-05-17
            date_str = filename.replace('daily_prices_', '').replace('.csv', '')
            formatted_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'

            # 创建分区目录
            partition_dir = os.path.join(ODS_DIR, f'dt={formatted_date}')
            os.makedirs(partition_dir, exist_ok=True)

            # 读取并转换数据
            df = pd.read_csv(
                os.path.join(DAILY_PRICE_DIR, filename),
                encoding='gbk'
            )
            df = df[['product_id', 'category_id', 'name', 'price', 'change_date']]

            # 保存到分区
            output_file = os.path.join(partition_dir, 'product_price.csv')
            df.to_csv(output_file, index=False, encoding='utf-8-sig')

            count += 1
            if count % 100 == 0 or count == len(files):
                print(f'  进度: {count}/{len(files)} 文件 - {formatted_date}')

        except Exception as e:
            errors.append(f'{filename}: {str(e)}')

    print(f'\n  ✓ 成功导入 {count} 个价格文件')
    if errors:
        print(f'  ✗ {len(errors)} 个文件失败:')
        for err in errors[:5]:
            print(f'    - {err}')

    return count


def main():
    print('=' * 60)
    print('高频电商价格指数计算平台 - 数据导入工具')
    print('=' * 60)
    print(f'\n数据源: {SOURCE_DIR}')
    print(f'目标目录: {DATA_DIR}')
    print()

    # 创建目录
    os.makedirs(DIM_DIR, exist_ok=True)
    os.makedirs(ODS_DIR, exist_ok=True)

    # 导入数据
    categories = import_categories()
    products = import_products()
    daily_count = import_daily_prices()

    print('\n' + '=' * 60)
    print('导入完成！')
    print('=' * 60)
    print(f'  类目维度表: {len(categories)} 条')
    print(f'  商品维度表: {len(products)} 条')
    print(f'  每日价格数据: {daily_count} 天')
    print(f'\n接下来运行数据处理: python scripts/process_pipeline.py')
    print('=' * 60)


if __name__ == '__main__':
    main()

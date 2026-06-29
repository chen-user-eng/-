"""
CI/CD - 字段类型转换测试
验证字段类型转换和价格指数计算正确性
"""
import pandas as pd
import sys

def main():
    df = pd.read_csv('tests/test_data/test_all_index.csv')

    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['base_price'] = pd.to_numeric(df['base_price'], errors='coerce')
    df['price_index'] = pd.to_numeric(df['price_index'], errors='coerce')

    null_prices = df[['price', 'base_price']].isnull().sum()
    if null_prices.any():
        print(f'Warning: null values in price fields: {null_prices.to_dict()}')

    df['calc_index'] = (df['price'] / df['base_price']) * 100
    df['diff'] = abs(df['calc_index'] - df['price_index'])
    max_diff = df['diff'].max()
    print(f'Max price index calculation error: {max_diff:.4f}%')

    if max_diff > 0.1:
        print('ERROR: price index calculation error too large')
        sys.exit(1)
    else:
        print('Field type conversion test passed!')


if __name__ == '__main__':
    print('=== Field Type Conversion Test ===')
    main()

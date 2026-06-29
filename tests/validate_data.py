"""
CI/CD - 数据格式校验与字段类型转换
验证测试数据的格式、字段、类型是否正确
"""
import pandas as pd
import sys

def main():
    test_files = [
        'tests/test_data/test_all_index.csv',
        'tests/test_data/test_categories.csv',
        'tests/test_data/test_products.csv',
        'tests/test_data/test_anomaly_2028-05-15.csv'
    ]

    errors = []
    for f in test_files:
        try:
            df = pd.read_csv(f)
            print(f'  OK {f}: {len(df)} rows, {len(df.columns)} columns')

            if 'test_all_index' in f:
                required = ['dt', 'index_type', 'target_id', 'price', 'base_price', 'price_index']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    errors.append(f'{f}: missing columns {missing}')

            for col in ['price', 'base_price', 'price_index']:
                if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                    errors.append(f'{f}: column {col} is not numeric')

        except Exception as e:
            errors.append(f'{f}: {str(e)}')

    if errors:
        print('\nErrors found:')
        for e in errors:
            print(f'  - {e}')
        sys.exit(1)
    else:
        print('\nAll data files validated successfully!')


if __name__ == '__main__':
    print('=== Data Format Validation ===')
    main()

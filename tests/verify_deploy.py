"""
CI/CD - 验证ClickHouse部署
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from scripts.clickhouse_utils import get_ch_client
    
    try:
        client = get_ch_client()
        print('ClickHouse connection OK')
        
        try:
            result = client.query('SELECT count() FROM ads_price_index_local')
            print('ads_price_index_local rows:', result.first_row)
        except Exception as e:
            print('Warning: ads_price_index_local query failed:', e)
        
        try:
            result = client.query('SELECT count() FROM dim_products_local')
            print('dim_products_local rows:', result.first_row)
        except Exception as e:
            print('Warning: dim_products_local query failed:', e)
        
        print('Deployment verification completed.')
    except Exception as e:
        print('ERROR: ClickHouse connection failed:', e)
        sys.exit(1)


if __name__ == '__main__':
    main()

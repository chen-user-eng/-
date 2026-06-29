from scripts.clickhouse_utils import get_ch_client
client = get_ch_client()

# 看看价格突变的异常数据中，当前价和基期价一样的有多少
result = client.client.query_df("""
SELECT 
    count() as total,
    countIf(current_price = base_price) as same_as_base,
    countIf(current_price != base_price) as different_from_base
FROM ads_anomaly
WHERE anomaly_type = '价格突变'
  AND dt = '2028-05-15'
""")
print('价格突变异常总数:', result.iloc[0]['total'])
print('当前价=基期价:', result.iloc[0]['same_as_base'])
print('当前价≠基期价:', result.iloc[0]['different_from_base'])

# 看几个具体例子
result2 = client.client.query_df("""
SELECT product_name, current_price, base_price, change_rate, anomaly_desc
FROM ads_anomaly
WHERE anomaly_type = '价格突变'
  AND dt = '2028-05-15'
  AND current_price = base_price
LIMIT 5
""")
print()
print('当前价=基期价的例子:')
print(result2.to_string())

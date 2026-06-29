import pandas as pd

df = pd.read_csv('data/ads/all_index.csv', low_memory=False, nrows=10000)
print('数据类型:')
print(df.dtypes)
print()
print('CATEGORY_L1的target_id:')
l1 = df[df['index_type'] == 'CATEGORY_L1']
print(l1[['target_id', 'target_name']].head())
print()
if len(l1) > 0:
    print('target_id类型:', type(l1['target_id'].values[0]))
    print('target_id值:', l1['target_id'].values[0])
print()
print('CATEGORY的target_id:')
l2 = df[df['index_type'] == 'CATEGORY']
print(l2[['target_id', 'target_name']].head())

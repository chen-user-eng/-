import pandas as pd

products_df = pd.read_csv('data/dim/products.csv', encoding='gbk')
print('Total products:', len(products_df))
print('Unique category_id:', products_df['category_id'].nunique())

print()
print('First 10 category_id:')
print(products_df['category_id'].head(10))

print()
print('Last 10 category_id:')
print(products_df['category_id'].tail(10))

print()
print('category_id length distribution:')
products_df['id_len'] = products_df['category_id'].astype(str).str.len()
print(products_df['id_len'].value_counts())

print()
print('category_id_l2 values for empty category_l1:')
categories_df = pd.read_csv('data/dim/categories.csv', encoding='gbk')
cat_l1 = categories_df[categories_df['hierarchy'] == 1]
cat_l2 = categories_df[categories_df['hierarchy'] == 2]

l1_map = dict(zip(cat_l1['category_id'], cat_l1['category']))
l2_to_l1 = {}
for _, row in cat_l2.iterrows():
    parent_id = int(float(row['parent'])) if pd.notna(row['parent']) else ''
    l2_to_l1[row['category_id']] = l1_map.get(parent_id, '')

products_df['category_id_l2'] = products_df['category_id'] // 10 * 10
products_df['category_l1'] = products_df['category_id_l2'].map(lambda x: l2_to_l1.get(x, ''))

empty_l1 = products_df[products_df['category_l1'] == '']
print('Empty category_l1 count:', len(empty_l1))
print('Unique category_id_l2 for empty category_l1:')
print(empty_l1['category_id_l2'].unique()[:20])

print()
print('Available l2_to_l1 keys:')
print(list(l2_to_l1.keys())[:10])

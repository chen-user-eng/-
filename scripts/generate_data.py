import os
import random
import csv
from datetime import datetime, timedelta
import numpy as np

random.seed(42)
np.random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

CATEGORIES_L1 = [
    ('C01', '食品烟酒', 0.30),
    ('C02', '衣着', 0.08),
    ('C03', '居住', 0.20),
    ('C04', '生活用品及服务', 0.06),
    ('C05', '交通和通信', 0.10),
    ('C06', '教育文化和娱乐', 0.10),
    ('C07', '医疗保健', 0.08),
    ('C08', '其他用品和服务', 0.08),
]

CATEGORIES_L2 = {
    'C01': [('C0101', '食品', 0.75), ('C0102', '烟酒', 0.25)],
    'C02': [('C0201', '服装', 0.60), ('C0202', '鞋袜', 0.40)],
    'C03': [('C0301', '住房租金', 0.50), ('C0302', '水电燃料', 0.50)],
    'C04': [('C0401', '家居用品', 0.60), ('C0402', '家庭服务', 0.40)],
    'C05': [('C0501', '交通工具', 0.40), ('C0502', '通信工具', 0.60)],
    'C06': [('C0601', '教育服务', 0.50), ('C0602', '文化娱乐', 0.50)],
    'C07': [('C0701', '药品', 0.55), ('C0702', '医疗服务', 0.45)],
    'C08': [('C0801', '个人用品', 0.60), ('C0802', '其他服务', 0.40)],
}

PRODUCT_TEMPLATES = {
    'C0101': [
        ('大米', 6.5, 0.12), ('面粉', 5.2, 0.10), ('食用油', 75.0, 0.15),
        ('猪肉', 28.0, 0.20), ('牛肉', 58.0, 0.10), ('鸡肉', 18.0, 0.08),
        ('鸡蛋', 8.5, 0.08), ('牛奶', 5.5, 0.07), ('蔬菜', 4.5, 0.05),
        ('水果', 6.8, 0.05),
    ],
    'C0102': [
        ('白酒', 198.0, 0.30), ('啤酒', 6.0, 0.20), ('香烟', 25.0, 0.40),
        ('红酒', 128.0, 0.10),
    ],
    'C0201': [
        ('男士T恤', 99.0, 0.15), ('女士连衣裙', 199.0, 0.15), ('牛仔裤', 159.0, 0.12),
        ('羽绒服', 599.0, 0.10), ('衬衫', 129.0, 0.10), ('毛衣', 199.0, 0.08),
        ('运动服', 259.0, 0.10), ('外套', 359.0, 0.10), ('西装', 899.0, 0.05),
        ('休闲裤', 129.0, 0.05),
    ],
    'C0202': [
        ('运动鞋', 299.0, 0.20), ('皮鞋', 359.0, 0.15), ('休闲鞋', 199.0, 0.20),
        ('凉鞋', 129.0, 0.10), ('靴子', 399.0, 0.10), ('棉袜', 15.0, 0.15),
        ('丝袜', 12.0, 0.10),
    ],
    'C0301': [
        ('一室租金', 2500.0, 0.30), ('两室租金', 3800.0, 0.25), ('三室租金', 5200.0, 0.15),
        ('物业费', 250.0, 0.15), ('中介费', 2000.0, 0.15),
    ],
    'C0302': [
        ('电费', 0.55, 0.25), ('水费', 4.5, 0.20), ('燃气费', 2.8, 0.20),
        ('取暖费', 28.0, 0.15), ('物业费', 2.5, 0.20),
    ],
    'C0401': [
        ('洗发水', 35.0, 0.12), ('沐浴露', 28.0, 0.10), ('牙膏', 15.0, 0.12),
        ('洗衣液', 32.0, 0.10), ('卫生纸', 25.0, 0.10), ('纸巾', 12.0, 0.08),
        ('厨房用纸', 18.0, 0.08), ('垃圾袋', 15.0, 0.06), ('洗洁精', 12.0, 0.08),
        ('肥皂', 8.0, 0.06), ('拖把', 45.0, 0.04), ('扫帚', 25.0, 0.04),
    ],
    'C0402': [
        ('家政服务', 200.0, 0.30), ('维修服务', 150.0, 0.25), ('快递服务', 12.0, 0.20),
        ('美容美发', 68.0, 0.25),
    ],
    'C0501': [
        ('自行车', 599.0, 0.20), ('电动车', 2599.0, 0.15), ('摩托车', 9999.0, 0.10),
        ('汽车', 150000.0, 0.05), ('汽车保养', 450.0, 0.15), ('汽油', 7.5, 0.20),
        ('停车费', 250.0, 0.15),
    ],
    'C0502': [
        ('手机', 2999.0, 0.30), ('电脑', 4999.0, 0.20), ('平板', 2599.0, 0.10),
        ('耳机', 199.0, 0.10), ('充电器', 49.0, 0.08), ('手机壳', 29.0, 0.07),
        ('话费充值', 50.0, 0.10), ('宽带费', 100.0, 0.05),
    ],
    'C0601': [
        ('幼儿园学费', 2500.0, 0.20), ('小学学费', 500.0, 0.15), ('中学学费', 800.0, 0.15),
        ('大学学费', 5000.0, 0.15), ('培训班', 2500.0, 0.20), ('教材书籍', 85.0, 0.10),
        ('文具', 25.0, 0.05),
    ],
    'C0602': [
        ('电影票', 45.0, 0.15), ('景区门票', 80.0, 0.12), ('健身卡', 1999.0, 0.10),
        ('旅游套餐', 2999.0, 0.08), ('KTV', 98.0, 0.10), ('游戏充值', 50.0, 0.10),
        ('视频会员', 25.0, 0.12), ('音乐会员', 15.0, 0.08), ('书籍', 45.0, 0.08),
        ('乐器', 999.0, 0.07),
    ],
    'C0701': [
        ('感冒药', 25.0, 0.15), ('退烧药', 18.0, 0.12), ('消炎药', 45.0, 0.15),
        ('胃药', 28.0, 0.10), ('维生素', 68.0, 0.10), ('止痛药', 22.0, 0.10),
        ('膏药', 35.0, 0.08), ('眼药水', 18.0, 0.08), ('创可贴', 12.0, 0.06),
        ('保健品', 198.0, 0.06),
    ],
    'C0702': [
        ('挂号费', 50.0, 0.20), ('体检费', 598.0, 0.15), ('治疗费', 200.0, 0.20),
        ('手术费', 5000.0, 0.10), ('住院费', 800.0, 0.15), ('护理费', 150.0, 0.10),
        ('中医理疗', 128.0, 0.10),
    ],
    'C0801': [
        ('香水', 299.0, 0.15), ('化妆品套装', 399.0, 0.20), ('口红', 168.0, 0.12),
        ('面膜', 89.0, 0.10), ('手表', 999.0, 0.08), ('首饰', 599.0, 0.08),
        ('眼镜', 399.0, 0.10), ('雨伞', 45.0, 0.07), ('钱包', 199.0, 0.05),
        ('箱包', 299.0, 0.05),
    ],
    'C0802': [
        ('保险费', 500.0, 0.30), ('银行手续费', 25.0, 0.20), ('律师费', 500.0, 0.15),
        ('中介费', 1000.0, 0.15), ('彩票', 10.0, 0.10), ('宠物服务', 88.0, 0.10),
    ],
}


def generate_categories():
    cat_rows = []
    for l1_id, l1_name, l1_weight in CATEGORIES_L1:
        cat_rows.append({
            'category_id': l1_id,
            'category_name': l1_name,
            'hierarchy': 1,
            'weight': l1_weight,
            'base_price': 0.0,
            'parent_id': '',
        })
        l2_total_weight = 0
        for l2_id, l2_name, l2_weight in CATEGORIES_L2[l1_id]:
            l2_total_weight += l2_weight
            cat_rows.append({
                'category_id': l2_id,
                'category_name': l2_name,
                'hierarchy': 2,
                'weight': l2_weight * l1_weight,
                'base_price': 0.0,
                'parent_id': l1_id,
            })
    return cat_rows


def generate_products(categories):
    products = []
    product_id = 1
    for l2_cat_id, l2_cat_name, _ in [(c['category_id'], c['category_name'], c['weight'])
                                       for c in categories if c['hierarchy'] == 2]:
        templates = PRODUCT_TEMPLATES.get(l2_cat_id, [])
        for pname, base_price, pweight in templates:
            pid = f'P{product_id:05d}'
            products.append({
                'product_id': pid,
                'category_id': l2_cat_id,
                'name': pname,
                'weight': pweight,
                'price': round(base_price, 2),
                'change_count': 0,
            })
            product_id += 1
    cat_weights = {}
    for p in products:
        cid = p['category_id']
        if cid not in cat_weights:
            cat_weights[cid] = 0
        cat_weights[cid] += p['weight']
    for p in products:
        cid = p['category_id']
        p['weight'] = round(p['weight'] / cat_weights[cid], 4)
    return products


def generate_daily_price(products, date_str, anomaly_rate=0.02, missing_rate=0.01, duplicate_rate=0.01):
    rows = []
    for p in products:
        base_price = p['price']
        day_of_year = datetime.strptime(date_str, '%Y-%m-%d').timetuple().tm_yday
        seasonal = 1 + 0.03 * np.sin(2 * np.pi * day_of_year / 365)
        trend = 1 + 0.0001 * day_of_year
        random_walk = np.random.normal(0, 0.01)
        price = base_price * seasonal * trend * (1 + random_walk)
        price = round(max(0.01, price), 2)
        rows.append({
            'product_id': p['product_id'],
            'category_id': p['category_id'],
            'name': p['name'],
            'price': price,
            'change_date': date_str,
        })
    num_anomaly = int(len(rows) * anomaly_rate)
    anomaly_indices = random.sample(range(len(rows)), num_anomaly)
    for idx in anomaly_indices:
        if random.random() < 0.3:
            rows[idx]['price'] = 0.0
        elif random.random() < 0.5:
            rows[idx]['price'] = round(rows[idx]['price'] * random.uniform(2, 5), 2)
        else:
            rows[idx]['price'] = round(rows[idx]['price'] * random.uniform(0.1, 0.3), 2)
    num_duplicate = int(len(rows) * duplicate_rate)
    dup_indices = random.sample(range(len(rows)), num_duplicate)
    for idx in dup_indices:
        dup_row = rows[idx].copy()
        dup_row['price'] = round(dup_row['price'] * random.uniform(0.95, 1.05), 2)
        rows.append(dup_row)
    num_missing = int(len(rows) * missing_rate)
    missing_indices = random.sample(range(len(rows)), num_missing)
    for idx in missing_indices:
        field = random.choice(['product_id', 'price', 'name'])
        rows[idx][field] = ''
    random.shuffle(rows)
    return rows


def save_csv(filepath, rows, fieldnames):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    print('=' * 60)
    print('高频电商价格指数计算平台 - 数据生成模块')
    print('=' * 60)
    categories = generate_categories()
    cat_path = os.path.join(DATA_DIR, 'dim', 'categories.csv')
    save_csv(cat_path, categories,
             ['category_id', 'category_name', 'hierarchy', 'weight', 'base_price', 'parent_id'])
    print(f'类目维度表已生成: {cat_path} ({len(categories)}条)')
    products = generate_products(categories)
    prod_path = os.path.join(DATA_DIR, 'dim', 'products.csv')
    save_csv(prod_path, products,
             ['product_id', 'category_id', 'name', 'weight', 'price', 'change_count'])
    print(f'商品维度表已生成: {prod_path} ({len(products)}条)')
    start_date = datetime(2025, 5, 17)
    end_date = datetime(2026, 6, 24)
    total_days = (end_date - start_date).days + 1
    print(f'\n开始生成日度价格数据: {start_date.date()} ~ {end_date.date()} (共{total_days}天)')
    current = start_date
    count = 0
    while current <= end_date:
        date_str = current.strftime('%Y-%m-%d')
        daily_rows = generate_daily_price(products, date_str)
        day_dir = os.path.join(DATA_DIR, 'ods', f'dt={date_str}')
        day_file = os.path.join(day_dir, 'product_price.csv')
        save_csv(day_file, daily_rows,
                 ['product_id', 'category_id', 'name', 'price', 'change_date'])
        count += 1
        if count % 30 == 0 or count == total_days:
            print(f'  进度: {count}/{total_days} 天 - {date_str}')
        current += timedelta(days=1)
    print(f'\n数据生成完成！共 {count} 天数据，{len(products)} 个商品')
    print(f'数据目录: {DATA_DIR}')
    print('=' * 60)


if __name__ == '__main__':
    main()

import os
import json
from flask import Flask, jsonify, request, send_from_directory
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
WEB_DIR = os.path.join(BASE_DIR, 'web')

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='')

ads_df = None
anomaly_df = None


def load_data():
    global ads_df, anomaly_df
    ads_path = os.path.join(DATA_DIR, 'ads', 'all_index.csv')
    if os.path.exists(ads_path):
        ads_df = pd.read_csv(ads_path, low_memory=False)
        ads_df['dt'] = ads_df['dt'].astype(str)
        ads_df['target_id'] = ads_df['target_id'].astype(str)
        for col in ['category_id', 'category_id_l2', 'category_id_l1']:
            if col in ads_df.columns:
                ads_df[col] = pd.to_numeric(ads_df[col], errors='coerce').fillna(0).astype(int).astype(str)
        print(f'  已加载: {len(ads_df):,} 条指数, 日期范围: {ads_df["dt"].min()} ~ {ads_df["dt"].max()}')
    anomaly_dir = os.path.join(DATA_DIR, 'ads', 'anomaly')
    anomaly_list = []
    if os.path.exists(anomaly_dir):
        for f in sorted(os.listdir(anomaly_dir)):
            if f.endswith('.csv'):
                df = pd.read_csv(os.path.join(anomaly_dir, f))
                date_str = f.replace('anomaly_', '').replace('.csv', '')
                df['dt'] = date_str
                anomaly_list.append(df)
    if anomaly_list:
        anomaly_df = pd.concat(anomaly_list, ignore_index=True)
    else:
        anomaly_df = pd.DataFrame()


def get_latest_date():
    if ads_df is None or len(ads_df) == 0:
        return None
    return sorted(ads_df['dt'].unique())[-1]


@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(WEB_DIR, path)


@app.route('/api/overview')
def api_overview():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    latest = get_latest_date()
    overall = ads_df[(ads_df['index_type'] == 'OVERALL') & (ads_df['dt'] == latest)]
    fisher = ads_df[(ads_df['index_type'] == 'FISHER') & (ads_df['dt'] == latest)]
    sku_count = len(ads_df[(ads_df['index_type'] == 'SKU') & (ads_df['dt'] == latest)])
    cat_count = len(ads_df[(ads_df['index_type'] == 'CATEGORY') & (ads_df['dt'] == latest)])
    anomaly_count = len(anomaly_df[anomaly_df['dt'] == latest]) if anomaly_df is not None and len(anomaly_df) > 0 else 0
    return jsonify({
        'date': latest,
        'overall_index': float(overall['price_index'].values[0]) if len(overall) > 0 else 0,
        'overall_mom': float(overall['mom_change_rate'].values[0]) if len(overall) > 0 and pd.notna(overall['mom_change_rate'].values[0]) else 0,
        'fisher_index': float(fisher['price_index'].values[0]) if len(fisher) > 0 else 0,
        'product_count': sku_count,
        'category_count': cat_count,
        'anomaly_count': anomaly_count,
    })


@app.route('/api/overall/trend')
def api_overall_trend():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    days = request.args.get('days', 30, type=int)
    overall = ads_df[ads_df['index_type'] == 'OVERALL'].sort_values('dt')
    dates = sorted(overall['dt'].unique())
    if len(dates) > days:
        dates = dates[-days:]
    overall = overall[overall['dt'].isin(dates)]
    fisher = ads_df[ads_df['index_type'] == 'FISHER'].sort_values('dt')
    fisher = fisher[fisher['dt'].isin(dates)]
    return jsonify({
        'dates': list(dates),
        'overall_index': overall['price_index'].tolist(),
        'overall_mom': overall['mom_change_rate'].fillna(0).tolist(),
        'fisher_index': fisher['price_index'].tolist(),
    })


@app.route('/api/categories')
def api_categories():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    latest = get_latest_date()
    cats = ads_df[(ads_df['index_type'] == 'CATEGORY_L1') & (ads_df['dt'] == latest)]
    cats = cats.sort_values('price_index', ascending=False)
    return jsonify([{
        'id': row['target_id'],
        'name': row['target_name'],
        'price_index': float(row['price_index']),
        'mom_change': float(row['mom_change_rate']) if pd.notna(row['mom_change_rate']) else 0,
    } for _, row in cats.iterrows()])


@app.route('/api/categories/trend')
def api_categories_trend():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    days = request.args.get('days', 365, type=int)
    cat_data = ads_df[ads_df['index_type'] == 'CATEGORY_L1'].copy()
    dates = sorted(cat_data['dt'].unique())
    if len(dates) > days:
        dates = dates[-days:]
    cat_data = cat_data[cat_data['dt'].isin(dates)]
    categories = sorted(cat_data['target_name'].unique())
    result = {
        'dates': list(dates),
        'categories': []
    }
    for cat in categories:
        cat_row = cat_data[cat_data['target_name'] == cat].sort_values('dt')
        result['categories'].append({
            'name': cat,
            'price_index': cat_row['price_index'].tolist(),
            'mom_change': cat_row['mom_change_rate'].fillna(0).tolist(),
        })
    return jsonify(result)


@app.route('/api/category/trend')
def api_category_trend():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    category_id = str(request.args.get('id', ''))
    days = request.args.get('days', 30, type=int)

    cat_data = ads_df[(ads_df['index_type'] == 'CATEGORY_L1') &
                      (ads_df['target_id'] == category_id)].sort_values('dt')
    if len(cat_data) == 0:
        cat_data = ads_df[(ads_df['index_type'] == 'CATEGORY') &
                          (ads_df['target_id'] == category_id)].sort_values('dt')
    if len(cat_data) == 0:
        cat_data = ads_df[(ads_df['index_type'] == 'CATEGORY_L1') &
                          (ads_df['target_name'] == category_id)].sort_values('dt')
    if len(cat_data) == 0:
        cat_data = ads_df[(ads_df['index_type'] == 'CATEGORY') &
                          (ads_df['target_name'] == category_id)].sort_values('dt')

    if len(cat_data) == 0:
        return jsonify({'error': 'category not found'}), 404

    dates = sorted(cat_data['dt'].unique())
    if len(dates) > days:
        dates = dates[-days:]
    cat_data = cat_data[cat_data['dt'].isin(dates)]
    return jsonify({
        'dates': list(dates),
        'category_name': cat_data['target_name'].iloc[0] if len(cat_data) > 0 else '',
        'price_index': cat_data['price_index'].tolist(),
        'mom_change': cat_data['mom_change_rate'].fillna(0).tolist(),
    })


@app.route('/api/category/skus')
def api_category_skus():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    category_id = str(request.args.get('id', ''))
    latest = get_latest_date()
    skus = ads_df[(ads_df['index_type'] == 'SKU') &
                  (ads_df['dt'] == latest) &
                  (ads_df['category_id_l1'] == category_id)]
    if len(skus) == 0:
        skus = ads_df[(ads_df['index_type'] == 'SKU') &
                      (ads_df['dt'] == latest) &
                      (ads_df['category_id'] == category_id)]
    if len(skus) == 0:
        skus = ads_df[(ads_df['index_type'] == 'SKU') &
                      (ads_df['dt'] == latest) &
                      (ads_df['category_l1'] == category_id)]
    if len(skus) == 0:
        skus = ads_df[(ads_df['index_type'] == 'SKU') &
                      (ads_df['dt'] == latest) &
                      (ads_df['category_name'] == category_id)]
    skus['mom_change_rate'] = skus['mom_change_rate'].fillna(0)
    top_gain = skus.sort_values('mom_change_rate', ascending=False).head(10)
    top_loss = skus.sort_values('mom_change_rate', ascending=True).head(10)
    result = pd.concat([top_gain, top_loss]).drop_duplicates(subset=['target_id'])
    return jsonify([{
        'id': row['target_id'],
        'name': row['target_name'],
        'price_index': float(row['price_index']),
        'mom_change': float(row['mom_change_rate']),
        'price': float(row['price']),
        'base_price': float(row['base_price']),
    } for _, row in result.iterrows()])


@app.route('/api/sku/search')
def api_sku_search():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    keyword = request.args.get('q', '')
    latest = get_latest_date()
    skus = ads_df[(ads_df['index_type'] == 'SKU') & (ads_df['dt'] == latest)]
    if keyword:
        skus = skus[skus['target_name'].str.contains(keyword, case=False, na=False)]
    skus = skus.head(20)
    return jsonify([{
        'id': row['target_id'],
        'name': row['target_name'],
        'category': row['category_name'],
        'category_l1': row['category_l1'],
        'price_index': float(row['price_index']),
    } for _, row in skus.iterrows()])


@app.route('/api/sku/trend')
def api_sku_trend():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    sku_id = request.args.get('id', '')
    days = request.args.get('days', 30, type=int)
    sku_data = ads_df[(ads_df['index_type'] == 'SKU') &
                      (ads_df['target_id'] == sku_id)].sort_values('dt')
    dates = sorted(sku_data['dt'].unique())
    if len(dates) > days:
        dates = dates[-days:]
    sku_data = sku_data[sku_data['dt'].isin(dates)]
    if len(sku_data) == 0:
        return jsonify({'error': 'sku not found'}), 404
    latest_row = sku_data.iloc[-1]
    return jsonify({
        'sku_id': sku_id,
        'sku_name': latest_row['target_name'],
        'category': latest_row['category_name'],
        'category_l1': latest_row['category_l1'],
        'current_price': float(latest_row['price']),
        'base_price': float(latest_row['base_price']),
        'price_index': float(latest_row['price_index']),
        'dates': list(dates),
        'prices': sku_data['price'].tolist(),
        'indexes': sku_data['price_index'].tolist(),
    })


@app.route('/api/anomaly')
def api_anomaly():
    if anomaly_df is None or len(anomaly_df) == 0:
        return jsonify({'total': 0, 'list': [], 'stats': {}})
    date = request.args.get('date', '')
    atype = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    df = anomaly_df
    if date:
        df = df[df['dt'] == date]
    if atype:
        df = df[df['anomaly_type'] == atype]
    total = len(df)

    # 计算统计数据
    stats = {'total': total}
    if len(df) > 0:
        type_counts = df['anomaly_type'].value_counts()
        for t, c in type_counts.items():
            stats[t] = int(c)

    start = (page - 1) * page_size
    df = df.iloc[start:start + page_size]
    return jsonify({
        'total': total,
        'page': page,
        'page_size': page_size,
        'list': df.fillna('').to_dict('records'),
        'stats': stats,
    })


@app.route('/api/mom/distribution')
def api_mom_distribution():
    if ads_df is None or len(ads_df) == 0:
        return jsonify([])
    latest = get_latest_date()
    skus = ads_df[(ads_df['index_type'] == 'SKU') & (ads_df['dt'] == latest)]
    skus = skus[skus['mom_change_rate'].notna()]

    bins = [-60, -40, -20, -10, -5, -2, 0, 2, 5, 10, 20, 40, 60]
    total = len(skus)

    result = []
    for i in range(len(bins) - 1):
        name = f'{bins[i]}~{bins[i+1]}%'
        condition = (skus['mom_change_rate'] >= bins[i]) & (skus['mom_change_rate'] < bins[i+1])
        count = int(condition.sum())
        pct = count / total * 100 if total > 0 else 0
        result.append({'range': name, 'count': count, 'percentage': round(pct, 2)})

    return jsonify(result)


@app.route('/api/ranking')
def api_ranking():
    if ads_df is None or len(ads_df) == 0:
        return jsonify({'error': 'no data'}), 404
    latest = get_latest_date()
    rtype = request.args.get('type', 'gain')
    n = request.args.get('n', 10, type=int)
    skus = ads_df[(ads_df['index_type'] == 'SKU') & (ads_df['dt'] == latest)]
    skus = skus.dropna(subset=['mom_change_rate'])
    if rtype == 'gain':
        skus = skus.nlargest(n, 'mom_change_rate')
    elif rtype == 'loss':
        skus = skus.nsmallest(n, 'mom_change_rate')
    else:
        skus = skus.reindex(skus['mom_change_rate'].abs().sort_values(ascending=False).index).head(n)
    return jsonify([{
        'id': row['target_id'],
        'name': row['target_name'],
        'category': row['category_name'] if pd.notna(row['category_name']) else '',
        'price_index': float(row['price_index']),
        'mom_change': float(row['mom_change_rate']),
        'price': float(row['price']),
    } for _, row in skus.iterrows()])


@app.route('/api/report/latest')
def api_report_latest():
    latest = get_latest_date()
    if not latest:
        return jsonify({'error': 'no data'}), 404
    report_path = os.path.join(DATA_DIR, 'reports', f'report_{latest}.json')
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'report not found'}), 404


@app.route('/api/report/list')
def api_report_list():
    report_dir = os.path.join(DATA_DIR, 'reports')
    if not os.path.exists(report_dir):
        return jsonify([])
    reports = sorted([f.replace('report_', '').replace('.json', '')
                      for f in os.listdir(report_dir) if f.endswith('.json')], reverse=True)
    return jsonify(reports[:30])


if __name__ == '__main__':
    load_data()
    print('=' * 60)
    print('高频电商价格指数计算平台 - 可视化服务')
    print('=' * 60)
    print(f'数据加载完成: {len(ads_df) if ads_df is not None else 0} 条指数记录')
    latest = get_latest_date()
    print(f'最新数据日期: {latest}')
    print('访问地址: http://localhost:5000')
    print('=' * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)

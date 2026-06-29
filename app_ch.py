"""
Flask Web服务 - 高频电商价格指数计算平台
支持两种数据源模式：本地CSV 和 ClickHouse
"""
import os
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='')


@app.before_request
def before_first_request():
    """首次请求时初始化数据"""
    if not hasattr(app, '_data_initialized'):
        from scripts.data_source import init_data
        init_data()
        app._data_initialized = True


@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(WEB_DIR, path)


@app.route('/api/overview')
def api_overview():
    from scripts.data_source import get_overview
    try:
        data = get_overview()
        return jsonify(data)
    except Exception as e:
        print(f"api_overview error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/overall/trend')
def api_overall_trend():
    from scripts.data_source import get_overall_trend
    days = request.args.get('days', 30, type=int)
    data = get_overall_trend(days)
    if not data:
        return jsonify({'error': 'no data'}), 404
    return jsonify(data)


@app.route('/api/categories')
def api_categories():
    from scripts.data_source import get_categories
    data = get_categories()
    return jsonify(data)


@app.route('/api/category/trend')
def api_category_trend():
    from scripts.data_source import get_category_trend
    category_id = request.args.get('id', '')
    days = request.args.get('days', 30, type=int)
    data = get_category_trend(category_id, days)
    if not data or not data.get('dates'):
        return jsonify({'error': 'category not found'}), 404
    return jsonify(data)


@app.route('/api/category/skus')
def api_category_skus():
    from scripts.data_source import get_category_skus
    category_id = request.args.get('id', '')
    data = get_category_skus(category_id)
    return jsonify(data)


@app.route('/api/categories/trend')
def api_categories_trend():
    from scripts.data_source import get_categories_trend
    days = request.args.get('days', 365, type=int)
    data = get_categories_trend(days)
    return jsonify(data)


@app.route('/api/mom/distribution')
def api_mom_distribution():
    from scripts.data_source import get_mom_distribution
    days = request.args.get('days', 30, type=int)
    data = get_mom_distribution(days)
    return jsonify(data)


@app.route('/api/ranking')
def api_ranking():
    from scripts.data_source import get_ranking
    rtype = request.args.get('type', 'gain')
    n = request.args.get('n', 10, type=int)
    data = get_ranking(n)
    
    if rtype == 'gain':
        items = data.get('gain', [])
    elif rtype == 'loss':
        items = data.get('loss', [])
    else:
        # vol 类型：取涨幅和跌幅合并后按绝对值排序
        gain = data.get('gain', [])
        loss = data.get('loss', [])
        all_items = gain + loss
        all_items.sort(key=lambda x: abs(x.get('mom_change_rate', 0) or x.get('mom_change', 0)), reverse=True)
        items = all_items[:n]
    
    # 统一字段名
    result = []
    for item in items:
        result.append({
            'id': item.get('product_id', item.get('id', '')),
            'name': item.get('product_name', item.get('name', '')),
            'category': item.get('category_l1', item.get('category', '')),
            'price_index': float(item.get('price_index', 0)),
            'mom_change': float(item.get('mom_change_rate', item.get('mom_change', 0))),
            'price': float(item.get('price', 0)),
        })
    
    return jsonify(result)


@app.route('/api/sku/search')
def api_sku_search():
    from scripts.data_source import get_sku_search
    keyword = request.args.get('q', '')
    if not keyword:
        return jsonify([])
    data = get_sku_search(keyword)
    return jsonify(data)


@app.route('/api/sku/trend')
def api_sku_trend():
    from scripts.data_source import get_sku_trend
    sku_id = request.args.get('id', '')
    days = request.args.get('days', 30, type=int)
    data = get_sku_trend(sku_id, days)
    if not data:
        return jsonify({'error': 'SKU not found'}), 404
    return jsonify(data)


@app.route('/api/anomaly')
def api_anomaly():
    from scripts.data_source import get_anomaly
    date = request.args.get('date', '')
    atype = request.args.get('type', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    data = get_anomaly(date, atype, page, page_size)
    return jsonify(data)


@app.route('/api/report/list')
def api_report_list():
    from scripts.data_source import get_all_dates
    dates = get_all_dates()
    return jsonify(dates)


@app.route('/api/report/latest')
@app.route('/api/report')
def api_report():
    from scripts.data_source import (
        get_overview, get_categories, get_ranking
    )
    from datetime import datetime

    date = request.args.get('date', None)
    overview = get_overview()
    categories = get_categories()
    ranking = get_ranking(10)

    cat_sorted = sorted(categories, key=lambda x: x.get('mom_change', 0), reverse=True)
    top_gain = cat_sorted[:5]
    top_loss = cat_sorted[-5:][::-1]

    gain_skus = ranking.get('gain', [])
    loss_skus = ranking.get('loss', [])
    all_skus = gain_skus + loss_skus
    all_skus.sort(key=lambda x: abs(x.get('mom_change', 0)), reverse=True)
    top_volatile = all_skus[:10]

    report = {
        'date': overview.get('date', ''),
        'overall_index': overview.get('overall_index', 100),
        'overall_mom_change': overview.get('overall_mom', 0),
        'fisher_index': overview.get('fisher_index', 100),
        'product_count': overview.get('product_count', 0),
        'category_count': overview.get('category_count', 0),
        'anomaly_count': overview.get('anomaly_count', 0),
        'generate_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'top_gain_categories': [
            {
                'target_name': c.get('name', ''),
                'price_index': c.get('price_index', 0),
                'mom_change_rate': c.get('mom_change', 0),
            }
            for c in top_gain
        ],
        'top_loss_categories': [
            {
                'target_name': c.get('name', ''),
                'price_index': c.get('price_index', 0),
                'mom_change_rate': c.get('mom_change', 0),
            }
            for c in top_loss
        ],
        'top_volatile_skus': [
            {
                'target_name': s.get('product_name', s.get('name', '')),
                'price_index': s.get('price_index', 0),
                'mom_change_rate': s.get('mom_change', 0),
            }
            for s in top_volatile
        ],
    }

    return jsonify(report)


@app.route('/api/status')
def api_status():
    """API状态检查"""
    from scripts.data_source import get_latest_date, get_local_dataframes
    from scripts.data_source import _use_clickhouse
    import config

    ads_df, anomaly_df = get_local_dataframes()

    return jsonify({
        'status': 'running',
        'data_source': config.DATA_SOURCE,
        'use_clickhouse': _use_clickhouse,
        'latest_date': get_latest_date(),
        'ads_count': len(ads_df) if ads_df is not None else 0,
        'anomaly_count': len(anomaly_df) if anomaly_df is not None else 0,
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("高频电商价格指数计算平台")
    print("="*60)
    print("启动Flask服务...")
    print("访问地址: http://localhost:5000")
    print("="*60 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=False)

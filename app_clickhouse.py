"""
Flask API - ClickHouse版本
直接从ClickHouse查询数据，性能提升10~100倍
"""
import os
import sys
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clickhouse'))

from ch_client import get_client_from_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='')

ch_client = None


def get_ch():
    global ch_client
    if ch_client is None:
        ch_client = get_client_from_config()
    return ch_client


def get_latest_date():
    result = get_ch().execute(
        "SELECT max(dt) FROM ads_overall_price_index"
    )
    return result[0][0] if result and result[0][0] else None


@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(WEB_DIR, path)


@app.route('/api/overview')
def api_overview():
    latest = get_latest_date()
    if not latest:
        return jsonify({'error': 'no data'}), 404

    ch = get_ch()

    overall_sql = f"""
    SELECT
        maxIf(price_index, index_type = 'OVERALL') AS overall_index,
        maxIf(mom_change_rate, index_type = 'OVERALL') AS overall_mom,
        maxIf(price_index, index_type = 'FISHER') AS fisher_index
    FROM ads_overall_price_index
    WHERE dt = '{latest}'
    """
    result = ch.execute(overall_sql)
    overall_index, overall_mom, fisher_index = result[0]

    sku_count = ch.execute(
        f"SELECT count(DISTINCT product_id) FROM dws_sku_price_index_daily WHERE dt = '{latest}'"
    )[0][0]

    cat_count = ch.execute(
        f"SELECT count(DISTINCT category_id) FROM dws_category_price_index_daily WHERE category_level = 1 AND dt = '{latest}'"
    )[0][0]

    anomaly_count = ch.execute(
        f"SELECT count() FROM dwd_anomaly_data WHERE dt = '{latest}'"
    )[0][0]

    return jsonify({
        'date': str(latest),
        'overall_index': float(overall_index) if overall_index else 0,
        'overall_mom': float(overall_mom) if overall_mom else 0,
        'fisher_index': float(fisher_index) if fisher_index else 0,
        'product_count': int(sku_count),
        'category_count': int(cat_count),
        'anomaly_count': int(anomaly_count),
    })


@app.route('/api/overall/trend')
def api_overall_trend():
    days = request.args.get('days', 30, type=int)
    ch = get_ch()

    sql = f"""
    SELECT
        dt,
        maxIf(price_index, index_type = 'OVERALL') AS overall_index,
        maxIf(mom_change_rate, index_type = 'OVERALL') AS overall_mom,
        maxIf(price_index, index_type = 'FISHER') AS fisher_index
    FROM ads_overall_price_index
    WHERE dt >= (SELECT max(dt) - {days} FROM ads_overall_price_index)
    GROUP BY dt
    ORDER BY dt
    """
    result = ch.execute(sql)

    dates = [str(r[0]) for r in result]
    overall_index = [float(r[1]) if r[1] else 0 for r in result]
    overall_mom = [float(r[2]) if r[2] else 0 for r in result]
    fisher_index = [float(r[3]) if r[3] else 0 for r in result]

    return jsonify({
        'dates': dates,
        'overall_index': overall_index,
        'overall_mom': overall_mom,
        'fisher_index': fisher_index,
    })


@app.route('/api/categories')
def api_categories():
    latest = get_latest_date()
    if not latest:
        return jsonify({'error': 'no data'}), 404

    ch = get_ch()
    sql = f"""
    SELECT
        category_id,
        category_name,
        price_index,
        mom_change_rate
    FROM dws_category_price_index_daily
    WHERE category_level = 1
      AND dt = '{latest}'
    ORDER BY price_index DESC
    """
    result = ch.execute(sql)

    return jsonify([{
        'id': str(r[0]),
        'name': r[1],
        'price_index': float(r[2]),
        'mom_change': float(r[3]) if r[3] else 0,
    } for r in result])


@app.route('/api/category/trend')
def api_category_trend():
    category_id = request.args.get('id', '')
    days = request.args.get('days', 30, type=int)
    ch = get_ch()

    sql = f"""
    SELECT
        dt,
        category_name,
        price_index,
        mom_change_rate
    FROM dws_category_price_index_daily
    WHERE category_id = {category_id}
      AND dt >= (SELECT max(dt) - {days} FROM dws_category_price_index_daily WHERE category_id = {category_id})
    ORDER BY dt
    """
    result = ch.execute(sql)

    if not result:
        return jsonify({'error': 'category not found'}), 404

    return jsonify({
        'dates': [str(r[0]) for r in result],
        'category_name': result[0][1],
        'price_index': [float(r[2]) for r in result],
        'mom_change': [float(r[3]) if r[3] else 0 for r in result],
    })


@app.route('/api/category/skus')
def api_category_skus():
    category_id = request.args.get('id', '')
    latest = get_latest_date()
    if not latest:
        return jsonify({'error': 'no data'}), 404

    ch = get_ch()
    sql = f"""
    SELECT
        product_id,
        product_name,
        price_index,
        mom_change_rate,
        price,
        base_price
    FROM dws_sku_price_index_daily
    WHERE dt = '{latest}'
      AND (category_l1 = '{category_id}' OR category_id = {category_id})
    ORDER BY price_index DESC
    LIMIT 10
    """
    result = ch.execute(sql)

    return jsonify([{
        'id': str(r[0]),
        'name': r[1],
        'price_index': float(r[2]),
        'mom_change': float(r[3]) if r[3] else 0,
        'price': float(r[4]),
        'base_price': float(r[5]),
    } for r in result])


@app.route('/api/sku/search')
def api_sku_search():
    keyword = request.args.get('q', '')
    latest = get_latest_date()
    if not latest:
        return jsonify({'error': 'no data'}), 404

    ch = get_ch()
    where_sql = f"dt = '{latest}'"
    if keyword:
        where_sql += f" AND product_name LIKE '%{keyword}%'"

    sql = f"""
    SELECT
        product_id,
        product_name,
        category_name,
        category_l1,
        price_index
    FROM dws_sku_price_index_daily
    WHERE {where_sql}
    LIMIT 20
    """
    result = ch.execute(sql)

    return jsonify([{
        'id': str(r[0]),
        'name': r[1],
        'category': r[2],
        'category_l1': r[3],
        'price_index': float(r[4]),
    } for r in result])


@app.route('/api/sku/trend')
def api_sku_trend():
    sku_id = request.args.get('id', '')
    days = request.args.get('days', 30, type=int)
    ch = get_ch()

    sql = f"""
    SELECT
        dt,
        product_name,
        category_name,
        category_l1,
        price,
        base_price,
        price_index
    FROM dws_sku_price_index_daily
    WHERE product_id = {sku_id}
    ORDER BY dt
    LIMIT {days}
    """
    result = ch.execute(sql)

    if not result:
        return jsonify({'error': 'sku not found'}), 404

    latest = result[-1]
    return jsonify({
        'sku_id': sku_id,
        'sku_name': latest[1],
        'category': latest[2],
        'category_l1': latest[3],
        'current_price': float(latest[4]),
        'base_price': float(latest[5]),
        'price_index': float(latest[6]),
        'dates': [str(r[0]) for r in result],
        'prices': [float(r[4]) for r in result],
        'indexes': [float(r[6]) for r in result],
    })


@app.route('/api/anomaly')
def api_anomaly():
    date = request.args.get('date', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    ch = get_ch()

    where_sql = '1=1'
    if date:
        where_sql += f" AND dt = '{date}'"

    total = ch.execute(
        f"SELECT count() FROM dwd_anomaly_data WHERE {where_sql}"
    )[0][0]

    start = (page - 1) * page_size
    sql = f"""
    SELECT *
    FROM dwd_anomaly_data
    WHERE {where_sql}
    ORDER BY dt DESC
    LIMIT {page_size}
    OFFSET {start}
    """
    result = ch.execute(sql)

    return jsonify({
        'total': int(total),
        'page': page,
        'page_size': page_size,
        'list': [dict(zip(
            ['product_id', 'category_id', 'price', 'anomaly_type', 'dt', 'create_time'],
            r
        )) for r in result],
    })


@app.route('/api/ranking')
def api_ranking():
    latest = get_latest_date()
    if not latest:
        return jsonify({'error': 'no data'}), 404

    rtype = request.args.get('type', 'gain')
    n = request.args.get('n', 10, type=int)
    ch = get_ch()

    order = 'DESC' if rtype == 'gain' else ('ASC' if rtype == 'loss' else 'DESC')
    order_col = 'mom_change_rate' if rtype != 'vol' else 'abs(mom_change_rate)'

    sql = f"""
    SELECT
        product_id,
        product_name,
        category_name,
        price_index,
        mom_change_rate,
        price
    FROM dws_sku_price_index_daily
    WHERE dt = '{latest}'
      AND mom_change_rate IS NOT NULL
    ORDER BY {order_col} {order}
    LIMIT {n}
    """
    result = ch.execute(sql)

    return jsonify([{
        'id': str(r[0]),
        'name': r[1],
        'category': r[2],
        'price_index': float(r[3]),
        'mom_change': float(r[4]),
        'price': float(r[5]),
    } for r in result])


@app.route('/api/report/latest')
def api_report_latest():
    latest = get_latest_date()
    if not latest:
        return jsonify({'error': 'no data'}), 404

    ch = get_ch()
    sql = f"""
    SELECT *
    FROM ads_daily_report
    WHERE dt = '{latest}'
    LIMIT 1
    """
    result = ch.execute(sql)

    if not result:
        return jsonify({'error': 'report not found'}), 404

    row = result[0]
    return jsonify({
        'date': str(row[0]),
        'overall_index': float(row[1]),
        'overall_mom_change': float(row[2]),
        'fisher_index': float(row[3]),
        'product_count': int(row[4]),
        'category_count': int(row[5]),
        'anomaly_count': int(row[6]),
        'top_gain_categories': row[7],
        'top_loss_categories': row[8],
        'top_volatile_skus': row[9],
        'generate_time': str(row[10]),
    })


@app.route('/api/report/list')
def api_report_list():
    ch = get_ch()
    sql = """
    SELECT dt
    FROM ads_daily_report
    ORDER BY dt DESC
    LIMIT 30
    """
    result = ch.execute(sql)
    return jsonify([str(r[0]) for r in result])


if __name__ == '__main__':
    print('=' * 60)
    print('高频电商价格指数计算平台 - ClickHouse版可视化服务')
    print('=' * 60)

    try:
        ch = get_ch()
        if ch.test_connection():
            print('✓ ClickHouse连接成功')
            latest = get_latest_date()
            print(f'最新数据日期: {latest}')
        else:
            print('✗ ClickHouse连接失败')
    except Exception as e:
        print(f'✗ ClickHouse连接异常: {e}')

    print('访问地址: http://localhost:5000')
    print('=' * 60)

    app.run(host='0.0.0.0', port=5000, debug=False)

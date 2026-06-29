"""
ClickHouse数据查询模块 - OSS外表版
封装所有从ClickHouse查询数据的逻辑
支持从OSS外部表读取数据
"""
import pandas as pd
from typing import Optional, Dict, Any, List
from scripts.clickhouse_utils import get_ch_client


# ============================================================
# 表名配置
# 当OSS数据完整上传后，切换到 _oss 后缀的OSS外表
# ============================================================
def _get_table(name: str) -> str:
    """获取表名，优先使用OSS外表"""
    # 目前只有小文件表的OSS外表可用
    # ads_price_index 等all_index.csv上传后再切换
    oss_available = {
        'dim_categories': True,
        'dim_products': True,
        'ads_anomaly': False,  # 使用ClickHouse本地表（性能更好）
        'ads_price_index': False,  # 使用ClickHouse本地表（性能更好）
    }
    if oss_available.get(name, False):
        return name + '_oss'
    return name


def get_latest_date() -> str:
    """获取最新日期"""
    client = get_ch_client()
    if not client.is_connected():
        return "2028-05-15"

    table = _get_table('ads_price_index')
    result = client.query(f"""
        SELECT max(dt) as latest_date
        FROM {table}
        WHERE dt IS NOT NULL
    """)
    if len(result) > 0 and result['latest_date'].iloc[0]:
        return str(result['latest_date'].iloc[0])
    return "2028-05-15"


def get_all_dates() -> List[str]:
    """获取所有日期列表"""
    client = get_ch_client()
    if not client.is_connected():
        return ["2028-05-15"]

    table = _get_table('ads_price_index')
    result = client.query(f"""
        SELECT DISTINCT dt
        FROM {table}
        WHERE dt IS NOT NULL
        ORDER BY dt DESC
        LIMIT 365
    """)
    if len(result) > 0:
        return result['dt'].tolist()
    return ["2028-05-15"]


def get_overview() -> Dict[str, Any]:
    """获取首页概览数据"""
    client = get_ch_client()
    latest = get_latest_date()
    table = _get_table('ads_price_index')
    anomaly_table = _get_table('ads_anomaly')

    overall = client.query(f"""
        SELECT price_index, mom_change_rate
        FROM {table}
        WHERE index_type = 'OVERALL' AND dt = '{latest}'
        LIMIT 1
    """)

    fisher = client.query(f"""
        SELECT price_index, mom_change_rate
        FROM {table}
        WHERE index_type = 'FISHER' AND dt = '{latest}'
        LIMIT 1
    """)

    sku_count = client.query(f"""
        SELECT count(DISTINCT target_id) as cnt
        FROM {table}
        WHERE index_type = 'SKU' AND dt = '{latest}'
    """)

    cat_count = client.query(f"""
        SELECT count(DISTINCT target_id) as cnt
        FROM {table}
        WHERE index_type = 'CATEGORY_L1' AND dt = '{latest}'
    """)

    anomaly_count = client.query(f"""
        SELECT count() as cnt
        FROM {anomaly_table}
        WHERE dt = '{latest}'
    """)

    return {
        'date': latest,
        'overall_index': float(overall['price_index'].iloc[0]) if len(overall) > 0 else 100.0,
        'overall_mom': float(overall['mom_change_rate'].iloc[0]) if len(overall) > 0 else 0.0,
        'fisher_index': float(fisher['price_index'].iloc[0]) if len(fisher) > 0 else 100.0,
        'fisher_mom': float(fisher['mom_change_rate'].iloc[0]) if len(fisher) > 0 else 0.0,
        'product_count': int(sku_count['cnt'].iloc[0]) if len(sku_count) > 0 else 0,
        'category_count': int(cat_count['cnt'].iloc[0]) if len(cat_count) > 0 else 0,
        'anomaly_count': int(anomaly_count['cnt'].iloc[0]) if len(anomaly_count) > 0 else 0,
    }


def get_categories() -> List[Dict[str, Any]]:
    """获取一级类目列表"""
    client = get_ch_client()
    latest = get_latest_date()
    table = _get_table('ads_price_index')

    result = client.query(f"""
        SELECT
            target_id,
            target_name as name,
            price_index,
            mom_change_rate as mom_change
        FROM {table}
        WHERE index_type = 'CATEGORY_L1' AND dt = '{latest}'
        ORDER BY price_index DESC
    """)

    if len(result) == 0:
        return []

    return [{
        'id': str(row['target_id']),
        'name': row['name'],
        'price_index': float(row['price_index']),
        'mom_change': float(row['mom_change']) if pd.notna(row['mom_change']) else 0.0,
    } for _, row in result.iterrows()]


def get_ranking(limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    """获取涨幅/跌幅排行榜"""
    client = get_ch_client()
    latest = get_latest_date()
    table = _get_table('ads_price_index')

    gain = client.query(f"""
        SELECT
            target_id,
            target_name,
            category_l1,
            price_index,
            mom_change_rate,
            price
        FROM {table}
        WHERE index_type = 'SKU' AND dt = '{latest}'
        ORDER BY mom_change_rate DESC
        LIMIT {limit}
    """)

    loss = client.query(f"""
        SELECT
            target_id,
            target_name,
            category_l1,
            price_index,
            mom_change_rate,
            price
        FROM {table}
        WHERE index_type = 'SKU' AND dt = '{latest}'
        ORDER BY mom_change_rate ASC
        LIMIT {limit}
    """)

    gain_list = []
    loss_list = []

    for _, row in gain.iterrows():
        gain_list.append({
            'product_id': str(row['target_id']),
            'product_name': row['target_name'],
            'category': row['category_l1'],
            'price_index': float(row['price_index']),
            'mom_change': float(row['mom_change_rate']) if pd.notna(row['mom_change_rate']) else 0.0,
            'price': float(row['price']),
        })

    for _, row in loss.iterrows():
        loss_list.append({
            'product_id': str(row['target_id']),
            'product_name': row['target_name'],
            'category': row['category_l1'],
            'price_index': float(row['price_index']),
            'mom_change': float(row['mom_change_rate']) if pd.notna(row['mom_change_rate']) else 0.0,
            'price': float(row['price']),
        })

    return {'gain': gain_list, 'loss': loss_list}


def get_category_trend(category_id: str, days: int = 30) -> Dict[str, Any]:
    """获取类目趋势"""
    client = get_ch_client()
    table = _get_table('ads_price_index')

    result = client.query(f"""
        SELECT dt, target_name, price_index, mom_change_rate
        FROM {table}
        WHERE index_type = 'CATEGORY_L1'
          AND (target_id = '{category_id}' OR target_name = '{category_id}' OR toString(toInt64OrZero(target_id)) = '{category_id}')
        ORDER BY dt DESC
        LIMIT {days}
    """)

    if len(result) == 0:
        return {}

    result = result.sort_values('dt')

    return {
        'dates': result['dt'].tolist(),
        'category_name': result['target_name'].iloc[0] if len(result) > 0 else '',
        'price_index': result['price_index'].fillna(100).tolist(),
        'mom_change': result['mom_change_rate'].fillna(0).tolist(),
    }


def get_categories_trend(days: int = 365) -> Dict[str, Any]:
    """获取所有一级类目趋势"""
    client = get_ch_client()
    table = _get_table('ads_price_index')

    result = client.query(f"""
        SELECT
            target_name,
            dt,
            price_index,
            mom_change_rate
        FROM {table}
        WHERE index_type = 'CATEGORY_L1'
        ORDER BY dt
        LIMIT {days * 8}
    """)

    dates = sorted(result['dt'].unique())
    categories = result['target_name'].unique()

    cat_data = []
    for cat in categories:
        cat_rows = result[result['target_name'] == cat].sort_values('dt')
        cat_data.append({
            'name': cat,
            'price_index': cat_rows['price_index'].fillna(100).tolist(),
            'mom_change': cat_rows['mom_change_rate'].fillna(0).tolist(),
        })

    return {
        'dates': dates,
        'categories': cat_data,
    }


def get_category_skus(category_id: str, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
    """获取类目下SKU列表"""
    client = get_ch_client()
    latest = get_latest_date()
    table = _get_table('ads_price_index')

    result = client.query(f"""
        SELECT
            target_id,
            target_name,
            category_l1,
            category_name,
            price_index,
            mom_change_rate,
            price,
            base_price
        FROM {table}
        WHERE index_type = 'SKU'
          AND (category_l1 = '{category_id}'
               OR category_id_l1 = '{category_id}'
               OR category_id_l1 = '{category_id}.0'
               OR replaceOne(category_id_l1, '.0', '') = '{category_id}')
          AND dt = '{latest}'
        ORDER BY abs(mom_change_rate) DESC
        LIMIT {limit}
    """)

    if len(result) == 0:
        return []

    return [{
        'id': str(row['target_id']),
        'name': row['target_name'],
        'price_index': float(row['price_index']),
        'mom_change': float(row['mom_change_rate']) if pd.notna(row['mom_change_rate']) else 0.0,
        'price': float(row['price']),
        'base_price': float(row['base_price']),
    } for _, row in result.iterrows()]


def get_anomaly(
    date: str = None,
    anomaly_type: str = None,
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    """获取异常数据"""
    client = get_ch_client()
    table = _get_table('ads_anomaly')

    where = ""
    conditions = []
    if date:
        conditions.append(f"dt = '{date}'")
    if anomaly_type and anomaly_type != 'all':
        conditions.append(f"anomaly_type = '{anomaly_type}'")
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    result = client.query(f"""
        SELECT
            dt,
            product_id,
            product_name,
            category_l1,
            current_price,
            base_price,
            anomaly_type,
            anomaly_desc,
            change_rate,
            z_score,
            price_ratio,
            CASE
                WHEN change_rate IS NOT NULL AND change_rate != 0
                THEN current_price / (1 + change_rate / 100)
                ELSE NULL
            END as prev_price
        FROM {table}
        {where}
        ORDER BY dt DESC, abs(change_rate) DESC
        LIMIT {page_size}
        OFFSET {(page - 1) * page_size}
    """)

    stats_all = client.query(f"""
        SELECT anomaly_type, count() as cnt
        FROM {table}
        WHERE dt = (SELECT max(dt) FROM {table})
        GROUP BY anomaly_type
        ORDER BY cnt DESC
    """)

    total = client.query(f"""
        SELECT count() as cnt FROM {table} {where}
    """)

    stats_dict = {}
    total_stats = 0
    for _, row in stats_all.iterrows():
        stats_dict[row['anomaly_type']] = int(row['cnt'])
        total_stats += int(row['cnt'])
    stats_dict['total'] = total_stats

    records = result.to_dict('records') if len(result) > 0 else []
    for r in records:
        if r.get('prev_price') is not None and pd.notna(r['prev_price']):
            r['prev_price'] = round(float(r['prev_price']), 2)
        # 把 NaN 转成 None，否则 JSON 序列化失败
        for k, v in r.items():
            if isinstance(v, float) and pd.isna(v):
                r[k] = None

    return {
        'list': records,
        'total': int(total['cnt'].iloc[0]) if len(total) > 0 else 0,
        'stats': stats_dict,
        'page': page,
        'page_size': page_size,
    }


def get_sku_search(query: str) -> List[Dict[str, Any]]:
    """搜索SKU"""
    client = get_ch_client()
    latest = get_latest_date()
    table = _get_table('ads_price_index')

    result = client.query(f"""
        SELECT DISTINCT
            target_id,
            target_name,
            category_l1,
            category_name,
            price_index
        FROM {table}
        WHERE index_type = 'SKU'
          AND dt = '{latest}'
          AND target_name ILIKE '%{query}%'
        ORDER BY price_index DESC
        LIMIT 50
    """)

    if len(result) == 0:
        return []

    return [{
        'id': str(row['target_id']),
        'name': row['target_name'],
        'category_l1': row['category_l1'],
        'category': row['category_name'],
        'price_index': float(row['price_index']),
    } for _, row in result.iterrows()]


def get_sku_trend(sku_id: str, days: int = 30) -> Dict[str, Any]:
    """获取SKU趋势数据"""
    client = get_ch_client()
    table = _get_table('ads_price_index')

    result = client.query(f"""
        SELECT dt, target_name, price, base_price, price_index, mom_change_rate
        FROM {table}
        WHERE index_type = 'SKU'
          AND target_id = '{sku_id}'
        ORDER BY dt DESC
        LIMIT {days}
    """)

    if len(result) == 0:
        return {}

    result = result.sort_values('dt')

    return {
        'dates': result['dt'].tolist(),
        'sku_name': result['target_name'].iloc[0] if len(result) > 0 else '',
        'prices': result['price'].tolist(),
        'indexes': result['price_index'].tolist(),
        'current_price': float(result['price'].iloc[-1]),
        'base_price': float(result['base_price'].iloc[0]),
        'price_index': float(result['price_index'].iloc[-1]),
    }


def get_overall_trend(days: int = 30) -> Dict[str, Any]:
    """获取全网指数趋势"""
    client = get_ch_client()
    table = _get_table('ads_price_index')

    # 查询加权指数 (OVERALL)
    overall = client.query(f"""
        SELECT dt, price_index, mom_change_rate
        FROM {table}
        WHERE index_type = 'OVERALL'
        ORDER BY dt DESC
        LIMIT {days}
    """)

    # 查询费雪指数 (FISHER)
    fisher = client.query(f"""
        SELECT dt, price_index
        FROM {table}
        WHERE index_type = 'FISHER'
        ORDER BY dt DESC
        LIMIT {days}
    """)

    if len(overall) == 0:
        return {}

    overall = overall.sort_values('dt')
    fisher = fisher.sort_values('dt')

    return {
        'dates': overall['dt'].tolist(),
        'overall_index': overall['price_index'].tolist(),
        'overall_mom': overall['mom_change_rate'].fillna(0).tolist(),
        'fisher_index': fisher['price_index'].tolist() if len(fisher) > 0 else [],
    }


def get_mom_distribution(days: int = 30) -> List[Dict[str, Any]]:
    """获取日环比分布"""
    client = get_ch_client()
    latest = get_latest_date()
    table = _get_table('ads_price_index')

    bins = [-60, -40, -20, -10, -5, -2, 0, 2, 5, 10, 20, 40, 60]
    case_stmts = []
    for i in range(len(bins) - 1):
        case_stmts.append(
            f"sum(CASE WHEN mom_change_rate >= {bins[i]} AND mom_change_rate < {bins[i+1]} THEN 1 ELSE 0 END) as bin_{i}"
        )

    result = client.query(f"""
        SELECT
            count() as total,
            {', '.join(case_stmts)}
        FROM {table}
        WHERE index_type = 'SKU' AND dt = '{latest}'
          AND mom_change_rate IS NOT NULL
    """)

    if len(result) == 0:
        return []

    row = result.iloc[0]
    total = int(row['total'])

    ranges = []
    for i in range(len(bins) - 1):
        name = f'{bins[i]}~{bins[i+1]}%'
        cnt = int(row[f'bin_{i}'])
        ranges.append((name, cnt))

    return [{
        'range': name,
        'count': cnt,
        'percentage': round(cnt / total * 100, 2) if total > 0 else 0
    } for name, cnt in ranges]


def get_daily_report(date: str = None) -> List[Dict[str, Any]]:
    """获取日报数据"""
    client = get_ch_client()

    if date is None:
        date = get_latest_date()

    result = client.query(f"""
        SELECT *
        FROM ads_daily_report
        WHERE dt = '{date}'
        ORDER BY category
    """)

    return result.to_dict('records') if len(result) > 0 else []

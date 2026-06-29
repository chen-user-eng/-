"""
统一数据查询接口
根据配置自动选择数据源：本地CSV 或 ClickHouse
"""
import config
import pandas as pd
from typing import Optional, Dict, Any, List

# 延迟导入，避免未安装时报错
_use_clickhouse = config.DATA_SOURCE == "clickhouse"

# 本地数据（仅在local模式下使用）
_local_ads_df = None
_local_anomaly_df = None


def load_local_data():
    """加载本地CSV数据"""
    global _local_ads_df, _local_anomaly_df
    import os

    ads_path = os.path.join(config.LOCAL_DATA_DIR, 'ads', 'all_index.csv')
    if os.path.exists(ads_path):
        _local_ads_df = pd.read_csv(ads_path, low_memory=False)
        _local_ads_df['dt'] = _local_ads_df['dt'].astype(str)
        _local_ads_df['target_id'] = _local_ads_df['target_id'].astype(str)
        for col in ['category_id', 'category_id_l2', 'category_id_l1']:
            if col in _local_ads_df.columns:
                _local_ads_df[col] = pd.to_numeric(_local_ads_df[col], errors='coerce').fillna(0).astype(int).astype(str)

    anomaly_dir = os.path.join(config.LOCAL_DATA_DIR, 'ads', 'anomaly')
    anomaly_list = []
    if os.path.exists(anomaly_dir):
        for f in sorted(os.listdir(anomaly_dir)):
            if f.endswith('.csv'):
                df = pd.read_csv(os.path.join(anomaly_dir, f))
                date_str = f.replace('anomaly_', '').replace('.csv', '')
                df['dt'] = date_str
                anomaly_list.append(df)
    _local_anomaly_df = pd.concat(anomaly_list, ignore_index=True) if anomaly_list else pd.DataFrame()

    return len(_local_ads_df) if _local_ads_df is not None else 0


def init_data():
    """初始化数据（根据配置加载数据源）"""
    if _use_clickhouse:
        from scripts.clickhouse_utils import get_ch_client
        client = get_ch_client()
        if client.is_connected():
            print("✅ 数据源: ClickHouse")
            return True
        else:
            print("⚠️ ClickHouse连接失败，尝试使用本地数据...")
    else:
        count = load_local_data()
        print(f"✅ 数据源: 本地CSV ({count:,} 条)")
        return True
    return False


def get_latest_date() -> str:
    """获取最新日期"""
    if _use_clickhouse:
        from scripts.ch_queries import get_latest_date as ck_get_latest
        return ck_get_latest()
    else:
        if _local_ads_df is None or len(_local_ads_df) == 0:
            return "2028-05-15"
        return sorted(_local_ads_df['dt'].unique())[-1]


def get_all_dates() -> List[str]:
    """获取所有日期列表"""
    if _use_clickhouse:
        from scripts.ch_queries import get_all_dates as ck_get_all_dates
        return ck_get_all_dates()
    else:
        if _local_ads_df is None or len(_local_ads_df) == 0:
            return ["2028-05-15"]
        return sorted(_local_ads_df['dt'].unique(), reverse=True)[:365]


def get_overview() -> Dict[str, Any]:
    """获取首页概览数据"""
    if _use_clickhouse:
        from scripts.ch_queries import get_overview as ck_overview
        return ck_overview()
    else:
        latest = get_latest_date()
        overall = _local_ads_df[(_local_ads_df['index_type'] == 'OVERALL') & (_local_ads_df['dt'] == latest)]
        fisher = _local_ads_df[(_local_ads_df['index_type'] == 'FISHER') & (_local_ads_df['dt'] == latest)]
        sku_count = len(_local_ads_df[(_local_ads_df['index_type'] == 'SKU') & (_local_ads_df['dt'] == latest)])
        cat_count = len(_local_ads_df[(_local_ads_df['index_type'] == 'CATEGORY_L1') & (_local_ads_df['dt'] == latest)])
        anomaly_count = len(_local_anomaly_df[_local_anomaly_df['dt'] == latest]) if len(_local_anomaly_df) > 0 else 0

        return {
            'date': latest,
            'overall_index': float(overall['price_index'].values[0]) if len(overall) > 0 else 100.0,
            'overall_mom': float(overall['mom_change_rate'].values[0]) if len(overall) > 0 and pd.notna(overall['mom_change_rate'].values[0]) else 0.0,
            'fisher_index': float(fisher['price_index'].values[0]) if len(fisher) > 0 else 100.0,
            'fisher_mom': float(fisher['mom_change_rate'].values[0]) if len(fisher) > 0 and pd.notna(fisher['mom_change_rate'].values[0]) else 0.0,
            'product_count': sku_count,
            'category_count': cat_count,
            'anomaly_count': anomaly_count,
        }


def get_categories() -> List[Dict[str, Any]]:
    """获取一级类目列表"""
    if _use_clickhouse:
        from scripts.ch_queries import get_categories as ck_categories
        return ck_categories()
    else:
        latest = get_latest_date()
        cats = _local_ads_df[(_local_ads_df['index_type'] == 'CATEGORY_L1') & (_local_ads_df['dt'] == latest)]
        cats = cats.sort_values('price_index', ascending=False)
        return [{
            'id': row['target_id'],
            'name': row['target_name'],
            'price_index': float(row['price_index']),
            'mom_change': float(row['mom_change_rate']) if pd.notna(row['mom_change_rate']) else 0.0,
        } for _, row in cats.iterrows()]


def get_category_trend(category_id: str, days: int = 30) -> Dict[str, Any]:
    """获取类目趋势数据"""
    if _use_clickhouse:
        from scripts.ch_queries import get_category_trend as ck_trend
        return ck_trend(category_id, days)
    else:
        cat_data = _local_ads_df[(_local_ads_df['index_type'] == 'CATEGORY_L1') &
                                  (_local_ads_df['target_id'] == category_id)].sort_values('dt')
        if len(cat_data) == 0:
            cat_data = _local_ads_df[(_local_ads_df['index_type'] == 'CATEGORY_L1') &
                                      (_local_ads_df['target_name'] == category_id)].sort_values('dt')
        if len(cat_data) == 0:
            return {'dates': [], 'price_index': [], 'mom_change': []}

        dates = sorted(cat_data['dt'].unique())
        if len(dates) > days:
            dates = dates[-days:]
        cat_data = cat_data[cat_data['dt'].isin(dates)]

        return {
            'dates': list(dates),
            'category_name': cat_data['target_name'].iloc[0] if len(cat_data) > 0 else '',
            'price_index': cat_data['price_index'].tolist(),
            'mom_change': cat_data['mom_change_rate'].fillna(0).tolist(),
        }


def get_category_skus(category_id: str) -> List[Dict[str, Any]]:
    """获取类目内SKU涨跌幅"""
    if _use_clickhouse:
        from scripts.ch_queries import get_category_skus as ck_skus
        return ck_skus(category_id)
    else:
        latest = get_latest_date()
        skus = _local_ads_df[(_local_ads_df['index_type'] == 'SKU') &
                             (_local_ads_df['dt'] == latest) &
                             (_local_ads_df['category_id_l1'] == category_id)]
        if len(skus) == 0:
            skus = _local_ads_df[(_local_ads_df['index_type'] == 'SKU') &
                                  (_local_ads_df['dt'] == latest) &
                                  (_local_ads_df['category_l1'] == category_id)]
        if len(skus) == 0:
            skus = _local_ads_df[(_local_ads_df['index_type'] == 'SKU') &
                                  (_local_ads_df['dt'] == latest) &
                                  (_local_ads_df['category_name'] == category_id)]

        skus['mom_change_rate'] = skus['mom_change_rate'].fillna(0)
        top_gain = skus.sort_values('mom_change_rate', ascending=False).head(10)
        top_loss = skus.sort_values('mom_change_rate', ascending=True).head(10)
        result = pd.concat([top_gain, top_loss]).drop_duplicates(subset=['target_id'])

        return [{
            'id': row['target_id'],
            'name': row['target_name'],
            'price_index': float(row['price_index']),
            'mom_change': float(row['mom_change_rate']),
            'price': float(row['price']),
            'base_price': float(row['base_price']),
        } for _, row in result.iterrows()]


def get_categories_trend(days: int = 365) -> Dict[str, Any]:
    """获取所有一级类目趋势"""
    if _use_clickhouse:
        from scripts.ch_queries import get_categories_trend as ck_all_trend
        return ck_all_trend(days)
    else:
        cat_data = _local_ads_df[_local_ads_df['index_type'] == 'CATEGORY_L1'].copy()
        dates = sorted(cat_data['dt'].unique())
        if len(dates) > days:
            dates = dates[-days:]
        cat_data = cat_data[cat_data['dt'].isin(dates)]

        categories = sorted(cat_data['target_name'].unique())
        result = {'dates': list(dates), 'categories': []}

        for cat in categories:
            cat_row = cat_data[cat_data['target_name'] == cat].sort_values('dt')
            result['categories'].append({
                'name': cat,
                'price_index': cat_row['price_index'].tolist(),
                'mom_change': cat_row['mom_change_rate'].fillna(0).tolist(),
            })

        return result


def get_sku_trend(sku_id: str, days: int = 30) -> Dict[str, Any]:
    """获取SKU趋势数据"""
    if _use_clickhouse:
        from scripts.ch_queries import get_sku_trend as ck_sku_trend
        return ck_sku_trend(sku_id, days)
    else:
        sku_data = _local_ads_df[(_local_ads_df['index_type'] == 'SKU') &
                                 (_local_ads_df['target_id'] == sku_id)].sort_values('dt')
        if len(sku_data) == 0:
            return {}

        dates = sorted(sku_data['dt'].unique())
        if len(dates) > days:
            dates = dates[-days:]
        sku_data = sku_data[sku_data['dt'].isin(dates)]

        return {
            'dates': sku_data['dt'].tolist(),
            'sku_name': sku_data['target_name'].iloc[0],
            'prices': sku_data['price'].tolist(),
            'indexes': sku_data['price_index'].tolist(),
            'current_price': float(sku_data['price'].iloc[-1]),
            'base_price': float(sku_data['base_price'].iloc[0]),
            'price_index': float(sku_data['price_index'].iloc[-1]),
        }


def get_sku_search(keyword: str) -> List[Dict[str, Any]]:
    """搜索SKU"""
    if _use_clickhouse:
        from scripts.ch_queries import get_sku_search as ck_search
        return ck_search(keyword)
    else:
        latest = get_latest_date()
        results = _local_ads_df[(_local_ads_df['index_type'] == 'SKU') &
                                 (_local_ads_df['dt'] == latest) &
                                 (_local_ads_df['target_name'].str.contains(keyword, na=False))]
        results = results.drop_duplicates(subset=['target_id']).head(50)

        return [{
            'id': row['target_id'],
            'name': row['target_name'],
            'category_l1': row['category_l1'],
            'category': row['category_name'],
            'price_index': float(row['price_index']),
        } for _, row in results.iterrows()]


def get_anomaly(date: str = None, anomaly_type: str = None,
                page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """获取异常数据"""
    if _use_clickhouse:
        from scripts.ch_queries import get_anomaly as ck_anomaly
        return ck_anomaly(date, anomaly_type, page, page_size)
    else:
        df = _local_anomaly_df.copy() if len(_local_anomaly_df) > 0 else pd.DataFrame()
        if df.empty:
            return {'total': 0, 'list': [], 'stats': {}}

        if date:
            df = df[df['dt'] == date]
        if anomaly_type:
            df = df[df['anomaly_type'] == anomaly_type]

        total = len(df)
        stats = {'total': total}
        if len(df) > 0:
            type_counts = df['anomaly_type'].value_counts()
            for t, c in type_counts.items():
                stats[t] = int(c)

        start = (page - 1) * page_size
        df = df.iloc[start:start + page_size]

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'list': df.fillna('').to_dict('records'),
            'stats': stats,
        }


def get_ranking(limit: int = 10) -> Dict[str, Any]:
    """获取涨幅/跌幅排行榜"""
    if _use_clickhouse:
        from scripts.ch_queries import get_ranking as ck_ranking
        return ck_ranking(limit)
    else:
        latest = get_latest_date()
        skus = _local_ads_df[(_local_ads_df['index_type'] == 'SKU') & (_local_ads_df['dt'] == latest)]
        skus['mom_change_rate'] = skus['mom_change_rate'].fillna(0)

        top_gain = skus.nlargest(limit, 'mom_change_rate')
        top_loss = skus.nsmallest(limit, 'mom_change_rate')

        return {
            'gain': [{
                'product_id': row['target_id'],
                'product_name': row['target_name'],
                'category': row['category_l1'],
                'price_index': float(row['price_index']),
                'mom_change': float(row['mom_change_rate']),
                'price': float(row['price']),
            } for _, row in top_gain.iterrows()],
            'loss': [{
                'product_id': row['target_id'],
                'product_name': row['target_name'],
                'category': row['category_l1'],
                'price_index': float(row['price_index']),
                'mom_change': float(row['mom_change_rate']),
                'price': float(row['price']),
            } for _, row in top_loss.iterrows()],
        }


def get_overall_trend(days: int = 30) -> Dict[str, Any]:
    """获取全网指数趋势"""
    if _use_clickhouse:
        from scripts.ch_queries import get_overall_trend as ck_overall_trend
        return ck_overall_trend(days)
    else:
        overall = _local_ads_df[_local_ads_df['index_type'] == 'OVERALL'].sort_values('dt')
        dates = sorted(overall['dt'].unique())
        if len(dates) > days:
            dates = dates[-days:]
        overall = overall[overall['dt'].isin(dates)]
        fisher = _local_ads_df[_local_ads_df['index_type'] == 'FISHER'].sort_values('dt')
        fisher = fisher[fisher['dt'].isin(dates)]

        return {
            'dates': list(dates),
            'overall_index': overall['price_index'].tolist(),
            'overall_mom': overall['mom_change_rate'].fillna(0).tolist(),
            'fisher_index': fisher['price_index'].tolist(),
        }


def get_mom_distribution(days: int = 30) -> List[Dict[str, Any]]:
    """获取日环比分布"""
    if _use_clickhouse:
        from scripts.ch_queries import get_mom_distribution as ck_mom_dist
        return ck_mom_dist(days)
    else:
        latest = get_latest_date()
        skus = _local_ads_df[(_local_ads_df['index_type'] == 'SKU') & (_local_ads_df['dt'] == latest)]
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

        return result


# 获取原始数据引用（仅用于本地模式）
def get_local_dataframes():
    """获取本地DataFrame引用"""
    return _local_ads_df, _local_anomaly_df

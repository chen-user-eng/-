"""
集成测试：验证商品覆盖率和异常过滤准确性

测试场景：
1. 商品覆盖率测试 (>= 80%)
2. 异常过滤准确性测试 (>= 95%)

运行方式：
    python tests/test_integration.py
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# 导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试数据路径
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = []
        self.errors = []

    def record(self, name: str, passed: bool, msg: str = ""):
        if passed:
            self.passed += 1
            print(f"  ✅ {name}")
        else:
            self.failed += 1
            self.errors.append(f"❌ {name}: {msg}")
            print(f"  ❌ {name}: {msg}")

    def warn(self, name: str, msg: str):
        self.warnings.append(f"⚠️ {name}: {msg}")
        print(f"  ⚠️ {name}: {msg}")

    def summary(self):
        print("\n" + "=" * 60)
        print(f"  测试结果: {self.passed} 通过, {self.failed} 失败")
        if self.warnings:
            print("\n警告:")
            for w in self.warnings:
                print(f"  {w}")
        if self.errors:
            print("\n失败详情:")
            for e in self.errors:
                print(f"  {e}")
        print("=" * 60)
        return self.failed == 0


def test_product_coverage():
    """测试商品覆盖率"""
    print("\n========== 测试1: 商品覆盖率 ==========")
    result = TestResult()

    # 加载数据
    products_df = pd.read_csv(os.path.join(TEST_DATA_DIR, 'test_products.csv'))
    index_df = pd.read_csv(os.path.join(TEST_DATA_DIR, 'test_all_index.csv'))

    # 获取有索引数据的商品
    sku_data = index_df[index_df['index_type'] == 'Sku']
    indexed_products = set(sku_data['target_id'].astype(str).unique())
    total_products = set(products_df['product_id'].astype(str).unique())

    # 计算覆盖率
    covered = indexed_products & total_products
    total = len(total_products)
    coverage = len(covered) / total * 100 if total > 0 else 0

    result.record(
        f"商品覆盖率 = {coverage:.1f}% (阈值 >= 80%)",
        coverage >= 80,
        f"覆盖率 {coverage:.1f}% 低于 80%"
    )

    # 详细分析
    result.warn(
        f"总商品数: {total}",
        f"有索引商品数: {len(covered)}"
    )

    # 检查各类目覆盖情况
    products_df['category_id'] = products_df['category_id'].astype(str)
    sku_data['target_id'] = sku_data['target_id'].astype(str)
    indexed_products_str = set(sku_data['target_id'].unique())

    for cat_id in products_df['category_id'].unique():
        cat_products = set(products_df[products_df['category_id'] == cat_id]['product_id'].astype(str).unique())
        cat_indexed = indexed_products_str & cat_products
        cat_coverage = len(cat_indexed) / len(cat_products) * 100 if len(cat_products) > 0 else 0
        result.record(
            f"  类目 {cat_id} 覆盖率: {cat_coverage:.0f}%",
            cat_coverage >= 80,
            f"覆盖率 {cat_coverage:.0f}% 低于 80%"
        )

    return result


def test_anomaly_filter_accuracy():
    """测试异常过滤准确性"""
    print("\n========== 测试2: 异常过滤准确性 ==========")
    result = TestResult()

    # 加载数据
    index_df = pd.read_csv(os.path.join(TEST_DATA_DIR, 'test_all_index.csv'))
    anomaly_df = pd.read_csv(os.path.join(TEST_DATA_DIR, 'test_anomaly_2028-05-15.csv'))

    latest_date = index_df['dt'].max()
    skus = index_df[(index_df['index_type'] == 'Sku') & (index_df['dt'] == latest_date)]

    # 价格突变阈值
    sudden_threshold = 20  # |日环比| > 20% 判定为价格突变

    # 检测到的突变
    detected_sudden = set()
    for _, row in skus.iterrows():
        if abs(row['mom_change_rate']) > sudden_threshold:
            detected_sudden.add(str(row['target_id']))

    # 实际记录的突变 (从异常数据)
    actual_sudden = set(anomaly_df[anomaly_df['anomaly_type'] == '价格突变']['product_id'].astype(str).unique())

    # 计算准确性
    true_positive = len(detected_sudden & actual_sudden)
    false_positive = len(detected_sudden - actual_sudden)
    false_negative = len(actual_sudden - detected_sudden)
    true_negative = len(set(skus['target_id'].astype(str)) - detected_sudden - actual_sudden)

    # 准确率 = (TP + TN) / Total
    total = len(set(skus['target_id'].astype(str)))
    accuracy = (true_positive + true_negative) / total * 100 if total > 0 else 0

    # 精确率 = TP / (TP + FP)
    precision = true_positive / (true_positive + false_positive) * 100 if (true_positive + false_positive) > 0 else 0

    # 召回率 = TP / (TP + FN)
    recall = true_positive / (true_positive + false_negative) * 100 if (true_positive + false_negative) > 0 else 0

    result.record(
        f"异常过滤准确率 = {accuracy:.1f}% (阈值 >= 95%)",
        accuracy >= 95,
        f"准确率 {accuracy:.1f}% 低于 95%"
    )

    result.record(
        f"异常检测精确率 = {precision:.1f}%",
        precision >= 80
    )

    result.record(
        f"异常检测召回率 = {recall:.1f}%",
        recall >= 80
    )

    # 详细分析
    result.warn(f"检测到的突变: {len(detected_sudden)}", str(detected_sudden))
    result.warn(f"实际记录的突变: {len(actual_sudden)}", str(actual_sudden))

    if false_positive > 0:
        result.warn(f"误报 (FP): {false_positive}", str(detected_sudden - actual_sudden))

    if false_negative > 0:
        result.warn(f"漏报 (FN): {false_negative}", str(actual_sudden - detected_sudden))

    return result


def test_data_quality():
    """测试数据质量"""
    print("\n========== 测试3: 数据质量检查 ==========")
    result = TestResult()

    # 检查缺失值
    index_df = pd.read_csv(os.path.join(TEST_DATA_DIR, 'test_all_index.csv'))
    sku_df = index_df[index_df['index_type'] == 'Sku']

    required_fields = ['dt', 'target_id', 'price', 'base_price', 'mom_change_rate']
    for field in required_fields:
        null_count = sku_df[field].isnull().sum()
        null_ratio = null_count / len(sku_df) * 100 if len(sku_df) > 0 else 0
        result.record(
            f"字段 '{field}' 缺失率 = {null_ratio:.1f}% (阈值 < 5%)",
            null_ratio < 5,
            f"缺失率 {null_ratio:.1f}% 超过 5%"
        )

    # 检查价格合理性
    invalid_price = sku_df[sku_df['price'] <= 0].shape[0]
    result.record(
        f"无效价格数量 = {invalid_price} (应为 0)",
        invalid_price == 0
    )

    # 检查日期连续性
    dates = sorted(sku_df['dt'].unique())
    result.record(
        f"数据日期数 = {len(dates)}",
        len(dates) >= 2
    )

    return result


def test_distribution_analysis():
    """测试分布分析"""
    print("\n========== 测试4: 分布分析 ==========")
    result = TestResult()

    index_df = pd.read_csv(os.path.join(TEST_DATA_DIR, 'test_all_index.csv'))
    sku_df = index_df[index_df['index_type'] == 'Sku']

    mom_rates = sku_df['mom_change_rate'].dropna()

    # 统计信息
    mean_change = mom_rates.mean()
    std_change = mom_rates.std()
    median_change = mom_rates.median()
    p25 = mom_rates.quantile(0.25)
    p75 = mom_rates.quantile(0.75)

    result.record(
        f"日环比均值 = {mean_change:.2f}% (合理范围: -20% ~ +20%)",
        -20 <= mean_change <= 20
    )

    result.record(
        f"日环比标准差 = {std_change:.2f}% (合理范围: 0 ~ 50%)",
        0 <= std_change <= 50
    )

    result.warn(
        f"日环比中位数 = {median_change:.2f}%",
        f"Q1={p25:.2f}%, Q3={p75:.2f}%"
    )

    # 检查极端值比例
    extreme_ratio = (abs(mom_rates) > 50).sum() / len(mom_rates) * 100
    result.record(
        f"极端涨跌幅 (>±50%) 比例 = {extreme_ratio:.1f}% (合理范围: < 20%)",
        extreme_ratio < 20
    )

    return result


def test_api_integration():
    """测试API集成"""
    print("\n========== 测试5: API集成测试 ==========")
    result = TestResult()

    run_api_test = os.environ.get('RUN_API_TEST', 'false').lower() == 'true'

    if not run_api_test:
        result.warn("跳过API测试", "设置RUN_API_TEST=true启用")
        result.record("API集成测试（已跳过）", True)
        return result

    try:
        import requests

        base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')

        try:
            resp = requests.get(f"{base_url}/api/overview", timeout=5)
            result.record(
                f"概览接口状态码 = {resp.status_code}",
                resp.status_code == 200
            )
            if resp.status_code == 200:
                data = resp.json()
                result.record(
                    f"概览接口返回必要字段",
                    all(k in data for k in ['date', 'category_count', 'fisher_index'])
                )
        except Exception as e:
            result.record("概览接口可访问", False, str(e))

        try:
            resp = requests.get(f"{base_url}/api/anomaly?page=1&page_size=5", timeout=5)
            result.record(
                f"异常接口状态码 = {resp.status_code}",
                resp.status_code == 200
            )
            if resp.status_code == 200:
                data = resp.json()
                result.record(
                    f"异常接口返回必要字段",
                    all(k in data for k in ['list', 'total', 'stats'])
                )
        except Exception as e:
            result.record("异常接口可访问", False, str(e))

    except ImportError:
        result.warn("requests库未安装", "跳过API测试")
        result.record("API集成测试", True)

    return result


def run_all_tests():
    """运行所有集成测试"""
    print("=" * 60)
    print("  集成测试：覆盖率与异常过滤准确性验证")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = [
        test_product_coverage(),
        test_anomaly_filter_accuracy(),
        test_data_quality(),
        test_distribution_analysis(),
        test_api_integration(),
    ]

    # 汇总结果
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)

    print("\n" + "=" * 60)
    print("  汇总结果")
    print("=" * 60)
    print(f"  通过: {total_passed}")
    print(f"  失败: {total_failed}")
    print(f"  总计: {total_passed + total_failed}")
    print("=" * 60)

    return total_failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

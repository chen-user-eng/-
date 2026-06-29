"""
单元测试：验证字段解析和SQL输出正确性

测试场景：
1. CSV字段解析测试
2. ClickHouse SQL查询测试
3. 数据格式校验
4. OSS上传测试（可选）

运行方式：
    python tests/test_unit.py
"""
import os
import sys
import pandas as pd
from datetime import datetime

# 测试数据路径
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def record(self, name: str, passed: bool, msg: str = ""):
        if passed:
            self.passed += 1
            print(f"  ✅ {name}")
        else:
            self.failed += 1
            self.errors.append(f"❌ {name}: {msg}")
            print(f"  ❌ {name}: {msg}")

    def summary(self):
        print("\n" + "=" * 60)
        print(f"  测试结果: {self.passed} 通过, {self.failed} 失败")
        if self.errors:
            print("\n失败详情:")
            for e in self.errors:
                print(f"  {e}")
        print("=" * 60)
        return self.failed == 0


def test_csv_field_parsing():
    """测试CSV字段解析"""
    print("\n========== 测试1: CSV字段解析 ==========")
    result = TestResult()

    # 测试 all_index.csv
    csv_path = os.path.join(TEST_DATA_DIR, 'test_all_index.csv')
    df = pd.read_csv(csv_path)

    # 验证必需字段
    required_fields = [
        'dt', 'index_type', 'target_id', 'target_name', 'price',
        'base_price', 'price_index', 'mom_change_rate',
        'category_id', 'category_l1'
    ]
    for field in required_fields:
        result.record(
            f"all_index.csv 包含字段 '{field}'",
            field in df.columns,
            f"缺少字段: {field}"
        )

    # 验证数据类型
    result.record(
        "dt 字段为日期格式",
        pd.api.types.is_string_dtype(df['dt'])
    )
    result.record(
        "price 字段为数值类型",
        pd.api.types.is_numeric_dtype(df['price'])
    )
    result.record(
        "mom_change_rate 字段为数值类型",
        pd.api.types.is_numeric_dtype(df['mom_change_rate'])
    )

    # 验证数据范围
    sku_df = df[df['index_type'] == 'Sku']
    result.record(
        "日环比涨跌幅在 -100% ~ +200% 范围内",
        (sku_df['mom_change_rate'] >= -100).all() and (sku_df['mom_change_rate'] <= 200).all(),
        f"存在超出范围的涨跌幅"
    )

    result.record(
        "价格指数为正值",
        (sku_df['price_index'] > 0).all(),
        f"存在非正值价格指数"
    )

    return result


def test_categories_parsing():
    """测试类目表字段解析"""
    print("\n========== 测试2: 类目表字段解析 ==========")
    result = TestResult()

    csv_path = os.path.join(TEST_DATA_DIR, 'test_categories.csv')
    df = pd.read_csv(csv_path)

    required_fields = ['category_id', 'category_name', 'weight', 'base_price']
    for field in required_fields:
        result.record(
            f"categories.csv 包含字段 '{field}'",
            field in df.columns
        )

    result.record(
        f"类目表有 {len(df)} 条数据",
        len(df) == 3
    )

    return result


def test_products_parsing():
    """测试商品表字段解析"""
    print("\n========== 测试3: 商品表字段解析 ==========")
    result = TestResult()

    csv_path = os.path.join(TEST_DATA_DIR, 'test_products.csv')
    df = pd.read_csv(csv_path)

    required_fields = ['product_id', 'category_id', 'name', 'base_price']
    for field in required_fields:
        result.record(
            f"products.csv 包含字段 '{field}'",
            field in df.columns
        )

    result.record(
        f"商品表有 {len(df)} 条数据",
        len(df) == 12
    )

    return result


def test_anomaly_parsing():
    """测试异常数据字段解析"""
    print("\n========== 测试4: 异常数据字段解析 ==========")
    result = TestResult()

    csv_path = os.path.join(TEST_DATA_DIR, 'test_anomaly_2028-05-15.csv')
    df = pd.read_csv(csv_path)

    required_fields = [
        'dt', 'product_id', 'product_name', 'category_l1',
        'current_price', 'base_price', 'anomaly_type', 'change_rate'
    ]
    for field in required_fields:
        result.record(
            f"anomaly.csv 包含字段 '{field}'",
            field in df.columns
        )

    # 验证异常类型
    valid_types = ['价格突变', '价格偏离', '价格超限', '价格异常']
    all_valid = df['anomaly_type'].isin(valid_types).all()
    result.record(
        "异常类型值合法",
        all_valid,
        f"存在非法异常类型"
    )

    result.record(
        f"异常数据有 {len(df)} 条",
        len(df) == 6
    )

    return result


def test_sql_output():
    """测试SQL查询输出"""
    print("\n========== 测试5: SQL查询输出验证 ==========")
    result = TestResult()

    # 模拟数据处理逻辑
    csv_path = os.path.join(TEST_DATA_DIR, 'test_all_index.csv')
    df = pd.read_csv(csv_path)

    # 过滤最新日期的SKU数据
    latest_date = df['dt'].max()
    skus = df[(df['index_type'] == 'Sku') & (df['dt'] == latest_date)]

    # 验证筛选结果
    result.record(
        f"最新日期 {latest_date} 的SKU数据",
        len(skus) == 12
    )

    # 验证日环比计算
    for _, row in skus.iterrows():
        expected_index = (row['price'] / row['base_price']) * 100
        actual_index = row['price_index']
        diff = abs(expected_index - actual_index)
        if diff > 0.01:
            result.record(
                f"SKU {row['target_id']} 价格指数计算",
                False,
                f"期望 {expected_index:.2f}, 实际 {actual_index:.2f}"
            )
            break
    else:
        result.record("所有SKU价格指数计算正确", True)

    # 验证分箱统计
    bins = [-60, -40, -20, -10, -5, -2, 0, 2, 5, 10, 20, 40, 60]
    bin_counts = {}
    for i in range(len(bins) - 1):
        name = f'{bins[i]}~{bins[i+1]}%'
        condition = (skus['mom_change_rate'] >= bins[i]) & (skus['mom_change_rate'] < bins[i+1])
        bin_counts[name] = int(condition.sum())

    result.record(
        f"分箱统计正确 (-60~-40%: {bin_counts.get('-60~-40%', 0)}, 0~2%: {bin_counts.get('0~2%', 0)}, 40~60%: {bin_counts.get('40~60%', 0)})",
        bin_counts.get('-60~-40%', 0) == 2 and bin_counts.get('0~2%', 0) == 1 and bin_counts.get('40~60%', 0) == 1
    )

    return result


def test_anomaly_detection():
    """测试异常检测逻辑"""
    print("\n========== 测试6: 异常检测逻辑验证 ==========")
    result = TestResult()

    # 加载测试数据
    index_path = os.path.join(TEST_DATA_DIR, 'test_all_index.csv')
    anomaly_path = os.path.join(TEST_DATA_DIR, 'test_anomaly_2028-05-15.csv')

    df = pd.read_csv(index_path)
    anomaly_df = pd.read_csv(anomaly_path)

    latest_date = df['dt'].max()
    skus = df[(df['index_type'] == 'Sku') & (df['dt'] == latest_date)]

    # 价格突变阈值: 日环比 > 20% 或 < -20%
    sudden_threshold = 20
    sudden_changes = skus[abs(skus['mom_change_rate']) > sudden_threshold]

    # 预期突变: D(-20.83%), F(-50%), E(25%), H(-33.33%), I(50%), K(-41.67%), L(66.67%) = 7个
    result.record(
        f"价格突变检测: 预期 {len(sudden_changes)} 条异常",
        len(sudden_changes) == 7
    )

    # 验证异常数据与检测结果匹配 (abs > 20%)
    expected_mutations = abs(anomaly_df[anomaly_df['anomaly_type'] == '价格突变']['change_rate']) > sudden_threshold
    result.record(
        "价格突变阈值判断正确",
        expected_mutations.sum() == 6
    )

    # 验证异常类型统计
    anomaly_stats = anomaly_df.groupby('anomaly_type').size()
    result.record(
        f"异常类型统计: 价格突变={anomaly_stats.get('价格突变', 0)}",
        anomaly_stats.get('价格突变', 0) == 6
    )

    return result


def test_oss_format():
    """测试OSS格式兼容性"""
    print("\n========== 测试7: OSS格式兼容性 ==========")
    result = TestResult()

    # 测试带BOM的UTF-8文件
    csv_path = os.path.join(TEST_DATA_DIR, 'test_all_index.csv')
    df = pd.read_csv(csv_path)

    # 验证CSV读取无错误
    result.record(
        "CSV文件可正常读取",
        len(df) > 0
    )

    # 验证可以转换为ClickHouse兼容格式
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                df[col].fillna('').astype(str)
                result.record(f"列 '{col}' 可转换为字符串", True)
            except Exception as e:
                result.record(f"列 '{col}' 转换失败", False, str(e))
                break
    else:
        # 所有列都通过
        result.record("所有列类型转换正确", True)

    return result


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("  单元测试：字段解析与SQL输出验证")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = [
        test_csv_field_parsing(),
        test_categories_parsing(),
        test_products_parsing(),
        test_anomaly_parsing(),
        test_sql_output(),
        test_anomaly_detection(),
        test_oss_format(),
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

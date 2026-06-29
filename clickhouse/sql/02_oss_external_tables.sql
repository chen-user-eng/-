-- ============================================================
-- OSS外部表配置与数据加载
-- ============================================================

-- ============================================================
-- 方式一：使用 S3 引擎直接查询 OSS（推荐用于一次性查询）
-- ============================================================

-- 直接查询OSS上的CSV文件（以某一天为例）
SELECT count(*) AS total
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/ods/dt=2028-05-15/daily_prices.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV',
    'product_id UInt64, category_id UInt64, name String, price Float64, change_date Date'
)
SETTINGS input_format_csv_skip_first_lines = 1;

-- 查看样例数据
SELECT *
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/ods/dt=2028-05-15/daily_prices.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV',
    'product_id UInt64, category_id UInt64, name String, price Float64, change_date Date'
)
SETTINGS input_format_csv_skip_first_lines = 1
LIMIT 10;

-- ============================================================
-- 方式二：创建 S3 外部表（推荐用于频繁查询）
-- ============================================================

-- 创建OSS外部表（单文件）
CREATE TABLE IF NOT EXISTS oss_daily_prices_20280515
(
    product_id      UInt64,
    category_id     UInt64,
    name            String,
    price           Float64,
    change_date     Date
)
ENGINE = S3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/ods/dt=2028-05-15/daily_prices.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV'
)
SETTINGS
    input_format_csv_skip_first_lines = 1,
    format_csv_allow_single_quotes = 0;

-- 查询外部表
SELECT count(*) FROM oss_daily_prices_20280515;

-- ============================================================
-- 方式三：使用通配符查询多个文件（推荐用于批量处理）
-- ============================================================

-- 使用通配符查询多天数据（OSS支持路径通配符）
SELECT
    change_date,
    count(*) AS product_count,
    round(avg(price), 2) AS avg_price
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/ods/dt=*/daily_prices.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV',
    'product_id UInt64, category_id UInt64, name String, price Float64, change_date Date'
)
SETTINGS input_format_csv_skip_first_lines = 1
GROUP BY change_date
ORDER BY change_date;

-- ============================================================
-- 数据加载：从OSS导入到ClickHouse本地表
-- ============================================================

-- 1. 加载维度表 - 商品维度
INSERT INTO dim_products
SELECT
    product_id,
    name AS product_name,
    category_id,
    price AS base_price,
    weight,
    change_count,
    now() AS create_time,
    now() AS update_time
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/dim/products.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV',
    'product_id UInt64, category_id UInt64, name String, weight Float64, price Float64, change_count UInt32'
)
SETTINGS input_format_csv_skip_first_lines = 1;

-- 验证商品维度表
SELECT count() AS product_count FROM dim_products;

-- 2. 加载维度表 - 类目维度
INSERT INTO dim_categories
SELECT
    category_id,
    category AS category_name,
    hierarchy,
    weight,
    price AS base_price,
    if(parent = '', 0, toUInt64(parent)) AS parent_id,
    now() AS create_time
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/dim/categories.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV',
    'category String, category_id UInt64, hierarchy UInt8, weight Float64, price Float64, parent String'
)
SETTINGS input_format_csv_skip_first_lines = 1;

-- 验证类目维度表
SELECT
    hierarchy,
    count() AS category_count
FROM dim_categories
GROUP BY hierarchy
ORDER BY hierarchy;

-- 3. 加载ODS数据 - 单日数据
INSERT INTO ods_product_price
SELECT
    product_id,
    category_id,
    name AS product_name,
    price,
    change_date AS dt
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/ods/dt=2028-05-15/daily_prices.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV',
    'product_id UInt64, category_id UInt64, name String, price Float64, change_date Date'
)
SETTINGS input_format_csv_skip_first_lines = 1;

-- 4. 批量加载多天数据（使用通配符）
INSERT INTO ods_product_price
SELECT
    product_id,
    category_id,
    name AS product_name,
    price,
    change_date AS dt
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/ods/dt=*/daily_prices.csv',
    '$OSS_ACCESS_KEY_ID',
    '$OSS_ACCESS_KEY_SECRET',
    'CSV',
    'product_id UInt64, category_id UInt64, name String, price Float64, change_date Date'
)
SETTINGS
    input_format_csv_skip_first_lines = 1,
    max_insert_block_size = 1000000,
    insert_quorum = 0;

-- 验证ODS数据
SELECT
    dt,
    count() AS product_count,
    round(avg(price), 2) AS avg_price
FROM ods_product_price
GROUP BY dt
ORDER BY dt;

-- ============================================================
-- 查询性能优化建议
-- ============================================================

-- 1. 查看表大小
SELECT
    table,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows
FROM system.parts
WHERE active
GROUP BY table
ORDER BY sum(bytes) DESC;

-- 2. 查看分区信息
SELECT
    table,
    partition,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows
FROM system.parts
WHERE active AND table = 'ods_product_price'
GROUP BY table, partition
ORDER BY partition;

-- 3. 强制合并分区（优化查询性能）
OPTIMIZE TABLE ods_product_price PARTITION '202805' FINAL;

-- ============================================================
-- 高频电商价格指数计算平台 - ClickHouse 表结构设计
-- 数据仓库分层：ODS -> DWD -> DWS -> ADS
-- ============================================================

-- ============================================================
-- 一、维度表 DIM 层
-- ============================================================

-- 1. 商品维度表
CREATE TABLE IF NOT EXISTS dim_products
(
    product_id      UInt64      COMMENT '商品ID',
    product_name    String      COMMENT '商品名称',
    category_id     UInt64      COMMENT '三级类目ID',
    base_price      Float64     COMMENT '基期价格',
    weight          Float64     COMMENT '权重',
    change_count    UInt32      DEFAULT 0 COMMENT '价格变动次数',
    create_time     DateTime    DEFAULT now() COMMENT '创建时间',
    update_time     DateTime    DEFAULT now() COMMENT '更新时间'
)
ENGINE = ReplacingMergeTree(update_time)
ORDER BY (product_id, category_id)
COMMENT '商品维度表';

-- 2. 类目维度表
CREATE TABLE IF NOT EXISTS dim_categories
(
    category_id     UInt64      COMMENT '类目ID',
    category_name   String      COMMENT '类目名称',
    hierarchy       UInt8       COMMENT '层级：1-一级，2-二级，3-三级',
    weight          Float64     COMMENT '权重',
    base_price      Float64     DEFAULT 0 COMMENT '基准价格',
    parent_id       UInt64      DEFAULT 0 COMMENT '父类目ID',
    create_time     DateTime    DEFAULT now() COMMENT '创建时间'
)
ENGINE = ReplacingMergeTree(create_time)
ORDER BY (category_id, hierarchy)
COMMENT '类目维度表';

-- ============================================================
-- 二、ODS 层 - 原始数据层（OSS外部表）
-- ============================================================

-- OSS外部表 - 每日商品价格（直接读取OSS上的CSV文件，无需导入）
CREATE TABLE IF NOT EXISTS ods_product_price_external
(
    product_id      UInt64      COMMENT '商品ID',
    category_id     UInt64      COMMENT '类目ID',
    name            String      COMMENT '商品名称',
    price           Float64     COMMENT '价格',
    change_date     Date        COMMENT '价格日期'
)
ENGINE = S3('https://oss-cn-hangzhou.aliyuncs.com/dashujujishu/data/ods/dt={date}/daily_prices.csv',
            '$OSS_ACCESS_KEY_ID',
            '$OSS_ACCESS_KEY_SECRET',
            'CSV',
            'product_id UInt64, category_id UInt64, name String, price Float64, change_date Date')
SETTINGS
    format_csv_allow_single_quotes = 0,
    input_format_csv_skip_first_lines = 1,
    s3_truncate_on_insert = 0
COMMENT 'OSS外部表 - 每日商品价格';

-- ODS本地表 - 导入后的明细表（按日期分区）
CREATE TABLE IF NOT EXISTS ods_product_price
(
    product_id      UInt64      COMMENT '商品ID',
    category_id     UInt64      COMMENT '类目ID',
    product_name    String      COMMENT '商品名称',
    price           Float64     COMMENT '价格',
    dt              Date        COMMENT '数据日期'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(dt)
ORDER BY (dt, category_id, product_id)
TTL dt + INTERVAL 1 YEAR
SETTINGS index_granularity = 8192
COMMENT 'ODS层 - 商品价格明细表';

-- ============================================================
-- 三、DWD 层 - 明细数据层
-- ============================================================

-- DWD商品价格明细表（清洗后）
CREATE TABLE IF NOT EXISTS dwd_product_price_detail
(
    product_id      UInt64      COMMENT '商品ID',
    product_name    String      COMMENT '商品名称',
    category_id     UInt64      COMMENT '三级类目ID',
    category_name   String      COMMENT '三级类目名称',
    category_l1_id  UInt64      COMMENT '一级类目ID',
    category_l1     String      COMMENT '一级类目名称',
    category_l2_id  UInt64      COMMENT '二级类目ID',
    category_l2     String      COMMENT '二级类目名称',
    price           Float64     COMMENT '当前价格',
    base_price      Float64     COMMENT '基期价格',
    weight          Float64     COMMENT '商品权重',
    dt              Date        COMMENT '数据日期'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(dt)
ORDER BY (dt, category_l1_id, category_id, product_id)
SETTINGS index_granularity = 8192
COMMENT 'DWD层 - 商品价格明细（清洗关联后）';

-- 异常数据表
CREATE TABLE IF NOT EXISTS dwd_anomaly_data
(
    product_id      UInt64      COMMENT '商品ID',
    category_id     UInt64      COMMENT '类目ID',
    price           Float64     COMMENT '价格',
    anomaly_type    String      COMMENT '异常类型',
    dt              Date        COMMENT '数据日期',
    create_time     DateTime    DEFAULT now() COMMENT '创建时间'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(dt)
ORDER BY (dt, anomaly_type, product_id)
COMMENT 'DWD层 - 异常数据表';

-- ============================================================
-- 四、DWS 层 - 汇总数据层
-- ============================================================

-- SKU日度价格指数表
CREATE TABLE IF NOT EXISTS dws_sku_price_index_daily
(
    product_id      UInt64      COMMENT '商品ID',
    product_name    String      COMMENT '商品名称',
    category_id     UInt64      COMMENT '三级类目ID',
    category_name   String      COMMENT '三级类目名称',
    category_l1     String      COMMENT '一级类目名称',
    base_date       Date        COMMENT '基期日期',
    price           Float64     COMMENT '当前价格',
    base_price      Float64     COMMENT '基期价格',
    price_index     Float64     COMMENT '价格指数（基期=100）',
    index_weight    Float64     COMMENT '指数权重',
    mom_change_rate Float64     COMMENT '日环比变化率(%)',
    dt              Date        COMMENT '数据日期',
    create_time     DateTime    DEFAULT now() COMMENT '创建时间'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(dt)
ORDER BY (dt, category_l1, category_id, product_id)
SETTINGS index_granularity = 8192
COMMENT 'DWS层 - SKU日度价格指数';

-- 类目日度价格指数表
CREATE TABLE IF NOT EXISTS dws_category_price_index_daily
(
    category_id     UInt64      COMMENT '类目ID',
    category_name   String      COMMENT '类目名称',
    category_l1     String      COMMENT '一级类目名称',
    category_level  UInt8       COMMENT '类目层级',
    base_date       Date        COMMENT '基期日期',
    price_index     Float64     COMMENT '价格指数（基期=100）',
    product_count   UInt32      COMMENT '商品数量',
    index_weight    Float64     COMMENT '类目权重',
    mom_change_rate Float64     COMMENT '日环比变化率(%)',
    dt              Date        COMMENT '数据日期',
    create_time     DateTime    DEFAULT now() COMMENT '创建时间'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(dt)
ORDER BY (dt, category_level, category_id)
SETTINGS index_granularity = 8192
COMMENT 'DWS层 - 类目日度价格指数';

-- ============================================================
-- 五、ADS 层 - 应用数据层
-- ============================================================

-- 全网价格指数表
CREATE TABLE IF NOT EXISTS ads_overall_price_index
(
    index_type      String      COMMENT '指数类型：OVERALL-加权指数, FISHER-费雪指数',
    index_name      String      COMMENT '指数名称',
    base_date       Date        COMMENT '基期日期',
    price_index     Float64     COMMENT '价格指数',
    mom_change_rate Float64     COMMENT '日环比变化率(%)',
    dt              Date        COMMENT '数据日期',
    create_time     DateTime    DEFAULT now() COMMENT '创建时间'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(dt)
ORDER BY (dt, index_type)
COMMENT 'ADS层 - 全网价格指数';

-- 日报表
CREATE TABLE IF NOT EXISTS ads_daily_report
(
    dt                      Date        COMMENT '报表日期',
    overall_index           Float64     COMMENT '全网加权指数',
    overall_mom_change      Float64     COMMENT '全网日环比(%)',
    fisher_index            Float64     COMMENT '费雪指数',
    product_count           UInt32      COMMENT '商品总数',
    category_count          UInt32      COMMENT '类目总数',
    anomaly_count           UInt32      COMMENT '异常数据数',
    top_gain_categories     String      COMMENT '涨幅TOP5类目(JSON)',
    top_loss_categories     String      COMMENT '跌幅TOP5类目(JSON)',
    top_volatile_skus       String      COMMENT '波动TOP10 SKU(JSON)',
    generate_time           DateTime    DEFAULT now() COMMENT '生成时间'
)
ENGINE = ReplacingMergeTree(generate_time)
ORDER BY dt
COMMENT 'ADS层 - 每日报表';

-- ============================================================
-- 六、物化视图（加速常用查询）
-- ============================================================

-- 一级类目指数物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_category_l1_index
TO dws_category_price_index_daily
AS
SELECT
    category_id,
    category_name,
    category_l1,
    1 AS category_level,
    base_date,
    price_index,
    product_count,
    index_weight,
    mom_change_rate,
    dt,
    create_time
FROM dws_category_price_index_daily
WHERE category_level = 1;

-- ============================================================
-- 七、字典表（维度数据加速）
-- ============================================================

-- 类目字典（供函数使用）
CREATE DICTIONARY IF NOT EXISTS dict_category
(
    category_id UInt64,
    category_name String,
    hierarchy UInt8,
    parent_id UInt64,
    weight Float64
)
PRIMARY KEY category_id
SOURCE(CLICKHOUSE(TABLE 'dim_categories'))
LIFETIME(3600)
LAYOUT(FLAT())
COMMENT '类目字典';

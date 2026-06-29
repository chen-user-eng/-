-- ============================================================
-- 价格指数计算 SQL
-- 包括：SKU指数、类目指数、全网指数、费雪指数
-- ============================================================

-- ============================================================
-- 第一步：构建DWD层数据（关联维度表，清洗数据）
-- ============================================================

-- 清洗并关联维度数据，生成DWD明细表
INSERT INTO dwd_product_price_detail
WITH
    -- 二级类目映射
    cat_l2 AS (
        SELECT
            category_id,
            category_name,
            parent_id,
            weight
        FROM dim_categories
        WHERE hierarchy = 2
    ),
    -- 一级类目映射
    cat_l1 AS (
        SELECT
            category_id,
            category_name,
            weight AS l1_weight
        FROM dim_categories
        WHERE hierarchy = 1
    )
SELECT
    p.product_id,
    p.product_name,
    o.category_id,
    c2.category_name,
    c1.category_id AS category_l1_id,
    c1.category_name AS category_l1,
    c2.category_id AS category_l2_id,
    c2.category_name AS category_l2,
    o.price,
    p.base_price,
    p.weight,
    o.dt
FROM ods_product_price o
INNER JOIN dim_products p ON o.product_id = p.product_id
LEFT JOIN cat_l2 c2 ON intDiv(o.category_id, 100) * 100 = c2.category_id
LEFT JOIN cat_l1 c1 ON c2.parent_id = c1.category_id
WHERE o.price > 0
  AND p.base_price > 0
  AND c1.category_name IS NOT NULL;

-- 验证DWD数据
SELECT
    dt,
    category_l1,
    count(DISTINCT product_id) AS sku_count,
    round(avg(price), 2) AS avg_price
FROM dwd_product_price_detail
GROUP BY dt, category_l1
ORDER BY dt, category_l1;

-- ============================================================
-- 第二步：计算SKU价格指数
-- ============================================================

-- SKU价格指数 = 当前价格 / 基期价格 * 100
INSERT INTO dws_sku_price_index_daily
SELECT
    product_id,
    product_name,
    category_id,
    category_name,
    category_l1,
    toDate('2025-05-17') AS base_date,
    price,
    base_price,
    round(price / base_price * 100, 4) AS price_index,
    weight AS index_weight,
    0 AS mom_change_rate,
    dt,
    now() AS create_time
FROM dwd_product_price_detail;

-- 计算日环比
ALTER TABLE dws_sku_price_index_daily
UPDATE mom_change_rate = round(
    (price_index - prev_index) / prev_index * 100, 4
)
WHERE 1 = 1
FROM (
    SELECT
        product_id,
        dt,
        price_index,
        lag(price_index) OVER (PARTITION BY product_id ORDER BY dt) AS prev_index
    FROM dws_sku_price_index_daily
) AS t
WHERE dws_sku_price_index_daily.product_id = t.product_id
  AND dws_sku_price_index_daily.dt = t.dt
  AND t.prev_index IS NOT NULL;

-- 验证SKU指数
SELECT
    dt,
    count() AS sku_count,
    round(avg(price_index), 2) AS avg_index,
    round(avg(mom_change_rate), 4) AS avg_mom
FROM dws_sku_price_index_daily
GROUP BY dt
ORDER BY dt;

-- ============================================================
-- 第三步：计算二级类目价格指数（加权平均）
-- ============================================================

INSERT INTO dws_category_price_index_daily
SELECT
    category_id AS category_id,
    category_l2 AS category_name,
    category_l1,
    2 AS category_level,
    toDate('2025-05-17') AS base_date,
    round(sum(price_index * weight) / sum(weight), 4) AS price_index,
    count(DISTINCT product_id) AS product_count,
    max(c2_weight) AS index_weight,
    0 AS mom_change_rate,
    dt,
    now() AS create_time
FROM (
    SELECT
        d.category_id,
        d.category_l2,
        d.category_l1,
        d.product_id,
        d.price_index,
        d.weight,
        c.weight AS c2_weight
    FROM dws_sku_price_index_daily d
    LEFT JOIN dim_categories c
        ON intDiv(d.category_id, 100) * 100 = c.category_id
        AND c.hierarchy = 2
)
GROUP BY dt, category_id, category_l2, category_l1;

-- ============================================================
-- 第四步：计算一级类目价格指数
-- ============================================================

INSERT INTO dws_category_price_index_daily
SELECT
    category_l1_id AS category_id,
    category_l1 AS category_name,
    category_l1,
    1 AS category_level,
    toDate('2025-05-17') AS base_date,
    round(sum(price_index * weight) / sum(weight), 4) AS price_index,
    sum(product_count) AS product_count,
    max(l1_weight) AS index_weight,
    0 AS mom_change_rate,
    dt,
    now() AS create_time
FROM (
    SELECT
        c.parent_id AS category_l1_id,
        c1.category_name AS category_l1,
        d.price_index,
        d.product_count,
        d.index_weight AS weight,
        c1.weight AS l1_weight,
        d.dt
    FROM dws_category_price_index_daily d
    INNER JOIN dim_categories c
        ON d.category_id = c.category_id
        AND c.hierarchy = 2
    INNER JOIN dim_categories c1
        ON c.parent_id = c1.category_id
        AND c1.hierarchy = 1
    WHERE d.category_level = 2
)
GROUP BY dt, category_l1_id, category_l1;

-- 计算类目指数日环比
ALTER TABLE dws_category_price_index_daily
UPDATE mom_change_rate = round(
    (price_index - prev_index) / prev_index * 100, 4
)
WHERE 1 = 1
FROM (
    SELECT
        category_id,
        category_level,
        dt,
        price_index,
        lag(price_index) OVER (PARTITION BY category_id, category_level ORDER BY dt) AS prev_index
    FROM dws_category_price_index_daily
) AS t
WHERE dws_category_price_index_daily.category_id = t.category_id
  AND dws_category_price_index_daily.category_level = t.category_level
  AND dws_category_price_index_daily.dt = t.dt
  AND t.prev_index IS NOT NULL;

-- 验证类目指数
SELECT
    dt,
    category_level,
    count() AS cat_count,
    round(avg(price_index), 2) AS avg_index
FROM dws_category_price_index_daily
GROUP BY dt, category_level
ORDER BY dt, category_level;

-- ============================================================
-- 第五步：计算全网加权价格指数
-- ============================================================

INSERT INTO ads_overall_price_index
SELECT
    'OVERALL' AS index_type,
    '全网价格指数' AS index_name,
    toDate('2025-05-17') AS base_date,
    round(sum(price_index * l1_weight * cat_weight) / sum(l1_weight * cat_weight), 4) AS price_index,
    0 AS mom_change_rate,
    dt,
    now() AS create_time
FROM (
    SELECT
        d.price_index,
        d.index_weight AS cat_weight,
        c1.weight AS l1_weight,
        d.dt
    FROM dws_category_price_index_daily d
    INNER JOIN dim_categories c
        ON d.category_id = c.category_id
        AND c.hierarchy = 2
    INNER JOIN dim_categories c1
        ON c.parent_id = c1.category_id
        AND c1.hierarchy = 1
    WHERE d.category_level = 2
)
GROUP BY dt;

-- ============================================================
-- 第六步：计算费雪指数
-- ============================================================

-- 费雪指数 = sqrt(拉氏指数 * 帕氏指数)
-- 简化版：使用基期权重计算
INSERT INTO ads_overall_price_index
SELECT
    'FISHER' AS index_type,
    '全网费雪指数' AS index_name,
    toDate('2025-05-17') AS base_date,
    round(sqrt(pl * pp) * 100, 4) AS price_index,
    0 AS mom_change_rate,
    dt,
    now() AS create_time
FROM (
    SELECT
        dt,
        sum(weight * price) / sum(weight * base_price) AS pl,
        sum(weight * price) / sum(weight * base_price) AS pp
    FROM dwd_product_price_detail
    GROUP BY dt
);

-- 计算全网指数日环比
ALTER TABLE ads_overall_price_index
UPDATE mom_change_rate = round(
    (price_index - prev_index) / prev_index * 100, 4
)
WHERE 1 = 1
FROM (
    SELECT
        index_type,
        dt,
        price_index,
        lag(price_index) OVER (PARTITION BY index_type ORDER BY dt) AS prev_index
    FROM ads_overall_price_index
) AS t
WHERE ads_overall_price_index.index_type = t.index_type
  AND ads_overall_price_index.dt = t.dt
  AND t.prev_index IS NOT NULL;

-- 验证全网指数
SELECT
    dt,
    index_type,
    price_index,
    mom_change_rate
FROM ads_overall_price_index
ORDER BY index_type, dt;

-- ============================================================
-- 第七步：生成日报
-- ============================================================

INSERT INTO ads_daily_report
WITH
    latest AS (
        SELECT max(dt) AS max_dt FROM ads_overall_price_index
    ),
    overall AS (
        SELECT
            price_index AS overall_index,
            mom_change_rate AS overall_mom_change,
            dt
        FROM ads_overall_price_index
        WHERE index_type = 'OVERALL'
    ),
    fisher AS (
        SELECT
            price_index AS fisher_index,
            dt
        FROM ads_overall_price_index
        WHERE index_type = 'FISHER'
    ),
    top_gain AS (
        SELECT
            dt,
            groupArray(10)(JSONExtractString(json_data, 'name')) AS names,
            arrayStringConcat(groupArray(10)(json_data), ',') AS top_gain_categories
        FROM (
            SELECT
                dt,
                JSONString(category_name) AS json_data
            FROM (
                SELECT
                    dt,
                    category_name,
                    price_index,
                    row_number() OVER (PARTITION BY dt ORDER BY price_index DESC) AS rn
                FROM dws_category_price_index_daily
                WHERE category_level = 1
            )
            WHERE rn <= 5
            ORDER BY dt, rn
        )
        GROUP BY dt
    ),
    sku_count AS (
        SELECT
            dt,
            count(DISTINCT product_id) AS product_count
        FROM dws_sku_price_index_daily
        GROUP BY dt
    ),
    cat_count AS (
        SELECT
            dt,
            count(DISTINCT category_id) AS category_count
        FROM dws_category_price_index_daily
        WHERE category_level = 2
        GROUP BY dt
    )
SELECT
    o.dt,
    o.overall_index,
    o.overall_mom_change,
    f.fisher_index,
    s.product_count,
    c.category_count,
    0 AS anomaly_count,
    tg.top_gain_categories,
    '' AS top_loss_categories,
    '' AS top_volatile_skus,
    now() AS generate_time
FROM overall o
INNER JOIN fisher f ON o.dt = f.dt
INNER JOIN sku_count s ON o.dt = s.dt
INNER JOIN cat_count c ON o.dt = c.dt
LEFT JOIN top_gain tg ON o.dt = tg.dt;

-- 验证日报
SELECT * FROM ads_daily_report ORDER BY dt DESC LIMIT 5;

-- ============================================================
-- 常用查询示例
-- ============================================================

-- 1. 查询最新一天的概览数据
SELECT
    o.price_index AS overall_index,
    o.mom_change_rate AS overall_mom,
    f.price_index AS fisher_index,
    (SELECT count(DISTINCT product_id) FROM dws_sku_price_index_daily WHERE dt = o.dt) AS product_count,
    (SELECT count(DISTINCT category_id) FROM dws_category_price_index_daily WHERE category_level = 1 AND dt = o.dt) AS category_count
FROM ads_overall_price_index o
CROSS JOIN ads_overall_price_index f
WHERE o.index_type = 'OVERALL'
  AND f.index_type = 'FISHER'
  AND o.dt = (SELECT max(dt) FROM ads_overall_price_index)
  AND f.dt = o.dt;

-- 2. 查询近30天全网指数趋势
SELECT
    dt,
    maxIf(price_index, index_type = 'OVERALL') AS overall_index,
    maxIf(price_index, index_type = 'FISHER') AS fisher_index,
    maxIf(mom_change_rate, index_type = 'OVERALL') AS overall_mom
FROM ads_overall_price_index
WHERE dt >= (SELECT max(dt) - 30 FROM ads_overall_price_index)
GROUP BY dt
ORDER BY dt;

-- 3. 查询一级类目指数排名
SELECT
    category_name,
    price_index,
    mom_change_rate
FROM dws_category_price_index_daily
WHERE category_level = 1
  AND dt = (SELECT max(dt) FROM dws_category_price_index_daily)
ORDER BY price_index DESC;

-- 4. 查询涨幅TOP10 SKU
SELECT
    product_name,
    category_l1,
    price_index,
    mom_change_rate
FROM dws_sku_price_index_daily
WHERE dt = (SELECT max(dt) FROM dws_sku_price_index_daily)
  AND mom_change_rate IS NOT NULL
ORDER BY mom_change_rate DESC
LIMIT 10;

-- 5. 查询跌幅TOP10 SKU
SELECT
    product_name,
    category_l1,
    price_index,
    mom_change_rate
FROM dws_sku_price_index_daily
WHERE dt = (SELECT max(dt) FROM dws_sku_price_index_daily)
  AND mom_change_rate IS NOT NULL
ORDER BY mom_change_rate ASC
LIMIT 10;

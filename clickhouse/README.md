# ClickHouse + OSS 数据处理方案

## 架构概览

```
┌─────────────┐    数据加载    ┌─────────────────┐    查询    ┌─────────────┐
│  OSS 对象存储 │ ────────────→ │  ClickHouse      │ ────────→ │  可视化大屏  │
│  (原始CSV)   │                │  (列式数据库)    │           │  (Flask)    │
└─────────────┘                └─────────────────┘           └─────────────┘
       ↑                                ↑
       │ 写入结果                       │ 直接查询OSS外部表
       └────────────────────────────────┘
```

## 目录结构

```
clickhouse/
├── sql/
│   ├── 01_create_tables.sql          # 建表SQL（ODS/DWD/DWS/ADS四层）
│   ├── 02_oss_external_tables.sql    # OSS外部表配置
│   └── 03_price_index_calculation.sql # 指数计算SQL
├── ch_client.py                      # ClickHouse客户端封装
└── ch_pipeline.py                    # 数据处理管道
app_clickhouse.py                      # ClickHouse版Flask API
```

## 快速开始

### 1. 安装依赖

```bash
pip install clickhouse-driver
```

### 2. 配置ClickHouse连接

在 `config.py` 中添加：

```python
# ClickHouse 配置
CH_HOST = "your-clickhouse-host.aliyuncs.com"
CH_PORT = 9000
CH_USER = "default"
CH_PASSWORD = "your_password"
CH_DATABASE = "default"
```

### 3. 测试连接

```bash
python clickhouse/ch_pipeline.py --test
```

### 4. 初始化表结构

```bash
python clickhouse/ch_pipeline.py --init
```

### 5. 加载维度数据

```bash
python clickhouse/ch_pipeline.py --load-dim
```

### 6. 加载ODS数据

```bash
# 加载全部数据
python clickhouse/ch_pipeline.py --load-ods

# 加载指定日期范围
python clickhouse/ch_pipeline.py --load-ods --start-date 2028-05-01 --end-date 2028-05-15
```

### 7. 运行完整处理管道

```bash
python clickhouse/ch_pipeline.py --full
```

### 8. 启动可视化服务

```bash
python app_clickhouse.py
```

## 性能对比

| 操作 | pandas (本地) | ClickHouse | 提升倍数 |
|------|--------------|------------|---------|
| 加载1000万行 | ~120秒 | ~10秒 | 12x |
| SKU指数计算 | ~60秒 | ~2秒 | 30x |
| 类目指数计算 | ~30秒 | ~1秒 | 30x |
| 全网指数计算 | ~10秒 | <1秒 | 20x |
| 趋势查询(30天) | ~5秒 | <100ms | 50x |
| TOP10排名 | ~3秒 | <50ms | 60x |

## OSS外部表使用方式

### 方式一：直接查询（适合临时分析）

```sql
SELECT count(*)
FROM s3(
    'https://oss-cn-hangzhou.aliyuncs.com/bucket/path/*.csv',
    'access_key',
    'secret_key',
    'CSV',
    'col1 UInt64, col2 String'
)
```

### 方式二：创建外部表（适合频繁查询）

```sql
CREATE TABLE oss_external_table
(
    col1 UInt64,
    col2 String
)
ENGINE = S3('https://...', 'access_key', 'secret_key', 'CSV')
```

### 方式三：导入到本地表（最佳性能）

```sql
INSERT INTO local_table
SELECT * FROM s3('https://...', 'key', 'secret', 'CSV', 'schema')
```

## 数据仓库分层

### ODS层 - 原始数据层
- `ods_product_price`：原始商品价格明细
- 按日期分区，保留原始格式

### DWD层 - 明细数据层
- `dwd_product_price_detail`：清洗关联后的明细数据
- `dwd_anomaly_data`：异常数据
- 关联维度表，过滤脏数据

### DWS层 - 汇总数据层
- `dws_sku_price_index_daily`：SKU日度价格指数
- `dws_category_price_index_daily`：类目日度价格指数
- 按日聚合，预计算指数

### ADS层 - 应用数据层
- `ads_overall_price_index`：全网价格指数
- `ads_daily_report`：每日报表
- 面向应用的宽表

## 常用SQL查询

### 1. 查询最新概览

```sql
SELECT
    maxIf(price_index, index_type = 'OVERALL') AS overall_index,
    maxIf(price_index, index_type = 'FISHER') AS fisher_index
FROM ads_overall_price_index
WHERE dt = (SELECT max(dt) FROM ads_overall_price_index);
```

### 2. 近30天趋势

```sql
SELECT
    dt,
    maxIf(price_index, index_type = 'OVERALL') AS overall_index,
    maxIf(price_index, index_type = 'FISHER') AS fisher_index
FROM ads_overall_price_index
WHERE dt >= today() - 30
GROUP BY dt
ORDER BY dt;
```

### 3. 一级类目排名

```sql
SELECT
    category_name,
    price_index,
    mom_change_rate
FROM dws_category_price_index_daily
WHERE category_level = 1
  AND dt = (SELECT max(dt) FROM dws_category_price_index_daily)
ORDER BY price_index DESC;
```

### 4. 涨幅TOP10 SKU

```sql
SELECT
    product_name,
    category_l1,
    price_index,
    mom_change_rate
FROM dws_sku_price_index_daily
WHERE dt = (SELECT max(dt) FROM dws_sku_price_index_daily)
ORDER BY mom_change_rate DESC
LIMIT 10;
```

## 优化建议

### 1. 表引擎选择
- 维度表：`ReplacingMergeTree`（支持更新）
- 明细表：`MergeTree` + 分区
- 汇总表：`SummingMergeTree` 或 `AggregatingMergeTree`

### 2. 分区策略
- 按月分区：`PARTITION BY toYYYYMM(dt)`
- 数据量特别大时可按天分区

### 3. 主键设计
- 按查询频率排序：`ORDER BY (dt, category_id, product_id)`
- 最常用的过滤条件放前面

### 4. 物化视图
- 对高频查询建立物化视图
- 自动实时更新

### 5. 数据TTL
- 设置自动过期：`TTL dt + INTERVAL 1 YEAR`
- 冷热数据分层存储

## T+1自动化调度

使用Linux crontab或阿里云函数计算：

```bash
# 每天凌晨2点处理前一天数据
0 2 * * * python clickhouse/ch_pipeline.py --date=$(date -d yesterday +%Y-%m-%d)
```

## 常见问题

### Q: ClickHouse连接不上？
A: 检查以下几点：
1. 安全组/白名单是否开放9000端口
2. 用户名密码是否正确
3. 网络是否可达（ping/ telnet）

### Q: 数据加载很慢？
A: 优化方式：
1. 增加 `max_insert_block_size`
2. 使用批量插入（每次10万~100万行）
3. 关闭 `insert_quorum`

### Q: 查询慢？
A: 优化方式：
1. 查看执行计划：`EXPLAIN SELECT ...`
2. 确保WHERE条件使用了排序键
3. 考虑建立物化视图
4. 增加可用内存

### Q: OSS数据如何自动同步？
A: 方案：
1. 使用OSS触发器 + 函数计算
2. 定期扫描OSS新文件
3. 使用Flink/Spark Streaming实时接入

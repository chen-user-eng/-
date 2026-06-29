# ClickHouse + OSS 架构使用指南

## 架构概述

```
OSS（数据湖） ────── ETL ──────> ClickHouse（数据仓库） ──> Flask API ──> 前端
   ↓                                              ↑
   ↑                                              |
   └────────── 定期备份/恢复 ──────────────────────┘
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `config.py` | 配置文件，包含ClickHouse和OSS配置 |
| `scripts/clickhouse_utils.py` | ClickHouse客户端封装 |
| `scripts/ch_queries.py` | ClickHouse查询接口 |
| `scripts/data_source.py` | 统一数据查询接口（自动选择数据源） |
| `scripts/import_to_clickhouse.py` | 本地CSV导入ClickHouse |
| `scripts/oss_clickhouse_pipeline.py` | OSS + ClickHouse ETL流水线 |
| `app.py` | Flask服务（本地CSV模式） |
| `app_ch.py` | Flask服务（统一模式，支持自动切换） |

## 快速开始

### 方式1：本地CSV模式（当前默认）

```bash
# 安装依赖
pip install flask pandas oss2

# 启动服务
python app.py
```

### 方式2：ClickHouse + OSS模式

#### 步骤1：安装ClickHouse

```bash
# Windows: 下载并安装ClickHouse
# https://clickhouse.com/download

# 或使用Docker
docker run -d --name clickhouse -p 8123:8123 -p 9000:9000 clickhouse/clickhouse-server
```

#### 步骤2：安装依赖

```bash
pip install flask pandas oss2 clickhouse-connect
```

#### 步骤3：修改配置

编辑 `config.py`:

```python
# ClickHouse配置
CLICKHOUSE_HOST = "localhost"        # 改为你的ClickHouse地址
CLICKHOUSE_PORT = 8123
CLICKHOUSE_DATABASE = "price_index"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = ""             # 如果有密码

# 数据源模式改为clickhouse
DATA_SOURCE = "clickhouse"
```

#### 步骤4：导入数据到ClickHouse

```bash
# 方式A：从本地CSV导入
python scripts/import_to_clickhouse.py

# 方式B：从OSS下载并导入
python scripts/oss_clickhouse_pipeline.py full
```

#### 步骤5：启动服务

```bash
# 使用新版本app
python app_ch.py

# 或修改config.py后使用原app.py
python app.py
```

## 常用命令

### ETL流水线命令

```bash
# 全量同步：OSS → 本地 → ClickHouse
python scripts/oss_clickhouse_pipeline.py full

# 只从OSS下载到本地
python scripts/oss_clickhouse_pipeline.py download

# 只从本地导入ClickHouse
python scripts/oss_clickhouse_pipeline.py ck

# 强制覆盖下载
python scripts/oss_clickhouse_pipeline.py download --force
```

### ClickHouse管理

```bash
# 初始化表结构
python scripts/clickhouse_utils.py

# 查看数据量
python scripts/clickhouse_utils.py
```

## 数据源切换

在 `config.py` 中修改 `DATA_SOURCE`:

```python
# 使用本地CSV（默认，快速）
DATA_SOURCE = "local"

# 使用ClickHouse（适合大数据量）
DATA_SOURCE = "clickhouse"
```

切换后重启Flask服务即可。

## 性能对比

| 指标 | 本地CSV模式 | ClickHouse模式 |
|------|-----------|---------------|
| 启动时间 | ~60秒（加载26M数据） | <1秒（无需预加载） |
| 查询响应 | 毫秒级 | 毫秒~秒级（视查询复杂度） |
| 内存占用 | ~2GB | <100MB |
| 最大数据量 | 受内存限制 | 无限制（分布式） |
| 并发支持 | 低 | 高 |

## 常见问题

### Q: ClickHouse连接失败？

```bash
# 检查ClickHouse是否运行
curl http://localhost:8123

# 检查端口
netstat -an | grep 8123
```

### Q: 数据导入失败？

```bash
# 检查CSV文件是否存在
ls data/ads/all_index.csv

# 检查ClickHouse状态
python scripts/clickhouse_utils.py
```

### Q: 如何查看当前数据源模式？

访问 http://localhost:5000/api/status

```json
{
  "status": "running",
  "data_source": "clickhouse",
  "use_clickhouse": true,
  "latest_date": "2028-05-15",
  "ads_count": 26287457
}
```

## 下一步

1. 搭建ClickHouse服务
2. 导入历史数据
3. 切换到ClickHouse模式
4. 删除本地数据节省空间

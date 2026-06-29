# OSS配置文件
# 复制此文件为 config.py 并填入真实配置

# 阿里云OSS配置
OSS_ACCESS_KEY_ID = "your_access_key_id"
OSS_ACCESS_KEY_SECRET = "your_access_key_secret"
OSS_ENDPOINT = "oss-cn-hangzhou.aliyuncs.com"
OSS_BUCKET = "your-bucket-name"

# OSS中的数据路径配置
OSS_DATA_PREFIX = "ecommerce-price-index/data/"
OSS_ODS_PREFIX = "ecommerce-price-index/data/ods/"
OSS_DIM_PREFIX = "ecommerce-price-index/data/dim/"
OSS_ADS_PREFIX = "ecommerce-price-index/data/ads/"

# 本地数据路径
LOCAL_DATA_DIR = "e:/111/data"

# ============================================================
# ClickHouse 配置
# ============================================================
CH_HOST = "your-clickhouse-host.aliyuncs.com"
CH_PORT = 9000
CH_USER = "default"
CH_PASSWORD = "your_password"
CH_DATABASE = "default"

# 可选：HTTP端口（用于某些工具）
CH_HTTP_PORT = 8123

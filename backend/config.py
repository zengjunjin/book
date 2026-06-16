import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:123456@localhost:3306/book_recommend?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ========== 数据库连接池配置 ==========
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,           # 连接池大小
        'pool_recycle': 3600,       # 连接回收时间（秒）
        'pool_pre_ping': True,      # 连接前检测
        'max_overflow': 20,         # 额外连接数上限
        'pool_timeout': 30,         # 获取连接超时（秒）
    }
    POOL_WARMUP_COUNT = 3           # 启动时预热的连接数
    
    CORS_ORIGINS = [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5000',
        'http://127.0.0.1:5000'
    ]

    # ========== Redis 缓存配置 ==========
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_DECODE_RESPONSES = True
    
    # 缓存 TTL 配置（秒）
    CACHE_TTL_HOT_BOOKS = 3600       # 热门书籍列表（1小时）
    CACHE_TTL_RECOMMEND = 600        # 推荐结果（10分钟）
    CACHE_TTL_USER_PROFILE = 1800    # 用户画像（30分钟）
    CACHE_TTL_SEARCH = 300           # 搜索结果（5分钟）
    
    # ========== Celery 配置 ==========
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 
        'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND',
        'redis://localhost:6379/2')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'Asia/Shanghai'
    CELERY_ENABLE_UTC = False

    # ========== JWT 认证 ==========
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-dev-secret-change-in-production-please'
    JWT_ACCESS_TOKEN_EXPIRES = 3600        # 访问令牌 1 小时
    JWT_REFRESH_TOKEN_EXPIRES = 86400 * 30  # 刷新令牌 30 天
    JWT_TOKEN_LOCATION = ['headers', 'query_string']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    JWT_QUERY_STRING_NAME = 'token'
    JWT_COOKIE_CSRF_PROTECT = False

    # ========== 多级缓存策略 (L1 内存 + L2 Redis) ==========
    CACHE_L1_TTL = 60                        # 进程内 L1：1 分钟（快速）
    CACHE_L2_TTL = 600                       # 共享 L2（Redis）：10 分钟
    CACHE_STAMPED_LOCK_TTL = 30              # 缓存击穿：加锁 stampede lock 30s
    CACHE_JITTER = 0.1                       # TTL 抖动 10%，避免同时失效

    # ========== 推荐服务（独立进程） ==========
    RECOMMEND_SERVICE_HOST = os.environ.get('RECOMMEND_SERVICE_HOST', '127.0.0.1')
    RECOMMEND_SERVICE_PORT = int(os.environ.get('RECOMMEND_SERVICE_PORT', 5001))
    RECOMMEND_SERVICE_TIMEOUT = 2.5          # 2.5s 超时，自动降级为热门
    RECOMMEND_SERVICE_RETRY = 2

    # ========== 搜索服务 ==========
    SEARCH_USE_MEILISEARCH = False           # 默认走 MySQL FULLTEXT 降级；部署时可开
    MEILISEARCH_HOST = os.environ.get('MEILISEARCH_HOST', 'http://127.0.0.1:7700')
    MEILISEARCH_MASTER_KEY = os.environ.get('MEILISEARCH_MASTER_KEY', '')
    MEILISEARCH_INDEX = 'books'
    SEARCH_BM25_K1 = 1.2
    SEARCH_BM25_B = 0.75

    # ========== 向量检索 ==========
    EMBEDDING_ENABLE_FAISS = True            # 如果安装了 faiss，启用 ANN 检索
    EMBEDDING_MODEL = 'paraphrase-multilingual-MiniLM-L12-v2'
    EMBEDDING_TOP_K = 50

    # ========== AI 推理 ==========
    AI_MODEL = 'qwen2.5:1.5b'
    AI_OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
    AI_TIMEOUT = 30.0
    AI_RAG_MAX_DOCS = 5                      # RAG 最多注入 5 本书
    AI_CACHE_TTL = 86400                     # 24h AI 响应缓存

    # ========== 推荐算法权重（两阶段精排） ==========
    RECALL_CF_WEIGHT = 0.55
    RECALL_SVD_WEIGHT = 0.25
    RECALL_SEMANTIC_WEIGHT = 0.10
    RECALL_CONTENT_WEIGHT = 0.10             # 基于内容特征（分类/作者/热度）
    RECALL_N = 200                            # 召回池大小
    RANK_N = 10                               # 精排返回条数
    RANK_DIVERSITY_LAMBDA = 0.3               # 多样性惩罚系数（0-1）
    RANK_NOVELTY_BOOST = 0.15                 # 新颖度探索系数

    # ========== 缓存预热 ==========
    PREWARM_N_TOP_USERS = 20
    PREWARM_ENABLED = True

    # ========== API 优化配置 ==========
    # 请求限流（分级：AI接口更严格）
    RATELIMIT_DEFAULT = "200/minute"
    RATELIMIT_AI = "30/minute"        # AI接口：30次/分钟（更严格）
    RATELIMIT_AUTH = "10/minute"      # 登录/注册：10次/分钟（防爆破）
    RATELIMIT_WRITE = "60/minute"     # 写操作：60次/分钟
    RATELIMIT_STORAGE_URL = "redis://localhost:6379/3"
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True

    # 响应压缩
    COMPRESS_MIMETYPES = ['application/json', 'text/html', 'text/css', 'text/javascript']
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500
    
    # API 版本
    API_VERSION = 'v1'
    API_PREFIX = '/api'

    # 前端静态文件路径（相对 backend/）
    # 生产模式：复制 ../frontend/dist 到 ./static
    STATIC_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'static'
    )
    TEMPLATE_FOLDER = STATIC_FOLDER  # index.html 用作模板

    # ========== 日志配置 ==========
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    LOG_LEVEL = 'INFO'
    LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
    LOG_BACKUP_COUNT = 5


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    LOG_LEVEL = 'WARNING'


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

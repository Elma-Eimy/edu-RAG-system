import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import urllib.parse

# 项目根目录（config.py 位于 core/ 下，向上一级即为根）
_BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Education System API"
    API_V1_STR: str = "/api/v1"
    
    # 安全设置
    # ⚠️  必须在 .env 中配置真实密钥，不得使用默认值！
    # 生成方式：openssl rand -hex 32
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 访问令牌过期时间（8天）
    
    # 数据库配置 (MySQL 异步)
    MYSQL_USER: str = "root"
    # ⚠️  数据库密码必须在 .env 中以 MYSQL_PASSWORD=xxx 方式配置，不得硬编码
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "edu_system"
    MYSQL_PASSWORD: str = ""
    
    # Redis 与 Celery 配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS 允许的来源列表（多个域名用英文逗号分隔）
    # 生产环境中必须设置为前端实际部署的域名，不得使用 * 通配符（因为 credentials=True 时规范禁止）
    # 示例: ALLOWED_ORIGINS=http://localhost:5173,https://yourdomain.com
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # 通用大语言模型服务商配置
    # 使用兼容 OpenAI 接口标准的端点，方便无缝切换大模型
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL_NAME: str = "gpt-4o"
    # 新增：深度思考推理模型名称（如 deepseek-v4-pro）
    LLM_REASONING_MODEL_NAME: str = "deepseek-v4-pro"
    
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_MODEL_NAME: str = "text-embedding-3-small"
    
    # ChromaDB 向量数据库配置
    CHROMADB_PATH: str = "./chroma_db"


    # ── 文件上传配置 ──────────────────────────────────────────────────────────
    # 本地磁盘存储根目录（按 YYYY/MM/{uuid}.pdf 分子目录）
    UPLOAD_DIR: str = "./uploads/textbooks"
    # 单文件上传大小上限（MB），超出返回 413
    MAX_UPLOAD_MB: int = 50

    # ── 对话上下文配置 ────────────────────────────────────────────────────────
    # 每次问答携带的最近 N 轮对话（1 轮 = 1 条 user + 1 条 ai）
    CHAT_HISTORY_WINDOW: int = 5
    # ChromaDB 每次混合检索返回的文本块数量
    RAG_TOP_K: int = 4
    # 重排模式，可选 "none"、"cohere"、"llm"
    RERANK_MODE: str = "llm"  # 默认使用免算力 LLM 模式
    # Cohere API 密钥（使用 cohere 模式时必填）
    COHERE_API_KEY: str = ""
    # 重排前从双路检索召回的候选分块数量
    RERANK_CANDIDATES: int = 12
    # 系统提示词（可通过 .env 覆盖）
    CHAT_SYSTEM_PROMPT: str = (
        "你是一名专业的 AI 教学助手，正在辅导学生学习教材内容。请优先结合【参考资料】中的原文进行精准解答，"
        "并在回答中明确指出依据的页码（例如：根据教材第X页...）。如果参考资料中没有或仅有部分相关内容，"
        "允许你使用自身专业知识库进行补充与拓展回答，但你的回答内容绝对不得与参考资料中已有的事实相冲突或违背。"
        "若完全基于自身知识回答，请在回答中说明。回答请使用 Markdown 格式，结构清晰。"
    )
    # 是否在消息超过阈值时触发历史摘要压缩（节省 Token）
    ENABLE_HISTORY_SUMMARY: bool = False
    # 触发摘要压缩的消息条数阈值（超过此数量时，将旧消息压缩为摘要）
    HISTORY_SUMMARY_THRESHOLD: int = 20

    # 文本语义切片子块字数限制上限，默认值为 200 字
    TEXTBOOK_CHUNK_SIZE: int = 200

    # ── 新增统一配置与行为常量 ──────────────────────────────────────────────────
    FILE_BUFFER_CHUNK_BYTES: int = 1048576  # 异步文件写入每次缓冲大小（1MB）
    CELERY_EMBEDDING_BATCH_SIZE: int = 50  # 离线任务 Embedding 批处理大小
    CELERY_PROCESS_TEXTBOOK_MAX_RETRIES: int = 3
    CELERY_PROCESS_TEXTBOOK_RETRY_DELAY: int = 60  # 重新解析延迟时间（秒）
    CELERY_SUMMARIZE_CHAT_MAX_RETRIES: int = 2
    CELERY_SUMMARIZE_CHAT_RETRY_DELAY: int = 30  # 摘要提炼失败延迟时间（秒）
    RERANK_RRF_K: int = 60  # RRF 排名常数系数
    RERANK_SSE_HEARTBEAT_SECONDS: float = 8.0  # SSE 连接无数据自动维持心跳秒数

    def __init__(self, **values):
        super().__init__(**values)
        # 从 config.yaml 中安全地扁平化加载非敏感配置
        yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.yaml")
        if os.path.exists(yaml_file):
            try:
                import yaml
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                
                def update_if_present(setting_key: str, val):
                    if val is not None and val != "":
                        setattr(self, setting_key, val)

                # app
                if "app" in data:
                    app = data["app"]
                    update_if_present("PROJECT_NAME", app.get("project_name"))
                    update_if_present("API_V1_STR", app.get("api_v1_str"))
                    update_if_present("ACCESS_TOKEN_EXPIRE_MINUTES", app.get("access_token_expire_minutes"))

                # database
                if "database" in data:
                    db = data["database"]
                    if "mysql" in db:
                        mysql = db["mysql"]
                        update_if_present("MYSQL_USER", mysql.get("user"))
                        update_if_present("MYSQL_HOST", mysql.get("host"))
                        update_if_present("MYSQL_PORT", mysql.get("port"))
                        update_if_present("MYSQL_DB", mysql.get("db"))
                    if "redis" in db:
                        redis = db["redis"]
                        update_if_present("REDIS_URL", redis.get("url"))

                # storage
                if "storage" in data:
                    storage = data["storage"]
                    update_if_present("UPLOAD_DIR", storage.get("upload_dir"))
                    update_if_present("MAX_UPLOAD_MB", storage.get("max_upload_mb"))
                    update_if_present("FILE_BUFFER_CHUNK_BYTES", storage.get("file_buffer_chunk_bytes"))

                # celery
                if "celery" in data:
                    celery = data["celery"]
                    update_if_present("CELERY_EMBEDDING_BATCH_SIZE", celery.get("embedding_batch_size"))
                    if "process_textbook" in celery:
                        pt = celery["process_textbook"]
                        update_if_present("CELERY_PROCESS_TEXTBOOK_MAX_RETRIES", pt.get("max_retries"))
                        update_if_present("CELERY_PROCESS_TEXTBOOK_RETRY_DELAY", pt.get("retry_delay"))
                    if "summarize_chat" in celery:
                        sc = celery["summarize_chat"]
                        update_if_present("CELERY_SUMMARIZE_CHAT_MAX_RETRIES", sc.get("max_retries"))
                        update_if_present("CELERY_SUMMARIZE_CHAT_RETRY_DELAY", sc.get("retry_delay"))

                # llm
                if "llm" in data:
                    llm = data["llm"]
                    if "openai" in llm:
                        openai = llm["openai"]
                        update_if_present("LLM_BASE_URL", openai.get("base_url"))
                        update_if_present("LLM_MODEL_NAME", openai.get("model_name"))
                        # 新增：读取深度思考模型配置名称
                        update_if_present("LLM_REASONING_MODEL_NAME", openai.get("reasoning_model_name"))
                        # ⚠️  API Key 仅允许通过 .env 配置，config.yaml 不得覆盖
                    if "embedding" in llm:
                        emb = llm["embedding"]
                        update_if_present("EMBEDDING_BASE_URL", emb.get("base_url"))
                        update_if_present("EMBEDDING_MODEL_NAME", emb.get("model_name"))
                        # ⚠️  API Key 仅允许通过 .env 配置，config.yaml 不得覆盖

                # rag
                if "rag" in data:
                    rag = data["rag"]
                    update_if_present("CHROMADB_PATH", rag.get("chromadb_path"))
                    update_if_present("TEXTBOOK_CHUNK_SIZE", rag.get("textbook_chunk_size"))
                    update_if_present("CHAT_HISTORY_WINDOW", rag.get("history_window_rounds"))
                    update_if_present("RAG_TOP_K", rag.get("top_k"))
                    update_if_present("CHAT_SYSTEM_PROMPT", rag.get("system_prompt"))
                    update_if_present("ENABLE_HISTORY_SUMMARY", rag.get("enable_history_summary"))
                    update_if_present("HISTORY_SUMMARY_THRESHOLD", rag.get("history_summary_threshold"))

                # rerank
                if "rerank" in data:
                    rerank = data["rerank"]
                    update_if_present("RERANK_MODE", rerank.get("mode"))
                    update_if_present("RERANK_CANDIDATES", rerank.get("candidates_limit"))
                    update_if_present("RERANK_RRF_K", rerank.get("rrf_k"))
                    update_if_present("RERANK_SSE_HEARTBEAT_SECONDS", rerank.get("sse_heartbeat_seconds"))
                    update_if_present("COHERE_API_KEY", rerank.get("cohere_api_key"))
            except Exception as e:
                print(f"Failed to load config.yaml: {e}")

    @property
    def sync_database_url(self) -> str:
        # 对密码进行 URL 编码，以兼容包含特殊字符（如 @、# 等）的密码
        encoded_pw = urllib.parse.quote_plus(self.MYSQL_PASSWORD)
        return f"mysql+pymysql://{self.MYSQL_USER}:{encoded_pw}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    @property
    def async_database_url(self) -> str:
        encoded_pw = urllib.parse.quote_plus(self.MYSQL_PASSWORD)
        return f"mysql+aiomysql://{self.MYSQL_USER}:{encoded_pw}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    model_config = SettingsConfigDict(
        # 使用绝对路径，确保无论从哪个工作目录启动都能正确加载 .env
        env_file=str(_BASE_DIR / ".env"),
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

# ── 关键安全配置启动校验 ─────────────────────────────────────────────────────────
_PLACEHOLDER_KEYS = {"", "YOUR_SUPER_SECRET_KEY_REPLACE_ME_IN_PRODUCTION"}
if settings.SECRET_KEY in _PLACEHOLDER_KEYS:
    raise RuntimeError(
        "[安全错误] SECRET_KEY 未配置！请在 .env 文件中设置一个强随机密钥。\n"
        "生成命令：openssl rand -hex 32"
    )
if not settings.MYSQL_PASSWORD:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "[配置警告] MYSQL_PASSWORD 未在 .env 中配置，数据库连接可能失败！"
    )

# 如果存在本地动态配置文件，则加载并覆写默认设置
import json
override_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config_override.json")
if os.path.exists(override_file):
    try:
        with open(override_file, "r", encoding="utf-8") as f:
            overrides = json.load(f)
            for k, v in overrides.items():
                if hasattr(settings, k):
                    setattr(settings, k, v)
    except Exception as e:
        print(f"加载动态配置覆写失败: {e}")

def save_config_overrides(overrides: dict):
    """
    保存动态配置覆写内容到本地 config_override.json 中，并在当前运行时生效。
    """
    try:
        existing = {}
        if os.path.exists(override_file):
            with open(override_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        
        # 仅过滤并保留在 Settings 类中已定义的合法配置字段
        valid_overrides = {k: v for k, v in overrides.items() if hasattr(settings, k)}
        existing.update(valid_overrides)
        
        with open(override_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
            
        for k, v in valid_overrides.items():
            setattr(settings, k, v)
    except Exception as e:
        print(f"保存动态配置覆写失败: {e}")
        raise e


def reload_settings():
    """
    从本地 config_override.json 中重新加载最新配置，更新全局 settings 对象。
    常用于 Celery worker 在不重启的情况下同步加载最新配置。
    """
    if os.path.exists(override_file):
        try:
            with open(override_file, "r", encoding="utf-8") as f:
                overrides = json.load(f)
                for k, v in overrides.items():
                    if hasattr(settings, k):
                        setattr(settings, k, v)
        except Exception as e:
            print(f"重新加载动态配置失败: {e}")



# 智能教育系统 · 后端服务

> **Smart Education System — Backend API**
> 基于 FastAPI + MySQL + ChromaDB + Celery 构建的 AI 教学辅助后端，提供教材解析、RAG 检索问答、班级管理与用户权限等完整业务能力。

---

## 目录

- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [核心功能](#核心功能)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [数据库迁移](#数据库迁移)
- [启动服务](#启动服务)
- [API 概览](#api-概览)
- [系统架构](#系统架构)
- [注意事项](#注意事项)

---

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.110+ |
| ASGI 服务器 | Uvicorn |
| 数据库 ORM | SQLAlchemy 2.0（异步） |
| 关系型数据库 | MySQL 8.0（通过 aiomysql 异步驱动） |
| 数据迁移 | Alembic |
| 缓存 / 消息队列 Broker | Redis |
| 异步任务队列 | Celery |
| 向量数据库 | ChromaDB（本地持久化） |
| 大语言模型接入 | OpenAI 兼容接口（可对接 DeepSeek、通义等任何 OpenAI 协议服务商） |
| PDF 解析 | PyMuPDF4LLM + PaddleOCR（扫描件 OCR 兜底） |
| 认证 | JWT（HS256，`python-jose`） |
| 数据验证 | Pydantic v2 + pydantic-settings |

---

## 项目结构

```
app-backend/
├── main.py                  # FastAPI 应用入口，注册中间件与路由
├── alembic/                 # 数据库迁移脚本
│   ├── env.py
│   └── versions/            # 迁移版本文件（自动生成）
├── alembic.ini              # Alembic 配置
├── api/
│   └── v1/
│       ├── api.py           # 路由聚合
│       └── endpoints/
│           ├── users.py     # 用户注册、登录、登出
│           ├── classes.py   # 班级创建、学生申请、审批、解散
│           ├── textbooks.py # 教材上传、绑定班级、删除
│           ├── chat.py      # 会话管理、SSE 流式问答
│           └── admin.py     # 管理员：用户管理、配置、广播通知
├── core/
│   ├── config.py            # 全局配置（pydantic-settings，支持 .env + config.yaml）
│   ├── dependencies.py      # JWT 鉴权、RBAC 角色依赖注入
│   ├── exceptions.py        # 全局异常处理器
│   ├── redis.py             # Redis 客户端单例
│   └── security.py          # 密码哈希、JWT 签发
├── crud/
│   ├── base.py              # 通用 CRUD 基类（软删除、分页）
│   ├── crud_user.py
│   ├── crud_class.py
│   ├── crud_textbook.py
│   ├── crud_chat.py
│   ├── crud_relations.py    # 班级-教材、学生-班级关联（含幂等 create_or_restore）
│   └── crud_notification.py
├── db/
│   ├── database.py          # 异步 SQLAlchemy 引擎与 Session 工厂
│   └── models/              # ORM 数据模型
│       ├── base.py          # Base + SoftDeleteMixin
│       ├── user.py
│       ├── course_class.py
│       ├── textbook.py
│       ├── relations.py     # ClassTextbook / StudentClass（含唯一约束）
│       ├── chat.py          # ChatSession / Message
│       └── notification.py
├── services/
│   ├── ai_service.py        # LLM 流式调用封装
│   ├── rag_service.py       # RAG 上下文构建（ChromaDB + FTS5 混合检索）
│   ├── rag_optimizer.py     # FTS5 全文索引管理与重排
│   └── file_storage.py      # 本地磁盘文件存储（流式写入 + 大小校验）
├── worker/
│   ├── celery_app.py        # Celery 应用实例
│   └── tasks.py             # 异步任务：教材解析（OCR+Embedding）、会话摘要压缩
├── config.yaml              # 非敏感配置（模型名称、RAG 参数等）
├── .env                     # 敏感配置（密钥、密码、API Key）⚠️ 不提交 Git
├── requirements.txt
└── API_TABLE.md             # 完整 API 接口说明文档
```

---

## 核心功能

### 🎓 角色体系
系统支持三种用户角色，通过 JWT 载荷中的 `role` 字段区分：

| 角色 | 说明 |
|------|------|
| `student` | 申请加入班级、访问教材、与 AI 对话 |
| `teacher` | 创建班级、上传教材、管理学生、审批申请、审计学生对话 |
| `admin` | 用户管理、强制删除内容、系统配置、广播通知 |

### 📚 教材解析 RAG 链路
1. 教师上传 PDF → 写入数据库（`status=PENDING`）
2. Celery Worker 后台解析：PDF 物理提取（PyMuPDF4LLM）→ OCR 兜底（PaddleOCR）→ **层级父上下文切片（Hierarchical Parent-Context Chunking，自动解析段落标题层级并前置嵌入子块，保障小分块检索不失焦）** → Embedding → 写入 ChromaDB 向量集合 + SQLite FTS5 全文索引（修正了 `page_number` 1-indexed 的正确页码字段抽取）
3. 前端轮询 `/textbooks/{id}/status` 直到 `success`

### 💬 SSE 流式问答
```
用户提问
  → 实时鉴权（是否仍有权限访问该教材）
  → 写入 user 消息
  → 多轮对话上下文检索提炼（Conversational Query Condensation，利用极速 LLM 对前序轮次与当前追问进行提炼生成 Standalone Search Query，避免追问或指代代词导致 RAG 检索跑偏）
  → 双路检索（ChromaDB 向量 + FTS5 全文）→ 候选块重排（RRF 倒数排名融合 / LLM 启发式重排 / Cohere，修复了单项重排时的退化边界 Bug）
  → 构建 messages 载荷（灵活系统提示词与注入指令：优先采用教材事实并标明出处页码，教材缺失时允许利用自身专业知识库进行补充拓展，但绝对不得与教材原文相违背）
  → 流式调用 LLM → SSE 推送 token
  → 流结束写入 AI 消息 → （可选）触发摘要压缩 Celery 任务
```

### 🏫 班级流转
- 教师创建班级（生成 6 位 `class_code`）
- 学生凭 `class_code` 申请加入（支持退出/被踢后重新申请，幂等设计）
- 教师批量审批（单次 SQL，原子事务）
- 教材绑定/解绑班级（支持解绑后重绑，幂等 upsert）

---

## 快速开始

### 环境要求

- Python 3.11+
- MySQL 8.0+
- Redis 6.0+
- （可选）PaddleOCR 需要 CUDA 或 CPU 模式

### 1. 克隆并安装依赖

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`（若无则手动创建）并填写以下必填项：

```env
# JWT 签名密钥（必填！用 openssl rand -hex 32 生成）
SECRET_KEY=<your_secret_key>

# 数据库密码
MYSQL_PASSWORD=<your_mysql_password>

# 大语言模型 API Key
LLM_API_KEY=<your_llm_api_key>

# Embedding 模型 API Key
EMBEDDING_API_KEY=<your_embedding_api_key>

# 允许的前端来源（CORS）
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

> ⚠️ **安全提醒**：`.env` 文件已加入 `.gitignore`，切勿提交至版本控制。

### 3. 配置非敏感参数

在 `config.yaml` 中调整模型名称、数据库地址、RAG 参数等：

```yaml
llm:
  openai:
    base_url: "https://api.openai.com/v1"   # 替换为自己的 API 网关地址
    model_name: "gpt-4o"

database:
  mysql:
    host: localhost
    port: 3306
    db: edu_system
```

---

## 配置说明

配置系统采用 **三层优先级**（高优先级覆盖低优先级）：

```
config_override.json（运行时动态覆写，由 /admin/config 接口写入）
       ↓
.env（敏感配置：密钥、密码、API Key）
       ↓
config.yaml（非敏感配置：数据库地址、模型参数）
       ↓
core/config.py 中的代码默认值
```

### 主要配置项一览

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `SECRET_KEY` | JWT 签名密钥，**必须在 .env 中设置** | — |
| `MYSQL_PASSWORD` | 数据库密码 | — |
| `LLM_API_KEY` | 大模型 API Key | — |
| `LLM_BASE_URL` | 大模型 API 网关地址 | `https://api.openai.com/v1` |
| `LLM_MODEL_NAME` | 对话模型名称 | `gpt-4o` |
| `EMBEDDING_MODEL_NAME` | Embedding 模型名称 | `text-embedding-3-small` |
| `RERANK_MODE` | 重排模式：`none` / `llm` / `cohere` | `llm` |
| `RAG_TOP_K` | 最终注入 Prompt 的检索块数 | `4` |
| `CHAT_HISTORY_WINDOW` | 携带的历史对话轮数 | `5` |
| `MAX_UPLOAD_MB` | 单次 PDF 上传大小限制（MB） | `50` |
| `ENABLE_HISTORY_SUMMARY` | 是否启用历史摘要压缩（节省 Token） | `false` |
| `ALLOWED_ORIGINS` | CORS 白名单，多个用英文逗号分隔 | `http://localhost:5173` |

---

## 数据库迁移

```bash
# 初始化数据库（首次运行）
alembic upgrade head

# 修改 ORM 模型后，自动生成迁移文件
alembic revision --autogenerate -m "describe your change"

# 应用最新迁移
alembic upgrade head

# 回滚一个版本
alembic downgrade -1
```

---

## 启动服务

### 开发环境

```bash
# 启动 FastAPI 开发服务器（支持热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 新开终端：启动 Celery Worker（处理教材解析、摘要等异步任务）
celery -A worker.celery_app worker --loglevel=info -P solo
```

> 💡 Windows 上 Celery 需加 `-P solo`（不支持 fork 进程模型）

### 访问 API 文档

| 工具 | 地址 |
|------|------|
| Swagger UI | http://localhost:8000/api/v1/openapi.json |
| 内置 Docs | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

### 生产环境建议

```bash
# 使用 Gunicorn + Uvicorn worker 多进程部署
gunicorn main:app -k uvicorn.workers.UvicornWorker \
  --workers 4 --bind 0.0.0.0:8000

# Celery 多进程（Linux/macOS）
celery -A worker.celery_app worker --loglevel=info --concurrency=4
```

---

## API 概览

> 完整接口文档见 [API_TABLE.md](./API_TABLE.md)

| 模块 | 前缀 | 主要接口 |
|------|------|---------|
| 用户 | `/api/v1/users` | 注册、登录、获取当前用户、登出 |
| 班级 | `/api/v1/classes` | 创建班级、申请加入、批量审批、踢出学生、解散班级、看板数据 |
| 教材 | `/api/v1/textbooks` | 上传 PDF、查看列表、状态轮询、绑定/解绑班级、删除 |
| 对话 | `/api/v1/chat` | 创建会话、历史消息、SSE 流式问答、删除会话、教师审计 |
| 管理员 | `/api/v1/admin` | 用户管理、冻结/解冻、审批教师、全局教材及问答审计、强制删除内容、系统配置、推送通知 |


### 认证方式

所有接口（除注册/登录）均需在请求头中携带 Bearer Token：

```
Authorization: Bearer <access_token>
```

Token 通过 `POST /api/v1/users/login/access-token` 获取，有效期默认 **8 天**。

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   前端 (Vue / React)                  │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────┐
│              FastAPI (Uvicorn)                        │
│   ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│   │ users API   │  │ classes API │  │ chat API   │  │
│   └──────┬──────┘  └──────┬──────┘  └─────┬──────┘  │
│          │                │               │           │
│   ┌──────▼────────────────▼───────────────▼──────┐   │
│   │           CRUD Layer (SQLAlchemy Async)       │   │
│   └──────────────────────┬────────────────────────┘   │
└──────────────────────────┼────────────────────────────┘
                           │
           ┌───────────────┼──────────────┐
           ▼               ▼              ▼
      ┌─────────┐    ┌──────────┐   ┌──────────┐
      │  MySQL  │    │  Redis   │   │ ChromaDB │
      │ (主存储) │    │(缓存/队列)│   │ (向量库)  │
      └─────────┘    └────┬─────┘   └──────────┘
                          │
                   ┌──────▼──────┐
                   │Celery Worker│
                   │ ┌─────────┐ │
                   │ │教材解析  │ │  ← PDF → OCR → Embedding → ChromaDB
                   │ └─────────┘ │
                   │ ┌─────────┐ │
                   │ │摘要压缩  │ │  ← 历史消息 → LLM 摘要 → DB
                   │ └─────────┘ │
                   └─────────────┘
```

---

## 注意事项

### 🔐 安全
- `.env` 文件包含 `SECRET_KEY`、数据库密码、API Key 等敏感信息，**绝对不能提交到版本控制**
- `SECRET_KEY` 为空时服务启动会直接抛出 `RuntimeError` 阻止启动
- 全局异常 Handler 不会将 SQL 语句、表名等内部信息返回给客户端，仅记录到日志

### 📁 文件存储
- PDF 文件默认存储在 `./uploads/textbooks/YYYY/MM/` 下，生产环境建议挂载独立磁盘或替换为对象存储（OSS / COS）
- 软删除教材时会同步物理删除 PDF 文件，**不可恢复**

### 🔄 软删除
- 所有主要实体均采用软删除（`deleted_at` 时间戳），查询时自动过滤
- 中间表（`ClassTextbook`、`StudentClass`）的软删除与唯一约束通过 `create_or_restore` 幂等方法处理，支持解绑后重绑、退出后重新申请

### ⚡ Celery Worker
- 教材上传后 Celery 任务不可达时不影响 HTTP 响应，可通过 `POST /textbooks/{id}/reprocess` 手动重触发
- Windows 开发环境必须使用 `-P solo` 单进程模式启动 Celery

### 📝 日志
- 应用日志通过标准 `logging` 输出，建议生产环境接入日志采集系统（如 ELK、Loki 等）
- 所有异常均在 `core/exceptions.py` 的全局 Handler 中记录 `exception` 级别日志

---

*如需了解更多接口细节，请查阅 [API_TABLE.md](./API_TABLE.md)*

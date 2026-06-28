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

### 角色体系
系统支持三种用户角色，通过 JWT 载荷中的 `role` 字段区分：

| 角色 | 说明 |
|------|------|
| `student` | 申请加入班级、访问教材、与 AI 对话 |
| `teacher` | 创建班级、上传教材、管理学生、审批申请、审计学生对话 |
| `admin` | 用户管理、强制删除内容、系统配置、广播通知 |

### 教材解析 RAG 链路
1. 教师上传 PDF → 写入数据库（`status=PENDING`）
2. Celery Worker 后台解析：PDF 物理提取（PyMuPDF4LLM）→ OCR 兜底（PaddleOCR）→ 段落标题层级切片与前置嵌套（保障检索时的上下文关联） → Embedding → 写入 ChromaDB 向量集合 + SQLite FTS5 全文索引（修正了 `page_number` 1-indexed 的正确页码字段抽取）
3. 前端轮询 `/textbooks/{id}/status` 直到 `success`

### SSE 流式问答
```
用户提问
  → 实时鉴权（是否仍有权限访问该教材）
  → 写入 user 消息
  → 多轮对话上下文检索提炼（利用 LLM 提炼生成 Standalone Search Query，避免追问导致 RAG 检索偏差）
  → 双路检索（ChromaDB 向量 + FTS5 全文）→ 候选块重排（RRF 倒数排名融合 / LLM 启发式重排 / Cohere）
  → 构建 messages 载荷（灵活系统提示词与注入指令：优先采用教材事实并标明出处页码，教材缺失时允许利用自身专业知识库进行补充拓展，但绝对不得与教材原文相违背）
  → 流式调用 LLM → SSE 推送 token
  → 流结束写入 AI 消息 → （可选）触发摘要压缩 Celery 任务
```

### 班级流转
- 教师创建班级（生成 6 位 `class_code`）
- 学生凭 `class_code` 申请加入（支持退出/被踢后重新申请，幂等设计）
- 教师批量审批（单次 SQL，原子事务）
- 教材绑定/解绑班级（支持解绑后重绑，幂等 upsert）

---

## Windows 本地调试与运行说明

本部分详细介绍在 Windows 环境下如何快速搭建、配置并运行本系统的后端服务，以便老师或开发人员进行测试。

### 1. 本地环境准备

在开始之前，请确保您的 Windows 电脑已安装以下基础环境：
- **Python 3.11**（推荐使用 3.11 版本。安装时请务必勾选 **"Add Python to PATH"**，否则终端无法识别 `python` 命令）
- **关系型数据库 MySQL 8.0+**（推荐使用常规安装，或使用 **XAMPP / phpStudy (小皮面板)** 快速启动 MySQL 数据库服务）
- **缓存与消息队列 Redis**（在 Windows 下可以使用 Redis-Windows 版本，或直接下载 Windows 绿色的 Redis 二进制压缩包运行）

---

### 2. 数据库与 Redis 启动配置

#### 2.1 MySQL 数据库初始化
1. 启动本地 MySQL 服务。
2. 使用 Navicat、SQLyog 等可视化工具（或在命令行）连接数据库，并手动创建一个名为 `edu_system` 的空数据库：
   ```sql
   CREATE DATABASE edu_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

#### 2.2 Redis 启动
1. 进入您的 Redis 解压目录，在命令行中执行以下命令以启动 Redis 服务：
   ```cmd
   redis-server.exe
   ```
   *（启动后保持该命令行窗口不要关闭，默认监听端口为 6379）*

---

### 3. 后端依赖安装

1. **进入后端目录**：打开 Windows 终端（如 PowerShell 或 CMD），进入 `app-backend` 根目录。
2. **创建并激活 Python 虚拟环境**：
   - **使用 PowerShell**：
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - **使用 CMD**：
     ```cmd
     python -m venv .venv
     .venv\Scripts\activate.bat
     ```
     *(激活成功后，命令行提示符最前面会出现 `(.venv)` 标志)*
3. **安装依赖包**：
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
   > 💡 **小贴士**：因依赖包含 OCR 文字识别库 `paddleocr`，若安装速度缓慢，可使用国内镜像源加速：
   > `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

---

### 4. 环境变量与配置文件设置

1. **敏感与本地密码配置 (`.env`)**：
   在 `app-backend` 根目录下手动新建一个文件，命名为 **`.env`**。写入以下内容（请根据您的实际数据库密码、API Key 修改）：
   ```env
   # JWT 签名密钥（可用做测试默认值，或命令行运行 openssl rand -hex 32 生成）
   SECRET_KEY=f32f4e1859e77ffde529c2b3901b673af08badc0505d8322e725345559dd1908

   # 本地 MySQL 数据库密码（请修改为您的实际 MySQL 连接密码）
   MYSQL_PASSWORD=your_mysql_password

   # 大语言模型 API 密钥（可替换为您所用服务商的真实 API Key，如 DeepSeek、OpenAI）
   LLM_API_KEY=sk-...

   # Embedding 向量化模型 API 密钥（如不需要重写，可以直接使用与 LLM 相同的 Key）
   EMBEDDING_API_KEY=ark-...

   # 跨域允许的前端源列表（开发环境下，默认指向前端的启动端口 5173）
   ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000
   ```

2. **系统模型与常规配置 (`config.yaml`)**：
   在 `config.yaml` 中，您可以根据实际需求调整：
   - 本地 MySQL 连接信息（默认地址为 `localhost:3306`）。
   - 大语言模型的网关地址及调用的模型名称（`llm.openai.base_url`、`llm.openai.model_name` 等）。

---

### 5. 执行数据库初始化迁移

在已激活虚拟环境的终端中，运行 Alembic 指令以在 MySQL 中自动建立数据表结构：
```bash
alembic upgrade head
```
运行完成后，`edu_system` 数据库中会自动创建 `users`、`course_class`、`textbook`、`chat_session` 等多张实体数据表。

---

### 6. 一键启动后端服务进行测试

为了使系统正常运转，在 Windows 本地测试时，需要同时运行 **Web 接口服务** 与 **Celery 异步队列**：

#### 步骤一：启动 FastAPI API 服务
新开一个终端窗口，激活虚拟环境后运行：
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- 服务启动后，通过浏览器访问 `http://localhost:8000/docs` 即可进入交互式 API 文档页面（Swagger UI），能直接在网页上进行接口功能测试。

#### 步骤二：启动 Celery 异步队列 (Windows 注意事项)
由于 Windows 的默认并发机制与 Celery 内部设计在进程复用上存在兼容问题，**如果不加额外参数，在 Windows 上上传 PDF 后后台任务将会卡死或报错**。
因此，在 Windows 上启动 Celery Worker，**必须强制加上 `-P solo` 参数**（即串行执行模式）：

新开一个终端窗口，激活虚拟环境后运行：
```bash
celery -A worker.celery_app worker --loglevel=info -P solo
```
*(保持此窗口不要关闭，当教师上传教材 PDF 后，该窗口将显示 PDF 文本提取、段落标题语义切片与向量库入库的进度日志)*

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

### 安全
- `.env` 文件包含 `SECRET_KEY`、数据库密码、API Key 等敏感信息，**绝对不能提交到版本控制**
- `SECRET_KEY` 为空时服务启动会直接抛出 `RuntimeError` 阻止启动
- 全局异常 Handler 不会将 SQL 语句、表名等内部信息返回给客户端，仅记录到日志

### 文件存储
- PDF 文件默认存储在 `./uploads/textbooks/YYYY/MM/` 下，生产环境建议挂载独立磁盘或替换为对象存储（OSS / COS）
- 软删除教材时会同步物理删除 PDF 文件，**不可恢复**

### 软删除
- 所有主要实体均采用软删除（`deleted_at` 时间戳），查询时自动过滤
- 中间表（`ClassTextbook`、`StudentClass`）的软删除与唯一约束通过 `create_or_restore` 幂等方法处理，支持解绑后重绑、退出后重新申请

### Celery Worker
- 教材上传后 Celery 任务不可达时不影响 HTTP 响应，可通过 `POST /textbooks/{id}/reprocess` 手动重触发
- Windows 开发环境必须使用 `-P solo` 单进程模式启动 Celery

### 日志
- 应用日志通过标准 `logging` 输出，建议生产环境接入日志采集系统（如 ELK、Loki 等）
- 所有异常均在 `core/exceptions.py` 的全局 Handler 中记录 `exception` 级别日志

---

*如需了解更多接口细节，请查阅 [API_TABLE.md](./API_TABLE.md)*

# edu-RAG-system
这是一个基于 AI 驱动的智能教育教学辅助系统，采用前后端分离架构。前端基于 Vue 3、Vite 和 Pinia 构建，提供多角色用户界面；后端基于 FastAPI、MySQL 和 Redis 构建，采用异步架构。  系统核心实现了教材解析与 RAG（检索增强生成）问答链路。教师上传 PDF 教材后，系统通过 Celery 异步调用 PyMuPDF4LLM 及 PaddleOCR 进行解析、切片并提取向量，存储于 ChromaDB 与 SQLite FTS5 全文索引中。学生提问时，系统通过向量与全文双路检索及重排技术构建上下文，并通过 SSE（服务器发送事件）进行流式 AI 问答。此外，系统还提供班级流转、多角色（学生、教师、管理员）RBAC 权限管理及教师对话审计功能。

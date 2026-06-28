"""
Celery 后台任务

process_textbook_task:
  1. 将 textbook status → PROCESSING
  2. 用 DocumentParser 解析 PDF → 切块
  3. 调用 AIService 批量生成 Embedding
  4. 写入 ChromaDB collection（textbook_vec_<id>）
  5. 成功 → status = SUCCESS，失败 → status = FAILED
     （均使用同步 SQLAlchemy session，因为 Celery worker 是同步环境）
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import chromadb
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from core.config import settings, reload_settings
from db.models.textbook import Textbook, TextbookStatus
from db.models.chat import ChatSession, Message, SenderRole
from services.ai_service import AIService
from services.document_parser import DocumentParser
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

# ChromaDB 持久化客户端（与 RAGService 共享同一磁盘路径）
chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)

# 同步 SQLAlchemy 引擎（Celery worker 为同步环境，不能用 AsyncSession）
_sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# 内部：同步写库
# ---------------------------------------------------------------------------

_redis_available = True
_redis_client = None

def _get_redis_client():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL, 
            decode_responses=True,
            socket_connect_timeout=0.2, # 200ms timeout
            socket_timeout=0.2          # 200ms timeout
        )
    return _redis_client


def _update_textbook_status(
    textbook_id: int,
    status: TextbookStatus | None = None,
    chroma_collection_id: str | None = None,
    progress: int | None = None,
) -> None:
    """用同步 session 更新教材状态和进度（供 Celery task 内部调用）。"""
    values: dict = {}
    if status is not None:
        values["status"] = status
    if chroma_collection_id is not None:
        values["chroma_collection_id"] = chroma_collection_id
    if progress is not None:
        values["processing_progress"] = progress

    if not values:
        return

    with Session(_sync_engine) as session:
        # 在 commit 之前就取出 teacher_id，避免 commit 后对象过期需要二次查询
        teacher_id = None
        try:
            db_textbook = session.get(Textbook, textbook_id)
            if db_textbook:
                teacher_id = db_textbook.teacher_id
        except Exception as e:
            logger.warning("Failed to fetch teacher_id before status update: %s", e)

        session.execute(
            update(Textbook)
            .where(Textbook.id == textbook_id)
            .values(**values)
        )
        session.commit()
        
        # ── 同步清除该教材所属教师的列表与主看板缓存 ─────────────────────────────
        # 仅在 status 实际改变时才需要清理列表/主看板缓存，进度百分比更新无需清理
        global _redis_available
        if status is not None and teacher_id and _redis_available:
            try:
                r = _get_redis_client()
                r.delete(f"cache:textbooks:list:teacher:{teacher_id}")
                r.delete(f"cache:textbooks:list:admin:{teacher_id}")
                r.delete(f"cache:teacher_dashboard:{teacher_id}")
            except Exception as e:
                _redis_available = False
                logger.warning("Failed to invalidate teacher caches in Celery worker (circuit breaker triggered): %s", e)
        
    log_msg = f"[Textbook {textbook_id}]"
    if status:
        log_msg += f" status → {status.value}"
    if progress is not None:
        log_msg += f" progress → {progress}%"
    logger.info(log_msg)


def _run_async_in_thread(coro):
    import threading
    result = None
    exception = None

    def target():
        nonlocal result, exception
        try:
            result = asyncio.run(coro)
        except Exception as e:
            exception = e

    t = threading.Thread(target=target)
    t.start()
    t.join()

    if exception:
        raise exception
    return result


# ---------------------------------------------------------------------------
# Celery 异步任务
# ---------------------------------------------------------------------------

@celery_app.task(
    name="worker.tasks.process_textbook_task",
    bind=True,
    max_retries=settings.CELERY_PROCESS_TEXTBOOK_MAX_RETRIES,
    default_retry_delay=settings.CELERY_PROCESS_TEXTBOOK_RETRY_DELAY,
)
def process_textbook_task(self, textbook_id: int, file_path: str):
    """
    后台处理教材全流程：
    OCR 解析 → 语义切块 → Embedding 生成 → ChromaDB 注入。

    Args:
        textbook_id : Textbook 表主键
        file_path   : PDF 在服务器上的**绝对路径**
    """
    collection_name = f"textbook_vec_{textbook_id}"
    logger.info(
        "[Task %s] Started: textbook_id=%d, path=%s",
        self.request.id, textbook_id, file_path,
    )

    # ── 阶段 0：同步最新动态配置（管理员可能已通过 /admin/config 修改 LLM 参数）
    reload_settings()

    # ── 阶段 1：标记为「处理中」，进度设置为 5% ──────────────────────────────
    _update_textbook_status(textbook_id, status=TextbookStatus.PROCESSING, progress=5)

    try:
        # ── 阶段 2：解析 PDF ────────────────────────────────────────────
        parser = DocumentParser()
        markdown_content = parser.parse_pdf(file_path)
        _update_textbook_status(textbook_id, progress=15)

        # ── 阶段 3：语义切块（父子双路分块）──────────────────────────────
        chunks_data = parser.chunk_document_parent_child(markdown_content)
        _update_textbook_status(textbook_id, progress=30)
        
        if not chunks_data:
            logger.warning(
                "[Task %s] No text extracted from textbook %d, marking success with empty collection.",
                self.request.id, textbook_id,
            )
            # 空文档也算完成（不阻塞教学流程），创建空 collection 占位
            try:
                chroma_client.delete_collection(name=collection_name)
            except Exception:
                pass
            chroma_client.create_collection(name=collection_name)
            _update_textbook_status(
                textbook_id, 
                status=TextbookStatus.SUCCESS, 
                chroma_collection_id=collection_name, 
                progress=100
            )
            return {"status": "success", "chunks_processed": 0}

        # ── 阶段 4 & 5：Embedding 批量生成 + ChromaDB 注入 ───────────────────
        # 每次解析前先删除已有的 Collection 与 FTS5 全文索引，以防重试冲突及旧数据污染
        try:
            chroma_client.delete_collection(name=collection_name)
            from services.rag_optimizer import FTSIndexManager
            FTSIndexManager.delete_document_chunks(textbook_id)
        except Exception as cleanup_exc:
            # 集合不存在时会抛异常（属于正常情况），记录日志便于排查异常残留问题
            logger.warning(
                "[Task %s] Pre-cleanup for textbook %d raised (may be first run): %s",
                self.request.id, textbook_id, cleanup_exc,
            )
        collection = chroma_client.create_collection(name=collection_name)

        async def _embed_and_store_batches():
            ai_service = AIService()
            batch_size = settings.CELERY_EMBEDDING_BATCH_SIZE
            total_chunks = len(chunks_data)
            
            for i in range(0, total_chunks, batch_size):
                batch = chunks_data[i : i + batch_size]
                batch_docs = [item["child_content"] for item in batch]
                batch_embeddings = await ai_service.get_embeddings_batch(batch_docs)
                
                batch_ids = [f"chunk_{idx}" for idx in range(i, i + len(batch))]
                batch_metadatas = [
                    {
                        "textbook_id": textbook_id,
                        "parent_content": item["parent_content"],
                        "chunk_index": idx,
                        "page_number": item.get("page_number", 1)
                    }
                    for idx, item in enumerate(batch, start=i)
                ]
                
                collection.add(
                    documents=batch_docs,
                    embeddings=batch_embeddings,   # type: ignore[arg-type]
                    metadatas=batch_metadatas,     # type: ignore[arg-type]
                    ids=batch_ids,
                )
                
                # 进度在 30% 到 95% 之间按处理分块进度等分更新
                progress = 30 + int((i + len(batch)) / total_chunks * 65)
                _update_textbook_status(textbook_id, progress=progress)

        _run_async_in_thread(_embed_and_store_batches())

        # ── 阶段 4.5：同步建立 SQLite FTS5 全文检索索引 ───────────────────────
        try:
            from services.rag_optimizer import FTSIndexManager
            FTSIndexManager.add_document_chunks(textbook_id, chunks_data)
            logger.info("[Task %s] Indexing completed in FTS5 for textbook %d.", self.request.id, textbook_id)
        except Exception as fts_exc:
            logger.error("[Task %s] Failed to build FTS5 index: %s", self.request.id, fts_exc)

        logger.info(
            "[Task %s] SUCCESS: %d chunks ingested for textbook %d.",
            self.request.id, len(chunks_data), textbook_id,
        )

        # ── 阶段 5：回写最终成功状态与 100% 进度 ──────────────────────
        _update_textbook_status(
            textbook_id, 
            status=TextbookStatus.SUCCESS, 
            chroma_collection_id=collection_name, 
            progress=100
        )
        return {"status": "success", "chunks_processed": len(chunks_data)}

    except Exception as exc:
        logger.exception(
            "[Task %s] FAILED for textbook %d: %s",
            self.request.id, textbook_id, exc,
        )
        try:
            # 重试
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            # 重试耗尽 → 最终标记为 FAILED
            _update_textbook_status(textbook_id, status=TextbookStatus.FAILED)
            raise


@celery_app.task(
    name="worker.tasks.summarize_chat_session_task",
    bind=True,
    max_retries=settings.CELERY_SUMMARIZE_CHAT_MAX_RETRIES,
    default_retry_delay=settings.CELERY_SUMMARIZE_CHAT_RETRY_DELAY,
)
def summarize_chat_session_task(self, session_id: int, force: bool = False):
    """
    根据会话的历史消息自动生成/更新摘要。
    会对 AI 回复内容进行代码块过滤与长度截断（脱水），以节省 Token。
    """
    logger.info("[Task %s] Summarizing chat session %d (force=%s)", self.request.id, session_id, force)
    
    # ── 阶段 1：快速查询所需数据库信息，并立即释放连接 ──────────────────────────
    with Session(_sync_engine) as session:
        db_session = session.get(ChatSession, session_id)
        if not db_session or db_session.deleted_at is not None:
            logger.warning("ChatSession %d not found or deleted, skip summary.", session_id)
            return

        # 获取当前会话所有的未删除消息
        messages = (
            session.query(Message)
            .filter(Message.session_id == session_id, Message.deleted_at.is_(None))
            .order_by(Message.created_at.asc())
            .all()
        )
        
        # 如果没有任何消息，跳过
        if len(messages) == 0:
            logger.info("ChatSession %d has no messages, skip summary generation.", session_id)
            return

        # 如果对话太短（例如少于 1 轮即 2 条消息）且没有强制运行，则不更新摘要以节省 Token
        if len(messages) < 2 and not force:
            logger.info("ChatSession %d has only %d messages, skip summary generation.", session_id, len(messages))
            return
            
        # 组装对话历史文本 (在此 Session 仍在生命周期内读取消息内容，防止延迟加载错误)
        history_text = ""
        for msg in messages:
            if msg.sender == SenderRole.USER:
                history_text += f"学生: {msg.content.strip()}\n"
            elif msg.sender == SenderRole.AI:
                # 对 AI 的回复进行脱水处理：
                # 1. 移除 Markdown 代码块
                content_clean = re.sub(r"```[\s\S]*?```", "[代码块已省略]", msg.content)
                # 2. 限制单条回复长度（截断保留前 120 字）
                if len(content_clean) > 120:
                    content_clean = content_clean[:120] + "..."
                history_text += f"AI助手: {content_clean.strip()}\n"

    # 此时，Session 已经在退出 block 后自动关闭并归还数据库连接池 

    # ── 阶段 2：执行外部大模型网络 I/O 呼叫（不再长时间霸占 DB 连接） ──────────────────
    # 构造提炼 Prompt
    prompt = (
        "你是一个教学督导助手。请根据以下学生与AI教学助手的对话历史，"
        "提炼出一段简明扼要的会话摘要（不超过 150 字）。\n"
        "请重点提炼：1. 学生关注或疑惑的知识点是什么？ 2. 学生目前遇到了什么具体的学习难点？ 3. 最终该疑惑是否得到了解答或解决？\n"
        f"【对话历史】:\n{history_text}\n"
        "请直接输出提炼后的摘要内容，不要有任何前导或后缀修饰词语。"
    )

    try:
        ai_service = AIService()
        async def _run_summary():
            res = await ai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            return res.choices[0].message.content
            
        summary_content = _run_async_in_thread(_run_summary())
        summary_content = summary_content.strip()
        
    except Exception as exc:
        logger.exception("Failed to generate summary via LLM for ChatSession %d: %s", session_id, exc)
        raise self.retry(exc=exc)

    # ── 阶段 3：获取摘要成果后，开启独立的短 Session 写入数据库 ───────────────────
    try:
        with Session(_sync_engine) as write_session:
            db_session = write_session.get(ChatSession, session_id)
            if db_session and db_session.deleted_at is None:
                db_session.summary = summary_content
                db_session.summary_updated_at = datetime.now(timezone.utc)
                write_session.commit()
                logger.info("Successfully updated summary for ChatSession %d", session_id)
            else:
                logger.warning("ChatSession %d was deleted before saving summary.", session_id)
    except Exception as exc:
        logger.exception("Failed to save summary to DB for ChatSession %d: %s", session_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            # 重试次数耗尽，记录最终失败日志（不再抛出，避免 Celery 报未捕获异常）
            logger.error(
                "summarize_chat_session_task: max retries exceeded for ChatSession %d, summary not saved.",
                session_id,
            )


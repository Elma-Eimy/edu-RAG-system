"""
RAG（检索增强生成）服务

职责：
  1. query_context()  —— 接收用户问题，向 ChromaDB 检索相关文本块
  2. build_messages() —— 将检索结果 + 近 N 轮对话历史组装成 LLM messages 列表
"""

from __future__ import annotations

import logging
from typing import List, Dict

import chromadb
from chromadb import AsyncHttpClient, Collection

from core.config import settings
from services.ai_service import AIService

logger = logging.getLogger(__name__)


class RAGService:
    """
    教材检索增强服务。
    使用持久化本地 ChromaDB（PersistentClient），与 Celery 异步解析任务进程共享相同的磁盘数据库文件目录。
    """

    def __init__(self):
        self._chroma_client: chromadb.ClientAPI | None = None
        self._ai_service = AIService()

    # ------------------------------------------------------------------
    # 内部方法：懒加载初始化 ChromaDB 客户端（运行期全局仅初始化一次）
    # ------------------------------------------------------------------
    def _get_client(self) -> chromadb.ClientAPI:
        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
        return self._chroma_client

    def _get_collection(self, textbook_id: int) -> Collection | None:
        """
        按惯例获取名称为 textbook_vec_<id> 的向量集合（Collection）。
        若该教材尚未开始进行向量化解析（集合尚不存在），则返回 None 并记录警告日志。
        """
        name = f"textbook_vec_{textbook_id}"
        try:
            return self._get_client().get_collection(name=name)
        except Exception:
            logger.warning("ChromaDB 向量集合 '%s' 未找到 — 此次问答的 RAG 上下文将为空。", name)
            return None

    # ------------------------------------------------------------------
    # 公开接口 1：向 ChromaDB 检索教材相关的内容分块
    # ------------------------------------------------------------------
    async def query_context(self, textbook_id: int, query: str) -> List[str]:
        """
        系统升级：双路混合检索与重排（Hybrid Search & Reranking）系统。
        
        1. 向量稀疏检索 (Dense Retrieval via ChromaDB) -> 召回 Top 12 候选
        2. 全文检索 (Sparse Retrieval via SQLite FTS5) -> 召回 Top 12 候选
        3. 排名倒数融合 (Reciprocal Rank Fusion - RRF) -> 去重混合排序
        4. 二次精准重排 (Rerank via Cohere/LLM) -> 精选最匹配的 Top 4
        """
        collection = self._get_collection(textbook_id)
        if collection is None:
            return []

        # ── 1. 双路检索：向量密集检索 (Dense) ──────────────────────────────────
        dense_candidates = []
        try:
            query_embedding = await self._ai_service.get_embedding(query)
            import asyncio
            results = await asyncio.to_thread(
                collection.query,
                query_embeddings=[query_embedding],
                n_results=settings.RERANK_CANDIDATES,
                include=["documents", "metadatas"],
            )
            if results["documents"] and results["documents"][0]:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results["metadatas"] else [None] * len(docs)
                for doc, meta in zip(docs, metas):
                    parent_content = doc
                    page_num = 1
                    if meta and isinstance(meta, dict):
                        parent_content = meta.get("parent_content") or doc
                        page_num = meta.get("page_number", 1)
                    
                    dense_candidates.append({
                        "child_content": doc,
                        "parent_content": parent_content,
                        "page_number": page_num
                    })
        except Exception as e:
            logger.error("ChromaDB dense query failed for textbook %d: %s", textbook_id, e)

        # ── 2. 双路检索：SQLite FTS5 全文关键词检索 (Sparse) ──────────────────
        from services.rag_optimizer import FTSIndexManager, reciprocal_rank_fusion, Reranker
        sparse_candidates = []
        try:
            sparse_candidates = FTSIndexManager.query_fts(
                textbook_id=textbook_id,
                query_text=query,
                limit=settings.RERANK_CANDIDATES
            )
        except Exception as e:
            logger.error("SQLite FTS5 sparse query failed for textbook %d: %s", textbook_id, e)

        # ── 3. 倒数排名融合 (RRF) 去重打分 ────────────────────────────────────
        fused_candidates = reciprocal_rank_fusion(dense_candidates, sparse_candidates)

        if not fused_candidates:
            return []

        # ── 4. 二次精准重排，筛选出 Top-K (RAG_TOP_K, 默认 4 个) ─────────────
        try:
            reranker = Reranker()
            selected_chunks = await reranker.rerank(
                query=query,
                candidates=fused_candidates,
                top_k=settings.RAG_TOP_K
            )
        except Exception as e:
            logger.error("Reranking failed for textbook %d, falling back to top_k: %s", textbook_id, e)
            selected_chunks = fused_candidates[:settings.RAG_TOP_K]

        # ── 5. 格式化并还原为原接口兼容的文本片段列表 ──────────────────────────
        parent_chunks = []
        for chunk in selected_chunks:
            content_to_use = chunk["parent_content"]
            page_number = chunk.get("page_number", 1)
            
            # 使用与原版接口相同的源页码标记格式
            formatted = f"[源自第 {page_number} 页]\n{content_to_use}"
            parent_chunks.append(formatted)
            
        return parent_chunks


    # ------------------------------------------------------------------
    # 公开接口 2：组装并构建完整的大模型输入 Payload 列表
    # ------------------------------------------------------------------
    async def build_messages(
        self,
        textbook_id: int,
        user_query: str,
        history: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """
        构造符合 OpenAI 聊天补全接口规范的 messages 列表数据：

        结构：[system_prompt, ...历史问答轮次(N轮), 携带 RAG 上下文的用户当前提问]

        参数：
            textbook_id : 教材的主键 ID，用来定位向量数据库集合
            user_query  : 学生的当前提问明文内容
            history     : 已经提取出的最近几轮的历史聊天信息列表，
                          每一项格式为 {"role": "user"/"assistant", "content": "..."}
        """
        # 1. 检索教材关联度最高的内容片段
        chunks = await self.query_context(textbook_id, user_query)

        # 2. 获取预设的系统提示词（System Prompt）
        system_content = settings.CHAT_SYSTEM_PROMPT

        # 3. 如果召回到了教材内容，将其作为增强上下文拼装入用户的当前提问中
        if chunks:
            rag_context = "\n\n".join(
                f"【参考片段 {i + 1}】\n{chunk}" for i, chunk in enumerate(chunks)
            )
            augmented_user_content = (
                f"以下是教材中与你的问题相关的参考资料：\n\n"
                f"{rag_context}\n\n"
                f"---\n\n"
                f"学生问题：{user_query}\n\n"
                f"请严格根据以上参考片段回答问题，并在回答中明确指出依据的页码（例如：根据教材第X页...）。"
            )
        else:
            # 如果教材未处理完毕或者检索召回为空，依然允许直接和大模型对话，只是没有 RAG 原文佐证
            augmented_user_content = user_query

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content},
            *history,
            {"role": "user", "content": augmented_user_content},
        ]

        return messages


import os
import sqlite3
import logging
import json
import httpx
from typing import List, Dict, Any
from core.config import settings
from services.ai_service import AIService

logger = logging.getLogger(__name__)

# FTS5 本地 SQLite 数据库路径，与 ChromaDB 共享同一根级目录
FTS_DB_PATH = os.path.abspath(os.path.join(settings.CHROMADB_PATH, "fts5_index.db"))


class FTSIndexManager:
    """
    基于 SQLite FTS5 虚拟表的高效中文全文检索服务（提供传统 TF-IDF/BM25 稀疏检索）。
    """
    
    @staticmethod
    def _get_connection() -> sqlite3.Connection:
        """获取 SQLite 连接并确保目录存在。"""
        os.makedirs(os.path.dirname(FTS_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(FTS_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls) -> None:
        """初始化 FTS5 虚拟表结构，支持全文本分词检索。"""
        conn = cls._get_connection()
        try:
            with conn:
                # FTS5 表不支持外键，它是一个单纯的高速搜索引擎虚拟表
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS textbook_fts USING fts5(
                        textbook_id,
                        chunk_index,
                        child_content,
                        parent_content,
                        page_number
                    );
                """)
                logger.info("SQLite FTS5 virtual table initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize FTS5 virtual table: %s", e)
        finally:
            conn.close()

    @classmethod
    def add_document_chunks(cls, textbook_id: int, chunks_data: List[Dict[str, Any]]) -> None:
        """
        批量为教材的切分分块创建全文检索索引记录。
        """
        cls.init_db()  # 确保表已初始化
        conn = cls._get_connection()
        try:
            with conn:
                # 写入前先删除旧索引以防污染
                conn.execute(
                    "DELETE FROM textbook_fts WHERE textbook_id = ?;", 
                    (str(textbook_id),)
                )
                
                # 批量插入新索引分块
                conn.executemany(
                    """
                    INSERT INTO textbook_fts(textbook_id, chunk_index, child_content, parent_content, page_number)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    [
                        (
                            str(textbook_id),
                            idx,
                            item["child_content"],
                            item["parent_content"],
                            item.get("page_number", 1)
                        )
                        for idx, item in enumerate(chunks_data)
                    ]
                )
            logger.info("Indexed %d chunks for textbook %d in FTS5.", len(chunks_data), textbook_id)
        except Exception as e:
            logger.error("Failed to index chunks in FTS5 for textbook %d: %s", textbook_id, e)
        finally:
            conn.close()

    @classmethod
    def delete_document_chunks(cls, textbook_id: int) -> None:
        """删除指定教材的全部全文检索索引记录。"""
        conn = cls._get_connection()
        try:
            with conn:
                conn.execute(
                    "DELETE FROM textbook_fts WHERE textbook_id = ?;", 
                    (str(textbook_id),)
                )
            logger.info("Deleted FTS5 index records for textbook %d.", textbook_id)
        except Exception as e:
            logger.error("Failed to delete FTS5 index records for textbook %d: %s", textbook_id, e)
        finally:
            conn.close()

    @classmethod
    def query_fts(cls, textbook_id: int, query_text: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        利用 FTS5 原生的 MATCH 语法和 BM25 算法对分块进行稀疏关键词检索。
        """
        # 1. 过滤特殊字符，防范 FTS 语法解析崩溃
        import re
        cleaned_query = re.sub(r'[^\w\s]', ' ', query_text)
        words = [w.strip() for w in cleaned_query.split() if w.strip()]
        if not words:
            return []
        
        # 2. 用 OR 拼接多词匹配，提高稀疏检索召回率
        match_expression = " OR ".join(words)
        
        cls.init_db()
        conn = cls._get_connection()
        try:
            # 3. 运行 BM25 检索评分
            cursor = conn.execute(
                """
                SELECT child_content, parent_content, page_number, chunk_index
                FROM textbook_fts
                WHERE textbook_id = ? AND textbook_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
                """,
                (str(textbook_id), match_expression, limit)
            )
            rows = cursor.fetchall()
            return [
                {
                    "child_content": row["child_content"],
                    "parent_content": row["parent_content"],
                    "page_number": row["page_number"],
                    "chunk_index": row["chunk_index"]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("FTS5 query failed for textbook %d: %s", textbook_id, e)
            return []
        finally:
            conn.close()


def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]], 
    sparse_results: List[Dict[str, Any]], 
    k: int = settings.RERANK_RRF_K
) -> List[Dict[str, Any]]:
    """
    RRF（倒数排名融合）算法。
    将语义向量匹配结果（Dense）和关键词全文检索结果（Sparse）进行混合打分排序并去重。
    
    参数:
        dense_results: 向量检索召回的列表，每项包含 child_content, parent_content, page_number
        sparse_results: FTS 检索召回的列表
        k: RRF 常数，默认 settings.RERANK_RRF_K
    """
    rrf_scores: Dict[str, float] = {}
    item_map: Dict[str, Dict[str, Any]] = {}

    def _process_ranking(results: List[Dict[str, Any]]):
        for rank, item in enumerate(results, start=1):
            # 以 child_content 作为唯一去重标识键值
            key = item["child_content"]
            if key not in item_map:
                item_map[key] = item
            
            # 累计 RRF 分值：1 / (k + rank)
            score = 1.0 / (k + rank)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + score

    # 双路排名累计
    _process_ranking(dense_results)
    _process_ranking(sparse_results)

    # 按照 RRF 得分降序排列候选集
    sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    return [item_map[key] for key in sorted_keys]


class Reranker:
    """
    检索增强重排服务模块（支持 Cohere API 与 免算力 LLM-based 启发式重排）。
    """
    
    def __init__(self):
        self._ai_service = AIService()

    async def rerank(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """
        对外公开的二次重排入口。根据设置自动调度重排策略。
        """
        if not candidates:
            return []
            
        mode = settings.RERANK_MODE.lower()
        if mode == "cohere" and settings.COHERE_API_KEY:
            return await self._rerank_cohere(query, candidates, top_k)
        elif mode == "llm":
            return await self._rerank_llm(query, candidates, top_k)
        
        # none 模式或未配置密钥，降级不进行重排，直接截断返回 Top-K
        return candidates[:top_k]

    async def _rerank_cohere(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """调用云端 Cohere Rerank v3/v2 极速重排接口。"""
        url = "https://api.cohere.ai/v1/rerank"
        headers = {
            "Authorization": f"Bearer {settings.COHERE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 准备文档列表（使用子分块内容进行精准匹配）
        documents = [c["child_content"] for c in candidates]
        payload = {
            "model": "rerank-multilingual-v3.0",
            "query": query,
            "documents": documents,
            "top_n": top_k
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    reranked = []
                    for res in results:
                        idx = res["index"]
                        reranked.append(candidates[idx])
                    return reranked
                else:
                    logger.error(
                        "Cohere Rerank API returned error: %d, response: %s", 
                        response.status_code, response.text
                    )
        except Exception as e:
            logger.error("Cohere Rerank call failed, falling back: %s", e)
            
        # 发生异常降级不重排
        return candidates[:top_k]

    async def _rerank_llm(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        利用已配置的现有大模型，零成本实现高灵活性重排（LLM-based Listwise Reranking）。
        通过 Prompt 引导 LLM 从候选集挑选出最相关的分块索引号。
        """
        # 限制候选数量防 Prompt 过长
        cand_list = candidates[:12]
        
        # 格式化候选文本
        formatted_docs = ""
        for i, c in enumerate(cand_list):
            formatted_docs += f"【编号 {i}】: {c['child_content'].strip()}\n\n"

        prompt = (
            "你是一个精准的信息检索重排专家。下面有几段从教材中检索出的参考片段，"
            "请评估它们与学生提出的问题的相关程度，并从中精选出最能精准解答该问题的参考片段。\n\n"
            f"学生提问: \"{query}\"\n\n"
            f"检索出的备选教材参考片段列表:\n{formatted_docs}"
            f"请挑选出与学生问题最相关的参考片段的【编号】。挑选数量最多为 {top_k} 个。\n"
            "必须严格按照与问题的相关度由高到低降序排列，优先推荐最相关的编号。\n"
            "【输出格式要求】:\n"
            "你必须只输出一个有效的 JSON 数组，包含你精选出的编号（整数类型），例如: [2, 0, 4]\n"
            "请直接输出该 JSON 数组，绝不要包含任何前导、后缀或 Markdown 代码块包裹修饰词（如 ```json 等），只输出纯净的 JSON 字符串。"
        )

        try:
            # 调用全局大模型（使用 stream=False 获取完整响应）
            res = await self._ai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            content = res.choices[0].message.content.strip()
            
            # 防御式清洗 markdown 包裹语法（有些 LLM 仍会倔强输出 ```json）
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            # 解析编号数组
            indices = json.loads(content)
            if isinstance(indices, list):
                reranked = []
                seen_idx = set()
                for idx in indices:
                    try:
                        idx_int = int(idx)
                        if 0 <= idx_int < len(cand_list) and idx_int not in seen_idx:
                            seen_idx.add(idx_int)
                            reranked.append(cand_list[idx_int])
                    except (ValueError, TypeError):
                        continue
                
                # 如果挑选出的优质片段大于等于 1 个，正常返回重排后内容
                if len(reranked) >= 1:
                    return reranked[:top_k]
                    
        except Exception as e:
            logger.warning("LLM-based Rerank failed or returned invalid JSON, falling back: %s", e)
            
        # 出错或格式不匹配降级返回前 top_k 个候选
        return candidates[:top_k]

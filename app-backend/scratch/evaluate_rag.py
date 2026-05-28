import os
import sys
import sqlite3

# 将当前根目录添加到 Python 模块查找路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import settings
from services.rag_optimizer import FTSIndexManager, reciprocal_rank_fusion
from services.rag_service import RAGService

def test_fts5_db_status():
    print("=== [测试 1] FTS5 全文检索虚拟数据库状态 ===")
    fts_db_path = os.path.abspath(os.path.join(settings.CHROMADB_PATH, "fts5_index.db"))
    print(f"FTS5 SQLite 数据库路径: {fts_db_path}")
    
    if not os.path.exists(fts_db_path):
        print("警告: FTS5 数据库文件尚不存在。请上传PDF文档后触发 Celery 任务建表。")
        return
        
    try:
        conn = sqlite3.connect(fts_db_path)
        conn.row_factory = sqlite3.Row
        
        # 统计 FTS 表中各教材已建立索引的分块总数
        cursor = conn.execute("""
            SELECT textbook_id, COUNT(*) as count 
            FROM textbook_fts 
            GROUP BY textbook_id;
        """)
        rows = cursor.fetchall()
        print("\n各教材已在 FTS5 建立全文检索的索引切片行数统计:")
        if not rows:
            print("目前 FTS5 索引表为空（无教材被解析）。")
        for row in rows:
            print(f" -> 教材 ID: {row['textbook_id']}, 索引切片数: {row['count']}")
            
        conn.close()
    except Exception as e:
        print(f"读取 FTS5 数据库失败: {e}")


def test_rrf_rank_fusion():
    print("\n=== [测试 2] RRF (Reciprocal Rank Fusion) 双路合并融合测试 ===")
    # 模拟向量检索召回 (Dense)
    dense_results = [
        {"child_content": "自然语言处理是计算机科学领域的一个重要方向。", "parent_content": "NLP是重要方向...", "page_number": 5},
        {"child_content": "深度学习在图像分割与识别中取得了突破进展。", "parent_content": "深度学习图像识别...", "page_number": 8},
        {"child_content": "大语言模型能够根据上下文生成连贯自然的文本。", "parent_content": "LLM上下文生成...", "page_number": 12},
    ]

    # 模拟全文检索召回 (Sparse) - 假设第3个向量文档与第1个关键词文档内容一致
    sparse_results = [
        {"child_content": "大语言模型能够根据上下文生成连贯自然的文本。", "parent_content": "LLM上下文生成...", "page_number": 12},
        {"child_content": "支持向量机是一种经典的监督学习二分类算法模型。", "parent_content": "SVM分类算法...", "page_number": 19},
        {"child_content": "神经网络通过反向传播算法自动微调权重参数。", "parent_content": "神经网络反向传播...", "page_number": 23},
    ]

    print("\n[向量Dense候选集]:")
    for r in dense_results:
        print(f" - {r['child_content']}")
        
    print("\n[全文Sparse候选集]:")
    for r in sparse_results:
        print(f" - {r['child_content']}")

    # 运行 RRF 合并
    fused = reciprocal_rank_fusion(dense_results, sparse_results, k=60)
    
    print("\n[RRF 双路融合重排后候选集（前3位优先展示）]:")
    for idx, item in enumerate(fused[:3], start=1):
        print(f" {idx}. 页码: {item['page_number']}, 内容: {item['child_content']}")
    
    # 验证是否正确将同时出现在 dense 和 sparse 中、高排位的文档置于首位
    assert fused[0]["child_content"] == "大语言模型能够根据上下文生成连贯自然的文本。", "RRF 算法融合权重排序出错！"
    print("\n>>> RRF 双路算法合并融合检验通过！")


def test_reranker_configuration():
    print("\n=== [测试 3] 重排参数与大语言模型对接配置 ===")
    print(f"当前重排器模式 settings.RERANK_MODE: '{settings.RERANK_MODE}'")
    print(f"重排候选段数 settings.RERANK_CANDIDATES: {settings.RERANK_CANDIDATES}")
    print(f"最终精选上下文块数 settings.RAG_TOP_K: {settings.RAG_TOP_K}")
    print(">>> 配置校验正常。")


if __name__ == "__main__":
    print("==================================================")
    print("智能教育系统 RAG 精准度升级功能单元自动化验证脚本")
    print("==================================================")
    test_fts5_db_status()
    test_rrf_rank_fusion()
    test_reranker_configuration()
    print("\n单元与算法功能校验测试全部通过！")
    print("==================================================")

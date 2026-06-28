import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rag_service import RAGService
from services.ai_service import AIService
import chromadb
from core.config import settings

async def debug():
    # Let's get the last uploaded textbook ID
    from db.database import AsyncSessionLocal
    from db.models.textbook import Textbook
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Textbook).order_by(Textbook.id.desc()))
        textbook = res.scalars().first()
        if not textbook:
            print("No textbook found!")
            return
        textbook_id = textbook.id
        print(f"Debug retrieval for Textbook ID: {textbook_id} | Title: {textbook.title}")

    rag_service = RAGService()
    
    # 1. Test Query Context
    query = "书里是怎么解释Crash Consistency的呢？"
    print(f"\n--- Running query_context for: '{query}' ---")
    chunks = await rag_service.query_context(textbook_id, query)
    for i, chunk in enumerate(chunks):
        print(f"\n[Retrieved Chunk {i+1}]:\n{chunk}")

    # 2. Test ChromaDB directly
    client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
    coll_name = f"textbook_vec_{textbook_id}"
    try:
        collection = client.get_collection(name=coll_name)
        print(f"\nChromaDB collection count: {collection.count()}")
        
        # Query ChromaDB directly
        ai_service = AIService()
        q_emb = await ai_service.get_embedding(query)
        results = collection.query(query_embeddings=[q_emb], n_results=5)
        print("\n--- ChromaDB direct query results ---")
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            print(f"Page: {meta.get('page_number')} | Doc: {doc[:150]}...")
    except Exception as e:
        print(f"ChromaDB error: {e}")

    # 3. Test SQLite FTS5 directly
    from services.rag_optimizer import FTSIndexManager
    print("\n--- SQLite FTS5 direct query results ---")
    fts_results = FTSIndexManager.query_fts(textbook_id, query, limit=5)
    for r in fts_results:
        print(f"Page: {r['page_number']} | Chunk Index: {r['chunk_index']} | Doc: {r['child_content'][:150]}...")

if __name__ == "__main__":
    asyncio.run(debug())

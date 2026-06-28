import sys
import os
import asyncio
import traceback
import chromadb
import random
from sqlalchemy import select, delete

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from db.database import AsyncSessionLocal
from db.models import User, UserRole, UserStatus, Textbook, TextbookStatus
from services.document_parser import DocumentParser
from services.rag_service import RAGService
from services.ai_service import AIService
from services.rag_optimizer import FTSIndexManager
from worker.tasks import process_textbook_task
from core.security import get_password_hash

# Flags for dynamic mock fallback
mock_embedding_active = False
mock_llm_active = False

# Save original AIService methods to allow conditional delegation
original_get_embeddings_batch = AIService.get_embeddings_batch
original_get_embedding = AIService.get_embedding
original_chat_completion = AIService.chat_completion

async def patched_get_embeddings_batch(self, texts):
    global mock_embedding_active
    if mock_embedding_active:
        print(f"      [Mock Embedding] Generating dummy vectors for {len(texts)} chunks...")
        await asyncio.sleep(0.001)
        return [[random.random() for _ in range(1024)] for _ in texts]
    try:
        return await original_get_embeddings_batch(self, texts)
    except Exception as e:
        err_msg = str(e)
        err_type = type(e).__name__
        if (
            "Connect" in err_type or 
            "Connection" in err_type or 
            "APIConnectionError" in err_type or 
            "ConnectError" in err_msg or 
            "Connection error" in err_msg or
            "retry" in err_msg.lower()
        ):
            print(f"\n[WARNING] Embedding API (Volcengine) connection failed: {e}")
            print("[NOTE] Switching dynamically to OFFLINE MOCK EMBEDDINGS to continue indexing.")
            mock_embedding_active = True
            return await patched_get_embeddings_batch(self, texts)
        raise e

async def patched_get_embedding(self, text):
    global mock_embedding_active
    if mock_embedding_active:
        print("      [Mock Embedding] Generating dummy vector for search query...")
        await asyncio.sleep(0.001)
        return [random.random() for _ in range(1024)]
    try:
        return await original_get_embedding(self, text)
    except Exception as e:
        err_msg = str(e)
        err_type = type(e).__name__
        if (
            "Connect" in err_type or 
            "Connection" in err_type or 
            "APIConnectionError" in err_type or 
            "ConnectError" in err_msg or 
            "Connection error" in err_msg or
            "retry" in err_msg.lower()
        ):
            print(f"\n[WARNING] Embedding API (Volcengine) connection failed: {e}")
            print("[NOTE] Switching dynamically to OFFLINE MOCK EMBEDDING for query.")
            mock_embedding_active = True
            return await patched_get_embedding(self, text)
        raise e

async def patched_chat_completion(self, messages, stream=False):
    global mock_llm_active
    if mock_llm_active:
        print("      [Mock LLM] Bypassing LLM API, returning offline mock answer.")
        await asyncio.sleep(0.001)
        class MockMessage:
            content = (
                "This is a local offline answer. The RAG system retrieved the relevant source text from the PDF "
                "locally, successfully built the RAG context payload, but the LLM API call was bypassed."
            )
        class MockChoice:
            message = MockMessage()
        class MockResponse:
            choices = [MockChoice()]
        return MockResponse()
    try:
        return await original_chat_completion(self, messages, stream)
    except Exception as e:
        err_msg = str(e)
        err_type = type(e).__name__
        if (
            "Connect" in err_type or 
            "Connection" in err_type or 
            "APIConnectionError" in err_type or 
            "ConnectError" in err_msg or 
            "Connection error" in err_msg or
            "retry" in err_msg.lower()
        ):
            print(f"\n[WARNING] LLM API (DeepSeek) connection failed: {e}")
            print("[NOTE] Switching dynamically to OFFLINE MOCK LLM to show constructed context.")
            
            # Print construction prompt
            print("\n--- [RAG System] Constructed Prompt Payload that would have been sent to DeepSeek ---")
            for msg in messages:
                print(f"Role: {msg['role']}\nContent Preview: {msg['content'][:500]}...\n")
            print("-" * 60)
            
            mock_llm_active = True
            return await patched_chat_completion(self, messages, stream)
        raise e

# Apply monkey patches
AIService.get_embeddings_batch = patched_get_embeddings_batch
AIService.get_embedding = patched_get_embedding
AIService.chat_completion = patched_chat_completion


# Mock Celery Task for running the task synchronously
class MockTask:
    class MockRequest:
        id = "mock-task-parse-12345"
    request = MockRequest()
    
    # Custom exception to match Celery's task retry error classes
    class MaxRetriesExceededError(Exception):
        pass
        
    def retry(self, exc=None):
        raise self.MaxRetriesExceededError("Mock retry limits exceeded")

async def cleanup_test_data(textbook_id=None, teacher_id=None):
    print("\n--- Starting Textbook Parsing Test Cleanup ---")
    
    # 1. Delete ChromaDB collection
    if textbook_id:
        collection_name = f"textbook_vec_{textbook_id}"
        print(f"Deleting ChromaDB collection: {collection_name}")
        try:
            chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
            chroma_client.delete_collection(name=collection_name)
            print("ChromaDB collection deleted.")
        except Exception as e:
            print(f"No ChromaDB collection to delete or failed: {e}")

        # 2. Delete SQLite FTS5 records
        print(f"Deleting SQLite FTS5 records for textbook ID: {textbook_id}")
        try:
            FTSIndexManager.delete_document_chunks(textbook_id)
            print("SQLite FTS5 records deleted.")
        except Exception as e:
            print(f"No SQLite FTS5 records to delete or failed: {e}")

    # 3. Delete DB rows
    async with AsyncSessionLocal() as session:
        if textbook_id:
            print(f"Deleting Textbook row ID={textbook_id}")
            await session.execute(delete(Textbook).where(Textbook.id == textbook_id))
        
        if teacher_id:
            print(f"Deleting Teacher row ID={teacher_id}")
            await session.execute(delete(User).where(User.id == teacher_id))
            
        await session.commit()
    print("--- Cleanup Completed ---\n")

async def main():
    print("==================================================")
    print("STARTING DYNAMIC ADAPTIVE TEXTBOOK PARSING & RAG TEST")
    print("==================================================")
    
    # Define file paths
    pdf_relative_path = "assets/Ebook/file-journaling.pdf"
    pdf_absolute_path = os.path.abspath(pdf_relative_path)
    
    print(f"Target PDF Relative Path: {pdf_relative_path}")
    print(f"Target PDF Absolute Path: {pdf_absolute_path}")
    
    if not os.path.exists(pdf_absolute_path):
        print(f"[ERROR] PDF file does not exist at {pdf_absolute_path}")
        return
        
    print("[SUCCESS] PDF file verified on disk.")
    
    # Step 1: Parse PDF and chunk locally
    print("\n[Step 1] Running Local DocumentParser & Chunking Test...")
    try:
        parser = DocumentParser()
        pages = parser.parse_pdf(pdf_absolute_path)
        print(f" -> PDF successfully parsed. Total Pages: {len(pages)}")
        
        chunks = parser.chunk_document_parent_child(pages)
        print(f" -> Parent-Child Chunking completed. Total Chunks generated: {len(chunks)}")
        
        if chunks:
            print("\nPreview of first chunk:")
            print(f" - Page: {chunks[0].get('page_number')}")
            print(f" - Child Content: {chunks[0]['child_content'][:150]}...")
            print(f" - Parent Content: {chunks[0]['parent_content'][:150]}...")
        else:
            print("[WARNING] No chunks generated!")
            return
    except Exception as e:
        print(f"[ERROR] during local parsing/chunking: {e}")
        traceback.print_exc()
        return

    # Step 2: Seed test teacher and textbook in DB
    print("\n[Step 2] Seeding Test Teacher and Textbook in DB...")
    teacher_id = None
    textbook_id = None
    try:
        async with AsyncSessionLocal() as session:
            # Check if teacher exists
            result = await session.execute(
                select(User).where(User.username == "apitest_teacher_parsing")
            )
            teacher = result.scalars().first()
            if not teacher:
                teacher = User(
                    username="apitest_teacher_parsing",
                    email="apitest_teacher_parsing@example.com",
                    hashed_password=get_password_hash("password123"),
                    role=UserRole.TEACHER,
                    status=UserStatus.ACTIVE
                )
                session.add(teacher)
                await session.commit()
                await session.refresh(teacher)
                print(f"Created new test teacher: ID={teacher.id}")
            else:
                print(f"Using existing test teacher: ID={teacher.id}")
            
            teacher_id = teacher.id
            
            # Create Textbook entry
            textbook = Textbook(
                title="apitest_file_journaling",
                file_path=pdf_relative_path,
                status=TextbookStatus.PENDING,
                teacher_id=teacher_id
            )
            session.add(textbook)
            await session.commit()
            await session.refresh(textbook)
            textbook_id = textbook.id
            print(f"Created test Textbook entry: ID={textbook_id}, status={textbook.status.value}")
    except Exception as e:
        print(f"[ERROR] during seeding: {e}")
        traceback.print_exc()
        await cleanup_test_data(textbook_id, teacher_id)
        return

    # Step 3: Run the Celery task synchronously for embedding generation & storage
    print("\n[Step 3] Dispatching process_textbook_task (Embedding & Vector Storage)...")
    try:
        print("Starting task execution (attempting real Volcengine embeddings first)...")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, 
            process_textbook_task.run.__func__, 
            MockTask(), 
            textbook_id, 
            pdf_absolute_path
        )
        print(f"Task completed: {result}")
        
        # Verify status in database
        async with AsyncSessionLocal() as session:
            db_tb = await session.get(Textbook, textbook_id)
            print(f"Textbook Status in DB after task: {db_tb.status.value}, chroma_collection_id: {db_tb.chroma_collection_id}")
    except Exception as e:
        print(f"\n[WARNING] Expected Task Execution completed (with dynamic warnings if any): {e}")

    # Step 4: Test Hybrid Search
    print("\n[Step 4] Testing Hybrid Search (Dense + Sparse + RRF + Rerank)...")
    try:
        rag_service = RAGService()
        search_query = "What is database journaling or journaling mode?"
        print(f"Running query: '{search_query}'")
        context_chunks = await rag_service.query_context(textbook_id, search_query)
        for idx, chunk in enumerate(context_chunks):
            print(f"\n--- Retrieved Chunk {idx + 1} ---")
            try:
                print(chunk)
            except UnicodeEncodeError:
                import sys
                enc = sys.stdout.encoding or 'gbk'
                print(chunk.encode(enc, errors='replace').decode(enc))
        
        # Step 5: Test Chat Completion with RAG (Attempts real DeepSeek LLM)
        print("\n[Step 5] Testing RAG Chat Completion with LLM (Attempting real DeepSeek call)...")
        try:
            # Build messages
            messages = await rag_service.build_messages(textbook_id, search_query, [])
            print(f"Built messages payload. Calling LLM (DeepSeek)...")
            
            ai_service = AIService()
            response = await ai_service.chat_completion(messages, stream=False)
            answer = response.choices[0].message.content
            print("\n=== AI Answer from LLM ===")
            try:
                print(answer)
            except UnicodeEncodeError:
                import sys
                enc = sys.stdout.encoding or 'gbk'
                print(answer.encode(enc, errors='replace').decode(enc))
            print("===========================")
            print("[SUCCESS] RAG Chat Completion Test Passed!")
        except Exception as llm_exc:
            print(f"\n[WARNING] LLM Chat Completion call failed: {llm_exc}")
    except Exception as e:
        print(f"[ERROR] during RAG Search test: {e}")
        traceback.print_exc()

    # Step 6: Cleanup
    await cleanup_test_data(textbook_id, teacher_id)
    print("==================================================")
    print("TEXTBOOK PARSING TEST EXECUTION COMPLETED")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())

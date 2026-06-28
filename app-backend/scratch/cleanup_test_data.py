import sys
import os
import asyncio
import shutil

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import AsyncSessionLocal
from db.models import (
    User, CourseClass, Textbook, ClassTextbook, StudentClass,
    ChatSession, Message, Notification
)
from sqlalchemy import delete
from core.config import settings
import chromadb

def _cleanup_files_and_vector():
    # 1. Clear all physical files in uploads
    uploads_dirs = [
        os.path.join("uploads", "textbooks"),
        os.path.join("uploads", "credentials")
    ]
    for d in uploads_dirs:
        if os.path.exists(d):
            try:
                for filename in os.listdir(d):
                    file_path = os.path.join(d, filename)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                print(f"Cleared physical files in: {d}")
            except Exception as e:
                print(f"Failed to clear physical files in {d}: {e}")

    # 2. Delete all collections in ChromaDB
    try:
        chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
        collections = chroma_client.list_collections()
        for col in collections:
            chroma_client.delete_collection(name=col.name)
            print(f"Deleted ChromaDB collection: {col.name}")
    except Exception as e:
        print(f"ChromaDB connection or delete failed: {e}")

    # 3. Clear SQLite FTS5 database file altogether (it will be auto-recreated on next use)
    from services.rag_optimizer import FTS_DB_PATH
    if os.path.exists(FTS_DB_PATH):
        try:
            os.remove(FTS_DB_PATH)
            print(f"Deleted FTS5 database file: {FTS_DB_PATH}")
        except Exception as e:
            # If database is locked, fallback to deleting all contents inside FTS table
            print(f"FTS5 database file locked, fallback to deleting contents: {e}")
            from services.rag_optimizer import FTSIndexManager
            try:
                conn = FTSIndexManager._get_connection()
                with conn:
                    conn.execute("DELETE FROM textbook_fts;")
                conn.close()
                print("Truncated SQLite FTS5 index records successfully.")
            except Exception as fts_err:
                print(f"Failed to truncate FTS5 index: {fts_err}")

async def cleanup_db():
    print("--- Starting Force Test Data Cleanup (Truncate All Tables) ---")
    
    # Run vector and file cleanups
    _cleanup_files_and_vector()
    
    async with AsyncSessionLocal() as session:
        # Delete from all tables completely (respecting database dependencies by ordering)
        # 1. Message
        await session.execute(delete(Message))
        print("Truncated Message table.")
        
        # 2. ChatSession
        await session.execute(delete(ChatSession))
        print("Truncated ChatSession table.")
        
        # 3. StudentClass
        await session.execute(delete(StudentClass))
        print("Truncated StudentClass table.")
        
        # 4. ClassTextbook
        await session.execute(delete(ClassTextbook))
        print("Truncated ClassTextbook table.")
        
        # 5. CourseClass
        await session.execute(delete(CourseClass))
        print("Truncated CourseClass table.")
        
        # 6. Textbook
        await session.execute(delete(Textbook))
        print("Truncated Textbook table.")
        
        # 7. Notification
        await session.execute(delete(Notification))
        print("Truncated Notification table.")
        
        # 8. User
        await session.execute(delete(User))
        print("Truncated User table.")
        
        await session.commit()
    print("--- Force Test Data Cleanup Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(cleanup_db())

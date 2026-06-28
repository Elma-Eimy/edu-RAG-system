import sys
import os
import asyncio

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import AsyncSessionLocal
from db.models import (
    User, CourseClass, Textbook, ClassTextbook, StudentClass,
    ChatSession, Message, Notification
)
from sqlalchemy import delete, select
from core.config import settings
from services.rag_optimizer import FTSIndexManager
import chromadb

def _cleanup_vector_and_fts(tb_ids):
    if not tb_ids:
        return
    # 1. Delete ChromaDB collections
    try:
        chroma_client = chromadb.PersistentClient(path=settings.CHROMADB_PATH)
        for tb_id in tb_ids:
            collection_name = f"textbook_vec_{tb_id}"
            try:
                chroma_client.delete_collection(name=collection_name)
                print(f"Deleted ChromaDB collection: {collection_name}")
            except Exception:
                pass
    except Exception as e:
        print(f"ChromaDB connection failed during cleanup: {e}")

    # 2. Delete SQLite FTS5 records
    for tb_id in tb_ids:
        try:
            FTSIndexManager.delete_document_chunks(tb_id)
            print(f"Deleted SQLite FTS5 records for textbook ID: {tb_id}")
        except Exception:
            pass

async def cleanup_e2e():
    print("--- Starting E2E Test Data Cleanup ---")
    async with AsyncSessionLocal() as session:
        # Find user IDs of E2E test users containing e2e
        result = await session.execute(
            select(User.id).where(User.username.like("%e2e%"))
        )
        test_user_ids = list(result.scalars().all())
        
        if test_user_ids:
            print(f"Found {len(test_user_ids)} E2E test users to delete.")
            
            # Delete messages of sessions owned by these users
            result_sess = await session.execute(
                select(ChatSession.id).where(ChatSession.student_id.in_(test_user_ids))
            )
            test_sess_ids = list(result_sess.scalars().all())
            
            if test_sess_ids:
                await session.execute(delete(Message).where(Message.session_id.in_(test_sess_ids)))
                await session.execute(delete(ChatSession).where(ChatSession.id.in_(test_sess_ids)))
                print(f"Deleted {len(test_sess_ids)} chat sessions and their messages.")
            
            # Delete student classes
            await session.execute(delete(StudentClass).where(StudentClass.student_id.in_(test_user_ids)))
            
            # Delete textbooks uploaded by test teachers
            result_tb = await session.execute(
                select(Textbook.id).where(Textbook.teacher_id.in_(test_user_ids))
            )
            test_tb_ids = list(result_tb.scalars().all())
            
            # Delete classes created by test teachers
            result_cls = await session.execute(
                select(CourseClass.id).where(CourseClass.teacher_id.in_(test_user_ids))
            )
            test_cls_ids = list(result_cls.scalars().all())
            
            if test_cls_ids:
                await session.execute(delete(ClassTextbook).where(ClassTextbook.class_id.in_(test_cls_ids)))
                await session.execute(delete(StudentClass).where(StudentClass.class_id.in_(test_cls_ids)))
                await session.execute(delete(CourseClass).where(CourseClass.id.in_(test_cls_ids)))
                print(f"Deleted {len(test_cls_ids)} classes.")
            
            if test_tb_ids:
                _cleanup_vector_and_fts(test_tb_ids)
                await session.execute(delete(ClassTextbook).where(ClassTextbook.textbook_id.in_(test_tb_ids)))
                await session.execute(delete(Textbook).where(Textbook.id.in_(test_tb_ids)))
                print(f"Deleted {len(test_tb_ids)} textbooks.")

            # Delete notifications
            await session.execute(delete(Notification).where(
                (Notification.sender_id.in_(test_user_ids)) | (Notification.receiver_id.in_(test_user_ids))
            ))

            # Delete users
            await session.execute(delete(User).where(User.id.in_(test_user_ids)))
            print(f"Deleted E2E test users.")
        else:
            print("No E2E test users found.")
            
        await session.commit()
    print("--- E2E Test Data Cleanup Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(cleanup_e2e())

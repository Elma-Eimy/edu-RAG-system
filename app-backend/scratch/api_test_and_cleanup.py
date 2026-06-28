import sys
import os
import asyncio
import httpx

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from db.database import AsyncSessionLocal
from db.models import (
    User, UserRole, UserStatus,
    CourseClass,
    Textbook, TextbookStatus,
    ClassTextbook, StudentClass, StudentClassStatus,
    ChatSession, Message,
    Notification
)
from core.security import get_password_hash
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

async def cleanup_db():
    print("--- Starting Database Cleanup ---")
    async with AsyncSessionLocal() as session:
        # Find user IDs of test users to delete their relations cleanly
        result = await session.execute(
            select(User.id).where(User.username.like("apitest_%"))
        )
        test_user_ids = list(result.scalars().all())
        
        if test_user_ids:
            # Delete messages of sessions owned by these users
            result_sess = await session.execute(
                select(ChatSession.id).where(ChatSession.student_id.in_(test_user_ids))
            )
            test_sess_ids = list(result_sess.scalars().all())
            
            if test_sess_ids:
                await session.execute(delete(Message).where(Message.session_id.in_(test_sess_ids)))
                await session.execute(delete(ChatSession).where(ChatSession.id.in_(test_sess_ids)))
            
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
                # Delete class textbook relations
                await session.execute(delete(ClassTextbook).where(ClassTextbook.class_id.in_(test_cls_ids)))
                # Delete student classes related to these classes
                await session.execute(delete(StudentClass).where(StudentClass.class_id.in_(test_cls_ids)))
                # Delete classes
                await session.execute(delete(CourseClass).where(CourseClass.id.in_(test_cls_ids)))

            if test_tb_ids:
                _cleanup_vector_and_fts(test_tb_ids)
                await session.execute(delete(ClassTextbook).where(ClassTextbook.textbook_id.in_(test_tb_ids)))
                await session.execute(delete(Textbook).where(Textbook.id.in_(test_tb_ids)))

            # Delete notifications
            await session.execute(delete(Notification).where(
                (Notification.sender_id.in_(test_user_ids)) | (Notification.receiver_id.in_(test_user_ids))
            ))

            # Delete users
            await session.execute(delete(User).where(User.id.in_(test_user_ids)))

        # Also cleanup any books/classes/sessions starting with apitest prefix directly
        result_sess2 = await session.execute(
            select(ChatSession.id).where(ChatSession.title.like("apitest_%"))
        )
        test_sess_ids2 = list(result_sess2.scalars().all())
        if test_sess_ids2:
            await session.execute(delete(Message).where(Message.session_id.in_(test_sess_ids2)))
            await session.execute(delete(ChatSession).where(ChatSession.id.in_(test_sess_ids2)))

        result_tb2 = await session.execute(
            select(Textbook.id).where(Textbook.title.like("apitest_%"))
        )
        test_tb_ids2 = list(result_tb2.scalars().all())
        if test_tb_ids2:
            _cleanup_vector_and_fts(test_tb_ids2)
            await session.execute(delete(ClassTextbook).where(ClassTextbook.textbook_id.in_(test_tb_ids2)))
            await session.execute(delete(Textbook).where(Textbook.id.in_(test_tb_ids2)))

        result_cls2 = await session.execute(
            select(CourseClass.id).where(CourseClass.name.like("apitest_%"))
        )
        test_cls_ids2 = list(result_cls2.scalars().all())
        if test_cls_ids2:
            await session.execute(delete(ClassTextbook).where(ClassTextbook.class_id.in_(test_cls_ids2)))
            await session.execute(delete(StudentClass).where(StudentClass.class_id.in_(test_cls_ids2)))
            await session.execute(delete(CourseClass).where(CourseClass.id.in_(test_cls_ids2)))
            
        await session.commit()
    print("--- Database Cleanup Completed ---")

async def seed_admin():
    print("--- Seeding Test Admin ---")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == "apitest_admin")
        )
        admin = result.scalars().first()
        if not admin:
            admin = User(
                username="apitest_admin",
                email="apitest_admin@example.com",
                hashed_password=get_password_hash("password123"),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE
            )
            session.add(admin)
            await session.commit()
            print("Seeded test admin successfully.")
        else:
            print("Test admin already exists.")

async def run_tests():
    from core.redis import redis_client
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register Student
        print("\n1. Testing Student Registration...")
        # 先发送验证码
        await client.post("/api/v1/users/send-verification-code", json={"email": "apitest_student@example.com"})
        code_student = await redis_client.get("email_verification:apitest_student@example.com")

        reg_student_payload = {
            "username": "apitest_student",
            "email": "apitest_student@example.com",
            "password": "password123",
            "role": "student",
            "verification_code": code_student
        }
        res = await client.post("/api/v1/users/register", json=reg_student_payload)
        assert res.status_code == 201, f"Failed registration: {res.text}"
        student_data = res.json()
        print(f"Student registered: ID={student_data['id']}")

        # 2. Register Teacher
        print("\n2. Testing Teacher Registration...")
        # 先发送验证码
        await client.post("/api/v1/users/send-verification-code", json={"email": "apitest_teacher@example.com"})
        code_teacher = await redis_client.get("email_verification:apitest_teacher@example.com")

        reg_teacher_payload = {
            "username": "apitest_teacher",
            "email": "apitest_teacher@example.com",
            "password": "password123",
            "role": "teacher",
            "verification_code": code_teacher,
            "real_name": "测试教师",
            "school_name": "测试学校",
            "credential_code": "TC12345678",
            "credential_image_url": "/static/credentials/mock.png"
        }
        res = await client.post("/api/v1/users/register", json=reg_teacher_payload)
        assert res.status_code == 201, f"Failed registration: {res.text}"
        teacher_data = res.json()
        assert teacher_data["status"] == "frozen", "Teacher should be frozen upon registration"
        print(f"Teacher registered: ID={teacher_data['id']}, status=frozen")

        # 3. Log in as Teacher (should fail because frozen)
        print("\n3. Testing Login for Frozen Teacher...")
        login_payload = {
            "username": "apitest_teacher",
            "password": "password123"
        }
        res = await client.post("/api/v1/users/login/access-token", data=login_payload)
        assert res.status_code == 400, f"Expected 400 for frozen user login, got {res.status_code}"
        assert "审核中" in res.text or "冻结" in res.text, f"Unexpected error message: {res.text}"
        print("Login correctly rejected for frozen teacher.")

        # 4. Log in as Admin
        print("\n4. Testing Admin Login...")
        admin_login_payload = {
            "username": "apitest_admin",
            "password": "password123"
        }
        res = await client.post("/api/v1/users/login/access-token", data=admin_login_payload)
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        admin_token = res.json()["access_token"]
        print("Admin logged in successfully.")

        # 5. Admin approves Teacher
        print("\n5. Testing Admin Teacher Approval...")
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        res = await client.post(f"/api/v1/admin/users/{teacher_data['id']}/approve-teacher", headers=headers_admin)
        assert res.status_code == 200, f"Teacher approval failed: {res.text}"
        approved_teacher_data = res.json()
        assert approved_teacher_data["status"] == "active", "Approved teacher should be active"
        print("Teacher approved successfully.")

        # 6. Log in as approved Teacher
        print("\n6. Testing Login for Approved Teacher...")
        res = await client.post("/api/v1/users/login/access-token", data=login_payload)
        assert res.status_code == 200, f"Approved teacher login failed: {res.text}"
        teacher_token = res.json()["access_token"]
        headers_teacher = {"Authorization": f"Bearer {teacher_token}"}
        print("Teacher logged in successfully.")

        # 7. Log in as Student
        print("\n7. Testing Student Login...")
        student_login_payload = {
            "username": "apitest_student",
            "password": "password123"
        }
        res = await client.post("/api/v1/users/login/access-token", data=student_login_payload)
        assert res.status_code == 200, f"Student login failed: {res.text}"
        student_token = res.json()["access_token"]
        headers_student = {"Authorization": f"Bearer {student_token}"}
        print("Student logged in successfully.")

        # 7.1. Testing Email Login
        print("\n7.1. Testing Email Login (username/email fallback)...")
        student_email_login_payload = {
            "username": "apitest_student@example.com",
            "password": "password123"
        }
        res = await client.post("/api/v1/users/login/access-token", data=student_email_login_payload)
        assert res.status_code == 200, f"Email login failed: {res.text}"
        print("Email login verified successfully.")

        # 8. Teacher creates Class
        print("\n8. Testing Class Creation...")
        res = await client.post("/api/v1/classes/", json={"name": "apitest_class_math"}, headers=headers_teacher)
        assert res.status_code == 200, f"Class creation failed: {res.text}"
        class_data = res.json()
        class_id = class_data["id"]
        class_code = class_data["class_code"]
        print(f"Class created: ID={class_id}, code={class_code}")

        # 9. Student joins Class
        print("\n9. Testing Student Joining Class...")
        res = await client.post("/api/v1/classes/join", json={"class_code": class_code}, headers=headers_student)
        assert res.status_code == 201, f"Join class failed: {res.text}"
        join_data = res.json()
        application_id = join_data["application_id"]
        print(f"Student joined class: Application ID={application_id}")

        # 10. Student checks My Classes
        print("\n10. Testing Get My Classes list...")
        res = await client.get("/api/v1/classes/my-classes", headers=headers_student)
        assert res.status_code == 200, f"Get my classes failed: {res.text}"
        my_classes = res.json()
        matching_class = [c for c in my_classes if c["class_id"] == class_id]
        assert len(matching_class) == 1, "Class not found in student's classes list"
        assert matching_class[0]["application_status"] == "pending", "Status should be pending"
        print("Student's pending application verified in list.")

        # 11. Teacher reviews pending applications
        print("\n11. Testing Get Applications List...")
        res = await client.get(f"/api/v1/classes/{class_id}/applications?filter_status=pending", headers=headers_teacher)
        assert res.status_code == 200, f"Get applications failed: {res.text}"
        apps = res.json()
        matching_app = [a for a in apps if a["application_id"] == application_id]
        assert len(matching_app) == 1, "Application not found in teacher's pending list"
        print("Teacher retrieved pending application successfully.")

        # 12. Teacher approves Student
        print("\n12. Testing Bulk Application Review...")
        review_payload = {
            "application_ids": [application_id],
            "action": "approve"
        }
        res = await client.post(f"/api/v1/classes/{class_id}/applications/review", json=review_payload, headers=headers_teacher)
        assert res.status_code == 200, f"Review failed: {res.text}"
        assert res.json()["updated_count"] == 1
        print("Teacher approved student application.")

        # 13. Student checks My Classes again
        print("\n13. Checking Student My Classes status...")
        res = await client.get("/api/v1/classes/my-classes", headers=headers_student)
        my_classes = res.json()
        matching_class = [c for c in my_classes if c["class_id"] == class_id]
        assert matching_class[0]["application_status"] == "approved", "Status should be approved"
        print("Student status is now approved.")

        # 14. Inject dummy textbook into DB (excl. parsing)
        print("\n14. Injecting Dummy Textbook into database...")
        async with AsyncSessionLocal() as session:
            tb = Textbook(
                title="apitest_textbook_physics",
                file_path="uploads/textbooks/apitest.pdf",
                status=TextbookStatus.SUCCESS,
                chroma_collection_id="textbook_vec_apitest",
                teacher_id=teacher_data["id"]
            )
            session.add(tb)
            await session.commit()
            await session.refresh(tb)
            textbook_id = tb.id
        print(f"Dummy textbook injected: ID={textbook_id}")

        # 15. Teacher checks Textbook List
        print("\n15. Testing Teacher Textbooks List...")
        res = await client.get("/api/v1/textbooks/", headers=headers_teacher)
        assert res.status_code == 200, f"Teacher textbooks list failed: {res.text}"
        tbs = res.json()
        matching_tb = [t for t in tbs if t["id"] == textbook_id]
        assert len(matching_tb) == 1, "Textbook not found in teacher list"
        print("Teacher textbook list query verified.")

        # 16. Teacher binds Textbook to Class
        print("\n16. Testing Textbook Binding to Class...")
        bind_payload = {
            "class_ids": [class_id]
        }
        res = await client.post(f"/api/v1/textbooks/{textbook_id}/bind-classes", json=bind_payload, headers=headers_teacher)
        assert res.status_code == 200, f"Binding failed: {res.text}"
        print("Textbook bound to class successfully.")

        # 16.1 Testing Eager Load of boundClasses
        print("\n16.1 Verification of Eager Loaded boundClasses in list...")
        res = await client.get("/api/v1/textbooks/", headers=headers_teacher)
        tbs = res.json()
        matching_tb = [t for t in tbs if t["id"] == textbook_id][0]
        assert class_id in matching_tb["boundClasses"], "boundClasses list should contain the class ID"
        print("Textbook boundClasses verified in list.")

        # 17. Student checks Textbooks List (verify they have access)
        print("\n17. Testing Student Textbooks List (based on class binding)...")
        res = await client.get("/api/v1/textbooks/", headers=headers_student)
        assert res.status_code == 200, f"Student textbooks list failed: {res.text}"
        student_tbs = res.json()
        matching_student_tb = [t for t in student_tbs if t["id"] == textbook_id]
        assert len(matching_student_tb) == 1, "Student should have access to bound textbook"
        print("Student textbooks list verified.")

        # 18. Student creates Chat Session
        print("\n18. Testing Chat Session Creation...")
        session_payload = {
            "title": "apitest_session_optics",
            "textbook_id": textbook_id
        }
        res = await client.post("/api/v1/chat/sessions", json=session_payload, headers=headers_student)
        assert res.status_code == 200, f"Session creation failed: {res.text}"
        session_data = res.json()
        session_id = session_data["id"]
        print(f"Chat Session created: ID={session_id}")

        # 19. Student lists Chat Sessions
        print("\n19. Testing Student Chat Sessions Listing...")
        res = await client.get("/api/v1/chat/sessions", headers=headers_student)
        assert res.status_code == 200, f"List sessions failed: {res.text}"
        sessions_list = res.json()
        matching_sess = [s for s in sessions_list if s["id"] == session_id]
        assert len(matching_sess) == 1, "Session not found in list"
        print("Chat Sessions listing verified.")

        # 20. Student gets Session Messages
        print("\n20. Testing Student Chat Messages retrieval...")
        res = await client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers_student)
        assert res.status_code == 200, f"Get messages failed: {res.text}"
        messages_list = res.json()
        assert len(messages_list) == 0, "Expected 0 messages in new session"
        print("Chat messages retrieval verified (0 messages).")

        # 21. Teacher audits student session
        print("\n21. Testing Teacher Chat Audit Session list...")
        res = await client.get("/api/v1/chat/teacher/student-chats", headers=headers_teacher)
        assert res.status_code == 200, f"Audit list failed: {res.text}"
        audit_sessions = res.json()
        matching_audit = [s for s in audit_sessions if s["id"] == session_id]
        assert len(matching_audit) == 1, "Session not found in teacher audit list"
        print("Teacher audit session list verified.")

        # 22. Teacher audits student session messages
        print("\n22. Testing Teacher Chat Audit Session messages...")
        res = await client.get(f"/api/v1/chat/teacher/student-chats/{session_id}/messages", headers=headers_teacher)
        assert res.status_code == 200, f"Audit messages failed: {res.text}"
        audit_messages = res.json()
        assert len(audit_messages) == 0, "Expected 0 messages in audited session"
        print("Teacher audit messages retrieval verified.")

        # 23. Testing Unbinding (checklist uncheck synchronization)
        print("\n23. Testing Class Unbinding (checking checklist uncheck synchronization)...")
        unbind_payload = {
            "class_ids": [] # Uncheck all classes
        }
        res = await client.post(f"/api/v1/textbooks/{textbook_id}/bind-classes", json=unbind_payload, headers=headers_teacher)
        assert res.status_code == 200, f"Unbinding post failed: {res.text}"
        
        # Verify it's actually unbound
        res = await client.get("/api/v1/textbooks/", headers=headers_teacher)
        matching_tb = [t for t in res.json() if t["id"] == textbook_id][0]
        assert len(matching_tb["boundClasses"]) == 0, "Textbook boundClasses list should be empty after unbinding"
        print("Unbinding class synchronization verified successfully.")

        # 24. Student deletes Chat Session
        print("\n24. Testing Student Chat Session Deletion...")
        res = await client.delete(f"/api/v1/chat/sessions/{session_id}", headers=headers_student)
        assert res.status_code == 200, f"Delete session failed: {res.text}"
        
        # Check sessions list again
        res = await client.get("/api/v1/chat/sessions", headers=headers_student)
        sessions_list = res.json()
        matching_sess = [s for s in sessions_list if s["id"] == session_id]
        assert len(matching_sess) == 0, "Session should be deleted"
        print("Chat Session deletion verified successfully.")

        print("\n=== ALL TESTS PASSED SUCCESSFULLY ===")

async def main():
    try:
        # Pre-cleanup in case of leftovers
        await cleanup_db()
        # Seed test admin
        await seed_admin()
        # Run endpoints tests
        await run_tests()
    except Exception as e:
        import traceback
        print(f"\n[Error occurred during testing]: {e}")
        traceback.print_exc()
    finally:
        # Final cleanup to leave database clean
        await cleanup_db()

if __name__ == "__main__":
    asyncio.run(main())

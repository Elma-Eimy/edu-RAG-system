import sys
import os
import asyncio
import httpx
from sqlalchemy import delete, select
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from db.database import AsyncSessionLocal
from db.models import User, UserRole, UserStatus
from db.models.chat import ChatSession, Message, SenderRole
from db.models.course_class import CourseClass
from db.models.textbook import Textbook, TextbookStatus
from db.models.relations import StudentClass, ClassTextbook
from core.security import get_password_hash
from core.config import settings
from worker.tasks import summarize_chat_session_task

async def cleanup_db():
    print("--- Starting Database Cleanup ---")
    async with AsyncSessionLocal() as session:
        # Delete messages and sessions
        await session.execute(delete(Message))
        await session.execute(delete(ChatSession))
        
        # Delete class-textbook bindings and student class links
        await session.execute(delete(ClassTextbook))
        await session.execute(delete(StudentClass))
        
        # Delete test textbooks, classes, and users
        await session.execute(delete(Textbook).where(Textbook.title.like("sumtest_%")))
        await session.execute(delete(CourseClass).where(CourseClass.name.like("sumtest_%")))
        await session.execute(delete(User).where(User.username.like("sumtest_%")))
        
        await session.commit()
    print("--- Database Cleanup Completed ---")

async def seed_data():
    print("--- Seeding Test Data ---")
    async with AsyncSessionLocal() as session:
        # 1. Create Teacher
        teacher = User(
            username="sumtest_teacher",
            email="sumtest_teacher@example.com",
            hashed_password=get_password_hash("password123"),
            role=UserRole.TEACHER,
            status=UserStatus.ACTIVE
        )
        session.add(teacher)
        await session.flush()
        
        # 2. Create Student
        student = User(
            username="sumtest_student",
            email="sumtest_student@example.com",
            hashed_password=get_password_hash("password123"),
            role=UserRole.STUDENT,
            status=UserStatus.ACTIVE
        )
        session.add(student)
        await session.flush()

        # 3. Create Class
        course_class = CourseClass(
            name="sumtest_class",
            class_code="SUM123",
            teacher_id=teacher.id
        )
        session.add(course_class)
        await session.flush()

        # 4. Approve Student in Class
        link = StudentClass(
            student_id=student.id,
            class_id=course_class.id,
            status=UserStatus.ACTIVE # APPROVED
        )
        # Note: StudentClass model uses StudentClassStatus.APPROVED. In our db, APPROVED is equivalent to active or similar.
        from db.models.relations import StudentClassStatus
        link.status = StudentClassStatus.APPROVED
        session.add(link)
        await session.flush()

        # 5. Create Textbook (set to SUCCESS status)
        textbook = Textbook(
            title="sumtest_textbook",
            file_path="uploads/textbooks/sum_test.pdf",
            status=TextbookStatus.SUCCESS,
            teacher_id=teacher.id
        )
        session.add(textbook)
        await session.flush()

        # 6. Bind Textbook to Class
        binding = ClassTextbook(
            class_id=course_class.id,
            textbook_id=textbook.id
        )
        session.add(binding)
        
        await session.commit()
        print("Seeded test users, class, student enrollment, and textbook successfully.")

async def run_tests():
    # Force history summary enabling for testing triggers
    settings.ENABLE_HISTORY_SUMMARY = True

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Authenticate student
        res = await client.post("/api/v1/users/login/access-token", data={"username": "sumtest_student", "password": "password123"})
        student_token = res.json()["access_token"]
        headers_student = {"Authorization": f"Bearer {student_token}"}

        # Authenticate teacher
        res = await client.post("/api/v1/users/login/access-token", data={"username": "sumtest_teacher", "password": "password123"})
        teacher_token = res.json()["access_token"]
        headers_teacher = {"Authorization": f"Bearer {teacher_token}"}

        # Get Textbook ID
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Textbook).where(Textbook.title == "sumtest_textbook"))
            textbook_id = result.scalars().first().id

        # ---------------------------------------------------------------------
        # 1. Create Chat Session
        # ---------------------------------------------------------------------
        print("\n1. Creating chat session...")
        res = await client.post("/api/v1/chat/sessions", json={"title": "Test Chat", "textbook_id": textbook_id}, headers=headers_student)
        assert res.status_code == 200
        session_id = res.json()["id"]
        print(f"Chat session created: ID={session_id}")

        # ---------------------------------------------------------------------
        # 2. Test Stream Completion and Automatic Summary Trigger (Threshold = 2)
        # ---------------------------------------------------------------------
        print("\n2. Simulating full SSE chat interaction...")
        chat_payload = {
            "session_id": session_id,
            "content": "你好，请简单回答我。",
            "reasoning": False
        }
        # Consume the stream
        async with client.stream("POST", "/api/v1/chat/stream", json=chat_payload, headers=headers_student) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                pass # Consume stream completely

        # Wait a short moment to allow async flow to settle
        await asyncio.sleep(0.5)

        # Check that the AI reply is in the database
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Message).where(Message.session_id == session_id))
            messages = result.scalars().all()
            # There should be 2 messages: 1 user, 1 AI
            assert len(messages) == 2, f"Expected 2 messages in DB, found {len(messages)}"
            print(f"Verified: 2 messages saved in DB (1 User, 1 AI).")

        # 在异步 session 块外执行同步任务
        summarize_chat_session_task(session_id)
        
        # 另起一个全新的 session 来读取和校验摘要
        async with AsyncSessionLocal() as verify_session:
            result_sess = await verify_session.execute(select(ChatSession).where(ChatSession.id == session_id))
            session_obj = result_sess.scalars().first()
            assert session_obj.summary is not None, "Summary is None! It was skipped despite having 2 messages."
            print(f"Verified: Summary successfully generated for 2-message (1-round) session: {session_obj.summary}")

        # ---------------------------------------------------------------------
        # 3. Test Stream Interruption (Client Disconnect / Cancel)
        # ---------------------------------------------------------------------
        print("\n3. Simulating client stream interruption...")
        # Create a new session
        res = await client.post("/api/v1/chat/sessions", json={"title": "Test Chat Interrupted", "textbook_id": textbook_id}, headers=headers_student)
        assert res.status_code == 200
        session_id_int = res.json()["id"]

        chat_payload_int = {
            "session_id": session_id_int,
            "content": "你好，我想测试流中断场景。",
            "reasoning": False
        }

        # ── Monkeypatch AIService.chat_completion to return a slow stream ────
        from services.ai_service import AIService
        original_chat_completion = AIService.chat_completion

        class MockDelta:
            def __init__(self, content):
                self.content = content
                self.reasoning_content = None

        class MockChoice:
            def __init__(self, content):
                self.delta = MockDelta(content)

        class MockChunk:
            def __init__(self, content):
                self.choices = [MockChoice(content)]

        class SlowMockIterator:
            def __init__(self):
                self.chunks = [
                    MockChunk("你好，"),
                    MockChunk("这是一个"),
                    MockChunk("被中"),
                    MockChunk("断的流测试。"),
                ]
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index == 2:
                    # 模拟客户端连接断开，抛出 CancelledError
                    raise asyncio.CancelledError()
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                chunk = self.chunks[self.index]
                self.index += 1
                await asyncio.sleep(0.5)  # 延迟以确保客户端有机会断开连接
                return chunk

        async def mock_chat_completion(self, *args, **kwargs):
            if kwargs.get("stream"):
                return SlowMockIterator()
            return await original_chat_completion(self, *args, **kwargs)

        AIService.chat_completion = mock_chat_completion

        # Request stream but disconnect immediately after the first data chunk is received
        try:
            async with client.stream("POST", "/api/v1/chat/stream", json=chat_payload_int, headers=headers_student) as response:
                assert response.status_code == 200
                async for line in response.aiter_lines():
                    if line.strip().startswith("data:"):
                        # Disconnect immediately by breaking out of stream consumption loop
                        print("Disconnected client mid-stream.")
                        break
        except Exception as e:
            print(f"Stream connection closed: {e}")
        finally:
            AIService.chat_completion = original_chat_completion

        # Wait for finally block to execute
        await asyncio.sleep(0.5)

        # Check DB to verify that the partial AI message was saved with the interruption suffix
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Message).where(
                    Message.session_id == session_id_int, 
                    Message.sender == SenderRole.AI
                )
            )
            ai_msg = result.scalars().first()
            assert ai_msg is not None, "Partial AI message was NOT saved in database!"
            assert "[*回复因连接断开而中断*]" in ai_msg.content, f"Interrupted reply content incorrect: {ai_msg.content}"
            print("Verified: Interrupted partial AI message saved with connection loss suffix.")

        # 在 session 块外执行同步任务
        summarize_chat_session_task(session_id_int)

        # 另起一个全新的 session 来读取和校验摘要
        async with AsyncSessionLocal() as verify_session:
            result_sess = await verify_session.execute(select(ChatSession).where(ChatSession.id == session_id_int))
            session_obj = result_sess.scalars().first()
            assert session_obj.summary is not None, "Summary was not generated for interrupted session!"
            print(f"Verified: Summary successfully generated for interrupted session: {session_obj.summary}")

        # ---------------------------------------------------------------------
        # 4. Test Teacher Manual Summarize Trigger (Force summary)
        # ---------------------------------------------------------------------
        print("\n4. Testing Teacher Manual Summarize Trigger...")
        # Create a new session with NO messages
        res = await client.post("/api/v1/chat/sessions", json={"title": "Test Chat Manual", "textbook_id": textbook_id}, headers=headers_student)
        assert res.status_code == 200
        session_id_man = res.json()["id"]

        # Call summarize directly (should trigger the endpoint successfully)
        # Since there are no messages, Celery task has `len(messages) == 0` which skips,
        # but let's add 1 message (User only, no AI reply) to test the `force=True` threshold bypass!
        async with AsyncSessionLocal() as session:
            user_msg = Message(
                session_id=session_id_man,
                sender=SenderRole.USER,
                content="学生发起提问，但AI因故障完全未回复。"
            )
            session.add(user_msg)
            await session.commit()

        # If we run regular summarize_chat_session_task, it has only 1 message (User), which is < 2, so it will skip.
        # Let's verify it skips:
        async with AsyncSessionLocal() as session:
            summarize_chat_session_task(session_id_man)
            result_sess = await session.execute(select(ChatSession).where(ChatSession.id == session_id_man))
            session_obj = result_sess.scalars().first()
            assert session_obj.summary is None, "Regular summary run should have skipped 1-message session!"
            print("Verified: Regular summary task run correctly skipped 1-message session.")

        # Now, call the new teacher endpoint to manually trigger a summary refresh
        print("Calling teacher manual summarize endpoint...")
        sum_res = await client.post(
            f"/api/v1/chat/teacher/student-chats/{session_id_man}/summarize",
            headers=headers_teacher
        )
        assert sum_res.status_code == 200
        print(f"Teacher endpoint response: {sum_res.json()['message']}")

        # Verify that running the task with `force=True` successfully generates a summary
        # despite having only 1 message (threshold bypass)
        summarize_chat_session_task(session_id_man, force=True)
        async with AsyncSessionLocal() as session:
            result_sess = await session.execute(select(ChatSession).where(ChatSession.id == session_id_man))
            session_obj = result_sess.scalars().first()
            assert session_obj.summary is not None, "Summary not generated despite force=True override!"
            print(f"Verified: Forced summary successfully generated for 1-message session: {session_obj.summary}")

    print("\n=== ALL SUMMARY IMPROVEMENT TESTS PASSED SUCCESSFULLY ===")

async def main():
    await cleanup_db()
    await seed_data()
    
    # Mock Celery delay to prevent hanging when Redis is down
    from worker.tasks import summarize_chat_session_task
    original_delay = summarize_chat_session_task.delay
    summarize_chat_session_task.delay = lambda *args, **kwargs: None
    
    try:
        await run_tests()
    finally:
        summarize_chat_session_task.delay = original_delay
        await cleanup_db()

if __name__ == "__main__":
    asyncio.run(main())

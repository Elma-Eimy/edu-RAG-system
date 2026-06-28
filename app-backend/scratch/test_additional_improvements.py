import sys
import os
import asyncio
import httpx
from sqlalchemy import delete, select

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from db.database import AsyncSessionLocal
from db.models import User, UserRole, UserStatus
from db.models.course_class import CourseClass
from db.models.textbook import Textbook, TextbookStatus
from db.models.relations import StudentClass, ClassTextbook
from db.models.notification import Notification
from core.security import get_password_hash
from core.redis import redis_client

async def cleanup_db():
    print("--- Starting Database Cleanup ---")
    async with AsyncSessionLocal() as session:
        # Delete test notifications
        await session.execute(delete(Notification))
        
        # Delete class-textbook bindings
        await session.execute(delete(ClassTextbook))
        
        # Delete student-class links
        await session.execute(delete(StudentClass))
        
        # Delete test textbooks
        await session.execute(delete(Textbook).where(Textbook.title.like("notiftest_%")))
        
        # Delete test classes
        await session.execute(delete(CourseClass).where(CourseClass.name.like("notiftest_%")))
        
        # Delete test users
        await session.execute(delete(User).where(User.username.like("notiftest_%")))
        
        await session.commit()
    print("--- Database Cleanup Completed ---")

async def seed_data():
    print("--- Seeding Test Data ---")
    async with AsyncSessionLocal() as session:
        # 1. Create Teacher
        teacher = User(
            username="notiftest_teacher",
            email="notiftest_teacher@example.com",
            hashed_password=get_password_hash("password123"),
            role=UserRole.TEACHER,
            status=UserStatus.ACTIVE
        )
        session.add(teacher)
        await session.flush()
        
        # 2. Create Class for Teacher
        course_class = CourseClass(
            name="notiftest_class",
            class_code="NTF123",
            teacher_id=teacher.id
        )
        session.add(course_class)
        await session.flush()
        
        # 3. Create Textbook for Teacher (set to SUCCESS status)
        textbook = Textbook(
            title="notiftest_textbook",
            file_path="uploads/textbooks/notif_test.pdf",
            status=TextbookStatus.SUCCESS,
            teacher_id=teacher.id
        )
        session.add(textbook)
        
        await session.commit()
        print("Seeded test teacher, class, and textbook successfully.")

async def run_tests():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ---------------------------------------------------------------------
        # 1. Register Student
        # ---------------------------------------------------------------------
        print("\n1. Registering test student...")
        await client.post("/api/v1/users/send-verification-code", json={"email": "notiftest_student@example.com"})
        code = await redis_client.get("email_verification:notiftest_student@example.com")
        assert code is not None
        
        reg_payload = {
            "username": "notiftest_student",
            "email": "notiftest_student@example.com",
            "password": "password123",
            "role": "student",
            "verification_code": code
        }
        res = await client.post("/api/v1/users/register", json=reg_payload)
        assert res.status_code == 201
        student_data = res.json()
        print("Student registered successfully.")

        # Authenticate student
        res = await client.post("/api/v1/users/login/access-token", data={"username": "notiftest_student", "password": "password123"})
        assert res.status_code == 200
        student_token = res.json()["access_token"]
        headers_student = {"Authorization": f"Bearer {student_token}"}

        # Authenticate teacher
        res = await client.post("/api/v1/users/login/access-token", data={"username": "notiftest_teacher", "password": "password123"})
        assert res.status_code == 200
        teacher_token = res.json()["access_token"]
        headers_teacher = {"Authorization": f"Bearer {teacher_token}"}

        # ---------------------------------------------------------------------
        # 2. Test Student Joins Class -> Teacher gets notification
        # ---------------------------------------------------------------------
        print("\n2. Student applying to join class...")
        join_res = await client.post("/api/v1/classes/join", json={"class_code": "NTF123"}, headers=headers_student)
        assert join_res.status_code == 201
        app_id = join_res.json()["application_id"]
        
        # Check teacher notifications
        notif_res = await client.get("/api/v1/notifications", headers=headers_teacher)
        assert notif_res.status_code == 200
        notifs = notif_res.json()
        assert len(notifs) >= 1, "Teacher did not receive join class notification!"
        join_notif = next((n for n in notifs if "申请加入您的班级" in n["content"]), None)
        assert join_notif is not None
        assert join_notif["title"] == "新的入班申请"
        print("Verified: Teacher successfully received class join notification.")

        # ---------------------------------------------------------------------
        # 3. Test Teacher Approves Application -> Student gets notification
        # ---------------------------------------------------------------------
        print("\n3. Teacher approving class application...")
        class_id = join_res.json()["class_id"]
        review_payload = {
            "application_ids": [app_id],
            "action": "approve"
        }
        review_res = await client.post(f"/api/v1/classes/{class_id}/applications/review", json=review_payload, headers=headers_teacher)
        assert review_res.status_code == 200
        assert review_res.json()["updated_count"] == 1

        # Check student notifications
        notif_res = await client.get("/api/v1/notifications", headers=headers_student)
        assert notif_res.status_code == 200
        student_notifs = notif_res.json()
        assert len(student_notifs) >= 1, "Student did not receive approval notification!"
        approve_notif = next((n for n in student_notifs if "已被教师同意" in n["content"]), None)
        assert approve_notif is not None
        assert approve_notif["title"] == "入班申请审核结果"
        print("Verified: Student successfully received approval notification.")

        # ---------------------------------------------------------------------
        # 4. Test Teacher Binds Textbook -> Student gets notification
        # ---------------------------------------------------------------------
        print("\n4. Teacher binding textbook to class...")
        # Get textbook ID
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Textbook).where(Textbook.title == "notiftest_textbook"))
            textbook_obj = result.scalars().first()
            textbook_id = textbook_obj.id

        bind_res = await client.post(
            f"/api/v1/textbooks/{textbook_id}/bind-classes",
            json={"class_ids": [class_id]},
            headers=headers_teacher
        )
        assert bind_res.status_code == 200
        assert bind_res.json()["bound_count"] == 1

        # Check student notifications again
        notif_res = await client.get("/api/v1/notifications", headers=headers_student)
        student_notifs = notif_res.json()
        bind_notif = next((n for n in student_notifs if "新上架了教材" in n["content"]), None)
        assert bind_notif is not None, "Student did not receive textbook binding notification!"
        assert bind_notif["title"] == "新教材上架通知"
        print("Verified: Student successfully received textbook binding notification.")

        # ---------------------------------------------------------------------
        # 5. Test Password Reset via OTP Code
        # ---------------------------------------------------------------------
        print("\n5. Testing password reset flow...")
        # Send reset code
        reset_otp_res = await client.post("/api/v1/users/send-reset-code", json={"email": "notiftest_student@example.com"})
        assert reset_otp_res.status_code == 200
        
        reset_code = await redis_client.get("email_verification:notiftest_student@example.com")
        assert reset_code is not None
        print(f"Retrieved password reset code: {reset_code}")

        # Reset password
        reset_res = await client.post("/api/v1/users/reset-password", json={
            "email": "notiftest_student@example.com",
            "verification_code": reset_code,
            "new_password": "newpassword123"
        })
        assert reset_res.status_code == 200
        print("Password reset successful.")

        # Test login with old password (should fail)
        login_res = await client.post("/api/v1/users/login/access-token", data={"username": "notiftest_student", "password": "password123"})
        assert login_res.status_code == 400
        
        # Test login with new password (should succeed)
        login_res = await client.post("/api/v1/users/login/access-token", data={"username": "notiftest_student", "password": "newpassword123"})
        assert login_res.status_code == 200
        student_token = login_res.json()["access_token"]
        headers_student = {"Authorization": f"Bearer {student_token}"}
        print("Verified login with newly reset password.")

        # ---------------------------------------------------------------------
        # 6. Test Password Change (Authenticated)
        # ---------------------------------------------------------------------
        print("\n6. Testing authenticated password change...")
        change_res = await client.post("/api/v1/users/change-password", json={
            "old_password": "newpassword123",
            "new_password": "finalpassword123"
        }, headers=headers_student)
        assert change_res.status_code == 200
        print("Password change successful.")

        # Test login with old password (should fail)
        login_res = await client.post("/api/v1/users/login/access-token", data={"username": "notiftest_student", "password": "newpassword123"})
        assert login_res.status_code == 400

        # Test login with final password (should succeed)
        login_res = await client.post("/api/v1/users/login/access-token", data={"username": "notiftest_student", "password": "finalpassword123"})
        assert login_res.status_code == 200
        print("Verified login with newly changed password.")

    print("\n=== ALL ADDITIONAL TESTS PASSED SUCCESSFULLY ===")

async def main():
    await cleanup_db()
    await seed_data()
    try:
        await run_tests()
    finally:
        await cleanup_db()

if __name__ == "__main__":
    asyncio.run(main())

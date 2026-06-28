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
from core.security import get_password_hash
from core.redis import redis_client

async def cleanup_db():
    print("--- Starting Database Cleanup ---")
    async with AsyncSessionLocal() as session:
        # Delete test users
        await session.execute(
            delete(User).where(User.username.like("regtest_%"))
        )
        await session.commit()
    print("--- Database Cleanup Completed ---")

async def seed_admin():
    print("--- Seeding Test Admin ---")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == "regtest_admin")
        )
        admin = result.scalars().first()
        if not admin:
            admin = User(
                username="regtest_admin",
                email="regtest_admin@example.com",
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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # =====================================================================
        # 1. SEND OTP CODE
        # =====================================================================
        print("\n1. Testing OTP Code Sending...")
        otp_payload = {
            "email": "regtest_student@example.com"
        }
        res = await client.post("/api/v1/users/send-verification-code", json=otp_payload)
        assert res.status_code == 200, f"Failed to send code: {res.text}"
        print("OTP code request sent successfully.")

        # Read the code directly from Redis
        redis_key = "email_verification:regtest_student@example.com"
        verification_code = await redis_client.get(redis_key)
        assert verification_code is not None, "Verification code not found in Redis!"
        print(f"Retrieved code from Redis: {verification_code}")

        # =====================================================================
        # 2. STUDENT REGISTRATION - MISSING CODE (422)
        # =====================================================================
        print("\n2. Testing Student Registration (Missing Code)...")
        reg_payload = {
            "username": "regtest_student",
            "email": "regtest_student@example.com",
            "password": "password123",
            "role": "student"
        }
        res = await client.post("/api/v1/users/register", json=reg_payload)
        assert res.status_code == 422, f"Expected 422 for missing code, got {res.status_code}"
        print("Registration correctly blocked due to missing validation field.")

        # =====================================================================
        # 3. STUDENT REGISTRATION - WRONG CODE (400)
        # =====================================================================
        print("\n3. Testing Student Registration (Wrong Code)...")
        reg_payload["verification_code"] = "000000"
        res = await client.post("/api/v1/users/register", json=reg_payload)
        assert res.status_code == 400, f"Expected 400 for wrong code, got {res.status_code}"
        assert "验证码输入错误" in res.text, f"Unexpected error: {res.text}"
        print("Registration correctly blocked due to invalid OTP code.")

        # =====================================================================
        # 4. STUDENT REGISTRATION - SUCCESS (201)
        # =====================================================================
        print("\n4. Testing Student Registration (Success)...")
        reg_payload["verification_code"] = verification_code
        res = await client.post("/api/v1/users/register", json=reg_payload)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        student_data = res.json()
        assert student_data["username"] == "regtest_student"
        print(f"Student registered successfully: ID={student_data['id']}")

        # Verify Redis key is deleted
        code_after = await redis_client.get(redis_key)
        assert code_after is None, "Verification code not cleaned up from Redis!"
        print("Verified Redis OTP code was cleaned up post-registration.")

        # =====================================================================
        # 4.1. USERNAME FORMAT VALIDATION - EMAIL (422)
        # =====================================================================
        print("\n4.1. Testing Username Format (Email Format Blocked)...")
        # Send code to test email format registration
        await client.post("/api/v1/users/send-verification-code", json={"email": "regtest_collision1@example.com"})
        col_code = await redis_client.get("email_verification:regtest_collision1@example.com")
        
        reg_col_payload = {
            "username": "collision@example.com",
            "email": "regtest_collision1@example.com",
            "password": "password123",
            "role": "student",
            "verification_code": col_code
        }
        res = await client.post("/api/v1/users/register", json=reg_col_payload)
        assert res.status_code == 422, f"Expected 422 for email-like username, got {res.status_code}: {res.text}"
        assert "不能包含 '@'" in res.text, f"Unexpected error: {res.text}"
        print("Username in email format was correctly blocked by Pydantic validation.")

        # =====================================================================
        # 4.2. USERNAME FORMAT VALIDATION - SPECIAL CHARACTERS (422)
        # =====================================================================
        print("\n4.2. Testing Username Format (Special Characters Blocked)...")
        reg_col_payload["username"] = "collision space"
        res = await client.post("/api/v1/users/register", json=reg_col_payload)
        assert res.status_code == 422, f"Expected 422 for special chars, got {res.status_code}: {res.text}"
        assert "仅支持英文字母" in res.text, f"Unexpected error: {res.text}"
        print("Username with special characters/spaces was correctly blocked.")

        # =====================================================================
        # 4.3. CASE-INSENSITIVE USERNAME COLLISION (400)
        # =====================================================================
        print("\n4.3. Testing Case-Insensitive Username Collision...")
        # Since 'regtest_student' is registered, try to register 'RegTest_Student' (with different email)
        await client.post("/api/v1/users/send-verification-code", json={"email": "regtest_collision2@example.com"})
        col_code2 = await redis_client.get("email_verification:regtest_collision2@example.com")
        
        reg_col_payload2 = {
            "username": "RegTest_Student",
            "email": "regtest_collision2@example.com",
            "password": "password123",
            "role": "student",
            "verification_code": col_code2
        }
        res = await client.post("/api/v1/users/register", json=reg_col_payload2)
        assert res.status_code == 400, f"Expected 400 for duplicate case-insensitive username, got {res.status_code}: {res.text}"
        assert "该用户名已被注册" in res.text
        print("Case-insensitive duplicate username registration was correctly blocked.")

        # =====================================================================
        # 5. TEACHER REGISTRATION - OTP & MISSING QUALIFICATIONS (400)
        # =====================================================================
        print("\n5. Testing Teacher Registration (Missing Qualifications)...")
        # Send code to teacher email
        otp_payload_teacher = {"email": "regtest_teacher@example.com"}
        await client.post("/api/v1/users/send-verification-code", json=otp_payload_teacher)
        teacher_code = await redis_client.get("email_verification:regtest_teacher@example.com")
        assert teacher_code is not None
        
        reg_teacher_payload = {
            "username": "regtest_teacher",
            "email": "regtest_teacher@example.com",
            "password": "password123",
            "role": "teacher",
            "verification_code": teacher_code
        }
        res = await client.post("/api/v1/users/register", json=reg_teacher_payload)
        assert res.status_code == 400, f"Expected 400 for missing credentials, got {res.status_code}"
        assert "教师注册必须填写真实姓名" in res.text, f"Unexpected error: {res.text}"
        print("Teacher registration correctly blocked due to missing qualification fields.")

        # =====================================================================
        # 6. TEACHER REGISTRATION - SUCCESS (201)
        # =====================================================================
        print("\n6. Testing Teacher Registration (Success)...")
        reg_teacher_payload.update({
            "real_name": "张老师",
            "school_name": "实验一小",
            "credential_code": "T-2026-9999",
            "credential_image_url": "http://test-server/uploads/credentials/cert.jpg"
        })
        res = await client.post("/api/v1/users/register", json=reg_teacher_payload)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        teacher_data = res.json()
        assert teacher_data["status"] == "frozen", "Newly registered teacher must be frozen"
        assert teacher_data["real_name"] == "张老师"
        assert teacher_data["school_name"] == "实验一小"
        assert teacher_data["credential_code"] == "T-2026-9999"
        assert teacher_data["credential_image_url"] == "http://test-server/uploads/credentials/cert.jpg"
        print(f"Teacher registered successfully and set to FROZEN: ID={teacher_data['id']}")

        # =====================================================================
        # 7. ADMIN AUDIT VIEW
        # =====================================================================
        print("\n7. Testing Admin Audit Visibility...")
        # Login as Admin
        admin_login = {
            "username": "regtest_admin",
            "password": "password123"
        }
        login_res = await client.post("/api/v1/users/login/access-token", data=admin_login)
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        admin_token = login_res.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # Fetch users
        users_res = await client.get("/api/v1/admin/users", headers=headers_admin)
        assert users_res.status_code == 200
        users_list = users_res.json()
        
        # Find the registered teacher in the admin user list
        audit_teacher = next((u for u in users_list if u["id"] == teacher_data["id"]), None)
        assert audit_teacher is not None, "Teacher not found in admin user list"
        assert audit_teacher["real_name"] == "张老师", "Admin cannot see teacher's real name"
        assert audit_teacher["school_name"] == "实验一小", "Admin cannot see teacher's school name"
        assert audit_teacher["credential_code"] == "T-2026-9999", "Admin cannot see teacher's credential code"
        assert audit_teacher["credential_image_url"] is not None, "Admin cannot see teacher's credential image URL"
        print("Verified admin can fully inspect teacher qualification details.")

        # =====================================================================
        # 8. ADMIN APPROVE TEACHER
        # =====================================================================
        print("\n8. Testing Admin Teacher Approval...")
        approve_res = await client.post(
            f"/api/v1/admin/users/{teacher_data['id']}/approve-teacher",
            headers=headers_admin
        )
        assert approve_res.status_code == 200, f"Approve teacher failed: {approve_res.text}"
        approved_data = approve_res.json()
        assert approved_data["status"] == "active", "Approved teacher should be active"
        print("Verified admin can successfully approve and activate the teacher.")

    print("\n=== ALL TESTS PASSED SUCCESSFULLY ===")

async def main():
    await cleanup_db()
    await seed_admin()
    try:
        await run_tests()
    finally:
        await cleanup_db()

if __name__ == "__main__":
    asyncio.run(main())

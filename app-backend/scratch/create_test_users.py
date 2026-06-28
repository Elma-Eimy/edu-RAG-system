import sys
import os
import asyncio

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import AsyncSessionLocal
from db.models.user import User, UserRole, UserStatus
from core.security import get_password_hash
from sqlalchemy import select

async def create_users():
    print("--- Starting One-Click Test User Creation ---")
    
    users_to_create = [
        {
            "username": "apitest_student",
            "email": "apitest_student@example.com",
            "role": UserRole.STUDENT,
            "status": UserStatus.ACTIVE
        },
        {
            "username": "apitest_teacher",
            "email": "apitest_teacher@example.com",
            "role": UserRole.TEACHER,
            "status": UserStatus.ACTIVE
        },
        {
            "username": "apitest_admin",
            "email": "apitest_admin@example.com",
            "role": UserRole.ADMIN,
            "status": UserStatus.ACTIVE
        }
    ]
    
    password = "password123"
    hashed_password = get_password_hash(password)
    
    async with AsyncSessionLocal() as session:
        for u_data in users_to_create:
            # Check if user already exists
            result = await session.execute(
                select(User).where(User.username == u_data["username"])
            )
            user = result.scalars().first()
            
            if user:
                print(f"[SKIP] User '{u_data['username']}' already exists.")
            else:
                new_user = User(
                    username=u_data["username"],
                    email=u_data["email"],
                    hashed_password=hashed_password,
                    role=u_data["role"],
                    status=u_data["status"]
                )
                session.add(new_user)
                print(f"[CREATE] Created user '{u_data['username']}' with role '{u_data['role'].value}' and password '{password}'")
        
        await session.commit()
    print("--- Test User Creation Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(create_users())

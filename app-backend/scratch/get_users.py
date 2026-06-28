import asyncio
import sys
import os

# Add parent directory to sys.path to resolve imports correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import AsyncSessionLocal
from db.models.user import User
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(f"ID: {u.id} | Username: {u.username} | Email: {u.email} | Role: {u.role.value} | Status: {u.status.value}")

if __name__ == "__main__":
    asyncio.run(main())

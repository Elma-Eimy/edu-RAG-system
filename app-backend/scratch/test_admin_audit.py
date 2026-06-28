import asyncio
import os
import sys
from sqlalchemy import select

# Add parent dir to path so we can import from app-backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import AsyncSessionLocal
from db.models import User, UserRole, UserStatus, Textbook, ChatSession, Message, SenderRole
from api.v1.endpoints.admin import list_all_textbooks, list_all_chat_sessions, get_admin_session_messages
from core.security import get_password_hash

async def run_tests():
    print("=== 开始测试新增管理员内容审计 API ===")
    async with AsyncSessionLocal() as db:
        # 1. 种子测试数据 (管理员，教师，学生，教材，会话，消息)
        # 获取或创建管理员
        admin_res = await db.execute(select(User).where(User.role == UserRole.ADMIN))
        admin = admin_res.scalars().first()
        if not admin:
            admin = User(
                username="test_audit_admin",
                email="audit_admin@example.com",
                hashed_password=get_password_hash("password123"),
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
            )
            db.add(admin)
            await db.flush()

        # 获取或创建教师
        teacher_res = await db.execute(select(User).where(User.role == UserRole.TEACHER))
        teacher = teacher_res.scalars().first()
        if not teacher:
            teacher = User(
                username="test_audit_teacher",
                email="audit_teacher@example.com",
                hashed_password=get_password_hash("password123"),
                role=UserRole.TEACHER,
                status=UserStatus.ACTIVE,
            )
            db.add(teacher)
            await db.flush()

        # 获取或创建学生
        student_res = await db.execute(select(User).where(User.role == UserRole.STUDENT))
        student = student_res.scalars().first()
        if not student:
            student = User(
                username="test_audit_student",
                email="audit_student@example.com",
                hashed_password=get_password_hash("password123"),
                role=UserRole.STUDENT,
                status=UserStatus.ACTIVE,
            )
            db.add(student)
            await db.flush()

        # 获取或创建教材
        tb_res = await db.execute(select(Textbook).where(Textbook.title == "审计测试教材"))
        tb = tb_res.scalars().first()
        if not tb:
            tb = Textbook(
                title="审计测试教材",
                file_path="uploads/test_audit.pdf",
                teacher_id=teacher.id,
            )
            db.add(tb)
            await db.flush()

        # 创建会话
        session = ChatSession(
            title="审计测试对话",
            student_id=student.id,
            textbook_id=tb.id,
            summary="这是一段测试摘要",
        )
        db.add(session)
        await db.flush()

        # 创建消息
        msg1 = Message(
            session_id=session.id,
            sender=SenderRole.USER,
            content="管理员能看到我发的消息吗？",
        )
        msg2 = Message(
            session_id=session.id,
            sender=SenderRole.AI,
            content="可以的，管理员有全局审计权限。",
            reasoning_content="开始检索数据库... 检索到管理员权限列表。",
        )
        db.add_all([msg1, msg2])
        await db.commit()

        print(f"数据播种完成：\n - 管理员 ID: {admin.id}\n - 教材 ID: {tb.id}\n - 会话 ID: {session.id}")

        # 2. 测试 list_all_textbooks 接口
        print("\n[测试点 1] 获取全局教材审计列表...")
        tbs_list = await list_all_textbooks(db=db, _=admin)
        print(f" -> 成功获取 {len(tbs_list)} 本教材在案。")
        for t in tbs_list:
            print(f"    - ID: {t.id}, 标题: {t.title}, 状态: {t.status}, 教师: {t.teacher_name}")
        assert any(t.id == tb.id for t in tbs_list), "教材审计列表未能召回新增的测试教材！"

        # 3. 测试 list_all_chat_sessions 接口
        print("\n[测试点 2] 获取全局问答会话审计列表...")
        sessions_list = await list_all_chat_sessions(db=db, _=admin)
        print(f" -> 成功获取 {len(sessions_list)} 个会话监控。")
        for s in sessions_list:
            print(f"    - ID: {s.id}, 主题: {s.title}, 学生: {s.student_name}, 教材: {s.textbook_title}, 摘要: {s.summary}")
        assert any(s.id == session.id for s in sessions_list), "会话审计列表未能召回新增的测试会话！"

        # 4. 测试 get_admin_session_messages 接口
        print(f"\n[测试点 3] 审计调阅特定会话 {session.id} 的消息明细...")
        messages_list = await get_admin_session_messages(session_id=session.id, db=db, _=admin)
        print(f" -> 成功获取该会话下的 {len(messages_list)} 条消息。")
        for m in messages_list:
            print(f"    - 发送人: {m.sender}, 内容: {m.content}")
            if m.reasoning_content:
                print(f"      [思考过程]: {m.reasoning_content}")
        assert len(messages_list) == 2, "调阅的消息条数不匹配！"

        # 5. 清理测试产生的临时会话与消息数据
        print("\n[清理阶段] 正在删除临时审计测试数据...")
        from sqlalchemy import delete
        await db.execute(delete(Message).where(Message.session_id == session.id))
        await db.execute(delete(ChatSession).where(ChatSession.id == session.id))
        await db.execute(delete(Textbook).where(Textbook.id == tb.id))
        await db.commit()
        print(">>> 临时数据清理完毕，测试大获成功！")

if __name__ == "__main__":
    asyncio.run(run_tests())

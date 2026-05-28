"""add_summary_to_chatsession

Revision ID: 2453a03fe4f4
Revises: 6757c4c6cb4b
Create Date: 2026-05-22 00:20:03.538503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# 版本标识符，由 Alembic 使用。
revision: str = '2453a03fe4f4'
down_revision: Union[str, None] = '6757c4c6cb4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Alembic 自动生成的命令 - 请根据实际情况调整！ ###
    op.add_column('chat_sessions', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('chat_sessions', sa.Column('summary_updated_at', sa.DateTime(), nullable=True))
    # ### Alembic 命令结束 ###


def downgrade() -> None:
    # ### Alembic 自动生成的命令 - 请根据实际情况调整！ ###
    op.drop_column('chat_sessions', 'summary_updated_at')
    op.drop_column('chat_sessions', 'summary')
    # ### Alembic 命令结束 ###

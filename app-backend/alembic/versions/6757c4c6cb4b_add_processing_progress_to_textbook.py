"""add processing_progress to textbook

Revision ID: 6757c4c6cb4b
Revises: 57518168d445
Create Date: 2026-05-21 23:48:21.416155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# 版本标识符，由 Alembic 使用。
revision: str = '6757c4c6cb4b'
down_revision: Union[str, None] = '57518168d445'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Alembic 自动生成的命令 - 请根据实际情况调整！ ###
    op.add_column('textbooks', sa.Column('processing_progress', sa.Integer(), nullable=False))
    # ### Alembic 命令结束 ###


def downgrade() -> None:
    # ### Alembic 自动生成的命令 - 请根据实际情况调整！ ###
    op.drop_column('textbooks', 'processing_progress')
    # ### Alembic 命令结束 ###

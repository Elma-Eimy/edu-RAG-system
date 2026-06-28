"""add_reasoning_content_to_messages

Revision ID: 849155937fba
Revises: cebd28e41249
Create Date: 2026-06-07 15:56:34.316895

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic 自动生成的版本标识符
revision: str = '849155937fba'
down_revision: Union[str, None] = 'cebd28e41249'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Alembic 自动生成命令 - 请根据需要进行调整！ ###
    op.add_column('messages', sa.Column('reasoning_content', sa.Text(), nullable=True))
    # ### 自动生成命令结束 ###


def downgrade() -> None:
    # ### Alembic 自动生成命令 - 请根据需要进行调整！ ###
    op.drop_column('messages', 'reasoning_content')
    # ### 自动生成命令结束 ###

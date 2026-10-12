"""problem language, level and starter code

Each question now belongs to one language and has a difficulty level.

Revision ID: 5b7e2f1a9c3d
Revises: c160262a9054
Create Date: 2026-10-12 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b7e2f1a9c3d'
down_revision: Union[str, Sequence[str], None] = 'c160262a9054'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('problems', sa.Column('language', sa.String(length=30), nullable=True))
    op.add_column('problems', sa.Column('level', sa.Integer(), server_default='1', nullable=False))
    op.add_column('problems', sa.Column('starter_code', sa.Text(), nullable=True))
    # Existing questions keep their first allowed language, or become Python.
    op.execute("UPDATE problems SET language = COALESCE(languages->>0, 'python')")
    op.alter_column('problems', 'language', nullable=False)
    op.create_check_constraint('ck_problems_level', 'problems', 'level BETWEEN 1 AND 4')
    op.create_index(op.f('ix_problems_language'), 'problems', ['language'], unique=False)
    op.create_index(op.f('ix_problems_level'), 'problems', ['level'], unique=False)
    op.drop_column('problems', 'languages')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('problems', sa.Column('languages', sa.JSON(), nullable=True))
    op.execute("UPDATE problems SET languages = json_build_array(language)")
    op.alter_column('problems', 'languages', nullable=False)
    op.drop_index(op.f('ix_problems_level'), table_name='problems')
    op.drop_index(op.f('ix_problems_language'), table_name='problems')
    op.drop_constraint('ck_problems_level', 'problems', type_='check')
    op.drop_column('problems', 'starter_code')
    op.drop_column('problems', 'level')
    op.drop_column('problems', 'language')

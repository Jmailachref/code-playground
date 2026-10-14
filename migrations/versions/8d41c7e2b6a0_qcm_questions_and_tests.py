"""qcm questions, level 5, approval status and per-candidate tests

Revision ID: 8d41c7e2b6a0
Revises: 5b7e2f1a9c3d
Create Date: 2026-10-14 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8d41c7e2b6a0'
down_revision: Union[str, Sequence[str], None] = '5b7e2f1a9c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('problems', sa.Column('kind', sa.String(10), nullable=False, server_default='code'))
    op.add_column('problems', sa.Column('status', sa.String(20), nullable=False, server_default='approved'))
    op.add_column('problems', sa.Column('timer_seconds', sa.Integer(), nullable=False, server_default='180'))
    op.add_column('problems', sa.Column('choices', sa.JSON(), nullable=True))
    op.add_column('problems', sa.Column('correct_choices', sa.JSON(), nullable=True))
    op.create_index('ix_problems_kind', 'problems', ['kind'])
    op.create_index('ix_problems_status', 'problems', ['status'])
    op.drop_constraint('ck_problems_level', 'problems', type_='check')
    op.create_check_constraint('ck_problems_level', 'problems', 'level BETWEEN 1 AND 5')
    op.create_check_constraint('ck_problems_kind', 'problems', "kind IN ('code', 'qcm')")
    op.create_check_constraint('ck_problems_status', 'problems', "status IN ('pending', 'approved', 'rejected')")

    op.create_table(
        'tests',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('client_id', sa.String(100), nullable=False, index=True),
        sa.Column('scope', sa.String(200), nullable=True, index=True),
        sa.Column('external_ref', sa.String(200), nullable=True, index=True),
        sa.Column('recipe', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'test_questions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('test_id', sa.Uuid(), sa.ForeignKey('tests.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('problem_id', sa.Uuid(), sa.ForeignKey('problems.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.UniqueConstraint('test_id', 'problem_id', name='uq_test_questions_problem'),
    )


def downgrade() -> None:
    op.drop_table('test_questions')
    op.drop_table('tests')
    op.execute("DELETE FROM problems WHERE kind = 'qcm' OR level = 5")
    op.drop_constraint('ck_problems_status', 'problems', type_='check')
    op.drop_constraint('ck_problems_kind', 'problems', type_='check')
    op.drop_constraint('ck_problems_level', 'problems', type_='check')
    op.create_check_constraint('ck_problems_level', 'problems', 'level BETWEEN 1 AND 4')
    op.drop_index('ix_problems_status', 'problems')
    op.drop_index('ix_problems_kind', 'problems')
    for column in ('correct_choices', 'choices', 'timer_seconds', 'status', 'kind'):
        op.drop_column('problems', column)

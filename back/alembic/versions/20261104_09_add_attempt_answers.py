"""Store per-film quiz answers for personalized recommendations.

Revision ID: 20261104_09
Revises: 20261104_08
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_09"
down_revision = "20261104_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempt_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("film_title", sa.String(length=300), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_quiz_attempt_answers_attempt_id", "quiz_attempt_answers", ["attempt_id"])
    op.create_index("ix_quiz_attempt_answers_film_title", "quiz_attempt_answers", ["film_title"])


def downgrade() -> None:
    op.drop_index("ix_quiz_attempt_answers_film_title", table_name="quiz_attempt_answers")
    op.drop_index("ix_quiz_attempt_answers_attempt_id", table_name="quiz_attempt_answers")
    op.drop_table("quiz_attempt_answers")

"""add accounts and persistent quiz statistics

Revision ID: 20261104_08
Revises: 20261102_07
"""

from alembic import op
import sqlalchemy as sa

revision = "20261104_08"
down_revision = "20261102_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("normalized_username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_normalized_email", "users", ["normalized_email"], unique=True)
    op.create_index("ix_users_normalized_username", "users", ["normalized_username"], unique=True)
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quiz_session_id", sa.String(64), nullable=False),
        sa.Column("genre", sa.String(40), nullable=False),
        sa.Column("difficulty", sa.String(10), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Integer(), nullable=False),
        sa.Column("hints_used", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("quiz_session_id", name="uq_quiz_attempt_session"),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_genre", "quiz_attempts", ["genre"])
    op.create_index("ix_quiz_attempts_difficulty", "quiz_attempts", ["difficulty"])
    op.create_index("ix_quiz_attempts_completed_at", "quiz_attempts", ["completed_at"])


def downgrade() -> None:
    op.drop_table("quiz_attempts")
    op.drop_table("auth_sessions")
    op.drop_table("users")

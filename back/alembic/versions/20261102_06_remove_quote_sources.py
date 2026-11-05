"""Remove quote source storage."""

import sqlalchemy as sa
from alembic import op

revision = "20261102_06"
down_revision = "20261102_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("quote_sources")
    op.drop_table("sources")


def downgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(1000), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
    )
    op.create_table(
        "quote_sources",
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
    )

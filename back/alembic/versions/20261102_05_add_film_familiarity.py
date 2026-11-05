"""Add editorial film-familiarity metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20261102_05"
down_revision = "20261101_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("films", sa.Column("familiarity", sa.String(20), nullable=True))
    op.add_column("films", sa.Column("familiarity_rationale", sa.String(1000), nullable=True))
    op.add_column("films", sa.Column("familiarity_review_status", sa.String(20), nullable=True))
    op.create_index("ix_films_familiarity", "films", ["familiarity"])


def downgrade() -> None:
    op.drop_index("ix_films_familiarity", table_name="films")
    op.drop_column("films", "familiarity_review_status")
    op.drop_column("films", "familiarity_rationale")
    op.drop_column("films", "familiarity")

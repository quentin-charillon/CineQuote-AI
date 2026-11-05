"""Add optional film country metadata for catalog audits."""

import sqlalchemy as sa
from alembic import op

revision = "20261101_02"
down_revision = "20261101_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("films", sa.Column("country_of_origin", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("films", "country_of_origin")

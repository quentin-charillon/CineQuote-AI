"""make film release year optional

Revision ID: 20261102_07
Revises: 20261102_06
"""

from alembic import op
import sqlalchemy as sa

revision = "20261102_07"
down_revision = "20261102_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("films") as batch_op:
        batch_op.alter_column("release_year", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("films") as batch_op:
        batch_op.alter_column("release_year", existing_type=sa.Integer(), nullable=False)

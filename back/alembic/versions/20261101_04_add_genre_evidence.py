"""Add an audit trail for verified film genre assignments."""

import sqlalchemy as sa
from alembic import op

revision = "20261101_04"
down_revision = "20261101_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "film_genre_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("film_id", sa.Integer(), sa.ForeignKey("films.id", ondelete="CASCADE"), nullable=False),
        sa.Column("genre_id", sa.Integer(), sa.ForeignKey("genres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("external_genre_id", sa.String(80), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("film_id", "genre_id", "source_url", name="uq_film_genre_evidence"),
    )
    op.create_index("ix_film_genre_evidence_film_id", "film_genre_evidence", ["film_id"])
    op.create_index("ix_film_genre_evidence_genre_id", "film_genre_evidence", ["genre_id"])
    op.create_index("ix_film_genre_evidence_verified", "film_genre_evidence", ["verified"])


def downgrade() -> None:
    op.drop_table("film_genre_evidence")

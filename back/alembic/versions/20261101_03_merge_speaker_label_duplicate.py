"""Merge the AFI speaker-labelled Airplane! duplicate."""

from alembic import op

revision = "20261101_03"
down_revision = "20261101_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM quotes
        WHERE normalized_text = 'striker surely you can t be serious'
          AND film_id IN (
            SELECT id FROM films
            WHERE normalized_title = 'airplane' AND release_year = 1980
          )
          AND EXISTS (
            SELECT 1 FROM quotes AS spoken
            WHERE spoken.film_id = quotes.film_id
              AND spoken.normalized_text = 'surely you can t be serious'
          )
    """)


def downgrade() -> None:
    # Data-cleanup migrations are intentionally not recreated on downgrade.
    pass

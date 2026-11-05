"""Create normalized movie quote catalog and seed reviewed quotes."""

import json
import re
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "20261101_01"
down_revision = None
branch_labels = None
depends_on = None

DIFFICULTIES = {
    "star-wars-force": "easy", "terminator-back": "easy", "et-home": "easy",
    "wizard-home": "easy", "godfather-offer": "easy", "taxi-driver-talking": "easy",
    "sixth-sense-dead": "easy", "jerry-maguire-money": "easy", "casablanca-looking": "easy",
    "apollo-houston": "easy", "dirty-dancing-baby": "medium", "few-good-men-truth": "medium",
    "top-gun-speed": "medium", "airplane-serious": "hard",
}


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def upgrade() -> None:
    op.create_table("films", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(300), nullable=False), sa.Column("normalized_title", sa.String(300), nullable=False), sa.Column("release_year", sa.Integer(), nullable=False), sa.UniqueConstraint("normalized_title", "release_year", name="uq_film_identity"))
    op.create_index("ix_films_normalized_title", "films", ["normalized_title"])
    op.create_table("genres", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(100), nullable=False, unique=True))
    op.create_table("sources", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("url", sa.String(1000), nullable=False, unique=True), sa.Column("name", sa.String(300), nullable=False), sa.Column("source_type", sa.String(80), nullable=False))
    op.create_table("quotes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("external_id", sa.String(120), nullable=True, unique=True), sa.Column("text", sa.String(1000), nullable=False), sa.Column("normalized_text", sa.String(1000), nullable=False), sa.Column("difficulty", sa.String(10), nullable=False), sa.Column("is_verified", sa.Boolean(), nullable=False), sa.Column("film_id", sa.Integer(), sa.ForeignKey("films.id", ondelete="CASCADE"), nullable=False), sa.UniqueConstraint("film_id", "normalized_text", name="uq_quote_film_text"), sa.CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_quote_difficulty"))
    op.create_index("ix_quotes_normalized_text", "quotes", ["normalized_text"])
    op.create_index("ix_quotes_difficulty", "quotes", ["difficulty"])
    op.create_index("ix_quotes_is_verified", "quotes", ["is_verified"])
    op.create_index("ix_quotes_film_id", "quotes", ["film_id"])
    op.create_table("film_genres", sa.Column("film_id", sa.Integer(), sa.ForeignKey("films.id", ondelete="CASCADE"), primary_key=True), sa.Column("genre_id", sa.Integer(), sa.ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("quote_sources", sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id", ondelete="CASCADE"), primary_key=True), sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True))

    data_path = Path(__file__).parents[2] / "app" / "data" / "questions.json"
    records = json.loads(data_path.read_text(encoding="utf-8"))
    connection = op.get_bind()
    source_id = connection.execute(sa.text("INSERT INTO sources (url, name, source_type) VALUES (:url, :name, :type) RETURNING id"), {"url": records[0]["source_url"], "name": "AFI's 100 Years...100 Movie Quotes", "type": "afi"}).scalar_one()
    for record in records:
        film_id = connection.execute(sa.text("INSERT INTO films (title, normalized_title, release_year) VALUES (:title, :normalized, :year) RETURNING id"), {"title": record["film_title"], "normalized": normalize(record["film_title"]), "year": record["release_year"]}).scalar_one()
        quote_id = connection.execute(sa.text("INSERT INTO quotes (external_id, text, normalized_text, difficulty, is_verified, film_id) VALUES (:external_id, :text, :normalized, :difficulty, :verified, :film_id) RETURNING id"), {"external_id": record["id"], "text": record["quote"], "normalized": normalize(record["quote"]), "difficulty": DIFFICULTIES[record["id"]], "verified": record["verification_status"] == "verified", "film_id": film_id}).scalar_one()
        connection.execute(sa.text("INSERT INTO quote_sources (quote_id, source_id) VALUES (:quote_id, :source_id)"), {"quote_id": quote_id, "source_id": source_id})


def downgrade() -> None:
    for table in ("quote_sources", "film_genres", "quotes", "sources", "genres", "films"):
        op.drop_table(table)

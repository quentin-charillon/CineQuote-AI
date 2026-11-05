"""Stream IMDb's official non-commercial title basics dataset and import genres."""

import csv
import gzip
import json
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy import select

from app.catalog.genre_importer import GenreImporter
from app.database import SessionLocal
from app.models.catalog import Film
from app.repositories.catalog import normalize_catalog_text

DATASET_URL = "https://datasets.imdbws.com/title.basics.tsv.gz"
GENRE_MAP = {
    "Horror": "Horror", "Comedy": "Comedy", "Sci-Fi": "Science Fiction",
    "Thriller": "Thriller", "Action": "Action", "Animation": "Animation",
    "Drama": "Drama", "Romance": "Romance", "Fantasy": "Fantasy",
    "Crime": "Crime", "Adventure": "Adventure",
}


def main() -> None:
    with SessionLocal() as database:
        films = database.scalars(select(Film).order_by(Film.id)).all()
        expected = {(film.normalized_title, film.release_year): (film.title, film.release_year) for film in films}

    matches: dict[tuple[str, int], list[dict[str, str]]] = {key: [] for key in expected}
    request = Request(DATASET_URL, headers={"User-Agent": "CineQuote-AI/0.1 non-commercial metadata import"})
    with urlopen(request, timeout=60) as response, gzip.GzipFile(fileobj=response) as archive:
        reader = csv.DictReader((line.decode("utf-8") for line in archive), delimiter="\t")
        for row in reader:
            if row["titleType"] != "movie" or row["startYear"] == "\\N":
                continue
            year = int(row["startYear"])
            keys = {(normalize_catalog_text(row["primaryTitle"]), year), (normalize_catalog_text(row["originalTitle"]), year)}
            for key in keys & expected.keys():
                matches[key].append(row)

    records: list[dict[str, object]] = []
    review_queue: list[dict[str, object]] = []
    matched_films = 0
    for key, candidates in matches.items():
        title, year = expected[key]
        unique = {row["tconst"]: row for row in candidates}
        if len(unique) != 1:
            review_queue.append({"film_title": title, "release_year": year, "reason": "no unique IMDb movie title/year match", "candidate_ids": sorted(unique)})
            continue
        row = next(iter(unique.values()))
        mapped = [GENRE_MAP[item] for item in row["genres"].split(",") if item in GENRE_MAP]
        if not mapped:
            review_queue.append({"film_title": title, "release_year": year, "reason": "IMDb match has no supported genre", "candidate_ids": [row["tconst"]]})
            continue
        matched_films += 1
        for genre in mapped:
            records.append({
                "film_title": title, "release_year": year, "genre": genre,
                "source_url": f"https://www.imdb.com/title/{row['tconst']}/",
                "external_genre_id": genre,
            })

    result = GenreImporter(SessionLocal).import_records(records)
    Path("genre-review-queue.json").write_text(json.dumps(review_queue, indent=2), encoding="utf-8")
    print(json.dumps({"films_inspected": len(expected), "films_with_supported_genres": matched_films, "review_queue": len(review_queue), **result}, indent=2))


if __name__ == "__main__":
    main()

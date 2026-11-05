import re
from typing import Any

import httpx

from app.repositories.catalog import normalize_catalog_text

API_URL = "https://www.wikidata.org/w/api.php"
ENTITY_URL = "https://www.wikidata.org/wiki/"
GENRE_LABEL_MAP = {
    "horror film": "Horror", "comedy film": "Comedy", "science fiction film": "Science Fiction",
    "thriller film": "Thriller", "action film": "Action", "animated film": "Animation",
    "drama film": "Drama", "romance film": "Romance", "fantasy film": "Fantasy",
    "crime film": "Crime", "adventure film": "Adventure",
}


class WikidataGenreClient:
    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": "CineQuote-AI/0.1 genre-metadata-review"},
            follow_redirects=True,
        )
        self._genre_labels: dict[str, str] = {}

    def close(self) -> None:
        self._client.close()

    def find_film(self, title: str, year: int) -> tuple[list[dict[str, object]], str | None]:
        search = self._get({"action": "wbsearchentities", "format": "json", "language": "en", "type": "item", "limit": 20, "search": title})
        ids = [item["id"] for item in search.get("search", [])]
        if not ids:
            return [], "no search result"
        entities = self._entities(ids)
        normalized_title = normalize_catalog_text(title)
        candidates = []
        for entity_id in ids:
            entity = entities.get(entity_id, {})
            names = [entity.get("labels", {}).get("en", {}).get("value", "")]
            names.extend(alias.get("value", "") for alias in entity.get("aliases", {}).get("en", []))
            if normalized_title not in {normalize_catalog_text(name) for name in names}:
                continue
            years = self._years(entity.get("claims", {}).get("P577", []))
            if year not in years:
                continue
            genre_ids = self._item_claim_ids(entity.get("claims", {}).get("P136", []))
            mapped = []
            for genre_id in genre_ids:
                label = self._genre_label(genre_id)
                canonical = GENRE_LABEL_MAP.get(label.casefold())
                if canonical:
                    mapped.append({"genre": canonical, "external_genre_id": genre_id, "external_genre_label": label})
            candidates.append({"entity_id": entity_id, "source_url": f"{ENTITY_URL}{entity_id}", "genres": mapped})
        if len(candidates) != 1:
            return [], "no unique exact title/year match" if not candidates else "multiple exact title/year matches"
        if not candidates[0]["genres"]:
            return [], "matched film has no supported explicit genre claim"
        return list(candidates[0]["genres"]), str(candidates[0]["source_url"])

    def _genre_label(self, entity_id: str) -> str:
        if entity_id not in self._genre_labels:
            entity = self._entities([entity_id]).get(entity_id, {})
            self._genre_labels[entity_id] = entity.get("labels", {}).get("en", {}).get("value", "")
        return self._genre_labels[entity_id]

    def _entities(self, ids: list[str]) -> dict[str, Any]:
        return self._get({"action": "wbgetentities", "format": "json", "ids": "|".join(ids), "languages": "en", "props": "labels|aliases|claims"}).get("entities", {})

    def _get(self, params: dict[str, object]) -> dict[str, Any]:
        response = self._client.get(API_URL, params=params)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _years(claims: list[dict[str, Any]]) -> set[int]:
        years = set()
        for claim in claims:
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            match = re.match(r"[+-](\d{4})-", value.get("time", "")) if isinstance(value, dict) else None
            if match:
                years.add(int(match.group(1)))
        return years

    @staticmethod
    def _item_claim_ids(claims: list[dict[str, Any]]) -> list[str]:
        result = []
        for claim in claims:
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(value, dict) and value.get("id"):
                result.append(str(value["id"]))
        return result

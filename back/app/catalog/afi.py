import html
import re

import httpx

AFI_QUOTES_URL = "https://www.afi.com/afis-100-years-100-movie-quotes/"
ENTRY_PATTERN = re.compile(
    r'<h6 class="q_title">\s*(\d+)\.\s*"(.*?)"</h6>\s*<p>\s*(.*?)\s*</p>',
    re.DOTALL,
)


def fetch_afi_records(timeout_seconds: float = 20.0) -> list[dict[str, object]]:
    response = httpx.get(AFI_QUOTES_URL, timeout=timeout_seconds, follow_redirects=True)
    response.raise_for_status()
    return parse_afi_records(response.text)


def parse_afi_records(page_html: str) -> list[dict[str, object]]:
    matches = ENTRY_PATTERN.findall(page_html)
    ranks = [int(rank) for rank, _, _ in matches]
    if ranks != list(range(1, 101)):
        raise ValueError("AFI source validation failed: expected exactly ranked entries 1 through 100")

    records: list[dict[str, object]] = []
    for rank_text, raw_quote, raw_film in matches:
        rank = int(rank_text)
        quote = _clean(raw_quote)
        film_and_year = _clean(raw_film)
        film_match = re.fullmatch(r"(.+)\s+\((\d{4})\)", film_and_year)
        if film_match is None:
            raise ValueError(f"AFI source validation failed for rank {rank}: missing film year")
        records.append({
            "film_title": film_match.group(1),
            "release_year": int(film_match.group(2)),
            "quote": quote,
            "difficulty": "easy" if rank <= 34 else "medium" if rank <= 67 else "hard",
            "source_url": AFI_QUOTES_URL,
            "source_name": "AFI's 100 Years...100 Movie Quotes",
            "source_type": "afi",
            "afi_rank": rank,
        })
    return records


def _clean(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    return " ".join(html.unescape(without_tags).split())

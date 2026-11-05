import pytest

from app.catalog.afi import AFI_QUOTES_URL, parse_afi_records


def _afi_html(entry_count: int = 100) -> str:
    return "\n".join(
        f'<h6 class="q_title">{rank}. "Verified quote {rank}"</h6><p>Film {rank} ({1900 + rank})</p>'
        for rank in range(1, entry_count + 1)
    )


def test_afi_parser_requires_complete_ranked_source_and_assigns_balanced_difficulties() -> None:
    records = parse_afi_records(_afi_html())

    assert len(records) == 100
    assert [record["difficulty"] for record in records].count("easy") == 34
    assert [record["difficulty"] for record in records].count("medium") == 33
    assert [record["difficulty"] for record in records].count("hard") == 33
    assert all(record["source_url"] == AFI_QUOTES_URL for record in records)
    assert records[0]["afi_rank"] == 1
    assert records[-1]["afi_rank"] == 100


def test_afi_parser_rejects_incomplete_source() -> None:
    with pytest.raises(ValueError, match="ranked entries 1 through 100"):
        parse_afi_records(_afi_html(99))


def test_afi_parser_rejects_missing_release_year() -> None:
    page = _afi_html().replace("Film 50 (1950)", "Film 50")

    with pytest.raises(ValueError, match="missing film year"):
        parse_afi_records(page)

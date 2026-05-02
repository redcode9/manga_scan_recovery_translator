from __future__ import annotations

import pytest

from msrt.scrape.base import ChapterLink
from msrt.scrape.selection import (
    parse_chapter_list,
    parse_chapter_range,
    select_chapters,
)


def _link(chapter_number: str) -> ChapterLink:
    return ChapterLink(
        url=f"https://example.test/chapter/{chapter_number}",
        chapter_number=chapter_number,
    )


def test_parse_chapter_range_inclusive() -> None:
    assert parse_chapter_range("50-51") == (50.0, 51.0)


def test_parse_chapter_range_decimals() -> None:
    assert parse_chapter_range("50.5-51.0") == (50.5, 51.0)


def test_parse_chapter_range_strips_whitespace() -> None:
    assert parse_chapter_range("  50  -  51  ") == (50.0, 51.0)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "50",
        "50-",
        "-51",
        "abc-def",
        "nan-51",
        "50-inf",
        "50-51-52",
        "51-50",  # reversed
    ],
)
def test_parse_chapter_range_rejects_malformed(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_chapter_range(raw)


def test_parse_chapter_list_basic() -> None:
    assert parse_chapter_list("50,51,51.1") == {"50", "51", "51.1"}


def test_parse_chapter_list_tolerates_whitespace_and_trailing_commas() -> None:
    assert parse_chapter_list(" 50 ,, 51 , 51.1 , ") == {"50", "51", "51.1"}


def test_parse_chapter_list_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_chapter_list("   ")
    with pytest.raises(ValueError):
        parse_chapter_list(",, ,")


def test_select_chapters_with_range_filter() -> None:
    chapters = [_link("48"), _link("50"), _link("50.5"), _link("51"), _link("52")]
    assert [c.chapter_number for c in select_chapters(chapters, range_filter=(50.0, 51.0))] == [
        "50",
        "50.5",
        "51",
    ]


def test_select_chapters_range_skips_non_numeric() -> None:
    chapters = [_link("50"), _link("extra"), _link("51")]
    assert [c.chapter_number for c in select_chapters(chapters, range_filter=(50.0, 51.0))] == [
        "50",
        "51",
    ]


def test_select_chapters_with_chapter_list() -> None:
    chapters = [_link("50"), _link("51"), _link("51.1"), _link("52")]
    assert [c.chapter_number for c in select_chapters(chapters, chapter_list={"50", "51.1"})] == [
        "50",
        "51.1",
    ]


def test_select_chapters_with_limit() -> None:
    chapters = [_link("1"), _link("2"), _link("3"), _link("4")]
    assert [c.chapter_number for c in select_chapters(chapters, limit=2)] == ["1", "2"]


def test_select_chapters_limit_after_other_filters() -> None:
    """``--limit 2`` of ``--range 50-100`` keeps the first two of that range."""

    chapters = [_link("48"), _link("50"), _link("51"), _link("52"), _link("100"), _link("101")]
    out = select_chapters(chapters, range_filter=(50.0, 100.0), limit=2)
    assert [c.chapter_number for c in out] == ["50", "51"]


def test_select_chapters_combines_range_and_explicit_list() -> None:
    chapters = [_link("48"), _link("50"), _link("51.1"), _link("52")]
    # Range catches 50-52, then chapters list keeps only "51.1".
    out = select_chapters(chapters, range_filter=(50.0, 52.0), chapter_list={"51.1"})
    assert [c.chapter_number for c in out] == ["51.1"]


def test_select_chapters_limit_below_one_raises() -> None:
    with pytest.raises(ValueError):
        select_chapters([_link("1")], limit=0)


def test_select_chapters_no_filters_returns_input_in_order() -> None:
    chapters = [_link("1"), _link("2"), _link("3")]
    assert [c.chapter_number for c in select_chapters(chapters)] == ["1", "2", "3"]


def test_select_chapters_preserves_link_metadata() -> None:
    rich = ChapterLink(
        url="https://example.test/c/50",
        chapter_number="50",
        title="The Trial",
        series="Wistoria",
    )
    out = select_chapters([rich], chapter_list={"50"})
    assert out == [rich]

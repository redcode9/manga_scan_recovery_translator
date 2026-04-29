from __future__ import annotations

from pathlib import Path

from msrt.package.naming import natural_sort_key


def test_natural_sort_key_orders_page_numbers() -> None:
    names = ["10.jpg", "2.jpg", "001.jpg"]
    ordered = sorted((Path(name) for name in names), key=natural_sort_key)
    assert [path.name for path in ordered] == ["001.jpg", "2.jpg", "10.jpg"]

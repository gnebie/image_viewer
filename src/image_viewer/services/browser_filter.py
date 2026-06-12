from __future__ import annotations

from pathlib import Path


def filter_items(items: list[Path], query: str) -> list[Path]:
    q = query.strip().lower()
    if not q:
        return items
    return [p for p in items if q in p.name.lower()]

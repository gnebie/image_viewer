from __future__ import annotations

from pathlib import Path
from typing import TypedDict


class SortingRule(TypedDict, total=False):
    name_contains: str
    ext: str
    destination: str


def match_rule(name: str, suffix: str, rule: SortingRule) -> bool:
    if "name_contains" in rule and rule["name_contains"].lower() not in name.lower():
        return False
    if "ext" in rule and rule["ext"].lower() != suffix.lower():
        return False
    return True


def resolve_destination(rules: list[SortingRule], src: Path) -> Path | None:
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if not match_rule(src.name, src.suffix, rule):
            continue
        dest = rule.get("destination")
        if isinstance(dest, str) and dest.strip():
            return Path(dest).expanduser()
    return None

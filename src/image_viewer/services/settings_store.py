"""Load and save user preferences under ``cwd/config/settings.json``."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

THUMBNAIL_LEVEL_MIN = 1
THUMBNAIL_LEVEL_MAX = 9
DEFAULT_THUMBNAIL_LEVEL = 5
SHORTCUT_KEYS = frozenset(str(i) for i in range(10))
# Note: "enter_organize_mode" and "organize_target_zip" intentionally share the
# same default key "d". They are context-sensitive: "d" enters organize mode from
# the browser, then acts as a toggle to zip/folder target once already inside.
DEFAULT_HOTKEYS: dict[str, str] = {
    "enter_organize_mode": "d",
    "organize_target_image": "i",
    "organize_target_zip": "d",
    "organize_op_move": "m",
    "organize_op_copy": "c",
}


def normalize_hotkeys(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for action, default_key in DEFAULT_HOTKEYS.items():
        val = raw.get(action)
        if not isinstance(val, str) or not val.strip():
            out[action] = default_key
            continue
        out[action] = val.strip().lower()
    return out


def config_dir(cwd: Path | None = None) -> Path:
    base = cwd if cwd is not None else Path.cwd()
    return base / "config"


def settings_path(cwd: Path | None = None) -> Path:
    return config_dir(cwd) / "settings.json"


def normalize_folder_shortcuts(raw: Any) -> dict[str, str]:
    """Keep at most 10 entries with keys ``\"0\"``..``\"9\"`` and string paths."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for ks in sorted(SHORTCUT_KEYS, key=int):
        v = raw.get(ks)
        if not isinstance(v, str) or not v.strip():
            continue
        out[ks] = v.strip()
    return out


AUTOPLAY_MS_MIN = 250
AUTOPLAY_MS_MAX = 20000
DEFAULT_AUTOPLAY_MS = 2500


@dataclass
class Settings:
    thumbnail_size_level: int = DEFAULT_THUMBNAIL_LEVEL
    folder_shortcuts: dict[str, str] = field(default_factory=dict)
    onboarding_done: bool = False
    hotkeys: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))
    sorting_rules: list[dict[str, str]] = field(default_factory=list)
    autoplay_ms: int = DEFAULT_AUTOPLAY_MS
    sort_mode: str = "name_asc"
    window_geometry: str = ""

    def clamp(self) -> None:
        self.thumbnail_size_level = max(
            THUMBNAIL_LEVEL_MIN,
            min(THUMBNAIL_LEVEL_MAX, int(self.thumbnail_size_level)),
        )
        self.autoplay_ms = max(AUTOPLAY_MS_MIN, min(AUTOPLAY_MS_MAX, int(self.autoplay_ms)))
        self.folder_shortcuts = normalize_folder_shortcuts(self.folder_shortcuts)
        self.onboarding_done = bool(self.onboarding_done)
        self.hotkeys = normalize_hotkeys(self.hotkeys)
        if self.sort_mode not in {"name_asc", "name_desc", "date_asc", "date_desc"}:
            self.sort_mode = "name_asc"
        if not isinstance(self.window_geometry, str):
            self.window_geometry = ""
        if not isinstance(self.sorting_rules, list):
            self.sorting_rules = []
        cleaned_rules: list[dict[str, str]] = []
        for item in self.sorting_rules:
            if not isinstance(item, dict):
                continue
            name_contains = item.get("name_contains")
            ext = item.get("ext")
            destination = item.get("destination")
            if not isinstance(destination, str) or not destination.strip():
                continue
            out: dict[str, str] = {"destination": destination.strip()}
            if isinstance(name_contains, str) and name_contains.strip():
                out["name_contains"] = name_contains.strip()
            if isinstance(ext, str) and ext.strip():
                out["ext"] = ext.strip().lower()
            cleaned_rules.append(out)
        self.sorting_rules = cleaned_rules


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load(cwd: Path | None = None) -> Settings:
    path = settings_path(cwd)
    if not path.is_file():
        s = Settings()
        s.clamp()
        return s
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read settings from %s: %s", path, e)
        s = Settings()
        s.clamp()
        return s
    if not isinstance(raw, dict):
        s = Settings()
        s.clamp()
        return s
    s = Settings(
        thumbnail_size_level=_coerce_int(
            raw.get("thumbnail_size_level"), DEFAULT_THUMBNAIL_LEVEL
        ),
        folder_shortcuts=normalize_folder_shortcuts(raw.get("folder_shortcuts")),
        onboarding_done=bool(raw.get("onboarding_done", False)),
        hotkeys=normalize_hotkeys(raw.get("hotkeys")),
        sorting_rules=raw.get("sorting_rules") if isinstance(raw.get("sorting_rules"), list) else [],
        autoplay_ms=_coerce_int(raw.get("autoplay_ms"), DEFAULT_AUTOPLAY_MS),
        sort_mode=raw.get("sort_mode", "name_asc") if isinstance(raw.get("sort_mode"), str) else "name_asc",
        window_geometry=raw.get("window_geometry", "") if isinstance(raw.get("window_geometry"), str) else "",
    )
    s.clamp()
    return s


def save(settings: Settings, cwd: Path | None = None) -> None:
    settings.clamp()
    path = settings_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {f.name: getattr(settings, f.name) for f in fields(settings)}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.debug("Saved settings to %s", path)


def level_to_thumb_max_px(level: int) -> int:
    """Map discrete level 1..9 to max thumbnail edge in pixels."""
    level = max(THUMBNAIL_LEVEL_MIN, min(THUMBNAIL_LEVEL_MAX, int(level)))
    # Level 1: 64px, level 9: 512px (step 56)
    return 8 + level * 56

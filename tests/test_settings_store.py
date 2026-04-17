import json
import tempfile
import unittest
from pathlib import Path

from image_viewer import settings_store
from image_viewer.settings_store import (
    DEFAULT_HOTKEYS,
    DEFAULT_THUMBNAIL_LEVEL,
    Settings,
    load,
    save,
)


class SettingsStoreTests(unittest.TestCase):
    def test_load_missing_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            s = load(cwd)
            self.assertEqual(s.thumbnail_size_level, DEFAULT_THUMBNAIL_LEVEL)

    def test_save_and_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            s = Settings(thumbnail_size_level=8)
            save(s, cwd)
            s2 = load(cwd)
            self.assertEqual(s2.thumbnail_size_level, 8)
            data = json.loads((cwd / "config" / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(data["thumbnail_size_level"], 8)

    def test_load_clamps_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            (cwd / "config").mkdir(parents=True)
            (cwd / "config" / "settings.json").write_text(
                '{"thumbnail_size_level": 99}', encoding="utf-8"
            )
            s = load(cwd)
            self.assertEqual(s.thumbnail_size_level, settings_store.THUMBNAIL_LEVEL_MAX)

    def test_folder_shortcuts_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            s = Settings(
                thumbnail_size_level=5,
                folder_shortcuts={"1": "/tmp/a", "bad": "x", "11": "y"},
            )
            save(s, cwd)
            s2 = load(cwd)
            self.assertEqual(s2.folder_shortcuts.get("1"), "/tmp/a")
            self.assertNotIn("bad", s2.folder_shortcuts)
            self.assertNotIn("11", s2.folder_shortcuts)

    def test_new_fields_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            s = Settings(
                thumbnail_size_level=5,
                onboarding_done=True,
                hotkeys={"enter_organize_mode": "x"},
                sorting_rules=[{"ext": ".jpg", "destination": "/tmp/ok"}],
            )
            save(s, cwd)
            s2 = load(cwd)
            self.assertTrue(s2.onboarding_done)
            self.assertEqual(s2.hotkeys["enter_organize_mode"], "x")
            self.assertEqual(s2.hotkeys["organize_op_copy"], DEFAULT_HOTKEYS["organize_op_copy"])
            self.assertEqual(len(s2.sorting_rules), 1)


if __name__ == "__main__":
    unittest.main()

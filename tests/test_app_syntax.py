import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "image_viewer"
PY_FILES = [
    "app.py",
    "ui/app.py",
    "ui/controllers/browser.py",
    "ui/controllers/organize.py",
    "ui/controllers/slideshow.py",
    "ui/widgets/help_text.py",
]


class AppSyntaxTests(unittest.TestCase):
    def _assert_parses(self, name: str) -> None:
        path = SRC / name
        self.assertTrue(path.is_file(), f"missing {path}")
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))

    def test_app_shim_parses(self) -> None:
        self._assert_parses("app.py")

    def test_ui_app_parses(self) -> None:
        self._assert_parses("ui/app.py")

    def test_browser_parses(self) -> None:
        self._assert_parses("ui/controllers/browser.py")

    def test_organize_parses(self) -> None:
        self._assert_parses("ui/controllers/organize.py")

    def test_slideshow_parses(self) -> None:
        self._assert_parses("ui/controllers/slideshow.py")

    def test_help_text_parses(self) -> None:
        self._assert_parses("ui/widgets/help_text.py")


if __name__ == "__main__":
    unittest.main()

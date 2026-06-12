import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "image_viewer"
PY_FILES = [
    "app.py",
    "browser_mixin.py",
    "organize_mixin.py",
    "slideshow_mixin.py",
    "help_text.py",
]


class AppSyntaxTests(unittest.TestCase):
    def _assert_parses(self, name: str) -> None:
        path = SRC / name
        self.assertTrue(path.is_file(), f"missing {path}")
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))

    def test_app_py_parses(self) -> None:
        self._assert_parses("app.py")

    def test_browser_mixin_parses(self) -> None:
        self._assert_parses("browser_mixin.py")

    def test_organize_mixin_parses(self) -> None:
        self._assert_parses("organize_mixin.py")

    def test_slideshow_mixin_parses(self) -> None:
        self._assert_parses("slideshow_mixin.py")

    def test_help_text_parses(self) -> None:
        self._assert_parses("help_text.py")


if __name__ == "__main__":
    unittest.main()

import ast
import unittest
from pathlib import Path


class AppSyntaxTests(unittest.TestCase):
    def test_app_py_parses(self) -> None:
        """Ensure app.py is syntactically valid without importing Tkinter."""
        root = Path(__file__).resolve().parents[1]
        app_py = root / "src" / "image_viewer" / "app.py"
        self.assertTrue(app_py.is_file(), f"missing {app_py}")
        source = app_py.read_text(encoding="utf-8")
        ast.parse(source, filename=str(app_py))


if __name__ == "__main__":
    unittest.main()

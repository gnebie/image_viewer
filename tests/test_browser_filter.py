import unittest
from pathlib import Path

from image_viewer.browser_filter import filter_items


class BrowserFilterTests(unittest.TestCase):
    def test_empty_query_returns_all(self) -> None:
        items = [Path("/a/A.jpg"), Path("/a/b.png")]
        self.assertEqual(filter_items(items, ""), items)

    def test_case_insensitive_contains(self) -> None:
        items = [Path("/a/Holidays.jpg"), Path("/a/work.png")]
        out = filter_items(items, "day")
        self.assertEqual(out, [Path("/a/Holidays.jpg")])


if __name__ == "__main__":
    unittest.main()

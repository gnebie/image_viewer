import unittest
from pathlib import Path

from image_viewer.sorting_rules import resolve_destination


class SortingRulesTests(unittest.TestCase):
    def test_resolve_destination_first_match(self) -> None:
        rules = [
            {"ext": ".png", "destination": "/tmp/png"},
            {"name_contains": "vac", "destination": "/tmp/vac"},
        ]
        out = resolve_destination(rules, Path("/x/vacation.png"))
        self.assertEqual(str(out), "/tmp/png")

    def test_resolve_destination_no_match(self) -> None:
        rules = [{"ext": ".jpg", "destination": "/tmp/jpg"}]
        out = resolve_destination(rules, Path("/x/a.png"))
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()

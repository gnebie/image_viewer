import unittest

from image_viewer.gallery_layout import (
    clamp_col_for_row,
    compute_columns,
    index_from_rc,
    move_gallery_index,
    page_vertical,
    rc_from_index,
)


class GalleryLayoutTests(unittest.TestCase):
    def test_compute_columns(self) -> None:
        self.assertEqual(compute_columns(800, 100, gap=8), 7)
        self.assertEqual(compute_columns(0, 100), 1)
        self.assertEqual(compute_columns(120, 100, gap=8), 1)

    def test_rc_roundtrip(self) -> None:
        cols = 4
        for idx in range(11):
            r, c = rc_from_index(idx, cols)
            self.assertEqual(index_from_rc(r, c, cols, 11), idx)

    def test_move_gallery_index_row_major(self) -> None:
        total = 5
        cols = 2
        # indices: 0 1 / 2 3 / 4
        self.assertEqual(move_gallery_index(0, total, cols, -1, 0), 0)
        self.assertEqual(move_gallery_index(4, total, cols, 1, 0), 4)
        self.assertEqual(move_gallery_index(1, total, cols, 0, 1), 2)
        self.assertEqual(move_gallery_index(2, total, cols, 0, -1), 1)

    def test_last_row_partial(self) -> None:
        total = 5
        cols = 2
        self.assertEqual(move_gallery_index(3, total, cols, 1, 0), 4)
        self.assertEqual(move_gallery_index(4, total, cols, 0, 1), 4)

    def test_page_vertical(self) -> None:
        total = 10
        cols = 3
        idx = 7
        self.assertEqual(page_vertical(idx, total, cols, -2), 1)

    def test_clamp_col_for_row(self) -> None:
        total = 5
        cols = 2
        self.assertEqual(clamp_col_for_row(2, 5, cols, total), 0)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from image_viewer.organize_ops import (
    OrganizeError,
    execute_move_or_copy,
    execute_move_or_copy_to_final,
    remove_path_for_overwrite,
    unique_destination_path,
)


class OrganizeOpsTests(unittest.TestCase):
    def test_unique_destination_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.txt").write_text("x", encoding="utf-8")
            u = unique_destination_path(d, "a.txt")
            self.assertEqual(u.name, "a_1.txt")

    def test_move_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src_dir = base / "src"
            dst_dir = base / "dst"
            src_dir.mkdir()
            dst_dir.mkdir()
            f = src_dir / "hello.txt"
            f.write_text("ab", encoding="utf-8")
            out = execute_move_or_copy(f, dst_dir, copy=False)
            self.assertTrue(out.exists())
            self.assertFalse(f.exists())
            self.assertEqual(out.read_text(encoding="utf-8"), "ab")

    def test_copy_file_collision_renames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dst = base / "dst"
            dst.mkdir()
            (dst / "x.txt").write_text("old", encoding="utf-8")
            src = base / "x.txt"
            src.write_text("new", encoding="utf-8")
            out = execute_move_or_copy(src, dst, copy=True)
            self.assertEqual(out.name, "x_1.txt")
            self.assertEqual(out.read_text(encoding="utf-8"), "new")

    def test_reject_dest_inside_src(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "folder"
            src.mkdir()
            inner = src / "inner"
            inner.mkdir()
            with self.assertRaises(OrganizeError):
                execute_move_or_copy(src, inner, copy=False)

    def test_to_final_rejects_existing_dest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dst = base / "dst"
            dst.mkdir()
            (dst / "x.txt").write_text("a", encoding="utf-8")
            src = base / "y.txt"
            src.write_text("b", encoding="utf-8")
            with self.assertRaises(OrganizeError):
                execute_move_or_copy_to_final(src, dst / "x.txt", copy=True)

    def test_to_final_after_remove_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dst = base / "dst"
            dst.mkdir()
            (dst / "x.txt").write_text("old", encoding="utf-8")
            src = base / "x.txt"
            src.write_text("new", encoding="utf-8")
            remove_path_for_overwrite(dst / "x.txt")
            out = execute_move_or_copy_to_final(src, dst / "x.txt", copy=False)
            self.assertEqual(out.read_text(encoding="utf-8"), "new")
            self.assertFalse(src.exists())


if __name__ == "__main__":
    unittest.main()

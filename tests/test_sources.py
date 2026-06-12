"""Tests for FolderSource and ZipSource."""

from __future__ import annotations

import io
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from image_viewer.sources import (
    FolderSource,
    ImageEntry,
    SourceError,
    SUPPORTED_EXTS,
    ZipSource,
)


def _make_png(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Return minimal valid PNG bytes (1×1 pixel)."""
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color).save(buf, format="PNG")
    return buf.getvalue()


class FolderSourceTests(unittest.TestCase):
    def test_list_images_returns_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.jpg").write_bytes(_make_png())
            (d / "b.png").write_bytes(_make_png())
            (d / "ignore.txt").write_text("x")
            src = FolderSource(d)
            entries = src.list_images()
            names = {e.path.name for e in entries}
            self.assertIn("a.jpg", names)
            self.assertIn("b.png", names)
            self.assertNotIn("ignore.txt", names)

    def test_list_images_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name in ("z.png", "a.jpg", "m.png"):
                (d / name).write_bytes(_make_png())
            src = FolderSource(d)
            names = [e.path.name for e in src.list_images()]
            self.assertEqual(names, sorted(names, key=str.lower))

    def test_open_image_returns_pil(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            p = d / "img.png"
            p.write_bytes(_make_png())
            src = FolderSource(d)
            entries = src.list_images()
            img = src.open_image(entries[0])
            self.assertEqual(img.size, (1, 1))

    def test_open_image_corrupt_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            p = d / "bad.png"
            p.write_bytes(b"not an image")
            src = FolderSource(d)
            entry = ImageEntry(kind="file", path=p)
            with self.assertRaises(SourceError):
                src.open_image(entry)

    def test_container_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertEqual(FolderSource(d).container_dir(), d)

    def test_display_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertEqual(FolderSource(d).display_name(), d.name)

    def test_missing_folder_raises(self) -> None:
        src = FolderSource(Path("/nonexistent/path/xyz"))
        with self.assertRaises(SourceError):
            src.list_images()


class ZipSourceTests(unittest.TestCase):
    def _make_zip(self, tmp: str, images: dict[str, bytes] | None = None) -> Path:
        z = Path(tmp) / "test.zip"
        with zipfile.ZipFile(z, "w") as zf:
            if images:
                for name, data in images.items():
                    zf.writestr(name, data)
        return z

    def test_list_images_returns_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            z = self._make_zip(tmp, {"a.jpg": _make_png(), "b.txt": b"text"})
            src = ZipSource(z)
            entries = src.list_images()
            names = {e.member for e in entries}
            self.assertIn("a.jpg", names)
            self.assertNotIn("b.txt", names)
            src.close()

    def test_list_images_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imgs = {"z.png": _make_png(), "a.jpg": _make_png(), "m.png": _make_png()}
            z = self._make_zip(tmp, imgs)
            src = ZipSource(z)
            members = [e.member for e in src.list_images()]
            self.assertEqual(members, sorted(members, key=str.lower))
            src.close()

    def test_open_image_returns_pil(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            z = self._make_zip(tmp, {"img.png": _make_png()})
            src = ZipSource(z)
            entries = src.list_images()
            img = src.open_image(entries[0])
            self.assertEqual(img.size, (1, 1))
            src.close()

    def test_open_image_corrupt_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            z = self._make_zip(tmp, {"bad.png": b"garbage"})
            src = ZipSource(z)
            entry = src.list_images()[0]
            with self.assertRaises(SourceError):
                src.open_image(entry)
            src.close()

    def test_container_dir_is_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            z = self._make_zip(tmp)
            src = ZipSource(z)
            self.assertEqual(src.container_dir(), z.parent)
            src.close()

    def test_display_name_is_zip_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            z = self._make_zip(tmp)
            src = ZipSource(z)
            self.assertEqual(src.display_name(), "test.zip")
            src.close()

    def test_missing_zip_raises(self) -> None:
        src = ZipSource(Path("/nonexistent/archive.zip"))
        with self.assertRaises(SourceError):
            src.list_images()

    def test_close_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            z = self._make_zip(tmp)
            src = ZipSource(z)
            src.close()
            src.close()  # must not raise

    def test_skip_directories_in_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "dirs.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("subdir/", "")
                zf.writestr("subdir/img.png", _make_png())
            src = ZipSource(z)
            entries = src.list_images()
            members = [e.member for e in entries]
            self.assertNotIn("subdir/", members)
            self.assertIn("subdir/img.png", members)
            src.close()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
ZIP_EXT = ".zip"


@dataclass(frozen=True)
class ImageEntry:
    """Reference to an image either on filesystem or inside a zip."""

    kind: str  # "file" | "zipmember"
    path: Path
    member: Optional[str] = None

    def display_name(self) -> str:
        if self.kind == "file":
            return self.path.name
        return f"{self.path.name}::{self.member or ''}"


class SourceError(Exception):
    pass


class ImageSource(ABC):
    """Abstraction of a collection of images with open/close lifecycle."""

    @abstractmethod
    def list_images(self) -> list[ImageEntry]:
        raise NotImplementedError

    @abstractmethod
    def open_image(self, entry: ImageEntry) -> Image.Image:
        raise NotImplementedError

    def close(self) -> None:
        pass

    @abstractmethod
    def container_dir(self) -> Path:
        raise NotImplementedError

    def display_name(self) -> str:
        """Short name shown in window title — override for non-folder sources."""
        return self.container_dir().name

    def describe_entry(self, entry: ImageEntry) -> dict[str, str]:
        base = {
            "name": entry.path.name if entry.kind == "file" else Path(entry.member or "").name,
            "path": str(entry.path),
            "source_type": entry.kind,
        }
        if entry.kind == "zipmember":
            base["zip_path"] = str(entry.path)
            base["zip_member"] = entry.member or ""
        return base


class FolderSource(ImageSource):
    def __init__(self, folder: Path):
        self.folder = folder

    def container_dir(self) -> Path:
        return self.folder

    def list_images(self) -> list[ImageEntry]:
        try:
            items = []
            for p in self.folder.iterdir():
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                    items.append(ImageEntry(kind="file", path=p))
            items.sort(key=lambda e: e.path.name.lower())
            return items
        except Exception as e:
            raise SourceError(f"Impossible de lister le dossier: {self.folder} ({e})") from e

    def open_image(self, entry: ImageEntry) -> Image.Image:
        if entry.kind != "file":
            raise SourceError("Entree invalide pour FolderSource")
        try:
            img = Image.open(entry.path)
            img.load()
            return img
        except (UnidentifiedImageError, OSError) as e:
            raise SourceError(f"Image illisible/corrompue: {entry.path.name} ({e})") from e

    def describe_entry(self, entry: ImageEntry) -> dict[str, str]:
        info = super().describe_entry(entry)
        info["path"] = str(entry.path)
        info["source_type"] = "fichier"
        return info


class ZipSource(ImageSource):
    def __init__(self, zip_path: Path):
        self.zip_path = zip_path
        self._zf: Optional[zipfile.ZipFile] = None

    def container_dir(self) -> Path:
        return self.zip_path.parent

    def _ensure_open(self) -> zipfile.ZipFile:
        if self._zf is None:
            try:
                self._zf = zipfile.ZipFile(self.zip_path, "r")
            except Exception as e:
                raise SourceError(f"Impossible d'ouvrir le zip: {self.zip_path} ({e})") from e
        return self._zf

    def list_images(self) -> list[ImageEntry]:
        zf = self._ensure_open()
        try:
            entries: list[ImageEntry] = []
            for info in zf.infolist():
                name = info.filename
                if name.endswith("/"):
                    continue
                ext = Path(name).suffix.lower()
                if ext in SUPPORTED_EXTS:
                    entries.append(ImageEntry(kind="zipmember", path=self.zip_path, member=name))
            entries.sort(key=lambda e: (e.member or "").lower())
            return entries
        except Exception as e:
            raise SourceError(f"Impossible de lister le contenu du zip: {self.zip_path} ({e})") from e

    def open_image(self, entry: ImageEntry) -> Image.Image:
        if entry.kind != "zipmember" or entry.member is None:
            raise SourceError("Entree invalide pour ZipSource")
        zf = self._ensure_open()
        try:
            raw = zf.read(entry.member)
            bio = BytesIO(raw)
            img = Image.open(bio)
            img.load()
            return img
        except KeyError as e:
            raise SourceError(f"Fichier introuvable dans le zip: {entry.member}") from e
        except (UnidentifiedImageError, OSError, RuntimeError, zipfile.BadZipFile) as e:
            raise SourceError(f"Image zip illisible/corrompue: {entry.member} ({e})") from e

    def display_name(self) -> str:
        return self.zip_path.name

    def close(self) -> None:
        if self._zf is not None:
            try:
                self._zf.close()
            finally:
                self._zf = None

    def describe_entry(self, entry: ImageEntry) -> dict[str, str]:
        info = super().describe_entry(entry)
        info["name"] = Path(entry.member or "").name
        info["path"] = entry.member or ""
        info["source_type"] = "zip"
        info["zip_path"] = str(self.zip_path)
        info["zip_member"] = entry.member or ""
        return info

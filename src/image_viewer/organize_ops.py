"""Move/copy files for browser organize (tri) mode."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class OrganizeError(Exception):
    """User-visible error for organize operations."""


def source_allows_move(src: Path) -> bool:
    """Move is allowed for normal filesystem paths (not e.g. virtual zip members)."""
    try:
        return src.exists() and (src.is_file() or src.is_dir())
    except OSError:
        return False


def _is_under(path: Path, ancestor: Path) -> bool:
    try:
        path.resolve().relative_to(ancestor.resolve())
        return True
    except ValueError:
        return False


def unique_destination_path(dest_dir: Path, base_name: str) -> Path:
    """Return ``dest_dir / base_name`` or add ``_N`` before suffix if name exists."""
    dest = dest_dir / base_name
    if not dest.exists():
        return dest
    stem = Path(base_name).stem
    suffix = Path(base_name).suffix
    n = 1
    while True:
        candidate = dest_dir / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def remove_path_for_overwrite(path: Path) -> None:
    """Remove a file, symlink, or directory so ``path`` can be replaced."""
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            raise OrganizeError(f"Type non supporte pour ecrasement: {path}")
    except OSError as e:
        raise OrganizeError(f"Impossible d'ecraser {path}: {e}") from e


def execute_move_or_copy_to_final(src: Path, final_dest: Path, *, copy: bool) -> Path:
    """Move or copy ``src`` to the exact path ``final_dest`` (must not exist yet).

    Caller must remove an existing destination first when overwriting.
    """
    if not src.exists():
        raise OrganizeError(f"Source introuvable: {src}")
    parent = final_dest.parent
    if not parent.is_dir():
        raise OrganizeError(f"Dossier parent introuvable: {parent}")

    src_r = src.resolve()
    dest_parent_r = parent.resolve()
    if src_r == dest_parent_r:
        raise OrganizeError("La source et la destination sont identiques.")
    if _is_under(dest_parent_r, src_r):
        raise OrganizeError("Impossible: la destination est a l'interieur de la source.")

    if final_dest.exists():
        raise OrganizeError(f"La destination existe deja: {final_dest}")

    try:
        if copy:
            if src.is_dir():
                shutil.copytree(src, final_dest, dirs_exist_ok=False)
            else:
                shutil.copy2(src, final_dest)
            logger.info("Organize: copie %s -> %s", src, final_dest)
        else:
            shutil.move(str(src), str(final_dest))
            logger.info("Organize: deplacement %s -> %s", src, final_dest)
    except OSError as e:
        raise OrganizeError(str(e)) from e
    except shutil.Error as e:
        raise OrganizeError(str(e)) from e

    return final_dest


def execute_move_or_copy(src: Path, dest_dir: Path, *, copy: bool) -> Path:
    """Move or copy ``src`` into ``dest_dir``, picking a non-colliding name if needed.

    Kept for tests and callers that do not need overwrite semantics.
    """
    final_name = unique_destination_path(dest_dir, src.name)
    if final_name.name != src.name:
        logger.info("Organize: collision renommage vers %s", final_name.name)
    return execute_move_or_copy_to_final(src, final_name, copy=copy)

"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(cwd: Path | None = None) -> Path:
    """Configure the ``image_viewer`` logger with a rotating-style single file handler.

    Returns the path to the log file.
    """
    base = cwd if cwd is not None else Path.cwd()
    log_path = base / "logs" / "image_viewer.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log = logging.getLogger("image_viewer")
    log.setLevel(logging.INFO)
    log.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    logging.captureWarnings(True)
    return log_path

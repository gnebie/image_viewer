"""Compatibility shim for legacy `python src/app.py` usage."""

from image_viewer.app import run_with_error_boundary


if __name__ == "__main__":
    run_with_error_boundary()


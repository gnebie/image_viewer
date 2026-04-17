"""Package entry point for `python -m image_viewer`."""

from .app import run_with_error_boundary


if __name__ == "__main__":
    run_with_error_boundary()

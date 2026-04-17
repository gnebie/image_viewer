"""Image viewer package."""

__all__ = ["main", "run_with_error_boundary"]


def main() -> None:
    from .app import main as _main

    _main()


def run_with_error_boundary() -> None:
    from .app import run_with_error_boundary as _run

    _run()

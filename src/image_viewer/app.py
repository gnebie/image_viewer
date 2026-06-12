"""Compatibility shim — re-exports from ui.app for the pyproject.toml entry point.

The pyproject.toml entry point references ``image_viewer.app:run_with_error_boundary``.
The real implementation lives in ``image_viewer.ui.app``.
"""

from .ui.app import main, run_with_error_boundary

__all__ = ["main", "run_with_error_boundary"]

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"

echo "[image-viewer] root: ${ROOT_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "[image-viewer] creating virtual environment..."
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

echo "[image-viewer] upgrading pip/setuptools/wheel..."
python -m pip install --upgrade pip setuptools wheel

echo "[image-viewer] installing project in editable mode..."
python -m pip install -e "${ROOT_DIR}"

echo "[image-viewer] checking Tkinter runtime..."
python - <<'PY'
import sys

try:
    import tkinter  # noqa: F401
except ModuleNotFoundError as e:
    if getattr(e, "name", "") == "_tkinter":
        print(
            "[image-viewer] ERROR: Tkinter is not available for this Python build "
            f"({sys.executable}).\n"
            "This app requires a Python with Tk support.\n"
            "Examples:\n"
            "  - Ubuntu/Debian: sudo apt install python3-tk\n"
            "  - Fedora: sudo dnf install python3-tkinter\n"
            "  - macOS/Homebrew: install a Tk-enabled Python (often `brew install python-tk@3.12` "
            "matching your Python minor version), or set PYTHON_BIN to a Python that imports tkinter.\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from e
    raise
PY

START_PATH="${1:-}"
if [[ -n "${START_PATH}" ]]; then
  echo "[image-viewer] launching with start path: ${START_PATH}"
  image-viewer "${START_PATH}"
else
  echo "[image-viewer] launching with current directory..."
  image-viewer
fi

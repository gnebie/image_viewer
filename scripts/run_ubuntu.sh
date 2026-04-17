#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

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

START_PATH="${1:-}"
if [[ -n "${START_PATH}" ]]; then
  echo "[image-viewer] launching with start path: ${START_PATH}"
  image-viewer "${START_PATH}"
else
  echo "[image-viewer] launching with current directory..."
  image-viewer
fi

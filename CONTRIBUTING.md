# Contributing

Thanks for your interest in contributing to `image_viewer`.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

On Ubuntu/Debian, install Tk:

```bash
sudo apt update
sudo apt install -y python3-tk
```

## Run tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

## Pull request guidelines

- Keep changes focused and documented.
- Add or update tests for behavior changes.
- Update docs when user-facing behavior changes.
- Use clear commit messages and PR descriptions.

## Reporting bugs

Please use the issue templates and include:
- OS and Python version
- steps to reproduce
- expected vs actual behavior

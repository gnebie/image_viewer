"""Pure helpers for thumbnail grid layout and keyboard navigation."""

from __future__ import annotations


def compute_columns(inner_width: int, slot_px: int, gap: int = 8) -> int:
    """How many columns fit in ``inner_width`` if each slot is ``slot_px`` wide plus ``gap``."""
    if inner_width <= 0 or slot_px <= 0:
        return 1
    step = slot_px + gap
    return max(1, (inner_width + gap) // step)


def rc_from_index(index: int, columns: int) -> tuple[int, int]:
    if columns <= 0:
        return 0, 0
    return index // columns, index % columns


def index_from_rc(row: int, col: int, columns: int, total: int) -> int:
    if total <= 0 or columns <= 0:
        return 0
    idx = row * columns + col
    return max(0, min(idx, total - 1))


def max_row_for_total(total: int, columns: int) -> int:
    if total <= 0 or columns <= 0:
        return 0
    return (total - 1) // columns


def clamp_col_for_row(row: int, col: int, columns: int, total: int) -> int:
    if total <= 0 or columns <= 0:
        return 0
    last_row = max_row_for_total(total, columns)
    row = max(0, min(row, last_row))
    last_index_in_row = min(total - 1, (row + 1) * columns - 1)
    max_col = last_index_in_row - row * columns
    return max(0, min(col, max_col))


def move_gallery_index(index: int, total: int, columns: int, drow: int, dcol: int) -> int:
    """Row-major grid: ``dcol`` moves ±1 in the flat list, ``drow`` moves by full rows."""
    if total <= 0:
        return 0
    cols = max(1, columns)
    new_index = index + dcol + drow * cols
    return max(0, min(new_index, total - 1))


def page_vertical(index: int, total: int, columns: int, rows_delta: int) -> int:
    """Move selection by ``rows_delta`` rows (negative = up / Page Up)."""
    if total <= 0 or columns <= 0 or rows_delta == 0:
        return index
    row, col = rc_from_index(index, columns)
    row = max(0, min(row + rows_delta, max_row_for_total(total, columns)))
    col = clamp_col_for_row(row, col, columns, total)
    return index_from_rc(row, col, columns, total)


def visible_rows(canvas_height: int, row_height: int) -> int:
    if row_height <= 0:
        return 1
    return max(1, (canvas_height + row_height - 1) // row_height)

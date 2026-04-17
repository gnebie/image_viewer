from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable


@dataclass(frozen=True)
class OperationRecord:
    kind: str
    src: str
    dest: str
    detail: str = ""


class OperationLog:
    def __init__(self, max_items: int = 20) -> None:
        self._items: Deque[OperationRecord] = deque(maxlen=max_items)

    def add(self, record: OperationRecord) -> None:
        self._items.appendleft(record)

    def items(self) -> Iterable[OperationRecord]:
        return tuple(self._items)

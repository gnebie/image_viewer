from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Literal, Optional

from .sources import ImageEntry, ImageSource


NavigationCommand = Literal["prev", "next", "first", "last"]
NavigationResult = Literal["stay", "show", "close"]


@dataclass
class SlideshowState:
    source: ImageSource
    images: List[ImageEntry]
    index: int = 0
    pending_navigation: Deque[NavigationCommand] = field(default_factory=deque)
    max_pending_navigation: int = 3

    def current_entry(self) -> Optional[ImageEntry]:
        if not self.images:
            return None
        return self.images[self.index]

    def enqueue_navigation(self, command: NavigationCommand) -> bool:
        if len(self.pending_navigation) >= self.max_pending_navigation:
            return False
        self.pending_navigation.append(command)
        return True

    def pop_navigation(self) -> Optional[NavigationCommand]:
        if not self.pending_navigation:
            return None
        return self.pending_navigation.popleft()

    def clear_navigation(self) -> None:
        self.pending_navigation.clear()


def clamp_index(index: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(index, total - 1))


def move_previous(state: SlideshowState) -> NavigationResult:
    if not state.images or state.index <= 0:
        return "close"
    state.index -= 1
    return "show"


def move_next(state: SlideshowState) -> NavigationResult:
    if not state.images or state.index >= len(state.images) - 1:
        return "close"
    state.index += 1
    return "show"


def move_first(state: SlideshowState) -> NavigationResult:
    if not state.images:
        return "close"
    if state.index == 0:
        return "stay"
    state.index = 0
    return "show"


def move_last(state: SlideshowState) -> NavigationResult:
    if not state.images:
        return "close"
    last_index = len(state.images) - 1
    if state.index == last_index:
        return "stay"
    state.index = last_index
    return "show"


def apply_navigation(state: SlideshowState, command: NavigationCommand) -> NavigationResult:
    if command == "prev":
        return move_previous(state)
    if command == "next":
        return move_next(state)
    if command == "first":
        return move_first(state)
    return move_last(state)

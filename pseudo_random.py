"""
pseudo_random.py — shuffle-bag picking ("non-repeating random").

A `random.choice()` on a small list will visibly repeat the same
value back-to-back fairly often — it's a 1-in-N coin flip on every
draw, and for N=5 that means a roughly 20% chance the next pick is
the same as the last. In a chat-bot context (or anywhere you want
the user to FEEL variety) that gets stale fast.

Apple's iPod "Shuffle" mode famously uses the trick we implement
here instead: shuffle the playlist into a queue, play through it,
reshuffle on exhaustion. Every item is yielded once per cycle, the
order LOOKS random, and you never hear the same song twice in a
row — except, naively, at the seam where one shuffle ends and the
next begins. `ShuffleBag` guards against that seam too.

Usage:

    >>> bag = ShuffleBag(["a", "b", "c"])
    >>> [bag.next() for _ in range(7)]
    ['b', 'c', 'a', 'c', 'a', 'b', 'a']   # any "c, c" or "a, a" pair
                                          # in a row is impossible

A single-item bag is a degenerate case — repeats are unavoidable
and the bag just keeps yielding the one item. An empty bag yields
None forever.
"""
from __future__ import annotations

import random
from typing import Iterable, Optional


class ShuffleBag:
    """Yield items from a source list in non-repeating shuffled order.

    The implementation keeps a `_queue` of items still to yield in
    the current cycle. When the queue empties we reshuffle the
    source and, if the freshly-shuffled queue would start with the
    same value we yielded last, swap that slot with a random later
    one — guaranteeing no back-to-back repeats across cycles.

    Thread-safety: not thread-safe. Pick the right bag and yield
    from it on a single thread (we always do this on the main
    thread in RLQuickChat, so it's fine).
    """

    __slots__ = ("_source", "_queue", "_last")

    def __init__(self, items: Iterable):
        # Materialise once so subsequent reshuffles don't reread an
        # exhaustible iterable, and so identity-equal items behave
        # predictably under `==` comparison.
        self._source = tuple(items)
        self._queue: list = []
        self._last = None

    def __len__(self) -> int:
        return len(self._source)

    def next(self) -> Optional[object]:
        """Yield the next item; return None if the source is empty."""
        if not self._source:
            return None
        if not self._queue:
            self._reshuffle()
        item = self._queue.pop(0)
        self._last = item
        return item

    def _reshuffle(self) -> None:
        items = list(self._source)
        random.shuffle(items)
        # Anti-seam swap: if the new cycle would start with the
        # same item we just yielded, push it to a random later
        # slot. Only meaningful for len > 1 — a single-item bag
        # has nothing to swap with.
        if (
            self._last is not None
            and len(items) > 1
            and items[0] == self._last
        ):
            swap_with = random.randint(1, len(items) - 1)
            items[0], items[swap_with] = items[swap_with], items[0]
        self._queue = items

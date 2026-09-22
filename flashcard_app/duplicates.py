"""Exact and near-duplicate detection for card fronts."""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import TypeVar

T = TypeVar("T")

NEAR_THRESHOLD = 0.9


def normalize_front(text: str) -> str:
    text = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    left = normalize_front(a)
    right = normalize_front(b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def is_near_duplicate(a: str, b: str, threshold: float = NEAR_THRESHOLD) -> bool:
    left = normalize_front(a)
    right = normalize_front(b)
    if not left or not right:
        return False
    if left == right:
        return True
    longer = max(len(left), len(right))
    shorter = min(len(left), len(right))
    if longer < 8 or shorter / longer < 0.75:
        return False
    return SequenceMatcher(None, left, right).ratio() >= threshold


def _bucket_key(normalized: str) -> str:
    words = [word for word in normalized.split() if len(word) >= 4]
    base = words[0] if words else normalized
    return base[:6]


def first_duplicate(
    front: str,
    others: list[tuple[T, str]],
    threshold: float = NEAR_THRESHOLD,
) -> str | None:
    """Return the other front text when `front` duplicates something in `others`."""
    normalized = normalize_front(front)
    if not normalized:
        return None
    buckets: dict[str, list[str]] = defaultdict(list)
    for _item, other in others:
        other_norm = normalize_front(other)
        if not other_norm:
            continue
        if other_norm == normalized:
            return other
        buckets[_bucket_key(other_norm)].append(other)
    if len(normalized) < 8:
        return None
    for other in buckets.get(_bucket_key(normalized), []):
        if is_near_duplicate(front, other, threshold):
            return other
    return None


def find_duplicate_groups(
    items: list[tuple[T, str]],
    threshold: float = NEAR_THRESHOLD,
) -> list[list[T]]:
    """Group item ids whose fronts are exact or near duplicates."""
    count = len(items)
    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    by_exact: dict[str, list[int]] = defaultdict(list)
    normalized: list[str] = []
    for index, (_item, front) in enumerate(items):
        text = normalize_front(front)
        normalized.append(text)
        if text:
            by_exact[text].append(index)
    for indexes in by_exact.values():
        for other in indexes[1:]:
            union(indexes[0], other)

    buckets: dict[str, list[int]] = defaultdict(list)
    for index, text in enumerate(normalized):
        if len(text) >= 8:
            buckets[_bucket_key(text)].append(index)
    for indexes in buckets.values():
        for left_i, left in enumerate(indexes):
            for right in indexes[left_i + 1 :]:
                if find(left) == find(right):
                    continue
                if is_near_duplicate(items[left][1], items[right][1], threshold):
                    union(left, right)

    grouped: dict[int, list[T]] = defaultdict(list)
    for index, (item, _front) in enumerate(items):
        grouped[find(index)].append(item)
    groups = [members for members in grouped.values() if len(members) > 1]
    groups.sort(key=len, reverse=True)
    return groups

"""Tag names stored on cards."""

from __future__ import annotations

import re


def normalize_tag(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"\s+", "-", name)
    name = name.replace(",", "").replace("|", "").replace("\x1f", "")
    if not name:
        raise ValueError("Empty tag")
    return name[:40]


def parse_tags(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,|]", value)
    else:
        parts = list(value)
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        try:
            name = normalize_tag(str(part))
        except ValueError:
            continue
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result

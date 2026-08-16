from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    stop = {"apartamento", "arriendo", "alquiler", "cali", "valle", "del", "cauca", "en"}
    return " ".join(word for word in text.split() if word not in stop)


def close_number(a: Any, b: Any, absolute: float, ratio: float) -> bool:
    if a is None or b is None:
        return True
    a, b = float(a), float(b)
    return abs(a - b) <= max(absolute, max(a, b) * ratio)


def compatible(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("source") == b.get("source"):
        return False

    zone_a, zone_b = normalized(a.get("zone")), normalized(b.get("zone"))
    generic = {"", "cali zona por confirmar"}
    if zone_a in generic or zone_b in generic or zone_a != zone_b:
        return False

    if not close_number(a.get("price"), b.get("price"), 50_000, 0.03):
        return False
    if a.get("price") is None or b.get("price") is None:
        return False

    for field in ("bedrooms", "bathrooms"):
        if a.get(field) is not None and b.get(field) is not None and a.get(field) != b.get(field):
            return False

    if not close_number(a.get("area_m2"), b.get("area_m2"), 4, 0.05):
        return False

    title_similarity = SequenceMatcher(None, normalized(a.get("title")), normalized(b.get("title"))).ratio()
    structured = sum(
        a.get(field) is not None and b.get(field) is not None
        for field in ("bedrooms", "bathrooms", "area_m2")
    )
    return title_similarity >= 0.48 or structured >= 3


def quality(item: dict[str, Any]) -> tuple[int, int, int]:
    structured = sum(item.get(k) is not None for k in ("price", "bedrooms", "bathrooms", "area_m2", "parking"))
    description = len(str(item.get("description") or ""))
    fresh = 0 if item.get("stale") else 1
    return fresh, structured, description


def merge_group(items: list[dict[str, Any]]) -> dict[str, Any]:
    primary = max(items, key=quality)
    merged = dict(primary)
    links = []
    seen = set()

    for item in items:
        key = (item.get("source"), item.get("url"))
        if key in seen:
            continue
        seen.add(key)
        links.append({"source": item.get("source"), "url": item.get("url")})

    sources = sorted({link["source"] for link in links if link.get("source")})
    merged["links"] = links
    merged["sources"] = sources
    merged["source_count"] = len(sources)
    merged["source"] = primary.get("source")
    merged["url"] = primary.get("url")
    merged["stale"] = all(bool(item.get("stale")) for item in items)
    merged["first_seen"] = min((item.get("first_seen") for item in items if item.get("first_seen")), default=primary.get("first_seen"))
    merged["last_seen"] = max((item.get("last_seen") for item in items if item.get("last_seen")), default=primary.get("last_seen"))
    return merged


def merge_duplicates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []

    for item in items:
        matched = None
        for group in groups:
            if compatible(item, group[0]):
                matched = group
                break
        if matched is None:
            groups.append([item])
        else:
            matched.append(item)

    return [merge_group(group) for group in groups]

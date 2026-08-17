from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

PRICE_PATTERNS = [
    re.compile(r"\$\s*([0-9]{1,3}(?:[.,\s][0-9]{3}){1,4}|[0-9]{6,12})", re.I),
    re.compile(r"(?:canon|arriendo|alquiler)\D{0,24}([0-9]{6,12})", re.I),
]
BED_PATTERNS = [re.compile(r"(\d+)\s*(?:hab(?:itaciones?)?|alcobas?)\b", re.I)]
BATH_PATTERNS = [re.compile(r"(\d+)\s*(?:bañ(?:o|os)|banos?)\b", re.I)]
AREA_PATTERNS = [re.compile(r"(\d+(?:[.,]\d+)?)\s*m(?:²|2)\b", re.I)]
PARKING_PATTERNS = [re.compile(r"(\d+)\s*(?:parq(?:ueaderos?)?|garajes?|estacionamientos?)\b", re.I)]
TYPE_PATTERN = re.compile(r"\b(apartamento|apto|apartaestudio|arriendo|alquiler)\b", re.I)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_url(base: str, href: str) -> str | None:
    if not href:
        return None
    parsed = urlparse(urljoin(base, href))
    if parsed.scheme not in {"http", "https"}:
        return None
    return urlunparse(parsed._replace(fragment="", query=""))


def allowed_url(url: str, source: dict[str, Any]) -> bool:
    parsed = urlparse(url)
    domains = {d.lower() for d in source.get("allowed_domains", [])}
    if parsed.netloc.lower() not in domains:
        return False
    pattern = source.get("listing_regex")
    return bool(pattern and re.search(pattern, parsed.path, re.I))


def parse_price(text: str) -> int | None:
    for pattern in PRICE_PATTERNS:
        for match in pattern.finditer(text):
            digits = re.sub(r"\D", "", match.group(1))
            if 6 <= len(digits) <= 12:
                value = int(digits)
                if value >= 250_000:
                    return value
    return None


def first_number(text: str, patterns: list[re.Pattern[str]]) -> int | float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", "."))
            return int(value) if value.is_integer() else value
        except ValueError:
            continue
    return None


def detect_location(text: str, zones: list[dict[str, Any]], macro_areas: list[dict[str, Any]]) -> tuple[str, str]:
    lower = text.casefold()
    for zone in zones:
        for alias in zone.get("aliases", []):
            if alias.casefold() in lower:
                return zone["name"], zone.get("macro", "Otra zona de Cali")
    for macro in macro_areas:
        for alias in macro.get("aliases", []):
            if alias.casefold() in lower:
                return f"{macro['name']} (barrio por confirmar)", macro["name"]
    return "Cali (zona por confirmar)", "Otra zona de Cali"


def canonical_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def ld_price(obj: dict[str, Any]) -> int | None:
    offers = obj.get("offers")
    candidates = offers if isinstance(offers, list) else [offers]
    for offer in candidates:
        if not isinstance(offer, dict):
            continue
        raw = offer.get("price") or offer.get("lowPrice")
        if raw is None:
            continue
        digits = re.sub(r"\D", "", str(raw))
        if digits and int(digits) >= 250_000:
            return int(digits)
    return None


def property_type(text: str) -> str:
    lower = text.casefold()
    if "apartaestudio" in lower:
        return "Apartaestudio"
    return "Apartamento"


def listing_from_text(
    source_name: str,
    url: str,
    text: str,
    title: str,
    zones: list[dict[str, Any]],
    macro_areas: list[dict[str, Any]],
    timestamp: str,
    explicit_price: int | None = None,
) -> dict[str, Any] | None:
    text = clean_text(text)
    title = clean_text(title) or "Apartamento en arriendo"
    combined = f"{title} {text}"
    if not TYPE_PATTERN.search(combined):
        return None
    if re.search(r"\b(venta|vendo|comprar)\b", combined, re.I) and not re.search(r"\b(arriendo|alquiler)\b", combined, re.I):
        return None

    zone, macro_zone = detect_location(combined, zones, macro_areas)
    if "cali" not in combined.casefold() and macro_zone == "Otra zona de Cali":
        return None

    price = explicit_price if explicit_price is not None else parse_price(combined)
    return {
        "id": canonical_key(url),
        "source": source_name,
        "url": url,
        "title": title[:180],
        "description": text[:520],
        "property_type": property_type(combined),
        "zone": zone,
        "macro_zone": macro_zone,
        "price": price,
        "bedrooms": first_number(combined, BED_PATTERNS),
        "bathrooms": first_number(combined, BATH_PATTERNS),
        "area_m2": first_number(combined, AREA_PATTERNS),
        "parking": first_number(combined, PARKING_PATTERNS),
        "first_seen": timestamp,
        "last_seen": timestamp,
        "stale": False,
    }


def extract_json_ld(
    soup: BeautifulSoup,
    source: dict[str, Any],
    page_url: str,
    zones: list[dict[str, Any]],
    macro_areas: list[dict[str, Any]],
    timestamp: str,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for obj in walk_json(payload):
            raw_url = obj.get("url")
            if isinstance(raw_url, dict):
                raw_url = raw_url.get("@id")
            if not isinstance(raw_url, str):
                continue
            url = normalize_url(page_url, raw_url)
            if not url or url == normalize_url(page_url, page_url) or not allowed_url(url, source):
                continue

            title = clean_text(obj.get("name") or obj.get("headline"))
            description = clean_text(obj.get("description"))
            item = listing_from_text(
                source["name"], url, f"{title} {description}", title,
                zones, macro_areas, timestamp, ld_price(obj)
            )
            if item:
                found.append(item)
    return found


def useful_context(anchor) -> str:
    candidate = anchor
    best = clean_text(anchor.get_text(" ", strip=True))
    for _ in range(6):
        parent = getattr(candidate, "parent", None)
        if parent is None:
            break
        text = clean_text(parent.get_text(" ", strip=True))
        if 45 <= len(text) <= 1800 and ("$" in text or PRICE_PATTERNS[1].search(text)):
            best = text
            if TYPE_PATTERN.search(text):
                break
        candidate = parent
    return best


def extract_anchors(
    soup: BeautifulSoup,
    source: dict[str, Any],
    page_url: str,
    zones: list[dict[str, Any]],
    macro_areas: list[dict[str, Any]],
    timestamp: str,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    page_normalized = normalize_url(page_url, page_url)
    for anchor in soup.find_all("a", href=True):
        url = normalize_url(page_url, anchor.get("href", ""))
        if not url or url == page_normalized or not allowed_url(url, source):
            continue

        title = clean_text(anchor.get("aria-label") or anchor.get("title") or anchor.get_text(" ", strip=True))
        text = useful_context(anchor)
        item = listing_from_text(
            source["name"], url, text, title or text[:150],
            zones, macro_areas, timestamp
        )
        if item:
            found.append(item)
    return found


def dedupe_urls(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    score_fields = ("price", "bedrooms", "bathrooms", "area_m2", "parking")
    for item in items:
        current = best.get(item["url"])
        if current is None:
            best[item["url"]] = item
            continue
        current_score = sum(current.get(key) is not None for key in score_fields)
        item_score = sum(item.get(key) is not None for key in score_fields)
        if item_score > current_score:
            item["first_seen"] = current.get("first_seen", item["first_seen"])
            best[item["url"]] = item
    return list(best.values())


def fetch_with_retry(session: requests.Session, url: str, timeout: int, attempts: int = 2):
    """Reintenta una vez ante errores transitorios (timeout, conexión) antes de darse por vencido."""
    last_exc = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            continue
    raise last_exc


def scrape_source(
    session: requests.Session,
    source: dict[str, Any],
    zones: list[dict[str, Any]],
    macro_areas: list[dict[str, Any]],
    timestamp: str,
    timeout: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []

    for page_url in source.get("urls", []):
        try:
            response = fetch_with_retry(session, page_url, timeout)
            soup = BeautifulSoup(response.text, "html.parser")
            items.extend(extract_json_ld(soup, source, response.url, zones, macro_areas, timestamp))
            items.extend(extract_anchors(soup, source, response.url, zones, macro_areas, timestamp))
        except requests.RequestException as exc:
            errors.append(f"{page_url}: {type(exc).__name__}")
        except Exception as exc:  # noqa: BLE001 - una fuente mal formada nunca debe tumbar todo el pipeline
            errors.append(f"{page_url}: error de análisis ({type(exc).__name__})")

    unique = dedupe_urls(items)
    limit = int(source.get("max_items", 100))
    return unique[:limit], errors

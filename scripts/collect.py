#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from dedupe import merge_duplicates
from scrape import scrape_source

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
AREAS_PATH = ROOT / "config" / "areas.json"
OUTPUT_PATH = ROOT / "data" / "listings.json"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36 CaliArriendos/4.0"


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_dt().replace(microsecond=0).isoformat()


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def source_due(source: dict[str, Any], previous_status: dict[str, Any] | None, force_all: bool) -> bool:
    if force_all:
        return True
    cadence = int(source.get("cadence_hours", 4))
    if cadence <= 0:
        return False
    if not previous_status:
        return True
    last_checked = parse_iso(previous_status.get("last_checked"))
    if not last_checked:
        return True
    return now_dt() - last_checked.astimezone(timezone.utc) >= timedelta(hours=cadence)


def expand_previous(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded = []
    for item in items:
        links = item.get("links")
        if not isinstance(links, list) or not links:
            clone = dict(item)
            clone.pop("links", None)
            clone.pop("sources", None)
            clone.pop("source_count", None)
            expanded.append(clone)
            continue

        for link in links:
            url, source = link.get("url"), link.get("source")
            if not url or not source:
                continue
            clone = dict(item)
            clone["url"] = url
            clone["source"] = source
            clone.pop("links", None)
            clone.pop("sources", None)
            clone.pop("source_count", None)
            expanded.append(clone)
    return expanded


def merge_history(
    fresh: list[dict[str, Any]],
    previous: list[dict[str, Any]],
    checked: dict[str, bool],
    ttl_days: int,
) -> list[dict[str, Any]]:
    fresh_by_url = {item["url"]: item for item in fresh if item.get("url")}
    old_by_url = {item["url"]: item for item in expand_previous(previous) if item.get("url")}
    merged: dict[str, dict[str, Any]] = {}
    now = now_dt()

    for url, item in fresh_by_url.items():
        old = old_by_url.get(url)
        if old:
            item["first_seen"] = old.get("first_seen") or item.get("first_seen")
        item["stale"] = False
        merged[url] = item

    for url, old in old_by_url.items():
        if url in merged:
            continue
        last_seen = parse_iso(old.get("last_seen"))
        if not last_seen:
            continue
        if now - last_seen.astimezone(timezone.utc) > timedelta(days=ttl_days):
            continue

        kept = dict(old)
        source = str(old.get("source") or "")
        if source in checked and checked[source]:
            kept["stale"] = True
        merged[url] = kept

    return list(merged.values())


def listing_sort(item: dict[str, Any]):
    price = item.get("price")
    return (
        bool(item.get("stale")),
        price is None,
        price if isinstance(price, int) else 10**15,
        str(item.get("zone") or ""),
    )


def previous_status_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    statuses = payload.get("meta", {}).get("sources", [])
    return {str(status.get("name")): status for status in statuses if status.get("name")}


def status_base(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": source["name"],
        "tier": source.get("tier", "secondary"),
        "cadence_hours": int(source.get("cadence_hours", 0)),
        "automated": bool(source.get("automated", False)),
        "ok": None,
        "found": 0,
        "errors": [],
        "last_checked": None,
        "skipped": False,
        "manual_urls": source.get("manual_urls", source.get("urls", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recolector multi-fuente de Cali Arriendos.")
    parser.add_argument("--no-network", action="store_true", help="Valida configuración sin consultar portales.")
    parser.add_argument("--all", action="store_true", help="Fuerza la revisión de todas las fuentes automáticas.")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, {})
    areas = load_json(AREAS_PATH, {})
    previous = load_json(OUTPUT_PATH, {"meta": {}, "listings": []})

    site = config.get("site", {})
    sources = config.get("sources", [])
    zones = areas.get("zones", [])
    macro_areas = areas.get("macro_areas", [])
    ttl_days = int(site.get("stale_ttl_days", 14))
    timeout = int(site.get("request_timeout_seconds", 24))
    max_total = int(site.get("max_total_listings", 1200))
    previous_statuses = previous_status_map(previous)

    if args.no_network:
        assert sources and zones and macro_areas
        print(f"Configuración válida: {len(sources)} fuentes, {len(zones)} barrios/sectores.")
        return 0

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CO,es;q=0.9,en;q=0.5",
        "Cache-Control": "no-cache",
    })

    fresh: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    checked_success: dict[str, bool] = {}
    timestamp = now_iso()

    for source in sources:
        status = status_base(source)
        previous_status = previous_statuses.get(source["name"])

        if not source.get("automated", False):
            status["skipped"] = True
            status["last_checked"] = previous_status.get("last_checked") if previous_status else None
            statuses.append(status)
            continue

        if not source_due(source, previous_status, args.all):
            status.update({
                "ok": previous_status.get("ok") if previous_status else None,
                "found": previous_status.get("found", 0) if previous_status else 0,
                "errors": previous_status.get("errors", []) if previous_status else [],
                "last_checked": previous_status.get("last_checked") if previous_status else None,
                "skipped": True,
            })
            statuses.append(status)
            continue

        items, errors = scrape_source(session, source, zones, macro_areas, timestamp, timeout)
        total_urls = max(1, len(source.get("urls", [])))
        ok = len(errors) < total_urls
        checked_success[source["name"]] = ok

        status.update({
            "ok": ok,
            "found": len(items),
            "errors": errors[:5],
            "last_checked": timestamp,
            "skipped": False,
        })
        statuses.append(status)
        fresh.extend(items)

    historical = merge_history(
        fresh,
        previous.get("listings", []),
        checked_success,
        ttl_days,
    )
    grouped = merge_duplicates(historical)
    grouped.sort(key=listing_sort)
    grouped = grouped[:max_total]

    payload = {
        "meta": {
            "version": 4,
            "updated_at": timestamp,
            "price_policy": "no_fixed_cap",
            "total": len(grouped),
            "source_count": len(sources),
            "automated_source_count": sum(bool(s.get("automated")) for s in sources),
            "sources": statuses,
        },
        "listings": grouped,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Actualización V4: {len(grouped)} avisos agrupados.")
    for status in statuses:
        state = "manual" if not status["automated"] else ("omitida" if status["skipped"] else ("ok" if status["ok"] else "falló"))
        print(f"- {status['name']}: {state}; {status['found']} resultados")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
CONFIG_PATH=ROOT/"config"/"sources.json"
AREAS_PATH=ROOT/"config"/"areas.json"
OUTPUT_PATH=ROOT/"data"/"listings.json"
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36 CaliArriendos/1.0"

PRICE_PATTERNS=[
    re.compile(r"\$\s*([0-9]{1,3}(?:[.,\s][0-9]{3}){1,4}|[0-9]{6,12})",re.I),
    re.compile(r"(?:canon|arriendo|alquiler)\D{0,22}([0-9]{6,12})",re.I),
]
BED_PATTERNS=[re.compile(r"(\d+)\s*(?:hab(?:itaciones?)?|alcobas?)\b",re.I)]
BATH_PATTERNS=[re.compile(r"(\d+)\s*(?:bañ(?:o|os)|banos?)\b",re.I)]
AREA_PATTERNS=[re.compile(r"(\d+(?:[.,]\d+)?)\s*m(?:²|2)\b",re.I)]
PARKING_PATTERNS=[re.compile(r"(\d+)\s*(?:parq(?:ueaderos?)?|garajes?)\b",re.I)]

def now_utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_json(path:Path,fallback:Any):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):return fallback

def clean_text(value:Any)->str:
    if value is None:return""
    return re.sub(r"\s+"," ",str(value)).strip()

def normalize_url(base:str,href:str):
    if not href:return None
    parsed=urlparse(urljoin(base,href))
    if parsed.scheme not in {"http","https"}:return None
    return urlunparse(parsed._replace(fragment="",query=""))

def allowed_url(url:str,source:dict[str,Any])->bool:
    parsed=urlparse(url)
    if parsed.netloc.lower() not in {d.lower() for d in source.get("allowed_domains",[])}:return False
    pattern=source.get("listing_regex")
    return bool(pattern and re.search(pattern,parsed.path,re.I))

def parse_price(text:str):
    for pattern in PRICE_PATTERNS:
        for match in pattern.finditer(text):
            digits=re.sub(r"\D","",match.group(1))
            if 6<=len(digits)<=12:
                value=int(digits)
                if value>=300_000:return value
    return None

def first_number(text:str,patterns):
    for pattern in patterns:
        match=pattern.search(text)
        if not match:continue
        try:
            value=float(match.group(1).replace(",","."))
            return int(value) if value.is_integer() else value
        except ValueError:continue
    return None

def detect_location(text:str,zones,macro_areas):
    lower=text.casefold()
    for zone in zones:
        for alias in zone.get("aliases",[]):
            if alias.casefold() in lower:
                return zone["name"],zone.get("macro","Otra zona de Cali")
    for macro in macro_areas:
        for alias in macro.get("aliases",[]):
            if alias.casefold() in lower:
                return f"{macro['name']} (barrio por confirmar)",macro["name"]
    return"Cali (zona por confirmar)","Otra zona de Cali"

def canonical_key(url:str)->str:return hashlib.sha1(url.encode()).hexdigest()[:16]

def walk_json(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from walk_json(child)
    elif isinstance(value,list):
        for child in value:yield from walk_json(child)

def ld_price(obj):
    offers=obj.get("offers")
    for offer in offers if isinstance(offers,list) else [offers]:
        if not isinstance(offer,dict):continue
        raw=offer.get("price") or offer.get("lowPrice")
        if raw is None:continue
        digits=re.sub(r"\D","",str(raw))
        if digits:
            value=int(digits)
            if value>=300_000:return value
    return None

def listing_from_text(source_name,url,text,title,zones,macro_areas,explicit_price=None):
    text,title=clean_text(text),clean_text(title) or"Apartamento en arriendo"
    combined=f"{title} {text}"
    if not re.search(r"\b(apartamento|apto|arriendo|alquiler)\b",combined,re.I):return None
    zone,macro_zone=detect_location(combined,zones,macro_areas)
    if "cali" not in combined.casefold() and macro_zone=="Otra zona de Cali":return None
    price=explicit_price if explicit_price is not None else parse_price(combined)
    timestamp=now_utc()
    return{
        "id":canonical_key(url),"source":source_name,"url":url,"title":title[:180],"description":text[:420],
        "zone":zone,"macro_zone":macro_zone,"price":price,"bedrooms":first_number(combined,BED_PATTERNS),
        "bathrooms":first_number(combined,BATH_PATTERNS),"area_m2":first_number(combined,AREA_PATTERNS),
        "parking":first_number(combined,PARKING_PATTERNS),"first_seen":timestamp,"last_seen":timestamp,"stale":False
    }

def extract_json_ld(soup,source,page_url,zones,macro_areas):
    found=[]
    for script in soup.find_all("script",attrs={"type":"application/ld+json"}):
        raw=script.string or script.get_text()
        if not raw.strip():continue
        try:payload=json.loads(raw)
        except json.JSONDecodeError:continue
        for obj in walk_json(payload):
            raw_url=obj.get("url")
            if isinstance(raw_url,dict):raw_url=raw_url.get("@id")
            if not isinstance(raw_url,str):continue
            url=normalize_url(page_url,raw_url)
            if not url or not allowed_url(url,source):continue
            title=clean_text(obj.get("name") or obj.get("headline"))
            description=clean_text(obj.get("description"))
            item=listing_from_text(source["name"],url,f"{title} {description}",title,zones,macro_areas,ld_price(obj))
            if item:found.append(item)
    return found

def extract_anchors(soup,source,page_url,zones,macro_areas):
    found=[]
    for anchor in soup.find_all("a",href=True):
        url=normalize_url(page_url,anchor.get("href",""))
        if not url or not allowed_url(url,source):continue
        title=clean_text(anchor.get("aria-label") or anchor.get_text(" ",strip=True))
        container=anchor
        for _ in range(4):
            if container.parent is None:break
            parent=container.parent
            if len(clean_text(parent.get_text(" ",strip=True)))>=65:
                container=parent;break
            container=parent
        text=clean_text(container.get_text(" ",strip=True)) or title
        item=listing_from_text(source["name"],url,text,title or text[:120],zones,macro_areas)
        if item:found.append(item)
    return found

def dedupe(items):
    best={}
    for item in items:
        current=best.get(item["url"])
        if current is None:best[item["url"]]=item;continue
        score=lambda x:sum(x.get(k) is not None for k in ("price","bedrooms","bathrooms","area_m2"))
        if score(item)>score(current):
            item["first_seen"]=current.get("first_seen",item["first_seen"])
            best[item["url"]]=item
    return list(best.values())

def fetch_source(session,source,zones,macro_areas):
    items,errors=[],[]
    for page_url in source.get("urls",[]):
        try:
            response=session.get(page_url,timeout=24,allow_redirects=True);response.raise_for_status()
            soup=BeautifulSoup(response.text,"html.parser")
            items+=extract_json_ld(soup,source,response.url,zones,macro_areas)
            items+=extract_anchors(soup,source,response.url,zones,macro_areas)
        except requests.RequestException as exc:errors.append(f"{page_url}: {type(exc).__name__}")
    return dedupe(items),errors

def parse_iso(value):
    if not value:return None
    try:return datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:return None

def merge_previous(fresh,previous,source_status,ttl_days):
    now=datetime.now(timezone.utc);fresh_by={x["url"]:x for x in fresh};old_by={x.get("url"):x for x in previous if x.get("url")};merged={}
    for url,item in fresh_by.items():
        old=old_by.get(url)
        if old:item["first_seen"]=old.get("first_seen") or item["first_seen"]
        item["stale"]=False;merged[url]=item
    for url,old in old_by.items():
        if url in merged:continue
        last_seen=parse_iso(old.get("last_seen"))
        if not last_seen or now-last_seen.astimezone(timezone.utc)>timedelta(days=ttl_days):continue
        kept=dict(old);source=old.get("source","")
        kept["stale"]=True if source_status.get(source,False) else old.get("stale",False)
        merged[url]=kept
    return list(merged.values())

def sort_key(item):
    price=item.get("price")
    return(price is None,price if isinstance(price,int) else 10**12,str(item.get("zone","")),str(item.get("source","")))

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--no-network",action="store_true");args=parser.parse_args()
    config=load_json(CONFIG_PATH,{});areas=load_json(AREAS_PATH,{"zones":[],"macro_areas":[]});previous=load_json(OUTPUT_PATH,{"listings":[]});site=config.get("site",{})
    zones,macro_areas,sources=areas.get("zones",[]),areas.get("macro_areas",[]),config.get("sources",[]);ttl=int(site.get("stale_ttl_days",14))
    session=requests.Session();session.headers.update({"User-Agent":USER_AGENT,"Accept-Language":"es-CO,es;q=0.9,en;q=0.6"})
    fresh,statuses,source_ok=[],[],{}
    for source in sources:
        automated=bool(source.get("automated",False))
        status={"name":source["name"],"automated":automated,"ok":None,"found":0,"errors":[],"manual_urls":source.get("manual_urls",source.get("urls",[])),"manual_urls_by_area":source.get("manual_urls_by_area",{})}
        if not automated or args.no_network:statuses.append(status);continue
        items,errors=fetch_source(session,source,zones,macro_areas)
        status["ok"]=len(errors)<len(source.get("urls",[]));status["found"]=len(items);status["errors"]=errors[:5]
        source_ok[source["name"]]=bool(status["ok"]);fresh+=items;statuses.append(status)
    if args.no_network:print("Configuración válida.");return 0
    merged=merge_previous(dedupe(fresh),previous.get("listings",[]),source_ok,ttl)
    merged.sort(key=sort_key)
    payload={"meta":{"updated_at":now_utc(),"price_filter":"user-controlled","total":len(merged),"sources":statuses},"listings":merged}
    OUTPUT_PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Actualización terminada: {len(merged)} avisos visibles.")
    for s in statuses:print(f"- {s['name']}: ok={s['ok']} encontrados={s['found']}")
    return 0

if __name__=="__main__":sys.exit(main())

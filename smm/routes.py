"""
SMM AI Department — Routes and business logic.
Extracted from server.py for modularity.
"""

import asyncio
import json
import os
import signal
import subprocess
import time
import urllib.request
import urllib.error
import re as _re_smm
import unicodedata as _ucd
import xml.etree.ElementTree as _ET
import threading as _threading
from pathlib import Path
from datetime import datetime as _dt
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

router = APIRouter()

# SMM Database + Data Directories
from smm.db import (init_db, migrate_json_to_db, queue_list, queue_get, queue_add,
                     queue_update, queue_delete, queue_get_scheduled, queue_cleanup_old,
                     queue_count, trends_save, trends_latest, trends_count,
                     trends_list, trends_get_by_id, analytics_save, analytics_get_latest,
                     analytics_summary)

_smm_trend_scan: dict = {"status": "idle"}

SMM_PROFILES_DIR = Path("smm_profiles")
SMM_PROFILES_DIR.mkdir(exist_ok=True)
SMM_TRENDS_DIR = Path("smm_trends")
SMM_TRENDS_DIR.mkdir(exist_ok=True)
SMM_QUEUE_DIR = Path("smm_queue")
SMM_QUEUE_DIR.mkdir(exist_ok=True)
SMM_IMG_DIR = Path("smm_images")
SMM_IMG_DIR.mkdir(exist_ok=True)
COMFYUI_OUTPUT = Path("/home/definitelynotme/Desktop/ComfyUI/output")

# These will be set by register_smm_routes()
_start_module = None
_stop_module = None
_load_modules = None

def register_dependencies(load_modules_fn, start_module_fn, stop_module_fn):
    global _load_modules, _start_module, _stop_module
    _load_modules = load_modules_fn
    _start_module = start_module_fn
    _stop_module = stop_module_fn
    # Initialize database and migrate existing JSON data
    init_db()
    if queue_count() == 0 and SMM_QUEUE_DIR.exists() and list(SMM_QUEUE_DIR.glob("*.json")):
        mq, mt = migrate_json_to_db(SMM_QUEUE_DIR, SMM_TRENDS_DIR)
        if mq or mt:
            print(f"SMM: Migrated {mq} queue items, {mt} trend reports to SQLite")

# ─── SMM AI Department ───────────────────────────────────────────

import re as _re_smm
from datetime import datetime as _dt


def _smm_safe_id(id_str: str) -> str:
    """Sanitize ID to prevent path traversal."""
    return _re_smm.sub(r'[^a-z0-9а-яё\-_]', '', id_str.lower().strip())


def _smm_slugify(name: str) -> str:
    slug = name.lower().strip().replace(" ", "-")
    slug = _re_smm.sub(r'[^a-z0-9а-яё\-]', '', slug)
    return slug or "profile"


def _smm_unique_id(name: str) -> str:
    slug = _smm_slugify(name)
    if not (SMM_PROFILES_DIR / f"{slug}.json").exists():
        return slug
    import uuid
    return f"{slug}-{uuid.uuid4().hex[:6]}"


def _smm_strip_credentials(profile: dict) -> dict:
    """Remove sensitive tokens from profile for API response."""
    p = json.loads(json.dumps(profile))  # deep copy via JSON
    secret_keys = {"bot_token", "webhook", "api_key", "api_secret", "access_token",
                   "access_secret", "page_token", "person_urn", "account_id", "user_id"}
    for platform, config in p.get("platforms", {}).items():
        if isinstance(config, dict):
            has_creds = any(k in config and config[k] for k in secret_keys)
            config["connected"] = has_creds
            for k in secret_keys:
                if k in config:
                    config[k] = "***" if config[k] else ""
    return p


@router.get("/api/smm/profiles")
async def smm_list_profiles():
    profiles = []
    for f in sorted(SMM_PROFILES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            profiles.append(_smm_strip_credentials(json.loads(f.read_text())))
        except Exception:
            pass
    return {"ok": True, "profiles": profiles}


@router.get("/api/smm/profiles/{profile_id}")
async def smm_get_profile(profile_id: str):
    profile_id = _smm_safe_id(profile_id)
    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}
    return {"ok": True, "profile": _smm_strip_credentials(json.loads(path.read_text()))}


@router.post("/api/smm/profiles")
async def smm_create_profile(request: Request):
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return {"ok": False, "message": "Profile name is required"}
    pid = _smm_unique_id(name)
    now = _dt.now().isoformat(timespec="seconds")
    profile = {
        "id": pid,
        "name": name,
        "niche": data.get("niche", ""),
        "tone": data.get("tone", "professional"),
        "language": data.get("language", "ru"),
        "hashtags": data.get("hashtags", []),
        "competitors": data.get("competitors", []),
        "visual_style": data.get("visual_style", "tech-dark"),
        "platforms": data.get("platforms", {
            "telegram": {"enabled": False}, "linkedin": {"enabled": False},
            "twitter": {"enabled": False}, "facebook": {"enabled": False},
            "instagram": {"enabled": False}, "threads": {"enabled": False},
            "discord": {"enabled": False},
        }),
        "posting_schedule": data.get("posting_schedule", {}),
        "created": now,
        "updated": now,
    }
    (SMM_PROFILES_DIR / f"{pid}.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2))
    return {"ok": True, "id": pid, "message": "Profile created"}


@router.put("/api/smm/profiles/{profile_id}")
async def smm_update_profile(profile_id: str, request: Request):
    profile_id = _smm_safe_id(profile_id)
    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}
    existing = json.loads(path.read_text())
    data = await request.json()
    for key in ("name", "niche", "tone", "language", "hashtags", "competitors",
                "visual_style", "posting_schedule"):
        if key in data:
            existing[key] = data[key]
    # Merge platforms carefully — don't overwrite real tokens with "***"
    if "platforms" in data:
        for plat, new_cfg in data["platforms"].items():
            if not isinstance(new_cfg, dict):
                continue
            old_cfg = existing.get("platforms", {}).get(plat, {})
            for k, v in new_cfg.items():
                if v == "***":
                    continue  # Skip masked credentials — keep existing
                old_cfg[k] = v
            existing.setdefault("platforms", {})[plat] = old_cfg
    existing["updated"] = _dt.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    return {"ok": True, "message": "Profile updated"}


@router.delete("/api/smm/profiles/{profile_id}")
async def smm_delete_profile(profile_id: str):
    profile_id = _smm_safe_id(profile_id)
    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}
    path.unlink()
    return {"ok": True, "message": "Profile deleted"}


# ─── SMM Trend Sources ───────────────────────────────────────────

import unicodedata as _ucd
import xml.etree.ElementTree as _ET


def _has_cjk(text: str) -> bool:
    """Detect Chinese/Japanese/Korean characters."""
    return any(_ucd.category(c).startswith('Lo') and ord(c) > 0x2E80 for c in text[:100])


def _smm_src_reddit(subreddits: list, keywords: list, **kw) -> list:
    """Fetch Reddit content via SearXNG + RSS feeds. V4."""
    import urllib.parse as _up
    results = []
    seen = set()
    _reddit_errors = []

    # Strategy 1: SearXNG site:reddit.com (most reliable)
    # Use English keywords for Reddit (international platform)
    _ru_en = {"ресторан": "restaurant", "еда": "food", "рецепт": "recipe", "кафе": "cafe",
              "фитнес": "fitness", "тренировк": "workout", "питание": "nutrition", "зож": "health",
              "крипто": "crypto", "блокчейн": "blockchain", "дизайн": "design", "бизнес": "business",
              "стартап": "startup", "маркетинг": "marketing", "игр": "gaming", "музык": "music",
              "кулинар": "cooking", "кухня": "cuisine", "спорт": "sport"}
    en_keywords = []
    for keyword in keywords[:6]:
        kw_low = keyword.lower()
        translated = False
        for ru, en in _ru_en.items():
            if ru in kw_low:
                en_keywords.append(en)
                translated = True
                break
        if not translated:
            en_keywords.append(keyword)
    reddit_keywords = list(dict.fromkeys(en_keywords))  # deduplicate preserving order

    for keyword in reddit_keywords[:4]:
        try:
            q = _up.quote(f"reddit {keyword}")
            url = f"http://localhost:8888/search?q={q}&format=json&time_range=week&engines=google,bing,duckduckgo"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            for r in data.get("results", [])[:12]:
                rurl = r.get("url", "")
                if not rurl or rurl in seen or "/wiki/" in rurl:
                    continue
                # Only keep actual Reddit post URLs
                if "reddit.com/r/" not in rurl:
                    continue
                seen.add(rurl)
                results.append({
                    "title": r.get("title", "").replace(" : ", ": ").replace("on Reddit", "").strip(),
                    "url": rurl,
                    "content": r.get("content", "")[:400],
                    "published": r.get("publishedDate", ""),
                    "source_type": "reddit",
                    "engagement": 0,
                    "extra": f"Reddit (via search)",
                })
        except Exception:
            pass

    # Strategy 2: Reddit RSS feeds (backup, no auth needed)
    for sub in subreddits[:3]:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot/.rss?limit=10"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
            root = _ET.fromstring(xml_data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns)[:8]:
                title = (entry.findtext("atom:title", "", ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                if not title or link in seen or title.startswith("[D]"):
                    continue
                seen.add(link)
                content = entry.findtext("atom:content", "", ns) or ""
                content = _re_smm.sub(r'<[^>]+>', '', content)[:400]
                results.append({
                    "title": title,
                    "url": link,
                    "content": content,
                    "published": (entry.findtext("atom:updated", "", ns) or "")[:25],
                    "source_type": "reddit",
                    "engagement": 0,
                    "extra": f"r/{sub} (RSS)",
                })
        except Exception as e:
            _reddit_errors.append(f"RSS r/{sub}: {e}")
        time.sleep(1)

    # If no results, write errors to debug
    if not results and _reddit_errors:
        try:
            (SMM_TRENDS_DIR / "_reddit_debug.txt").write_text(
                f"errors={_reddit_errors}\nkeywords={keywords}\nsubreddits={subreddits}\n"
                f"reddit_keywords={reddit_keywords}\n")
        except Exception:
            pass
    return results


def _smm_src_hackernews(keywords: list, **kw) -> list:
    """Fetch stories from HackerNews Algolia API."""
    results = []
    seen = set()
    for keyword in keywords[:4]:
        try:
            q = urllib.request.quote(keyword)
            url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&numericFilters=points%3E15&hitsPerPage=12"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            for hit in data.get("hits", []):
                hurl = hit.get("url", "") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                if hurl in seen:
                    continue
                seen.add(hurl)
                points = hit.get("points", 0) or 0
                comments = hit.get("num_comments", 0) or 0
                results.append({
                    "title": hit.get("title", ""),
                    "url": hurl,
                    "content": (hit.get("story_text", "") or hit.get("title", ""))[:400],
                    "published": hit.get("created_at", "")[:10],
                    "source_type": "hackernews",
                    "engagement": points + comments,
                    "extra": f"HN ⬆{points} 💬{comments}",
                })
        except Exception:
            pass
    return results


def _smm_src_rss(feeds: list, **kw) -> list:
    """Fetch articles from RSS feeds (stdlib XML parser)."""
    results = []
    seen = set()
    for feed_url in feeds[:6]:
        try:
            req = urllib.request.Request(feed_url, headers={"User-Agent": "SMM-TrendScout/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()
            root = _ET.fromstring(xml_data)
            # Handle both RSS and Atom
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//item") or root.findall(".//atom:entry", ns)
            for item in items[:10]:
                title = (item.findtext("title") or item.findtext("atom:title", "", ns) or "").strip()
                link = (item.findtext("link") or "")
                if not link:
                    link_el = item.find("atom:link", ns)
                    link = link_el.get("href", "") if link_el is not None else ""
                if not title or link in seen:
                    continue
                seen.add(link)
                desc = item.findtext("description") or item.findtext("atom:summary", "", ns) or ""
                # Strip HTML tags from description
                desc = _re_smm.sub(r'<[^>]+>', '', desc)[:400]
                pub = item.findtext("pubDate") or item.findtext("atom:published", "", ns) or ""
                results.append({
                    "title": title,
                    "url": link,
                    "content": desc,
                    "published": pub[:25],
                    "source_type": "rss",
                    "engagement": 0,
                    "extra": f"RSS: {feed_url.split('/')[2] if '/' in feed_url else feed_url}",
                })
        except Exception:
            pass
    return results


def _smm_src_github(keywords: list, **kw) -> list:
    """Fetch trending repos from GitHub API."""
    results = []
    seen = set()
    week_ago = (_dt.now() - __import__('datetime').timedelta(days=7)).strftime("%Y-%m-%d")
    for keyword in keywords[:3]:
        try:
            q = urllib.request.quote(f"{keyword} created:>{week_ago}")
            url = f"https://api.github.com/search/repositories?q={q}&sort=stars&per_page=8"
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "SMM-TrendScout/1.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            for repo in data.get("items", []):
                rurl = repo.get("html_url", "")
                if rurl in seen:
                    continue
                seen.add(rurl)
                stars = repo.get("stargazers_count", 0)
                results.append({
                    "title": f"[GitHub] {repo.get('full_name', '')}",
                    "url": rurl,
                    "content": (repo.get("description", "") or "")[:400],
                    "published": (repo.get("created_at", "") or "")[:10],
                    "source_type": "github",
                    "engagement": stars,
                    "extra": f"⭐{stars} {repo.get('language', '')}",
                })
        except Exception:
            pass
    return results


def _smm_src_github_trending_ai(**kw) -> list:
    """Fetch hottest AI/ML/LLM repos from GitHub — created in last 7 days, sorted by stars."""
    results = []
    seen = set()
    week_ago = (_dt.now() - __import__('datetime').timedelta(days=7)).strftime("%Y-%m-%d")


    queries = [
        f"AI OR LLM OR \"large language model\" created:>{week_ago}",
        f"agents OR \"AI agent\" created:>{week_ago}",
        f"\"stable diffusion\" OR comfyui OR \"image generation\" created:>{week_ago}",
        f"RAG OR \"retrieval augmented\" OR embedding created:>{week_ago}",
        f"fine-tuning OR LoRA OR PEFT created:>{week_ago}",
    ]

    for q_raw in queries:
        try:
            q = urllib.request.quote(q_raw)
            url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=10"
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "SMM-TrendScout/2.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            for repo in data.get("items", []):
                rurl = repo.get("html_url", "")
                if rurl in seen or repo.get("stargazers_count", 0) < 10:
                    continue
                seen.add(rurl)
                stars = repo.get("stargazers_count", 0)
                forks = repo.get("forks_count", 0)
                lang = repo.get("language", "") or ""
                created = (repo.get("created_at", "") or "")[:10]
                days_old = (_dt.now() - _dt.strptime(created, "%Y-%m-%d")).days if created else 0
                stars_per_day = round(stars / max(days_old, 1))
                results.append({
                    "title": repo.get("full_name", ""),
                    "url": rurl,
                    "content": (repo.get("description", "") or "")[:400],
                    "published": created,
                    "source_type": "github_trending",
                    "engagement": stars + forks * 3,
                    "extra": f"⭐{stars} ({stars_per_day}/day) 🍴{forks} {lang}",
                    "repo_data": {
                        "full_name": repo.get("full_name", ""),
                        "stars": stars,
                        "forks": forks,
                        "language": lang,
                        "created": created,
                        "stars_per_day": stars_per_day,
                        "topics": repo.get("topics", [])[:5],
                    },
                })
        except Exception:
            pass
        time.sleep(1)  # GitHub rate limit

    # Sort by stars_per_day (velocity) — hottest rising repos first
    results.sort(key=lambda r: r.get("repo_data", {}).get("stars_per_day", 0), reverse=True)
    return results[:20]


def _smm_src_google_trends(keywords: list, **kw) -> list:
    """Fetch Google Trends daily trending via RSS."""
    results = []
    seen = set()
    geo_codes = ["US", "GB", "EE"]
    for geo in geo_codes[:2]:
        try:
            url = f"https://trends.google.com/trending/rss?geo={geo}"
            req = urllib.request.Request(url, headers={"User-Agent": "SMM-TrendScout/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
            root = _ET.fromstring(xml_data)
            for item in root.findall(".//item")[:10]:
                title = (item.findtext("title") or "").strip()
                link = item.findtext("link") or ""
                if not title or title in seen:
                    continue
                seen.add(title)
                # Check keyword relevance
                title_lower = title.lower()
                if not any(kw.lower() in title_lower for kw in keywords):
                    continue
                traffic = item.findtext("{https://trends.google.com/trending/rss}approx_traffic") or ""
                results.append({
                    "title": f"[Trending] {title}",
                    "url": link,
                    "content": f"Google Trends: {title} ({traffic})",
                    "published": (item.findtext("pubDate") or "")[:25],
                    "source_type": "google_trends",
                    "engagement": int(traffic.replace("+", "").replace(",", "")) if traffic.replace("+", "").replace(",", "").isdigit() else 0,
                    "extra": f"🔍 Google Trends {geo} {traffic}",
                })
        except Exception:
            pass
    return results


def _smm_detect_locations(keywords: list) -> tuple:
    """Split keywords into topics and locations. No hardcoded city list — uses heuristics."""
    # Common location indicators (suffixes, prepositions context)
    # Instead of listing cities, detect by: capitalized single words that aren't common tech/food terms
    topic_words = []
    location_words = []
    # Common non-location words to skip
    skip = {"ai", "ml", "devops", "saas", "b2b", "defi", "web3", "llm", "api", "open source",
            "fitness", "cooking", "food", "crypto", "blockchain", "art", "design", "gaming",
            "фитнес", "еда", "рецепт", "тренировк", "питание", "зож", "ресторан", "кафе",
            "блюд", "кухня", "меню", "дизайн", "крипто", "биткоин", "маркетинг", "стартап",
            "продукт", "бизнес", "курс", "обучен", "образован", "tutorial", "startup",
            "programming", "developer", "software", "marketing", "health", "gym", "workout"}
    for kw in keywords:
        kw_lower = kw.lower().strip()
        # If it's not a common topic word and looks like a proper noun — treat as location
        if kw_lower not in skip and not any(s in kw_lower for s in skip):
            # Heuristic: short capitalized words, or words ending in common geo suffixes
            if (len(kw) > 2 and kw[0].isupper()) or any(kw_lower.endswith(s) for s in (
                    "город", "burg", "town", "ville", "grad", "sk", "ино", "ово")):
                location_words.append(kw)
            else:
                topic_words.append(kw)
        else:
            topic_words.append(kw)
    return topic_words or keywords, location_words


def _smm_src_searxng(keywords: list, lang: str = "ru", site_filters: list = None, **kw) -> list:
    """Fetch results from SearXNG with geo-aware queries."""
    import urllib.parse as _up
    results = []
    seen = set()
    year = _dt.now().strftime("%Y")
    month = _dt.now().strftime("%Y-%m")

    topics, locations = _smm_detect_locations(keywords)
    location_str = " ".join(locations) if locations else ""

    queries = []
    # Topic queries (with location if detected)
    for keyword in topics[:4]:
        q_base = f"{keyword} {location_str}".strip() if location_str else keyword
        queries.append(f"{q_base} {month}")
        queries.append(f"{q_base} {year}")
    # Location-specific queries
    if locations:
        for loc in locations[:2]:
            for topic in topics[:3]:
                queries.append(f"{topic} {loc} {year}")
        # Geo review sites
        geo_sites = ["tripadvisor.com", "yelp.com", "google.com/maps"]
        for site in geo_sites[:2]:
            queries.append(f"site:{site} {location_str} {topics[0] if topics else ''}")
    # Site-specific queries from route
    if site_filters:
        for site in site_filters[:3]:
            for keyword in topics[:2]:
                queries.append(f"site:{site} {keyword} {location_str}".strip())
    # Localized
    if lang in ("ru", "ru+en"):
        for keyword in topics[:2]:
            q = f"{keyword} {location_str} новости {year}".strip()
            queries.append(q)

    for time_range in ("day", "week"):
        for q in queries[:12]:
            try:
                lang_param = ""
                if lang == "en":
                    lang_param = "&language=en"
                elif lang == "ru":
                    lang_param = "&language=ru"
                url = (f"http://localhost:8888/search?q={_up.quote(q)}"
                       f"&format=json&time_range={time_range}"
                       f"&engines=google,bing,duckduckgo{lang_param}")
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                for r in data.get("results", [])[:8]:
                    rurl = r.get("url", "")
                    if not rurl or rurl in seen:
                        continue
                    seen.add(rurl)
                    results.append({
                        "title": r.get("title", ""),
                        "url": rurl,
                        "content": r.get("content", "")[:400],
                        "published": r.get("publishedDate", ""),
                        "source_type": "web",
                        "engagement": 0,
                        "freshness": time_range,
                        "extra": f"SearXNG ({time_range})",
                    })
            except Exception:
                pass
        if len(results) >= 25 and time_range == "day":
            break
    return results


# ─── Niche Router ─────────────────────────────────────────────────

SMM_NICHE_ROUTES = {
    "tech": {
        "keywords": ["ai", "ml", "devops", "programming", "software", "open source", "llm",
                     "developer", "kubernetes", "docker", "linux", "python", "api",
                     "agent", "rag", "lora", "fine-tun", "comfyui", "stable diffusion"],
        "sources": ["github_trending_ai", "hackernews", "reddit", "github_trending", "rss", "searxng"],
        "subreddits": ["MachineLearning", "selfhosted", "devops", "LocalLLaMA", "opensource", "programming", "StableDiffusion"],
        "rss_feeds": ["https://hnrss.org/newest?points=50", "https://techcrunch.com/feed/"],
    },
    "crypto": {
        "keywords": ["crypto", "defi", "web3", "blockchain", "bitcoin", "ethereum", "nft",
                     "крипто", "биткоин", "блокчейн", "токен"],
        "sources": ["reddit", "rss", "searxng"],
        "subreddits": ["cryptocurrency", "defi", "ethereum", "CryptoMarkets", "Bitcoin"],
        "rss_feeds": ["https://www.coindesk.com/arc/outboundfeeds/rss/"],
    },
    "food": {
        "keywords": ["ресторан", "еда", "рецепт", "кафе", "food", "restaurant", "cooking",
                     "chef", "кулинар", "кухня", "блюд", "меню"],
        "sources": ["reddit", "rss", "searxng"],
        "subreddits": ["food", "Cooking", "FoodPorn", "AskCulinary", "MealPrepSunday"],
        "rss_feeds": [],
        "searxng_site_filters": ["tripadvisor.com", "wolt.com", "bolt.eu/food"],
    },
    "fitness": {
        "keywords": ["фитнес", "тренировк", "зож", "питание", "fitness", "workout", "health",
                     "gym", "спорт", "бег", "мышц", "диет"],
        "sources": ["reddit", "google_trends", "searxng"],
        "subreddits": ["fitness", "nutrition", "bodyweightfitness", "running", "GYM"],
        "rss_feeds": [],
    },
    "business": {
        "keywords": ["saas", "b2b", "startup", "стартап", "маркетинг", "marketing", "продукт",
                     "growth", "venture", "инвестиц", "бизнес", "product"],
        "sources": ["hackernews", "reddit", "rss", "searxng"],
        "subreddits": ["SaaS", "startups", "Entrepreneur", "marketing", "smallbusiness"],
        "rss_feeds": ["https://hnrss.org/newest?points=30&q=startup"],
    },
    "art": {
        "keywords": ["art", "design", "comfyui", "stable diffusion", "flux", "generative",
                     "дизайн", "иллюстрац", "midjourney", "рисова", "график"],
        "sources": ["reddit", "github_trending", "searxng"],
        "subreddits": ["StableDiffusion", "comfyui", "AIArt", "generative", "DigitalArt"],
        "rss_feeds": [],
    },
    "gaming": {
        "keywords": ["game", "gaming", "игр", "esport", "steam", "unity", "unreal", "геймд"],
        "sources": ["reddit", "rss", "searxng"],
        "subreddits": ["gaming", "Games", "pcgaming", "indiegaming", "gamedev"],
        "rss_feeds": [],
    },
    "education": {
        "keywords": ["образован", "курс", "обучен", "education", "course", "learn", "tutorial",
                     "универс", "школ", "студент"],
        "sources": ["reddit", "searxng", "google_trends"],
        "subreddits": ["learnprogramming", "education", "OnlineCourses"],
        "rss_feeds": [],
    },
}


def _smm_route_niche(niche: str, profile: dict) -> dict:
    """Determine best source route based on profile niche keywords."""
    niche_lower = niche.lower()
    niche_words = [w.strip().lower() for w in niche.split(",")]
    scores = {}
    for route_name, route in SMM_NICHE_ROUTES.items():
        score = 0
        for rk in route["keywords"]:
            if rk in niche_lower:
                score += 2
            for nw in niche_words:
                if rk in nw or nw in rk:
                    score += 1
        scores[route_name] = score
    best = max(scores, key=scores.get) if scores else "tech"
    if scores.get(best, 0) == 0:
        # No match — use generic fallback
        return {
            "sources": ["searxng", "reddit"],
            "subreddits": [],
            "rss_feeds": [],
            "searxng_site_filters": [],
        }
    route = SMM_NICHE_ROUTES[best].copy()
    route["subreddits"] = list(route.get("subreddits", []))  # copy list

    # Auto-detect locations from niche and add geo-subreddits dynamically
    niche_keywords = [w.strip() for w in niche.split(",") if w.strip()]
    _, locations = _smm_detect_locations(niche_keywords)
    for loc in locations:
        # Add location name as subreddit (many cities have their own: r/tallinn, r/berlin, etc.)
        loc_lower = loc.lower().replace(" ", "")
        # Transliteration for Cyrillic location names
        _translit = {"таллинн": "tallinn", "москва": "moscow", "петербург": "stpetersburg",
                     "берлин": "berlin", "лондон": "london", "париж": "paris",
                     "нью-йорк": "nyc", "токио": "tokyo", "варшава": "warsaw",
                     "киев": "kyiv", "рига": "riga", "вильнюс": "vilnius",
                     "хельсинки": "helsinki", "стокгольм": "stockholm"}
        sub_name = _translit.get(loc_lower, loc_lower)
        if sub_name not in route["subreddits"]:
            route["subreddits"].append(sub_name)
    return route


def _smm_run_trend_scan(profile: dict, model: str = "qwen3.5:27b", custom_prompt: str = ""):
    """Trend scan v2: intelligent multi-source router → LLM analysis → report."""
    profile_id = profile["id"]
    _smm_trend_scan.update({"status": "running", "profile_id": profile_id,
                            "started": time.time(), "message": "Identifying sources..."})
    try:
        niche = profile.get("niche", "")
        keywords = [k.strip() for k in niche.split(",") if k.strip()]
        tags = [h.lstrip("#") for h in profile.get("hashtags", [])[:5]]
        competitors = profile.get("competitors", [])[:3]
        lang = profile.get("language", "ru")
        today = _dt.now().strftime("%Y-%m-%d")
        year = today[:4]

        # ── Route: determine sources for this niche ──
        route = _smm_route_niche(niche, profile)
        source_plan = route.get("sources", ["searxng"])
        subreddits = route.get("subreddits", [])
        rss_feeds = route.get("rss_feeds", [])
        site_filters = route.get("searxng_site_filters", [])

        search_keywords = keywords + [t for t in tags if t not in keywords]

        # ── Collect from all sources ──
        all_results = []
        source_stats = {}

        source_fns = {
            "reddit": lambda: _smm_src_reddit(subreddits=subreddits, keywords=search_keywords),
            "hackernews": lambda: _smm_src_hackernews(keywords=search_keywords),
            "rss": lambda: _smm_src_rss(feeds=rss_feeds),
            "github_trending": lambda: _smm_src_github(keywords=search_keywords),
            "github_trending_ai": lambda: _smm_src_github_trending_ai(),
            "google_trends": lambda: _smm_src_google_trends(keywords=search_keywords),
            "searxng": lambda: _smm_src_searxng(keywords=search_keywords, lang=lang, site_filters=site_filters),
        }

        for src_name in source_plan:
            fn = source_fns.get(src_name)
            if not fn:
                continue
            _smm_trend_scan["message"] = f"Collecting: {src_name}... [{len(all_results)} found]"
            try:
                src_results = fn()
                source_stats[src_name] = len(src_results)
                all_results.extend(src_results)
            except Exception as e:
                source_stats[src_name] = f"err:{e}"

        # Deduplicate by URL across all sources
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(r)
        all_results = unique_results

        if not all_results:
            _smm_trend_scan.update({"status": "error",
                "message": "No results found. Check SearXNG and internet connection."})
            return

        # ── Pre-scoring ──
        _smm_trend_scan["message"] = f"Ranking {len(all_results)} sources..."
        for r in all_results:
            score = 0
            # Source type boost
            st = r.get("source_type", "web")
            if st == "reddit":
                score += 12
            elif st == "hackernews":
                score += 10
            elif st == "github":
                score += 6
            elif st == "rss":
                score += 8
            elif st == "google_trends":
                score += 15
            # Engagement boost (real virality signal from Reddit/HN)
            eng = r.get("engagement", 0)
            if eng > 500:
                score += 25
            elif eng > 100:
                score += 15
            elif eng > 30:
                score += 8
            elif eng > 0:
                score += 3
            # Freshness boost
            if r.get("freshness") == "day":
                score += 20
            # Keyword density in title
            title_lower = r.get("title", "").lower()
            for kw in keywords:
                if kw.lower() in title_lower:
                    score += 5
            # Penalize old content
            combined = title_lower + " " + (r.get("content") or "").lower() + " " + (r.get("published") or "")
            prev_year = str(int(year) - 1)
            if prev_year in combined or str(int(year) - 2) in combined:
                score -= 15
            if year in combined:
                score += 8
            # Language filter: hard-filter CJK for ru/en profiles
            if lang in ("ru", "en", "ru+en") and _has_cjk(r.get("title", "")):
                score -= 100  # effectively removes from top results
            # For en-only profiles, penalize non-latin URLs
            if lang == "en":
                domain = r.get("url", "").split("/")[2] if "/" in r.get("url", "") else ""
                if any(d in domain for d in ["zhihu.com", "baidu.com", "csdn.net", "bilibili.com"]):
                    score -= 100
            r["_score"] = score

        # Sort by score, take top for LLM
        all_results.sort(key=lambda r: r["_score"], reverse=True)
        top_results = all_results[:35]

        # ── Load previous report for diff ──
        prev_titles = set()
        prev_report = trends_latest(profile_id)
        if prev_report:
            prev_titles = {t.get("title", "") for t in prev_report.get("topics", [])}
        prev_context = ""
        if prev_titles:
            prev_list = "\n".join(f"- {t}" for t in list(prev_titles)[:10])
            prev_context = f"\n\nПРЕДЫДУЩИЕ ТЕМЫ (НЕ ПОВТОРЯЙ, покажи только НОВЫЕ):\n{prev_list}"

        # ── Build enriched context for LLM ──
        results_text = "\n".join(
            f"{i+1}. [{r['title']}]({r['url']})"
            f"{' [' + (r.get('published') or '')[:16] + ']' if r.get('published') else ''}"
            f" [{r['source_type'].upper()}]"
            f"{' ' + r.get('extra', '') if r.get('extra') else ''}"
            f"\n   {r['content']}"
            for i, r in enumerate(top_results)
        )

        sources_used = ", ".join(f"{k}:{v}" for k, v in source_stats.items())
        lang_name = "русском" if lang == "ru" else "английском" if lang == "en" else "русском и английском" if lang == "ru+en" else lang
        tone = profile.get("tone", "professional")
        _, detected_locations = _smm_detect_locations([k.strip() for k in niche.split(",") if k.strip()])
        geo_rule = ""
        if detected_locations:
            loc_names = ", ".join(detected_locations)
            geo_rule = f"""
8. ГЕО-ФИЛЬТР — профиль привязан к: {loc_names}. ИСКЛЮЧАЙ контент про другие города/страны. Если статья про Москву, а профиль про Таллинн — НЕ включай. Только контент релевантный для {loc_names} и окрестностей."""
        prompt = f"""Ты — профессиональный AI-аналитик трендов для SMM-агентства. Сегодня {today}.
Ниша: "{niche}". Тон бренда: "{tone}". Язык контента: {lang_name}.

Проанализируй {len(top_results)} результатов поиска и составь отчёт из 5-10 трендовых тем.

ПРАВИЛА РАНЖИРОВАНИЯ:
1. АКТУАЛЬНОСТЬ — сейчас {today}, март {year}! Статьи и темы 2025 года и старше — УСТАРЕВШИЕ. Снижай relevance на 20-30 пунктов. Приоритет контенту {year} года.
2. Свежесть — [СВЕЖЕЕ] статьи получают приоритет
3. Виральность — темы с дискуссиями (REDDIT, HACKERNEWS) имеют высокий потенциал
4. Релевантность — только темы, напрямую полезные для ниши "{niche}"
5. Уникальность — группируй похожие статьи в одну тему, не дублируй
6. Actionability — тема должна давать повод для поста в соцсетях
7. В заголовках НЕ ПИШИ год, если тема актуальна прямо сейчас{geo_rule}

ТИПЫ КОНТЕНТА (укажи в description):
- 🔥 Breaking — горячая новость, нужно реагировать быстро
- 📊 Analysis — аналитика, можно написать экспертный пост
- 💡 Tutorial — можно сделать обучающий контент
- 🤔 Opinion — провокационная тема для дискуссии
- 📢 Announcement — запуск продукта/фичи

Верни JSON массив. Каждый объект:
{{"title": "заголовок на {lang_name}", "description": "тип + описание 1-2 предложения", "relevance": 0-100, "virality": "high/medium/low", "suggested_angle": "конкретный угол для поста в тоне {tone}", "sources": [{{"title": "название", "url": "ссылка"}}]}}

Источники: {sources_used}

Результаты поиска:
{results_text}
{prev_context}
{"ДОПОЛНИТЕЛЬНЫЕ УКАЗАНИЯ ОТ ПОЛЬЗОВАТЕЛЯ: " + custom_prompt if custom_prompt else ""}

Верни ТОЛЬКО JSON массив. Без текста до или после.
/no_think"""

        payload = json.dumps({
            "model": model, "prompt": prompt, "stream": False,
            "options": {"num_predict": 12000, "temperature": 0.3}
        }).encode("utf-8")
        req = urllib.request.Request("http://localhost:11434/api/generate",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw_bytes = resp.read()

        # Parse Ollama API response (handle NDJSON — multiple JSON lines)
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        llm_response = ""
        try:
            ollama_resp = json.loads(raw_text)
            llm_response = ollama_resp.get("response", "")
        except json.JSONDecodeError:
            # Ollama sometimes returns NDJSON (one JSON object per line)
            for line in raw_text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    llm_response += obj.get("response", "")
                except json.JSONDecodeError:
                    continue
        if not llm_response:
            _smm_trend_scan.update({"status": "error", "message": "Ollama returned empty response"})
            return

        # Remove think tags
        llm_response = _re_smm.sub(r'<think>.*?</think>', '', llm_response, flags=_re_smm.DOTALL).strip()
        # Remove markdown code fences
        llm_response = _re_smm.sub(r'^```json\s*', '', llm_response)
        llm_response = _re_smm.sub(r'\s*```\s*$', '', llm_response).strip()

        # Log cleaned LLM response for debugging
        debug_log = SMM_TRENDS_DIR / f"_debug_{profile_id}_{int(time.time())}.txt"
        try:
            route_info = f"route={source_plan}\nsource_stats={json.dumps(source_stats)}\ntotal_results={len(all_results)}\ntop_results={len(top_results)}"
            debug_log.write_text(f"{route_info}\nllm_len={len(llm_response)}\n---\n{llm_response}")
        except Exception:
            pass

        topics = None
        # Try 1: Direct JSON parse
        try:
            parsed = json.loads(llm_response)
            if isinstance(parsed, list):
                topics = parsed
            elif isinstance(parsed, dict):
                for key in ("topics", "results", "trends", "data"):
                    if key in parsed and isinstance(parsed[key], list):
                        topics = parsed[key]
                        break
                if topics is None and "title" in parsed:
                    topics = [parsed]
        except json.JSONDecodeError:
            pass

        # Try 2: Extract JSON array with regex (find the LARGEST [...] block)
        if topics is None:
            all_arrays = _re_smm.findall(r'\[[\s\S]*?\](?=\s*(?:,\s*\{|\s*$|\s*\n\n))', llm_response)
            # Find array that contains "title"
            for arr_str in sorted(all_arrays, key=len, reverse=True):
                try:
                    parsed = json.loads(arr_str)
                    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict) and "title" in parsed[0]:
                        topics = parsed
                        break
                except json.JSONDecodeError:
                    continue

        # Try 3: Extract individual JSON objects and combine them
        if topics is None:
            objects = []
            for m in _re_smm.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_response):
                try:
                    obj = json.loads(m.group())
                    if isinstance(obj, dict) and "title" in obj and "relevance" in obj:
                        # Filter junk: title must be >3 chars, not placeholder
                        title = obj.get("title", "").strip()
                        if (len(title) > 3
                                and title not in ("...", "заголовок", "title", "example")
                                and obj.get("relevance", 0) > 0
                                and obj.get("description", "")):
                            objects.append(obj)
                except json.JSONDecodeError:
                    continue
            if objects:
                topics = objects

        # Try 4: Fix truncated JSON — close brackets and retry
        if topics is None and llm_response:
            # Find where JSON array starts
            arr_start = llm_response.find('[')
            if arr_start >= 0:
                json_part = llm_response[arr_start:].rstrip().rstrip(',')
                if not json_part.endswith(']'):
                    json_part += '}]' if json_part.count('{') > json_part.count('}') else ']'
                try:
                    topics = json.loads(json_part)
                except json.JSONDecodeError:
                    pass

        # Fallback
        if not topics:
            topics = [{"title": "Failed to parse LLM response", "description": llm_response[:500],
                       "relevance": 0, "virality": "low", "suggested_angle": "", "sources": []}]

        # Filter junk, deduplicate, sort
        seen_titles = set()
        clean_topics = []
        for t in topics:
            title = t.get("title", "").strip()
            if (title
                    and len(title) > 5
                    and title not in seen_titles
                    and t.get("relevance", 0) > 0
                    and t.get("description")):
                seen_titles.add(title)
                clean_topics.append(t)
        topics = clean_topics if clean_topics else topics  # keep original if all filtered
        topics.sort(key=lambda t: t.get("relevance", 0), reverse=True)

        # Enrich topics with published dates from sources
        url_dates = {r.get("url", ""): (r.get("published") or "")[:16] for r in top_results if r.get("published")}
        for t in topics:
            if not t.get("published_date"):
                for s in t.get("sources", []):
                    pub = url_dates.get(s.get("url", ""))
                    if pub:
                        t["published_date"] = pub
                        break

        # Step 3: Save report
        now = _dt.now()
        report = {
            "profile_id": profile_id,
            "timestamp": now.isoformat(timespec="seconds"),
            "topics": topics[:10],
            "query_keywords": keywords + tags,
            "search_results_count": len(all_results),
            "sources_used": source_stats,
            "scan_duration_sec": round(time.time() - _smm_trend_scan["started"]),
        }
        trends_save(profile_id, report)

        _smm_trend_scan.update({"status": "done", "message": f"Found {len(topics)} topics"})

    except Exception as e:
        _smm_trend_scan.update({"status": "error", "message": f"Error: {e}"})


@router.post("/api/smm/trends/scan")
async def smm_scan_trends(request: Request):
    data = await request.json()
    profile_id = _smm_safe_id(data.get("profile_id", ""))
    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}
    if _smm_trend_scan.get("status") == "running":
        return {"ok": False, "message": "Scan already in progress"}
    _smm_trend_scan.update({"status": "running", "message": "Starting..."})
    profile = json.loads(path.read_text())
    model = data.get("model", "qwen3.5:27b")
    custom_prompt = data.get("custom_prompt", "")
    asyncio.get_event_loop().run_in_executor(None, _smm_run_trend_scan, profile, model, custom_prompt)
    return {"ok": True, "message": "Scan started"}


@router.get("/api/smm/trends/history")
async def smm_trends_history(profile_id: str = ""):
    """List past trend scans for a profile."""
    if not profile_id:
        return {"ok": False, "message": "profile_id is required"}
    scans = trends_list(profile_id, limit=20)
    return {"ok": True, "scans": scans}


@router.get("/api/smm/trends/by-id")
async def smm_trends_by_id(id: int = 0):
    """Get a specific trend report by ID."""
    if not id:
        return {"ok": False, "message": "id is required"}
    report = trends_get_by_id(id)
    if not report:
        return {"ok": False, "message": "Report not found"}
    return {"ok": True, "report": report}


@router.get("/api/smm/trends/latest")
async def smm_get_latest_trends(profile_id: str = ""):
    if not profile_id:
        return {"ok": False, "message": "profile_id is required"}
    report = trends_latest(profile_id)
    return {
        "ok": True,
        "report": report,
        "scan_status": _smm_trend_scan.get("status", "idle"),
        "scan_message": _smm_trend_scan.get("message", ""),
    }


# ─── SMM Post Writer + Queue ─────────────────────────────────────

SMM_QUEUE_DIR = Path("smm_queue")
SMM_QUEUE_DIR.mkdir(exist_ok=True)

SMM_PLATFORM_FORMATS = {
    "telegram": {"max": 4096, "max_hashtags": 5, "desc": "Markdown, структурированный, emoji заголовки, 3-5 хэштегов, ссылки на источники"},
    "twitter": {"max": 280, "max_hashtags": 3, "desc": "Hook + ключевая мысль, 2-3 хэштега, провокация, без ссылок в тексте"},
    "linkedin": {"max": 3000, "max_hashtags": 5, "desc": "Профессиональный тон, 3-5 абзацев, экспертная позиция, call-to-action, 3-5 хэштегов"},
    "instagram": {"max": 2200, "max_hashtags": 28, "desc": "Эмоциональный storytelling, emoji-rich, 20-28 хэштегов в конце"},
    "facebook": {"max": 2000, "max_hashtags": 5, "desc": "Разговорный, вопросы к аудитории, engagement bait, 3-5 хэштегов"},
    "threads": {"max": 500, "max_hashtags": 5, "desc": "Короткое мнение, conversational, 3-5 хэштегов"},
    "discord": {"max": 2000, "max_hashtags": 0, "desc": "Casual community стиль, embed-friendly, без хэштегов"},
}


def _smm_trim_hashtags(text: str, platform: str) -> str:
    """Trim hashtags to platform limit."""
    max_tags = SMM_PLATFORM_FORMATS.get(platform, {}).get("max_hashtags", 30)
    if max_tags == 0:
        # Remove all hashtags
        return " ".join(w for w in text.split() if not w.startswith("#"))
    words = text.split()
    hashtags = [w for w in words if w.startswith("#")]
    if len(hashtags) <= max_tags:
        return text
    excess = set(hashtags[max_tags:])
    return " ".join(w for w in words if w not in excess)


def _smm_scrape_url(url: str, timeout: int = 10) -> str:
    """Scrape article text from URL. Returns cleaned text or empty string."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Extract text: remove scripts, styles, tags
        html = _re_smm.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', '', html, flags=_re_smm.DOTALL)
        text = _re_smm.sub(r'<[^>]+>', ' ', html)
        text = _re_smm.sub(r'\s+', ' ', text).strip()
        # Take meaningful middle (skip nav/header, ~first 500 chars)
        if len(text) > 1000:
            text = text[300:4000]
        return text[:3500]
    except Exception:
        return ""


def _smm_call_ollama(prompt: str, model: str, num_predict: int = 8000, temperature: float = 0.7, think: bool = True) -> str:
    """Call Ollama and return cleaned response text. Auto-retries on timeout."""
    req_data = {
        "model": model, "prompt": prompt, "stream": False,
        "options": {"num_predict": num_predict, "temperature": temperature}
    }
    if not think:
        req_data["think"] = False
    payload = json.dumps(req_data).encode("utf-8")
    # Retry up to 2 times (model may need loading into VRAM)
    raw = ""
    for attempt in range(2):
        try:
            req = urllib.request.Request("http://localhost:11434/api/generate",
                data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=360) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            break
        except Exception:
            if attempt == 0:
                time.sleep(5)  # Wait for model to load
            else:
                return ""
    # Parse Ollama response (handle NDJSON)
    llm_text = ""
    try:
        llm_text = json.loads(raw).get("response", "")
    except (json.JSONDecodeError, ValueError):
        for line in raw.strip().split("\n"):
            try:
                llm_text += json.loads(line.strip()).get("response", "")
            except Exception:
                pass
    # Clean think tags and markdown
    llm_text = _re_smm.sub(r'<think>.*?</think>', '', llm_text, flags=_re_smm.DOTALL).strip()
    llm_text = _re_smm.sub(r'^```json\s*', '', llm_text)
    llm_text = _re_smm.sub(r'\s*```\s*$', '', llm_text).strip()
    return llm_text


def _smm_parse_json_obj(text: str) -> dict | None:
    """Parse JSON object from LLM text with multiple fallback strategies."""
    # Try 1: direct
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    # Try 2: find last complete {...} from end
    brace_depth = 0
    json_end = json_start = -1
    for i in range(len(text) - 1, -1, -1):
        if text[i] == '}':
            if json_end == -1:
                json_end = i
            brace_depth += 1
        elif text[i] == '{':
            brace_depth -= 1
            if brace_depth == 0 and json_end != -1:
                json_start = i
                break
    if json_start >= 0:
        try:
            return json.loads(text[json_start:json_end + 1])
        except (json.JSONDecodeError, ValueError):
            pass
    # Try 3: fix truncated JSON
    first_brace = text.find('{')
    if first_brace >= 0:
        fragment = text[first_brace:].rstrip()
        if fragment.count('"') % 2 == 1:
            fragment += '"'
        open_b = fragment.count('{') - fragment.count('}')
        fragment += '}' * open_b
        try:
            return json.loads(fragment)
        except (json.JSONDecodeError, ValueError):
            pass
    return None


@router.post("/api/smm/generate")
async def smm_generate_posts(request: Request):
    """Generate platform-specific posts: scrape source → deep summary → write posts."""
    data = await request.json()
    profile_id = _smm_safe_id(data.get("profile_id", ""))
    topic = data.get("topic", {})
    platforms = data.get("platforms", [])
    model = data.get("model", "qwen3.5:27b")
    custom_context = data.get("custom_context", "").strip()

    if not profile_id or not topic or not platforms:
        return {"ok": False, "message": "profile_id, topic and platforms are required"}

    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}
    profile = json.loads(path.read_text())

    tone = profile.get("tone", "professional")
    lang = profile.get("language", "ru")
    lang_name = "русском" if lang == "ru" else "английском" if lang == "en" else "русском и английском" if lang == "ru+en" else lang
    hashtags = ", ".join(profile.get("hashtags", []))

    def _generate_posts():
        # ── Pass 0: Scrape source articles for deep context ──
        scraped_text = ""
        for src in topic.get("sources", [])[:3]:
            url = src.get("url", "")
            if url and "reddit.com" not in url:
                text = _smm_scrape_url(url)
                if text:
                    scraped_text += f"\n--- Источник: {src.get('title', '')} ---\n{text}\n"
        scraped_text = scraped_text[:5000]  # limit total context

        # ── Pass 1: Deep summary — extract facts, stats, quotes ──
        summary_prompt = f"""Ты — аналитик контента. Изучи материал и создай ПОДРОБНОЕ резюме для копирайтера.

ТЕМА: {topic.get('title', '')}
ОПИСАНИЕ: {topic.get('description', '')}
УГОЛ ПОДАЧИ: {topic.get('suggested_angle', '')}
{"ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ОТ ПОЛЬЗОВАТЕЛЯ: " + custom_context if custom_context else ""}

ТЕКСТ СТАТЬИ/ИСТОЧНИКА:
{scraped_text if scraped_text else "(статья недоступна — работай с описанием темы)"}

Извлеки и структурируй:
1. КЛЮЧЕВЫЕ ФАКТЫ (3-5 конкретных фактов, цифр, дат)
2. ГЛАВНЫЙ ТЕЗИС (1 предложение — в чём суть)
3. СПОРНЫЕ МОМЕНТЫ (что может вызвать дискуссию)
4. ЦИТАТЫ/ЦИФРЫ (конкретные данные для убедительности)
5. УГОЛ ДЛЯ ПОСТОВ (как подать, чтобы вызвать реакцию)

Пиши на {lang_name} языке. Будь конкретным, не общим.
/no_think"""

        summary = _smm_call_ollama(summary_prompt, model, num_predict=3000, temperature=0.3)
        if not summary:
            summary = f"Тема: {topic.get('title', '')}. {topic.get('description', '')}. Угол: {topic.get('suggested_angle', '')}"

        # ── Pass 2: Generate posts based on deep summary ──
        platform_instructions = "\n".join(
            f"- {p}: до {SMM_PLATFORM_FORMATS[p]['max']} символов. {SMM_PLATFORM_FORMATS[p]['desc']}"
            for p in platforms if p in SMM_PLATFORM_FORMATS
        )

        # Detect GitHub repo in sources — enable link mode
        github_url = ""
        for src in topic.get("sources", []):
            url = src.get("url", "")
            if "github.com/" in url and "/search" not in url:
                github_url = url
                break

        posts_prompt = f"""Ты — топовый SMM-копирайтер. Напиши ОРИГИНАЛЬНЫЕ посты для соцсетей.

АНАЛИТИКА ТЕМЫ:
{summary}

ТОН БРЕНДА: {tone}
ЯЗЫК: {lang_name}
ХЭШТЕГИ БРЕНДА: {hashtags}

ПЛАТФОРМЫ:
{platform_instructions}

КРИТИЧЕСКИ ВАЖНО:
1. Пиши как АВТОР с собственным мнением, НЕ как репост/пересказ чужой статьи
2. {"Это GitHub-проект — ОБЯЗАТЕЛЬНО включи ссылку " + github_url + " в каждый пост! Формат: краткое описание + почему это круто + ссылка + хэштеги" if github_url else "НИКАКИХ ссылок на источники — пост должен быть самодостаточным"}
3. Используй факты и цифры из аналитики, но переформулируй своими словами
4. Каждый пост УНИКАЛЬНЫЙ — разный стиль, разный фокус, разная подача
5. Пост должен выглядеть как написанный живым человеком-экспертом
6. Для Twitter — строго до 280 символов, острый hook
7. Для Instagram — эмоциональный, 20-30 хэштегов в конце
8. НЕ начинай посты с "🚀" — разнообразь emoji

Верни ТОЛЬКО JSON: {{{', '.join(f'"{p}": "текст"' for p in platforms)}}}
/no_think"""

        posts_text = _smm_call_ollama(posts_prompt, model, num_predict=16000, temperature=0.8)
        if not posts_text:
            return None
        result = _smm_parse_json_obj(posts_text)
        if not result:
            # Debug log
            try:
                (SMM_TRENDS_DIR / f"_debug_generate_{int(time.time())}.txt").write_text(
                    f"summary_len={len(summary)}\nposts_text_len={len(posts_text)}\n---\n{posts_text[:3000]}")
            except Exception:
                pass
        return result

    try:
        posts = await asyncio.to_thread(_generate_posts)
        if not posts:
            return {"ok": False, "message": "Failed to generate posts"}
        return {"ok": True, "posts": posts}
    except Exception as e:
        return {"ok": False, "message": f"Error: {e}"}


SMM_IMG_DIR = Path("smm_images")
SMM_IMG_DIR.mkdir(exist_ok=True)

# Platform image sizes (crop/resize from 1024x1024 source)
SMM_IMG_SIZES = {
    "telegram": (1280, 720),    # 16:9
    "twitter": (1200, 675),     # 16:9
    "linkedin": (1200, 627),    # ~1.91:1
    "instagram": (1080, 1080),  # 1:1
    "instagram_story": (1080, 1920),  # 9:16
    "facebook": (1200, 630),    # ~1.91:1
    "threads": (1080, 1080),    # 1:1
    "discord": (1280, 720),     # 16:9
}


@router.post("/api/smm/generate-image-prompt")
async def smm_generate_image_prompt(request: Request):
    """Use LLM to create a cinematic image generation prompt from post context."""
    data = await request.json()
    title = data.get("title", "")
    description = data.get("description", "")
    angle = data.get("angle", "")
    style = data.get("style", "tech-dark")

    style_map = {
        "tech-dark": "dark cyberpunk aesthetic, neon blue and purple glow, circuit patterns, holographic displays",
        "clean-corp": "clean minimalist corporate style, white space, subtle gradients, professional",
        "bright-social": "vibrant colorful social media style, bold gradients, energetic",
        "photorealism": "photorealistic, natural lighting, detailed textures, cinematic depth of field",
        "illustration": "digital illustration, stylized, artistic brush strokes, creative",
        "meme": "bold graphic style, high contrast, pop culture aesthetic",
        "infographic": "data visualization aesthetic, charts, clean geometric shapes",
    }
    style_desc = style_map.get(style, "modern tech aesthetic, dramatic lighting")

    prompt = f"""You are an expert AI image prompt engineer for FLUX/Stable Diffusion.

Create a vivid, cinematic image generation prompt for a social media post about:

TITLE: {title}
DESCRIPTION: {description}
ANGLE: {angle}

STYLE DIRECTION: {style_desc}

RULES:
1. Describe a SCENE, not text — the image must tell the story visually
2. Include specific visual elements: lighting, mood, composition, colors, objects
3. Make it cinematic and dramatic — like a movie still or concept art
4. Include technical quality tags: 8k, cinematic lighting, detailed, professional
5. ALWAYS end with: "No text, no letters, no words, no typography, no watermarks on the image."
6. Keep the prompt under 200 words
7. Do NOT include the article title literally — translate the CONCEPT into visual language
8. Avoid generic descriptions — be specific and atmospheric

Return ONLY the image prompt, nothing else.
/no_think"""

    try:
        result = await asyncio.to_thread(_smm_call_ollama, prompt, "qwen3.5:9b", 1000, 0.8, False)
        if result:
            # Clean up — remove quotes, newlines
            result = result.strip().strip('"').strip("'").replace("\n", " ")
            if not result.endswith("."):
                result += "."
            if "no text" not in result.lower():
                result += " No text, no letters, no words, no typography, no watermarks on the image."
            return {"ok": True, "prompt": result}
    except Exception:
        pass
    return {"ok": False, "message": "Failed to generate prompt"}


@router.post("/api/smm/generate-image")
async def smm_generate_image(request: Request):
    """Generate 1 image via ComfyUI FLUX, then resize for all platforms via ffmpeg."""
    data = await request.json()
    prompt_text = data.get("prompt", "")
    platforms = data.get("platforms", ["instagram"])
    prefix = data.get("prefix", "smm_post")

    if not prompt_text:
        return {"ok": False, "message": "Prompt is required"}

    # Always generate 1024x1024 square (best for cropping to any ratio)
    w, h = 1024, 1024

    workflow = {"prompt": {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b-fp8.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt_text, "clip": ["3", 0]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["4", 0],
            "latent_image": ["5", 0], "seed": int(time.time()) % 999999,
            "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0
        }},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["2", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }}

    def _generate():
        comfyui_started_by_us = False
        try:
            # Auto-start ComfyUI if not running
            try:
                urllib.request.urlopen("http://localhost:8188/api/system_stats", timeout=3)
            except Exception:
                # ComfyUI not running — start it
                for m in _load_modules():
                    if m.get("_file") == "comfyui.yaml":
                        _start_module(m)
                        comfyui_started_by_us = True
                        break
                # Wait for ComfyUI to be ready
                for _ in range(30):
                    time.sleep(2)
                    try:
                        urllib.request.urlopen("http://localhost:8188/api/system_stats", timeout=3)
                        break
                    except Exception:
                        pass
                else:
                    return None, "ComfyUI не запустился за 60 секунд"

            # Submit workflow
            payload = json.dumps(workflow).encode("utf-8")
            req = urllib.request.Request("http://localhost:8188/api/prompt",
                data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                prompt_id = json.loads(resp.read()).get("prompt_id", "")
            if not prompt_id:
                return None, "ComfyUI не вернул prompt_id"
            # Poll for result
            for _ in range(30):
                time.sleep(2)
                try:
                    hist_req = urllib.request.Request(f"http://localhost:8188/api/history/{prompt_id}")
                    with urllib.request.urlopen(hist_req, timeout=5) as resp:
                        hist = json.loads(resp.read())
                    if prompt_id in hist:
                        outputs = hist[prompt_id].get("outputs", {})
                        for node_out in outputs.values():
                            images = node_out.get("images", [])
                            if images:
                                filename = images[0]["filename"]
                                # Auto-stop ComfyUI if we started it
                                if comfyui_started_by_us:
                                    time.sleep(1)
                                    for m in _load_modules():
                                        if m.get("_file") == "comfyui.yaml":
                                            _stop_module(m)
                                            break
                                return filename, None
                except Exception:
                    pass
            return None, "Image generation timeout"
        except Exception as e:
            return None, str(e)
        finally:
            # Always stop ComfyUI if we started it (even on error/timeout)
            if comfyui_started_by_us:
                try:
                    for m in _load_modules():
                        if m.get("_file") == "comfyui.yaml":
                            _stop_module(m)
                            break
                except Exception:
                    pass

    filename, error = await asyncio.to_thread(_generate)
    if error:
        return {"ok": False, "message": error}

    # Resize for all requested platforms via ffmpeg
    source_path = COMFYUI_OUTPUT / filename
    if not source_path.exists():
        return {"ok": False, "message": "Source image not found"}

    ts = int(time.time())
    variants = {}
    for platform in platforms:
        size = SMM_IMG_SIZES.get(platform)
        if not size:
            continue
        tw, th = size
        out_name = f"{prefix}_{platform}_{ts}.png"
        out_path = SMM_IMG_DIR / out_name
        try:
            # ffmpeg: scale + crop to exact size from center
            subprocess.run([
                "ffmpeg", "-y", "-i", str(source_path),
                "-vf", f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}",
                "-frames:v", "1",
                str(out_path)
            ], capture_output=True, timeout=15)
            if out_path.exists():
                variants[platform] = {"filename": out_name, "url": f"/api/smm/image/{out_name}", "size": f"{tw}x{th}"}
        except Exception:
            pass

    # Also keep original
    orig_name = f"{prefix}_original_{ts}.png"
    orig_dest = SMM_IMG_DIR / orig_name
    try:
        import shutil
        shutil.copy2(source_path, orig_dest)
    except Exception:
        pass

    return {
        "ok": True,
        "original": {"filename": orig_name, "url": f"/api/smm/image/{orig_name}", "size": "1024x1024"},
        "variants": variants,
    }


@router.get("/api/smm/image/{filename}")
async def smm_get_image(filename: str):
    """Serve generated image from smm_images or ComfyUI output."""
    filename = Path(filename).name  # sanitize: strip path separators
    if ".." in filename or "/" in filename:
        return {"ok": False, "message": "Invalid filename"}
    path = SMM_IMG_DIR / filename
    if not path.exists():
        path = COMFYUI_OUTPUT / filename
    if not path.exists():
        return {"ok": False, "message": "Image not found"}
    return FileResponse(path)


@router.get("/api/smm/queue")
async def smm_list_queue(profile_id: str = ""):
    """List queue items for a profile."""
    return {"ok": True, "items": queue_list(profile_id)}


@router.post("/api/smm/queue")
async def smm_add_to_queue(request: Request):
    """Add generated posts to content queue."""
    import uuid
    data = await request.json()
    now = _dt.now().isoformat(timespec="seconds")
    item = {
        "id": uuid.uuid4().hex[:8],
        "profile_id": data.get("profile_id", ""),
        "topic_title": data.get("topic_title", ""),
        "posts": data.get("posts", {}),
        "image": data.get("image", None),
        "image_variants": data.get("image_variants", {}),
        "status": "draft",
        "scheduled_time": None,
        "publish_results": {},
        "created": now,
        "updated": now,
    }
    queue_add(item)
    return {"ok": True, "id": item["id"], "message": "Added to queue"}


@router.put("/api/smm/queue/{item_id}")
async def smm_update_queue(item_id: str, request: Request):
    """Update queue item (edit posts, change status, schedule)."""
    item_id = _smm_safe_id(item_id)
    if not queue_get(item_id):
        return {"ok": False, "message": "Item not found"}
    data = await request.json()
    queue_update(item_id, data)
    return {"ok": True, "message": "Updated"}


@router.delete("/api/smm/queue/{item_id}")
async def smm_delete_queue(item_id: str):
    """Delete queue item."""
    item_id = _smm_safe_id(item_id)
    if not queue_get(item_id):
        return {"ok": False, "message": "Item not found"}
    queue_delete(item_id)
    return {"ok": True, "message": "Deleted"}


@router.get("/api/smm/storage")
async def smm_storage_info():
    """Get SMM storage usage: images, queue, trends."""
    def _count(d):
        files = list(d.glob("*")) if d.exists() else []
        size = sum(f.stat().st_size for f in files if f.is_file())
        return len(files), round(size / 1024 / 1024, 1)

    img_count, img_mb = _count(SMM_IMG_DIR)
    q_count = queue_count()
    t_count = trends_count()
    db_size = round(Path("smm_data.db").stat().st_size / 1024 / 1024, 2) if Path("smm_data.db").exists() else 0
    return {
        "ok": True,
        "images": {"count": img_count, "size_mb": img_mb},
        "queue": {"count": q_count, "size_mb": db_size},
        "trends": {"count": t_count, "size_mb": 0},
        "total_mb": round(img_mb + db_size, 1),
    }


@router.post("/api/smm/cleanup")
async def smm_cleanup(request: Request):
    """Clean up SMM generated files."""
    data = await request.json()
    target = data.get("target", "images")  # images, trends, all
    deleted = 0
    freed_mb = 0

    dirs_to_clean = []
    if target in ("images", "all"):
        dirs_to_clean.append(SMM_IMG_DIR)
    if target in ("trends", "all"):
        dirs_to_clean.append(SMM_TRENDS_DIR)

    for d in dirs_to_clean:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.is_file():
                freed_mb += f.stat().st_size / 1024 / 1024
                f.unlink()
                deleted += 1

    return {"ok": True, "message": f"Deleted {deleted} files ({round(freed_mb, 1)} MB)"}


# ─── SMM GitHub Trending Search ───────────────────────────────────

# Category detection for repos
_GH_CATEGORIES = {
    "🤖 Agent": ["agent", "autonomous", "crew", "swarm", "orchestrat", "agentic"],
    "🖼 Image Gen": ["stable diffusion", "comfyui", "flux", "image gen", "diffusion", "sdxl"],
    "📊 RAG": ["rag", "retrieval", "vector", "embedding", "knowledge base"],
    "🔧 Tool": ["tool", "cli", "sdk", "framework", "library", "api"],
    "📚 Dataset": ["dataset", "benchmark", "eval", "leaderboard"],
    "🧠 LLM": ["llm", "language model", "transformer", "fine-tun", "lora", "inference"],
    "💬 Chat": ["chat", "assistant", "copilot", "companion"],
}


def _gh_detect_category(description: str, topics: list) -> str:
    """Auto-detect repo category from description and topics."""
    text = (description + " " + " ".join(topics)).lower()
    for cat, keywords in _GH_CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return cat
    return "📦 Other"


def _gh_scrape_trending(period: str = "daily") -> list:
    """Scrape GitHub Trending page for hot repos."""
    results = []
    try:
        spoken = "any"
        url = f"https://github.com/trending?since={period}&spoken_language_code={spoken}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Parse repo links: /owner/name pattern in trending articles
        import re as _re_gh
        for match in _re_gh.finditer(r'<h2[^>]*>\s*<a[^>]*href="(/[^/]+/[^/"]+)"', html):
            full_name = match.group(1).strip("/")
            if full_name and "/" in full_name and full_name not in [r.get("full_name") for r in results]:
                results.append({"full_name": full_name, "source": "trending_page"})
            if len(results) >= 25:
                break
    except Exception:
        pass
    return results


@router.post("/api/smm/github-search")
async def smm_github_search(request: Request):
    """Hybrid GitHub search: API + Trending page scrape."""
    data = await request.json()
    keywords_raw = data.get("keywords", "AI, LLM")
    period = data.get("period", "week")
    min_stars = data.get("min_stars", 10)
    sort_by = data.get("sort_by", "velocity")
    profile_id = data.get("profile_id", "")

    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    if not keywords:
        return {"ok": False, "message": "Enter keywords"}

    # Get already posted repos for "posted" marker
    posted_urls = set()
    if profile_id:
        for item in queue_list(profile_id):
            for src in (item.get("posts", {}).values()):
                if isinstance(src, str) and "github.com/" in src:
                    import re as _re_urls
                    for u in _re_urls.findall(r'https://github\.com/[^\s\)\"\']+', src):
                        posted_urls.add(u.rstrip("/"))

    def _search():
        import datetime as _dtmod
        days_map = {"day": 1, "week": 7, "month": 30}
        days = days_map.get(period, 7)
        since = (_dt.now() - _dtmod.timedelta(days=days)).strftime("%Y-%m-%d")
        results = []
        seen = set()

        def _add_repo(repo, source="api"):
            rurl = repo.get("html_url", "")
            stars = repo.get("stargazers_count", 0)
            if rurl in seen or stars < min_stars:
                return
            seen.add(rurl)
            forks = repo.get("forks_count", 0)
            lang = repo.get("language", "") or ""
            created = (repo.get("created_at", "") or "")[:10]
            days_old = max((_dt.now() - _dt.strptime(created, "%Y-%m-%d")).days, 1) if created else 1
            stars_per_day = round(stars / days_old)
            description = (repo.get("description", "") or "")[:300]
            topics = repo.get("topics", [])[:8]
            category = _gh_detect_category(description, topics)
            results.append({
                "full_name": repo.get("full_name", ""),
                "url": rurl,
                "description": description,
                "stars": stars,
                "forks": forks,
                "language": lang,
                "created": created,
                "stars_per_day": stars_per_day,
                "topics": topics,
                "category": category,
                "source": source,
                "posted": rurl.rstrip("/") in posted_urls,
            })

        # Source 1: GitHub Search API (keyword-based)
        for keyword in keywords[:6]:
            try:
                q = urllib.request.quote(f"{keyword} created:>{since}")
                url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=15"
                req = urllib.request.Request(url, headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "SMM-TrendScout/2.0",
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    api_data = json.loads(resp.read())
                for repo in api_data.get("items", []):
                    _add_repo(repo, "api")
            except Exception:
                pass
            time.sleep(1)

        # Source 2: GitHub Trending page (scrape + enrich via API)
        trending_period = "daily" if period == "day" else "weekly"
        trending_repos = _gh_scrape_trending(trending_period)
        kw_lower = [k.lower() for k in keywords]
        for tr in trending_repos:
            try:
                fn = tr["full_name"]
                # Get full repo info via API
                url = f"https://api.github.com/repos/{fn}"
                req = urllib.request.Request(url, headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "SMM-TrendScout/2.0",
                })
                with urllib.request.urlopen(req, timeout=5) as resp:
                    repo = json.loads(resp.read())
                # Filter: only add if related to keywords
                desc_lower = (repo.get("description", "") or "").lower()
                topics_lower = " ".join(repo.get("topics", []))
                if any(kw in desc_lower or kw in topics_lower or kw in fn.lower() for kw in kw_lower):
                    _add_repo(repo, "trending")
            except Exception:
                pass
            time.sleep(0.5)

        # Sort
        if sort_by == "velocity":
            results.sort(key=lambda r: r["stars_per_day"], reverse=True)
        elif sort_by == "stars":
            results.sort(key=lambda r: r["stars"], reverse=True)
        elif sort_by == "forks":
            results.sort(key=lambda r: r["forks"], reverse=True)

        return results[:30]

    repos = await asyncio.to_thread(_search)
    return {"ok": True, "repos": repos, "count": len(repos)}


# ─── SMM Publishing ──────────────────────────────────────────────

@router.post("/api/smm/publish")
async def smm_publish(request: Request):
    """Publish a queue item to connected platforms (Telegram, Discord)."""
    data = await request.json()
    queue_id = _smm_safe_id(data.get("queue_id", ""))
    profile_id = _smm_safe_id(data.get("profile_id", ""))
    platforms_to_publish = data.get("platforms", [])

    # Load queue item
    queue_item = queue_get(queue_id)
    if not queue_item:
        return {"ok": False, "message": "Queue item not found"}

    # Load profile for credentials
    p_path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not p_path.exists():
        return {"ok": False, "message": "Profile not found"}
    profile = json.loads(p_path.read_text())

    posts = queue_item.get("posts", {})
    image_file = queue_item.get("image")
    image_path = (SMM_IMG_DIR / image_file) if image_file else None
    image_variants = queue_item.get("image_variants", {})

    # Build image lookup: platform → file path
    def _get_platform_image(platform):
        """Get best image for platform: variant > original."""
        v = image_variants.get(platform, {})
        if v.get("filename"):
            p = SMM_IMG_DIR / v["filename"]
            if p.exists():
                return p
        if image_path and image_path.exists():
            return image_path
        return None

    results = {}

    _publish_imgur_url = [None]  # mutable container for closure

    def _publish():
        nonlocal results
        # Pre-upload images to imgur (separate URLs for Instagram and Threads to avoid Meta caching issues)
        _imgur_urls = {}
        import base64 as _b64pub
        def _upload_to_imgur(plat):
            pub_img = _get_platform_image(plat) or (image_path if image_path and image_path.exists() else None)
            if not pub_img:
                return None
            try:
                img_b64 = _b64pub.b64encode(pub_img.read_bytes()).decode()
                imgur_payload = json.dumps({"image": img_b64, "type": "base64"}).encode("utf-8")
                imgur_req = urllib.request.Request("https://api.imgur.com/3/image",
                    data=imgur_payload, headers={"Authorization": "Client-ID 546c25a59c58ad7",
                                                  "Content-Type": "application/json"})
                with urllib.request.urlopen(imgur_req, timeout=30) as resp:
                    return json.loads(resp.read()).get("data", {}).get("link", "")
            except Exception:
                return None
        for plat in ("instagram", "threads"):
            if plat in platforms_to_publish:
                url = _upload_to_imgur(plat)
                if url:
                    _imgur_urls[plat] = url
                    _publish_imgur_url[0] = url
                time.sleep(1)  # Avoid imgur rate limit

        for _plat_idx, platform in enumerate(platforms_to_publish):
            if _plat_idx > 0:
                time.sleep(2)  # Rate limit between platforms
            pconfig = profile.get("platforms", {}).get(platform, {})
            post_text = _smm_trim_hashtags(posts.get(platform, ""), platform)
            if not post_text:
                results[platform] = {"ok": False, "message": "No text for this platform"}
                continue

            try:
                if platform == "telegram":
                    bot_token = pconfig.get("bot_token", "")
                    channel = pconfig.get("channel", "")
                    if not bot_token or not channel:
                        results[platform] = {"ok": False, "message": "Bot token or channel not configured"}
                        continue
                    # Send photo+caption or just text
                    tg_img = _get_platform_image(platform)
                    if tg_img:
                        # sendPhoto with multipart — use no parse_mode to avoid Markdown errors
                        boundary = f"----SMM{int(time.time())}"
                        body = (
                            f"--{boundary}\r\n"
                            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{channel}\r\n'
                            f"--{boundary}\r\n"
                            f'Content-Disposition: form-data; name="caption"\r\n\r\n{post_text}\r\n'
                            f"--{boundary}\r\n"
                            f'Content-Disposition: form-data; name="photo"; filename="image.png"\r\n'
                            f"Content-Type: image/png\r\n\r\n"
                        ).encode("utf-8")
                        body += tg_img.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
                        req = urllib.request.Request(
                            f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                            data=body,
                            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
                        )
                    else:
                        # sendMessage — text only
                        payload = json.dumps({
                            "chat_id": channel,
                            "text": post_text,
                        }).encode("utf-8")
                        req = urllib.request.Request(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            data=payload,
                            headers={"Content-Type": "application/json"}
                        )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        tg_result = json.loads(resp.read())
                    if tg_result.get("ok"):
                        results[platform] = {"ok": True, "message": "Published to Telegram", "post_id": str(tg_result.get("result", {}).get("message_id", ""))}
                    else:
                        results[platform] = {"ok": False, "message": tg_result.get("description", "TG API error")}

                elif platform == "discord":
                    webhook_url = pconfig.get("webhook", "").replace("discordapp.com", "discord.com")
                    if not webhook_url:
                        results[platform] = {"ok": False, "message": "Webhook URL not configured"}
                        continue
                    # Upload image as multipart if available
                    dc_img = _get_platform_image(platform)
                    if dc_img:
                        boundary = f"----DC{int(time.time())}"
                        body = (
                            f"--{boundary}\r\nContent-Disposition: form-data; name=\"content\"\r\n\r\n{post_text}\r\n"
                            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"image.png\"\r\nContent-Type: image/png\r\n\r\n"
                        ).encode("utf-8") + dc_img.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
                        req = urllib.request.Request(webhook_url, data=body,
                            headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                     "User-Agent": "Mozilla/5.0 SMM-Bot/1.0"})
                    else:
                        payload = json.dumps({"content": post_text}).encode("utf-8")
                        req = urllib.request.Request(webhook_url, data=payload,
                            headers={"Content-Type": "application/json",
                                     "User-Agent": "Mozilla/5.0 SMM-Bot/1.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        pass  # Discord returns 204 No Content on success
                    results[platform] = {"ok": True, "message": "Published to Discord"}

                elif platform == "twitter":
                    import hashlib, hmac, base64, urllib.parse as _twup
                    consumer_key = pconfig.get("api_key", "")
                    consumer_secret = pconfig.get("api_secret", "")
                    access_token_tw = pconfig.get("access_token", "")
                    access_secret_tw = pconfig.get("access_secret", "")
                    if not all([consumer_key, consumer_secret, access_token_tw, access_secret_tw]):
                        results[platform] = {"ok": False, "message": "Twitter API keys not configured"}
                        continue

                    def _tw_oauth_header(method, url, extra_params=None):
                        nonce = hashlib.md5(str(time.time()).encode()).hexdigest()
                        ts = str(int(time.time()))
                        params = {
                            "oauth_consumer_key": consumer_key, "oauth_nonce": nonce,
                            "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": ts,
                            "oauth_token": access_token_tw, "oauth_version": "1.0",
                        }
                        if extra_params:
                            params.update(extra_params)
                        pstr = "&".join(f"{_twup.quote(k,'')}"+"="+f"{_twup.quote(str(v),'')}" for k,v in sorted(params.items()))
                        bstr = f"{method}&{_twup.quote(url,'')}&{_twup.quote(pstr,'')}"
                        skey = f"{_twup.quote(consumer_secret,'')}&{_twup.quote(access_secret_tw,'')}"
                        sig = base64.b64encode(hmac.new(skey.encode(), bstr.encode(), hashlib.sha1).digest()).decode()
                        params["oauth_signature"] = sig
                        # Remove extra_params from header (they go in body)
                        oauth_only = {k:v for k,v in params.items() if k.startswith("oauth_")}
                        return "OAuth " + ", ".join(f'{k}="{_twup.quote(str(v),"")}"' for k,v in sorted(oauth_only.items()))

                    # Upload image if available
                    media_id = None
                    tw_img = _get_platform_image(platform)
                    if tw_img:
                        try:
                            import base64 as _b64tw
                            img_b64 = _b64tw.b64encode(tw_img.read_bytes()).decode()
                            upload_url = "https://upload.twitter.com/1.1/media/upload.json"
                            auth_h = _tw_oauth_header("POST", upload_url)
                            # Use multipart for media upload (media_data must NOT be in OAuth signature)
                            boundary = f"----TW{int(time.time())}"
                            upload_data = (
                                f"--{boundary}\r\nContent-Disposition: form-data; name=\"media_data\"\r\n\r\n{img_b64}\r\n"
                                f"--{boundary}--\r\n"
                            ).encode("utf-8")
                            up_req = urllib.request.Request(upload_url, data=upload_data, headers={
                                "Authorization": auth_h,
                                "Content-Type": f"multipart/form-data; boundary={boundary}",
                            })
                            with urllib.request.urlopen(up_req, timeout=30) as resp:
                                media_id = json.loads(resp.read()).get("media_id_string")
                        except Exception:
                            pass

                    # Post tweet
                    tweet_url = "https://api.twitter.com/2/tweets"
                    tweet_data = {"text": post_text}
                    if media_id:
                        tweet_data["media"] = {"media_ids": [media_id]}
                    tweet_body = json.dumps(tweet_data).encode("utf-8")
                    auth_h = _tw_oauth_header("POST", tweet_url)
                    req = urllib.request.Request(tweet_url, data=tweet_body, headers={
                        "Authorization": auth_h, "Content-Type": "application/json",
                    })
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        tw_result = json.loads(resp.read())
                    if tw_result.get("data", {}).get("id"):
                        results[platform] = {"ok": True, "message": f"Published to Twitter", "post_id": str(tw_result['data']['id'])}
                    else:
                        results[platform] = {"ok": False, "message": str(tw_result)}

                elif platform == "facebook":
                    page_token = pconfig.get("page_token", "")
                    page_id = pconfig.get("page_id", "")
                    if not page_token or not page_id:
                        results[platform] = {"ok": False, "message": "Facebook Page Token not configured"}
                        continue
                    # Post with image if available
                    fb_img = _get_platform_image(platform)
                    if fb_img:
                        # Upload photo with message
                        boundary = f"----FB{int(time.time())}"
                        body = (
                            f"--{boundary}\r\nContent-Disposition: form-data; name=\"message\"\r\n\r\n{post_text}\r\n"
                            f"--{boundary}\r\nContent-Disposition: form-data; name=\"access_token\"\r\n\r\n{page_token}\r\n"
                            f"--{boundary}\r\nContent-Disposition: form-data; name=\"source\"; filename=\"image.png\"\r\nContent-Type: image/png\r\n\r\n"
                        ).encode("utf-8") + fb_img.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
                        req = urllib.request.Request(
                            f"https://graph.facebook.com/v19.0/{page_id}/photos",
                            data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
                    else:
                        payload = json.dumps({"message": post_text, "access_token": page_token}).encode("utf-8")
                        req = urllib.request.Request(
                            f"https://graph.facebook.com/v19.0/{page_id}/feed",
                            data=payload, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        fb_result = json.loads(resp.read())
                    if fb_result.get("id") or fb_result.get("post_id"):
                        results[platform] = {"ok": True, "message": "Published to Facebook", "post_id": str(fb_result.get("post_id") or fb_result.get("id", ""))}
                    else:
                        results[platform] = {"ok": False, "message": str(fb_result.get("error", fb_result))}

                elif platform == "instagram":
                    ig_token = pconfig.get("access_token", "")
                    ig_account = pconfig.get("account_id", "")
                    if not ig_token or not ig_account:
                        results[platform] = {"ok": False, "message": "Instagram token or Account ID not configured"}
                        continue
                    post_text = _smm_trim_hashtags(post_text, platform)
                    ig_img_url = _imgur_urls.get("instagram")
                    if not ig_img_url:
                        results[platform] = {"ok": False, "message": "Instagram requires an image. Generate an image first."}
                        continue
                    # Step 1: Create media container with image
                    create_payload = json.dumps({
                        "image_url": ig_img_url,
                        "caption": post_text,
                        "access_token": ig_token,
                    }).encode("utf-8")
                    try:
                        req = urllib.request.Request(
                            f"https://graph.facebook.com/v19.0/{ig_account}/media",
                            data=create_payload, headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            container = json.loads(resp.read())
                    except urllib.error.HTTPError as he:
                        err_body = he.read().decode()[:300] if hasattr(he, 'read') else str(he)
                        results[platform] = {"ok": False, "message": f"IG container: {err_body}"}
                        continue
                    container_id = container.get("id")
                    if not container_id:
                        results[platform] = {"ok": False, "message": str(container.get("error", container))}
                        continue
                    # Wait for media processing
                    time.sleep(5)
                    # Step 2: Publish
                    pub_payload = json.dumps({
                        "creation_id": container_id,
                        "access_token": ig_token,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"https://graph.facebook.com/v19.0/{ig_account}/media_publish",
                        data=pub_payload, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        ig_result = json.loads(resp.read())
                    if ig_result.get("id"):
                        results[platform] = {"ok": True, "message": "Published to Instagram", "post_id": str(ig_result.get("id", ""))}
                    else:
                        results[platform] = {"ok": False, "message": str(ig_result.get("error", ig_result))}

                elif platform == "threads":
                    th_token = pconfig.get("access_token", "")
                    th_user = pconfig.get("user_id", "")
                    if not th_token or not th_user:
                        results[platform] = {"ok": False, "message": "Threads token or User ID not configured"}
                        continue
                    th_img_url = _imgur_urls.get("threads")
                    # Step 1: Create container (IMAGE if url available, TEXT otherwise)
                    container_data = {"text": post_text, "access_token": th_token}
                    if th_img_url:
                        container_data["media_type"] = "IMAGE"
                        container_data["image_url"] = th_img_url
                    else:
                        container_data["media_type"] = "TEXT"
                    create_payload = json.dumps(container_data).encode("utf-8")
                    req = urllib.request.Request(
                        f"https://graph.threads.net/v1.0/{th_user}/threads",
                        data=create_payload, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        container = json.loads(resp.read())
                    container_id = container.get("id")
                    if not container_id:
                        results[platform] = {"ok": False, "message": str(container.get("error", container))}
                        continue
                    # Step 2: Publish
                    pub_payload = json.dumps({
                        "creation_id": container_id,
                        "access_token": th_token,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"https://graph.threads.net/v1.0/{th_user}/threads_publish",
                        data=pub_payload, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        th_result = json.loads(resp.read())
                    if th_result.get("id"):
                        results[platform] = {"ok": True, "message": "Published to Threads", "post_id": str(th_result.get("id", ""))}
                    else:
                        results[platform] = {"ok": False, "message": str(th_result.get("error", th_result))}

                elif platform == "linkedin":
                    ln_token = pconfig.get("access_token", "")
                    ln_urn = pconfig.get("person_urn", "")
                    if not ln_token or not ln_urn:
                        results[platform] = {"ok": False, "message": "LinkedIn token not configured"}
                        continue
                    ln_headers = {"Authorization": f"Bearer {ln_token}", "X-Restli-Protocol-Version": "2.0.0"}

                    # Try to upload image
                    ln_asset = None
                    ln_img = _get_platform_image(platform)
                    if ln_img:
                        # Step 1: Register upload
                        reg_payload = json.dumps({
                            "registerUploadRequest": {
                                "owner": ln_urn,
                                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                                "serviceRelationships": [{"identifier": "urn:li:userGeneratedContent",
                                    "relationshipType": "OWNER"}]
                            }
                        }).encode("utf-8")
                        reg_req = urllib.request.Request("https://api.linkedin.com/v2/assets?action=registerUpload",
                            data=reg_payload, headers={**ln_headers, "Content-Type": "application/json"})
                        with urllib.request.urlopen(reg_req, timeout=15) as resp:
                            reg_result = json.loads(resp.read())
                        upload_url = reg_result["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                        ln_asset = reg_result["value"]["asset"]
                        # Step 2: Upload binary
                        img_data = ln_img.read_bytes()
                        up_req = urllib.request.Request(upload_url, data=img_data,
                            headers={**ln_headers, "Content-Type": "image/png"}, method="PUT")
                        urllib.request.urlopen(up_req, timeout=30)

                    # Step 3: Create post
                    if ln_asset:
                        share_content = {
                            "shareCommentary": {"text": post_text},
                            "shareMediaCategory": "IMAGE",
                            "media": [{"status": "READY", "media": ln_asset}]
                        }
                    else:
                        share_content = {
                            "shareCommentary": {"text": post_text},
                            "shareMediaCategory": "NONE"
                        }
                    payload = json.dumps({
                        "author": ln_urn,
                        "lifecycleState": "PUBLISHED",
                        "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
                        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
                    }).encode("utf-8")
                    req = urllib.request.Request("https://api.linkedin.com/v2/ugcPosts",
                        data=payload, headers={**ln_headers, "Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        ln_result = json.loads(resp.read())
                    results[platform] = {"ok": True, "message": "Published to LinkedIn", "post_id": str(ln_result.get("id", ""))}

                else:
                    results[platform] = {"ok": False, "message": f"Auto-publishing for {platform} is not yet supported. Copy the text manually."}

            except Exception as e:
                results[platform] = {"ok": False, "message": str(e)}

    await asyncio.to_thread(_publish)

    # Log publish results
    log_entry = {
        "timestamp": _dt.now().isoformat(timespec="seconds"),
        "queue_id": queue_id,
        "profile_id": profile_id,
        "topic": queue_item.get("topic_title", ""),
        "image": image_file,
        "imgur_url": _publish_imgur_url[0],
        "results": results,
    }
    try:
        log_dir = SMM_TRENDS_DIR / "_publish_logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / f"publish_{queue_id}_{int(time.time())}.json").write_text(
            json.dumps(log_entry, ensure_ascii=False, indent=2))
    except Exception:
        pass

    # Update queue item status
    # Save publish results per platform
    publish_results = {p: {"ok": r.get("ok", False), "message": r.get("message", ""), "post_id": r.get("post_id", "")} for p, r in results.items()}
    all_ok = all(r.get("ok") for r in results.values() if r)
    any_ok = any(r.get("ok") for r in results.values() if r)
    new_status = "published" if all_ok and results else "partial" if any_ok else queue_item.get("status")
    queue_update(queue_id, {"publish_results": publish_results, "status": new_status})

    return {"ok": True, "results": results}


# ─── Regenerate Single Platform Post ──────────────────────────────

@router.post("/api/smm/regen-post")
async def smm_regen_post(request: Request):
    """Regenerate a single platform post using the same topic context."""
    data = await request.json()
    queue_id = _smm_safe_id(data.get("queue_id", ""))
    platform = data.get("platform", "")
    profile_id = _smm_safe_id(data.get("profile_id", ""))
    model = data.get("model", "qwen3.5:9b")

    queue_item = queue_get(queue_id)
    if not queue_item:
        return {"ok": False, "message": "Item not found"}
    p_path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not p_path.exists():
        return {"ok": False, "message": "Profile not found"}
    if platform not in SMM_PLATFORM_FORMATS:
        return {"ok": False, "message": f"Unknown platform: {platform}"}

    profile = json.loads(p_path.read_text())
    topic_title = queue_item.get("topic_title", "")
    current_text = queue_item.get("posts", {}).get(platform, "")

    tone = profile.get("tone", "professional")
    lang = profile.get("language", "ru")
    lang_name = "русском" if lang == "ru" else "английском" if lang == "en" else "русском и английском" if lang == "ru+en" else lang
    hashtags = ", ".join(profile.get("hashtags", []))
    fmt = SMM_PLATFORM_FORMATS[platform]

    def _regen():
        prompt = f"""Перепиши пост для {platform} на тему "{topic_title}".

ТЕКУЩИЙ ПОСТ (для референса — НЕ копируй, напиши НОВЫЙ вариант):
{current_text[:500]}

ПРАВИЛА:
- Платформа: {platform}, до {fmt['max']} символов. {fmt['desc']}
- Тон: {tone}. Язык: {lang_name}
- Хэштеги бренда: {hashtags}
- Пиши как живой человек-эксперт, не как бот
- Сделай ДРУГОЙ угол подачи чем в текущем посте
- НЕ включай ссылки если это не GitHub проект

Верни ТОЛЬКО текст нового поста. Без кавычек, без пояснений.
/no_think"""
        result = _smm_call_ollama(prompt, model, 4000, 0.85, False)
        if result:
            result = result.strip().strip('"').strip("'")
        return result

    try:
        new_text = await asyncio.to_thread(_regen)
        if not new_text:
            return {"ok": False, "message": "LLM returned no text"}
        # Auto-save to queue
        posts = queue_item.get("posts", {})
        posts[platform] = new_text
        queue_update(queue_id, {"posts": posts})
        return {"ok": True, "text": new_text}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ─── Batch Generation & Calendar ─────────────────────────────────

_smm_batch_status: dict = {"status": "idle"}


def _smm_run_batch(profile_id: str, days: int, model: str, platforms: list, generate_images: bool):
    """Background: scan trends → generate posts for N days → add to queue with schedule."""
    import uuid as _uuid
    _smm_batch_status.update({"status": "running", "progress": "0/" + str(days), "message": "Scanning trends..."})
    try:
        # Load profile
        p_path = SMM_PROFILES_DIR / f"{profile_id}.json"
        profile = json.loads(p_path.read_text())
        schedule = profile.get("posting_schedule", {})
        # Determine posting time — use first platform's time or default 10:00
        post_time = "10:00"
        for plat_sched in schedule.values():
            if plat_sched.get("time"):
                post_time = plat_sched["time"]
                break

        # Step 1: Get latest trends or scan new
        _smm_batch_status["message"] = "Searching for trends..."
        report = trends_latest(profile_id)
        topics = report.get("topics", []) if report else []
        if len(topics) < days:
            _smm_run_trend_scan(profile, model)
            report = trends_latest(profile_id)
            topics = report.get("topics", []) if report else []

        topics = topics[:days]
        if not topics:
            _smm_batch_status.update({"status": "error", "message": "No trends available for generation"})
            return

        # Step 2: Generate posts for each topic
        now = _dt.now()
        generated_count = 0
        for i, topic in enumerate(topics):
            day_offset = i
            sched_date = now + __import__('datetime').timedelta(days=day_offset + 1)
            sched_dt = sched_date.replace(
                hour=int(post_time.split(":")[0]),
                minute=int(post_time.split(":")[1]) if ":" in post_time else 0,
                second=0, microsecond=0
            )
            _smm_batch_status.update({
                "progress": f"{i+1}/{len(topics)}",
                "message": f"Generating {i+1}/{len(topics)}: {topic.get('title', '')[:40]}..."
            })

            # Generate posts
            tone = profile.get("tone", "professional")
            lang = profile.get("language", "ru")
            lang_name = "русском" if lang == "ru" else "английском" if lang == "en" else "русском и английском" if lang == "ru+en" else lang
            hashtags = ", ".join(profile.get("hashtags", []))
            sources_text = ""
            for s in topic.get("sources", [])[:2]:
                u = s.get("url", "")
                if u and "reddit.com" not in u:
                    scraped = _smm_scrape_url(u)
                    if scraped:
                        sources_text += scraped[:1500] + "\n"

            # Quick summary
            summary = _smm_call_ollama(
                f"Summarize for SMM: {topic.get('title','')}. {topic.get('description','')}. "
                f"Context: {sources_text[:2000]}. Language: {lang_name}. /no_think",
                model, 1500, 0.3, False
            ) or topic.get("description", "")

            platform_fmts = "\n".join(
                f"- {p}: до {SMM_PLATFORM_FORMATS[p]['max']} символов. {SMM_PLATFORM_FORMATS[p]['desc']}"
                for p in platforms if p in SMM_PLATFORM_FORMATS
            )
            github_url = ""
            for s in topic.get("sources", []):
                if "github.com/" in s.get("url", ""):
                    github_url = s["url"]
                    break

            posts_prompt = f"""Write unique social media posts. Topic: {topic.get('title','')}.
Summary: {summary[:1000]}
Tone: {tone}. Language: {lang_name}. Hashtags: {hashtags}
{"Include link: " + github_url if github_url else "No links."}
Platforms:\n{platform_fmts}
Return ONLY JSON: {{{', '.join(f'"{p}": "text"' for p in platforms)}}}
/no_think"""
            # Retry up to 3 times if LLM fails
            posts = None
            for _attempt in range(3):
                posts_text = _smm_call_ollama(posts_prompt, model, 12000, 0.8, False)
                posts = _smm_parse_json_obj(posts_text) if posts_text else None
                if posts:
                    break
                time.sleep(3)
            # Fallback: if still no valid JSON, create simple posts from summary
            if not posts:
                posts = {}
                fallback_text = f"{topic.get('title','')}\n\n{summary[:500]}\n\n{hashtags}"
                for p in platforms:
                    max_len = SMM_PLATFORM_FORMATS.get(p, {}).get("max", 2000)
                    posts[p] = fallback_text[:max_len]
            if not posts:
                continue

            # Generate image if requested
            img_filename = None
            img_variants = {}
            if generate_images:
                _smm_batch_status["message"] = f"Generating image {i+1}/{len(topics)}..."
                try:
                    # Generate image prompt via LLM
                    style_desc = "dark cyberpunk aesthetic, neon blue and purple glow, circuit patterns, holographic displays"
                    img_prompt_text = _smm_call_ollama(
                        f"Create a cinematic image prompt for: {topic.get('title','')}. "
                        f"{topic.get('description','')}. Style: {style_desc}. "
                        f"Describe a visual SCENE. Include lighting, mood, objects. "
                        f"End with: No text, no letters, no words. Under 150 words. /no_think",
                        "qwen3.5:9b", 800, 0.8, False
                    )
                    if not img_prompt_text:
                        img_prompt_text = f"Cinematic tech scene: {topic.get('title','')}. Cyberpunk, neon, dramatic lighting, 8k. No text."
                    img_prompt_text = img_prompt_text.strip().strip('"')
                    if "no text" not in img_prompt_text.lower():
                        img_prompt_text += " No text, no letters, no words on the image."

                    # Call ComfyUI via our own API
                    import urllib.request as _bur
                    img_payload = json.dumps({
                        "prompt": img_prompt_text,
                        "platforms": platforms,
                        "prefix": "smm_batch",
                    }).encode("utf-8")
                    img_req = _bur.Request("http://localhost:9000/api/smm/generate-image",
                        data=img_payload, headers={"Content-Type": "application/json"})
                    with _bur.urlopen(img_req, timeout=300) as img_resp:
                        img_result = json.loads(img_resp.read())
                    if img_result.get("ok"):
                        img_filename = img_result.get("original", {}).get("filename")
                        img_variants = img_result.get("variants", {})
                except Exception:
                    pass  # Image generation failed — post without image

            # Create queue item
            item_id = _uuid.uuid4().hex[:8]
            created = _dt.now()
            item = {
                "id": item_id,
                "profile_id": profile_id,
                "topic_title": topic.get("title", ""),
                "posts": posts,
                "image": img_filename,
                "image_variants": img_variants,
                "status": "approved",
                "scheduled_time": sched_dt.isoformat(timespec="seconds"),
                "created": created.isoformat(timespec="seconds"),
                "updated": created.isoformat(timespec="seconds"),
            }
            queue_add(item)
            generated_count += 1

        _smm_batch_status.update({"status": "done", "message": f"Done! {generated_count}/{len(topics)} posts queued"})
    except Exception as e:
        _smm_batch_status.update({"status": "error", "message": f"Error: {e}"})


@router.post("/api/smm/batch-generate")
async def smm_batch_generate(request: Request):
    """Generate posts for multiple days and add to queue with schedule."""
    data = await request.json()
    profile_id = _smm_safe_id(data.get("profile_id", ""))
    days = min(data.get("days", 7), 14)
    model = data.get("model", "qwen3.5:9b")
    platforms = data.get("platforms", [])
    generate_images = data.get("generate_images", False)

    if not profile_id or not platforms:
        return {"ok": False, "message": "profile_id and platforms are required"}
    if _smm_batch_status.get("status") == "running":
        return {"ok": False, "message": "Batch generation already in progress"}

    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}

    asyncio.get_event_loop().run_in_executor(None, _smm_run_batch, profile_id, days, model, platforms, generate_images)
    return {"ok": True, "message": f"Generation of {days} posts started"}


@router.get("/api/smm/batch-status")
async def smm_batch_status():
    return {"ok": True, **_smm_batch_status}


@router.get("/api/smm/calendar")
async def smm_calendar(profile_id: str = "", date_from: str = "", date_to: str = ""):
    """Get queue items grouped by date for calendar view."""
    profile_id = _smm_safe_id(profile_id)
    if not date_from:
        # Default: current week
        today = _dt.now()
        weekday = today.weekday()  # Monday = 0
        start = today - __import__('datetime').timedelta(days=weekday)
        date_from = start.strftime("%Y-%m-%d")
        date_to = (start + __import__('datetime').timedelta(days=6)).strftime("%Y-%m-%d")

    days = {}
    items = queue_list(profile_id)
    for item in items:
        dt_str = item.get("scheduled_time") or item.get("created", "")
        if not dt_str:
            continue
        day_key = dt_str[:10]
        if day_key < date_from or day_key > date_to:
            continue
        entry = {
            "id": item.get("id"),
            "topic_title": item.get("topic_title", "")[:50],
            "status": item.get("status", "draft"),
            "platforms": list(item.get("posts", {}).keys()),
            "scheduled_time": item.get("scheduled_time"),
            "image": item.get("image"),
        }
        days.setdefault(day_key, []).append(entry)
    return {"ok": True, "days": days, "from": date_from, "to": date_to}


# ─── SMM Event Log ───────────────────────────────────────────────

@router.get("/api/smm/events")
async def smm_events(profile_id: str = "", limit: int = 20):
    """Get recent SMM events from publish logs."""
    events = []
    log_dir = SMM_TRENDS_DIR / "_publish_logs"
    if log_dir.exists():
        for f in sorted(log_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                entry = json.loads(f.read_text())
                if profile_id and entry.get("profile_id") != profile_id:
                    continue
                # Summarize results
                results = entry.get("results", {})
                ok_count = sum(1 for r in results.values() if r.get("ok"))
                fail_count = sum(1 for r in results.values() if not r.get("ok"))
                failed_platforms = [p for p, r in results.items() if not r.get("ok")]
                events.append({
                    "timestamp": entry.get("timestamp", ""),
                    "topic": entry.get("topic", "")[:50],
                    "ok": ok_count,
                    "fail": fail_count,
                    "failed": failed_platforms,
                    "total": len(results),
                })
            except Exception:
                pass
    return {"ok": True, "events": events}


# ─── Token Health & Auto-Refresh ─────────────────────────────────

import threading as _threading


def _smm_refresh_threads_token(profile_path: Path) -> dict:
    """Refresh Threads long-lived token (valid 60 more days)."""
    profile = json.loads(profile_path.read_text())
    th = profile.get("platforms", {}).get("threads", {})
    token = th.get("access_token", "")
    if not token:
        return {"ok": False, "message": "No Threads token"}
    try:
        url = f"https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token={token}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            result = json.loads(resp.read())
        new_token = result.get("access_token", "")
        expires_in = result.get("expires_in", 5184000)
        if new_token:
            th["access_token"] = new_token
            th["token_expires_at"] = (_dt.now() + __import__('datetime').timedelta(seconds=expires_in)).isoformat()
            profile["platforms"]["threads"] = th
            profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
            return {"ok": True, "message": f"Threads token refreshed, expires in {expires_in // 86400} days"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
    return {"ok": False, "message": "Refresh failed"}


def _smm_refresh_linkedin_token(profile_path: Path) -> dict:
    """Refresh LinkedIn token using refresh_token if available."""
    profile = json.loads(profile_path.read_text())
    ln = profile.get("platforms", {}).get("linkedin", {})
    refresh_token = ln.get("refresh_token", "")
    client_id = ln.get("client_id", "")
    client_secret = ln.get("client_secret", "")
    if not refresh_token or not client_id or not client_secret:
        return {"ok": False, "message": "LinkedIn refresh_token or client credentials not configured. Re-authorization required."}
    try:
        import urllib.parse as _lup
        data = _lup.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode("utf-8")
        req = urllib.request.Request("https://www.linkedin.com/oauth/v2/accessToken",
            data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        new_token = result.get("access_token", "")
        expires_in = result.get("expires_in", 5184000)
        if new_token:
            ln["access_token"] = new_token
            ln["token_expires_at"] = (_dt.now() + __import__('datetime').timedelta(seconds=expires_in)).isoformat()
            if result.get("refresh_token"):
                ln["refresh_token"] = result["refresh_token"]
            profile["platforms"]["linkedin"] = ln
            profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
            return {"ok": True, "message": f"LinkedIn token refreshed, expires in {expires_in // 86400} days"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
    return {"ok": False, "message": "Refresh failed"}


@router.get("/api/smm/token-health")
async def smm_token_health(profile_id: str = ""):
    """Check token expiry status for all platforms."""
    profile_id = _smm_safe_id(profile_id)
    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}
    profile = json.loads(path.read_text())
    now = _dt.now()
    health = {}
    for platform, config in profile.get("platforms", {}).items():
        if not isinstance(config, dict) or not config.get("enabled"):
            continue
        expires_at = config.get("token_expires_at", "")
        if expires_at:
            try:
                exp_dt = _dt.fromisoformat(expires_at)
                days_left = (exp_dt - now).days
                if days_left < 0:
                    health[platform] = {"status": "expired", "days_left": days_left, "message": "Token expired"}
                elif days_left < 7:
                    health[platform] = {"status": "expiring", "days_left": days_left, "message": f"Expires in {days_left} days"}
                else:
                    health[platform] = {"status": "ok", "days_left": days_left, "message": f"Valid for {days_left} days"}
            except Exception:
                health[platform] = {"status": "unknown", "days_left": -1, "message": "Unable to verify"}
        else:
            # No expiry tracked — permanent or unknown
            has_token = any(config.get(k) for k in ("bot_token", "webhook", "api_key", "access_token", "page_token"))
            if has_token:
                if platform in ("threads", "linkedin"):
                    health[platform] = {"status": "unknown", "days_left": -1, "message": "Expiry not tracked"}
                else:
                    health[platform] = {"status": "permanent", "days_left": 999, "message": "Permanent"}
    return {"ok": True, "health": health}


@router.post("/api/smm/token-refresh")
async def smm_token_refresh(request: Request):
    """Manually refresh a platform token."""
    data = await request.json()
    profile_id = _smm_safe_id(data.get("profile_id", ""))
    platform = data.get("platform", "")
    path = SMM_PROFILES_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"ok": False, "message": "Profile not found"}
    if platform == "threads":
        return await asyncio.to_thread(_smm_refresh_threads_token, path)
    elif platform == "linkedin":
        return await asyncio.to_thread(_smm_refresh_linkedin_token, path)
    return {"ok": False, "message": f"Auto-refresh not supported for {platform}"}


# ─── Analytics Collector & Endpoints ─────────────────────────────

def _smm_collect_analytics():
    """Collect metrics from FB/IG/Threads/LinkedIn for recent published posts."""
    import datetime as _dtmod
    cutoff = (_dt.now() - _dtmod.timedelta(days=7)).isoformat()
    items = [i for i in queue_list() if i.get("status") in ("published", "partial")
             and (i.get("updated", "") > cutoff or i.get("created", "") > cutoff)]
    if not items:
        return

    for item in items[:20]:  # Max 20 posts per cycle
        profile_id = item.get("profile_id", "")
        p_path = SMM_PROFILES_DIR / f"{profile_id}.json"
        if not p_path.exists():
            continue
        profile = json.loads(p_path.read_text())
        pr = item.get("publish_results", {})

        for platform, result in pr.items():
            if not result.get("ok") or not result.get("post_id"):
                continue
            post_id = result["post_id"]
            pconfig = profile.get("platforms", {}).get(platform, {})

            try:
                if platform == "facebook":
                    token = pconfig.get("page_token", "")
                    if not token:
                        continue
                    url = f"https://graph.facebook.com/v19.0/{post_id}?fields=likes.summary(true),comments.summary(true),shares&access_token={token}"
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        d = json.loads(resp.read())
                    analytics_save(item["id"], profile_id, platform, post_id,
                        likes=d.get("likes", {}).get("summary", {}).get("total_count", 0),
                        comments=d.get("comments", {}).get("summary", {}).get("total_count", 0),
                        shares=d.get("shares", {}).get("count", 0))

                elif platform == "instagram":
                    token = pconfig.get("access_token", "")
                    if not token:
                        continue
                    url = f"https://graph.facebook.com/v19.0/{post_id}?fields=like_count,comments_count&access_token={token}"
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        d = json.loads(resp.read())
                    analytics_save(item["id"], profile_id, platform, post_id,
                        likes=d.get("like_count", 0),
                        comments=d.get("comments_count", 0))

                elif platform == "threads":
                    token = pconfig.get("access_token", "")
                    if not token:
                        continue
                    url = f"https://graph.threads.net/v1.0/{post_id}?fields=likes,views,replies&access_token={token}"
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        d = json.loads(resp.read())
                    analytics_save(item["id"], profile_id, platform, post_id,
                        likes=d.get("likes", 0),
                        views=d.get("views", 0),
                        comments=d.get("replies", 0))

                elif platform == "linkedin":
                    # LinkedIn: only every 6 hours (100 req/day limit)
                    if now.hour % 6 != 0:
                        continue
                    token = pconfig.get("access_token", "")
                    if not token or not post_id:
                        continue
                    url = f"https://api.linkedin.com/v2/socialActions/{post_id}?fields=likes,comments"
                    req = urllib.request.Request(url, headers={
                        "Authorization": f"Bearer {token}",
                        "X-Restli-Protocol-Version": "2.0.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        d = json.loads(resp.read())
                    analytics_save(item["id"], profile_id, platform, post_id,
                        likes=d.get("likes", {}).get("_total", 0),
                        comments=d.get("comments", {}).get("_total", 0))
            except Exception:
                pass
            time.sleep(1)  # Rate limit between API calls


@router.get("/api/smm/analytics")
async def smm_analytics(profile_id: str = ""):
    """Get analytics summary for a profile."""
    if not profile_id:
        return {"ok": False, "message": "profile_id is required"}
    profile_id = _smm_safe_id(profile_id)
    summary = analytics_summary(profile_id)
    return {"ok": True, **summary}


@router.get("/api/smm/analytics/post/{queue_id}")
async def smm_analytics_post(queue_id: str):
    """Get analytics for a specific post."""
    queue_id = _smm_safe_id(queue_id)
    metrics = analytics_get_latest(queue_id)
    return {"ok": True, "metrics": metrics}


# ─── Queue Scheduler ─────────────────────────────────────────────

def _smm_publish_queue_item(item: dict, item_path=None):
    """Publish a single queue item to all connected platforms."""
    try:
        profile_id = item.get("profile_id", "")
        p_path = SMM_PROFILES_DIR / f"{profile_id}.json"
        if not p_path.exists():
            return
        profile = json.loads(p_path.read_text())
        posts = item.get("posts", {})
        image_file = item.get("image")
        image_variants = item.get("image_variants", {})
        image_path = (SMM_IMG_DIR / image_file) if image_file else None

        def _get_img(plat):
            v = image_variants.get(plat, {})
            if v.get("filename"):
                p = SMM_IMG_DIR / v["filename"]
                if p.exists():
                    return p
            if image_path and image_path.exists():
                return image_path
            return None

        # Determine platforms to publish
        platforms = []
        for plat, cfg in profile.get("platforms", {}).items():
            if not cfg.get("enabled") or plat not in posts:
                continue
            has_creds = any(cfg.get(k) for k in ("bot_token", "webhook", "api_key", "access_token", "page_token"))
            if has_creds:
                platforms.append(plat)

        if not platforms:
            return

        # Use the existing publish API internally
        import urllib.request as _ur
        payload = json.dumps({
            "queue_id": item["id"],
            "profile_id": profile_id,
            "platforms": platforms,
        }).encode("utf-8")
        req = _ur.Request("http://localhost:9000/api/smm/publish",
            data=payload, headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=120) as resp:
            pass  # publish endpoint handles everything
    except Exception:
        pass


def _smm_scheduler_loop():
    """Background thread: auto-publish approved queue items at scheduled time + auto-refresh tokens."""
    time.sleep(10)  # Wait for server to fully start
    while True:
        try:
            now = _dt.now()
            # 1. Check scheduled queue items (from SQLite)
            for item in queue_get_scheduled():
                try:
                    _smm_publish_queue_item(item, None)
                except Exception:
                    pass

            # 2. Collect analytics (every hour around minute 30)
            if 28 <= now.minute <= 32:
                try:
                    _smm_collect_analytics()
                except Exception:
                    pass

            # 3. Auto-refresh tokens (check every loop, refresh if < 7 days left)
            for pf in SMM_PROFILES_DIR.glob("*.json"):
                try:
                    profile = json.loads(pf.read_text())
                    for platform, refresh_fn in [("threads", _smm_refresh_threads_token), ("linkedin", _smm_refresh_linkedin_token)]:
                        cfg = profile.get("platforms", {}).get(platform, {})
                        expires_at = cfg.get("token_expires_at", "")
                        if expires_at:
                            try:
                                exp_dt = _dt.fromisoformat(expires_at)
                                if (exp_dt - now).days < 7:
                                    refresh_fn(pf)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

        # 3. Auto-cleanup old data (check every hour — use minute == 0)
        if 0 <= now.minute <= 2:
            try:
                import datetime as _dtmod
                cutoff_images = now - _dtmod.timedelta(days=30)
                cutoff_debug = now - _dtmod.timedelta(days=7)
                cutoff_published = now - _dtmod.timedelta(days=14)
                # Clean old images
                for f in SMM_IMG_DIR.glob("*"):
                    if f.is_file() and _dt.fromtimestamp(f.stat().st_mtime) < cutoff_images:
                        f.unlink()
                # Clean old debug/trend files
                for f in SMM_TRENDS_DIR.rglob("*"):
                    if f.is_file() and f.name.startswith("_debug") and _dt.fromtimestamp(f.stat().st_mtime) < cutoff_debug:
                        f.unlink()
                # Clean published queue items older than 14 days
                queue_cleanup_old(14)
                # Clean old analytics data
                from smm.db import analytics_cleanup_old
                analytics_cleanup_old(30)
            except Exception:
                pass

        time.sleep(60)


# Start scheduler on import
_smm_scheduler = _threading.Thread(target=_smm_scheduler_loop, daemon=True, name="smm-scheduler")
_smm_scheduler.start()



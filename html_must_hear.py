#!/usr/bin/env python3
"""
1001 Albums Must Hear — HTML Generator
Scrapes MusicBrainz series, crosses with last.fm scrobbles DB,
generates per-user HTML grids + index.html
"""

import subprocess, json, re, time, argparse, sqlite3, urllib.parse
from html import unescape
from pathlib import Path
from datetime import datetime

# Optional clients — imported lazily so the script works without them
def _try_import(mod):
    try:
        import importlib
        return importlib.import_module(mod)
    except ImportError:
        return None

# ── CONFIG ────────────────────────────────────────────────────────────────────
DEFAULT_SERIES = "https://musicbrainz.org/series/4bc2a338-e1d8-4546-8a61-640da8aaf888"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
CAA = "https://coverartarchive.org/release-group"

# ── SCRAPER ───────────────────────────────────────────────────────────────────

GEN_INDEX = "https://1001albumsgenerator.com/albums"

def curl_get(url: str) -> str:
    r = subprocess.run(
        ["curl", "-s", "-L", "-A", UA, "--max-time", "30", url],
        capture_output=True, text=True
    )
    return r.stdout if r.returncode == 0 else ""

def extract_series_id(url: str) -> str:
    m = re.search(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", url)
    if not m: raise ValueError(f"No MBID in: {url}")
    return m.group(1)

def get_total_pages(html: str) -> int:
    pages = re.findall(r'[?&]page=(\d+)', html)
    return max((int(p) for p in pages), default=1)

def parse_page(html: str) -> list[dict]:
    items = []
    for row in re.findall(r'<tr class="(?:odd|even)">(.*?)</tr>', html, re.DOTALL):
        num_m   = re.search(r'<td class="number-column">(\d+)</td>', row)
        year_m  = re.search(r'<td class="c">(\d{4})</td>', row)
        title_m = re.search(r'href="/release-group/([a-f0-9-]{36})"[^>]*><bdi>(.*?)</bdi>', row)
        artist_m= re.search(r'<td><bdi>(.*?)</bdi></td>', row, re.DOTALL)
        if not (num_m and title_m): continue
        artist = ""
        if artist_m:
            artist = unescape(re.sub(r'<[^>]+>', '', artist_m.group(1))).strip()
            artist = re.sub(r'\s+', ' ', artist)
        items.append({
            "number": int(num_m.group(1)),
            "year":   int(year_m.group(1)) if year_m else None,
            "title":  unescape(re.sub(r'<[^>]+>', '', title_m.group(2))).strip(),
            "artist": artist,
            "mbid":   title_m.group(1),
        })
    return items

def fetch_page_with_retry(url: str, retries: int = 3, delay: float = 3.0) -> str:
    for attempt in range(retries):
        html = curl_get(url)
        rows = re.findall(r'<tr class="(?:odd|even)">', html)
        if rows:
            return html
        if attempt < retries - 1:
            wait = delay * (attempt + 1)
            print(f"    ⚠ Vacío, reintentando en {wait:.0f}s...")
            time.sleep(wait)
    return html  # devolver aunque esté vacío

def fetch_series(series_url: str, cache_file: Path) -> list[dict]:
    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        nums = {a["number"] for a in data}
        missing = sorted(set(range(1, 1002)) - nums)
        if not missing:
            print(f"📦 Caché completo ({len(data)} álbumes): {cache_file}")
            return data
        print(f"📦 Caché incompleto: {len(data)} álbumes, faltan {len(missing)} (p.ej {missing[:5]})")
        print("🔄 Re-scrapeando páginas faltantes...")

    sid  = extract_series_id(series_url)
    base = f"https://musicbrainz.org/series/{sid}"

    # Primera página para obtener total
    print("📡 Página 1...")
    html = fetch_page_with_retry(f"{base}?page=1")
    if not html: raise RuntimeError("No se pudo obtener la primera página")
    total = get_total_pages(html)
    print(f"📚 {total} páginas detectadas")

    all_items = parse_page(html)
    print(f"  → {len(all_items)} álbumes")

    for page in range(2, total + 1):
        print(f"📡 Página {page}/{total}...")
        time.sleep(2)  # delay conservador para evitar rate limit
        html = fetch_page_with_retry(f"{base}?page={page}")
        items = parse_page(html)
        print(f"  → {len(items)} álbumes")
        all_items.extend(items)

    all_items.sort(key=lambda x: x["number"])

    # Verificar completitud
    nums = {a["number"] for a in all_items}
    missing = sorted(set(range(1, 1002)) - nums)
    if missing:
        print(f"⚠ Aún faltan {len(missing)} álbumes: {missing[:10]}...")
    else:
        print(f"✅ Lista completa!")

    cache_file.write_text(json.dumps(all_items, ensure_ascii=False, indent=2))
    print(f"✅ {len(all_items)} álbumes scrapeados → {cache_file}")
    return all_items

def fetch_descriptions_1001(cache_file: Path) -> dict:
    """Scrape 1001albumsgenerator.com for Spotify IDs + descriptions.
    Returns dict keyed by _norm(artist)+'|||'+_norm(title)."""
    desc_cache = cache_file.parent / "descriptions_1001_cache.json"
    if desc_cache.exists():
        print(f"  📦 1001gen caché: {desc_cache}")
        return json.loads(desc_cache.read_text())

    print("  🌐 Scrapeando 1001albumsgenerator.com/albums...")
    html = curl_get("https://1001albumsgenerator.com/albums")
    if not html:
        print("  ⚠ No se pudo obtener la página")
        return {}

    rows = re.findall(
        r'href="/albums/([A-Za-z0-9]{22})"[^>]*>\s*([^<]+)</a>.*?'
        r'href="/artists/[^"]*"[^>]*>\s*([^<]+)</a>',
        html, re.DOTALL
    )
    data = {}
    for spotify_id, title, artist in rows:
        key = _norm(artist.strip()) + "|||" + _norm(title.strip())
        data[key] = {"spotify_id": spotify_id, "title": title.strip(),
                     "artist": artist.strip(), "desc": ""}

    print(f"  ✅ {len(data)} álbumes con Spotify ID")

    items = list(data.items())
    for i, (key, info) in enumerate(items):
        if i % 50 == 0:
            print(f"  📄 Desc {i}/{len(items)}...")
        dhtml = curl_get(f"https://1001albumsgenerator.com/albums/{info['spotify_id']}")
        m = re.search(r'<(?:p|div)[^>]*class="[^"]*(?:description|about)[^"]*"[^>]*>(.*?)</(?:p|div)>',
                      dhtml, re.DOTALL | re.IGNORECASE)
        if m:
            info["desc"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()[:800]
        else:
            for p in re.findall(r'<p[^>]*>((?:[^<]|<(?!/?p))*)</p>', dhtml, re.DOTALL):
                clean = re.sub(r'<[^>]+>', '', p).strip()
                if len(clean) > 120:
                    info["desc"] = clean[:800]
                    break
        time.sleep(0.3)

    desc_cache.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"  💾 {desc_cache}")
    return data


def fetch_album_info_spotify(albums: list, cache_file: Path,
                              client_id: str, client_secret: str) -> dict:
    """Fetch Spotify IDs + album descriptions via spotipy.
    Returns dict keyed by _norm(artist)+'|||'+_norm(title)."""
    sp_cache = cache_file.parent / "descriptions_spotify_cache.json"
    if sp_cache.exists():
        cached = json.loads(sp_cache.read_text())
        # Only skip if all albums are already there
        missing = [a for a in albums
                   if (_norm(a["artist"]) + "|||" + _norm(a["title"])) not in cached]
        if not missing:
            print(f"  📦 Spotify caché completo: {sp_cache}")
            return cached
        print(f"  📦 Spotify caché parcial: {len(cached)} entradas, {len(missing)} nuevas")
    else:
        cached = {}
        missing = albums

    spotipy = _try_import("spotipy")
    if not spotipy:
        print("  ⚠ spotipy no disponible. Instala con: pip install spotipy --break-system-packages")
        return cached

    from spotipy.oauth2 import SpotifyClientCredentials
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=client_id, client_secret=client_secret))

    print(f"  🎵 Buscando {len(missing)} álbumes en Spotify...")
    for i, album in enumerate(missing):
        if i % 20 == 0:
            print(f"    {i}/{len(missing)}...")
        key = _norm(album["artist"]) + "|||" + _norm(album["title"])
        try:
            q = f"album:{album['title']} artist:{album['artist']}"
            results = sp.search(q=q, type="album", limit=1)
            items = results.get("albums", {}).get("items", [])
            if items:
                item = items[0]
                cached[key] = {
                    "spotify_id": item["id"],
                    "title":      item["name"],
                    "artist":     ", ".join(a["name"] for a in item["artists"]),
                    "desc":       "",   # Spotify API doesn't have album descriptions
                    "spotify_url": item["external_urls"].get("spotify", ""),
                }
            else:
                cached[key] = {"spotify_id": "", "title": album["title"],
                                "artist": album["artist"], "desc": "", "spotify_url": ""}
        except Exception as e:
            print(f"    ⚠ {album['artist']} – {album['title']}: {e}")
            cached[key] = {"spotify_id": "", "title": album["title"],
                           "artist": album["artist"], "desc": "", "spotify_url": ""}
        time.sleep(0.1)

    sp_cache.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    print(f"  💾 {sp_cache}")
    return cached


def fetch_album_info_lastfm(albums: list, cache_file: Path,
                             api_key: str, api_secret: str) -> dict:
    """Fetch album wiki/bio via pylast (Last.fm).
    Returns dict keyed by _norm(artist)+'|||'+_norm(title).
    Merges with existing data (keeps spotify_id if already present)."""
    lfm_cache = cache_file.parent / "descriptions_lastfm_cache.json"
    if lfm_cache.exists():
        cached = json.loads(lfm_cache.read_text())
        missing = [a for a in albums
                   if (_norm(a["artist"]) + "|||" + _norm(a["title"])) not in cached]
        if not missing:
            print(f"  📦 Last.fm caché completo: {lfm_cache}")
            return cached
        print(f"  📦 Last.fm caché parcial: {len(cached)}, {len(missing)} nuevos")
    else:
        cached = {}
        missing = albums

    pylast = _try_import("pylast")
    if not pylast:
        print("  ⚠ pylast no disponible. Instala con: pip install pylast --break-system-packages")
        return cached

    network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
    print(f"  🎙 Obteniendo info Last.fm de {len(missing)} álbumes...")

    for i, album in enumerate(missing):
        if i % 50 == 0:
            print(f"    {i}/{len(missing)}...")
        key = _norm(album["artist"]) + "|||" + _norm(album["title"])
        entry = cached.get(key, {"spotify_id": "", "title": album["title"],
                                  "artist": album["artist"], "desc": ""})
        try:
            lfm_album = network.get_album(album["artist"], album["title"])
            wiki = lfm_album.get_wiki_summary() or ""
            # strip Last.fm "Read more" anchor
            wiki = re.sub(r'<a href="[^"]*last\.fm[^"]*"[^>]*>[^<]*</a>', '', wiki)
            wiki = re.sub(r'<[^>]+>', '', wiki).strip()
            entry["desc"] = wiki[:800] if wiki else entry.get("desc", "")
        except Exception:
            # Try artist bio as fallback
            try:
                artist = network.get_artist(album["artist"])
                bio = artist.get_bio_summary() or ""
                bio = re.sub(r'<a href="[^"]*last\.fm[^"]*"[^>]*>[^<]*</a>', '', bio)
                bio = re.sub(r'<[^>]+>', '', bio).strip()
                entry["desc"] = bio[:800] if bio else entry.get("desc", "")
            except Exception:
                pass
        cached[key] = entry
        time.sleep(0.25)

    lfm_cache.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    print(f"  💾 {lfm_cache}")
    return cached


def fetch_album_info(albums: list, cache_file: Path, args) -> dict:
    """Dispatcher: choose info source based on CLI args.
    Priority: --1001-albums > --spotify-* > --lastfm-*
    Multiple sources are merged (1001gen wins for desc if available)."""
    desc_db = {}

    use_1001  = getattr(args, "gen_1001", False)
    sp_id     = getattr(args, "spotify_client_id",     None)
    sp_secret = getattr(args, "spotify_client_secret", None)
    lfm_key   = getattr(args, "lastfm_api_key",        None)
    lfm_secret= getattr(args, "lastfm_api_secret",     None)

    if not any([use_1001, sp_id, lfm_key]):
        print("ℹ️  Sin fuente de descripciones (usa --1001-albums, --spotify-client-id/secret o --lastfm-api-key/secret)")
        return {}

    # Layer sources from lowest to highest priority
    if lfm_key and lfm_secret:
        print("\n📡 Fuente: Last.fm")
        lfm_data = fetch_album_info_lastfm(albums, cache_file, lfm_key, lfm_secret)
        desc_db.update(lfm_data)

    if sp_id and sp_secret:
        print("\n📡 Fuente: Spotify")
        sp_data = fetch_album_info_spotify(albums, cache_file, sp_id, sp_secret)
        # Merge: keep existing desc if spotify has none
        for k, v in sp_data.items():
            if k in desc_db:
                desc_db[k]["spotify_id"]  = v.get("spotify_id", "")
                desc_db[k]["spotify_url"] = v.get("spotify_url", "")
                if v.get("desc"):
                    desc_db[k]["desc"] = v["desc"]
            else:
                desc_db[k] = v

    if use_1001:
        print("\n📡 Fuente: 1001albumsgenerator.com")
        data_1001 = fetch_descriptions_1001(cache_file)
        # 1001gen wins: overwrite desc + spotify_id
        for k, v in data_1001.items():
            if k in desc_db:
                desc_db[k]["spotify_id"] = v.get("spotify_id", desc_db[k].get("spotify_id",""))
                if v.get("desc"):
                    desc_db[k]["desc"] = v["desc"]
            else:
                desc_db[k] = v

    found = sum(1 for v in desc_db.values() if v.get("desc"))
    print(f"\n  📖 {found}/{len(desc_db)} álbumes con descripción")
    return desc_db


# ── DATABASE ──────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())

def get_users(db_path: str) -> list[str]:
    with sqlite3.connect(db_path) as c:
        rows = c.execute("SELECT DISTINCT user FROM scrobbles ORDER BY user").fetchall()
    return [r[0] for r in rows]

def get_user_albums(db_path: str, user: str) -> set[tuple]:
    """Returns set of (norm_artist, norm_album) heard by user."""
    with sqlite3.connect(db_path) as c:
        rows = c.execute(
            "SELECT artist, album FROM scrobbles WHERE user=? AND album IS NOT NULL AND album != ''",
            (user,)
        ).fetchall()
    return {(_norm(r[0]), _norm(r[1])) for r in rows}

def check_heard(user_albums: set, album: dict) -> bool:
    """Match by normalized (title, artist).
    Title: canonical title must be contained in the scrobble title OR vice-versa
           (handles remasters, editions, bonus discs, e.g.
            'boston' matches 'boston2000remaster', 'bostondeluxeedition', etc.)
    Artist: fuzzy substring match in either direction.
    """
    a_n = _norm(album["artist"])
    t_n = _norm(album["title"])
    if not t_n:
        return False
    for ua, ut in user_albums:
        if not ut:
            continue
        # Title match: exact, canonical-in-scrobble, or scrobble-in-canonical (min 80% length)
        title_match = (
            t_n == ut or
            t_n in ut or
            (ut in t_n and len(ut) >= len(t_n) * 0.8)
        )
        if not title_match:
            continue
        # Artist match: substring in either direction
        if not a_n or a_n in ua or ua in a_n:
            return True
    return False

# ── HTML GENERATION ───────────────────────────────────────────────────────────

COVER_PLACEHOLDER = "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20width=%22250%22%20height=%22250%22%20viewBox=%220%200%20250%20250%22%3E%3Crect%20width=%22250%22%20height=%22250%22%20fill=%22%23111%22/%3E%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%2260%22%20fill=%22none%22%20stroke=%22%23333%22%20stroke-width=%222%22/%3E%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%228%22%20fill=%22%23333%22/%3E%3C/svg%3E"

def album_to_json(album: dict, heard: bool, desc_db: dict = None) -> dict:
    key = _norm(album.get("artist","")) + "|||" + _norm(album.get("title",""))
    info = (desc_db or {}).get(key, {})
    return {
        "n":          album["number"],
        "title":      album["title"],
        "artist":     album["artist"],
        "year":       album["year"],
        "mbid":       album["mbid"],
        "heard":      heard,
        "cover":      f"{CAA}/{album['mbid']}/front-250",
        "spotify_id": info.get("spotify_id", ""),
        "spotify_url":info.get("spotify_url", ""),
        "desc":       info.get("desc", ""),
    }

def render_user_html(user: str, albums_data: list[dict], series_name: str) -> str:
    heard_count   = sum(1 for a in albums_data if a["heard"])
    pending_count = len(albums_data) - heard_count
    pct           = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0
    data_json     = json.dumps(albums_data, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{user} — {series_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:       #0a0a0a;
    --surface:  #111111;
    --border:   #1e1e1e;
    --accent:   #e8ff47;
    --heard:    #e8ff47;
    --pending:  #ff4747;
    --text:     #e0e0e0;
    --muted:    #555;
    --gap:      6px;
    --panel:    400px;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
  }}

  /* ── HEADER ── */
  header {{
    position: sticky; top: 0; z-index: 100;
    background: rgba(10,10,10,.95);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 14px 28px;
    display: flex; align-items: center; gap: 24px; flex-wrap: wrap;
  }}
  .header-title {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2rem;
    letter-spacing: .08em;
    color: var(--accent);
    text-decoration: none;
    white-space: nowrap;
  }}
  .header-sub {{
    font-family: 'DM Mono', monospace;
    font-size: .72rem;
    color: var(--muted);
    line-height: 1.5;
  }}
  .header-sub strong {{ color: var(--text); }}

  /* ── PROGRESS BAR ── */
  .progress-wrap {{ flex: 1; min-width: 160px; }}
  .progress-bar {{
    height: 4px; background: var(--border);
    border-radius: 2px; overflow: hidden;
  }}
  .progress-fill {{
    height: 100%; background: var(--accent);
    border-radius: 2px; transition: width .6s ease;
    width: {pct}%;
  }}
  .progress-label {{
    font-family: 'DM Mono', monospace;
    font-size: .65rem; color: var(--muted); margin-top: 4px;
  }}
  .progress-label span {{ color: var(--accent); font-weight: 500; }}

  /* ── CONTROLS ── */
  .controls {{ display: flex; align-items: center; gap: 10px; margin-left: auto; }}
  .filter-btn {{
    font-family: 'DM Mono', monospace; font-size: .72rem;
    letter-spacing: .1em; text-transform: uppercase;
    padding: 6px 14px; border-radius: 3px;
    border: 1px solid var(--border); background: transparent;
    color: var(--muted); cursor: pointer; transition: all .15s;
  }}
  .filter-btn:hover {{ border-color: var(--muted); color: var(--text); }}
  .filter-btn.active {{ border-color: var(--accent); color: var(--accent); background: rgba(232,255,71,.06); }}
  .search-box {{
    font-family: 'DM Mono', monospace; font-size: .72rem;
    padding: 6px 12px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 3px;
    color: var(--text); width: 200px; outline: none;
    transition: border-color .15s;
  }}
  .search-box:focus {{ border-color: var(--accent); }}
  .search-box::placeholder {{ color: var(--muted); }}

  /* ── GRID SLIDER ── */
  .grid-sizer {{ display: flex; align-items: center; gap: 8px; padding: 0 2px; }}
  .grid-sizer label {{
    font-family: 'DM Mono', monospace; font-size: .65rem;
    color: var(--muted); white-space: nowrap; min-width: 28px; text-align: right;
  }}
  #grid-slider {{
    -webkit-appearance: none; appearance: none;
    width: 90px; height: 3px; background: var(--border);
    border-radius: 2px; outline: none; cursor: pointer;
  }}
  #grid-slider::-webkit-slider-thumb {{
    -webkit-appearance: none; appearance: none;
    width: 12px; height: 12px; border-radius: 50%;
    background: var(--accent); cursor: pointer; transition: transform .1s;
  }}
  #grid-slider::-webkit-slider-thumb:hover {{ transform: scale(1.3); }}
  #grid-slider::-moz-range-thumb {{
    width: 12px; height: 12px; border-radius: 50%;
    background: var(--accent); border: none; cursor: pointer;
  }}

  /* ── GRID ── */
  main {{ padding: 20px 28px 60px; transition: margin-right .35s ease; }}
  main.panel-open {{ margin-right: var(--panel); }}
  .count-bar {{
    font-family: 'DM Mono', monospace; font-size: .7rem;
    color: var(--muted); margin-bottom: 14px; display: flex; gap: 16px;
  }}
  .count-bar b {{ color: var(--text); }}
  #grid {{
    display: grid;
    grid-template-columns: repeat(15, 1fr);
    gap: var(--gap);
  }}

  /* ── CARD ── */
  .card {{
    position: relative; aspect-ratio: 1; border-radius: 3px;
    overflow: hidden; cursor: pointer;
    transition: transform .18s, z-index 0s .18s;
  }}
  .card:hover {{ transform: scale(1.06); z-index: 10; transition: transform .18s, z-index 0s; }}
  .card.hidden {{ display: none; }}
  .card.active-card {{ outline: 2px solid var(--accent); outline-offset: 2px; z-index: 11; }}
  .card img {{
    width: 100%; height: 100%; object-fit: cover;
    display: block; background: var(--surface);
  }}
  .card::before {{
    content: ''; position: absolute; top: 5px; right: 5px;
    width: 8px; height: 8px; border-radius: 50%; z-index: 3;
  }}
  .card.heard::before  {{ background: var(--heard); box-shadow: 0 0 6px var(--heard); }}
  .card.pending::before {{ background: var(--pending); box-shadow: 0 0 6px var(--pending); }}
  .card-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(0deg, rgba(0,0,0,.88) 0%, rgba(0,0,0,0) 55%);
    opacity: 0; transition: opacity .2s;
    display: flex; flex-direction: column; justify-content: flex-end;
    padding: 8px; z-index: 2;
  }}
  .card:hover .card-overlay {{ opacity: 1; }}
  .card-num {{ font-family: 'Bebas Neue', sans-serif; font-size: .9rem; color: var(--accent); line-height: 1; }}
  .card-title {{ font-size: .62rem; font-weight: 500; color: #fff; line-height: 1.3; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
  .card-artist {{ font-size: .58rem; color: var(--muted); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  /* ── DETAIL PANEL ── */
  #panel {{
    position: fixed; top: 0; right: 0; bottom: 0;
    width: var(--panel);
    background: #0d0d0d;
    border-left: 1px solid var(--border);
    transform: translateX(100%);
    transition: transform .35s cubic-bezier(.4,0,.2,1);
    z-index: 200;
    display: flex; flex-direction: column;
    overflow: hidden;
  }}
  #panel.open {{ transform: translateX(0); }}

  .panel-close {{
    position: absolute; top: 14px; right: 14px;
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--surface); border: 1px solid var(--border);
    color: var(--muted); font-size: 1rem; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all .15s; z-index: 10;
  }}
  .panel-close:hover {{ background: var(--border); color: var(--text); }}

  .panel-cover {{
    width: 100%; aspect-ratio: 1; flex-shrink: 0;
    position: relative; background: var(--surface);
    max-height: 200px; overflow: hidden;
  }}
  .panel-cover img {{
    width: 100%; height: 100%; object-fit: cover;
    display: block;
  }}
  .panel-cover-status {{
    position: absolute; bottom: 10px; left: 10px;
    font-family: 'DM Mono', monospace; font-size: .65rem;
    letter-spacing: .12em; text-transform: uppercase;
    padding: 3px 8px; border-radius: 2px;
  }}
  .panel-cover-status.heard  {{ background: var(--heard); color: #000; }}
  .panel-cover-status.pending {{ background: var(--pending); color: #fff; }}

  .panel-body {{
    flex: 1; overflow-y: auto; padding: 20px;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .panel-body::-webkit-scrollbar {{ width: 4px; }}
  .panel-body::-webkit-scrollbar-track {{ background: transparent; }}
  .panel-body::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}

  .panel-num {{
    font-family: 'DM Mono', monospace; font-size: .65rem;
    color: var(--accent); letter-spacing: .15em; margin-bottom: 6px;
  }}
  .panel-title {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.6rem; letter-spacing: .04em;
    color: var(--text); line-height: 1.05; margin-bottom: 4px;
  }}
  .panel-artist {{
    font-size: .85rem; color: var(--muted); margin-bottom: 2px;
  }}
  .panel-year {{
    font-family: 'DM Mono', monospace; font-size: .7rem;
    color: var(--muted); margin-bottom: 16px;
  }}

  .panel-divider {{
    height: 1px; background: var(--border); margin: 16px 0;
  }}

  /* Info / bio */
  .panel-section-label {{
    font-family: 'DM Mono', monospace; font-size: .6rem;
    letter-spacing: .18em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 8px;
  }}
  .panel-bio {{
    font-size: .78rem; color: #aaa; line-height: 1.65;
    max-height: 160px; overflow-y: auto;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .panel-bio::-webkit-scrollbar {{ width: 3px; }}
  .panel-bio::-webkit-scrollbar-thumb {{ background: var(--border); }}
  .panel-bio-loading {{
    font-family: 'DM Mono', monospace; font-size: .72rem;
    color: var(--muted); font-style: italic;
  }}

  /* Links row */
  .panel-links {{
    display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px;
  }}
  .panel-link {{
    font-family: 'DM Mono', monospace; font-size: .65rem;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 5px 12px; border-radius: 3px;
    border: 1px solid var(--border); color: var(--muted);
    text-decoration: none; transition: all .15s; cursor: pointer;
    background: transparent;
  }}
  .panel-link:hover {{ border-color: var(--accent); color: var(--accent); }}
  .panel-link.spotify {{ border-color: #1DB954; color: #1DB954; }}
  .panel-link.spotify:hover {{ background: rgba(29,185,84,.08); }}

  /* YouTube embed */
  .panel-yt-wrap {{
    margin-top: 16px; border-radius: 4px; overflow: hidden;
    background: var(--surface); border: 1px solid var(--border);
    position: relative;
  }}
  .panel-yt-wrap iframe {{
    display: block; width: 100%; height: 160px; border: none;
  }}
  .panel-yt-placeholder {{
    height: 80px; display: flex; align-items: center; justify-content: center;
    font-family: 'DM Mono', monospace; font-size: .7rem; color: var(--muted);
    cursor: pointer; transition: background .15s;
  }}
  .panel-yt-placeholder:hover {{ background: var(--border); }}

  /* ── OVERLAY BACKDROP ── */
  #backdrop {{
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,.4); z-index: 190;
  }}
  #backdrop.show {{ display: block; }}

  /* ── MISC ── */
  .back-link {{ font-family: 'DM Mono', monospace; font-size: .7rem; color: var(--muted); text-decoration: none; margin-right: 8px; }}
  .back-link:hover {{ color: var(--text); }}
  #empty {{ display: none; text-align: center; padding: 80px 0; font-family: 'DM Mono', monospace; color: var(--muted); font-size: .8rem; }}

  @media (max-width: 600px) {{
    header {{ padding: 10px 16px; }}
    main {{ padding: 14px 16px 40px; }}
    :root {{ --panel: 100vw; }}
    main.panel-open {{ margin-right: 0; }}
  }}
</style>
</head>
<body>

<header>
  <a href="index.html" class="back-link">← all users</a>
  <a href="#" class="header-title">{user}</a>
  <div class="header-sub">
    <strong>{series_name}</strong><br>
    {heard_count} heard &middot; {pending_count} pending
  </div>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill" id="prog-fill"></div></div>
    <div class="progress-label"><span id="prog-pct">{pct}%</span> complete</div>
  </div>
  <div class="controls">
    <button class="filter-btn active" id="btn-all" onclick="setFilter('all')">All</button>
    <button class="filter-btn" id="btn-heard" onclick="setFilter('heard')">Heard</button>
    <button class="filter-btn" id="btn-pending" onclick="setFilter('pending')">Pending</button>
    <input class="search-box" id="search" placeholder="Search…" oninput="applyFilters()">
    <div class="grid-sizer">
      <label id="grid-label">5×5</label>
      <input type="range" id="grid-slider" min="3" max="15" value="5" step="1" oninput="setGridSize(this.value)">
    </div>
  </div>
</header>

<main id="main">
  <div class="count-bar">
    <span>Showing <b id="vis-count">{len(albums_data)}</b> of {len(albums_data)} albums</span>
    <span><b id="vis-heard">0</b> heard &middot; <b id="vis-pending">0</b> pending</span>
  </div>
  <div id="grid"></div>
  <div id="empty">No albums match your filters.</div>
</main>

<!-- Detail panel -->
<div id="backdrop" onclick="closePanel()"></div>
<aside id="panel">
  <button class="panel-close" onclick="closePanel()">✕</button>
  <div class="panel-cover">
    <img id="p-cover" src="" alt="">
    <span class="panel-cover-status" id="p-status"></span>
  </div>
  <div class="panel-body">
    <div class="panel-num" id="p-num"></div>
    <div class="panel-title" id="p-title"></div>
    <div class="panel-artist" id="p-artist"></div>
    <div class="panel-year" id="p-year"></div>

    <div class="panel-links" id="p-links"></div>

    <div class="panel-divider"></div>
    <div class="panel-section-label">About</div>
    <div class="panel-bio" id="p-bio"><span class="panel-bio-loading">Loading info…</span></div>

    <div class="panel-divider"></div>
    <div class="panel-section-label">Listen on YouTube</div>
    <div class="panel-yt-wrap" id="p-yt">
      <div class="panel-yt-placeholder" id="p-yt-placeholder" onclick="loadYT()">▶ Click to load video</div>
    </div>
  </div>
</aside>

<script>
const ALBUMS = {data_json};
let filter = 'all';
let gridCols = 5;
let currentAlbum = null;
let ytLoaded = false;

// ── LAZY LOADING via IntersectionObserver ──
const imgObserver = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      const img = e.target;
      if (img.dataset.src) {{
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
        imgObserver.unobserve(img);
      }}
    }}
  }});
}}, {{ rootMargin: '200px' }});

// ── GRID SIZE ──
function setGridSize(val) {{
  gridCols = parseInt(val);
  document.getElementById('grid-label').textContent = val + '\xd7' + val;
  document.getElementById('grid').style.gridTemplateColumns = `repeat(${{gridCols}}, 1fr)`;
  try {{ localStorage.setItem('grid-cols', val); }} catch(e) {{}}
}}

// ── GRID BUILD ──
function buildGrid() {{
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  ALBUMS.forEach(a => {{
    const card = document.createElement('div');
    card.className = `card ${{a.heard ? 'heard' : 'pending'}}`;
    card.dataset.title  = a.title.toLowerCase();
    card.dataset.artist = a.artist.toLowerCase();
    card.dataset.heard  = a.heard ? '1' : '0';
    card.dataset.num    = a.n;
    card.innerHTML = `
      <img data-src="${{a.cover}}" src="{COVER_PLACEHOLDER}" alt="${{a.n}}"
           onerror="this.src='{COVER_PLACEHOLDER}'">
      <div class="card-overlay">
        <div class="card-num">#${{a.n}}</div>
        <div class="card-title">${{a.title}}</div>
        <div class="card-artist">${{a.artist}} \xb7 ${{a.year ?? ''}}</div>
      </div>`;
    card.addEventListener('click', () => openPanel(a, card));
    grid.appendChild(card);
  }});
  // Observe all lazy images
  document.querySelectorAll('img[data-src]').forEach(img => imgObserver.observe(img));
  applyFilters();
}}

// ── PANEL ──
function openPanel(a, cardEl) {{
  // Mark active card
  document.querySelectorAll('.card.active-card').forEach(c => c.classList.remove('active-card'));
  cardEl.classList.add('active-card');
  currentAlbum = a;
  ytLoaded = false;

  // Fill static info
  const cover = `https://coverartarchive.org/release-group/${{a.mbid}}/front-500`;
  document.getElementById('p-cover').src = cover;
  document.getElementById('p-cover').onerror = function() {{
    this.src = '{COVER_PLACEHOLDER}';
  }};
  const statusEl = document.getElementById('p-status');
  statusEl.textContent = a.heard ? 'Heard' : 'Pending';
  statusEl.className   = 'panel-cover-status ' + (a.heard ? 'heard' : 'pending');
  document.getElementById('p-num').textContent    = `#${{a.n}}`;
  document.getElementById('p-title').textContent  = a.title;
  document.getElementById('p-artist').textContent = a.artist;
  document.getElementById('p-year').textContent   = a.year ?? '';

  // Links
  const mbUrl      = `https://musicbrainz.org/release-group/${{a.mbid}}`;
  const spotifyUrl = a.spotify_url
    || (a.spotify_id ? `https://open.spotify.com/album/${{a.spotify_id}}`
    : `https://open.spotify.com/search/${{encodeURIComponent(a.artist + ' ' + a.title)}}`);
  const gen1001Url = a.spotify_id
    ? `https://1001albumsgenerator.com/albums/${{a.spotify_id}}`
    : '';
  document.getElementById('p-links').innerHTML = `
    <a class="panel-link" href="${{mbUrl}}" target="_blank">MusicBrainz</a>
    <a class="panel-link spotify" href="${{spotifyUrl}}" target="_blank">Spotify</a>
    ${{gen1001Url ? `<a class="panel-link" href="${{gen1001Url}}" target="_blank" style="border-color:#7b61ff;color:#7b61ff">1001gen</a>` : ''}}
  `;

  // Reset YT
  document.getElementById('p-yt').innerHTML = `
    <div class="panel-yt-placeholder" id="p-yt-placeholder" onclick="loadYT()">▶ Click to load video</div>`;

  // Bio: reset + fetch
  const bioEl = document.getElementById('p-bio');
  if (a.desc && a.desc.length > 40) {{
    bioEl.textContent = a.desc;
  }} else {{
    bioEl.innerHTML = '<span class="panel-bio-loading">Loading info…</span>';
    fetchBio(a.artist, a.title, a.mbid);
  }}

  // Show panel
  document.getElementById('panel').classList.add('open');
  document.getElementById('backdrop').classList.add('show');
  document.getElementById('main').classList.add('panel-open');
}}

function closePanel() {{
  document.getElementById('panel').classList.remove('open');
  document.getElementById('backdrop').classList.remove('show');
  document.getElementById('main').classList.remove('panel-open');
  document.querySelectorAll('.card.active-card').forEach(c => c.classList.remove('active-card'));
  // Stop YT if playing
  const iframe = document.querySelector('#p-yt iframe');
  if (iframe) {{ const s = iframe.src; iframe.src = ''; iframe.src = s; }}
  currentAlbum = null;
}}

// ── YOUTUBE ──
function loadYT() {{
  if (!currentAlbum || ytLoaded) return;
  ytLoaded = true;
  const a = currentAlbum;
  const q = encodeURIComponent(a.artist + ' ' + a.title + ' full album');
  const ytSearch = `https://www.youtube.com/results?search_query=${{q}}`;
  // Use noembed / oEmbed to avoid CORS — just open search if embed fails
  // We'll do a lightweight fetch via a CORS proxy to get the first video ID
  const proxy = `https://api.allorigins.win/get?url=${{encodeURIComponent(ytSearch)}}`;
  document.getElementById('p-yt').innerHTML = '<div class="panel-yt-placeholder">Searching…</div>';
  fetch(proxy)
    .then(r => r.json())
    .then(d => {{
      const ids = [...d.contents.matchAll(/"videoId"[ ]*:[ ]*"([A-Za-z0-9_-]{11})"/g)].map(m => m[1]);
      const unique = [...new Set(ids)];
      if (unique.length === 0) throw new Error('no results');
      const vid = unique[0];
      document.getElementById('p-yt').innerHTML = `
        <iframe src="https://www.youtube.com/embed/${{vid}}?autoplay=1"
          allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
    }})
    .catch(() => {{
      document.getElementById('p-yt').innerHTML = `
        <div class="panel-yt-placeholder">
          <a href="${{ytSearch}}" target="_blank" style="color:var(--accent);text-decoration:none">
            ▶ Open YouTube search
          </a>
        </div>`;
    }});
}}

// ── BIO from Last.fm API (no key needed for basic info) + Wikipedia fallback ──
async function fetchBio(artist, title, mbid) {{
  const bioEl = document.getElementById('p-bio');
  try {{
    // Try Last.fm album.getinfo (no API key needed for public data via noembed proxy)
    const lfmUrl = `https://ws.audioscrobbler.com/2.0/?method=album.getinfo&artist=${{encodeURIComponent(artist)}}&album=${{encodeURIComponent(title)}}&format=json&api_key=c9b21e5a749e4f279b6cdce9d5b3a7b3`;
    const res = await fetch(lfmUrl);
    const d   = await res.json();
    const wiki = d?.album?.wiki?.summary || d?.album?.wiki?.content || '';
    if (wiki && wiki.length > 40) {{
      // Strip Last.fm "read more" link at end
      const clean = (wiki || bio).replace(/<[^>]+>/g, '').replace(/[ ]{2,}/g, ' ').trim();
      bioEl.textContent = clean.length > 800 ? clean.slice(0, 800) + '…' : clean;
      return;
    }}
    // Fallback: Last.fm artist.getinfo
    const lfmArtist = `https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist=${{encodeURIComponent(artist)}}&format=json&api_key=c9b21e5a749e4f279b6cdce9d5b3a7b3`;
    const res2 = await fetch(lfmArtist);
    const d2   = await res2.json();
    const bio  = d2?.artist?.bio?.summary || '';
    if (bio && bio.length > 40) {{
      const clean = (wiki || bio).replace(/<[^>]+>/g, '').replace(/[ ]{2,}/g, ' ').trim();
      bioEl.textContent = clean.length > 800 ? clean.slice(0, 800) + '…' : clean;
      return;
    }}
    // Fallback: Wikipedia summary via REST API
    const wikiUrl = `https://en.wikipedia.org/api/rest_v1/page/summary/${{encodeURIComponent(artist + ' (album)')}}`;
    const res3 = await fetch(wikiUrl);
    const d3   = await res3.json();
    const extract = d3?.extract || '';
    if (extract && extract.length > 40) {{
      bioEl.textContent = extract.length > 800 ? extract.slice(0, 800) + '…' : extract;
      return;
    }}
    bioEl.textContent = 'No info available.';
  }} catch(e) {{
    bioEl.textContent = 'Could not load info.';
  }}
}}

// ── FILTERS ──
function setFilter(f) {{
  filter = f;
  ['all','heard','pending'].forEach(x => {{
    const btn = document.getElementById('btn-' + x);
    btn.classList.toggle('active', x === f);
    if (x === 'pending') {{
      btn.style.borderColor = f === 'pending' ? 'var(--pending)' : '';
      btn.style.color       = f === 'pending' ? 'var(--pending)' : '';
      btn.style.background  = f === 'pending' ? 'rgba(255,71,71,.06)' : '';
    }}
  }});
  applyFilters();
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase().trim();
  let vis = 0, visH = 0, visP = 0;
  document.querySelectorAll('.card').forEach(c => {{
    const matchFilter = filter === 'all'
      || (filter === 'heard'   && c.dataset.heard === '1')
      || (filter === 'pending' && c.dataset.heard === '0');
    const matchSearch = !q || c.dataset.title.includes(q) || c.dataset.artist.includes(q);
    const show = matchFilter && matchSearch;
    c.classList.toggle('hidden', !show);
    if (show) {{ vis++; if (c.dataset.heard === '1') visH++; else visP++; }}
  }});
  document.getElementById('vis-count').textContent   = vis;
  document.getElementById('vis-heard').textContent   = visH;
  document.getElementById('vis-pending').textContent = visP;
  document.getElementById('empty').style.display     = vis === 0 ? 'block' : 'none';
  if (filter !== 'all' || q) {{
    const pct = vis > 0 ? Math.round(visH / vis * 100) : 0;
    document.getElementById('prog-fill').style.width = pct + '%';
    document.getElementById('prog-pct').textContent  = pct + '%';
  }} else {{
    document.getElementById('prog-fill').style.width = '{pct}%';
    document.getElementById('prog-pct').textContent  = '{pct}%';
  }}
}}

// Keyboard: Escape closes panel
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closePanel(); }});

// Restore grid size
try {{
  const saved = localStorage.getItem('grid-cols');
  if (saved) {{
    const v = Math.min(15, Math.max(3, parseInt(saved)));
    document.getElementById('grid-slider').value = v;
    setGridSize(v);
  }} else {{
    // Default 5x5
    setGridSize(5);
  }}
}} catch(e) {{
  setGridSize(5);
}}
buildGrid();

// Open panel on first visible album by default
setTimeout(() => {{
  const firstCard = document.querySelector('.card:not(.hidden)');
  if (firstCard) {{
    const idx = parseInt(firstCard.dataset.num) - 1;
    const album = ALBUMS.find(a => a.n === parseInt(firstCard.dataset.num));
    if (album) openPanel(album, firstCard);
  }}
}}, 100);
</script>
</body>
</html>
"""


def render_collection_index_html(users_data: list[dict], series_name: str, generated: str) -> str:
    cards_html = ""
    for u in users_data:
        pct  = u["pct"]
        bar_w = pct
        cards_html += f"""
        <a class="user-card" href="{u['file']}">
          <div class="uc-name">{u['user']}</div>
          <div class="uc-stats">
            <span class="uc-heard">{u['heard']}</span>
            <span class="uc-sep">/</span>
            <span class="uc-total">{u['total']}</span>
            <span class="uc-label">albums heard</span>
          </div>
          <div class="uc-bar-wrap">
            <div class="uc-bar" style="width:{bar_w}%"></div>
          </div>
          <div class="uc-pct">{pct}%</div>
        </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{series_name} — Must Hear</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:     #0a0a0a;
    --surface:#111;
    --border: #1e1e1e;
    --accent: #e8ff47;
    --muted:  #555;
    --text:   #e0e0e0;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
  }}

  /* noise grain overlay */
  body::before {{
    content: '';
    position: fixed; inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
    pointer-events: none; z-index: 0; opacity: .4;
  }}

  header {{
    position: relative; z-index: 1;
    padding: 60px 60px 40px;
    border-bottom: 1px solid var(--border);
  }}
  .site-label {{
    font-family: 'DM Mono', monospace;
    font-size: .7rem;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
  }}
  h1 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(2.4rem, 6vw, 5rem);
    letter-spacing: .04em;
    line-height: .95;
    color: var(--accent);
  }}
  .header-meta {{
    font-family: 'DM Mono', monospace;
    font-size: .72rem;
    color: var(--muted);
    margin-top: 16px;
  }}
  .header-meta span {{ color: var(--text); }}

  main {{
    position: relative; z-index: 1;
    padding: 48px 60px 80px;
  }}
  .section-label {{
    font-family: 'DM Mono', monospace;
    font-size: .65rem;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 24px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }}

  .users-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
  }}

  .user-card {{
    display: block;
    text-decoration: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 22px 20px 18px;
    transition: border-color .15s, transform .15s;
    position: relative;
    overflow: hidden;
  }}
  .user-card::after {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
    transform: scaleX(0);
    transform-origin: left;
    transition: transform .25s ease;
  }}
  .user-card:hover {{ border-color: #333; transform: translateY(-2px); }}
  .user-card:hover::after {{ transform: scaleX(1); }}

  .uc-name {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.5rem;
    letter-spacing: .06em;
    color: var(--text);
    margin-bottom: 10px;
  }}
  .uc-stats {{
    display: flex; align-items: baseline; gap: 4px;
    margin-bottom: 12px;
  }}
  .uc-heard  {{ font-family: 'DM Mono', monospace; font-size: 1.4rem; color: var(--accent); font-weight: 500; }}
  .uc-sep    {{ font-family: 'DM Mono', monospace; font-size: .8rem; color: var(--muted); }}
  .uc-total  {{ font-family: 'DM Mono', monospace; font-size: .8rem; color: var(--muted); }}
  .uc-label  {{ font-size: .7rem; color: var(--muted); margin-left: 4px; }}

  .uc-bar-wrap {{
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 6px;
  }}
  .uc-bar {{
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width .8s ease;
  }}
  .uc-pct {{
    font-family: 'DM Mono', monospace;
    font-size: .65rem;
    color: var(--muted);
    text-align: right;
  }}

  footer {{
    position: relative; z-index: 1;
    padding: 24px 60px;
    border-top: 1px solid var(--border);
    font-family: 'DM Mono', monospace;
    font-size: .65rem;
    color: var(--muted);
  }}

  @media (max-width: 700px) {{
    header, main, footer {{ padding-left: 20px; padding-right: 20px; }}
    header {{ padding-top: 36px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="site-label"><a href="../index.html" style="color:var(--muted);text-decoration:none;letter-spacing:.2em">← All Collections</a></div>
  <h1>{series_name}</h1>
  <div class="header-meta">
    <span>{len(users_data)}</span> users &nbsp;·&nbsp;
    <span>1,001</span> albums &nbsp;·&nbsp;
    Generated {generated}
  </div>
</header>
<main>
  <div class="section-label">Users — click to explore</div>
  <div class="users-grid">
    {cards_html}
  </div>
</main>
<footer>Data from MusicBrainz &amp; Last.fm · Cover art from Cover Art Archive</footer>
</body>
</html>
"""


def render_root_index_html(collections: list[dict], generated: str) -> str:
    """Top-level index listing all music collections."""
    cards_html = ""
    for c in collections:
        avg_pct  = c["avg_pct"]
        users_n  = c["users"]
        total    = c["total"]
        cards_html += f"""
      <a class="col-card" href="{c['slug']}/index.html">
        <div class="col-name">{c['name']}</div>
        <div class="col-meta">{users_n} users &middot; {total} albums</div>
        <div class="col-bar-wrap">
          <div class="col-bar" style="width:{avg_pct:.1f}%"></div>
        </div>
        <div class="col-pct">{avg_pct:.1f}% avg completion</div>
      </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Must Hear — Collections</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0a0a0a; --surface:#111; --border:#1e1e1e;
    --accent:#e8ff47; --muted:#555; --text:#e0e0e0;
  }}
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:var(--bg); color:var(--text);
    font-family:'DM Sans',sans-serif; min-height:100vh;
  }}
  body::before {{
    content:''; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.4;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
  }}
  header {{
    position:relative; z-index:1;
    padding:60px 60px 40px;
    border-bottom:1px solid var(--border);
  }}
  .site-label {{
    font-family:'DM Mono',monospace; font-size:.7rem;
    letter-spacing:.2em; text-transform:uppercase;
    color:var(--muted); margin-bottom:12px;
  }}
  h1 {{
    font-family:'Bebas Neue',sans-serif;
    font-size:clamp(2.4rem,6vw,5rem);
    letter-spacing:.04em; line-height:.95; color:var(--accent);
  }}
  .header-meta {{
    font-family:'DM Mono',monospace; font-size:.72rem;
    color:var(--muted); margin-top:16px;
  }}
  main {{ position:relative; z-index:1; padding:40px 60px 80px; }}
  .section-label {{
    font-family:'DM Mono',monospace; font-size:.65rem;
    letter-spacing:.2em; text-transform:uppercase;
    color:var(--muted); margin-bottom:20px;
  }}
  .collections-grid {{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
    gap:16px;
  }}
  .col-card {{
    display:block; text-decoration:none;
    background:var(--surface); border:1px solid var(--border);
    border-radius:6px; padding:26px 22px 20px;
    transition:border-color .15s, transform .15s;
    position:relative; overflow:hidden;
  }}
  .col-card::after {{
    content:''; position:absolute; top:0; left:0; right:0;
    height:3px; background:var(--accent);
    transform:scaleX(0); transform-origin:left;
    transition:transform .25s ease;
  }}
  .col-card:hover {{ border-color:#333; transform:translateY(-2px); }}
  .col-card:hover::after {{ transform:scaleX(1); }}
  .col-name {{
    font-family:'Bebas Neue',sans-serif;
    font-size:1.6rem; letter-spacing:.05em;
    color:var(--text); margin-bottom:8px; line-height:1.1;
  }}
  .col-meta {{
    font-family:'DM Mono',monospace; font-size:.65rem;
    color:var(--muted); margin-bottom:14px;
  }}
  .col-bar-wrap {{
    height:3px; background:var(--border);
    border-radius:2px; overflow:hidden; margin-bottom:6px;
  }}
  .col-bar {{
    height:100%; background:var(--accent);
    border-radius:2px; transition:width .8s ease;
  }}
  .col-pct {{
    font-family:'DM Mono',monospace; font-size:.62rem; color:var(--muted);
  }}
  footer {{
    position:relative; z-index:1;
    padding:24px 60px; border-top:1px solid var(--border);
    font-family:'DM Mono',monospace; font-size:.65rem; color:var(--muted);
  }}
  @media (max-width:700px) {{
    header,main,footer {{ padding-left:20px; padding-right:20px; }}
    header {{ padding-top:36px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="site-label">Must Hear Tracker</div>
  <h1>Collections</h1>
  <div class="header-meta">
    {len(collections)} collection{'s' if len(collections) != 1 else ''} &nbsp;&middot;&nbsp;
    Generated {generated}
  </div>
</header>
<main>
  <div class="section-label">All Lists</div>
  <div class="collections-grid">{cards_html}
  </div>
</main>
<footer>Generated {generated}</footer>
</body>
</html>
"""


def update_root_index(root_dir: Path, collection_name: str, slug: str,
                      users_index: list[dict], generated: str) -> None:
    """Read existing root index data (if any), upsert this collection, rewrite."""
    meta_file = root_dir / ".collections_meta.json"

    # Load existing metadata
    if meta_file.exists():
        collections = json.loads(meta_file.read_text())
    else:
        collections = []

    # Compute avg completion for this collection
    avg_pct = (sum(u["pct"] for u in users_index) / len(users_index)) if users_index else 0
    total   = users_index[0]["total"] if users_index else 0

    entry = {
        "slug":    slug,
        "name":    collection_name,
        "users":   len(users_index),
        "total":   total,
        "avg_pct": round(avg_pct, 1),
        "updated": generated,
    }

    # Upsert by slug
    existing = [c for c in collections if c["slug"] != slug]
    existing.append(entry)
    existing.sort(key=lambda c: c["name"])

    meta_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    # Render and write root index
    html = render_root_index_html(existing, generated)
    (root_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"📋 root index → {root_dir / 'index.html'} ({len(existing)} collections)")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="1001 Albums Must Hear — HTML Generator")
    parser.add_argument("--db",     required=True, help="Ruta a lastfm_cache.db")
    parser.add_argument("--out",    default="docs/must_hear",
                        help="Directorio raíz de salida (contiene el index superior)")
    parser.add_argument("--series", default=DEFAULT_SERIES, help="URL de la serie en MusicBrainz")
    parser.add_argument("--name",   default="1001 Albums You Must Hear Before You Die",
                        help="Nombre de la serie (usado en títulos y en el index superior)")
    parser.add_argument("--slug",   default=None,
                        help="Nombre del subdirectorio para esta colección (auto si no se indica)")
    parser.add_argument("--cache",  default=None,
                        help="Caché local del scraping (por defecto <out>/<slug>/series_cache.json)")
    parser.add_argument("--users",       nargs="*", help="Usuarios específicos (por defecto todos)")
    parser.add_argument("--from-cache",  action="store_true",
                        help="No re-scrapear series, solo actualizar HTMLs con la DB")
    # ── Fuentes de descripción (opcionales, combinables) ──
    parser.add_argument("--1001-albums", dest="gen_1001", action="store_true",
                        help="Scrape 1001albumsgenerator.com para descripciones y Spotify IDs")
    parser.add_argument("--spotify-client-id",     dest="spotify_client_id",     default=None,
                        help="Spotify API client_id (para buscar álbumes)")
    parser.add_argument("--spotify-client-secret", dest="spotify_client_secret", default=None,
                        help="Spotify API client_secret")
    parser.add_argument("--lastfm-api-key",        dest="lastfm_api_key",        default=None,
                        help="Last.fm API key (para wiki de álbumes/artistas)")
    parser.add_argument("--lastfm-api-secret",     dest="lastfm_api_secret",     default=None,
                        help="Last.fm API secret")
    args = parser.parse_args()

    root_dir = Path(args.out)
    root_dir.mkdir(parents=True, exist_ok=True)

    # Slug: directorio de esta colección dentro del root
    if args.slug:
        slug = args.slug
    else:
        # Auto-slug from series name: lowercase, spaces→underscores, strip non-alnum
        slug = re.sub(r"[^a-z0-9]+", "_", args.name.lower()).strip("_")
        slug = re.sub(r"_+", "_", slug)

    out_dir = root_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = Path(args.cache) if args.cache else out_dir / "series_cache.json"

    # 1. Obtener lista de álbumes
    if args.from_cache:
        if not cache_path.exists():
            print(f"❌ --from-cache: no existe {cache_path}")
            return
        albums = json.loads(cache_path.read_text())
        print(f"\n📦 --from-cache: {len(albums)} álbumes desde {cache_path}")
    else:
        albums = fetch_series(args.series, cache_path)
        print(f"\n🎵 {len(albums)} álbumes en la serie")

    # 1b. Descripciones / info de álbumes
    desc_db = fetch_album_info(albums, cache_path, args)

    # 2. Obtener usuarios
    users = args.users or get_users(args.db)
    print(f"👥 {len(users)} usuarios: {', '.join(users)}")

    users_index = []

    # 3. Por cada usuario
    for user in users:
        print(f"\n── {user} ──")
        user_albums = get_user_albums(args.db, user)
        print(f"   {len(user_albums)} álbumes únicos en DB")

        albums_data = []
        for album in albums:
            heard = check_heard(user_albums, album)
            albums_data.append(album_to_json(album, heard, desc_db))

        heard_count = sum(1 for a in albums_data if a["heard"])
        pct = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0
        print(f"   ✅ {heard_count}/{len(albums_data)} escuchados ({pct}%)")

        fname = f"user_{re.sub(r'[^a-z0-9]', '_', user.lower())}.html"
        html  = render_user_html(user, albums_data, args.name)
        (out_dir / fname).write_text(html, encoding="utf-8")
        print(f"   💾 {out_dir / fname}")

        users_index.append({
            "user":  user,
            "file":  fname,
            "heard": heard_count,
            "total": len(albums_data),
            "pct":   pct,
        })

    # 4. Collection index (usuarios de esta colección)
    users_index.sort(key=lambda u: u["pct"], reverse=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    index_html = render_collection_index_html(users_index, args.name, generated)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"\n📋 collection index → {out_dir / 'index.html'}")

    # 5. Root index (agrupa todas las colecciones)
    update_root_index(root_dir, args.name, slug, users_index, generated)
    print(f"\n🎉 Listo! Abre: {root_dir / 'index.html'}")

if __name__ == "__main__":
    main()

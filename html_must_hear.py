#!/usr/bin/env python3
"""
1001 Albums Must Hear — HTML Generator
Scrapes MusicBrainz series, crosses with last.fm scrobbles DB,
generates per-user HTML grids + index.html
"""

import subprocess, json, re, time, argparse, sqlite3, urllib.parse, urllib.request, urllib.error
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
    lfm_key   = getattr(args, "lastfm_api_key",        None)
    lfm_secret= getattr(args, "lastfm_api_secret",     None)

    if not any([use_1001, lfm_key]):
        print("ℹ️  Sin fuente de descripciones (usa --1001-albums o --lastfm-api-key/secret)")
        return {}

    # Layer sources from lowest to highest priority
    if lfm_key and lfm_secret:
        print("\n📡 Fuente: Last.fm")
        lfm_data = fetch_album_info_lastfm(albums, cache_file, lfm_key, lfm_secret)
        desc_db.update(lfm_data)

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

# ── YOUTUBE PRE-FETCH ────────────────────────────────────────────────────────

def fetch_youtube_ids(albums: list, cache_file: Path, force: bool = False) -> dict:
    """Pre-fetch YouTube video IDs for all albums.
    Returns dict keyed by mbid → video_id (str, may be "").
    Uses YouTube search page HTML scrape — no API key needed."""
    yt_cache = cache_file.parent / "youtube_cache.json"
    if yt_cache.exists() and not force:
        cached = json.loads(yt_cache.read_text())
        # Re-try entries that are missing OR were cached as empty (possible bot-wall hit)
        missing = [a for a in albums if a["mbid"] not in cached or cached[a["mbid"]] == ""]
        if not missing:
            print(f"  📦 YouTube caché completo: {yt_cache}")
            return cached
        print(f"  📦 YouTube caché: {len(cached)-sum(1 for v in cached.values() if not v)} con vídeo, "
              f"{sum(1 for v in cached.values() if not v)} vacíos, {len(missing)} a buscar")
    else:
        cached = {}
        missing = albums

    print(f"  🎬 Buscando {len(missing)} vídeos en YouTube...")
    bot_wall_hits = 0
    for i, album in enumerate(missing):
        if i % 25 == 0:
            print(f"    {i}/{len(missing)}... (bot-walls: {bot_wall_hits})")
        q    = urllib.parse.quote_plus(f"{album['artist']} {album['title']} full album")
        html = curl_get(f"https://www.youtube.com/results?search_query={q}")

        # Detect bot/consent wall — YT returns short page or consent redirect
        if not html or len(html) < 5000 or 'consent.youtube.com' in html or '"videoId"' not in html:
            # Don't cache this failure — we'll retry next time
            bot_wall_hits += 1
            time.sleep(2.0)
            continue

        # Extract video IDs from initial page JSON
        ids  = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
        seen = set(); unique = []
        for v in ids:
            if v not in seen:
                seen.add(v); unique.append(v)

        if unique:
            cached[album["mbid"]] = unique[0]
        # If no IDs found but page seems valid, cache empty to avoid re-scraping
        else:
            cached[album["mbid"]] = ""

        time.sleep(0.8)   # be polite to YouTube

    yt_cache.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    found = sum(1 for v in cached.values() if v)
    print(f"  💾 {yt_cache} ({found}/{len(cached)} encontrados, {bot_wall_hits} bloqueados sin cachear)")
    if bot_wall_hits > 0:
        print(f"  ⚠ YouTube bloqueó {bot_wall_hits} peticiones (bot-wall/consent). "
              f"Vuelve a ejecutar con --youtube para reintentar.")
    return cached



# ── MUSICBRAINZ GENRE FETCH ──────────────────────────────────────────────────

# Genres too generic / meta to be useful for filtering
GENRE_BLACKLIST = {
    "seen live", "electronic", "pop", "rock", "music", "indie",
    "alternative", "experimental", "ambient", "noise", "progressive",
    "contemporary", "modern", "classic", "traditional", "americana",
    "lo-fi", "lo fi", "chillout", "chill", "downtempo", "adult contemporary",
    "easy listening", "background music", "world", "world music",
    "singer-songwriter", "singer songwriter", "acoustic", "instrumental",
    "australian", "british", "american", "canadian", "french", "german",
    "spanish", "japanese", "swedish", "norwegian", "irish",
}

def fetch_genres_musicbrainz(albums: list, cache_file: Path) -> dict:
    """Fetch genres for each release-group from MusicBrainz API.
    Returns dict keyed by mbid → list[str] of genres (filtered by blacklist)."""
    genre_cache_path = cache_file.parent / "genres_mb_cache.json"
    if genre_cache_path.exists():
        cached = json.loads(genre_cache_path.read_text())
        missing = [a for a in albums if a["mbid"] not in cached]
        if not missing:
            print(f"  📦 Géneros MB caché completo: {genre_cache_path}")
            return cached
        print(f"  📦 Géneros MB caché parcial: {len(cached)} OK, {len(missing)} pendientes")
    else:
        cached = {}
        missing = albums

    print(f"  🎸 Obteniendo géneros de MusicBrainz para {len(missing)} álbumes...")
    for i, album in enumerate(missing):
        if i % 50 == 0:
            print(f"    {i}/{len(missing)}...")
        url = f"https://musicbrainz.org/ws/2/release-group/{album['mbid']}?inc=genres&fmt=json"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "MustHearAlbums/1.0 (https://github.com/musthear)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            genres = [
                g["name"].lower() for g in data.get("genres", [])
                if g.get("count", 1) >= 1
                and g["name"].lower() not in GENRE_BLACKLIST
                and len(g["name"]) > 2
            ]
            # Sort by vote count descending, keep top 6
            genres_with_count = [
                (g["name"].lower(), g.get("count", 1))
                for g in data.get("genres", [])
                if g["name"].lower() not in GENRE_BLACKLIST and len(g["name"]) > 2
            ]
            genres_with_count.sort(key=lambda x: x[1], reverse=True)
            cached[album["mbid"]] = [g for g, _ in genres_with_count[:6]]
        except Exception as e:
            cached[album["mbid"]] = []
        time.sleep(1.1)  # MB rate limit: 1 req/sec

    genre_cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    total_with = sum(1 for v in cached.values() if v)
    print(f"  💾 {genre_cache_path} ({total_with}/{len(cached)} álbumes con géneros)")
    return cached

# ── HTML GENERATION ───────────────────────────────────────────────────────────

COVER_PLACEHOLDER = "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20width=%22250%22%20height=%22250%22%20viewBox=%220%200%20250%20250%22%3E%3Crect%20width=%22250%22%20height=%22250%22%20fill=%22%23111%22/%3E%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%2260%22%20fill=%22none%22%20stroke=%22%23333%22%20stroke-width=%222%22/%3E%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%228%22%20fill=%22%23333%22/%3E%3C/svg%3E"

def album_to_json(album: dict, heard: bool, desc_db: dict = None,
                   yt_cache: dict = None, genre_cache: dict = None) -> dict:
    key  = _norm(album.get("artist","")) + "|||" + _norm(album.get("title",""))
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
        "yt_id":      (yt_cache or {}).get(album["mbid"], ""),
        "genres":     (genre_cache or {}).get(album["mbid"], []),
    }

def render_user_html(user: str, albums_data: list[dict], series_name: str,
                     data_file: str = "data/albums.json") -> str:
    heard_count   = sum(1 for a in albums_data if a["heard"])
    pending_count = len(albums_data) - heard_count
    pct           = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0

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
    --panel:    380px;
    --header-h: 58px;
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

  /* ── LAYOUT: header top strip, grid left, panel fixed right ── */
  header {{
    position: fixed; top: 0; left: 0;
    right: var(--panel);   /* header stops where panel begins */
    height: var(--header-h);
    z-index: 100;
    background: rgba(10,10,10,.97);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    border-right: 1px solid var(--border);
    padding: 0 20px;
    display: flex; align-items: center; gap: 16px;
    overflow: hidden;
  }}
  .header-title {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.6rem; letter-spacing: .08em;
    color: var(--accent); text-decoration: none; white-space: nowrap;
  }}
  .header-sub {{
    font-family: 'DM Mono', monospace; font-size: .65rem;
    color: var(--muted); line-height: 1.5; flex-shrink: 0;
  }}
  .header-sub strong {{ color: var(--text); }}

  /* ── PROGRESS BAR ── */
  .progress-wrap {{ width: 110px; flex-shrink: 0; }}
  .progress-bar {{
    height: 3px; background: var(--border); border-radius: 2px; overflow: hidden;
  }}
  .progress-fill {{
    height: 100%; background: var(--accent); border-radius: 2px;
    width: {pct}%;
  }}
  .progress-label {{
    font-family: 'DM Mono', monospace; font-size: .6rem; color: var(--muted); margin-top: 3px;
  }}
  .progress-label span {{ color: var(--accent); }}

  /* ── CONTROLS ── */
  .controls {{ display: flex; align-items: center; gap: 8px; margin-left: auto; flex-shrink: 0; }}
  .filter-btn {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 5px 11px; border-radius: 3px;
    border: 1px solid var(--border); background: transparent;
    color: var(--muted); cursor: pointer; transition: all .15s;
  }}
  .filter-btn:hover {{ border-color: var(--muted); color: var(--text); }}
  .filter-btn.active {{ border-color: var(--accent); color: var(--accent); background: rgba(232,255,71,.06); }}
  .search-box {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    padding: 5px 10px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 3px;
    color: var(--text); width: 160px; outline: none; transition: border-color .15s;
  }}
  .search-box:focus {{ border-color: var(--accent); }}
  .search-box::placeholder {{ color: var(--muted); }}

  /* ── GENRE DROPDOWN ── */
  .genre-wrap {{ position: relative; }}
  .genre-btn {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 5px 11px; border-radius: 3px;
    border: 1px solid var(--border); background: transparent;
    color: var(--muted); cursor: pointer; transition: all .15s;
    display: flex; align-items: center; gap: 5px; white-space: nowrap;
  }}
  .genre-btn:hover {{ border-color: var(--muted); color: var(--text); }}
  .genre-btn.active {{ border-color: var(--accent); color: var(--accent); background: rgba(232,255,71,.06); }}
  .genre-btn .badge {{
    background: var(--accent); color: #000; border-radius: 10px;
    padding: 1px 6px; font-size: .58rem; font-weight: 700;
  }}
  .genre-dropdown {{
    display: none; position: absolute; top: calc(100% + 6px); right: 0;
    background: #161616; border: 1px solid var(--border); border-radius: 4px;
    z-index: 500; min-width: 220px; max-height: 360px;
    overflow-y: auto; padding: 6px 0;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
    box-shadow: 0 8px 32px rgba(0,0,0,.6);
  }}
  .genre-dropdown.open {{ display: block; }}
  .genre-dropdown-header {{
    padding: 6px 12px 4px;
    font-family: 'DM Mono', monospace; font-size: .6rem;
    letter-spacing: .15em; text-transform: uppercase; color: var(--muted);
    border-bottom: 1px solid var(--border); margin-bottom: 4px;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .genre-clear {{ color: var(--pending); cursor: pointer; font-size: .58rem; }}
  .genre-clear:hover {{ color: #ff7070; }}
  .genre-item {{
    display: flex; align-items: center; gap: 8px;
    padding: 5px 12px; cursor: pointer; transition: background .1s;
  }}
  .genre-item:hover {{ background: var(--surface); }}
  .genre-item input {{ accent-color: var(--accent); cursor: pointer; flex-shrink: 0; }}
  .genre-item label {{
    font-family: 'DM Mono', monospace; font-size: .7rem; color: var(--text);
    cursor: pointer; flex: 1;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .genre-item label .genre-count {{
    color: var(--muted); font-size: .6rem;
  }}

  /* ── GRID SLIDER ── */
  .grid-sizer {{ display: flex; align-items: center; gap: 6px; }}
  .grid-sizer span {{
    font-family: 'DM Mono', monospace; font-size: .6rem;
    color: var(--muted); min-width: 26px; text-align: right;
  }}
  #grid-slider {{
    -webkit-appearance: none; appearance: none;
    width: 80px; height: 3px; background: var(--border); border-radius: 2px; outline: none; cursor: pointer;
  }}
  #grid-slider::-webkit-slider-thumb {{
    -webkit-appearance: none; width: 11px; height: 11px; border-radius: 50%;
    background: var(--accent); cursor: pointer;
  }}
  #grid-slider::-moz-range-thumb {{
    width: 11px; height: 11px; border-radius: 50%;
    background: var(--accent); border: none; cursor: pointer;
  }}

  /* ── GRID AREA ── */
  #main {{
    margin-top: var(--header-h);
    margin-right: var(--panel);
    padding: 16px 20px 60px;
  }}
  .count-bar {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    color: var(--muted); margin-bottom: 12px; display: flex; gap: 16px; flex-wrap: wrap;
  }}
  .count-bar b {{ color: var(--text); }}
  #grid {{
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: var(--gap);
  }}

  /* ── CARD ── */
  .card {{
    position: relative; aspect-ratio: 1; border-radius: 3px;
    overflow: hidden; cursor: pointer;
    transition: transform .15s;
  }}
  .card:hover {{ transform: scale(1.05); z-index: 10; }}
  .card.hidden {{ display: none; }}
  .card.active-card {{ outline: 2px solid var(--accent); outline-offset: 2px; z-index: 11; }}
  .card img {{
    width: 100%; height: 100%; object-fit: cover; display: block; background: var(--surface);
  }}
  .card::before {{
    content: ''; position: absolute; top: 5px; right: 5px;
    width: 7px; height: 7px; border-radius: 50%; z-index: 3;
  }}
  .card.heard::before  {{ background: var(--heard); box-shadow: 0 0 5px var(--heard); }}
  .card.pending::before {{ background: var(--pending); box-shadow: 0 0 5px var(--pending); }}
  .card-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(0deg, rgba(0,0,0,.9) 0%, rgba(0,0,0,0) 55%);
    opacity: 0; transition: opacity .18s;
    display: flex; flex-direction: column; justify-content: flex-end;
    padding: 7px; z-index: 2;
  }}
  .card:hover .card-overlay {{ opacity: 1; }}
  .card-num   {{ font-family: 'Bebas Neue', sans-serif; font-size: .85rem; color: var(--accent); line-height: 1; }}
  .card-title {{ font-size: .6rem; font-weight: 500; color: #fff; line-height: 1.3;
                 overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
  .card-artist {{ font-size: .55rem; color: var(--muted); margin-top: 2px;
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  /* ── SIDE PANEL (always visible, fixed) ── */
  #panel {{
    position: fixed; top: 0; right: 0; bottom: 0;
    width: var(--panel);
    background: #0c0c0c;
    border-left: 1px solid var(--border);
    z-index: 50;
    display: flex; flex-direction: column;
    overflow: hidden;
  }}
  /* Panel top strip (mirrors header height) */
  .panel-topbar {{
    height: var(--header-h);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center;
    padding: 0 16px;
    flex-shrink: 0;
  }}
  .panel-topbar-label {{
    font-family: 'DM Mono', monospace; font-size: .6rem;
    letter-spacing: .18em; text-transform: uppercase; color: var(--muted);
  }}

  .panel-cover {{
    width: 100%; aspect-ratio: 1; flex-shrink: 0;
    position: relative; background: var(--surface);
    max-height: 190px; overflow: hidden;
  }}
  .panel-cover img {{
    width: 100%; height: 100%; object-fit: cover; display: block;
  }}
  .panel-cover-status {{
    position: absolute; bottom: 8px; left: 8px;
    font-family: 'DM Mono', monospace; font-size: .6rem;
    letter-spacing: .12em; text-transform: uppercase;
    padding: 2px 7px; border-radius: 2px;
  }}
  .panel-cover-status.heard   {{ background: var(--heard); color: #000; }}
  .panel-cover-status.pending {{ background: var(--pending); color: #fff; }}

  .panel-body {{
    flex: 1; overflow-y: auto; padding: 16px;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .panel-body::-webkit-scrollbar {{ width: 3px; }}
  .panel-body::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}

  .panel-empty {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 100%; gap: 8px;
    font-family: 'DM Mono', monospace; font-size: .75rem; color: var(--muted); text-align: center;
  }}
  .panel-empty-icon {{ font-size: 2rem; opacity: .3; }}

  .panel-num    {{ font-family: 'DM Mono', monospace; font-size: .62rem; color: var(--accent); letter-spacing: .15em; margin-bottom: 4px; }}
  .panel-title  {{ font-family: 'Bebas Neue', sans-serif; font-size: 1.5rem; letter-spacing: .04em; color: var(--text); line-height: 1.05; margin-bottom: 3px; }}
  .panel-artist {{ font-size: .82rem; color: var(--muted); margin-bottom: 2px; }}
  .panel-year   {{ font-family: 'DM Mono', monospace; font-size: .68rem; color: var(--muted); margin-bottom: 12px; }}
  .panel-genres {{
    display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 14px;
  }}
  .panel-genre-tag {{
    font-family: 'DM Mono', monospace; font-size: .6rem;
    padding: 2px 8px; border-radius: 2px;
    background: rgba(232,255,71,.08); border: 1px solid rgba(232,255,71,.2);
    color: rgba(232,255,71,.7); letter-spacing: .05em;
  }}
  .panel-divider {{ height: 1px; background: var(--border); margin: 12px 0; }}
  .panel-section-label {{
    font-family: 'DM Mono', monospace; font-size: .58rem;
    letter-spacing: .18em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px;
  }}
  .panel-bio {{
    font-size: .76rem; color: #aaa; line-height: 1.65;
    max-height: 140px; overflow-y: auto;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .panel-bio::-webkit-scrollbar {{ width: 3px; }}
  .panel-bio::-webkit-scrollbar-thumb {{ background: var(--border); }}
  .panel-bio-loading {{ font-family: 'DM Mono', monospace; font-size: .7rem; color: var(--muted); font-style: italic; }}

  .panel-links {{ display: flex; gap: 7px; flex-wrap: wrap; margin-top: 12px; }}
  .panel-link {{
    font-family: 'DM Mono', monospace; font-size: .62rem;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 4px 10px; border-radius: 3px;
    border: 1px solid var(--border); color: var(--muted);
    text-decoration: none; transition: all .15s;
  }}
  .panel-link:hover {{ border-color: var(--accent); color: var(--accent); }}

  .panel-yt-wrap {{
    margin-top: 14px; border-radius: 4px; overflow: hidden;
    background: var(--surface); border: 1px solid var(--border);
  }}
  .panel-yt-wrap iframe {{ display: block; width: 100%; height: 150px; border: none; }}
  .panel-yt-placeholder {{
    height: 70px; display: flex; align-items: center; justify-content: center;
    font-family: 'DM Mono', monospace; font-size: .68rem; color: var(--muted);
  }}

  /* ── MISC ── */
  .back-link {{ font-family: 'DM Mono', monospace; font-size: .68rem; color: var(--muted); text-decoration: none; }}
  .back-link:hover {{ color: var(--text); }}
  #empty {{ display: none; text-align: center; padding: 60px 0; font-family: 'DM Mono', monospace; color: var(--muted); font-size: .75rem; }}

  @media (max-width: 800px) {{
    :root {{ --panel: 100vw; --header-h: 52px; }}
    header {{ right: 0; }}
    #main {{ margin-right: 0; }}
    #panel {{ top: auto; bottom: 0; height: 60vh; border-left: none; border-top: 1px solid var(--border); }}
  }}
</style>
</head>
<body>

<header>
  <a href="index.html" class="back-link">←</a>
  <a href="#" class="header-title">{user}</a>
  <div class="header-sub">
    <strong>{series_name}</strong><br>
    {heard_count} heard &middot; {pending_count} pending
  </div>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill"></div></div>
    <div class="progress-label"><span id="prog-pct">{pct}%</span></div>
  </div>
  <div class="controls">
    <button class="filter-btn active" id="btn-all"     onclick="setFilter('all')">All</button>
    <button class="filter-btn"        id="btn-heard"   onclick="setFilter('heard')">Heard</button>
    <button class="filter-btn"        id="btn-pending" onclick="setFilter('pending')">Pending</button>
    <input class="search-box" id="search" placeholder="Search…" oninput="applyFilters()">

    <!-- Genre multi-select -->
    <div class="genre-wrap">
      <button class="genre-btn" id="genre-btn" onclick="toggleGenreDropdown()">
        Genre <span class="badge" id="genre-badge" style="display:none">0</span> ▾
      </button>
      <div class="genre-dropdown" id="genre-dropdown">
        <div class="genre-dropdown-header">
          Filter by genre
          <span class="genre-clear" onclick="clearGenres()">clear</span>
        </div>
        <div id="genre-list"></div>
      </div>
    </div>

    <div class="grid-sizer">
      <span id="grid-label">10×</span>
      <input type="range" id="grid-slider" min="3" max="20" value="10" step="1" oninput="setGridSize(this.value)">
    </div>
  </div>
</header>

<main id="main">
  <div class="count-bar">
    <span>Showing <b id="vis-count">{len(albums_data)}</b> of {len(albums_data)}</span>
    <span><b id="vis-heard">0</b> heard · <b id="vis-pending">0</b> pending</span>
  </div>
  <div id="grid"></div>
  <div id="empty">No albums match your filters.</div>
</main>

<!-- Side panel: always visible -->
<aside id="panel">
  <div class="panel-topbar">
    <span class="panel-topbar-label">Album detail</span>
  </div>
  <div id="panel-cover-wrap" class="panel-cover" style="display:none">
    <img id="p-cover" src="" alt="">
    <span class="panel-cover-status" id="p-status"></span>
  </div>
  <div class="panel-body" id="panel-body">
    <div class="panel-empty">
      <div class="panel-empty-icon">◉</div>
      Click an album to see details
    </div>
  </div>
</aside>

<script>
let ALBUMS = [];
let filter = 'all';
let gridCols = 10;
let currentAlbum = null;
let selectedGenres = new Set();

// ── LAZY LOADING ──
const imgObserver = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (e.isIntersecting && e.target.dataset.src) {{
      e.target.src = e.target.dataset.src;
      e.target.removeAttribute('data-src');
      imgObserver.unobserve(e.target);
    }}
  }});
}}, {{ rootMargin: '200px' }});

// ── GRID SIZE ──
function setGridSize(val) {{
  gridCols = parseInt(val);
  document.getElementById('grid-label').textContent = val + '\xd7';
  document.getElementById('grid').style.gridTemplateColumns = `repeat(${{gridCols}}, 1fr)`;
  try {{ localStorage.setItem('grid-cols', val); }} catch(e) {{}}
}}

// ── GENRE DROPDOWN ──
function buildGenreList() {{
  const counts = {{}};
  ALBUMS.forEach(a => (a.genres || []).forEach(g => counts[g] = (counts[g] || 0) + 1));
  const sorted = Object.entries(counts).sort((a,b) => b[1]-a[1]);
  const list = document.getElementById('genre-list');
  list.innerHTML = '';
  sorted.forEach(([genre, count]) => {{
    const div = document.createElement('div');
    div.className = 'genre-item';
    const id = 'g-' + genre.replace(/[^a-z0-9]/g,'_');
    div.innerHTML = `
      <input type="checkbox" id="${{id}}" value="${{genre}}" onchange="toggleGenre('${{genre}}', this.checked)">
      <label for="${{id}}">${{genre}} <span class="genre-count">${{count}}</span></label>`;
    list.appendChild(div);
  }});
}}

function toggleGenreDropdown() {{
  const dd = document.getElementById('genre-dropdown');
  const btn = document.getElementById('genre-btn');
  dd.classList.toggle('open');
  btn.classList.toggle('active', dd.classList.contains('open') || selectedGenres.size > 0);
}}

function toggleGenre(genre, checked) {{
  if (checked) selectedGenres.add(genre); else selectedGenres.delete(genre);
  updateGenreBadge();
  applyFilters();
}}

function clearGenres() {{
  selectedGenres.clear();
  document.querySelectorAll('#genre-list input').forEach(i => i.checked = false);
  updateGenreBadge();
  applyFilters();
}}

function updateGenreBadge() {{
  const badge = document.getElementById('genre-badge');
  const btn   = document.getElementById('genre-btn');
  if (selectedGenres.size > 0) {{
    badge.textContent = selectedGenres.size;
    badge.style.display = '';
    btn.classList.add('active');
  }} else {{
    badge.style.display = 'none';
    btn.classList.remove('active');
  }}
}}

// Close dropdown when clicking outside
document.addEventListener('click', e => {{
  if (!e.target.closest('.genre-wrap')) {{
    document.getElementById('genre-dropdown').classList.remove('open');
  }}
}});

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
    card.dataset.genres = (a.genres || []).join(',');
    card.innerHTML = `
      <img data-src="${{a.cover}}" src="{COVER_PLACEHOLDER}" alt="${{a.n}}"
           onerror="this.src='{COVER_PLACEHOLDER}'">
      <div class="card-overlay">
        <div class="card-num">#${{a.n}}</div>
        <div class="card-title">${{a.title}}</div>
        <div class="card-artist">${{a.artist}} · ${{a.year ?? ''}}</div>
      </div>`;
    card.addEventListener('click', () => openPanel(a, card));
    grid.appendChild(card);
  }});
  document.querySelectorAll('img[data-src]').forEach(img => imgObserver.observe(img));
  applyFilters();
}}

// ── PANEL ──
function openPanel(a, cardEl) {{
  document.querySelectorAll('.card.active-card').forEach(c => c.classList.remove('active-card'));
  cardEl.classList.add('active-card');
  currentAlbum = a;

  // Cover
  const coverWrap = document.getElementById('panel-cover-wrap');
  coverWrap.style.display = '';
  const img = document.getElementById('p-cover');
  img.src = `https://coverartarchive.org/release-group/${{a.mbid}}/front-500`;
  img.onerror = function() {{ this.src = '{COVER_PLACEHOLDER}'; }};
  const statusEl = document.getElementById('p-status');
  statusEl.textContent = a.heard ? 'Heard' : 'Pending';
  statusEl.className   = 'panel-cover-status ' + (a.heard ? 'heard' : 'pending');

  // Body
  const body = document.getElementById('panel-body');

  const genreTags = (a.genres || []).map(g =>
    `<span class="panel-genre-tag">${{g}}</span>`).join('');

  const mbUrl      = `https://musicbrainz.org/release-group/${{a.mbid}}`;
  const gen1001Url = a.spotify_id
    ? `https://1001albumsgenerator.com/albums/${{a.spotify_id}}` : '';

  const ytSearchUrl = `https://www.youtube.com/results?search_query=${{encodeURIComponent(a.artist + ' ' + a.title + ' full album')}}`;
  const ytBlock = a.yt_id
    ? `<iframe src="https://www.youtube.com/embed/${{a.yt_id}}"
         allow="autoplay; encrypted-media" allowfullscreen></iframe>
       <div style="padding:5px 10px;font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted)">
         <a href="${{ytSearchUrl}}" target="_blank" style="color:var(--muted);text-decoration:none">↗ open in YouTube</a>
       </div>`
    : `<div class="panel-yt-placeholder">
         No video cached — <a href="${{ytSearchUrl}}" target="_blank" style="color:var(--accent);text-decoration:none">Search YouTube ↗</a>
       </div>`;

  body.innerHTML = `
    <div class="panel-num">#${{a.n}}</div>
    <div class="panel-title">${{a.title}}</div>
    <div class="panel-artist">${{a.artist}}</div>
    <div class="panel-year">${{a.year ?? ''}}</div>
    ${{genreTags ? `<div class="panel-genres">${{genreTags}}</div>` : ''}}
    <div class="panel-links">
      <a class="panel-link" href="${{mbUrl}}" target="_blank">MusicBrainz</a>
      ${{gen1001Url ? `<a class="panel-link" href="${{gen1001Url}}" target="_blank" style="border-color:#7b61ff;color:#7b61ff">1001gen</a>` : ''}}
    </div>
    <div class="panel-divider"></div>
    <div class="panel-section-label">About</div>
    <div class="panel-bio" id="p-bio">
      ${{a.desc && a.desc.length > 40
        ? a.desc
        : '<span class="panel-bio-loading">Loading…</span>'}}
    </div>
    <div class="panel-divider"></div>
    <div class="panel-section-label">Listen on YouTube</div>
    <div class="panel-yt-wrap">${{ytBlock}}</div>
  `;

  if (!a.desc || a.desc.length <= 40) fetchBio(a.artist, a.title, a.mbid);
}}

// ── BIO FETCH ──
async function fetchBio(artist, title, mbid) {{
  const bioEl = document.getElementById('p-bio');
  if (!bioEl) return;
  try {{
    const lfmUrl = `https://ws.audioscrobbler.com/2.0/?method=album.getinfo&artist=${{encodeURIComponent(artist)}}&album=${{encodeURIComponent(title)}}&format=json&api_key=c9b21e5a749e4f279b6cdce9d5b3a7b3`;
    const d = await fetch(lfmUrl).then(r => r.json());
    const wiki = d?.album?.wiki?.summary || d?.album?.wiki?.content || '';
    if (wiki && wiki.length > 40) {{
      bioEl.textContent = wiki.replace(/<[^>]+>/g,'').replace(/ {{2,}}/g,' ').trim().slice(0,800);
      return;
    }}
    const d2 = await fetch(`https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist=${{encodeURIComponent(artist)}}&format=json&api_key=c9b21e5a749e4f279b6cdce9d5b3a7b3`).then(r=>r.json());
    const bio = d2?.artist?.bio?.summary || '';
    if (bio && bio.length > 40) {{
      bioEl.textContent = bio.replace(/<[^>]+>/g,'').replace(/ {{2,}}/g,' ').trim().slice(0,800);
      return;
    }}
    const d3 = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${{encodeURIComponent(artist + ' (album)')}}`).then(r=>r.json());
    const extract = d3?.extract || '';
    bioEl.textContent = extract.length > 40 ? extract.slice(0,800) : 'No info available.';
  }} catch(e) {{
    if (bioEl) bioEl.textContent = 'Could not load info.';
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
    const cardGenres = c.dataset.genres ? c.dataset.genres.split(',') : [];
    const matchGenre = selectedGenres.size === 0
      || [...selectedGenres].some(g => cardGenres.includes(g));
    const show = matchFilter && matchSearch && matchGenre;
    c.classList.toggle('hidden', !show);
    if (show) {{ vis++; if (c.dataset.heard === '1') visH++; else visP++; }}
  }});
  document.getElementById('vis-count').textContent   = vis;
  document.getElementById('vis-heard').textContent   = visH;
  document.getElementById('vis-pending').textContent = visP;
  document.getElementById('empty').style.display     = vis === 0 ? 'block' : 'none';
  const pct = vis > 0 ? Math.round(visH / vis * 100) : 0;
  document.getElementById('prog-pct').textContent = (filter !== 'all' || q || selectedGenres.size > 0)
    ? pct + '%' : '{pct}%';
}}

// ── INIT ──
try {{
  const saved = localStorage.getItem('grid-cols');
  if (saved) {{ const v = Math.min(20,Math.max(3,parseInt(saved))); document.getElementById('grid-slider').value=v; setGridSize(v); }}
  else setGridSize(10);
}} catch(e) {{ setGridSize(10); }}

fetch('{data_file}')
  .then(r => {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
  .then(data => {{
    ALBUMS = data;
    buildGrid();
    buildGenreList();
    // Open first card by default
    setTimeout(() => {{
      const firstCard = document.querySelector('.card:not(.hidden)');
      if (firstCard) {{
        const album = ALBUMS.find(a => a.n === parseInt(firstCard.dataset.num));
        if (album) openPanel(album, firstCard);
      }}
    }}, 100);
  }})
  .catch(err => {{
    document.getElementById('grid').innerHTML =
      '<div style="color:var(--muted);font-family:monospace;padding:40px">⚠ Could not load data: ' + err.message + '</div>';
  }});
</script>
</body>
</html>
"""



# ── SCARUFFI DECADES ──────────────────────────────────────────────────────────

SCARUFFI_DECADES = ["60", "70", "80", "90", "00", "10", "20"]
SCARUFFI_BASE    = "https://scaruffiplaylists.netlify.app"
SCARUFFI_DECADE_LABELS = {
    "60": "1960s", "70": "1970s", "80": "1980s",
    "90": "1990s", "00": "2000s", "10": "2010s", "20": "2020s",
}


def scaruffi_fetch_decade(decade: str, cache_dir: Path, debug: bool = False) -> list:
    """Scrape one decade page from scaruffiplaylists.netlify.app.
    Handles both HTML and Markdown responses automatically."""
    cache_file = cache_dir / f"scaruffi_{decade}s_cache.json"
    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        if data:
            print(f"  📦 Scaruffi {decade}s cache: {cache_file} ({len(data)} albums)")
            return data
        print(f"  ⚠ Cache empty for {decade}s, re-fetching...")

    url = f"{SCARUFFI_BASE}/{decade}/"
    print(f"  🌐 Scaruffi {decade}s: {url}")

    # Try urllib with text/plain Accept first — Netlify SSG sometimes serves
    # the pre-rendered content directly when JS is not requested
    raw = ""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "curl/7.88.1",
            "Accept": "text/plain, text/html;q=0.5",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception:
        pass

    # Fallback to subprocess curl
    if not raw:
        raw = curl_get(url)

    if not raw:
        print(f"  ❌ Could not fetch {url}")
        return []

    if debug:
        debug_file = cache_dir / f"scaruffi_{decade}s_raw.txt"
        debug_file.write_text(raw[:8000], encoding="utf-8")
        print(f"  🔍 Raw saved to {debug_file} ({len(raw)} chars)")

    is_html = raw.strip().startswith("<!") or "<html" in raw[:200] or "<body" in raw[:500]

    if is_html:
        albums = _parse_scaruffi_html(raw)
    else:
        albums = _parse_scaruffi_markdown(raw)
        if not albums:
            albums = _parse_scaruffi_html(raw)

    if not albums:
        print(f"  ⚠ Parsed 0 albums from {len(raw)} chars ({'HTML' if is_html else 'Markdown'})")
        print(f"     First 300 chars: {repr(raw[:300])}")

    cache_file.write_text(json.dumps(albums, ensure_ascii=False, indent=2))
    print(f"  ✅ {len(albums)} albums -> {cache_file}")
    return albums


def _get_link_from_html(html_frag: str, domains: list) -> str:
    """Extract first href matching any of the given domain substrings."""
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_frag)
    for href in hrefs:
        for domain in domains:
            if domain in href:
                return href
    return ""


def _get_cover_from_html(html_frag: str) -> str:
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_frag, re.IGNORECASE)
    if m:
        src = m.group(1)
        return src if src.startswith("http") else SCARUFFI_BASE + src
    return ""


def _parse_scaruffi_html(html: str) -> list:
    """Parse rendered HTML from scaruffiplaylists.netlify.app using stdlib HTMLParser.
    Structure: <h2 id="hN">rating/10</h2><ol class="playlist"><li id="N">...</li></ol>
    Each <li> has: <span class="title">Artist<br><cite>Title</cite><br>(year)</span>
                   <span class="stream"><a class="youtube-link" href="...">
    """
    from html.parser import HTMLParser as _HTMLParser

    class _Parser(_HTMLParser):
        def __init__(self):
            super().__init__()
            self.albums       = []
            self.rank         = 0
            self.cur_rating   = None
            self._h2_buf      = None   # None = not in h2
            self._in_li       = False
            self._in_title    = False
            self._in_cite     = False
            self._li          = {}
            self._title_parts = []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "h2":
                self._h2_buf = ""
            if tag == "li" and a.get("id", "").isdigit():
                self._in_li       = True
                self._in_title    = False
                self._in_cite     = False
                self._li          = {"cover": "", "yt": "", "sp": "", "bc": "", "sc": ""}
                self._title_parts = []
            if not self._in_li:
                return
            cls  = a.get("class", "")
            href = a.get("href",  "")
            if tag == "span" and "title" in cls:
                self._in_title = True
            if tag == "cite" and self._in_title:
                self._in_cite = True
            if tag == "br" and self._in_title:
                self._title_parts.append("\n")
            if tag == "img":
                src = a.get("src", "")
                if src and "icons" not in src and not self._li["cover"]:
                    self._li["cover"] = src if src.startswith("http") else SCARUFFI_BASE + src
            if tag == "a" and href:
                if   "youtube"     in cls: self._li["yt"] = href
                elif "spotify"     in cls: self._li["sp"] = href
                elif "bandcamp"    in cls: self._li["bc"] = href
                elif "soundcloud"  in cls: self._li["sc"] = href

        def handle_endtag(self, tag):
            if tag == "h2" and self._h2_buf is not None:
                m = re.search(r"([\d.]+)/10", self._h2_buf)
                if m:
                    self.cur_rating = float(m.group(1))
                self._h2_buf = None
            if tag == "cite":
                self._in_cite = False
            if tag == "span" and self._in_title:
                self._in_title = False
            if tag == "li" and self._in_li:
                self._in_li = False
                parts = [p.strip() for p in "".join(self._title_parts).split("\n") if p.strip()]
                artist = parts[0] if len(parts) >= 1 else ""
                title  = parts[1] if len(parts) >= 2 else ""
                year   = None
                if len(parts) >= 3:
                    my = re.search(r"\((\d{4})\)", parts[2])
                    if my:
                        year = int(my.group(1))
                if artist and title:
                    self.rank += 1
                    self.albums.append({
                        "rank": self.rank, "artist": artist, "title": title,
                        "year": year, "cover": self._li["cover"],
                        "rating": self.cur_rating,
                        "youtube": self._li["yt"], "spotify": self._li["sp"],
                        "bandcamp": self._li["bc"], "soundcloud": self._li["sc"],
                        "note": "", "mbid": "", "genres": [], "desc": "", "yt_id": "",
                    })

        def handle_data(self, data):
            if self._h2_buf is not None:
                self._h2_buf += data
            if self._in_title:
                self._title_parts.append(data)

    p = _Parser()
    p.feed(html)

    if p.albums:
        return p.albums

    # Fallback: strip tags, parse visible text as Markdown
    clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<style[^>]*>.*?</style>",   "", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<br\s*/?>",                "\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"</(p|li|div|tr|cite)>",     "\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<[^>]+>",                   " ",   clean)
    clean = unescape(clean)
    clean = re.sub(r"[ \t]+",  " ",   clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return _parse_scaruffi_markdown(clean)


def _parse_scaruffi_markdown(md: str) -> list:
    """Parse raw Markdown: ## rating, numbered list items."""
    albums = []
    current_rating = None

    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Rating header — Markdown "## 9.5/10" OR plain stripped text "9.5/10"
        m_rating = re.match(r"^#{1,3}\s*([\d.]+)/10", line) or re.match(r"^([\d.]+)/10\s*$", line)
        if m_rating:
            current_rating = float(m_rating.group(1))
            i += 1
            continue

        m_num = re.match(r"^(\d+)\.\s*(.*)", line)
        if m_num and current_rating is not None:
            rank      = int(m_num.group(1))
            remainder = m_num.group(2).strip()

            cover = ""
            m_img = re.search(r"!\[art\]\((/img/[^)]+)\)", remainder)
            if m_img:
                cover     = SCARUFFI_BASE + m_img.group(1)
                remainder = re.sub(r"!\[art\]\([^)]+\)", "", remainder).strip()

            block_lines = [remainder] if remainder else []
            j = i + 1
            while j < len(lines):
                nl = lines[j].strip()
                if re.match(r"^\d+\.\s", nl) or re.match(r"^##\s+[\d.]+/10", nl) or nl.startswith("[Home]"):
                    break
                block_lines.append(nl)
                j += 1

            raw_block = "\n".join(block_lines)

            def extract_md_link(s, platform):
                m = re.search(r"\[!\[" + platform + r"\]\([^)]*\)\]\(([^)]+)\)", s, re.IGNORECASE)
                return m.group(1) if m else ""

            yt = extract_md_link(raw_block, "youtube")
            sp = extract_md_link(raw_block, "spotify")
            bc = extract_md_link(raw_block, "bandcamp")
            sc = extract_md_link(raw_block, "soundcloud")

            def strip_md_icons(s):
                s = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", "", s)
                s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
                return s.strip()

            text_lines = [strip_md_icons(bl) for bl in block_lines if strip_md_icons(bl)]

            artist = text_lines[0].strip() if len(text_lines) >= 1 else ""
            title  = text_lines[1].strip() if len(text_lines) >= 2 else ""
            year   = None
            note   = ""

            if len(text_lines) >= 3:
                m_year = re.search(r"\((\d{4})\)", text_lines[2])
                if m_year:
                    year = int(m_year.group(1))
            if len(text_lines) >= 4:
                note = re.sub(r"\s+", " ", " ".join(text_lines[3:])).strip()

            if artist and title:
                albums.append({
                    "rank":       rank,
                    "artist":     artist,
                    "title":      title,
                    "year":       year,
                    "cover":      cover,
                    "rating":     current_rating,
                    "youtube":    yt,
                    "spotify":    sp,
                    "bandcamp":   bc,
                    "soundcloud": sc,
                    "note":       note,
                    "mbid":       "",
                    "genres":     [],
                    "desc":       "",
                    "yt_id":      "",
                })
            i = j
            continue

        i += 1

    return albums

def scaruffi_enrich_albums(albums: list, cache_dir: Path,
                            lfm_key: str = "", lfm_secret: str = "",
                            fetch_genres: bool = False) -> list:
    """Enrich Scaruffi albums with Last.fm desc + MusicBrainz genres."""
    enrich_cache = cache_dir / "scaruffi_enrich_cache.json"
    cached = json.loads(enrich_cache.read_text()) if enrich_cache.exists() else {}

    pylast  = None
    network = None
    if lfm_key and lfm_secret:
        pylast = _try_import("pylast")
        if pylast:
            network = pylast.LastFMNetwork(api_key=lfm_key, api_secret=lfm_secret)

    changed = False
    for album in albums:
        key   = _norm(album["artist"]) + "|||" + _norm(album["title"])
        entry = cached.get(key, {})

        if network and not entry.get("desc"):
            try:
                lfm_al = network.get_album(album["artist"], album["title"])
                wiki   = lfm_al.get_wiki_summary() or ""
                wiki   = re.sub(r'<a href="[^"]*last\.fm[^"]*"[^>]*>[^<]*</a>', '', wiki)
                wiki   = re.sub(r'<[^>]+>', '', wiki).strip()
                if wiki and len(wiki) > 40:
                    entry["desc"] = wiki[:800]
                    changed = True
            except Exception:
                pass
            time.sleep(0.25)

        if fetch_genres and not entry.get("mbid") and not entry.get("mbid_tried"):
            q = urllib.parse.quote(f'releasegroup:"{album["title"]}" AND artist:"{album["artist"]}"')
            try:
                req = urllib.request.Request(
                    f"https://musicbrainz.org/ws/2/release-group?query={q}&limit=1&fmt=json",
                    headers={"User-Agent": "ScaruffiTracker/1.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                rgs = data.get("release-groups", [])
                if rgs:
                    entry["mbid"] = rgs[0]["id"]
                    changed = True
            except Exception:
                pass
            entry["mbid_tried"] = True
            time.sleep(1.1)

        if fetch_genres and entry.get("mbid") and not entry.get("genres"):
            try:
                req = urllib.request.Request(
                    f"https://musicbrainz.org/ws/2/release-group/{entry['mbid']}?inc=genres&fmt=json",
                    headers={"User-Agent": "ScaruffiTracker/1.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                glist = [
                    (g["name"].lower(), g.get("count", 1))
                    for g in data.get("genres", [])
                    if g["name"].lower() not in GENRE_BLACKLIST and len(g["name"]) > 2
                ]
                glist.sort(key=lambda x: x[1], reverse=True)
                entry["genres"] = [g for g, _ in glist[:6]]
                changed = True
            except Exception:
                pass
            time.sleep(1.1)

        if entry:
            cached[key]     = entry
            album["desc"]   = entry.get("desc", "")
            album["mbid"]   = entry.get("mbid", "")
            album["genres"] = entry.get("genres", [])

    if changed:
        enrich_cache.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
        print(f"  💾 enrich cache -> {enrich_cache}")

    return albums


def scaruffi_check_heard(user_albums: set, album: dict) -> bool:
    a_n = _norm(album["artist"])
    t_n = _norm(album["title"])
    if not t_n:
        return False
    for ua, ut in user_albums:
        if not ut:
            continue
        title_match = (t_n == ut or t_n in ut or (ut in t_n and len(ut) >= len(t_n) * 0.8))
        if not title_match:
            continue
        if not a_n or a_n in ua or ua in a_n:
            return True
    return False


def render_scaruffi_decade_html(decade: str, albums: list, users_heard: dict,
                                 series_name: str, all_decades: list) -> str:
    label     = SCARUFFI_DECADE_LABELS.get(decade, decade + "s")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    total     = len(albums)
    users     = list(users_heard.keys())

    decade_nav = ""
    for d in SCARUFFI_DECADES:
        lbl    = SCARUFFI_DECADE_LABELS.get(d, d + "s")
        active = "active" if d == decade else ""
        decade_nav += f'<a class="dec-item {active}" href="decade_{d}s.html">{lbl}</a>'

    all_genres: dict = {}
    for a in albums:
        for g in (a.get("genres") or []):
            all_genres[g] = all_genres.get(g, 0) + 1
    genre_opts_js = json.dumps(sorted(all_genres.items(), key=lambda x: -x[1]))

    albums_js = []
    for a in albums:
        heard_by = [u for u in users if scaruffi_check_heard(users_heard[u], a)]
        albums_js.append({
            "rank":       a["rank"],
            "artist":     a["artist"],
            "title":      a["title"],
            "year":       a.get("year"),
            "cover":      a.get("cover", ""),
            "rating":     a.get("rating", 0),
            "youtube":    a.get("youtube", ""),
            "spotify":    a.get("spotify", ""),
            "bandcamp":   a.get("bandcamp", ""),
            "soundcloud": a.get("soundcloud", ""),
            "note":       a.get("note", ""),
            "mbid":       a.get("mbid", ""),
            "genres":     a.get("genres", []),
            "desc":       a.get("desc", ""),
            "yt_id":      a.get("yt_id", ""),
            "heard_by":   heard_by,
        })

    albums_json   = json.dumps(albums_js, ensure_ascii=False)
    users_json    = json.dumps(users, ensure_ascii=False)
    genre_json    = genre_opts_js
    cover_ph      = COVER_PLACEHOLDER

    # ── HTML ─────────────────────────────────────────────────────────────────
    css = """
:root{
  --bg:#0a0a0a;--surface:#111;--border:#1e1e1e;
  --accent:#e8ff47;--heard:#e8ff47;--pending:#ff4747;
  --text:#e0e0e0;--muted:#555;--gap:6px;
  --panel:390px;--header-h:58px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh}
header{
  position:fixed;top:0;left:0;right:var(--panel);height:var(--header-h);z-index:100;
  background:rgba(10,10,10,.97);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--border);border-right:1px solid var(--border);
  padding:0 18px;display:flex;align-items:center;gap:12px;overflow:hidden;
}
.back-link{font-family:'DM Mono',monospace;font-size:.68rem;color:var(--muted);text-decoration:none}
.back-link:hover{color:var(--text)}
.header-title{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;letter-spacing:.08em;color:var(--accent);white-space:nowrap}
.dec-wrap{position:relative}
.dec-btn{
  font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 9px;border-radius:3px;border:1px solid var(--accent);background:rgba(232,255,71,.06);
  color:var(--accent);cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:4px;white-space:nowrap;
}
.dec-btn:hover{background:rgba(232,255,71,.12)}
.dec-dropdown{
  display:none;position:fixed;background:#161616;border:1px solid var(--border);border-radius:4px;
  z-index:9999;min-width:160px;padding:4px 0;box-shadow:0 8px 32px rgba(0,0,0,.6);
}
.dec-dropdown.open{display:block}
.dec-dh{padding:5px 10px 4px;font-family:'DM Mono',monospace;font-size:.56rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);margin-bottom:3px}
.dec-item{display:block;padding:6px 14px;font-family:'DM Mono',monospace;font-size:.68rem;color:var(--text);text-decoration:none;transition:background .1s}
.dec-item:hover{background:var(--surface)}
.dec-item.active{color:var(--accent)}
.controls{display:flex;align-items:center;gap:7px;margin-left:auto;flex-shrink:0}
.filter-btn{
  font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 9px;border-radius:3px;border:1px solid var(--border);
  background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;
}
.filter-btn:hover{border-color:var(--muted);color:var(--text)}
.filter-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(232,255,71,.06)}
.search-box{
  font-family:'DM Mono',monospace;font-size:.62rem;padding:4px 9px;
  background:var(--surface);border:1px solid var(--border);border-radius:3px;
  color:var(--text);width:130px;outline:none;transition:border-color .15s;
}
.search-box:focus{border-color:var(--accent)}
.search-box::placeholder{color:var(--muted)}
.genre-wrap{position:relative}
.genre-btn{
  font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 9px;border-radius:3px;border:1px solid var(--border);background:transparent;
  color:var(--muted);cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:4px;
}
.genre-btn:hover,.genre-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(232,255,71,.06)}
.genre-btn .badge{background:var(--accent);color:#000;border-radius:10px;padding:1px 5px;font-size:.52rem;font-weight:700}
.genre-dropdown{
  display:none;position:fixed;top:calc(100% + 6px);right:0;
  background:#161616;border:1px solid var(--border);border-radius:4px;
  z-index:9999;min-width:200px;max-height:320px;overflow-y:auto;padding:4px 0;
  box-shadow:0 8px 32px rgba(0,0,0,.6);
}
.genre-dropdown.open{display:block}
.genre-dh{
  padding:5px 10px 4px;font-family:'DM Mono',monospace;font-size:.56rem;
  letter-spacing:.15em;text-transform:uppercase;color:var(--muted);
  border-bottom:1px solid var(--border);margin-bottom:3px;
  display:flex;justify-content:space-between;
}
.genre-clear{color:var(--pending);cursor:pointer}
.genre-item{display:flex;align-items:center;gap:7px;padding:4px 10px;cursor:pointer;transition:background .1s}
.genre-item:hover{background:var(--surface)}
.genre-item input{accent-color:var(--accent);cursor:pointer;flex-shrink:0}
.genre-item label{font-family:'DM Mono',monospace;font-size:.65rem;color:var(--text);cursor:pointer;flex:1;display:flex;justify-content:space-between}
.genre-item label span{color:var(--muted);font-size:.56rem}
.rating-wrap{display:flex;gap:3px}
.rating-btn{
  font-family:'DM Mono',monospace;font-size:.58rem;padding:3px 6px;border-radius:3px;
  border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;
}
.rating-btn:hover{border-color:var(--muted);color:var(--text)}
.rating-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(232,255,71,.06)}
#main{margin-top:var(--header-h);margin-right:var(--panel);padding:14px 18px 60px}
.count-bar{font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted);margin-bottom:10px;display:flex;gap:14px}
.count-bar b{color:var(--text)}
#grid{display:grid;grid-template-columns:repeat(10,1fr);gap:var(--gap)}
.card{position:relative;aspect-ratio:1;border-radius:3px;overflow:hidden;cursor:pointer;transition:transform .15s}
.card:hover{transform:scale(1.05);z-index:10}
.card.hidden{display:none}
.card.active-card{outline:2px solid var(--accent);outline-offset:2px;z-index:11}
.card img{width:100%;height:100%;object-fit:cover;display:block;background:var(--surface)}
.heard-dot{position:absolute;top:4px;right:4px;width:7px;height:7px;border-radius:50%;z-index:3;background:var(--heard);box-shadow:0 0 5px var(--heard)}
.card-overlay{
  position:absolute;inset:0;
  background:linear-gradient(0deg,rgba(0,0,0,.9) 0%,rgba(0,0,0,0) 55%);
  opacity:0;transition:opacity .18s;display:flex;flex-direction:column;justify-content:flex-end;
  padding:6px;z-index:2;
}
.card:hover .card-overlay{opacity:1}
.card-rating{font-family:'Bebas Neue',sans-serif;font-size:.78rem;color:var(--accent);line-height:1}
.card-title{font-size:.56rem;font-weight:500;color:#fff;line-height:1.25;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.card-artist{font-size:.52rem;color:var(--muted);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#panel{
  position:fixed;top:0;right:0;bottom:0;width:var(--panel);
  background:#0c0c0c;border-left:1px solid var(--border);
  z-index:50;display:flex;flex-direction:column;overflow:hidden;
}
.panel-topbar{height:var(--header-h);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 15px;flex-shrink:0}
.panel-topbar-label{font-family:'DM Mono',monospace;font-size:.56rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
.panel-cover{width:100%;aspect-ratio:1;flex-shrink:0;position:relative;background:var(--surface);max-height:180px;overflow:hidden}
.panel-cover img{width:100%;height:100%;object-fit:cover;display:block}
.panel-cover-rating{position:absolute;bottom:8px;left:8px;font-family:'Bebas Neue',sans-serif;font-size:1rem;color:var(--accent);background:rgba(0,0,0,.7);padding:2px 7px;border-radius:2px}
.panel-body{flex:1;overflow-y:auto;padding:14px;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.panel-body::-webkit-scrollbar{width:3px}
.panel-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:8px;font-family:'DM Mono',monospace;font-size:.7rem;color:var(--muted);text-align:center}
.panel-empty-icon{font-size:2rem;opacity:.3}
.panel-title{font-family:'Bebas Neue',sans-serif;font-size:1.4rem;letter-spacing:.04em;color:var(--text);line-height:1.05;margin-bottom:2px}
.panel-artist{font-size:.78rem;color:var(--muted);margin-bottom:1px}
.panel-year{font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted);margin-bottom:10px}
.panel-genres{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.panel-genre-tag{font-family:'DM Mono',monospace;font-size:.56rem;padding:2px 6px;border-radius:2px;background:rgba(232,255,71,.07);border:1px solid rgba(232,255,71,.18);color:rgba(232,255,71,.65)}
.panel-heard-by{font-family:'DM Mono',monospace;font-size:.6rem;color:var(--muted);margin-bottom:9px}
.panel-heard-by b{color:var(--heard)}
.panel-divider{height:1px;background:var(--border);margin:9px 0}
.panel-section-label{font-family:'DM Mono',monospace;font-size:.54rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:5px}
.panel-bio{font-size:.72rem;color:#aaa;line-height:1.6;max-height:120px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.panel-bio::-webkit-scrollbar{width:3px}
.panel-bio::-webkit-scrollbar-thumb{background:var(--border)}
.panel-note{font-family:'DM Mono',monospace;font-size:.62rem;color:#666;font-style:italic;line-height:1.5;margin-top:6px}
.panel-links{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}
.panel-link{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.07em;text-transform:uppercase;padding:3px 8px;border-radius:3px;border:1px solid var(--border);color:var(--muted);text-decoration:none;transition:all .15s}
.panel-link:hover{border-color:var(--accent);color:var(--accent)}
.panel-link.yt{border-color:#f00;color:#f00}
.panel-link.yt:hover{background:rgba(255,0,0,.08)}
.panel-link.sp{border-color:#1db954;color:#1db954}
.panel-link.sp:hover{background:rgba(29,185,84,.08)}
.panel-link.bc{border-color:#1da0c3;color:#1da0c3}
.panel-link.sc{border-color:#f50;color:#f50}
.panel-yt-wrap{margin-top:11px;border-radius:4px;overflow:hidden;background:var(--surface);border:1px solid var(--border)}
.panel-yt-wrap iframe{display:block;width:100%;height:145px;border:none}
.panel-yt-placeholder{height:60px;display:flex;align-items:center;justify-content:center;font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted)}
#empty{display:none;text-align:center;padding:50px 0;font-family:'DM Mono',monospace;color:var(--muted);font-size:.7rem}
@media(max-width:800px){
  :root{--panel:100vw;--header-h:50px}
  header{right:0}
  #main{margin-right:0}
  #panel{top:auto;bottom:0;height:55vh;border-left:none;border-top:1px solid var(--border)}
  .dec-wrap{display:none}
}
.user-wrap{position:relative}
.user-btn{font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;padding:4px 9px;border-radius:3px;border:1px solid var(--accent);background:rgba(232,255,71,.06);color:var(--accent);cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:5px;white-space:nowrap}
.user-btn:hover{background:rgba(232,255,71,.12)}
.user-btn .u-name{max-width:90px;overflow:hidden;text-overflow:ellipsis}
.user-dropdown{display:none;position:fixed;background:#161616;border:1px solid var(--border);border-radius:4px;z-index:9999;min-width:164px;padding:4px 0;box-shadow:0 8px 32px rgba(0,0,0,.6)}
.user-dropdown.open{display:block}
.user-dh{padding:5px 10px 4px;font-family:'DM Mono',monospace;font-size:.56rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);margin-bottom:3px}
.user-item{display:flex;align-items:center;gap:7px;padding:5px 10px;cursor:pointer;transition:background .1s;font-family:'DM Mono',monospace;font-size:.68rem;color:var(--text)}
.user-item:hover{background:var(--surface)}
.user-item.active{color:var(--accent)}
.user-item .u-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;background:var(--border)}
.user-item.active .u-dot{background:var(--accent)}
.card::before{content:'';position:absolute;top:4px;right:4px;width:7px;height:7px;border-radius:50%;z-index:3}
.card.heard-user::before{background:var(--heard);box-shadow:0 0 5px var(--heard)}
.card.unheard-user::before{background:var(--pending);box-shadow:0 0 5px var(--pending)}"""

    js = f"""
const ALBUMS = {albums_json};
const USERS  = {users_json};
const GENRE_OPTS = {genre_json};
let filter = 'all';
let selectedGenres = new Set();
let selectedRating = null;
let selectedUser   = null;
const COVER_PH = '{cover_ph}';

function isHeard(a) {{
  if (selectedUser) return a.heard_by.includes(selectedUser);
  return a.heard_by.length > 0;
}}

const imgObs = new IntersectionObserver(entries => {{
  entries.forEach(e => {{
    if (e.isIntersecting && e.target.dataset.src) {{
      e.target.src = e.target.dataset.src;
      e.target.removeAttribute('data-src');
      imgObs.unobserve(e.target);
    }}
  }});
}}, {{rootMargin:'200px'}});

function buildGenreList() {{
  const list = document.getElementById('genre-list');
  list.innerHTML = '';
  GENRE_OPTS.forEach(([genre, count]) => {{
    const div = document.createElement('div');
    div.className = 'genre-item';
    const id = 'g-'+genre.replace(/[^a-z0-9]/g,'_');
    div.innerHTML = '<input type="checkbox" id="'+id+'" value="'+genre+'" onchange="toggleGenre(\\''+genre+'\\',this.checked)"><label for="'+id+'">'+genre+'<span>'+count+'</span></label>';
    list.appendChild(div);
  }});
}}

function toggleGenreDD() {{
  const dd  = document.getElementById('genre-dd');
  const btn = document.getElementById('genre-btn');
  const open = !dd.classList.contains('open');
  dd.classList.toggle('open', open);
  btn.classList.toggle('active', open || selectedGenres.size > 0);
  if (open) {{
    const r = btn.getBoundingClientRect();
    dd.style.top  = (r.bottom + 4) + 'px';
    dd.style.left = Math.max(4, r.right - 200) + 'px';
  }}
}}

function toggleGenre(g, checked) {{
  if (checked) selectedGenres.add(g); else selectedGenres.delete(g);
  const badge = document.getElementById('genre-badge');
  const btn   = document.getElementById('genre-btn');
  if (selectedGenres.size>0) {{ badge.textContent=selectedGenres.size; badge.style.display=''; btn.classList.add('active'); }}
  else {{ badge.style.display='none'; btn.classList.remove('active'); }}
  applyFilters();
}}

function clearGenres() {{
  selectedGenres.clear();
  document.querySelectorAll('#genre-list input').forEach(i=>i.checked=false);
  document.getElementById('genre-badge').style.display='none';
  document.getElementById('genre-btn').classList.remove('active');
  applyFilters();
}}

document.addEventListener('click', e => {{
  if (!e.target.closest('.genre-wrap')) document.getElementById('genre-dd').classList.remove('open');
  if (!e.target.closest('.user-wrap'))  document.getElementById('user-dd').classList.remove('open');
  if (!e.target.closest('.dec-wrap'))   document.getElementById('dec-dd').classList.remove('open');
}});

function toggleDecDD() {{
  const dd  = document.getElementById('dec-dd');
  const btn = document.getElementById('dec-btn');
  const open = !dd.classList.contains('open');
  dd.classList.toggle('open', open);
  if (open) {{
    const r = btn.getBoundingClientRect();
    dd.style.top  = (r.bottom + 4) + 'px';
    dd.style.left = r.left + 'px';
  }}
}}

function buildRatingBtns() {{
  const ratings = [...new Set(ALBUMS.map(a=>a.rating))].sort((a,b)=>b-a);
  const wrap = document.getElementById('rating-btns');
  ratings.forEach(r => {{
    const btn = document.createElement('button');
    btn.className='rating-btn'; btn.textContent=r; btn.dataset.rating=r;
    btn.onclick = () => {{
      if (selectedRating===r) {{ selectedRating=null; btn.classList.remove('active'); }}
      else {{ selectedRating=r; document.querySelectorAll('.rating-btn').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); }}
      applyFilters();
    }};
    wrap.appendChild(btn);
  }});
}}

function buildUserList() {{
  const list = document.getElementById('user-list');
  list.innerHTML = '';
  const allDiv = document.createElement('div');
  allDiv.className = 'user-item' + (!selectedUser ? ' active' : '');
  allDiv.innerHTML = '<span class="u-dot"></span>All users';
  allDiv.onclick = () => setUser(null);
  list.appendChild(allDiv);
  USERS.forEach(u => {{
    const div = document.createElement('div');
    div.className = 'user-item' + (selectedUser===u ? ' active' : '');
    const n = ALBUMS.filter(a=>a.heard_by.includes(u)).length;
    div.innerHTML = '<span class="u-dot"></span>'+u+'<span style="color:var(--muted);font-size:.58rem;margin-left:auto">'+n+'</span>';
    div.onclick = () => setUser(u);
    list.appendChild(div);
  }});
}}

function toggleUserDD() {{
  const dd  = document.getElementById('user-dd');
  const btn = document.getElementById('user-btn');
  const open = !dd.classList.contains('open');
  dd.classList.toggle('open', open);
  if (open) {{
    const r = btn.getBoundingClientRect();
    dd.style.top  = (r.bottom + 4) + 'px';
    dd.style.left = Math.max(4, r.right - 164) + 'px';
  }}
}}

function setUser(u) {{
  selectedUser = u;
  document.getElementById('user-btn-label').textContent = u || 'All users';
  document.getElementById('user-dd').classList.remove('open');
  buildUserList();
  document.querySelectorAll('.card').forEach(card => {{
    const rank = parseInt(card.dataset.num);
    const a    = ALBUMS.find(x=>x.rank===rank);
    if (!a) return;
    const heard = isHeard(a);
    card.dataset.heard = heard ? '1' : '0';
    card.classList.remove('heard-user','unheard-user');
    card.classList.add(heard ? 'heard-user' : 'unheard-user');
    let dot = card.querySelector('.heard-dot');
    if (heard && !dot) {{ dot = document.createElement('div'); dot.className='heard-dot'; card.appendChild(dot); }}
    else if (!heard && dot) {{ dot.remove(); }}
  }});
  applyFilters();
}}

function buildGrid() {{
  const grid = document.getElementById('grid');
  grid.innerHTML='';
  ALBUMS.forEach(a => {{
    const card = document.createElement('div');
    const heard = isHeard(a);
    card.className = 'card ' + (heard ? 'heard-user' : 'unheard-user');
    card.dataset.artist = a.artist.toLowerCase();
    card.dataset.title  = a.title.toLowerCase();
    card.dataset.rating = a.rating;
    card.dataset.genres = (a.genres||[]).join(',');
    card.dataset.heard  = heard ? '1' : '0';
    card.dataset.num    = a.rank;
    const coverSrc = a.cover || COVER_PH;
    const img = document.createElement('img');
    img.dataset.src = coverSrc; img.src = COVER_PH; img.alt = a.rank;
    img.onerror = function(){{ this.onerror=null; this.src=COVER_PH; }};
    card.appendChild(img);
    if (heard) {{ const dot=document.createElement('div'); dot.className='heard-dot'; card.appendChild(dot); }}
    card.insertAdjacentHTML('beforeend',
      '<div class="card-overlay">'+
      '<div class="card-rating">'+a.rating+'</div>'+
      '<div class="card-title">'+a.title+'</div>'+
      '<div class=\"card-artist\">'+a.artist+(a.year?' \xb7 '+a.year:'')+'</div>'+
      '</div>');
    card.addEventListener('click', () => openPanel(a, card));
    grid.appendChild(card);
  }});
  document.querySelectorAll('img[data-src]').forEach(img=>imgObs.observe(img));
  applyFilters();
}}

function openPanel(a, cardEl) {{
  document.querySelectorAll('.card.active-card').forEach(c=>c.classList.remove('active-card'));
  cardEl.classList.add('active-card');

  const coverWrap = document.getElementById('panel-cover-wrap');
  coverWrap.style.display='';
  const img = document.getElementById('p-cover');
  img.src = a.cover || COVER_PH;
  img.onerror = function(){{ this.src=COVER_PH; }};
  document.getElementById('p-rating').textContent = a.rating+'/10';

  const links = [];
  if (a.youtube)    links.push('<a class="panel-link yt" href="'+a.youtube+'" target="_blank">YouTube</a>');
  if (a.spotify)    links.push('<a class="panel-link sp" href="'+a.spotify+'" target="_blank">Spotify</a>');
  if (a.bandcamp)   links.push('<a class="panel-link bc" href="'+a.bandcamp+'" target="_blank">Bandcamp</a>');
  if (a.soundcloud) links.push('<a class="panel-link sc" href="'+a.soundcloud+'" target="_blank">SoundCloud</a>');
  if (a.mbid)       links.push('<a class="panel-link" href="https://musicbrainz.org/release-group/'+a.mbid+'" target="_blank">MusicBrainz</a>');

  let ytBlock = '';
  if (a.yt_id) {{
    ytBlock = '<iframe src="https://www.youtube.com/embed/'+a.yt_id+'" allow="autoplay;encrypted-media" allowfullscreen></iframe>';
  }} else if (a.youtube && a.youtube.includes('youtube')) {{
    const ytUrl = a.youtube.replace('music.youtube.com','www.youtube.com').replace('/playlist?','/embed/videoseries?');
    ytBlock = '<iframe src="'+ytUrl+'" allow="autoplay;encrypted-media" allowfullscreen></iframe>';
  }} else {{
    const q = encodeURIComponent(a.artist+' '+a.title+' full album');
    ytBlock = '<div class="panel-yt-placeholder"><a href="https://www.youtube.com/results?search_query='+q+'" target="_blank" style="color:var(--accent);text-decoration:none">Search YouTube \u2197</a></div>';
  }}

  const genreTags = (a.genres||[]).map(g=>'<span class="panel-genre-tag">'+g+'</span>').join('');
  const heardLine = a.heard_by.length>0 ? '<div class="panel-heard-by">Heard by <b>'+a.heard_by.join(', ')+'</b></div>' : '';
  const bioHtml   = (a.desc&&a.desc.length>40) ? a.desc : '<span style="color:var(--muted);font-style:italic">Loading\u2026</span>';
  const noteHtml  = a.note ? '<div class="panel-note">'+a.note+'</div>' : '';

  document.getElementById('panel-body').innerHTML =
    '<div class="panel-title">'+a.title+'</div>'
    +'<div class="panel-artist">'+a.artist+'</div>'
    +'<div class="panel-year">'+(a.year||'')+'</div>'
    +(genreTags?'<div class="panel-genres">'+genreTags+'</div>':'')
    +heardLine
    +'<div class="panel-links">'+links.join('')+'</div>'
    +'<div class="panel-divider"></div>'
    +'<div class="panel-section-label">Listen on YouTube</div>'
    +'<div class="panel-yt-wrap">'+ytBlock+'</div>'
    +'<div class="panel-divider"></div>'
    +'<div class="panel-section-label">About</div>'
    +'<div class="panel-bio" id="p-bio">'+bioHtml+'</div>'
    +noteHtml;

  if (!a.desc||a.desc.length<=40) fetchBio(a.artist, a.title);
}}

async function fetchBio(artist, title) {{
  const bioEl = document.getElementById('p-bio');
  if (!bioEl) return;
  const KEY = 'c9b21e5a749e4f279b6cdce9d5b3a7b3';
  try {{
    const d = await fetch('https://ws.audioscrobbler.com/2.0/?method=album.getinfo&artist='+encodeURIComponent(artist)+'&album='+encodeURIComponent(title)+'&format=json&api_key='+KEY).then(r=>r.json());
    const wiki = d?.album?.wiki?.summary||d?.album?.wiki?.content||'';
    if (wiki&&wiki.length>40) {{ bioEl.textContent=wiki.replace(/<[^>]+>/g,'').replace(/ {{2,}}/g,' ').trim().slice(0,800); return; }}
    const d2 = await fetch('https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist='+encodeURIComponent(artist)+'&format=json&api_key='+KEY).then(r=>r.json());
    const bio = d2?.artist?.bio?.summary||'';
    if (bio&&bio.length>40) {{ bioEl.textContent=bio.replace(/<[^>]+>/g,'').replace(/ {{2,}}/g,' ').trim().slice(0,800); return; }}
    const d3 = await fetch('https://en.wikipedia.org/api/rest_v1/page/summary/'+encodeURIComponent(artist+' (album)')).then(r=>r.json());
    const ex = d3?.extract||'';
    bioEl.textContent = ex.length>40 ? ex.slice(0,800) : 'No info available.';
  }} catch(e) {{ if(bioEl) bioEl.textContent='Could not load info.'; }}
}}

function setFilter(f) {{
  filter=f;
  ['all','heard','unheard'].forEach(x => {{
    const btn=document.getElementById('btn-'+x); if(!btn) return;
    btn.classList.toggle('active',x===f);
    if(x==='unheard') {{
      btn.style.borderColor=f==='unheard'?'var(--pending)':'';
      btn.style.color=f==='unheard'?'var(--pending)':'';
      btn.style.background=f==='unheard'?'rgba(255,71,71,.06)':'';
    }}
  }});
  applyFilters();
}}

function applyFilters() {{
  const q=document.getElementById('search').value.toLowerCase().trim();
  let vis=0,visH=0;
  document.querySelectorAll('.card').forEach(c => {{
    const mf=filter==='all'||(filter==='heard'&&c.dataset.heard==='1')||(filter==='unheard'&&c.dataset.heard==='0');
    const ms=!q||c.dataset.title.includes(q)||c.dataset.artist.includes(q);
    const cg=c.dataset.genres?c.dataset.genres.split(','):[];
    const mg=selectedGenres.size===0||[...selectedGenres].some(g=>cg.includes(g));
    const mr=!selectedRating||parseFloat(c.dataset.rating)===selectedRating;
    const show=mf&&ms&&mg&&mr;
    c.classList.toggle('hidden',!show);
    if(show){{vis++;if(c.dataset.heard==='1')visH++;}}
  }});
  document.getElementById('vis-count').textContent=vis;
  const uLabel = selectedUser ? ' ('+selectedUser+')' : '';
  document.getElementById('vis-heard').textContent=visH+' heard'+uLabel;
  document.getElementById('empty').style.display=vis===0?'block':'none';
}}

buildGenreList(); buildRatingBtns(); buildUserList(); buildGrid();
setTimeout(()=>{{
  const first=document.querySelector('.card:not(.hidden)');
  if(first){{const a=ALBUMS.find(x=>x.rank===parseInt(first.dataset.num));if(a)openPanel(a,first);}}
}},100);"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Scaruffi {label}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<header>
  <a href="index.html" class="back-link">←</a>
  <span class="header-title">Scaruffi {label}</span>
  <div class="dec-wrap">
    <button class="dec-btn" id="dec-btn" onclick="toggleDecDD()">
      Decade: {label} &#x25BE;
    </button>
    <div class="dec-dropdown" id="dec-dd">
      <div class="dec-dh">Jump to decade</div>
      {decade_nav}
    </div>
  </div>
  <div class="controls">
    <button class="filter-btn active" id="btn-all"     onclick="setFilter('all')">All</button>
    <button class="filter-btn"        id="btn-heard"   onclick="setFilter('heard')">Heard</button>
    <button class="filter-btn"        id="btn-unheard" onclick="setFilter('unheard')">Unheard</button>
    <input class="search-box" id="search" placeholder="Search..." oninput="applyFilters()">
    <div class="genre-wrap">
      <button class="genre-btn" id="genre-btn" onclick="toggleGenreDD()">
        Genre <span class="badge" id="genre-badge" style="display:none">0</span> v
      </button>
      <div class="genre-dropdown" id="genre-dd">
        <div class="genre-dh">Filter by genre <span class="genre-clear" onclick="clearGenres()">clear</span></div>
        <div id="genre-list"></div>
      </div>
    </div>
    <div class="user-wrap">
      <button class="user-btn" id="user-btn" onclick="toggleUserDD()">
        <span class="u-name" id="user-btn-label">All users</span> &#x25BE;
      </button>
      <div class="user-dropdown" id="user-dd">
        <div class="user-dh">View as user</div>
        <div id="user-list"></div>
      </div>
    </div>
    <div class="rating-wrap" id="rating-btns"></div>
  </div>
</header>
<main id="main">
  <div class="count-bar">
    <span>Showing <b id="vis-count">{total}</b> of {total}</span>
    <span><b id="vis-heard">0</b> heard</span>
  </div>
  <div id="grid"></div>
  <div id="empty">No albums match your filters.</div>
</main>
<aside id="panel">
  <div class="panel-topbar">
    <span class="panel-topbar-label">Album detail</span>
  </div>
  <div id="panel-cover-wrap" class="panel-cover" style="display:none">
    <img id="p-cover" src="" alt="">
    <span class="panel-cover-rating" id="p-rating"></span>
  </div>
  <div class="panel-body" id="panel-body">
    <div class="panel-empty"><div class="panel-empty-icon">◉</div>Click an album</div>
  </div>
</aside>
<script>{js}</script>
</body>
</html>"""


def render_scaruffi_index_html(decades_data: dict, users: list, generated: str) -> str:
    rows = ""
    for decade in SCARUFFI_DECADES:
        if decade not in decades_data:
            continue
        albums = decades_data[decade]
        label  = SCARUFFI_DECADE_LABELS.get(decade, decade + "s")
        total  = len(albums)
        user_cells = ""
        for u in users:
            heard = sum(1 for a in albums if u in (a.get("heard_by") or []))
            pct   = round(heard / total * 100) if total else 0
            user_cells += f'<td class="uc"><span class="uc-heard">{heard}</span><span class="uc-pct">{pct}%</span></td>'
        rows += f'<tr><td class="dc"><a href="decade_{decade}s.html" class="dec-a">{label}</a></td><td class="tc">{total}</td>{user_cells}</tr>'

    user_headers = "".join(f'<th>{u}</th>' for u in users)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Scaruffi Decades</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0a0a;--surface:#111;--border:#1e1e1e;--accent:#e8ff47;--text:#e0e0e0;--muted:#555}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh}}
header{{padding:48px 60px 32px;border-bottom:1px solid var(--border)}}
.site-label{{font-family:'DM Mono',monospace;font-size:.65rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}}
h1{{font-family:'Bebas Neue',sans-serif;font-size:3.5rem;letter-spacing:.06em;color:var(--accent);line-height:1}}
.header-meta{{font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted);margin-top:8px}}
main{{padding:40px 60px 80px}}
.back-link{{font-family:'DM Mono',monospace;font-size:.7rem;color:var(--muted);text-decoration:none;display:inline-block;margin-bottom:24px}}
.back-link:hover{{color:var(--text)}}
table{{width:100%;border-collapse:collapse;font-family:'DM Mono',monospace;font-size:.72rem}}
thead th{{color:var(--muted);font-size:.62rem;letter-spacing:.15em;text-transform:uppercase;padding:8px 12px;border-bottom:1px solid var(--border);text-align:left}}
tbody tr{{border-bottom:1px solid #161616;transition:background .1s}}
tbody tr:hover{{background:var(--surface)}}
td{{padding:10px 12px;vertical-align:middle}}
.dc{{width:110px}}
.dec-a{{font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.04em;color:var(--text);text-decoration:none;transition:color .15s}}
.dec-a:hover{{color:var(--accent)}}
.tc{{color:var(--muted);text-align:center}}
.uc{{text-align:center}}
.uc-heard{{color:var(--accent);font-weight:500;display:block}}
.uc-pct{{color:var(--muted);font-size:.6rem}}
footer{{padding:24px 60px;border-top:1px solid var(--border);font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted)}}
@media(max-width:700px){{header,main,footer{{padding-left:20px;padding-right:20px}}}}
</style>
</head>
<body>
<header>
  <div class="site-label">Scaruffi's Best Rock Albums</div>
  <h1>By Decade</h1>
  <div class="header-meta">Generated {generated}</div>
</header>
<main>
  <a href="../index.html" class="back-link">All collections</a>
  <table>
    <thead><tr><th>Decade</th><th>Albums</th>{user_headers}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
</main>
<footer>Generated {generated}</footer>
</body>
</html>"""


def scaruffi_fetch_covers(albums_all: list, cache_dir: Path,
                          lfm_key: str = "", discogs_token: str = "") -> int:
    """Fetch HD covers for Scaruffi albums.
    Priority: MusicBrainz CAA (needs mbid) → Last.fm → Discogs.
    Updates the cover field in-place and persists cache.
    Returns number of covers updated."""
    cover_cache_file = cache_dir / "scaruffi_covers_cache.json"
    cache = json.loads(cover_cache_file.read_text()) if cover_cache_file.exists() else {}

    updated = 0
    for album in albums_all:
        key = _norm(album["artist"]) + "|||" + _norm(album["title"])
        if cache.get(key):
            album["cover"] = cache[key]
            continue  # already have HD cover

        artist = album["artist"]
        title  = album["title"]
        mbid   = album.get("mbid", "")
        new_cover = ""

        # ── Strategy 1: Cover Art Archive (free, high-res) ──
        if mbid and not new_cover:
            try:
                url = f"https://coverartarchive.org/release-group/{mbid}/front"
                req = urllib.request.Request(url, headers={"User-Agent": "ScaruffiTracker/1.0"})
                # CAA redirects to actual image — follow redirect
                with urllib.request.urlopen(req, timeout=10) as r:
                    new_cover = r.url  # final URL after redirect
            except Exception:
                pass
            time.sleep(0.3)

        # ── Strategy 2: Last.fm album.getInfo image (extralarge ~300px) ──
        if not new_cover:
            try:
                api_key = lfm_key or "c9b21e5a749e4f279b6cdce9d5b3a7b3"
                params  = urllib.parse.urlencode({
                    "method": "album.getinfo",
                    "artist": artist, "album": title,
                    "api_key": api_key, "format": "json"
                })
                req = urllib.request.Request(
                    f"https://ws.audioscrobbler.com/2.0/?{params}",
                    headers={"User-Agent": "ScaruffiTracker/1.0"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                images = data.get("album", {}).get("image", [])
                # Pick largest available: extralarge (index 3), then mega (4)
                for img in reversed(images):
                    src = img.get("#text", "")
                    if src and "2a96cbd8b46e442fc41c2b86b821562f" not in src:
                        new_cover = src
                        break
            except Exception:
                pass
            time.sleep(0.25)

        # ── Strategy 3: Discogs search ──
        if not new_cover and discogs_token:
            try:
                q = urllib.parse.urlencode({"q": f"{artist} {title}", "type": "release", "per_page": "1"})
                req = urllib.request.Request(
                    f"https://api.discogs.com/database/search?{q}",
                    headers={
                        "User-Agent":    "ScaruffiTracker/1.0",
                        "Authorization": f"Discogs token={discogs_token}",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                results = data.get("results", [])
                if results:
                    thumb = results[0].get("cover_image") or results[0].get("thumb", "")
                    if thumb:
                        new_cover = thumb
            except Exception:
                pass
            time.sleep(0.5)

        if new_cover:
            album["cover"] = new_cover
            cache[key] = new_cover
            updated += 1
            print(f"    🖼  {artist} — {title}")

    cover_cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return updated


def run_scaruffi(args, root_dir: Path) -> None:
    out_dir = root_dir / "scaruffi"
    out_dir.mkdir(parents=True, exist_ok=True)

    lfm_key    = getattr(args, "lastfm_api_key",    None) or ""
    lfm_secret = getattr(args, "lastfm_api_secret", None) or ""
    do_genres  = getattr(args, "genres",             False)
    index_only = getattr(args, "index_only",         False)

    users = args.users or get_users(args.db)
    print(f"Scaruffi: {len(users)} users: {', '.join(users)}")

    users_heard = {u: get_user_albums(args.db, u) for u in users}
    generated   = datetime.now().strftime("%Y-%m-%d %H:%M")
    decades_data: dict = {}

    # Decide which decades to process
    decade_arg = getattr(args, "scaruffi_decade", None)
    if decade_arg:
        def _norm_decade(d):
            d = d.strip()
            if len(d) == 4: d = d[2:]    # "1960" → "60"
            if d == "0":    d = "00"      # edge case
            return d.zfill(2)
        decades_to_run = [_norm_decade(d) for d in decade_arg]
    else:
        decades_to_run = list(SCARUFFI_DECADES) if not index_only else []

    # Always load all existing caches for the index, but only scrape selected decades
    for decade in SCARUFFI_DECADES:
        cache_file = out_dir / f"scaruffi_{decade}s_cache.json"

        # Decades NOT selected: just load from cache for the combined index
        if decade not in decades_to_run and not index_only:
            if cache_file.exists():
                cached = json.loads(cache_file.read_text())
                if cached:
                    enrich_path = out_dir / "scaruffi_enrich_cache.json"
                    if enrich_path.exists() and not index_only:
                        ec = json.loads(enrich_path.read_text())
                        for a in cached:
                            key = _norm(a["artist"]) + "|||" + _norm(a["title"])
                            e   = ec.get(key, {})
                            a.setdefault("desc",   e.get("desc",   ""))
                            a.setdefault("mbid",   e.get("mbid",   ""))
                            a.setdefault("genres", e.get("genres", []))
                    for a in cached:
                        a["heard_by"] = [u for u in users if scaruffi_check_heard(users_heard[u], a)]
                    decades_data[decade] = cached
            continue

        print(f"\n-- Scaruffi {SCARUFFI_DECADE_LABELS.get(decade, decade+'s')} --")
        cache_file = out_dir / f"scaruffi_{decade}s_cache.json"

        if index_only:
            if not cache_file.exists():
                print(f"  No cache for {decade}s, skipping")
                continue
            albums = json.loads(cache_file.read_text())
        else:
            # Force re-fetch if --decade was explicitly specified
            if decade_arg and cache_file.exists():
                cache_file.unlink()
                print(f"  🗑 Deleted cache for {decade}s (--decade flag, re-fetching)")
            albums = scaruffi_fetch_decade(decade, out_dir, debug=getattr(args,'scaruffi_debug',False))

        if not albums:
            continue

        if (lfm_key or do_genres) and not index_only:
            print(f"  Enriching {len(albums)} albums...")
            albums = scaruffi_enrich_albums(albums, out_dir, lfm_key, lfm_secret, do_genres)
        elif index_only:
            enrich_path = out_dir / "scaruffi_enrich_cache.json"
            if enrich_path.exists():
                ec = json.loads(enrich_path.read_text())
                for a in albums:
                    key = _norm(a["artist"]) + "|||" + _norm(a["title"])
                    e   = ec.get(key, {})
                    a["desc"]   = e.get("desc",   "")
                    a["mbid"]   = e.get("mbid",   "")
                    a["genres"] = e.get("genres", [])

        for a in albums:
            a["heard_by"] = [u for u in users if scaruffi_check_heard(users_heard[u], a)]

        decades_data[decade] = albums

        html = render_scaruffi_decade_html(
            decade, albums, users_heard, "Scaruffi",
            list(SCARUFFI_DECADES)
        )
        out_path = out_dir / f"decade_{decade}s.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"  -> {out_path}")

    # ── Carátulas HD (--caratulas) ──
    do_caratulas = getattr(args, "caratulas", False)
    if do_caratulas and not index_only and decades_data:
        discogs_token = getattr(args, "discogs_token", "") or ""
        all_albums = [a for v in decades_data.values() for a in v]
        print(f"\n🖼  Buscando carátulas HD para {len(all_albums)} álbumes...")
        n = scaruffi_fetch_covers(all_albums, out_dir, lfm_key, discogs_token)
        print(f"  ✅ {n} carátulas actualizadas")
        # Re-render HTMLs with updated covers
        if n > 0:
            print("  Re-rendering HTMLs con carátulas HD...")
            # Persist updated covers back to decade caches
            for decade, albums in decades_data.items():
                cf = out_dir / f"scaruffi_{decade}s_cache.json"
                if cf.exists():
                    cached = json.loads(cf.read_text())
                    cover_map = {(a["artist"], a["title"]): a["cover"] for a in albums}
                    for ca in cached:
                        new_c = cover_map.get((ca["artist"], ca["title"]))
                        if new_c:
                            ca["cover"] = new_c
                    cf.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
            # Re-render
            for decade, albums in decades_data.items():
                html = render_scaruffi_decade_html(
                    decade, albums, users_heard, "Scaruffi", list(SCARUFFI_DECADES)
                )
                (out_dir / f"decade_{decade}s.html").write_text(html, encoding="utf-8")
            print("  ✅ HTMLs re-renderizados")

    if not decades_data:
        print("No decade data to index")
        return

    (out_dir / "index.html").write_text(
        render_scaruffi_index_html(decades_data, users, generated), encoding="utf-8"
    )
    print(f"\nScaruffi index -> {out_dir / 'index.html'}")

    # Update root index
    meta_file = root_dir / ".collections_meta.json"
    collections = json.loads(meta_file.read_text()) if meta_file.exists() else []
    total_albums = sum(len(v) for v in decades_data.values())
    entry = {
        "slug":    "scaruffi",
        "name":    "Scaruffi's Best Rock (by Decade)",
        "users":   len(users),
        "total":   total_albums,
        "avg_pct": 0,
        "updated": generated,
        "url":     "scaruffi/index.html",
    }
    existing = [c for c in collections if c["slug"] != "scaruffi"]
    existing.append(entry)
    existing.sort(key=lambda c: c["name"])
    meta_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    (root_dir / "index.html").write_text(render_root_index_html(existing, generated), encoding="utf-8")
    print(f"Root index updated -> {root_dir / 'index.html'}")
    print(f"\nDone! Open: {out_dir / 'index.html'}")

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
      <a class="col-card" href="{c.get('url', c['slug']+'/index.html')}">
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

    parser.add_argument("--lastfm-api-key",        dest="lastfm_api_key",        default=None,
                        help="Last.fm API key (para wiki de álbumes/artistas)")
    parser.add_argument("--lastfm-api-secret",     dest="lastfm_api_secret",     default=None,
                        help="Last.fm API secret")
    parser.add_argument("--youtube",      action="store_true",
                        help="Pre-fetch YouTube video IDs for all albums (saved in youtube_cache.json)")
    parser.add_argument("--genres",       action="store_true",
                        help="Pre-fetch géneros desde MusicBrainz (guardado en genres_mb_cache.json)")
    parser.add_argument("--audit",        action="store_true",
                        help="Mostrar álbumes sin descripción / sin YouTube y salir")
    parser.add_argument("--index-only",   action="store_true",
                        help="Solo regenerar HTMLs y ambos índices desde caché existente, sin scrapear ni APIs")
    parser.add_argument("--scaruffi-decades", dest="scaruffi_decades", action="store_true",
                        help="Scrapear decadas de Scaruffi (scaruffiplaylists.netlify.app)")
    parser.add_argument("--decade", dest="scaruffi_decade", nargs="+", metavar="DECADE",
                        help="Décadas a (re)scrapear: 60 70 80 90 00 10  (borra caché y re-fetcha)")
    parser.add_argument("--caratulas", dest="caratulas", action="store_true",
                        help="Buscar carátulas HD para álbumes Scaruffi (CAA → Last.fm → Discogs)")
    parser.add_argument("--discogs-token", dest="discogs_token", default="",
                        help="Token Discogs para carátulas HD (opcional, mejora resultados)")
    parser.add_argument("--scaruffi-debug",   dest="scaruffi_debug",   action="store_true",
                        help="Guardar HTML/Markdown crudo de Scaruffi para depurar el parser")
    args = parser.parse_args()

    root_dir = Path(args.out)
    root_dir.mkdir(parents=True, exist_ok=True)

    # Scaruffi mode: fully separate flow
    if getattr(args, "scaruffi_decades", False):
        run_scaruffi(args, root_dir)
        return

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

    # --index-only implies --from-cache and skips all API fetching
    if args.index_only:
        args.from_cache = True

    # 1. Obtener lista de álbumes
    if args.from_cache:
        if not cache_path.exists():
            print(f"❌ --from-cache / --index-only: no existe {cache_path}")
            return
        albums = json.loads(cache_path.read_text())
        print(f"\n📦 caché: {len(albums)} álbumes desde {cache_path}")
    else:
        albums = fetch_series(args.series, cache_path)
        print(f"\n🎵 {len(albums)} álbumes en la serie")

    # 1b. Descripciones / info de álbumes (skip if --index-only)
    if args.index_only:
        # Load whichever description cache exists
        desc_db = {}
        for fname in ("descriptions_lastfm_cache.json", "descriptions_1001_cache.json"):
            p = cache_path.parent / fname
            if p.exists():
                data = json.loads(p.read_text())
                for k, v in data.items():
                    if k not in desc_db or (v.get("desc") and not desc_db[k].get("desc")):
                        desc_db[k] = v
                print(f"  📦 Desc cargado desde {fname}: {len(data)} entradas")
    else:
        desc_db = fetch_album_info(albums, cache_path, args)

    # 1c. YouTube IDs — always load existing cache; only re-fetch if --youtube passed
    yt_cache_path = cache_path.parent / "youtube_cache.json"
    if yt_cache_path.exists():
        yt_cache = json.loads(yt_cache_path.read_text())
        print(f"  📦 YouTube caché cargado: {sum(1 for v in yt_cache.values() if v)}/{len(yt_cache)} con vídeo")
    else:
        yt_cache = {}
    if args.youtube and not args.index_only:
        print("\n🎬 YouTube pre-fetch")
        yt_cache = fetch_youtube_ids(albums, cache_path)

    # 1d. Genre IDs — always load existing cache; only re-fetch if --genres passed
    genre_cache_path = cache_path.parent / "genres_mb_cache.json"
    if genre_cache_path.exists():
        genre_cache = json.loads(genre_cache_path.read_text())
        print(f"  📦 Géneros caché cargado: {sum(1 for v in genre_cache.values() if v)}/{len(genre_cache)} con géneros")
    else:
        genre_cache = {}
    if args.genres and not args.index_only:
        print("\n🎸 MusicBrainz géneros pre-fetch")
        genre_cache = fetch_genres_musicbrainz(albums, cache_path)

    # 1d. Audit mode: show gaps in cache and exit
    if args.audit:
        print("\n🔍 AUDIT — álbumes con datos incompletos:")
        no_desc = []; no_yt = []
        for album in albums:
            key = _norm(album["artist"]) + "|||" + _norm(album["title"])
            info = desc_db.get(key, {})
            label = f"  #{album['number']:4d}  {album['artist']} — {album['title']}"
            if not info.get("desc"):        no_desc.append(label)
            if not yt_cache.get(album["mbid"]): no_yt.append(label)

        for section, items in [
            (f"Sin descripción ({len(no_desc)})", no_desc),
            (f"Sin YouTube ({len(no_yt)})", no_yt),
        ]:
            print(f"\n{'─'*50}\n{section}:")
            for item in items[:20]:
                print(item)
            if len(items) > 20:
                print(f"  ... y {len(items)-20} más")
        return

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
            albums_data.append(album_to_json(album, heard, desc_db, yt_cache, genre_cache))

        heard_count = sum(1 for a in albums_data if a["heard"])
        pct = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0
        print(f"   ✅ {heard_count}/{len(albums_data)} escuchados ({pct}%)")

        # Save per-user JSON (external data file)
        safe_user = re.sub(r"[^a-z0-9]", "_", user.lower())
        data_dir  = out_dir / "data"
        data_dir.mkdir(exist_ok=True)
        json_fname = f"{safe_user}.json"
        (data_dir / json_fname).write_text(
            json.dumps(albums_data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8"
        )

        fname    = f"user_{safe_user}.html"
        data_rel = f"data/{json_fname}"
        html     = render_user_html(user, albums_data, args.name, data_file=data_rel)
        (out_dir / fname).write_text(html, encoding="utf-8")
        print(f"   💾 {out_dir / fname}  +  {data_dir / json_fname}")

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

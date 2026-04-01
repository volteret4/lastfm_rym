#!/usr/bin/env python3
"""
Sputnikmusic Best Albums Scraper & HTML Generator

Scrapes https://www.sputnikmusic.com/best/albums/YYYY/ for multiple years,
organises albums by genre, and generates HTML grids with per-user heard status.

Standalone:
    python3 tools/must_hear/sputnik_must_hear.py
        --years 2020 2021 2022
        --must-hear-db db/must_hear_rym_new.db
        --scrobbles-db db/lastfm_cache_rym_new_normalized.db
        [--out docs/must_hear] [--force-scrape]

From html_must_hear.py:
    from tools.must_hear.sputnik_must_hear import run_sputnik
    run_sputnik(args, root_dir)
"""

import json, re, time, sqlite3, argparse, random
from pathlib import Path
from datetime import datetime
from html import unescape, escape

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ── CONSTANTS ─────────────────────────────────────────────────────────────────

SPUTNIK_BASE = "https://www.sputnikmusic.com"
CHART_URL    = "https://www.sputnikmusic.com/best/albums/{year}/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language":          "en-US,en;q=0.9",
    "Accept-Encoding":          "gzip, deflate, br",
    "Connection":               "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":           "document",
    "Sec-Fetch-Mode":           "navigate",
    "Sec-Fetch-Site":           "none",
    "Sec-Fetch-User":           "?1",
    "Cache-Control":            "max-age=0",
}


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _cover_hd(url: str) -> str:
    """Convert a Sputnik cover path to a full HTTPS URL."""
    if not url:
        return ""
    url = url.strip()
    # Strip thumbnail suffix
    url = re.sub(r"-thumbl?$", "", url)
    if url.startswith("/"):
        url = SPUTNIK_BASE + url
    elif url.startswith("//"):
        url = "https:" + url
    return url


def _ensure_col(conn: sqlite3.Connection, table: str, col: str, coltype: str = "TEXT") -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


def _get_users(mh_conn, scr_conn, users_arg) -> list[str]:
    if users_arg:
        return list(users_arg)
    if mh_conn:
        rows = mh_conn.execute("SELECT username FROM users ORDER BY username").fetchall()
        if rows:
            return [r[0] for r in rows]
    if scr_conn:
        # Normalized DB: users table
        try:
            rows = scr_conn.execute("SELECT name FROM users ORDER BY name").fetchall()
            return [r[0] for r in rows]
        except Exception:
            pass
    return []


def _get_scrobbles(scr_conn, user: str) -> set:
    """Return set of (norm_artist, norm_title) tuples from scrobbles DB."""
    if not scr_conn:
        return set()
    safe = re.sub(r"[^a-z0-9_]", "_", user.lower())
    try:
        rows = scr_conn.execute(
            f"SELECT ar.name, t.name FROM scrobbles_{safe} s "
            "JOIN tracks t ON t.id=s.track_id "
            "JOIN artists ar ON ar.id=t.artist_id"
        ).fetchall()
        return {(_norm(r[0]), _norm(r[1])) for r in rows}
    except Exception:
        pass
    try:
        rows = scr_conn.execute(
            "SELECT artist, track FROM scrobbles WHERE user=?", (user,)
        ).fetchall()
        return {(_norm(r[0]), _norm(r[1])) for r in rows}
    except Exception:
        return set()


def _check_heard(scrobbles: set, artist: str, title: str) -> bool:
    na, nt = _norm(artist), _norm(title)
    for sa, st in scrobbles:
        if not (na in sa or sa in na):
            continue
        if st == nt:
            return True
        if len(nt) >= 4 and len(st) >= 4 and (nt in st or st in nt):
            return True
    return False


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch(url: str, session, retries: int = 3, delay: float = 2.5) -> str:
    for attempt in range(retries):
        if attempt:
            time.sleep(4 * attempt + random.uniform(0, 2))
        try:
            r = session.get(url, headers=_HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  ⚠  Rate limited, esperando {wait}s...")
                time.sleep(wait)
                continue
            print(f"  ⚠  HTTP {r.status_code}: {url}")
        except Exception as e:
            print(f"  ⚠  Intento {attempt + 1}/{retries}: {e}")
    return ""


# ── CHART PAGE PARSER ─────────────────────────────────────────────────────────

def _parse_genre_map(html: str) -> dict[str, str]:
    """
    Extract {genre_id: genre_name} for the main genres from the chart dropdown.

    Dropdown structure:
      All Genres (0)
      -----             ← first separator (cosmetic, after "All Genres")
      Alternative Rock, Electronic, ..., Rock   ← MAIN genres
      -----             ← second separator
      Ambient, Americana, ...                   ← sub-genres (skipped)

    We collect genres between the first and second separator.
    """
    gmap: dict[str, str] = {}
    sep_count = 0
    for m in re.finditer(r'<option[^>]+value="([^"]*)"[^>]*>([^<]+)</option>', html):
        gid, gname = m.group(1), unescape(m.group(2).strip())
        if not gid:
            sep_count += 1
            if sep_count >= 2:
                break   # sub-genres start here — stop
            continue
        if gid == "0":
            continue
        gmap[gid] = gname.strip()
    return gmap


def _fetch_genre_chart(year: int, genre_id: str, session) -> set[str]:
    """POST to get genre-filtered chart and return set of album paths."""
    url = CHART_URL.format(year=year)
    try:
        time.sleep(1.5 + random.uniform(0, 1))
        r = session.post(url, headers=_HEADERS,
                         data={"genreid2": genre_id}, timeout=20)
        if r.status_code == 200:
            return {
                m.group(1).rstrip("/")
                for m in re.finditer(
                    r'OnClick="window\.location\.href\s*=\s*\'(/album/[^\']+)\'"',
                    r.text, re.IGNORECASE
                )
            }
    except Exception as e:
        print(f"    ⚠  género {genre_id}: {e}")
    return set()


def _parse_chart(html: str, year: int) -> list[dict]:
    """
    Parse Sputnikmusic best-albums chart page.

    Actual structure (confirmed from live HTML):
      - Info cell: OnClick="window.location.href = '/album/ID/Slug'"
          <font size=3 ...><b>Artist</b></font>
          <font size=2 class=darktext>Title</font>
          <font size=3>4.44</font>   ← rating
          <font size=2 class=contrasttext>35 votes
      - Cover cell: <a href=/album/ID/Slug/><img data-original=/images/albums/ID.jpg-thumbl>

    Genres are fetched separately via genre-filtered POST requests.
    """
    albums = []

    # Build cover map: album path (no trailing slash) → cover URL
    cover_map: dict[str, str] = {}
    for m in re.finditer(
        r'href=(/album/(\d+)/[^>"\s]+?)(?:/)?\s*>'
        r'.*?data-original=(/images/albums/\d+\.jpg[^\s"\'<>]*)',
        html, re.DOTALL
    ):
        path = m.group(1).rstrip("/")
        cover_map[path] = _cover_hd(m.group(3))

    # Parse info cells in order
    info_re = re.compile(
        r'OnClick="window\.location\.href\s*=\s*\'(/album/[^\']+)\'"[^>]*>(.*?)</td>',
        re.DOTALL | re.IGNORECASE,
    )
    artist_re = re.compile(r'<b>\s*([^<]+?)\s*</b>')
    title_re  = re.compile(r'class=darktext>\s*([^<]+?)\s*</font>', re.IGNORECASE)
    rating_re = re.compile(r'<font\s+size=3>\s*([0-9]+\.[0-9]+)\s*</font>', re.IGNORECASE)
    votes_re  = re.compile(r'([\d,]+)\s+vote', re.IGNORECASE)

    rank = 1
    for m in info_re.finditer(html):
        album_path = m.group(1).rstrip("/")
        cell       = m.group(2)

        ar_m  = artist_re.search(cell)
        ti_m  = title_re.search(cell)
        if not ar_m or not ti_m:
            continue

        artist = unescape(ar_m.group(1).strip())
        title  = unescape(ti_m.group(1).strip())
        if not artist or not title:
            continue

        rat_m = rating_re.search(cell)
        vot_m = votes_re.search(cell)

        albums.append({
            "number":          rank,
            "artist":          artist,
            "title":           title,
            "year":            year,
            "rating":          float(rat_m.group(1)) if rat_m else 0.0,
            "votes":           int(vot_m.group(1).replace(",", "")) if vot_m else 0,
            "cover_url":       cover_map.get(album_path, ""),
            "sputnik_url":     SPUTNIK_BASE + album_path + "/",
            "genres":          [],
            "mbid":            "",
            "yt_id":           "",
            "desc_lfm_album":  "",
            "desc_lfm_artist": "",
        })
        rank += 1

    return albums


def _fetch_album_genres(url: str, session, cache: dict) -> list[str]:
    """Scrape genres from an individual Sputnikmusic album page, with in-memory cache."""
    if url in cache:
        return cache[url]
    html = _fetch(url, session, delay=1.5)
    genres: list[str] = []
    if html:
        for m in re.finditer(
            r'href=["\'][^"\']*?/genre/[^"\']*["\'][^>]*>\s*([^<]+?)\s*<', html
        ):
            g = unescape(m.group(1).strip())
            if g and g not in genres:
                genres.append(g)
    cache[url] = genres
    return genres


def sputnik_fetch_year(year: int, cache_path: Path,
                       force: bool = False,
                       enrich_genres: bool = True) -> list[dict]:
    """
    Scrape (or load from cache) all albums for one Sputnikmusic best-albums year.
    When genres are not embedded in the chart, fetches individual album pages.
    """
    if not force and cache_path.exists():
        data = json.loads(cache_path.read_text())
        if data:
            print(f"  📦 {year}: {len(data)} álbumes desde caché")
            return data
        print(f"  ⚠  Caché vacío para {year}, re-scrapeando...")

    if not _HAS_REQUESTS:
        raise RuntimeError("Instala requests: pip install requests")

    session = _req.Session()
    url     = CHART_URL.format(year=year)
    print(f"  📡 {url}")
    time.sleep(2 + random.uniform(0, 1))
    html = _fetch(url, session)

    # Fallback: if scraping failed or blocked, try a manually saved HTML file
    tmp_path = Path(f"/tmp/sputnik_{year}.html")
    if not html:
        if tmp_path.exists():
            print(f"  📂 Usando HTML guardado en {tmp_path}")
            html = tmp_path.read_text(errors="replace")
        else:
            print(f"  ❌ No se pudo obtener {year}")
            print(f"     💡 Descarga manualmente {url} y guárdalo en {tmp_path}")
            return []

    albums = _parse_chart(html, year)
    print(f"  🎵 {len(albums)} álbumes para {year}")

    if not albums:
        print(f"  ⚠  Sin álbumes — parser puede necesitar ajuste")
        try:
            tmp_path.write_text(html)
            print(f"     HTML guardado en {tmp_path} para inspección")
        except Exception:
            pass
        return []

    # Assign genres via genre-filtered chart POSTs
    if enrich_genres:
        genre_map = _parse_genre_map(html)
        if genre_map:
            # Build path → genres mapping from genre-specific charts
            path_genres: dict[str, list[str]] = {}
            print(f"  🏷  Géneros via {len(genre_map)} charts de género...")
            for genre_id, genre_name in genre_map.items():
                paths = _fetch_genre_chart(year, genre_id, session)
                for path in paths:
                    path_genres.setdefault(path, []).append(genre_name)
            # Assign to albums
            for album in albums:
                path = album["sputnik_url"].replace(SPUTNIK_BASE, "").rstrip("/")
                album["genres"] = path_genres.get(path, [])
            n_with = sum(1 for a in albums if a["genres"])
            print(f"  ✅ {n_with}/{len(albums)} álbumes con género asignado")
        else:
            print(f"  ⚠  Sin mapa de géneros en la página")

    cache_path.write_text(json.dumps(albums, ensure_ascii=False, indent=2))
    print(f"  💾 Caché: {cache_path}")
    return albums


# ── DB SYNC ───────────────────────────────────────────────────────────────────

def sputnik_sync_to_db(mh_conn: sqlite3.Connection,
                       year: int, albums: list[dict]) -> list[dict]:
    """Upsert one Sputnikmusic year chart into must_hear.db."""
    _ensure_col(mh_conn, "albums", "sputnikmusic_url")
    _ensure_col(mh_conn, "albums", "sputnik_rating", "REAL")

    slug    = f"sputnik_{year}"
    name    = f"Sputnikmusic Best Albums {year}"
    src_url = CHART_URL.format(year=year)
    ts      = int(time.time())

    row = mh_conn.execute("SELECT id FROM collections WHERE slug=?", (slug,)).fetchone()
    if row:
        coll_id = row[0]
        mh_conn.execute(
            "UPDATE collections SET name=?, source_url=?, last_updated=? WHERE id=?",
            (name, src_url, ts, coll_id)
        )
    else:
        mh_conn.execute(
            "INSERT INTO collections "
            "(name, slug, source_url, source_type, last_updated, added_timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (name, slug, src_url, "sputnikmusic", ts, ts)
        )
        coll_id = mh_conn.execute(
            "SELECT id FROM collections WHERE slug=?", (slug,)
        ).fetchone()[0]
    mh_conn.commit()

    result = []
    for album in albums:
        a_name  = album["artist"]
        title   = album["title"]
        cover   = album.get("cover_url", "")
        sp_url  = album.get("sputnik_url", "")
        rating  = album.get("rating", 0.0)
        genres  = album.get("genres", [])

        # Artist
        ar = mh_conn.execute("SELECT id FROM artists WHERE name=?", (a_name,)).fetchone()
        if ar:
            artist_id = ar[0]
        else:
            mh_conn.execute(
                "INSERT INTO artists (name, added_timestamp) VALUES (?,?)", (a_name, ts)
            )
            artist_id = mh_conn.execute(
                "SELECT id FROM artists WHERE name=?", (a_name,)
            ).fetchone()[0]

        # Album
        al = mh_conn.execute(
            "SELECT id FROM albums WHERE artist_id=? AND name=?", (artist_id, title)
        ).fetchone()
        if al:
            album_id = al[0]
            mh_conn.execute(
                "UPDATE albums SET "
                "year=COALESCE(year,?), "
                "cover_url=CASE WHEN (cover_url IS NULL OR cover_url='') AND ?!='' "
                "  THEN ? ELSE cover_url END, "
                "sputnikmusic_url=CASE WHEN "
                "  (sputnikmusic_url IS NULL OR sputnikmusic_url='') AND ?!='' "
                "  THEN ? ELSE sputnikmusic_url END, "
                "sputnik_rating=COALESCE(sputnik_rating,?), "
                "last_updated=? WHERE id=?",
                (year, cover, cover, sp_url, sp_url, rating, ts, album_id)
            )
        else:
            mh_conn.execute(
                "INSERT INTO albums "
                "(artist_id, name, year, cover_url, sputnikmusic_url, "
                " sputnik_rating, added_timestamp) "
                "VALUES (?,?,?,?,?,?,?)",
                (artist_id, title, year, cover, sp_url, rating, ts)
            )
            album_id = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?", (artist_id, title)
            ).fetchone()[0]

        # Genres (up to 6)
        for g_name in genres[:6]:
            g = mh_conn.execute("SELECT id FROM genres WHERE name=?", (g_name,)).fetchone()
            if g:
                g_id = g[0]
            else:
                mh_conn.execute(
                    "INSERT OR IGNORE INTO genres (name, source) VALUES (?,?)",
                    (g_name, "sputnikmusic")
                )
                g_id = mh_conn.execute(
                    "SELECT id FROM genres WHERE name=?", (g_name,)
                ).fetchone()[0]
            mh_conn.execute(
                "INSERT OR IGNORE INTO album_genres (album_id, genre_id, weight) "
                "VALUES (?,?,1.0)",
                (album_id, g_id)
            )

        # collection_albums
        if not mh_conn.execute(
            "SELECT id FROM collection_albums WHERE collection_id=? AND album_id=?",
            (coll_id, album_id)
        ).fetchone():
            mh_conn.execute(
                "INSERT INTO collection_albums (collection_id, album_id, rank) "
                "VALUES (?,?,?)",
                (coll_id, album_id, album.get("number", 0))
            )

        result.append(dict(album, id=album_id))

    mh_conn.execute(
        "UPDATE collections SET total_albums=?, last_updated=? WHERE id=?",
        (len(result), ts, coll_id)
    )
    mh_conn.commit()
    print(f"  💾 DB: {slug} → {len(result)} álbumes")
    return result


# ── HTML ──────────────────────────────────────────────────────────────────────

_CSS = """\
:root{--bg:#0d0d0d;--bg2:#1a1a1a;--bg3:#242424;--border:#333;--text:#e0e0e0;
      --muted:#777;--accent:#e8a020;--green:#4caf50}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
select,input{background:var(--bg3);color:var(--text);border:1px solid var(--border);
             border-radius:4px;padding:5px 10px;font-size:.88em;cursor:pointer}
/* header */
.hdr{position:sticky;top:0;z-index:200;background:var(--bg2);
     border-bottom:1px solid var(--border);padding:10px 16px;
     display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.hdr-title{font-size:1.15em;font-weight:700;color:var(--accent)}
.hdr-back{color:var(--muted);font-size:.85em}
.hdr-back:hover{color:var(--text)}
.hdr-stats{font-size:.82em;color:var(--muted);margin-left:auto}
.search-box{width:170px}
/* year sections */
.year-block{padding:18px 16px 0}
.year-heading{font-size:.95em;font-weight:700;color:var(--muted);letter-spacing:.06em;
              border-bottom:1px solid var(--border);padding-bottom:6px;margin-bottom:10px;
              cursor:pointer;user-select:none;display:flex;align-items:center;gap:6px}
.year-heading:hover{color:var(--text)}
.yr-arrow{font-size:.7em;flex-shrink:0;transition:transform .15s}
.album-grid{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
.album-grid.collapsed{display:none}
/* card */
.card{width:120px;cursor:pointer;position:relative;flex-shrink:0;border-radius:3px;overflow:hidden}
.card-img{width:120px;height:120px;object-fit:cover;background:var(--bg3);display:block}
.card-rating{position:absolute;top:3px;right:3px;background:rgba(0,0,0,.78);
             color:#fff;font-size:.72em;font-weight:700;padding:2px 5px;border-radius:2px}
.card-info{padding:4px 3px 0;font-size:.7em;line-height:1.3;
           background:linear-gradient(transparent,var(--bg))}
.card-artist{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-title{color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card.heard{outline:2px solid var(--green);outline-offset:1px}
.card.heard .card-img{filter:brightness(.62)}
.card.heard::after{content:'✓';position:absolute;top:3px;left:5px;color:var(--green);
                   font-size:1.05em;font-weight:900;text-shadow:0 0 5px #000}
/* panel */
.panel{position:fixed;right:0;top:0;height:100vh;width:350px;background:var(--bg2);
       border-left:1px solid var(--border);overflow-y:auto;z-index:300;
       transform:translateX(100%);transition:transform .18s ease}
.panel.open{transform:none}
.panel-close{position:sticky;top:0;background:var(--bg2);border-bottom:1px solid var(--border);
             padding:8px 12px;cursor:pointer;display:flex;justify-content:flex-end;
             font-size:1.2em;color:var(--muted)}
.panel-close:hover{color:var(--text)}
.panel-cover{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:var(--bg3)}
.panel-body{padding:12px}
.panel-title{font-size:1.05em;font-weight:700;margin-bottom:3px}
.panel-artist{color:var(--muted);font-size:.88em;margin-bottom:8px}
.panel-meta{font-size:.78em;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.panel-rating{color:var(--accent);font-weight:700}
.panel-genres{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:9px}
.panel-genre{background:var(--bg3);border:1px solid var(--border);border-radius:10px;
             padding:2px 8px;font-size:.72em}
.panel-heard{font-size:.78em;margin-bottom:9px}
.heard-label{color:var(--muted);margin-right:5px}
.heard-user{display:inline-block;background:rgba(76,175,80,.2);border:1px solid var(--green);
            color:var(--green);border-radius:3px;padding:1px 6px;font-size:.85em;margin:2px}
.panel-links{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.panel-link{font-size:.78em;background:var(--bg3);border:1px solid var(--border);
            border-radius:4px;padding:3px 9px}
.panel-desc{font-size:.78em;color:#999;line-height:1.5;max-height:180px;overflow-y:auto;
            border-top:1px solid var(--border);padding-top:8px;margin-top:6px}
.yt-wrap{margin-top:10px}
.yt-wrap iframe{width:100%;aspect-ratio:16/9;border:0;border-radius:4px}
/* index genre grid */
.genre-grid{display:flex;flex-wrap:wrap;gap:10px;padding:18px 16px}
.genre-card{background:var(--bg2);border:1px solid var(--border);border-radius:5px;
            padding:12px 14px;width:190px;transition:border-color .15s;color:inherit}
.genre-card:hover{border-color:var(--accent);text-decoration:none}
.genre-name{font-size:.97em;font-weight:700;color:var(--accent);margin-bottom:5px}
.genre-count{font-size:.78em;color:var(--muted);margin-bottom:7px}
.pbar{height:3px;background:var(--bg3);border-radius:2px;overflow:hidden;margin-bottom:4px}
.pfill{height:100%;background:var(--green);border-radius:2px;transition:width .3s}
.genre-pct{font-size:.72em;color:var(--muted)}
.summary{padding:12px 16px;font-size:.85em;color:var(--muted);
         border-bottom:1px solid var(--border)}\
"""


def render_sputnik_genre_html(
    genre: str,
    albums: list[dict],
    users: list[str],
    users_heard: dict[str, set],
    all_genres: list[str],
    collection_name: str,
    generated: str,
) -> str:
    """Render one genre page: albums grouped by year, user heard toggle."""

    records = []
    for a in sorted(albums, key=lambda x: (-x.get("year", 0), -x.get("rating", 0))):
        heard_by = [
            u for u in users
            if _check_heard(users_heard.get(u, set()), a["artist"], a["title"])
        ]
        records.append({
            "n":     a.get("number", 0),
            "year":  a.get("year", 0),
            "ar":    a.get("artist", ""),
            "ti":    a.get("title", ""),
            "cv":    a.get("cover_url", ""),
            "rt":    a.get("rating", 0.0),
            "sp":    a.get("sputnik_url", ""),
            "yt":    a.get("yt_id", ""),
            "gen":   a.get("genres", []),
            "hb":    heard_by,
            "da":    a.get("desc_lfm_album", ""),
            "dar":   a.get("desc_lfm_artist", ""),
        })

    albums_j = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    users_j  = json.dumps(users,   ensure_ascii=False)
    ge       = escape(genre)
    cn       = escape(collection_name)

    genre_opts = "".join(
        f'<option value="{_slug(g)}"{"" if g != genre else " selected"}>'
        f'{escape(g)}</option>'
        for g in sorted(all_genres)
    )
    user_opts = "".join(
        f'<option value="{escape(u)}">{escape(u)}</option>'
        for u in users
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{ge} — {cn}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="hdr">
  <a class="hdr-back" href="index.html">← {cn}</a>
  <span class="hdr-title">{ge}</span>
  <select onchange="location.href='genre_'+this.value+'.html'">{genre_opts}</select>
  <select id="usel" onchange="setUser(this.value)">
    <option value="">— Todos —</option>
    {user_opts}
  </select>
  <input class="search-box" id="srch" placeholder="Buscar..." oninput="render()">
  <span class="hdr-stats" id="stats"></span>
</div>

<div id="content"></div>

<div class="panel" id="panel">
  <div class="panel-close" onclick="closePanel()">✕</div>
  <img id="pcv" class="panel-cover" src="" alt="">
  <div class="panel-body">
    <div class="panel-title"  id="pti"></div>
    <div class="panel-artist" id="par"></div>
    <div class="panel-meta">
      <span id="pyr"></span>
      <span class="panel-rating" id="prt"></span>
    </div>
    <div class="panel-genres" id="pgen"></div>
    <div class="panel-heard"  id="phb"></div>
    <div class="panel-links"  id="plk"></div>
    <div id="pyt" class="yt-wrap"></div>
    <div class="panel-desc"   id="pds"></div>
  </div>
</div>

<script>
const A = {albums_j};
const U = {users_j};
let cu = localStorage.getItem('sp_user') || '';
let ci = null;

const obs = new IntersectionObserver(es => {{
  es.forEach(e => {{
    if (e.isIntersecting) {{
      const i = e.target;
      i.src = i.dataset.src;
      delete i.dataset.src;
      obs.unobserve(i);
    }}
  }});
}}, {{rootMargin: '200px'}});

const sel = document.getElementById('usel');
if (cu) sel.value = cu;

function setUser(u) {{
  cu = u;
  localStorage.setItem('sp_user', u);
  render();
  if (ci !== null) openPanel(ci);
}}

function heard(a) {{
  return cu ? a.hb.includes(cu) : false;
}}

function render() {{
  const q = (document.getElementById('srch').value || '').toLowerCase();
  const filtered = q
    ? A.filter(a => a.ar.toLowerCase().includes(q) || a.ti.toLowerCase().includes(q))
    : A;

  const byYear = {{}};
  filtered.forEach(a => {{
    (byYear[a.year] = byYear[a.year] || []).push(a);
  }});
  const years = Object.keys(byYear).map(Number).sort((a, b) => b - a);
  const latestYear = years[0];

  const hc = filtered.filter(heard).length;
  const pct = filtered.length ? Math.round(hc / filtered.length * 100) : 0;
  document.getElementById('stats').textContent =
    filtered.length + ' álbumes' +
    (cu ? ' · ' + hc + ' escuchados (' + pct + '%)' : '');

  document.getElementById('content').innerHTML = years.map(yr => {{
    const yAlb = byYear[yr];
    const yHc  = yAlb.filter(heard).length;
    const open = (yr === latestYear);
    const cards = yAlb.map(a => {{
      const idx = A.indexOf(a);
      const h   = heard(a);
      return '<div class="card' + (h ? ' heard' : '') + '" onclick="openPanel(' + idx + ')">' +
        (a.cv
          ? '<img class="card-img" data-src="' + a.cv + '" src="" alt="" referrerpolicy="no-referrer">'
          : '<div class="card-img"></div>') +
        (a.rt ? '<span class="card-rating">' + a.rt.toFixed(2) + '</span>' : '') +
        '<div class="card-info">' +
          '<div class="card-artist">' + a.ar + '</div>' +
          '<div class="card-title">'  + a.ti + '</div>' +
        '</div></div>';
    }}).join('');
    return '<div class="year-block">' +
      '<div class="year-heading" onclick="toggleYear(this)">' +
        '<span class="yr-arrow">' + (open ? '▾' : '▸') + '</span>' +
        yr +
        '<small style="font-weight:400;color:#555;margin-left:8px">(' +
          yAlb.length + ' álbumes' +
          (cu ? ' · ' + yHc + ' escuchados' : '') +
        ')</small></div>' +
      '<div class="album-grid' + (open ? '' : ' collapsed') + '">' + cards + '</div>' +
      '</div>';
  }}).join('') || '<p style="padding:40px;color:#555">Sin resultados.</p>';

  document.querySelectorAll('.card-img[data-src]').forEach(i => obs.observe(i));
}}

function toggleYear(heading) {{
  const grid  = heading.nextElementSibling;
  const arrow = heading.querySelector('.yr-arrow');
  const now   = grid.classList.toggle('collapsed');
  if (arrow) arrow.textContent = now ? '▸' : '▾';
}}

function openPanel(idx) {{
  ci = idx;
  const a = A[idx];
  document.getElementById('pcv').src = a.cv || '';
  document.getElementById('pti').textContent = a.ti;
  document.getElementById('par').textContent = a.ar;
  document.getElementById('pyr').textContent = a.year;
  document.getElementById('prt').textContent = a.rt ? '★ ' + a.rt.toFixed(2) : '';
  document.getElementById('pgen').innerHTML =
    (a.gen || []).map(g => '<span class="panel-genre">' + g + '</span>').join('');
  document.getElementById('phb').innerHTML = a.hb.length
    ? '<span class="heard-label">Escuchado por:</span>' +
      a.hb.map(u => '<span class="heard-user">' + u + '</span>').join('')
    : (cu ? '<span style="color:#555">No escuchado</span>' : '');
  const links = [];
  if (a.sp) links.push('<a class="panel-link" href="' + a.sp + '" target="_blank">Sputnikmusic</a>');
  document.getElementById('plk').innerHTML = links.join('');
  document.getElementById('pyt').innerHTML = a.yt
    ? '<iframe src="https://www.youtube.com/embed/' + a.yt + '" allowfullscreen></iframe>' : '';
  const desc = [a.da, a.dar].filter(Boolean).join('<hr style="margin:7px 0;border-color:#2a2a2a">');
  document.getElementById('pds').innerHTML = desc;
  document.getElementById('panel').classList.add('open');
}}

function closePanel() {{
  document.getElementById('panel').classList.remove('open');
  ci = null;
}}

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closePanel(); }});
render();
</script>
<!-- {generated} -->
</body>
</html>"""


def render_sputnik_index_html(
    genres_stats: list[dict],
    users: list[str],
    collection_name: str,
    years: list[int],
    total_albums: int,
    generated: str,
) -> str:
    """Index page: genre cards with per-user progress bars."""

    gj = json.dumps(genres_stats, ensure_ascii=False, separators=(",", ":"))
    uj = json.dumps(users,        ensure_ascii=False)
    cn = escape(collection_name)
    yr = f"{min(years)}–{max(years)}" if years else ""

    genre_opts = "".join(
        f'<option value="{d["slug"]}">{escape(d["name"])}</option>'
        for d in genres_stats
    )
    user_opts = "".join(
        f'<option value="{escape(u)}">{escape(u)}</option>'
        for u in users
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{cn}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="hdr">
  <a class="hdr-back" href="../index.html">← Must Hear</a>
  <span class="hdr-title">{cn}</span>
  <select id="usel" onchange="setUser(this.value)">
    <option value="">— Seleccionar usuario —</option>
    {user_opts}
  </select>
  <select onchange="if(this.value) location.href='genre_'+this.value+'.html'">
    <option value="">Ir a género...</option>
    {genre_opts}
  </select>
</div>
<div class="summary" id="summary">
  {escape(yr)} · {total_albums} álbumes · {len(genres_stats)} géneros
</div>
<div class="genre-grid" id="grid"></div>

<script>
const G = {gj};
const U = {uj};
let cu = localStorage.getItem('sp_user') || '';
const sel = document.getElementById('usel');
if (cu) sel.value = cu;

function setUser(u) {{
  cu = u;
  localStorage.setItem('sp_user', u);
  render();
}}

function render() {{
  const hdr = document.getElementById('summary');
  let total = 0, heard = 0;
  G.forEach(g => {{
    total += g.total;
    if (cu) heard += (g.heard[cu] || 0);
  }});
  const pct = total ? Math.round(heard / total * 100) : 0;
  hdr.textContent = '{escape(yr)} · ' + total + ' álbumes · {len(genres_stats)} géneros' +
    (cu ? ' · ' + heard + ' escuchados (' + pct + '%)' : '');

  document.getElementById('grid').innerHTML = G.map(g => {{
    const h   = cu ? (g.heard[cu] || 0) : 0;
    const pct = g.total ? Math.round(h / g.total * 100) : 0;
    return '<a class="genre-card" href="genre_' + g.slug + '.html">' +
      '<div class="genre-name">' + g.name + '</div>' +
      '<div class="genre-count">' + g.total + ' álbumes' +
        (cu ? ' · ' + h + ' escuchados' : '') + '</div>' +
      '<div class="pbar"><div class="pfill" style="width:' + (cu ? pct : 0) + '%"></div></div>' +
      '<div class="genre-pct">' + (cu ? pct + '%' : '') + '</div>' +
      '</a>';
  }}).join('');
}}

render();
</script>
<!-- {generated} -->
</body>
</html>"""


# ── MAIN RUNNER ───────────────────────────────────────────────────────────────

def run_sputnik(args, root_dir: Path) -> None:
    """
    Main entry point called from html_must_hear.py.

    args attributes used:
      sputnik_years     : list[int]            — years to process (required)
      must_hear_db      : str | None
      _sputnik_mh_conn  : sqlite3.Connection | None  — pre-opened connection
      scrobbles_db / db : str | None
      users             : list[str] | None
      force_scrape      : bool
      index_only        : bool
    """
    try:
        from html_must_hear import update_root_index
    except ImportError:
        update_root_index = None

    years     = sorted(set(int(y) for y in (getattr(args, "sputnik_years", None) or [])))
    force     = getattr(args, "force_scrape", False)
    idx_only  = getattr(args, "index_only",   False)
    coll_name = "Sputnikmusic Best Albums"

    if not years:
        print("❌ run_sputnik: no hay años en sputnik_years")
        return

    out_dir   = root_dir / "sputnik"
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    # DB connections
    mh_conn: sqlite3.Connection | None = getattr(args, "_sputnik_mh_conn", None)
    if mh_conn is None and getattr(args, "must_hear_db", None):
        p = Path(args.must_hear_db)
        if p.exists():
            mh_conn = sqlite3.connect(str(p))
            mh_conn.execute("PRAGMA journal_mode=WAL")

    scr_path = getattr(args, "scrobbles_db", None) or getattr(args, "db", None)
    scr_conn: sqlite3.Connection | None = None
    if scr_path and Path(scr_path).exists():
        scr_conn = sqlite3.connect(scr_path)

    users = _get_users(mh_conn, scr_conn, getattr(args, "users", None))
    print(f"👥 Usuarios: {', '.join(users) or '(ninguno)'}")

    users_heard = {u: _get_scrobbles(scr_conn, u) for u in users}

    # ── Load albums ───────────────────────────────────────────────────────────
    all_albums: list[dict] = []

    for year in years:
        cache_path = out_dir / f"sputnik_{year}_cache.json"

        if idx_only:
            if cache_path.exists():
                data = json.loads(cache_path.read_text())
                print(f"  📦 {year}: {len(data)} álbumes (index-only)")
                all_albums.extend(data)
            else:
                print(f"  ⚠  {year}: sin caché, saltando")
            continue

        # Try DB first (skip if force)
        loaded_from_db = False
        if mh_conn and not force:
            try:
                from html_must_hear import mh_load_collection
                data = mh_load_collection(mh_conn, f"sputnik_{year}")
                if data:
                    print(f"  📦 {year}: {len(data)} álbumes desde must_hear.db")
                    all_albums.extend(data)
                    loaded_from_db = True
            except Exception:
                pass

        if loaded_from_db:
            continue

        data = sputnik_fetch_year(year, cache_path, force=force)
        if data and mh_conn:
            data = sputnik_sync_to_db(mh_conn, year, data)
        all_albums.extend(data)

    # Also load any other sputnik years already in DB/cache (not in this run)
    if mh_conn:
        existing = mh_conn.execute(
            "SELECT slug FROM collections WHERE slug LIKE 'sputnik_%'"
        ).fetchall()
        extra_years = sorted(
            int(r[0].replace("sputnik_", ""))
            for r in existing
            if r[0].replace("sputnik_", "").isdigit()
            and int(r[0].replace("sputnik_", "")) not in years
        )
        if extra_years:
            print(f"  📚 Cargando años adicionales desde DB: {extra_years}")
            for yr in extra_years:
                try:
                    from html_must_hear import mh_load_collection
                    data = mh_load_collection(mh_conn, f"sputnik_{yr}")
                    if data:
                        all_albums.extend(data)
                except Exception:
                    # Fallback to cache file
                    cp = out_dir / f"sputnik_{yr}_cache.json"
                    if cp.exists():
                        all_albums.extend(json.loads(cp.read_text()))
    else:
        # No DB: load from cache files for years not already loaded
        loaded_years = {a.get("year") for a in all_albums}
        for cp in sorted(out_dir.glob("sputnik_*_cache.json")):
            m = re.search(r"sputnik_(\d+)_cache", cp.name)
            if m and int(m.group(1)) not in loaded_years:
                try:
                    all_albums.extend(json.loads(cp.read_text()))
                except Exception:
                    pass

    if not all_albums:
        print("⚠  Sin álbumes — nada que generar")
        if scr_conn: scr_conn.close()
        return

    # ── Build genre index ─────────────────────────────────────────────────────
    genre_albums: dict[str, list[dict]] = {}
    for a in all_albums:
        for g in (a.get("genres") or []):
            genre_albums.setdefault(g, []).append(a)

    if not genre_albums:
        print("⚠  Sin géneros — asignando categoría 'Sin género'")
        genre_albums["Sin género"] = all_albums

    all_genre_names = sorted(genre_albums, key=lambda g: -len(genre_albums[g]))

    genres_stats = []
    for g_name in all_genre_names:
        g_albs = genre_albums[g_name]
        heard_per_user = {
            u: sum(
                1 for a in g_albs
                if _check_heard(users_heard.get(u, set()), a["artist"], a["title"])
            )
            for u in users
        }
        genres_stats.append({
            "name":  g_name,
            "slug":  _slug(g_name),
            "total": len(g_albs),
            "heard": heard_per_user,
        })

    # ── Generate genre pages ──────────────────────────────────────────────────
    print(f"\n🎨 Generando {len(genre_albums)} páginas de género...")
    for g_name, g_albs in genre_albums.items():
        html = render_sputnik_genre_html(
            genre=g_name,
            albums=g_albs,
            users=users,
            users_heard=users_heard,
            all_genres=all_genre_names,
            collection_name=coll_name,
            generated=generated,
        )
        p = out_dir / f"genre_{_slug(g_name)}.html"
        p.write_text(html, encoding="utf-8")
        print(f"  📄 {p.name} ({len(g_albs)} álbumes)")

    # ── Generate index page ───────────────────────────────────────────────────
    index_html = render_sputnik_index_html(
        genres_stats=genres_stats,
        users=users,
        collection_name=coll_name,
        years=years,
        total_albums=len(all_albums),
        generated=generated,
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"\n📋 {out_dir / 'index.html'}")

    # ── Update root index ─────────────────────────────────────────────────────
    if update_root_index:
        users_index = []
        for u in users:
            sc    = users_heard.get(u, set())
            total = len(all_albums)
            heard = sum(
                1 for a in all_albums
                if _check_heard(sc, a["artist"], a["title"])
            )
            pct = round(heard / total * 100, 1) if total else 0
            users_index.append({
                "user": u, "file": "index.html",
                "heard": heard, "total": total, "pct": pct,
            })
        try:
            update_root_index(root_dir, coll_name, "sputnik", users_index, generated)
        except Exception as e:
            print(f"  ⚠  update_root_index: {e}")

    if scr_conn: scr_conn.close()
    print("\n✅ Sputnikmusic done")


# ── STANDALONE ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sputnikmusic Best Albums → Must Hear HTML Generator"
    )
    parser.add_argument(
        "--years", dest="sputnik_years", nargs="+", type=int, required=True,
        metavar="YEAR", help="Años a scrapear, ej: --years 2020 2021 2022"
    )
    parser.add_argument("--must-hear-db", dest="must_hear_db", default=None,
                        help="Ruta a must_hear.db")
    parser.add_argument("--scrobbles-db", dest="scrobbles_db", default=None)
    parser.add_argument("--db",           dest="db",           default=None,
                        help="[alias] --scrobbles-db")
    parser.add_argument("--out",    default="docs/must_hear",
                        help="Directorio raíz de salida (default: docs/must_hear)")
    parser.add_argument("--users",  nargs="*",
                        help="Usuarios específicos (por defecto todos)")
    parser.add_argument("--force-scrape", dest="force_scrape", action="store_true",
                        help="Re-scrapear aunque haya caché")
    parser.add_argument("--index-only",   dest="index_only",   action="store_true",
                        help="Regenerar HTML sin scrapear (usa caché existente)")
    args = parser.parse_args()
    args._sputnik_mh_conn = None

    root_dir = Path(args.out)
    root_dir.mkdir(parents=True, exist_ok=True)

    run_sputnik(args, root_dir)


if __name__ == "__main__":
    main()

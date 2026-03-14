#!/usr/bin/env python3
"""
RateYourMusic List Scraper & HTML Generator

Scrapes RateYourMusic user lists (bypassing Cloudflare via headful Chromium)
and generates HTML grids with per-user heard status.

Requires:
    playwright + system Chromium:
        playwright install  (only needed once to set up drivers)
    or use the system Chromium directly (auto-detected).

First run opens a visible browser window; Cloudflare state is saved in
~/.rym_playwright_state/ so subsequent runs auto-pass the challenge.

Standalone:
    python3 rym_must_hear.py --url "https://rateyourmusic.com/list/user/list-name/"
                              --must-hear-db db/must_hear.db
                              [--scrobbles-db db/rym_lastfm.db]
                              [--out docs/must_hear] [--name "My List"] [--slug my_list]

From html_must_hear.py:
    from tools.must_hear.rym_must_hear import run_rym
    run_rym(args, root_dir)
"""

import json, re, time, sqlite3, os, argparse
from html import unescape
from pathlib import Path
from datetime import datetime

# ── CONFIG ─────────────────────────────────────────────────────────────────────

RYM_BASE  = "https://rateyourmusic.com"
STATE_DIR = Path.home() / ".rym_playwright_state"

COVER_PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20"
    "width=%22250%22%20height=%22250%22%20viewBox=%220%200%20250%20250%22%3E"
    "%3Crect%20width=%22250%22%20height=%22250%22%20fill=%22%23111%22/%3E"
    "%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%2260%22%20fill=%22none%22"
    "%20stroke=%22%23333%22%20stroke-width=%222%22/%3E%3C/svg%3E"
)


# ── HELPERS ─────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())


def _cover_hd(url: str) -> str:
    """Upgrade 150px RYM cover to 600px."""
    if not url:
        return ""
    url = url.lstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return re.sub(r"/i/\d+/", "/i/600/", url)


def _slug_from_url(url: str) -> str:
    """Derive a slug from a RYM list URL."""
    m = re.search(r"/list/[^/]+/([^/]+)/?$", url.rstrip("/"))
    if m:
        return re.sub(r"[^a-z0-9]+", "_", m.group(1).lower()).strip("_")
    return re.sub(r"[^a-z0-9]+", "_", url.lower())[-40:].strip("_")


def _find_chromium() -> str | None:
    """Find a usable Chromium/Chrome binary."""
    for binary in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        path = __import__("shutil").which(binary)
        if path:
            return path
    return None


# ── PLAYWRIGHT SCRAPER ─────────────────────────────────────────────────────────

def _wait_for_page(page, url: str, timeout_s: int = 120) -> str:
    """Navigate to url on an existing Playwright page, wait for CF, return HTML."""
    print(f"  🌐 {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    except Exception:
        pass  # may time out during CF redirect — we poll title instead

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            title = page.title()
        except Exception:
            time.sleep(0.5)
            continue
        low = title.lower()
        if "moment" not in low and "momento" not in low and "security check" not in low:
            print(f"  ✅ {title}")
            break
        print(f"  ⏳ CF activo ({title!r}), esperando... ({int(deadline - time.time())}s restantes)")
        time.sleep(3)
    else:
        try:
            title = page.title()
        except Exception:
            title = "?"
        print(f"  ⚠  Timeout ({title!r}) — CF no resolvió")

    try:
        return page.content()
    except Exception as e:
        print(f"  ❌ No se pudo obtener HTML: {e}")
        return ""


def _get_page_html(url: str, state_dir: Path, timeout_s: int = 120) -> str:
    """
    Fetch the HTML of a single RYM page using a new Playwright browser session.
    Use rym_fetch_list (which keeps one browser open) for multi-page scraping.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    chromium = _find_chromium()
    extra_kwargs = {"executable_path": chromium} if chromium else {}
    if chromium:
        print(f"  🔍 Chromium: {chromium}")

    html = ""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(state_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            **extra_kwargs,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        html = _wait_for_page(page, url, timeout_s)
        ctx.close()

    return html


# ── PARSER ──────────────────────────────────────────────────────────────────────

def _parse_rym_page(html: str, base_rank: int = 1) -> list[dict]:
    """
    Parse one RYM list page and return album dicts.

    RYM lists use comment markers to delimit each item:
      <!-- @@_list_item_N -->
      <tr ...>
        <td class="list_art"><img data-src="..."></td>
        <td class="main_entry">
          <h2><a class="list_artist">Artist</a></h2>
          <h3><a class="list_album">Title</a><span class="rel_date">(Year)</span></h3>
        </td>
      </tr>

    We split by the comment markers instead of by <tr> tags to avoid issues
    with deeply nested tables (review content) that break regex-based table extraction.
    Items without list_album (e.g. section headers) are silently skipped.
    """
    albums = []
    rank   = base_rank

    # Split by item markers — each section is one list entry (album or header)
    sections = re.split(r'<!-- @@_list_item_\d+ -->', html)

    for section in sections[1:]:  # first slice is preamble before any item
        # Skip non-album rows (section headers, generic items)
        if 'class="list_album"' not in section:
            continue

        # Artist
        artist_m = re.search(r'class="list_artist"[^>]*>([^<]+)<', section)
        if not artist_m:
            continue
        artist = unescape(artist_m.group(1).strip())

        # Title
        title_m = re.search(r'class="list_album"[^>]*>([^<]+)<', section)
        if not title_m:
            continue
        title = unescape(title_m.group(1).strip())

        # Year — from <span class="rel_date">(YYYY)</span>
        year_m = re.search(r'class="rel_date"[^>]*>\s*\((\d{4})\)', section)
        year   = int(year_m.group(1)) if year_m else None

        # RYM URL — from the album link
        rym_m  = re.search(r'href="(/release/album/[^"]+)"[^>]*class="list_album"', section)
        if not rym_m:
            rym_m = re.search(r'class="list_album"[^>]*href="(/release/album/[^"]+)"', section)
        rym_path = rym_m.group(1) if rym_m else ""
        rym_url  = f"{RYM_BASE}{rym_path}" if rym_path else ""

        # Cover — data-src from list_art td (take only the FIRST match to avoid nested table images)
        art_m  = re.search(r'<td class="list_art">(.*?)</td>', section, re.DOTALL)
        cover  = ""
        if art_m:
            img_m = re.search(r'data-src="([^"]+)"', art_m.group(1))
            if not img_m:
                img_m = re.search(r'src="([^"]+)"', art_m.group(1))
            if img_m and "blank.png" not in img_m.group(1):
                cover = _cover_hd(img_m.group(1))

        albums.append({
            "number":   rank,
            "artist":   artist,
            "title":    title,
            "year":     year,
            "mbid":     "",
            "rym":      rym_url,
            "cover_url": cover,
            # enrichment placeholders
            "desc_lfm_album":  "",
            "desc_lfm_artist": "",
            "desc_mb_album":   "",
            "desc_mb_artist":  "",
            "yt_id":           "",
            "genres":          [],
        })
        rank += 1

    return albums


def _get_page_count(html: str) -> int:
    """Detect total number of pages from the navigation links."""
    # Links like href="/list/user/name/3/"
    nums = re.findall(r'href="[^"]+/(\d+)/"', html)
    nums = [int(n) for n in nums if n.isdigit()]
    return max(nums, default=1)


def rym_fetch_list(url: str, state_dir: Path,
                   cache_path: Path | None = None,
                   force: bool = False) -> list[dict]:
    """
    Fetch all pages of a RYM list and return combined album list.
    All pages are fetched within a single browser session to avoid repeated
    Cloudflare challenges. Results are cached to cache_path as JSON.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    url = url.rstrip("/") + "/"

    if cache_path and cache_path.exists() and not force:
        data = json.loads(cache_path.read_text())
        if data:
            print(f"  📦 RYM caché: {cache_path} ({len(data)} álbumes)")
            return data
        print("  ⚠  Caché vacío, re-scrapeando...")

    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    chromium = _find_chromium()
    extra_kwargs = {"executable_path": chromium} if chromium else {}
    if chromium:
        print(f"  🔍 Chromium: {chromium}")

    albums = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(state_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            **extra_kwargs,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # ── Page 1 ──
        html1 = _wait_for_page(page, url)
        if not html1:
            ctx.close()
            return []

        albums      = _parse_rym_page(html1, base_rank=1)
        total_pages = _get_page_count(html1)

        if total_pages > 1:
            print(f"  📄 {total_pages} páginas detectadas")

        # ── Remaining pages ──
        for page_n in range(2, total_pages + 1):
            time.sleep(1.5)
            page_url = f"{url}{page_n}/"
            html_n   = _wait_for_page(page, page_url)
            if not html_n:
                print(f"  ⚠  Página {page_n} vacía, deteniendo")
                break
            base = len(albums) + 1
            more = _parse_rym_page(html_n, base_rank=base)
            if not more:
                print(f"  ⚠  Página {page_n}: sin álbumes, deteniendo")
                break
            albums.extend(more)

        ctx.close()

    print(f"  🎵 {len(albums)} álbumes totales en la lista")

    if cache_path:
        cache_path.write_text(json.dumps(albums, ensure_ascii=False, indent=2))
        print(f"  💾 Caché guardado: {cache_path}")

    return albums


# ── DB INTEGRATION ─────────────────────────────────────────────────────────────

def rym_sync_to_db(mh_conn: sqlite3.Connection,
                   slug: str, name: str, source_url: str,
                   albums: list[dict]) -> list[dict]:
    """
    Upsert a RYM list into must_hear.db.
    Reuses mh_sync_mb_collection logic but tags source_type as 'rateyourmusic'.
    Returns albums with 'id' field populated.
    """
    ts = int(time.time())

    # ── Collection ──
    row = mh_conn.execute("SELECT id FROM collections WHERE slug=?", (slug,)).fetchone()
    if row:
        coll_id = row[0]
        mh_conn.execute(
            "UPDATE collections SET name=?, source_url=?, source_type=?, last_updated=? WHERE id=?",
            (name, source_url, "rateyourmusic", ts, coll_id)
        )
        print(f"  📋 Colección existente '{slug}' (id={coll_id}) — actualizando")
    else:
        mh_conn.execute(
            "INSERT INTO collections (name, slug, source_url, source_type, last_updated, added_timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (name, slug, source_url, "rateyourmusic", ts, ts)
        )
        coll_id = mh_conn.execute("SELECT id FROM collections WHERE slug=?", (slug,)).fetchone()[0]
        print(f"  📋 Colección nueva '{slug}' (id={coll_id})")
    mh_conn.commit()

    # ── Albums ──
    result = []
    for album in albums:
        artist_name = album.get("artist", "")
        title       = album.get("title", "")
        mbid        = album.get("mbid") or None
        year        = album.get("year")
        rank        = album.get("number", 0)
        cover_url   = album.get("cover_url", "")
        rym_url     = album.get("rym", "")

        # Artist
        artist_row = mh_conn.execute("SELECT id FROM artists WHERE name=?", (artist_name,)).fetchone()
        if artist_row:
            artist_id = artist_row[0]
        else:
            mh_conn.execute("INSERT INTO artists (name, added_timestamp) VALUES (?,?)", (artist_name, ts))
            artist_id = mh_conn.execute("SELECT id FROM artists WHERE name=?", (artist_name,)).fetchone()[0]

        # Album
        album_row = None
        if mbid:
            album_row = mh_conn.execute(
                "SELECT id FROM albums WHERE release_group_mbid=?", (mbid,)
            ).fetchone()
        if not album_row:
            album_row = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?", (artist_id, title)
            ).fetchone()

        if album_row:
            album_id = album_row[0]
            mh_conn.execute(
                "UPDATE albums SET "
                "release_group_mbid = CASE WHEN release_group_mbid IS NULL THEN ? ELSE release_group_mbid END, "
                "year = COALESCE(year, ?), "
                "cover_url = CASE WHEN (cover_url IS NULL OR cover_url = '') AND ? != '' THEN ? ELSE cover_url END, "
                "rateyourmusic_url = CASE WHEN (rateyourmusic_url IS NULL OR rateyourmusic_url = '') AND ? != '' THEN ? ELSE rateyourmusic_url END, "
                "last_updated = ? WHERE id=?",
                (mbid, year, cover_url, cover_url, rym_url, rym_url, ts, album_id)
            )
        else:
            mh_conn.execute(
                "INSERT INTO albums (artist_id, name, year, release_group_mbid, cover_url, rateyourmusic_url, added_timestamp) "
                "VALUES (?,?,?,?,?,?,?)",
                (artist_id, title, year, mbid, cover_url, rym_url or None, ts)
            )
            album_id = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?", (artist_id, title)
            ).fetchone()[0]

        # collection_albums
        ca_row = mh_conn.execute(
            "SELECT id FROM collection_albums WHERE collection_id=? AND album_id=?",
            (coll_id, album_id)
        ).fetchone()
        if not ca_row:
            mh_conn.execute(
                "INSERT INTO collection_albums (collection_id, album_id, rank) VALUES (?,?,?)",
                (coll_id, album_id, rank)
            )

        merged = dict(album)
        merged["id"] = album_id
        result.append(merged)

    mh_conn.execute(
        "UPDATE collections SET total_albums=?, last_updated=? WHERE id=?",
        (len(result), ts, coll_id)
    )
    mh_conn.commit()
    print(f"  💾 DB: '{slug}' → {len(result)} álbumes guardados")
    return result


# ── MAIN RUNNER ─────────────────────────────────────────────────────────────────

def run_rym(args, root_dir: Path) -> None:
    """
    Main entry point for a single RYM list.
    args attributes:
      - rym_url            : str — RateYourMusic list URL (required)
      - name               : str — display name (auto-detected if empty)
      - slug               : str — output subdirectory (auto-derived if None)
      - collection         : str | None — group subdirectory
      - must_hear_db       : str | None — path to must_hear.db
      - _rym_mh_conn       : sqlite3.Connection | None
      - scrobbles_db / db  : str | None — scrobbles DB
      - users              : list[str] | None
      - index_only         : bool — skip scraping, just regenerate HTML
      - force_scrape       : bool — ignore cache
    """
    from html_must_hear import (
        mh_get_users, mh_get_user_albums, mh_load_collection,
        check_heard, mh_album_to_json, render_collection_index_html,
        render_user_html, update_root_index, update_collection_group_index,
        mh_populate_user_heard,
    )

    rym_url    = getattr(args, "rym_url",      None) or getattr(args, "url", None)
    name       = getattr(args, "name",         "") or ""
    slug       = getattr(args, "slug",         None)
    collection = getattr(args, "collection",   None)
    index_only = getattr(args, "index_only",   False)
    force      = getattr(args, "force_scrape", False)

    if not rym_url:
        print("❌ --url requerido (URL de lista RateYourMusic)")
        return

    rym_url = rym_url.rstrip("/") + "/"

    # ── Slug & output dir ──────────────────────────────────────────────────────
    if not slug:
        slug = _slug_from_url(rym_url)

    if collection:
        coll_slug = re.sub(r"[^a-z0-9]+", "_", collection.lower()).strip("_")
        out_dir   = root_dir / coll_slug / slug
    else:
        coll_slug = None
        out_dir   = root_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = out_dir / "rym_list_cache.json"
    generated  = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── DB connections ─────────────────────────────────────────────────────────
    mh_conn: sqlite3.Connection | None = getattr(args, "_rym_mh_conn", None)
    if mh_conn is None and getattr(args, "must_hear_db", None):
        p = Path(args.must_hear_db)
        if p.exists():
            mh_conn = sqlite3.connect(str(p))
            mh_conn.execute("PRAGMA journal_mode=WAL")

    scr_path = getattr(args, "scrobbles_db", None) or getattr(args, "db", None)

    # ── Users ──────────────────────────────────────────────────────────────────
    if mh_conn:
        users = getattr(args, "users", None) or mh_get_users(mh_conn)
    elif scr_path:
        import sqlite3 as _sq
        with _sq.connect(scr_path) as _c:
            rows  = _c.execute("SELECT DISTINCT user FROM scrobbles ORDER BY user").fetchall()
            users = getattr(args, "users", None) or [r[0] for r in rows]
    else:
        users = getattr(args, "users", None) or []
    print(f"👥 Usuarios: {', '.join(users) or '(ninguno)'}")

    # ── Scrobbles ──────────────────────────────────────────────────────────────
    if scr_path:
        import sqlite3 as _sq
        _scr = _sq.connect(scr_path)
        users_heard = {u: mh_get_user_albums(_scr, u) for u in users}
        _scr.close()
    elif mh_conn:
        # Read from user_heard table in must_hear.db
        users_heard = {}
        for u in users:
            rows = mh_conn.execute(
                "SELECT a.name, ar.name FROM user_heard uh "
                "JOIN albums a ON a.id=uh.album_id "
                "JOIN artists ar ON ar.id=a.artist_id "
                "WHERE uh.username=?", (u,)
            ).fetchall()
            users_heard[u] = {(_norm(ar), _norm(al)) for al, ar in rows}
    else:
        users_heard = {u: set() for u in users}

    # ── Albums ─────────────────────────────────────────────────────────────────
    albums_from_db = False
    if mh_conn and not force:
        albums = mh_load_collection(mh_conn, slug)
        if albums:
            albums_from_db = True
            if not name:
                row = mh_conn.execute(
                    "SELECT name FROM collections WHERE slug=?", (slug,)
                ).fetchone()
                if row:
                    name = row[0]
            print(f"  📦 {len(albums)} álbumes desde must_hear.db ('{slug}')")

    if not albums_from_db:
        if index_only:
            if cache_path.exists():
                albums = json.loads(cache_path.read_text())
                print(f"  📦 {len(albums)} álbumes desde caché ({cache_path})")
            else:
                print(f"  ❌ --index-only pero no existe caché: {cache_path}")
                return
        else:
            albums = rym_fetch_list(rym_url, STATE_DIR, cache_path, force=force)
            if not albums:
                print("  ❌ No se obtuvieron álbumes")
                return

        # Auto-detect name from page if not given
        if not name:
            if cache_path.exists():
                pass  # already set or will use slug
            name = slug.replace("_", " ").title()

        # Save to DB
        if mh_conn and not index_only:
            albums = rym_sync_to_db(mh_conn, slug, name, rym_url, albums)
            albums_from_db = True

    if not name:
        name = slug.replace("_", " ").title()

    # ── Per-user HTML ──────────────────────────────────────────────────────────
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)

    users_index = []
    for user in users:
        user_scrobbles = users_heard.get(user, set())
        albums_data    = []
        heard_ids      = []

        for album in albums:
            heard = check_heard(user_scrobbles, album)
            if albums_from_db:
                jdata = mh_album_to_json(album, heard)
            else:
                jdata = {
                    "artist":         album.get("artist", ""),
                    "title":          album.get("title", ""),
                    "year":           album.get("year"),
                    "mbid":           album.get("mbid", ""),
                    "cover_url":      album.get("cover_url", "") or COVER_PLACEHOLDER,
                    "rym":            album.get("rym", ""),
                    "yt_id":          album.get("yt_id", ""),
                    "genres":         album.get("genres", []),
                    "desc_lfm_album":  album.get("desc_lfm_album", ""),
                    "desc_lfm_artist": album.get("desc_lfm_artist", ""),
                    "desc_mb_album":   album.get("desc_mb_album", ""),
                    "desc_mb_artist":  album.get("desc_mb_artist", ""),
                    "heard":          heard,
                    "number":         album.get("number", 0),
                }
            if heard and album.get("id"):
                heard_ids.append((album["id"], 0))
            albums_data.append(jdata)

        heard_count = sum(1 for a in albums_data if a["heard"])
        pct         = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0
        safe_user   = re.sub(r"[^a-z0-9]", "_", user.lower())
        json_fname  = f"{safe_user}.json"
        fname       = f"user_{safe_user}.html"

        (data_dir / json_fname).write_text(
            json.dumps(albums_data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8"
        )
        (out_dir / fname).write_text(
            render_user_html(user, albums_data, name, data_file=f"data/{json_fname}"),
            encoding="utf-8"
        )

        if heard_ids and mh_conn and not index_only:
            try:
                scr_conn = sqlite3.connect(scr_path) if scr_path else None
                mh_populate_user_heard(mh_conn, scr_conn, user, heard_ids)
                if scr_conn:
                    scr_conn.close()
            except Exception:
                pass

        users_index.append({
            "user": user, "file": fname,
            "heard": heard_count, "total": len(albums_data), "pct": pct,
        })
        print(f"   {user}: {heard_count}/{len(albums_data)} ({pct}%)")

    users_index.sort(key=lambda u: u["pct"], reverse=True)

    # ── Collection index ───────────────────────────────────────────────────────
    (out_dir / "index.html").write_text(
        render_collection_index_html(users_index, name, generated),
        encoding="utf-8"
    )
    print(f"  📋 {out_dir / 'index.html'}")

    # ── Root index update ──────────────────────────────────────────────────────
    if coll_slug:
        update_collection_group_index(
            root_dir, collection, coll_slug, name, slug, users_index, generated
        )
    else:
        update_root_index(root_dir, name, slug, users_index, generated)


# ── STANDALONE ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RateYourMusic List → Must Hear HTML Generator"
    )
    parser.add_argument("--url",          required=True,
                        help="URL de lista RateYourMusic (ej: https://rateyourmusic.com/list/user/list-name/)")
    parser.add_argument("--must-hear-db", dest="must_hear_db", default=None,
                        help="Ruta a must_hear.db")
    parser.add_argument("--scrobbles-db", dest="scrobbles_db", default=None)
    parser.add_argument("--db",           dest="db",           default=None,
                        help="[alias] --scrobbles-db")
    parser.add_argument("--out",          default="docs/must_hear",
                        help="Directorio raíz de salida")
    parser.add_argument("--name",         default="",
                        help="Nombre de la colección (auto-detectado si no se da)")
    parser.add_argument("--slug",         default=None,
                        help="Subdirectorio de salida (auto si no se da)")
    parser.add_argument("--collection",   default=None,
                        help="Agrupa bajo docs/must_hear/<collection>/<slug>/")
    parser.add_argument("--users",        nargs="*",
                        help="Usuarios específicos (por defecto todos)")
    parser.add_argument("--index-only",   dest="index_only", action="store_true",
                        help="Solo regenerar HTML desde caché, sin scrapear")
    parser.add_argument("--force",        dest="force_scrape", action="store_true",
                        help="Re-scrapear aunque haya caché")
    args = parser.parse_args()
    args.rym_url = args.url

    root_dir = Path(args.out)
    root_dir.mkdir(parents=True, exist_ok=True)

    if args.must_hear_db:
        p = Path(args.must_hear_db)
        if not p.exists():
            print(f"❌ --must-hear-db no existe: {p}")
            return
        args._rym_mh_conn = sqlite3.connect(str(p))
        args._rym_mh_conn.execute("PRAGMA journal_mode=WAL")
    else:
        args._rym_mh_conn = None

    run_rym(args, root_dir)

    if args._rym_mh_conn:
        args._rym_mh_conn.close()


if __name__ == "__main__":
    main()

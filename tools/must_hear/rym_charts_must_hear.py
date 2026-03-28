#!/usr/bin/env python3
"""
RateYourMusic Charts Scraper & HTML Generator

Scrapes RateYourMusic chart pages, e.g.:
  https://rateyourmusic.com/charts/top/album/all-time/g:ambient-americana/
  https://rateyourmusic.com/charts/top/album/2023/
  https://rateyourmusic.com/charts/top/album/all-time/

Uses the same Playwright/Cloudflare setup as rym_must_hear.py.
Results are cached as JSON in the output directory.

Standalone:
    python3 tools/must_hear/rym_charts_must_hear.py
        --url "https://rateyourmusic.com/charts/top/album/all-time/g:ambient-americana/"
        --must-hear-db db/must_hear_rym_new.db
        [--scrobbles-db db/lastfm_cache_rym_new_normalized.db]
        [--limit 100] [--out docs/must_hear]
        [--name "Ambient Americana Top"] [--slug rym_chart_ambient_americana]

From html_must_hear.py:
    from tools.must_hear.rym_charts_must_hear import run_rym_chart
    run_rym_chart(args, root_dir)
"""

import json, re, time, sqlite3, argparse
from html import unescape
from pathlib import Path
from datetime import datetime

# ── reuse helpers from rym_must_hear ──────────────────────────────────────────
from tools.must_hear.rym_must_hear import (
    _cover_hd, _norm, _find_chromium, _wait_for_page,
    rym_sync_to_db, STATE_DIR, RYM_BASE, COVER_PLACEHOLDER,
)

# ── SLUG / NAME HELPERS ───────────────────────────────────────────────────────

def _slug_from_chart_url(url: str) -> str:
    """
    Derive a filesystem-safe slug from a RYM chart URL.

    Examples:
      .../charts/top/album/all-time/g:ambient-americana/ → rym_chart_all_time_ambient_americana
      .../charts/top/album/2023/                         → rym_chart_2023
      .../charts/top/album/all-time/                     → rym_chart_all_time
    """
    url = url.rstrip("/")
    # Strip scheme and host
    path = re.sub(r"^https?://[^/]+", "", url)
    # Take everything after /charts/top/album/
    m = re.search(r"/charts/top/album/(.+)$", path)
    if not m:
        return re.sub(r"[^a-z0-9]+", "_", url.lower())[-50:].strip("_")
    parts = m.group(1).strip("/").split("/")
    cleaned = []
    for part in parts:
        # g:ambient-americana → ambient_americana
        part = re.sub(r"^g:", "", part)
        part = re.sub(r"[^a-z0-9]+", "_", part.lower()).strip("_")
        if part:
            cleaned.append(part)
    slug = "rym_chart_" + "_".join(cleaned)
    return re.sub(r"_+", "_", slug).strip("_")


def _name_from_chart_url(url: str) -> str:
    """
    Derive a human-readable name from a RYM chart URL.

    Examples:
      .../charts/top/album/all-time/g:ambient-americana/ → RYM Top — All Time — Ambient Americana
      .../charts/top/album/2023/                         → RYM Top — 2023
    """
    url = url.rstrip("/")
    path = re.sub(r"^https?://[^/]+", "", url)
    m = re.search(r"/charts/top/album/(.+)$", path)
    if not m:
        return "RYM Chart"
    parts = m.group(1).strip("/").split("/")
    labels = []
    for part in parts:
        # g:ambient-americana → Ambient Americana
        part = re.sub(r"^g:", "", part)
        # Keep trailing 's' lowercase for decades like "2020s"
        words = part.replace("-", " ").split()
        words = [w.capitalize() if not re.match(r"^\d{4}s$", w) else w for w in words]
        part  = " ".join(words)
        if part:
            labels.append(part)
    return "RYM Top — " + " — ".join(labels)


# ── PARSER ────────────────────────────────────────────────────────────────────

def _parse_rym_chart_page(html: str, base_rank: int = 1, limit: int = 0) -> list[dict]:
    """
    Parse one RYM chart page and return album dicts.

    Actual RYM chart page structure (confirmed from live HTML, 2024):

      <div id="page_charts_section_charts_item_XXXXXX"
           class="page_charts_section_charts_item object_release">

        <!-- cover -->
        <a class="page_charts_section_charts_item_image_link"
           href="/release/album/ARTIST/SLUG/">
          <img src="//e.snmc.io/i/300/s/HASH/ID/..." alt="Artist - Title, Cover art">
        </a>

        <!-- info block -->
        <div class="page_charts_section_charts_item_info">
          <div class="page_charts_section_charts_item_title">
            <a class="page_charts_section_charts_item_link release"
               href="/release/album/ARTIST/SLUG/">
              <span class="ui_name_locale_original">Title</span>
            </a>
          </div>
          <div class="page_charts_section_charts_item_credited_text">
            <a class="artist" href="/artist/ARTIST-SLUG">
              <span class="ui_name_locale">Artist Name</span>
            </a>
          </div>
          <div class="page_charts_section_charts_item_date">
            <span>YEAR</span>
          </div>
          <a class="genre comma_separated" href="/genre/...">Genre</a>
          <span class="page_charts_section_charts_item_details_average_num">3.80</span>
        </div>
      </div>

    Items appear in chart order; rank = base_rank + index.
    """
    albums: list[dict] = []
    rank = base_rank

    # Split by chart item divs (each has a unique numeric id)
    item_re = re.compile(
        r'<div\s+id="page_charts_section_charts_item_\d+"[^>]*'
        r'class="page_charts_section_charts_item[^"]*"[^>]*>',
        re.IGNORECASE,
    )
    positions = [m.start() for m in item_re.finditer(html)]

    if not positions:
        return []

    for i, start in enumerate(positions):
        end   = positions[i + 1] if i + 1 < len(positions) else len(html)
        block = html[start:end]

        # ── RYM URL (from image link — most reliable) ──────────────────────
        url_m = re.search(
            r'class="page_charts_section_charts_item_image_link"[^>]*'
            r'href="(/release/album/[^"]+)"',
            block
        )
        if not url_m:
            # Fallback: first release/album link
            url_m = re.search(r'href="(/release/album/[^"]+)"', block)
        if not url_m:
            continue
        rym_path = url_m.group(1).rstrip("/")
        rym_url  = f"{RYM_BASE}{rym_path}"

        # ── Title ─────────────────────────────────────────────────────────
        # Find the title <a> tag, then strip inner tags to get plain text.
        # Structure: <a class="...item_link release" href="..."><span ...><span ...>Title</span></span></a>
        title_link_m = re.search(
            r'<a\b[^>]*class="page_charts_section_charts_item_link\s+release"[^>]*>'
            r'(.*?)</a>',
            block, re.DOTALL
        )
        if title_link_m:
            title = re.sub(r'<[^>]+>', '', title_link_m.group(1)).strip()
            title = unescape(title) if title else ""
        else:
            # Fallback: first ui_name_locale_original anywhere in block
            m = re.search(r'class="ui_name_locale_original"[^>]*>([^<]+)<', block)
            title = unescape(m.group(1).strip()) if m else ""
        if not title:
            continue

        # ── Artist ────────────────────────────────────────────────────────
        # Structure: <a class="artist" href="..."><span ...><span ...>Name</span></span></a>
        artist_link_m = re.search(
            r'<a\b[^>]*class="artist"[^>]*>(.*?)</a>',
            block, re.DOTALL
        )
        if artist_link_m:
            artist = re.sub(r'<[^>]+>', '', artist_link_m.group(1)).strip()
            artist = unescape(artist) if artist else ""
        else:
            artist = ""
        if not artist:
            continue

        # ── Year ──────────────────────────────────────────────────────────
        year = None
        # Prefer the expanded date div (not the compact one, which repeats)
        year_m = re.search(
            r'class="page_charts_section_charts_item_date"[^>]*>'
            r'\s*<span>\s*(\d{4})\s*</span>',
            block
        )
        if not year_m:
            year_m = re.search(r'\b((?:19|20)\d{2})\b', block)
        if year_m:
            try:
                year = int(year_m.group(1))
            except ValueError:
                pass

        # ── Cover ─────────────────────────────────────────────────────────
        cover = ""
        # img inside the image_link a tag
        img_block_m = re.search(
            r'class="page_charts_section_charts_item_image_link"[^>]*>'
            r'.*?<img\b([^>]+)>',
            block, re.DOTALL
        )
        if img_block_m:
            img_attrs = img_block_m.group(1)
            src_m = re.search(r'src="([^"]+)"', img_attrs)
            if src_m and "blank" not in src_m.group(1):
                cover = _cover_hd(src_m.group(1))

        # ── Genres ────────────────────────────────────────────────────────
        genres = re.findall(r'<a\s+class="genre[^"]*"[^>]*>([^<]+)<', block)
        genres = [unescape(g.strip()) for g in genres]

        # ── Rating ────────────────────────────────────────────────────────
        rating_m = re.search(
            r'class="page_charts_section_charts_item_details_average_num"[^>]*>'
            r'([0-9.]+)<',
            block
        )
        rating = rating_m.group(1) if rating_m else ""

        albums.append({
            "number":          rank,
            "artist":          artist,
            "title":           title,
            "year":            year,
            "mbid":            "",
            "rym":             rym_url,
            "cover_url":       cover,
            "rating":          rating,
            "desc_lfm_album":  "",
            "desc_lfm_artist": "",
            "desc_mb_album":   "",
            "desc_mb_artist":  "",
            "yt_id":           "",
            "genres":          genres,
        })
        rank += 1
        if limit and len(albums) >= limit:
            break

    return albums


def _get_chart_page_count(html: str) -> int:
    """Detect total pages from RYM chart pagination links.

    RYM chart pagination links look like:
      href="/charts/top/album/all-time/g:ambient%2damericana/2/"
    The chart also links to year charts (/charts/.../2023/) which must be excluded.
    Real page numbers are small (< 500); year links are 4-digit numbers.
    """
    nums = re.findall(r'/charts/[^"\']+/(\d+)/?["\']', html)
    page_nums = [int(n) for n in nums if n.isdigit() and int(n) < 500]
    return max(page_nums, default=1)


# ── SCRAPER ───────────────────────────────────────────────────────────────────

def rym_fetch_chart(url: str, state_dir: Path,
                    cache_path: Path | None = None,
                    force: bool = False,
                    limit: int = 0) -> list[dict]:
    """
    Fetch a RYM chart (all pages up to limit) using a single Playwright session.
    Results are cached as JSON at cache_path.
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
            result = data[:limit] if limit else data
            print(f"  📦 RYM chart caché: {cache_path} ({len(result)} álbumes)")
            return result
        print("  ⚠  Caché vacío, re-scrapeando...")

    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    chromium = _find_chromium()
    extra_kwargs = {"executable_path": chromium} if chromium else {}
    if chromium:
        print(f"  🔍 Chromium: {chromium}")

    albums: list[dict] = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(state_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            **extra_kwargs,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # ── Page 1 ──
        page1_url = f"{url}1/"
        html1 = _wait_for_page(page, page1_url)
        if not html1:
            ctx.close()
            return []

        albums      = _parse_rym_chart_page(html1, base_rank=1, limit=limit)
        total_pages = _get_chart_page_count(html1)

        if len(albums) == 0:
            print(
                "  ⚠  Parser encontró 0 álbumes en la página 1.\n"
                "     Guarda el HTML manualmente en /tmp/rym_chart_debug.html para depurar."
            )
            # Dump for debugging
            try:
                Path("/tmp/rym_chart_debug.html").write_text(html1, encoding="utf-8")
                print("  💡 HTML guardado en /tmp/rym_chart_debug.html")
            except Exception:
                pass
            ctx.close()
            return []

        if total_pages > 1:
            print(f"  📄 {total_pages} páginas detectadas")

        # ── Remaining pages ──
        page_n = 2
        while page_n <= total_pages:
            if limit and len(albums) >= limit:
                break
            time.sleep(1.5)
            remaining = (limit - len(albums)) if limit else 0
            page_url  = f"{url}{page_n}/"
            html_n    = _wait_for_page(page, page_url)
            if not html_n:
                print(f"  ⚠  Página {page_n} vacía, deteniendo")
                break
            base = len(albums) + 1
            more = _parse_rym_chart_page(html_n, base_rank=base, limit=remaining)
            if not more:
                print(f"  ⚠  Página {page_n}: sin álbumes, deteniendo")
                break
            albums.extend(more)
            page_n += 1

        ctx.close()

    if limit:
        albums = albums[:limit]
    print(f"  🎵 {len(albums)} álbumes totales")

    if cache_path:
        cache_path.write_text(json.dumps(albums, ensure_ascii=False, indent=2))
        print(f"  💾 Caché guardado: {cache_path}")

    return albums


# ── MAIN RUNNER ───────────────────────────────────────────────────────────────

def run_rym_chart(args, root_dir: Path) -> None:
    """
    Main entry point for a RYM chart URL.

    args attributes:
      - rym_chart_url  : str  — RYM chart URL (required)
      - name           : str  — display name (auto-derived if empty)
      - slug           : str  — output subdirectory (auto-derived if None)
      - collection     : str | None
      - must_hear_db   : str | None
      - _rym_chart_mh_conn : sqlite3.Connection | None
      - scrobbles_db / db  : str | None
      - users          : list[str] | None
      - index_only     : bool
      - force_scrape   : bool
      - rym_chart_limit: int  — 0 = unlimited
    """
    from html_must_hear import (
        mh_get_users, mh_get_user_albums, mh_load_collection,
        check_heard, mh_album_to_json, render_collection_index_html,
        render_user_html, update_root_index, update_collection_group_index,
        mh_populate_user_heard,
    )

    chart_url  = getattr(args, "rym_chart_url",   None) or getattr(args, "url", None)
    name       = getattr(args, "name",             "") or ""
    slug       = getattr(args, "slug",             None)
    collection = getattr(args, "collection",       None) or "RYM Charts"
    index_only = getattr(args, "index_only",       False)
    force      = getattr(args, "force_scrape",     False)
    limit      = getattr(args, "rym_chart_limit",  0) or 0

    if not chart_url and not (index_only and slug):
        print("❌ --rym-chart requerido (URL de chart RateYourMusic)")
        return

    if chart_url:
        chart_url = chart_url.rstrip("/") + "/"

    # ── Slug & output dir ────────────────────────────────────────────────────
    if not slug:
        slug = _slug_from_chart_url(chart_url)

    if collection:
        coll_slug = re.sub(r"[^a-z0-9]+", "_", collection.lower()).strip("_")
        out_dir   = root_dir / coll_slug / slug
    else:
        coll_slug = None
        out_dir   = root_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = out_dir / "rym_chart_cache.json"
    generated  = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── DB connections ───────────────────────────────────────────────────────
    mh_conn: sqlite3.Connection | None = getattr(args, "_rym_chart_mh_conn", None)
    if mh_conn is None and getattr(args, "must_hear_db", None):
        p = Path(args.must_hear_db)
        if p.exists():
            mh_conn = sqlite3.connect(str(p))
            mh_conn.execute("PRAGMA journal_mode=WAL")

    scr_path = getattr(args, "scrobbles_db", None) or getattr(args, "db", None)

    # ── Users ────────────────────────────────────────────────────────────────
    if mh_conn:
        users = getattr(args, "users", None) or mh_get_users(mh_conn)
    elif scr_path:
        import sqlite3 as _sq
        with _sq.connect(scr_path) as _c:
            try:
                rows  = _c.execute("SELECT name FROM users ORDER BY name").fetchall()
            except Exception:
                rows  = _c.execute("SELECT DISTINCT user FROM scrobbles ORDER BY user").fetchall()
            users = getattr(args, "users", None) or [r[0] for r in rows]
    else:
        users = getattr(args, "users", None) or []
    print(f"👥 Usuarios: {', '.join(users) or '(ninguno)'}")

    # ── Scrobbles ────────────────────────────────────────────────────────────
    if scr_path:
        import sqlite3 as _sq
        _scr = _sq.connect(scr_path)
        users_heard = {u: mh_get_user_albums(_scr, u) for u in users}
        _scr.close()
    elif mh_conn:
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

    # ── Albums ───────────────────────────────────────────────────────────────
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
                raw   = json.loads(cache_path.read_text())
                albums = raw[:limit] if limit else raw
                print(f"  📦 {len(albums)} álbumes desde caché ({cache_path})")
            else:
                print(f"  ❌ --index-only pero no existe caché: {cache_path}")
                return
        else:
            albums = rym_fetch_chart(chart_url, STATE_DIR, cache_path,
                                     force=force, limit=limit)
            if not albums:
                print("  ❌ No se obtuvieron álbumes")
                return

        if not name:
            name = _name_from_chart_url(chart_url) if chart_url else slug.replace("_", " ").title()

        if mh_conn and not index_only:
            albums = rym_sync_to_db(mh_conn, slug, name, chart_url, albums)
            albums_from_db = True

    if not name:
        name = slug.replace("_", " ").title()

    # ── Per-user HTML ────────────────────────────────────────────────────────
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
                    "artist":          album.get("artist", ""),
                    "title":           album.get("title", ""),
                    "year":            album.get("year"),
                    "mbid":            album.get("mbid", ""),
                    "cover_url":       album.get("cover_url", "") or COVER_PLACEHOLDER,
                    "rym":             album.get("rym", ""),
                    "yt_id":           album.get("yt_id", ""),
                    "genres":          album.get("genres", []),
                    "desc_lfm_album":  album.get("desc_lfm_album", ""),
                    "desc_lfm_artist": album.get("desc_lfm_artist", ""),
                    "desc_mb_album":   album.get("desc_mb_album", ""),
                    "desc_mb_artist":  album.get("desc_mb_artist", ""),
                    "heard":           heard,
                    "number":          album.get("number", 0),
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

    # ── Collection index ─────────────────────────────────────────────────────
    (out_dir / "index.html").write_text(
        render_collection_index_html(users_index, name, generated),
        encoding="utf-8"
    )
    print(f"  📋 {out_dir / 'index.html'}")

    # ── Root index update ─────────────────────────────────────────────────────
    if coll_slug:
        update_collection_group_index(
            root_dir, collection, coll_slug, name, slug, users_index, generated
        )
    else:
        update_root_index(root_dir, name, slug, users_index, generated)


# ── STANDALONE ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RateYourMusic Chart → Must Hear HTML Generator"
    )
    parser.add_argument("--url", required=True,
                        help="URL de chart RYM (ej: https://rateyourmusic.com/charts/top/album/all-time/g:ambient-americana/)")
    parser.add_argument("--must-hear-db", dest="must_hear_db", default=None)
    parser.add_argument("--scrobbles-db", dest="scrobbles_db", default=None)
    parser.add_argument("--db",           dest="db",           default=None,
                        help="[alias] --scrobbles-db")
    parser.add_argument("--out",          default="docs/must_hear")
    parser.add_argument("--name",         default="")
    parser.add_argument("--slug",         default=None)
    parser.add_argument("--collection",   default=None)
    parser.add_argument("--users",        nargs="*")
    parser.add_argument("--limit",        dest="rym_chart_limit", type=int, default=0,
                        help="Limitar a N álbumes (0 = sin límite)")
    parser.add_argument("--index-only",   dest="index_only",    action="store_true")
    parser.add_argument("--force",        dest="force_scrape",  action="store_true")
    args = parser.parse_args()
    args.rym_chart_url = args.url

    root_dir = Path(args.out)
    root_dir.mkdir(parents=True, exist_ok=True)

    if args.must_hear_db:
        p = Path(args.must_hear_db)
        if not p.exists():
            print(f"❌ --must-hear-db no existe: {p}")
            return
        args._rym_chart_mh_conn = sqlite3.connect(str(p))
        args._rym_chart_mh_conn.execute("PRAGMA journal_mode=WAL")
    else:
        args._rym_chart_mh_conn = None

    run_rym_chart(args, root_dir)

    if getattr(args, "_rym_chart_mh_conn", None):
        args._rym_chart_mh_conn.close()


if __name__ == "__main__":
    main()

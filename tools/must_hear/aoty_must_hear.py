#!/usr/bin/env python3
"""
Album of the Year — Must Hear Scraper & HTML Generator

Scrapes https://www.albumoftheyear.org/must-hear/YYYYs/page/*/
for decades 1950s–2020s and generates HTML grids with per-user heard status.

Standalone:  python3 aoty_must_hear.py [--db DB] [--out OUT] [--decade 1960s 1970s]
From parent: from aoty_must_hear import aoty_fetch_decade, run_aoty
"""

import subprocess, json, re, time, sqlite3, argparse, urllib.request, urllib.parse
from html import unescape
from pathlib import Path
from datetime import datetime

# ── CONFIG ─────────────────────────────────────────────────────────────────────
AOTY_BASE = "https://www.albumoftheyear.org/must-hear"
UA        = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"

DECADES = ["1950s", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"]

COVER_PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20"
    "width=%22250%22%20height=%22250%22%20viewBox=%220%200%20250%20250%22%3E"
    "%3Crect%20width=%22250%22%20height=%22250%22%20fill=%22%23111%22/%3E"
    "%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%2260%22%20fill=%22none%22"
    "%20stroke=%22%23333%22%20stroke-width=%222%22/%3E%3C/svg%3E"
)


# ── HTTP ───────────────────────────────────────────────────────────────────────

def _curl_get(url: str) -> str:
    r = subprocess.run(
        ["curl", "-s", "-L", "-A", UA, "--max-time", "30", url],
        capture_output=True, text=True
    )
    return r.stdout if r.returncode == 0 else ""


# ── HELPERS ────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())


def _cover_hd(url: str) -> str:
    """Upgrade 200x0 thumbnail to 600x0."""
    return url.replace("/200x0/", "/600x0/") if url else ""


# ── PARSER ─────────────────────────────────────────────────────────────────────

def _get_total_pages(html: str) -> int:
    pages = re.findall(r'class="pageSelectSmall[^"]*">(\d+)<', html)
    return max((int(p) for p in pages), default=1)


def _parse_aoty_page(html: str, decade: str, start_rank: int = 1) -> list[dict]:
    """Parse one AOTY must-hear page into album dicts."""
    albums = []
    rank   = start_rank

    # Each album is wrapped in <div class="albumBlock" ...>
    blocks = re.split(r'<div class="albumBlock"[^>]*>', html)[1:]

    for block in blocks:
        # Album URL → extract numeric AOTY ID
        url_m = re.search(r'href="(/album/(\d+)-[^"]+\.php)"', block)
        if not url_m:
            continue
        aoty_path = url_m.group(1)
        aoty_id   = url_m.group(2)
        aoty_url  = f"https://www.albumoftheyear.org{aoty_path}"

        # Cover (use srcset 2x → 400x0, or upgrade src 200x0 → 600x0)
        cover_m = re.search(r'<img[^>]+src="([^"]+cdn[^"]+)"', block)
        cover   = _cover_hd(cover_m.group(1)) if cover_m else ""

        # Artist & title (inside their respective divs)
        artist_m = re.search(r'class="artistTitle"[^>]*>\s*([^<]+)\s*<', block)
        title_m  = re.search(r'class="albumTitle"[^>]*>\s*([^<]+)\s*<', block)
        if not title_m or not artist_m:
            continue
        artist = unescape(artist_m.group(1).strip())
        title  = unescape(title_m.group(1).strip())

        # Year (sits in a <div class="type">YYYY</div>)
        year_m = re.search(r'<div class="type">(\d{4})</div>', block)
        year   = int(year_m.group(1)) if year_m else None

        # Scores: first <div class="rating"> = critic, second = user
        ratings      = re.findall(r'<div class="rating">(\d+)</div>', block)
        critic_score = int(ratings[0]) if ratings else None
        user_score   = int(ratings[1]) if len(ratings) > 1 else None

        albums.append({
            "number":            rank,
            "title":             title,
            "artist":            artist,
            "year":              year,
            "mbid":              "",
            "aoty_id":           aoty_id,
            "aoty_url":          aoty_url,
            "cover_url":         cover,
            "aoty_critic_score": critic_score,
            "aoty_user_score":   user_score,
            "decade":            decade,
            # enrichment placeholders
            "desc_lfm_album":    "",
            "desc_lfm_artist":   "",
            "desc_mb_album":     "",
            "desc_mb_artist":    "",
            "yt_id":             "",
            "rym":               "",
            "genres":            [],
        })
        rank += 1

    return albums


# ── FETCHER ─────────────────────────────────────────────────────────────────────

def aoty_fetch_decade(decade: str, cache_dir: Path, force: bool = False) -> list[dict]:
    """Fetch and cache all AOTY must-hear albums for one decade (all pages)."""
    cache_file = cache_dir / f"aoty_{decade}_cache.json"

    if cache_file.exists() and not force:
        data = json.loads(cache_file.read_text())
        if data:
            print(f"  📦 AOTY {decade} caché: {cache_file} ({len(data)} álbumes)")
            return data
        print(f"  ⚠ Caché vacío para {decade}, re-scrapeando...")

    print(f"\n🌐 Scrapeando AOTY must-hear {decade}...")
    url  = f"{AOTY_BASE}/{decade}/"
    html = _curl_get(url)
    if not html:
        print(f"  ❌ No se pudo obtener {url}")
        return []

    total_pages = _get_total_pages(html)
    print(f"  📚 {total_pages} página(s) detectadas")

    all_albums = _parse_aoty_page(html, decade, start_rank=1)
    print(f"  → Pág 1: {len(all_albums)} álbumes")

    for page in range(2, total_pages + 1):
        time.sleep(1.5)
        purl  = f"{AOTY_BASE}/{decade}/page/{page}/"
        print(f"  🌐 Página {page}/{total_pages}: {purl}")
        phtml = _curl_get(purl)
        if not phtml:
            print(f"  ⚠ Pág {page} vacía, deteniéndose")
            break
        items = _parse_aoty_page(phtml, decade, start_rank=len(all_albums) + 1)
        print(f"  → Pág {page}: {len(items)} álbumes")
        all_albums.extend(items)

    cache_file.write_text(json.dumps(all_albums, ensure_ascii=False, indent=2))
    print(f"  ✅ {len(all_albums)} álbumes → {cache_file}")
    return all_albums


# ── SCROBBLES DB ───────────────────────────────────────────────────────────────

def _user_table_name(username: str) -> str:
    safe = re.sub(r"[^a-z0-9]", "_", username.lower()).strip("_")
    return f"scrobbles_{safe}"


def _scrobbles_schema(conn: sqlite3.Connection) -> str:
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    return "new" if "scrobbles" not in tables and "artists" in tables else "old"


def _get_users(db_path: str) -> list[str]:
    with sqlite3.connect(db_path) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "users" in tables:
            return [r[0] for r in c.execute(
                "SELECT username FROM users ORDER BY username"
            ).fetchall()]
        return [r[0] for r in c.execute(
            "SELECT DISTINCT user FROM scrobbles ORDER BY user"
        ).fetchall()]


def _get_user_albums(db_path: str, user: str) -> set[tuple]:
    """Return set of (norm_artist, norm_album) for user scrobbles."""
    with sqlite3.connect(db_path) as c:
        if _scrobbles_schema(c) == "new":
            tbl    = _user_table_name(user)
            exists = c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone()
            if not exists:
                return set()
            rows = c.execute(f"""
                SELECT ar.name, al.name
                FROM {tbl} sc
                JOIN artists ar ON ar.id = sc.artist_id
                JOIN albums  al ON al.id = sc.album_id
                WHERE sc.album_id IS NOT NULL
            """).fetchall()
        else:
            rows = c.execute(
                "SELECT artist, album FROM scrobbles "
                "WHERE user=? AND album IS NOT NULL AND album != ''",
                (user,)
            ).fetchall()
    return {(_norm(r[0]), _norm(r[1])) for r in rows}


# ── HEARD CHECK ────────────────────────────────────────────────────────────────

def aoty_check_heard(user_albums: set, album: dict) -> bool:
    """Fuzzy match: album heard if title+artist match scrobbles."""
    a_n = _norm(album["artist"])
    t_n = _norm(album["title"])
    if not t_n:
        return False
    for ua, ut in user_albums:
        if not ut:
            continue
        title_match = (t_n == ut or t_n in ut or
                       (ut in t_n and len(ut) >= len(t_n) * 0.8))
        if not title_match:
            continue
        if not a_n or a_n in ua or ua in a_n:
            return True
    return False


# ── HTML RENDERING ─────────────────────────────────────────────────────────────

def render_aoty_decade_html(decade: str, albums: list[dict],
                             users_heard: dict[str, set],
                             all_decades: list[str],
                             series_name: str = "AOTY Must Hear") -> str:
    """Generate HTML page for one AOTY decade (Scaruffi-style UI)."""
    users     = list(users_heard.keys())
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    total     = len(albums)

    decade_nav = ""
    for d in all_decades:
        active      = " active" if d == decade else ""
        decade_nav += f'<a class="dec-item{active}" href="decade_{d}.html">{d}</a>'

    # Collect genres across all albums
    all_genres: dict[str, int] = {}
    for a in albums:
        for g in (a.get("genres") or []):
            all_genres[g] = all_genres.get(g, 0) + 1
    genre_json = json.dumps(sorted(all_genres.items(), key=lambda x: -x[1]))

    albums_js = []
    for a in albums:
        heard_by = [u for u in users if aoty_check_heard(users_heard[u], a)]
        albums_js.append({
            "n":                 a["number"],
            "title":             a["title"],
            "artist":            a["artist"],
            "year":              a.get("year"),
            "cover":             a.get("cover_url", ""),
            "aoty_url":          a.get("aoty_url", ""),
            "aoty_critic_score": a.get("aoty_critic_score"),
            "aoty_user_score":   a.get("aoty_user_score"),
            "mbid":              a.get("mbid", ""),
            "yt_id":             a.get("yt_id", ""),
            "rym":               a.get("rym", ""),
            "genres":            a.get("genres", []),
            "desc_lfm_album":    a.get("desc_lfm_album", ""),
            "desc_lfm_artist":   a.get("desc_lfm_artist", ""),
            "desc_mb_album":     a.get("desc_mb_album", ""),
            "desc_mb_artist":    a.get("desc_mb_artist", ""),
            "heard_by":          heard_by,
        })

    albums_json = json.dumps(albums_js, ensure_ascii=False)
    users_json  = json.dumps(users,     ensure_ascii=False)
    cover_ph    = COVER_PLACEHOLDER

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
  padding:0 18px;display:flex;align-items:center;gap:12px;
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
  display:none;position:fixed;
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
  background:linear-gradient(0deg,rgba(0,0,0,.92) 0%,rgba(0,0,0,0) 55%);
  opacity:0;transition:opacity .18s;display:flex;flex-direction:column;justify-content:flex-end;
  padding:6px;z-index:2;
}
.card:hover .card-overlay{opacity:1}
.card-scores{display:flex;gap:3px;margin-bottom:2px}
.card-score{font-family:'DM Mono',monospace;font-size:.58rem;font-weight:700;padding:1px 4px;border-radius:2px}
.card-score.c{background:rgba(108,184,250,.2);color:#6cb8fa}
.card-score.u{background:rgba(191,143,255,.2);color:#bf8fff}
.card-title{font-size:.56rem;font-weight:500;color:#fff;line-height:1.25;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.card-artist{font-size:.52rem;color:var(--muted);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card::before{content:'';position:absolute;top:4px;right:4px;width:7px;height:7px;border-radius:50%;z-index:3}
.card.heard-user::before{background:var(--heard);box-shadow:0 0 5px var(--heard)}
.card.unheard-user::before{background:var(--pending);box-shadow:0 0 5px var(--pending)}
#panel{
  position:fixed;top:0;right:0;bottom:0;width:var(--panel);
  background:#0c0c0c;border-left:1px solid var(--border);
  z-index:50;display:flex;flex-direction:column;overflow:hidden;
}
.panel-topbar{height:var(--header-h);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 15px;flex-shrink:0}
.panel-topbar-label{font-family:'DM Mono',monospace;font-size:.56rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
.panel-cover{width:100%;aspect-ratio:1;flex-shrink:0;position:relative;background:var(--surface);max-height:200px;overflow:hidden}
.panel-cover img{width:100%;height:100%;object-fit:cover;display:block}
.panel-scores{display:flex;gap:6px;position:absolute;bottom:8px;left:8px}
.panel-score{padding:3px 8px;border-radius:3px;font-family:'DM Mono',monospace;font-size:.72rem;font-weight:700}
.panel-score.c{background:rgba(0,0,0,.7);color:#6cb8fa;border:1px solid #6cb8fa44}
.panel-score.u{background:rgba(0,0,0,.7);color:#bf8fff;border:1px solid #bf8fff44}
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
.desc-block{margin-bottom:9px}
.desc-source-label{font-family:'DM Mono',monospace;font-size:.5rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:2px;display:flex;align-items:center;gap:4px}
.desc-source-label::before{content:'';display:inline-block;width:5px;height:5px;border-radius:50%;background:currentColor;flex-shrink:0}
.desc-source-label.lfm{color:#d51007}.desc-source-label.mb{color:#ba478f}.desc-source-label.artist{color:#6a9fb5}
.desc-source-text{font-size:.7rem;color:#aaa;line-height:1.55}
.panel-links{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}
.panel-link{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.07em;text-transform:uppercase;padding:3px 8px;border-radius:3px;border:1px solid var(--border);color:var(--muted);text-decoration:none;transition:all .15s}
.panel-link:hover{border-color:var(--accent);color:var(--accent)}
.panel-link.aoty{border-color:#e87c2e;color:#e87c2e}
.panel-link.aoty:hover{background:rgba(232,124,46,.08)}
.panel-link.yt{border-color:#f00;color:#f00}
.panel-link.yt:hover{background:rgba(255,0,0,.08)}
.panel-link.rym{border-color:#5baadb;color:#5baadb}
.panel-link.rym:hover{background:rgba(91,170,219,.08)}
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
}"""

    js = f"""
const ALBUMS = {albums_json};
const USERS  = {users_json};
const GENRE_OPTS = {genre_json};
let filter = 'all';
let selectedGenres = new Set();
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
    const n = parseInt(card.dataset.num);
    const a = ALBUMS.find(x=>x.n===n);
    if (!a) return;
    const heard = isHeard(a);
    card.dataset.heard = heard ? '1' : '0';
    card.classList.toggle('heard-user',  heard);
    card.classList.toggle('unheard-user', !heard);
  }});
  applyFilters();
}}

document.addEventListener('click', e => {{
  if (!e.target.closest('.genre-wrap')) document.getElementById('genre-dd').classList.remove('open');
  if (!e.target.closest('.user-wrap'))  document.getElementById('user-dd').classList.remove('open');
  if (!e.target.closest('.dec-wrap'))   document.getElementById('dec-dd').classList.remove('open');
}});

function buildGrid() {{
  const grid = document.getElementById('grid');
  grid.innerHTML='';
  ALBUMS.forEach(a => {{
    const card = document.createElement('div');
    const heard = isHeard(a);
    card.className = 'card ' + (heard ? 'heard-user' : 'unheard-user');
    card.dataset.artist = (a.artist||'').toLowerCase();
    card.dataset.title  = (a.title||'').toLowerCase();
    card.dataset.genres = (a.genres||[]).join(',');
    card.dataset.heard  = heard ? '1' : '0';
    card.dataset.num    = a.n;
    const img = document.createElement('img');
    img.dataset.src = a.cover || COVER_PH;
    img.src = COVER_PH;
    img.alt = a.n;
    img.onerror = function(){{ this.onerror=null; this.src=COVER_PH; }};
    card.appendChild(img);
    const cs = a.aoty_critic_score != null ? '<span class="card-score c">'+a.aoty_critic_score+'</span>' : '';
    const us = a.aoty_user_score   != null ? '<span class="card-score u">'+a.aoty_user_score+'</span>'   : '';
    card.insertAdjacentHTML('beforeend',
      '<div class="card-overlay">'
      +'<div class="card-scores">'+cs+us+'</div>'
      +'<div class="card-title">'+a.title+'</div>'
      +'<div class="card-artist">'+a.artist+(a.year?' \xb7 '+a.year:'')+'</div>'
      +'</div>');
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
  document.getElementById('p-cover').src = a.cover || COVER_PH;
  document.getElementById('p-cover').onerror = function(){{ this.src=COVER_PH; }};

  const cs = a.aoty_critic_score != null ? '<span class="panel-score c">'+a.aoty_critic_score+' critic</span>' : '';
  const us = a.aoty_user_score   != null ? '<span class="panel-score u">'+a.aoty_user_score+' user</span>'     : '';
  document.getElementById('p-scores').innerHTML = cs + us;

  const links = [];
  if (a.aoty_url) links.push('<a class="panel-link aoty" href="'+a.aoty_url+'" target="_blank">AOTY</a>');
  if (a.rym)      links.push('<a class="panel-link rym"  href="'+a.rym+'"      target="_blank">RYM</a>');
  if (a.mbid)     links.push('<a class="panel-link"      href="https://musicbrainz.org/release-group/'+a.mbid+'" target="_blank">MusicBrainz</a>');
  if (a.yt_id)    links.push('<a class="panel-link yt"   href="https://youtu.be/'+a.yt_id+'" target="_blank">YouTube</a>');

  let ytBlock = '';
  if (a.yt_id) {{
    ytBlock = '<iframe src="https://www.youtube.com/embed/'+a.yt_id+'" allow="autoplay;encrypted-media" allowfullscreen></iframe>';
  }} else {{
    const q = encodeURIComponent(a.artist+' '+a.title+' full album');
    ytBlock = '<div class="panel-yt-placeholder"><a href="https://www.youtube.com/results?search_query='+q+'" target="_blank" style="color:var(--accent);text-decoration:none">Search YouTube \u2197</a></div>';
  }}

  const genreTags = (a.genres||[]).map(g=>'<span class="panel-genre-tag">'+g+'</span>').join('');
  const heardLine = a.heard_by.length>0 ? '<div class="panel-heard-by">Heard by <b>'+a.heard_by.join(', ')+'</b></div>' : '';

  const descSrcs = [
    {{key:'desc_lfm_album',  cls:'lfm',    lbl:'💿 Album \u00b7 Last.fm'}},
    {{key:'desc_lfm_artist', cls:'artist',  lbl:'🎤 Artist \u00b7 Last.fm'}},
    {{key:'desc_mb_album',   cls:'mb',      lbl:'💿 Album \u00b7 MusicBrainz'}},
    {{key:'desc_mb_artist',  cls:'mb artist',lbl:'🎤 Artist \u00b7 MusicBrainz'}},
  ];
  const descBlocks = descSrcs.filter(s=>a[s.key]&&a[s.key].length>40)
    .map(s=>'<div class="desc-block"><div class="desc-source-label '+s.cls+'">'+s.lbl+'</div><div class="desc-source-text">'+a[s.key]+'</div></div>').join('');
  const bioHtml   = descBlocks || '<span style="color:var(--muted);font-style:italic">Loading\u2026</span>';
  const needsFetch = !descBlocks;

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
    +'<div class="panel-bio" id="p-bio">'+bioHtml+'</div>';

  if (needsFetch) fetchBio(a.artist, a.title, a.mbid);
}}

async function fetchBio(artist, title, mbid) {{
  const bioEl = document.getElementById('p-bio');
  if (!bioEl) return;
  const KEY = 'key';
  const clean = t => t.replace(/<a href="[^"]*last\\.fm[^"]*"[^>]*>[^<]*<\\/a>/g,'').replace(/<[^>]+>/g,'').replace(/ {{2,}}/g,' ').trim().slice(0,800);
  const blocks = [];
  try {{
    const d  = await fetch('https://ws.audioscrobbler.com/2.0/?method=album.getinfo&artist='+encodeURIComponent(artist)+'&album='+encodeURIComponent(title)+'&format=json&api_key='+KEY).then(r=>r.json());
    const wiki = clean(d?.album?.wiki?.summary||d?.album?.wiki?.content||'');
    if (wiki.length>40) blocks.push('<div class="desc-block"><div class="desc-source-label lfm">💿 Album \u00b7 Last.fm</div><div class="desc-source-text">'+wiki+'</div></div>');
    const d2 = await fetch('https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist='+encodeURIComponent(artist)+'&format=json&api_key='+KEY).then(r=>r.json());
    const bio = clean(d2?.artist?.bio?.summary||'');
    if (bio.length>40) blocks.push('<div class="desc-block"><div class="desc-source-label artist">🎤 Artist \u00b7 Last.fm</div><div class="desc-source-text">'+bio+'</div></div>');
  }} catch(e) {{}}
  try {{
    if (mbid) {{
      const mb  = await fetch('https://musicbrainz.org/ws/2/release-group/'+mbid+'?inc=annotation&fmt=json').then(r=>r.json());
      const ann = (mb?.annotation?.text||'').trim();
      if (ann.length>20) blocks.push('<div class="desc-block"><div class="desc-source-label mb">💿 Album \u00b7 MusicBrainz</div><div class="desc-source-text">'+ann.slice(0,800)+'</div></div>');
    }}
  }} catch(e) {{}}
  if (bioEl) bioEl.innerHTML = blocks.length ? blocks.join('') : 'No info available.';
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
    const show=mf&&ms&&mg;
    c.classList.toggle('hidden',!show);
    if(show){{vis++;if(c.dataset.heard==='1')visH++;}}
  }});
  document.getElementById('vis-count').textContent=vis;
  const uLabel = selectedUser ? ' ('+selectedUser+')' : '';
  document.getElementById('vis-heard').textContent=visH+' heard'+uLabel;
  document.getElementById('empty').style.display=vis===0?'block':'none';
}}

buildGenreList(); buildUserList(); buildGrid();
setTimeout(()=>{{
  const first=document.querySelector('.card:not(.hidden)');
  if(first){{const a=ALBUMS.find(x=>x.n===parseInt(first.dataset.num));if(a)openPanel(a,first);}}
}},100);"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AOTY Must Hear — {decade}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<script defer src="https://cloud.umami.is/script.js"
    data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<header>
  <a href="index.html" class="back-link">←</a>
  <span class="header-title">AOTY Must Hear</span>
  <div class="dec-wrap">
    <button class="dec-btn" id="dec-btn" onclick="toggleDecDD()">
      {decade} &#x25BE;
    </button>
  </div>
  <div class="controls">
    <button class="filter-btn active" id="btn-all"     onclick="setFilter('all')">All</button>
    <button class="filter-btn"        id="btn-heard"   onclick="setFilter('heard')">Heard</button>
    <button class="filter-btn"        id="btn-unheard" onclick="setFilter('unheard')">Unheard</button>
    <input class="search-box" id="search" placeholder="Search..." oninput="applyFilters()">
    <div class="genre-wrap">
      <button class="genre-btn" id="genre-btn" onclick="toggleGenreDD()">
        Genre <span class="badge" id="genre-badge" style="display:none">0</span> &#x25BE;
      </button>
    </div>
    <div class="user-wrap">
      <button class="user-btn" id="user-btn" onclick="toggleUserDD()">
        <span class="u-name" id="user-btn-label">All users</span> &#x25BE;
      </button>
    </div>
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
    <div class="panel-scores" id="p-scores"></div>
  </div>
  <div class="panel-body" id="panel-body">
    <div class="panel-empty"><div class="panel-empty-icon">◉</div>Click an album</div>
  </div>
</aside>
<div class="dec-dropdown" id="dec-dd">
  <div class="dec-dh">Jump to decade</div>
  {decade_nav}
</div>
<div class="genre-dropdown" id="genre-dd">
  <div class="genre-dh">Filter by genre <span class="genre-clear" onclick="clearGenres()">clear</span></div>
  <div id="genre-list"></div>
</div>
<div class="user-dropdown" id="user-dd">
  <div class="user-dh">View as user</div>
  <div id="user-list"></div>
</div>
<script>{js}</script>
</body>
</html>"""

def render_aoty_index_html(decades_data: dict[str, list],
                            users: list[str],
                            users_heard: dict[str, set],
                            generated: str,
                            series_name: str = "AOTY Must Hear") -> str:
    """Index: table of decades with avg heard % across all users."""
    rows = ""
    for decade in DECADES:
        albums = decades_data.get(decade, [])
        if not albums:
            continue
        total = len(albums)
        # Avg heard across all users
        if users:
            per_user = []
            for u in users:
                heard = sum(1 for a in albums if aoty_check_heard(users_heard.get(u, set()), a))
                per_user.append(heard)
            avg_heard = sum(per_user) / len(per_user)
            avg_pct   = round(avg_heard / total * 100)
            heard_cell = f'<span class="uc-heard">{avg_heard:.0f}</span><span class="uc-pct">{avg_pct}%</span>'
        else:
            heard_cell = '<span class="uc-heard">—</span>'
        rows += f'<tr><td class="dc"><a href="decade_{decade}.html" class="dec-a">{decade}</a></td><td class="tc">{total}</td><td class="uc">{heard_cell}</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AOTY Must Hear</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<script defer src="https://cloud.umami.is/script.js"
    data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"></script>
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
.dc{{width:100px}}
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
  <div class="site-label">Album of the Year</div>
  <h1>AOTY Must Hear</h1>
  <div class="header-meta">Generated {generated}</div>
</header>
<main>
  <a href="../index.html" class="back-link">← All collections</a>
  <table>
    <thead><tr><th>Decade</th><th>Albums</th><th>Avg heard</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</main>
<footer>albumoftheyear.org must-hear lists</footer>
</body>
</html>"""


# ── MUST-HEAR DB INTEGRATION ───────────────────────────────────────────────────

def mh_load_aoty_collection(mh_conn: sqlite3.Connection,
                             collection_slug: str) -> list[dict]:
    """Load AOTY albums from must_hear.db for a given collection slug.
    Returns list of dicts with all enriched fields including aoty_url."""
    rows = mh_conn.execute("""
        SELECT
            al.id,
            ar.name                AS artist,
            al.name                AS title,
            al.year,
            al.release_group_mbid  AS mbid,
            ca.rank,
            al.aoty_url,
            al.aoty_critic_score,
            al.aoty_user_score,
            al.cover_url,
            al.yt_id,
            al.rateyourmusic_url   AS rym,
            am.desc_lfm_album,
            am.desc_lfm_artist,
            am.desc_mb_album,
            am.desc_mb_artist
        FROM collection_albums ca
        JOIN collections c        ON c.id  = ca.collection_id
        JOIN albums al            ON al.id = ca.album_id
        JOIN artists ar           ON ar.id = al.artist_id
        LEFT JOIN album_metadata am ON am.album_id = al.id
        WHERE c.slug = ?
        ORDER BY ca.rank ASC NULLS LAST, al.year ASC
    """, (collection_slug,)).fetchall()

    col_names = [
        "id", "artist", "title", "year", "mbid", "rank",
        "aoty_url", "aoty_critic_score", "aoty_user_score", "cover_url",
        "yt_id", "rym",
        "desc_lfm_album", "desc_lfm_artist", "desc_mb_album", "desc_mb_artist",
    ]
    albums = []
    for i, row in enumerate(rows):
        rd = dict(zip(col_names, row))
        rd["number"]  = rd["rank"] or (i + 1)
        rd["decade"]  = collection_slug.replace("aoty_", "")
        rd["genres"]  = []
        # Load genres
        genre_rows = mh_conn.execute("""
            SELECT g.name FROM genres g
            JOIN album_genres ag ON ag.genre_id = g.id
            WHERE ag.album_id = ?
            ORDER BY ag.weight DESC LIMIT 6
        """, (rd["id"],)).fetchall()
        rd["genres"] = [r[0] for r in genre_rows]
        albums.append(rd)
    return albums


def mh_sync_aoty_collection(mh_conn: sqlite3.Connection,
                              decade: str,
                              scraped_albums: list[dict]) -> list[dict]:
    """Upsert scraped AOTY albums into must_hear.db.
    Uses SELECT-first pattern throughout — no UNIQUE constraints exist on
    slug/name/artist_id+name, so INSERT OR IGNORE would silently do nothing.
    Returns album list with 'id' field set to DB row id."""
    ts   = int(time.time())
    slug = f"aoty_{decade}"
    url  = f"{AOTY_BASE}/{decade}/"

    # ── 1. Collection row ─────────────────────────────────────────────────────
    coll_row = mh_conn.execute(
        "SELECT id FROM collections WHERE slug=?", (slug,)
    ).fetchone()
    if coll_row:
        coll_id = coll_row[0]
        mh_conn.execute(
            "UPDATE collections SET name=?, source_url=?, source_type=?, "
            "last_updated=? WHERE id=?",
            (f"AOTY Must Hear {decade}", url, "aoty", ts, coll_id)
        )
        print(f"  📋 Colección existente '{slug}' (id={coll_id})")
    else:
        mh_conn.execute(
            "INSERT INTO collections "
            "(name, slug, source_url, source_type, last_updated, added_timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (f"AOTY Must Hear {decade}", slug, url, "aoty", ts, ts)
        )
        coll_id = mh_conn.execute(
            "SELECT id FROM collections WHERE slug=?", (slug,)
        ).fetchone()[0]
        print(f"  📋 Colección nueva '{slug}' creada (id={coll_id})")
    mh_conn.commit()

    # ── 2. Albums ─────────────────────────────────────────────────────────────
    result = []
    for album in scraped_albums:
        artist_name = album["artist"]
        title       = album["title"]

        # Artist: SELECT by name (indexed), insert only if missing
        artist_row = mh_conn.execute(
            "SELECT id FROM artists WHERE name=?", (artist_name,)
        ).fetchone()
        if artist_row:
            artist_id = artist_row[0]
        else:
            mh_conn.execute(
                "INSERT INTO artists (name, added_timestamp) VALUES (?,?)",
                (artist_name, ts)
            )
            artist_id = mh_conn.execute(
                "SELECT id FROM artists WHERE name=?", (artist_name,)
            ).fetchone()[0]

        # Album: SELECT by (artist_id, name), insert only if missing
        album_row = mh_conn.execute(
            "SELECT id FROM albums WHERE artist_id=? AND name=?",
            (artist_id, title)
        ).fetchone()
        if album_row:
            album_id = album_row[0]
        else:
            mh_conn.execute(
                "INSERT INTO albums "
                "(artist_id, name, year, aoty_url, aoty_critic_score, "
                "aoty_user_score, cover_url, added_timestamp) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (artist_id, title, album.get("year"),
                 album.get("aoty_url", ""),
                 album.get("aoty_critic_score"),
                 album.get("aoty_user_score"),
                 album.get("cover_url", ""),
                 ts)
            )
            album_id = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?",
                (artist_id, title)
            ).fetchone()[0]

        # Update aoty-specific scores/url only if still empty
        mh_conn.execute("""
            UPDATE albums SET
              aoty_url          = COALESCE(aoty_url,          ?),
              aoty_critic_score = COALESCE(aoty_critic_score, ?),
              aoty_user_score   = COALESCE(aoty_user_score,   ?),
              cover_url         = COALESCE(cover_url,         ?),
              last_updated      = ?
            WHERE id=?
        """, (album.get("aoty_url", ""),
              album.get("aoty_critic_score"),
              album.get("aoty_user_score"),
              album.get("cover_url", ""),
              ts, album_id))

        # collection_albums: SELECT by (collection_id, album_id) — no UNIQUE constraint
        ca_row = mh_conn.execute(
            "SELECT id FROM collection_albums "
            "WHERE collection_id=? AND album_id=?",
            (coll_id, album_id)
        ).fetchone()
        if not ca_row:
            mh_conn.execute(
                "INSERT INTO collection_albums (collection_id, album_id, rank) "
                "VALUES (?,?,?)",
                (coll_id, album_id, album.get("number", 0))
            )

        # Build merged dict: DB values win over scraped for enriched fields
        merged = dict(album)
        merged["id"] = album_id
        row = mh_conn.execute(
            "SELECT cover_url, yt_id, rateyourmusic_url FROM albums WHERE id=?",
            (album_id,)
        ).fetchone()
        if row:
            if row[0]: merged["cover_url"] = row[0]
            if row[1]: merged["yt_id"]     = row[1]
            if row[2]: merged["rym"]       = row[2]
        result.append(merged)

    # ── 3. Update total ───────────────────────────────────────────────────────
    mh_conn.execute(
        "UPDATE collections SET total_albums=?, last_updated=? WHERE id=?",
        (len(result), ts, coll_id)
    )
    mh_conn.commit()
    print(f"  💾 DB: '{slug}' → {len(result)} álbumes guardados")
    return result


def _yt_search(query: str) -> str:
    """Return first YouTube video ID for query using yt-dlp."""
    r = subprocess.run(
        ["yt-dlp", "--no-playlist", "--get-id", "--quiet",
         f"ytsearch1:{query}"],
        capture_output=True, text=True, timeout=30
    )
    vid = r.stdout.strip()
    return vid if len(vid) == 11 else ""


def mh_aoty_fetch_youtube(mh_conn: sqlite3.Connection,
                           albums: list[dict]) -> None:
    """Fetch YouTube IDs for albums missing yt_id; saves directly to DB."""
    missing = [a for a in albums if not a.get("yt_id")]
    if not missing:
        print(f"  📦 YouTube: todos los álbumes ya tienen vídeo en DB")
        return
    print(f"  🎬 Buscando YouTube IDs para {len(missing)} álbumes (yt-dlp)...")
    ts = int(time.time())
    for i, album in enumerate(missing):
        if i % 25 == 0:
            print(f"    {i}/{len(missing)}...")
        q     = f"{album['artist']} {album['title']} full album"
        yt_id = _yt_search(q)
        if yt_id:
            album["yt_id"] = yt_id
            mh_conn.execute(
                "UPDATE albums SET yt_id=?, last_updated=? WHERE id=?",
                (yt_id, ts, album["id"])
            )
        time.sleep(0.5)
    mh_conn.commit()
    found = sum(1 for a in missing if a.get("yt_id"))
    print(f"  ✅ {found}/{len(missing)} YouTube IDs guardados en DB")


def mh_aoty_fetch_covers(mh_conn: sqlite3.Connection, albums: list[dict],
                          lfm_key: str = "", discogs_token: str = "") -> None:
    """Fetch HD covers for albums missing cover_url; saves to DB.
    Skips albums that already have a cover_url in DB."""
    PLACEHOLDER = "2a96cbd8b46e442fc41c2b86b821562f"
    missing = [a for a in albums if not a.get("cover_url")]
    already = len(albums) - len(missing)
    if already:
        print(f"  📦 Carátulas: {already} ya tienen portada en DB, {len(missing)} a buscar")
    if not missing:
        return

    ts = int(time.time())
    updated = 0
    for i, album in enumerate(missing, 1):
        artist = album["artist"]
        title  = album["title"]
        print(f"  [{i}/{len(missing)}] {artist} — {title}", end="  ")
        new_cover = ""

        # Last.fm extralarge/mega
        try:
            api_key = lfm_key or "c9b21e5a749e4f279b6cdce9d5b3a7b3"
            params  = urllib.parse.urlencode({
                "method": "album.getinfo",
                "artist": artist, "album": title,
                "api_key": api_key, "format": "json",
            })
            req = urllib.request.Request(
                f"https://ws.audioscrobbler.com/2.0/?{params}",
                headers={"User-Agent": "AOTYTracker/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            for img in reversed(data.get("album", {}).get("image", [])):
                src = img.get("#text", "")
                if src and PLACEHOLDER not in src:
                    new_cover = src
                    break
        except Exception:
            pass
        time.sleep(0.25)

        # Discogs fallback
        if not new_cover and discogs_token:
            try:
                q = urllib.parse.urlencode({"q": f"{artist} {title}", "type": "release", "per_page": "1"})
                req = urllib.request.Request(
                    f"https://api.discogs.com/database/search?{q}",
                    headers={
                        "User-Agent":    "AOTYTracker/1.0",
                        "Authorization": f"Discogs token={discogs_token}",
                    },
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
            album["cover_url"] = new_cover
            mh_conn.execute(
                "UPDATE albums SET cover_url=?, last_updated=? WHERE id=?",
                (new_cover, ts, album["id"])
            )
            updated += 1
            print("🖼")
        else:
            print("—")

    mh_conn.commit()
    print(f"  ✅ {updated}/{len(missing)} carátulas nuevas guardadas en DB")


# ── YOUTUBE ───────────────────────────────────────────────────────────────────

def aoty_fetch_youtube(albums: list[dict], cache_dir: Path, force: bool = False) -> dict:
    """Pre-fetch YouTube video IDs for AOTY albums.
    Cache key: norm(artist)|||norm(title)  (no mbid available).
    Returns dict key → video_id (str, '' if not found)."""
    yt_cache_path = cache_dir / "aoty_youtube_cache.json"
    if yt_cache_path.exists() and not force:
        cached = json.loads(yt_cache_path.read_text())
        missing = [a for a in albums
                   if (_norm(a["artist"]) + "|||" + _norm(a["title"])) not in cached
                   or cached[_norm(a["artist"]) + "|||" + _norm(a["title"])] == ""]
        if not missing:
            found = sum(1 for v in cached.values() if v)
            print(f"  📦 YouTube caché: {found}/{len(cached)} con vídeo")
            return cached
        print(f"  📦 YouTube caché parcial: {len(cached)} OK, {len(missing)} a buscar")
    else:
        cached = {}
        missing = albums

    print(f"  🎬 Buscando {len(missing)} vídeos en YouTube (yt-dlp)...")
    for i, album in enumerate(missing):
        key = _norm(album["artist"]) + "|||" + _norm(album["title"])
        if i % 25 == 0:
            print(f"    {i}/{len(missing)}...")
        q        = f"{album['artist']} {album['title']} full album"
        cached[key] = _yt_search(q)
        time.sleep(0.5)

    yt_cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    found = sum(1 for v in cached.values() if v)
    print(f"  💾 {yt_cache_path} ({found}/{len(cached)} encontrados)")
    return cached


# ── COVERS ────────────────────────────────────────────────────────────────────

def aoty_fetch_covers(albums: list[dict], cache_dir: Path,
                      lfm_key: str = "", discogs_token: str = "") -> int:
    """Fetch HD covers via Last.fm (extralarge) and optionally Discogs.
    AOTY already provides 600px CDN covers; this goes higher when possible.
    Updates album['cover_url'] in-place and persists cache.
    Returns number of covers updated."""
    cover_cache_path = cache_dir / "aoty_covers_cache.json"
    cache = json.loads(cover_cache_path.read_text()) if cover_cache_path.exists() else {}
    PLACEHOLDER = "2a96cbd8b46e442fc41c2b86b821562f"

    updated = 0
    for album in albums:
        key = _norm(album["artist"]) + "|||" + _norm(album["title"])
        if cache.get(key):
            album["cover_url"] = cache[key]
            continue

        artist = album["artist"]
        title  = album["title"]
        new_cover = ""

        # ── Strategy 1: Last.fm album.getInfo (extralarge ~300px, sometimes mega ~500px) ──
        try:
            api_key = lfm_key or "c9b21e5a749e4f279b6cdce9d5b3a7b3"
            params  = urllib.parse.urlencode({
                "method": "album.getinfo",
                "artist": artist, "album": title,
                "api_key": api_key, "format": "json",
            })
            req = urllib.request.Request(
                f"https://ws.audioscrobbler.com/2.0/?{params}",
                headers={"User-Agent": "AOTYTracker/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            images = data.get("album", {}).get("image", [])
            for img in reversed(images):
                src = img.get("#text", "")
                if src and PLACEHOLDER not in src:
                    new_cover = src
                    break
        except Exception:
            pass
        time.sleep(0.25)

        # ── Strategy 2: Discogs search ──
        if not new_cover and discogs_token:
            try:
                q = urllib.parse.urlencode({"q": f"{artist} {title}", "type": "release", "per_page": "1"})
                req = urllib.request.Request(
                    f"https://api.discogs.com/database/search?{q}",
                    headers={
                        "User-Agent":    "AOTYTracker/1.0",
                        "Authorization": f"Discogs token={discogs_token}",
                    },
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
            album["cover_url"] = new_cover
            cache[key] = new_cover
            updated += 1
            print(f"    🖼  {artist} — {title}")

    cover_cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return updated


# ── MAIN RUNNER ────────────────────────────────────────────────────────────────

def run_aoty(args, root_dir: Path) -> None:
    """
    Main entry point. Called from html_must_hear.py or standalone.
    args attributes used:
      - must_hear_db / _aoty_mh_conn : must_hear.db connection or path
      - scrobbles_db / db            : scrobbles SQLite DB path
      - aoty_decades                 : list of decade strings or None for all
      - force_scrape                 : bool, re-scrape even if cache exists
      - users                        : list of specific users or None for all
      - youtube                      : bool, pre-fetch YouTube IDs
      - caratulas                    : bool, fetch HD covers
      - lastfm_api_key               : str
      - discogs_token                : str
    """
    out_dir = root_dir / "aoty"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── DB connections ────────────────────────────────────────────────────────
    mh_conn: sqlite3.Connection | None = getattr(args, "_aoty_mh_conn", None)
    if mh_conn is None and getattr(args, "must_hear_db", None):
        p = Path(args.must_hear_db)
        if p.exists():
            mh_conn = sqlite3.connect(str(p))
            mh_conn.execute("PRAGMA journal_mode=WAL")
            mh_conn.execute("PRAGMA synchronous=NORMAL")
            print(f"🗄  must_hear.db: {p}")

    db_path = getattr(args, "scrobbles_db", None) or getattr(args, "db", None)

    # ── Users ─────────────────────────────────────────────────────────────────
    if db_path:
        all_users = _get_users(db_path)
        users = getattr(args, "users", None) or all_users
        print(f"👥 Usuarios: {', '.join(users)}")
    elif mh_conn:
        rows  = mh_conn.execute("SELECT username FROM users ORDER BY username").fetchall()
        users = getattr(args, "users", None) or [r[0] for r in rows]
        print(f"👥 Usuarios (de must_hear.db): {', '.join(users)}")
    else:
        users = []
        print("⚠ Sin DB de scrobbles — sin marcar álbumes escuchados")

    users_heard: dict[str, set] = {}
    for user in users:
        if db_path:
            users_heard[user] = _get_user_albums(db_path, user)
            print(f"  📚 {user}: {len(users_heard[user])} álbumes en scrobbles")
        else:
            users_heard[user] = set()

    # ── Options ───────────────────────────────────────────────────────────────
    target_decades = getattr(args, "aoty_decades",   None) or DECADES
    force_scrape   = getattr(args, "force_scrape",   False)
    do_youtube     = getattr(args, "youtube",        False)
    do_caratulas   = getattr(args, "caratulas",      False)
    lfm_key        = getattr(args, "lastfm_api_key", None) or ""
    discogs_token  = getattr(args, "discogs_token",  "")   or ""

    decades_data: dict[str, list] = {}
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    for decade in target_decades:
        print(f"\n── {decade} ─────────────────────────────────────────────")
        slug = f"aoty_{decade}"

        # 1. Try loading from must_hear.db first
        if mh_conn and not force_scrape:
            db_albums = mh_load_aoty_collection(mh_conn, slug)
            if db_albums:
                print(f"  📦 DB: {len(db_albums)} álbumes desde must_hear.db")
                decades_data[decade] = db_albums
                continue  # skip scraping

        # 2. Scrape from AOTY
        scraped = aoty_fetch_decade(decade, out_dir, force=force_scrape)
        if not scraped:
            print(f"  ⚠ Sin álbumes para {decade}, omitiendo")
            continue

        # 3. Sync to must_hear.db if available
        if mh_conn:
            scraped = mh_sync_aoty_collection(mh_conn, decade, scraped)
        else:
            # Persist to JSON cache
            cache_f = out_dir / f"aoty_{decade}_cache.json"
            cache_f.write_text(json.dumps(scraped, ensure_ascii=False, indent=2))

        decades_data[decade] = scraped

    if not decades_data:
        print("❌ No se generó nada")
        if mh_conn and not getattr(args, "_aoty_mh_conn", None):
            mh_conn.close()
        return

    all_albums = [a for v in decades_data.values() for a in v]

    # ── YouTube (--youtube) ───────────────────────────────────────────────────
    if do_youtube:
        print(f"\n🎬 YouTube IDs...")
        if mh_conn:
            mh_aoty_fetch_youtube(mh_conn, all_albums)
            # Persist updated album dicts to decade caches
            for decade, albums in decades_data.items():
                (out_dir / f"aoty_{decade}_cache.json").write_text(
                    json.dumps(albums, ensure_ascii=False, indent=2))
        else:
            yt_cache = aoty_fetch_youtube(all_albums, out_dir, force=force_scrape)
            for a in all_albums:
                key = _norm(a["artist"]) + "|||" + _norm(a["title"])
                a["yt_id"] = yt_cache.get(key, "")
            for decade, albums in decades_data.items():
                (out_dir / f"aoty_{decade}_cache.json").write_text(
                    json.dumps(albums, ensure_ascii=False, indent=2))
    else:
        # Load existing YouTube cache into album dicts (file-based fallback)
        yt_cache_path = out_dir / "aoty_youtube_cache.json"
        if yt_cache_path.exists() and not mh_conn:
            yt_cache = json.loads(yt_cache_path.read_text())
            for a in all_albums:
                key = _norm(a["artist"]) + "|||" + _norm(a["title"])
                if key in yt_cache:
                    a["yt_id"] = yt_cache[key]

    # ── Carátulas HD (--caratulas) ────────────────────────────────────────────
    if do_caratulas:
        print(f"\n🖼  Carátulas HD...")
        if mh_conn:
            mh_aoty_fetch_covers(mh_conn, all_albums, lfm_key, discogs_token)
            for decade, albums in decades_data.items():
                (out_dir / f"aoty_{decade}_cache.json").write_text(
                    json.dumps(albums, ensure_ascii=False, indent=2))
        else:
            n = aoty_fetch_covers(all_albums, out_dir, lfm_key, discogs_token)
            print(f"  ✅ {n} carátulas actualizadas")
            if n > 0:
                for decade, albums in decades_data.items():
                    (out_dir / f"aoty_{decade}_cache.json").write_text(
                        json.dumps(albums, ensure_ascii=False, indent=2))

    # ── Render HTMLs ──────────────────────────────────────────────────────────
    all_avail = [d for d in DECADES if d in decades_data]
    for decade, albums in decades_data.items():
        html = render_aoty_decade_html(
            decade, albums, users_heard,
            all_decades=all_avail,
            series_name="AOTY Must Hear",
        )
        out_file = out_dir / f"decade_{decade}.html"
        out_file.write_text(html, encoding="utf-8")
        heard_total = sum(
            1 for a in albums
            if any(aoty_check_heard(users_heard.get(u, set()), a) for u in users)
        )
        print(f"  📄 {out_file} ({heard_total}/{len(albums)} heard)")

    # Index
    idx_html = render_aoty_index_html(
        decades_data, users, users_heard, generated
    )
    (out_dir / "index.html").write_text(idx_html, encoding="utf-8")
    print(f"\n📋 Index → {out_dir / 'index.html'}")

    # Update root index (if the function is available — i.e. called from html_must_hear.py)
    try:
        from html_must_hear import update_root_index
        all_albums_flat = [a for v in decades_data.values() for a in v]
        total_albums    = len(all_albums_flat)
        users_index = []
        for u in users:
            heard = sum(1 for a in all_albums_flat if aoty_check_heard(users_heard.get(u, set()), a))
            pct   = round(heard / total_albums * 100, 1) if total_albums else 0
            users_index.append({"user": u, "pct": pct, "total": total_albums, "heard": heard})
        update_root_index(
            root_dir,
            collection_name="AOTY Must Hear",
            slug="aoty",
            users_index=users_index,
            generated=generated,
        )
    except (ImportError, Exception):
        pass  # standalone mode, no root index update

    print(f"\n✅ AOTY done → {out_dir}")


# ── STANDALONE ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AOTY Must Hear — scrape & generate HTML"
    )
    parser.add_argument("--db", default=None,
                        help="Ruta a scrobbles SQLite DB (para marcar álbumes escuchados)")
    parser.add_argument("--out", default="docs/must_hear",
                        help="Directorio raíz de salida (default: docs/must_hear)")
    parser.add_argument("--decade", dest="aoty_decades", nargs="+",
                        metavar="DECADE",
                        help="Décadas a procesar (p.ej. 1960s 1970s). Default: todas")
    parser.add_argument("--force", dest="force_scrape", action="store_true",
                        help="Re-scrapear aunque haya caché")
    parser.add_argument("--users", nargs="*",
                        help="Usuarios específicos (default: todos los del DB)")
    parser.add_argument("--youtube", action="store_true",
                        help="Pre-fetch YouTube video IDs (guarda en aoty_youtube_cache.json)")
    parser.add_argument("--caratulas", action="store_true",
                        help="Buscar carátulas HD via Last.fm y Discogs")
    parser.add_argument("--lastfm-api-key", dest="lastfm_api_key", default=None,
                        help="Last.fm API key (para carátulas)")
    parser.add_argument("--discogs-token", dest="discogs_token", default="",
                        help="Token Discogs (para carátulas HD)")
    args = parser.parse_args()

    # Normalize: --db → args.scrobbles_db for run_aoty compatibility
    args.scrobbles_db = args.db

    run_aoty(args, Path(args.out))


if __name__ == "__main__":
    main()

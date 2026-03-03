#!/usr/bin/env python3
"""
1001 Albums Must Hear — HTML Generator
Scrapes MusicBrainz series, crosses with last.fm scrobbles DB,
generates per-user HTML grids + index.html
"""

import subprocess, json, re, time, argparse, sqlite3
from html import unescape
from pathlib import Path
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
DEFAULT_SERIES = "https://musicbrainz.org/series/4bc2a338-e1d8-4546-8a61-640da8aaf888"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
CAA = "https://coverartarchive.org/release-group"

# ── SCRAPER ───────────────────────────────────────────────────────────────────

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

def fetch_page_with_retry(url: str, retries: int = 10, delay: float = 10.0) -> str:
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
    """Match by normalized (title, artist). Artist match is fuzzy (substring)."""
    a_n = _norm(album["artist"])
    t_n = _norm(album["title"])
    for ua, ut in user_albums:
        if t_n == ut and (not a_n or a_n in ua or ua in a_n):
            return True
    return False

# ── HTML GENERATION ───────────────────────────────────────────────────────────

COVER_PLACEHOLDER = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='250' height='250' viewBox='0 0 250 250'%3E%3Crect width='250' height='250' fill='%23111'/%3E%3Ccircle cx='125' cy='125' r='60' fill='none' stroke='%23333' stroke-width='2'/%3E%3Ccircle cx='125' cy='125' r='8' fill='%23333'/%3E%3C/svg%3E"

def album_to_json(album: dict, heard: bool) -> dict:
    return {
        "n":      album["number"],
        "title":  album["title"],
        "artist": album["artist"],
        "year":   album["year"],
        "mbid":   album["mbid"],
        "heard":  heard,
        "cover":  f"{CAA}/{album['mbid']}/front-250",
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
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
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
  .progress-wrap {{
    flex: 1; min-width: 160px;
  }}
  .progress-bar {{
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
  }}
  .progress-fill {{
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width .6s ease;
    width: {pct}%;
  }}
  .progress-label {{
    font-family: 'DM Mono', monospace;
    font-size: .65rem;
    color: var(--muted);
    margin-top: 4px;
  }}
  .progress-label span {{ color: var(--accent); font-weight: 500; }}

  /* ── CONTROLS ── */
  .controls {{
    display: flex; align-items: center; gap: 10px; margin-left: auto;
  }}
  .filter-btn {{
    font-family: 'DM Mono', monospace;
    font-size: .72rem;
    letter-spacing: .1em;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 3px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: all .15s;
  }}
  .filter-btn:hover {{ border-color: var(--muted); color: var(--text); }}
  .filter-btn.active {{ border-color: var(--accent); color: var(--accent); background: rgba(232,255,71,.06); }}
  .filter-btn.active-pending {{ border-color: var(--pending); color: var(--pending); background: rgba(255,71,71,.06); }}
  .search-box {{
    font-family: 'DM Mono', monospace;
    font-size: .72rem;
    padding: 6px 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    color: var(--text);
    width: 200px;
    outline: none;
    transition: border-color .15s;
  }}
  .search-box:focus {{ border-color: var(--accent); }}
  .search-box::placeholder {{ color: var(--muted); }}

  /* ── GRID ── */
  main {{ padding: 20px 28px 60px; }}
  .count-bar {{
    font-family: 'DM Mono', monospace;
    font-size: .7rem;
    color: var(--muted);
    margin-bottom: 14px;
    display: flex; gap: 16px;
  }}
  .count-bar b {{ color: var(--text); }}

  #grid {{
    display: grid;
    grid-template-columns: repeat(15, 1fr);
    gap: var(--gap);
  }}

  /* ── CARD ── */
  .card {{
    position: relative;
    aspect-ratio: 1;
    border-radius: 3px;
    overflow: hidden;
    cursor: pointer;
    transition: transform .18s, z-index 0s .18s;
  }}
  .card:hover {{
    transform: scale(1.06);
    z-index: 10;
    transition: transform .18s, z-index 0s;
  }}
  .card.hidden {{ display: none; }}

  .card img {{
    width: 100%; height: 100%;
    object-fit: cover;
    display: block;
    background: var(--surface);
  }}

  /* Status dot */
  .card::before {{
    content: '';
    position: absolute; top: 5px; right: 5px;
    width: 8px; height: 8px;
    border-radius: 50%;
    z-index: 3;
  }}
  .card.heard::before  {{ background: var(--heard); box-shadow: 0 0 6px var(--heard); }}
  .card.pending::before {{ background: var(--pending); box-shadow: 0 0 6px var(--pending); }}

  /* Overlay on hover */
  .card-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(0deg, rgba(0,0,0,.88) 0%, rgba(0,0,0,0) 55%);
    opacity: 0;
    transition: opacity .2s;
    display: flex; flex-direction: column; justify-content: flex-end;
    padding: 8px;
    z-index: 2;
  }}
  .card:hover .card-overlay {{ opacity: 1; }}
  .card-num {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: .9rem;
    color: var(--accent);
    line-height: 1;
  }}
  .card-title {{
    font-size: .62rem;
    font-weight: 500;
    color: #fff;
    line-height: 1.3;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }}
  .card-artist {{
    font-size: .58rem;
    color: var(--muted);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  /* Heard overlay */
  .card.heard .card-img-wrap::after {{
    content: '';
    position: absolute; inset: 0;
    background: rgba(232,255,71,.04);
    pointer-events: none;
  }}

  /* ── BACK LINK ── */
  .back-link {{
    font-family: 'DM Mono', monospace;
    font-size: .7rem;
    color: var(--muted);
    text-decoration: none;
    margin-right: 8px;
  }}
  .back-link:hover {{ color: var(--text); }}

  /* ── EMPTY STATE ── */
  #empty {{
    display: none;
    text-align: center;
    padding: 80px 0;
    font-family: 'DM Mono', monospace;
    color: var(--muted);
    font-size: .8rem;
  }}

  @media (max-width: 1200px) {{
    #grid {{ grid-template-columns: repeat(12, 1fr); }}
  }}
  @media (max-width: 900px) {{
    #grid {{ grid-template-columns: repeat(9, 1fr); }}
  }}
  @media (max-width: 600px) {{
    #grid {{ grid-template-columns: repeat(6, 1fr); }}
    header {{ padding: 10px 16px; }}
    main {{ padding: 14px 16px 40px; }}
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
    <button class="filter-btn active-pending" id="btn-pending" onclick="setFilter('pending')" style="border-color:var(--border);color:var(--muted)">Pending</button>
    <input class="search-box" id="search" placeholder="Search…" oninput="applyFilters()">
  </div>
</header>

<main>
  <div class="count-bar">
    <span>Showing <b id="vis-count">{len(albums_data)}</b> of {len(albums_data)} albums</span>
    <span><b id="vis-heard">0</b> heard &middot; <b id="vis-pending">0</b> pending</span>
  </div>
  <div id="grid"></div>
  <div id="empty">No albums match your filters.</div>
</main>

<script>
const ALBUMS = {data_json};
let filter = 'all';

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
      <img src="${{a.cover}}" alt="${{a.n}}"
           loading="lazy"
           onerror="this.src='${COVER_PLACEHOLDER}'">
      <div class="card-overlay">
        <div class="card-num">#${{a.n}}</div>
        <div class="card-title">${{a.title}}</div>
        <div class="card-artist">${{a.artist}} · ${{a.year ?? ''}}</div>
      </div>
    `;
    card.addEventListener('click', () => {{
      window.open(`https://musicbrainz.org/release-group/${{a.mbid}}`, '_blank');
    }});
    grid.appendChild(card);
  }});
  applyFilters();
}}

function setFilter(f) {{
  filter = f;
  document.getElementById('btn-all').classList.toggle('active', f === 'all');
  document.getElementById('btn-heard').classList.toggle('active', f === 'heard');
  document.getElementById('btn-pending').style.borderColor = f === 'pending' ? 'var(--pending)' : 'var(--border)';
  document.getElementById('btn-pending').style.color       = f === 'pending' ? 'var(--pending)' : 'var(--muted)';
  document.getElementById('btn-pending').style.background  = f === 'pending' ? 'rgba(255,71,71,.06)' : 'transparent';
  applyFilters();
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase().trim();
  let vis = 0, visH = 0, visP = 0;
  document.querySelectorAll('.card').forEach(c => {{
    const matchFilter = filter === 'all' || (filter === 'heard' && c.dataset.heard === '1') || (filter === 'pending' && c.dataset.heard === '0');
    const matchSearch = !q || c.dataset.title.includes(q) || c.dataset.artist.includes(q);
    const show = matchFilter && matchSearch;
    c.classList.toggle('hidden', !show);
    if (show) {{
      vis++;
      if (c.dataset.heard === '1') visH++; else visP++;
    }}
  }});
  document.getElementById('vis-count').textContent   = vis;
  document.getElementById('vis-heard').textContent   = visH;
  document.getElementById('vis-pending').textContent = visP;
  document.getElementById('empty').style.display     = vis === 0 ? 'block' : 'none';

  // Update progress for current filter
  if (filter !== 'all' || q) {{
    const pct = vis > 0 ? Math.round(visH / vis * 100) : 0;
    document.getElementById('prog-fill').style.width = pct + '%';
    document.getElementById('prog-pct').textContent  = pct + '%';
  }} else {{
    document.getElementById('prog-fill').style.width = '{pct}%';
    document.getElementById('prog-pct').textContent  = '{pct}%';
  }}
}}

buildGrid();
</script>
</body>
</html>
"""

def render_index_html(users_data: list[dict], series_name: str, generated: str) -> str:
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
  <div class="site-label">Must Hear Tracker</div>
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

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="1001 Albums Must Hear — HTML Generator")
    parser.add_argument("--db",     required=True, help="Ruta a lastfm_cache.db")
    parser.add_argument("--out",    default="docs/must_hear", help="Directorio de salida")
    parser.add_argument("--series", default=DEFAULT_SERIES, help="URL de la serie en MusicBrainz")
    parser.add_argument("--name",   default="1001 Albums You Must Hear Before You Die", help="Nombre de la serie")
    parser.add_argument("--cache",  default="series_cache.json", help="Caché local del scraping")
    parser.add_argument("--users",  nargs="*", help="Usuarios específicos (por defecto todos)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Obtener lista de álbumes
    albums = fetch_series(args.series, Path(args.cache))
    print(f"\n🎵 {len(albums)} álbumes en la serie")

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
            albums_data.append(album_to_json(album, heard))

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

    # 4. Index
    users_index.sort(key=lambda u: u["pct"], reverse=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    index_html = render_index_html(users_index, args.name, generated)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"\n📋 index.html → {out_dir / 'index.html'}")
    print(f"\n🎉 Listo! Abre: {out_dir / 'index.html'}")

if __name__ == "__main__":
    main()

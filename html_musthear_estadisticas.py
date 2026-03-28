#!/usr/bin/env python3
"""
Must Hear — Estadísticas
Genera docs/must_hear/estadisticas.html con estadísticas de escuchas
de todos los usuarios en todas las colecciones.

Usage:
    python3 html_musthear_estadisticas.py
    python3 html_musthear_estadisticas.py --mh-db db/must_hear_rym_new.db
                                           --scr-db db/lastfm_cache_rym_new_normalized.db
                                           --out docs/must_hear/estadisticas.html
"""

import argparse, json, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_MH_DB  = "db/must_hear_rym_new.db"
DEFAULT_SCR_DB = "db/lastfm_cache_rym_new_normalized.db"
DEFAULT_OUT    = "docs/must_hear/estadisticas.html"

USER_COLORS = [
    "#c9a227", "#4fc3f7", "#81c784", "#e57373",
    "#ba68c8", "#ff8a65", "#4db6ac", "#f48fb1",
    "#90a4ae", "#fff176", "#a5d6a7",
]


def _safe(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()


def _coll_group(slug: str, name: str) -> str:
    s = slug.lower()
    if s.startswith("scaruffi"):        return "Scaruffi"
    if s.startswith("aoty"):            return "AOTY"
    if "1001" in s:                     return "1001 Albums"
    if "rolling_stone" in s:            return "Rolling Stone"
    if s.startswith("pitchfork"):       return "Pitchfork"
    if s.startswith("rym_chart"):       return "RYM Charts"
    return "Otras"


# ── data gathering ────────────────────────────────────────────────────────────

def gather_data(mh_path: str, scr_path: str) -> dict:
    conn = sqlite3.connect(mh_path)
    conn.row_factory = sqlite3.Row

    # Users
    users = [dict(r) for r in conn.execute(
        "SELECT id, username, lastfm_username FROM users ORDER BY username"
    ).fetchall()]

    # Collections (only those with heard data)
    colls = [dict(r) for r in conn.execute("""
        SELECT c.id, c.slug, c.name, c.total_albums, c.source_url
        FROM collections c
        WHERE EXISTS (
            SELECT 1 FROM collection_albums ca
            JOIN user_heard uh ON ca.album_id = uh.album_id
            WHERE ca.collection_id = c.id
        )
        ORDER BY c.name
    """).fetchall()]
    for c in colls:
        c["group"] = _coll_group(c["slug"], c["name"])

    coll_ids = [c["id"] for c in colls]

    # Per-user heard count per collection
    rows = conn.execute("""
        SELECT uh.user_id, ca.collection_id, COUNT(DISTINCT uh.album_id) AS n
        FROM user_heard uh
        JOIN collection_albums ca ON uh.album_id = ca.album_id
        GROUP BY uh.user_id, ca.collection_id
    """).fetchall()
    uc_heard = {}  # {user_id: {coll_id: n}}
    for r in rows:
        uc_heard.setdefault(r["user_id"], {})[r["collection_id"]] = r["n"]

    # Total heard per user
    total_heard = {r["user_id"]: r["n"] for r in conn.execute(
        "SELECT user_id, COUNT(*) AS n FROM user_heard GROUP BY user_id"
    ).fetchall()}

    # Total unique heard overall
    total_unique_heard = conn.execute(
        "SELECT COUNT(DISTINCT album_id) FROM user_heard"
    ).fetchone()[0]
    total_albums_db = conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0]

    # Top genres across all heard albums (deduped per album)
    top_genres = [(r["genre"], r["n"]) for r in conn.execute("""
        SELECT g.name AS genre, COUNT(DISTINCT uh.album_id) AS n
        FROM user_heard uh
        JOIN album_genres ag ON uh.album_id = ag.album_id
        JOIN genres g ON ag.genre_id = g.id
        GROUP BY g.id
        ORDER BY n DESC
        LIMIT 25
    """).fetchall()]

    # Top genres per user (top 15 per user)
    genre_by_user = {}
    for r in conn.execute("""
        SELECT uh.user_id, g.name AS genre, COUNT(DISTINCT uh.album_id) AS n
        FROM user_heard uh
        JOIN album_genres ag ON uh.album_id = ag.album_id
        JOIN genres g ON ag.genre_id = g.id
        GROUP BY uh.user_id, g.id
        ORDER BY uh.user_id, n DESC
    """).fetchall():
        lst = genre_by_user.setdefault(r["user_id"], [])
        if len(lst) < 15:
            lst.append((r["genre"], r["n"]))

    # Popular albums
    popular = [dict(r) for r in conn.execute("""
        SELECT a.name AS album, ar.name AS artist, a.year,
               COUNT(DISTINCT uh.user_id) AS n_users,
               GROUP_CONCAT(DISTINCT u.username ORDER BY u.username) AS who
        FROM user_heard uh
        JOIN albums a ON uh.album_id = a.id
        JOIN artists ar ON a.artist_id = ar.id
        JOIN users u ON uh.user_id = u.id
        GROUP BY uh.album_id
        HAVING n_users >= 5
        ORDER BY n_users DESC, a.year
        LIMIT 30
    """).fetchall()]

    # Albums heard by ONLY 1 user (unique discoveries)
    unique_albums = {}
    for r in conn.execute("""
        SELECT u.username, COUNT(*) AS n
        FROM user_heard uh
        JOIN users u ON uh.user_id = u.id
        WHERE uh.album_id NOT IN (
            SELECT album_id FROM user_heard GROUP BY album_id HAVING COUNT(*) > 1
        )
        GROUP BY uh.user_id
    """).fetchall():
        unique_albums[r["username"]] = r["n"]

    conn.close()

    # Temporal progression from scrobbles
    print("  ⏱ Calculando progresión temporal…")
    temporal = gather_temporal(mh_path, scr_path, users)

    return {
        "users":             users,
        "colls":             colls,
        "uc_heard":          {str(k): v for k, v in uc_heard.items()},
        "total_heard":       total_heard,
        "total_unique_heard": total_unique_heard,
        "total_albums_db":   total_albums_db,
        "top_genres":        top_genres,
        "genre_by_user":     {str(k): v for k, v in genre_by_user.items()},
        "popular":           popular,
        "unique_albums":     unique_albums,
        "temporal":          temporal,
    }


def gather_temporal(mh_path: str, scr_path: str, users: list[dict]) -> dict:
    """
    Build cumulative heard-over-time series per user by matching must_hear albums
    to scrobble timestamps (artist+album name, normalized).
    Returns {username: [[timestamp_ms, cumulative_count], ...]}
    """
    if not Path(scr_path).exists():
        return {}

    scr = sqlite3.connect(scr_path)
    mh  = sqlite3.connect(mh_path)

    result = {}
    for user in users:
        username   = user["username"]
        lastfm_u   = user.get("lastfm_username") or username
        table      = f"scrobbles_{_safe(lastfm_u)}"

        exists = scr.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue

        print(f"    {username}…", end=" ", flush=True)
        try:
            # Min timestamp per (artist_norm, album_norm) in scrobbles
            scr_rows = scr.execute(f"""
                SELECT LOWER(TRIM(ar.name)) AS an,
                       LOWER(TRIM(al.name)) AS bn,
                       MIN(s.timestamp) AS ts
                FROM "{table}" s
                JOIN artists ar ON s.artist_id = ar.id
                JOIN albums  al ON s.album_id  = al.id
                WHERE s.timestamp > 0
                GROUP BY ar.id, al.id
            """).fetchall()
            lookup = {(r[0], r[1]): r[2] for r in scr_rows}
        except Exception as e:
            print(f"ERR {e}")
            continue

        # Heard albums for this user in must_hear
        heard = mh.execute("""
            SELECT LOWER(TRIM(ar.name)) AS an,
                   LOWER(TRIM(a.name))  AS bn
            FROM user_heard uh
            JOIN albums  a  ON uh.album_id  = a.id
            JOIN artists ar ON a.artist_id  = ar.id
            WHERE uh.user_id = ?
        """, (user["id"],)).fetchall()

        timestamps = sorted(
            ts for r in heard
            if (ts := lookup.get((r[0], r[1]))) and ts > 0
        )

        matched = len(timestamps)
        print(f"{matched}/{len(heard)} matched")
        if not timestamps:
            continue

        # Downsample to ~200 points for chart performance
        series = [[ts * 1000, i + 1] for i, ts in enumerate(timestamps)]
        if len(series) > 200:
            step   = len(series) / 200
            series = [series[round(i * step)] for i in range(200)]
            series[-1] = [timestamps[-1] * 1000, matched]

        result[username] = series

    scr.close()
    mh.close()
    return result


# ── HTML rendering ────────────────────────────────────────────────────────────

def render_html(data: dict, generated: str) -> str:
    users        = data["users"]
    colls        = data["colls"]
    uc_heard     = {int(k): v for k, v in data["uc_heard"].items()}
    total_heard  = data["total_heard"]
    top_genres   = data["top_genres"]
    genre_by_user = {int(k): v for k, v in data["genre_by_user"].items()}
    popular      = data["popular"]
    temporal     = data["temporal"]
    unique_albums = data["unique_albums"]

    n_users  = len(users)
    n_total  = data["total_unique_heard"]
    n_db     = data["total_albums_db"]

    # Sort users by total heard desc
    users_sorted = sorted(users, key=lambda u: total_heard.get(u["id"], 0), reverse=True)
    user_color   = {u["username"]: USER_COLORS[i % len(USER_COLORS)]
                    for i, u in enumerate(users_sorted)}

    # ── leaderboard chart data ────────────────────────────────────────────────
    lb_labels  = [u["username"] for u in users_sorted]
    lb_values  = [total_heard.get(u["id"], 0) for u in users_sorted]
    lb_colors  = [user_color[u["username"]] for u in users_sorted]

    # ── collection groups completion ──────────────────────────────────────────
    GROUP_ORDER = ["Scaruffi", "AOTY", "1001 Albums", "Rolling Stone",
                   "Pitchfork", "RYM Charts", "Otras"]

    # Build group totals: {group: {album_id}}  and per user
    from collections import defaultdict
    grp_albums = defaultdict(set)         # group → set of album_ids
    grp_uc     = defaultdict(lambda: defaultdict(set))  # group → user_id → set of heard album_ids

    for c in colls:
        g = c["group"]
        # We need album_ids per collection — re-query here with separate conn
    # Skip the re-query; use uc_heard with collection-level data
    # Compute group completion: sum(heard) / sum(total) per user per group
    grp_heard_n  = defaultdict(lambda: defaultdict(int))   # group → user_id → heard count
    grp_total_n  = defaultdict(int)                         # group → total albums (unique)

    coll_by_id = {c["id"]: c for c in colls}
    for uid, cdict in uc_heard.items():
        for cid, heard in cdict.items():
            if cid in coll_by_id:
                g = coll_by_id[cid]["group"]
                grp_heard_n[g][uid] += heard

    for c in colls:
        grp_total_n[c["group"]] += c["total_albums"]

    groups_present = [g for g in GROUP_ORDER if g in grp_total_n]

    # Datasets for stacked bar chart (completion % per user per group)
    grp_datasets = []
    for u in users_sorted:
        uid  = u["id"]
        vals = []
        for g in groups_present:
            t = grp_total_n[g]
            h = grp_heard_n[g].get(uid, 0)
            vals.append(round(h / t * 100, 1) if t else 0)
        grp_datasets.append({
            "label":           u["username"],
            "data":            vals,
            "backgroundColor": user_color[u["username"]] + "cc",
            "borderColor":     user_color[u["username"]],
            "borderWidth":     1,
        })

    # ── top collections table (top 20 by total heards) ────────────────────────
    coll_total_heard = {}
    for uid, cdict in uc_heard.items():
        for cid, n in cdict.items():
            coll_total_heard[cid] = coll_total_heard.get(cid, 0) + n
    top_colls = sorted(colls, key=lambda c: coll_total_heard.get(c["id"], 0), reverse=True)[:20]

    def pct_cell(pct: float) -> str:
        if pct == 0:
            bg, txt = "#111", "#333"
        elif pct < 25:
            bg, txt = "#1a1500", "#666"
        elif pct < 50:
            bg, txt = "#2e2300", "#999"
        elif pct < 75:
            bg, txt = "#5c4400", "#ccc"
        else:
            bg, txt = "#c9a227", "#000"
        return f'<td style="background:{bg};color:{txt};text-align:center;font-size:.62rem;padding:4px 6px">{pct:.0f}%</td>'

    coll_table_rows = ""
    for c in top_colls:
        row = f'<tr><td class="coll-name"><a href="{c["slug"]}/index.html" style="color:var(--muted);text-decoration:none">{c["name"]}</a></td>'
        row += f'<td class="coll-total">{c["total_albums"]}</td>'
        for u in users_sorted:
            h = uc_heard.get(u["id"], {}).get(c["id"], 0)
            pct = h / c["total_albums"] * 100 if c["total_albums"] else 0
            row += pct_cell(pct)
        row += "</tr>"
        coll_table_rows += row

    coll_header_cells = "".join(
        f'<th style="writing-mode:vertical-rl;transform:rotate(180deg);padding:8px 4px;font-size:.6rem;white-space:nowrap;color:var(--muted)">{u["username"]}</th>'
        for u in users_sorted
    )

    # ── genre chart data ──────────────────────────────────────────────────────
    genre_labels = [g for g, _ in top_genres[:20]]
    genre_values = [n for _, n in top_genres[:20]]

    # Per-user genre radar: top 10 genres overall, values per user
    radar_genres = [g for g, _ in top_genres[:12]]
    radar_max    = max(n for _, n in top_genres[:12]) if top_genres else 1
    radar_datasets = []
    for u in users_sorted:
        uid   = u["id"]
        g_map = dict(genre_by_user.get(uid, []))
        vals  = [g_map.get(g, 0) for g in radar_genres]
        radar_datasets.append({
            "label":           u["username"],
            "data":            vals,
            "backgroundColor": user_color[u["username"]] + "33",
            "borderColor":     user_color[u["username"]],
            "borderWidth":     1.5,
            "pointRadius":     2,
        })

    # ── popular albums table ──────────────────────────────────────────────────
    all_usernames = {u["username"] for u in users}
    popular_rows = ""
    for p in popular:
        who_set = set(p["who"].split(",")) if p.get("who") else set()
        dots = "".join(
            f'<span style="width:8px;height:8px;border-radius:50%;display:inline-block;'
            f'background:{user_color.get(u["username"],"#333")};'
            f'opacity:{1.0 if u["username"] in who_set else 0.1}"'
            f' title="{u["username"]}"></span>'
            for u in users_sorted
        )
        popular_rows += (
            f'<tr>'
            f'<td class="pop-artist">{p["artist"]}</td>'
            f'<td class="pop-album">{p["album"]}</td>'
            f'<td class="pop-year">{p["year"] or "—"}</td>'
            f'<td class="pop-n">{p["n_users"]}/{n_users}</td>'
            f'<td class="pop-dots">{dots}</td>'
            f'</tr>'
        )

    # ── unique discoveries ────────────────────────────────────────────────────
    unique_rows = "".join(
        f'<div class="uniq-row">'
        f'<span class="uniq-user" style="color:{user_color.get(u["username"],"#666")}">{u["username"]}</span>'
        f'<span class="uniq-n">{unique_albums.get(u["username"], 0)}</span>'
        f'</div>'
        for u in users_sorted
    )

    # ── temporal chart data ───────────────────────────────────────────────────
    temporal_datasets = []
    for u in users_sorted:
        series = temporal.get(u["username"])
        if not series:
            continue
        temporal_datasets.append({
            "label":           u["username"],
            "data":            [{"x": pt[0], "y": pt[1]} for pt in series],
            "borderColor":     user_color[u["username"]],
            "backgroundColor": "transparent",
            "borderWidth":     2,
            "pointRadius":     0,
            "tension":         0.3,
        })
    has_temporal = bool(temporal_datasets)

    # ── summary cards ─────────────────────────────────────────────────────────
    total_heards_all = sum(total_heard.values())
    avg_heard = total_heards_all // n_users if n_users else 0

    summary_cards = f"""
    <div class="summary-grid">
      <div class="sum-card">
        <div class="sum-n">{n_users}</div>
        <div class="sum-label">Usuarios</div>
      </div>
      <div class="sum-card">
        <div class="sum-n">{n_total:,}</div>
        <div class="sum-label">Álbumes únicos escuchados</div>
      </div>
      <div class="sum-card">
        <div class="sum-n">{total_heards_all:,}</div>
        <div class="sum-label">Escuchas totales</div>
      </div>
      <div class="sum-card">
        <div class="sum-n">{avg_heard:,}</div>
        <div class="sum-label">Media por usuario</div>
      </div>
    </div>"""

    # ── JSON blobs for Chart.js ───────────────────────────────────────────────
    def jd(obj):
        return json.dumps(obj, ensure_ascii=False)

    temporal_section = ""
    if has_temporal:
        temporal_section = f"""
    <section id="temporal">
      <h2 class="sec-title">Progresión temporal</h2>
      <p class="sec-desc">Álbumes acumulados escuchados a lo largo del tiempo, calculados cruzando las colecciones con los scrobbles de Last.fm.</p>
      <div class="chart-wrap"><canvas id="temporalChart"></canvas></div>
    </section>"""

    temporal_js = ""
    if has_temporal:
        temporal_js = f"""
  new Chart(document.getElementById('temporalChart'), {{
    type: 'line',
    data: {{ datasets: {jd(temporal_datasets)} }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      scales: {{
        x: {{ type: 'time', time: {{ unit: 'year' }}, grid: {{ color: '#1e1e1e' }}, ticks: {{ color: '#555' }} }},
        y: {{ grid: {{ color: '#1e1e1e' }}, ticks: {{ color: '#555' }} }}
      }},
      plugins: {{
        legend: {{ labels: {{ color: '#888', boxWidth: 12, font: {{ size: 11 }} }} }},
        tooltip: {{ mode: 'index', intersect: false }}
      }},
      interaction: {{ mode: 'nearest', axis: 'x', intersect: false }}
    }}
  }});"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Must Hear — Estadísticas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<script defer src="https://cloud.umami.is/script.js" data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<style>
  :root {{
    --bg:#0a0a0a; --surface:#111; --border:#1e1e1e;
    --accent:#c9a227; --muted:#555; --text:#e0e0e0;
    --header-h:52px;
  }}
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; min-height:100vh; }}
  /* header */
  header {{
    position:fixed; top:0; left:0; right:0; z-index:100; height:var(--header-h);
    background:rgba(10,10,10,.97); backdrop-filter:blur(12px);
    border-bottom:1px solid var(--border);
    display:flex; align-items:center; gap:12px; padding:0 24px;
  }}
  /* ── MH unified nav ── */
  .mh-title {{ font-family:'Bebas Neue',sans-serif; font-size:1.1rem; letter-spacing:.1em; color:var(--text); white-space:nowrap; flex-shrink:0; }}
  .mh-nav {{ display:flex; gap:2px; flex-shrink:0; }}
  .mh-na {{ font-family:'DM Mono',monospace; font-size:.6rem; letter-spacing:.07em; text-transform:uppercase; color:var(--muted); text-decoration:none; padding:3px 8px; border-radius:3px; transition:all .12s; }}
  .mh-na:hover {{ color:var(--text); background:rgba(255,255,255,.06); }}
  .mh-na.on {{ color:var(--accent); background:rgba(255,255,255,.04); }}
  .mh-usr {{ position:relative; margin-left:auto; flex-shrink:0; }}
  .mh-usr-b {{ display:flex; align-items:center; gap:4px; background:none; border:1px solid var(--border); border-radius:4px; color:var(--muted); font-family:'DM Mono',monospace; font-size:.62rem; padding:4px 9px; cursor:pointer; white-space:nowrap; }}
  .mh-usr-b:hover {{ color:var(--text); border-color:var(--accent); }}
  .mh-usr-d {{ display:none; position:absolute; right:0; top:calc(100% + 5px); background:#0f0f0f; border:1px solid var(--border); border-radius:6px; padding:4px; min-width:130px; z-index:300; box-shadow:0 4px 16px rgba(0,0,0,.5); }}
  .mh-usr-d.open {{ display:block; }}
  .mh-usr-o {{ display:block; padding:4px 10px; border-radius:3px; font-family:'DM Mono',monospace; font-size:.62rem; color:var(--muted); text-decoration:none; cursor:pointer; white-space:nowrap; }}
  .mh-usr-o:hover {{ background:var(--border); color:var(--text); }}
  .mh-usr-o.cur {{ color:var(--accent); }}
  /* layout */
  main {{ margin-top:var(--header-h); padding:32px 40px 80px; max-width:1200px; }}
  section {{ margin-bottom:52px; }}
  .sec-title {{
    font-family:'Bebas Neue',sans-serif; font-size:1.8rem; letter-spacing:.06em;
    color:var(--accent); margin-bottom:6px;
  }}
  .sec-desc {{ font-size:.8rem; color:var(--muted); margin-bottom:20px; line-height:1.5; }}
  /* summary cards */
  .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:12px; margin-bottom:32px; }}
  .sum-card {{ background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:20px 18px; }}
  .sum-n {{ font-family:'Bebas Neue',sans-serif; font-size:2.4rem; color:var(--accent); line-height:1; }}
  .sum-label {{ font-family:'DM Mono',monospace; font-size:.6rem; color:var(--muted); margin-top:4px; text-transform:uppercase; letter-spacing:.1em; }}
  /* charts */
  .chart-wrap {{ position:relative; height:320px; background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:16px; }}
  .chart-wrap.tall {{ height:440px; }}
  .chart-wrap.short {{ height:240px; }}
  /* collection table */
  .coll-table-wrap {{ overflow-x:auto; border:1px solid var(--border); border-radius:6px; }}
  table.coll-table {{ border-collapse:collapse; width:100%; font-family:'DM Mono',monospace; }}
  .coll-table th {{ background:var(--surface); border-bottom:1px solid var(--border); padding:6px 8px; font-size:.6rem; color:var(--muted); text-align:left; }}
  .coll-table td {{ border-bottom:1px solid #161616; }}
  .coll-table .coll-name {{ padding:5px 10px; font-size:.68rem; color:var(--muted); white-space:nowrap; max-width:260px; overflow:hidden; text-overflow:ellipsis; }}
  .coll-table .coll-total {{ padding:5px 8px; font-size:.62rem; color:#444; text-align:right; }}
  .coll-table tr:hover .coll-name {{ color:var(--text); }}
  /* popular albums */
  table.pop-table {{ border-collapse:collapse; width:100%; font-size:.8rem; }}
  .pop-table th {{ font-family:'DM Mono',monospace; font-size:.6rem; color:var(--muted); padding:6px 10px; border-bottom:1px solid var(--border); text-align:left; }}
  .pop-table td {{ padding:7px 10px; border-bottom:1px solid #161616; }}
  .pop-artist {{ color:var(--muted); font-size:.78rem; }}
  .pop-album {{ font-weight:500; }}
  .pop-year {{ font-family:'DM Mono',monospace; font-size:.68rem; color:var(--muted); white-space:nowrap; }}
  .pop-n {{ font-family:'DM Mono',monospace; font-size:.68rem; color:var(--accent); white-space:nowrap; }}
  .pop-dots {{ display:flex; gap:3px; align-items:center; }}
  .pop-table tr:hover {{ background:rgba(255,255,255,.02); }}
  /* unique discoveries */
  .uniq-grid {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .uniq-row {{ background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:12px 16px; display:flex; flex-direction:column; align-items:center; gap:4px; min-width:110px; }}
  .uniq-user {{ font-family:'DM Mono',monospace; font-size:.62rem; text-transform:uppercase; letter-spacing:.06em; }}
  .uniq-n {{ font-family:'Bebas Neue',sans-serif; font-size:2rem; color:var(--text); line-height:1; }}
  /* two-column layout */
  .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  footer {{ padding:24px 40px; border-top:1px solid var(--border); font-family:'DM Mono',monospace; font-size:.65rem; color:var(--muted); }}
  @media (max-width:900px) {{
    main, footer {{ padding-left:16px; padding-right:16px; }}
    .two-col {{ grid-template-columns:1fr; }}
  }}
</style>
</head>
<body>
<header>
  <div class="mh-title">Estadísticas</div>
  <nav class="mh-nav">
    <a class="mh-na" href="index.html">Colección</a>
    <a class="mh-na" href="index_alternativo.html">Explorador</a>
    <a class="mh-na" href="rym_genre_tree.html">Géneros RYM</a>
    <a class="mh-na on" href="estadisticas.html">Estadísticas</a>
  </nav>
  <div class="mh-usr">
    <button class="mh-usr-b" id="mhUBtn">👤 <span id="mhULbl">—</span></button>
    <div class="mh-usr-d" id="mhUDd"></div>
  </div>
</header>
<main>

  <!-- summary -->
  <section id="resumen">
    <h2 class="sec-title">Resumen global</h2>
    {summary_cards}
    <div class="chart-wrap short">
      <canvas id="lbChart"></canvas>
    </div>
  </section>

  <!-- collection groups -->
  <section id="colecciones">
    <h2 class="sec-title">Progreso por colección</h2>
    <p class="sec-desc">% de álbumes escuchados por usuario en las 20 colecciones con más escuchas. Colores: 0% negro · &lt;25% oscuro · &lt;50% dorado oscuro · &lt;75% dorado medio · ≥75% dorado.</p>
    <div class="coll-table-wrap">
      <table class="coll-table">
        <thead>
          <tr>
            <th>Colección</th>
            <th style="text-align:right">Álb.</th>
            {coll_header_cells}
          </tr>
        </thead>
        <tbody>{coll_table_rows}</tbody>
      </table>
    </div>
    <br>
    <div class="chart-wrap tall">
      <canvas id="grpChart"></canvas>
    </div>
  </section>

  <!-- genres -->
  <section id="generos">
    <h2 class="sec-title">Géneros más escuchados</h2>
    <p class="sec-desc">Géneros más frecuentes en el total de álbumes escuchados (sin duplicar por usuario).</p>
    <div class="two-col">
      <div class="chart-wrap"><canvas id="genreChart"></canvas></div>
      <div class="chart-wrap"><canvas id="radarChart"></canvas></div>
    </div>
  </section>

  <!-- popular albums -->
  <section id="popular">
    <h2 class="sec-title">Álbumes más compartidos</h2>
    <p class="sec-desc">Álbumes de las colecciones escuchados por más usuarios. Los puntos indican qué usuarios lo han escuchado.</p>
    <table class="pop-table">
      <thead>
        <tr><th>Artista</th><th>Álbum</th><th>Año</th><th>Usuarios</th><th></th></tr>
      </thead>
      <tbody>{popular_rows}</tbody>
    </table>
  </section>

  <!-- unique discoveries -->
  <section id="descubrimientos">
    <h2 class="sec-title">Descubrimientos únicos</h2>
    <p class="sec-desc">Álbumes de las colecciones escuchados solo por ese usuario (nadie más los ha marcado).</p>
    <div class="uniq-grid">{unique_rows}</div>
  </section>

{temporal_section}

</main>
<footer>Generado {generated} · Datos de MusicBrainz, Last.fm, RYM &amp; Scaruffi</footer>

<script>
Chart.defaults.color = '#555';
Chart.defaults.borderColor = '#1e1e1e';

// Leaderboard
new Chart(document.getElementById('lbChart'), {{
  type: 'bar',
  data: {{
    labels: {jd(lb_labels)},
    datasets: [{{
      label: 'Álbumes escuchados',
      data: {jd(lb_values)},
      backgroundColor: {jd(lb_colors)},
      borderRadius: 3,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{
      label: ctx => ` ${{ctx.raw.toLocaleString()}} álbumes`
    }} }} }},
    scales: {{
      x: {{ grid: {{ color: '#1e1e1e' }}, ticks: {{ color: '#555' }} }},
      y: {{ grid: {{ display: false }}, ticks: {{ color: '#aaa', font: {{ size: 11 }} }} }}
    }}
  }}
}});

// Groups completion
new Chart(document.getElementById('grpChart'), {{
  type: 'bar',
  data: {{
    labels: {jd(groups_present)},
    datasets: {jd(grp_datasets)}
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ labels: {{ color: '#888', boxWidth: 10, font: {{ size: 10 }} }} }},
      tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.raw}}%` }} }}
    }},
    scales: {{
      x: {{ stacked: false, grid: {{ color: '#1e1e1e' }}, ticks: {{ color: '#777' }} }},
      y: {{
        max: 100,
        ticks: {{ color: '#555', callback: v => v + '%' }},
        grid: {{ color: '#1e1e1e' }}
      }}
    }}
  }}
}});

// Genre bar
new Chart(document.getElementById('genreChart'), {{
  type: 'bar',
  data: {{
    labels: {jd(genre_labels)},
    datasets: [{{
      label: 'Álbumes',
      data: {jd(genre_values)},
      backgroundColor: '#c9a22799',
      borderColor: '#c9a227',
      borderWidth: 1,
      borderRadius: 2,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: '#1e1e1e' }}, ticks: {{ color: '#555' }} }},
      y: {{ grid: {{ display: false }}, ticks: {{ color: '#888', font: {{ size: 10 }} }} }}
    }}
  }}
}});

// Genre radar
new Chart(document.getElementById('radarChart'), {{
  type: 'radar',
  data: {{
    labels: {jd(radar_genres)},
    datasets: {jd(radar_datasets)}
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{
      r: {{
        grid: {{ color: '#222' }},
        angleLines: {{ color: '#222' }},
        pointLabels: {{ color: '#666', font: {{ size: 9 }} }},
        ticks: {{ display: false }}
      }}
    }},
    plugins: {{
      legend: {{ labels: {{ color: '#888', boxWidth: 10, font: {{ size: 10 }} }} }}
    }}
  }}
}});

{temporal_js}

// ── MH user switcher ──────────────────────────────────────────────────────
(function() {{
  const KEY = 'mh_user';
  const stored = localStorage.getItem(KEY);
  const lbl = document.getElementById('mhULbl');
  if (stored && lbl) lbl.textContent = stored;
  const btn = document.getElementById('mhUBtn');
  const dd  = document.getElementById('mhUDd');
  if (!btn || !dd) return;
  btn.addEventListener('click', e => {{ e.stopPropagation(); dd.classList.toggle('open'); }});
  document.addEventListener('click', () => dd.classList.remove('open'));
  if (stored) dd.innerHTML = `<span class="mh-usr-o cur">${{stored}}</span>`;
}})();
</script>
</body>
</html>
"""


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Genera estadísticas de Must Hear")
    ap.add_argument("--mh-db",  default=DEFAULT_MH_DB,  metavar="PATH", help="Must Hear DB")
    ap.add_argument("--scr-db", default=DEFAULT_SCR_DB, metavar="PATH", help="Scrobbles DB (para temporal)")
    ap.add_argument("--out",    default=DEFAULT_OUT,    metavar="PATH", help="HTML de salida")
    args = ap.parse_args()

    if not Path(args.mh_db).exists():
        print(f"❌ DB not found: {args.mh_db}")
        return

    print(f"📊 Must Hear Estadísticas")
    print(f"   DB:  {args.mh_db}")
    print(f"   Scr: {args.scr_db}")

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data = gather_data(args.mh_db, args.scr_db)

    html = render_html(data, generated)
    out  = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✅ {out}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()

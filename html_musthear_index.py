#!/usr/bin/env python3
"""
Must Hear Alternative Index Generator

Reads must_hear_rym_new.db and generates:
  docs/must_hear/data/mh_index.json   — compact data for client-side filtering
  docs/must_hear/index_alternativo.html — multi-filter browser page

Usage:
  python3 html_musthear_index.py [--must-hear-db db/must_hear_rym_new.db]
                                  [--scrobbles-db db/lastfm_cache_rym_new_normalized.db]
                                  [--out docs/must_hear]
                                  [--top-genres 50]
"""

import argparse, json, os, re, sqlite3, sys
from pathlib import Path
from datetime import datetime

# ── COLLECTION GROUPS ─────────────────────────────────────────────────────────
# Maps slug prefix → (group_slug, group_name)
# Order determines display order in the filter panel.
GROUPS = [
    ("scaruffi",   lambda s: s.startswith("scaruffi_"),           "Scaruffi"),
    ("aoty",       lambda s: s.startswith("aoty_"),               "AOTY"),
    ("sputnik",    lambda s: s.startswith("sputnik_"),            "Sputnikmusic"),
    ("rym_charts", lambda s: s.startswith("rym_chart_"),          "RYM Charts"),
    ("pitchfork",  lambda s: s.startswith("pitchfork_"),          "Pitchfork"),
    ("kerrang",    lambda s: s.startswith("kerrang_"),            "Kerrang!"),
    ("bandcamp",   lambda s: s.startswith("bandcamp_"),           "Bandcamp"),
    ("grammy",     lambda s: s.startswith("grammy_"),             "Grammy"),
    ("1001",       lambda s: s == "1001_albums_you_must_hear_before_you_die", "1001 Albums"),
    ("rolling_stone", lambda s: s.startswith("rolling_stone_"),  "Rolling Stone"),
    ("juno",       lambda s: s.startswith("juno_"),               "Juno Awards"),
    ("ra",         lambda s: s.startswith("resident_advisor"),    "Resident Advisor"),
    ("rym_lists",  lambda s: True,                                 "RYM Lists"),  # catch-all
]

def _group_for(slug: str) -> tuple[str, str]:
    for gslug, test, gname in GROUPS:
        if test(slug):
            return gslug, gname
    return "other", "Other"


def _norm_genre(name: str) -> str:
    """Lowercase and strip genre name for deduplication."""
    return name.strip().lower()


def _canon_genre(names: list[str]) -> str:
    """Pick canonical (title-cased) form from a group of same-normalised genre names."""
    # prefer the one with most initial caps
    best = sorted(names, key=lambda n: sum(1 for c in n if c.isupper()), reverse=True)
    return best[0]


# ── DATA EXTRACTION ───────────────────────────────────────────────────────────

def build_data(mh_path: str, scr_path: str | None, top_genres: int) -> dict:
    conn = sqlite3.connect(mh_path)
    conn.row_factory = sqlite3.Row

    # ── Users ─────────────────────────────────────────────────────────────────
    users = [
        {"id": r["id"], "name": r["username"]}
        for r in conn.execute("SELECT id, username FROM users ORDER BY username")
    ]
    uid_to_idx = {u["id"]: i for i, u in enumerate(users)}

    # ── Collections ──────────────────────────────────────────────────────────
    coll_rows = conn.execute(
        "SELECT id, slug, name, source_type FROM collections"
    ).fetchall()
    coll_by_id: dict[int, dict] = {}
    groups_meta: dict[str, dict] = {}

    for r in coll_rows:
        gslug, gname = _group_for(r["slug"])
        entry = {
            "id":        r["id"],
            "slug":      r["slug"],
            "name":      r["name"],
            "group":     gslug,
            "group_name": gname,
        }
        coll_by_id[r["id"]] = entry
        if gslug not in groups_meta:
            groups_meta[gslug] = {"slug": gslug, "name": gname, "total": 0}

    # ── Genres — normalise + pick top N ──────────────────────────────────────
    genre_rows = conn.execute(
        "SELECT g.id, g.name, COUNT(ag.album_id) as cnt "
        "FROM genres g JOIN album_genres ag ON g.id=ag.genre_id "
        "GROUP BY g.id"
    ).fetchall()

    # Group by normalised name
    norm_map: dict[str, list] = {}
    for r in genre_rows:
        n = _norm_genre(r["name"])
        norm_map.setdefault(n, []).append((r["id"], r["name"], r["cnt"]))

    # Collapse and take top N
    merged: list[tuple] = []  # (norm, canon_name, total_cnt, [ids])
    for n, entries in norm_map.items():
        canon = _canon_genre([e[1] for e in entries])
        total = sum(e[2] for e in entries)
        ids   = [e[0] for e in entries]
        merged.append((n, canon, total, ids))
    merged.sort(key=lambda x: x[2], reverse=True)
    top_merged = merged[:top_genres]

    # genre_id → compact index (0-based)
    gid_to_idx: dict[int, int] = {}
    genres_out: list[dict] = []
    for i, (norm, canon, cnt, ids) in enumerate(top_merged):
        for gid in ids:
            gid_to_idx[gid] = i
        genres_out.append({"i": i, "name": canon, "n": cnt})

    # ── Individual collections → compact index ────────────────────────────────
    # Count albums per collection
    coll_album_counts: dict[int, int] = {}
    for r in conn.execute("SELECT collection_id, COUNT(*) as n FROM collection_albums GROUP BY collection_id"):
        coll_album_counts[r[0]] = r["n"]

    grp_order = {g[0]: i for i, g in enumerate(GROUPS)}
    sorted_colls = sorted(
        coll_by_id.values(),
        key=lambda c: (grp_order.get(c["group"], 99), (c["name"] or "").lower())
    )
    coll_id_to_cidx: dict[int, int] = {}
    collections_out: list[dict] = []
    for c in sorted_colls:
        n = coll_album_counts.get(c["id"], 0)
        if n == 0:
            continue
        idx = len(collections_out)
        coll_id_to_cidx[c["id"]] = idx
        collections_out.append({"i": idx, "slug": c["slug"], "name": c["name"], "group": c["group"], "n": n})

    # ── Albums ────────────────────────────────────────────────────────────────
    # Load album→collections (with rank)
    alb_colls: dict[int, list[tuple]] = {}  # album_id → [(collection_id, rank_or_None)]
    for r in conn.execute("SELECT album_id, collection_id, rank FROM collection_albums"):
        alb_colls.setdefault(r[0], []).append((r[1], r[2]))

    # Load album→genres (top genres only)
    alb_genres: dict[int, list[int]] = {}
    for r in conn.execute("SELECT album_id, genre_id FROM album_genres"):
        idx = gid_to_idx.get(r[1])
        if idx is not None:
            alb_genres.setdefault(r[0], set()).add(idx)

    # Load user_heard
    alb_heard: dict[int, list[int]] = {}
    for r in conn.execute("SELECT user_id, album_id FROM user_heard"):
        uidx = uid_to_idx.get(r[0])
        if uidx is not None:
            alb_heard.setdefault(r[1], []).append(uidx)

    # Main album query — only albums in at least one collection
    _acols = {r[1] for r in conn.execute("PRAGMA table_info(albums)")}
    def _dcol(col, alias):
        return f"COALESCE(a.{col}, '') as {alias}" if col in _acols else f"'' as {alias}"
    album_rows = conn.execute(f"""
        SELECT a.id, a.name, ar.name as artist, a.year, a.cover_url,
               a.rateyourmusic_url, a.sputnikmusic_url, a.aoty_url,
               COALESCE(a.yt_id, '') as yt_id,
               {_dcol('desc_lfm_album',  'd_la')},
               {_dcol('desc_lfm_artist', 'd_ar')},
               {_dcol('desc_mb_album',   'd_ma')},
               {_dcol('desc_mb_artist',  'd_mr')}
        FROM albums a
        JOIN artists ar ON ar.id = a.artist_id
        WHERE a.id IN (SELECT DISTINCT album_id FROM collection_albums)
        ORDER BY a.id
    """).fetchall()

    albums_out = []
    coll_id_to_gslug = {c["id"]: c["group"] for c in coll_by_id.values()}

    for r in album_rows:
        aid    = r["id"]
        colls  = alb_colls.get(aid, [])
        if not colls:
            continue
        year   = r["year"]
        decade = (year // 10) * 10 if year else None
        genres = sorted(alb_genres.get(aid, []))
        heard  = alb_heard.get(aid, [])
        # Collect unique group slugs this album belongs to
        coll_groups = list({coll_id_to_gslug.get(cid) for cid, _ in colls if coll_id_to_gslug.get(cid)})
        # Collect [collection_idx, rank_or_null] pairs sorted by idx
        coll_pairs = sorted(
            ([coll_id_to_cidx[cid], rank] for cid, rank in colls if cid in coll_id_to_cidx),
            key=lambda p: p[0]
        )
        cover = r["cover_url"] or ""
        # Pick best external URL for the album link
        url = r["rateyourmusic_url"] or r["aoty_url"] or r["sputnikmusic_url"] or ""

        def _trunc(s, n=500): return (s[:n] + "…") if s and len(s) > n else (s or "")

        albums_out.append({
            "id":  aid,
            "t":   r["name"],
            "a":   r["artist"],
            "y":   year,
            "d":   decade,
            "c":   cover,
            "u":   url,
            "yt":  r["yt_id"],
            "co":  coll_groups,
            "cs":  coll_pairs,
            "g":   genres,
            "h":   heard,
            "dla": _trunc(r["d_la"]),   # Last.fm album desc
            "dma": _trunc(r["d_ma"]),   # MusicBrainz album desc
            "dar": _trunc(r["d_ar"]),   # Last.fm artist desc
            "dmr": _trunc(r["d_mr"]),   # MusicBrainz artist desc
        })

        # Update group totals (count unique albums)
        for gs in coll_groups:
            if gs in groups_meta:
                groups_meta[gs]["total"] += 1

    # ── Collection groups list for filter panel ───────────────────────────────
    groups_out = [
        {"slug": v["slug"], "name": v["name"], "n": v["total"]}
        for v in groups_meta.values()
        if v["total"] > 0
    ]
    # Sort by display order defined in GROUPS
    order = {g[0]: i for i, g in enumerate(GROUPS)}
    groups_out.sort(key=lambda g: order.get(g["slug"], 99))

    # ── Decades ───────────────────────────────────────────────────────────────
    decade_counts: dict[int, int] = {}
    for a in albums_out:
        if a["d"]:
            decade_counts[a["d"]] = decade_counts.get(a["d"], 0) + 1
    decades_out = [
        {"d": d, "label": f"{d}s", "n": n}
        for d, n in sorted(decade_counts.items())
        if 1900 <= d <= 2030
    ]

    conn.close()
    return {
        "users":       users,
        "groups":      groups_out,
        "collections": collections_out,
        "genres":      genres_out,
        "decades":     decades_out,
        "albums":      albums_out,
        "generated":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ── HTML TEMPLATE ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Must Hear — Explorador</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">
<style>
:root {
  --bg:       #0a0a0a;
  --surface:  #111111;
  --surface2: #1a1a1a;
  --border:   #222222;
  --text:     #e0e0e0;
  --muted:    #555555;
  --accent:   #c9a227;
  --heard:    #c9a227;
  --pending:  #cc4444;
  --radius:   3px;
  --panel-w:  340px;
  --aside-w:  240px;
  --header-h: 52px;
  --mono: 'DM Mono', monospace;
  --display: 'Bebas Neue', sans-serif;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ── Header ── */
header {
  height: var(--header-h);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 14px;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}
.header-title {
  font-family: var(--display);
  font-size: 1.5rem;
  letter-spacing: .06em;
  color: var(--accent);
  white-space: nowrap;
}
.header-sub {
  font-family: var(--mono);
  font-size: .6rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--muted);
  flex: 1;
}
#statusBar {
  font-family: var(--mono);
  font-size: .65rem;
  color: var(--muted);
  white-space: nowrap;
  margin-left: auto;
}

/* ── User filter panel (sidebar) ── */
.user-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 6px; border-radius: 3px; cursor: pointer;
  transition: background .1s;
}
.user-row:hover { background: rgba(255,255,255,.04); }
.user-row.sel { background: rgba(255,255,255,.04); }
.user-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  opacity: .25; transition: opacity .15s;
}
.user-row.sel .user-dot { opacity: 1; }
.user-row-name {
  font-family: var(--mono); font-size: .72rem; color: var(--muted);
  transition: color .15s; flex: 1;
}
.user-row.sel .user-row-name { color: var(--text); }

/* ── Body layout: sidebar | grid | detail panel ── */
.body-wrap {
  flex: 1;
  display: grid;
  grid-template-columns: var(--aside-w) 1fr var(--panel-w);
  overflow: hidden;
  min-height: 0;
}

/* ── Left sidebar ── */
aside {
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.filter-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 12px 10px 0;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.filter-scroll::-webkit-scrollbar { width: 3px; }
.filter-scroll::-webkit-scrollbar-thumb { background: var(--border); }
.filter-footer {
  padding: 10px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
#filterBtn {
  width: 100%;
  padding: .5rem;
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: var(--radius);
  font-family: var(--mono);
  font-size: .72rem;
  font-weight: 500;
  letter-spacing: .12em;
  text-transform: uppercase;
  cursor: pointer;
  transition: opacity .15s;
}
#filterBtn:hover { opacity: .85; }
#filterBtn:disabled { opacity: .35; cursor: default; }

/* ── Filter panels ── */
.panel { margin-bottom: 1.2rem; }
.panel-title {
  font-family: var(--mono);
  font-size: .55rem;
  font-weight: 500;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--muted);
  padding-bottom: .4rem;
  margin-bottom: .5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title.collapsible { cursor: pointer; user-select: none; }
.panel-title.collapsible:hover { color: var(--text); }
.collapse-arrow {
  font-size: .6rem; margin-left: auto; flex-shrink: 0;
  transform: rotate(-90deg); transition: transform .18s;
}
.collapse-arrow.open { transform: rotate(0deg); }
.panel-body-collapse { overflow: hidden; max-height: 0; transition: max-height .22s ease; }
.panel-body-collapse.open { max-height: 2000px; }
.panel-clear {
  font-size: .55rem;
  letter-spacing: .06em;
  color: var(--border);
  cursor: pointer;
  border: none;
  background: none;
  padding: 0;
  font-family: var(--mono);
  text-transform: none;
}
.panel-clear:hover { color: var(--accent); }
.chip-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 240px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.chip-list::-webkit-scrollbar { width: 2px; }
.chip {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 7px;
  border-radius: var(--radius);
  cursor: pointer;
  border: 1px solid transparent;
  transition: all .12s;
  user-select: none;
  font-size: .75rem;
}
.chip:hover { background: var(--surface2); border-color: var(--border); }
.chip.sel { background: var(--surface2); border-color: var(--accent); color: var(--accent); }
.chip-check {
  width: 13px; height: 13px;
  border: 1px solid var(--border);
  border-radius: 2px;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px;
  transition: all .12s;
}
.chip.sel .chip-check { background: var(--accent); border-color: var(--accent); color: #000; }
.chip-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chip-count { font-family: var(--mono); font-size: .62rem; color: var(--muted); flex-shrink: 0; }
.chip.sel .chip-count { color: var(--accent); opacity: .8; }

/* ── Collection tree ── */
.coll-tree { display: flex; flex-direction: column; gap: 2px; }
.cgroup-row {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 7px; border-radius: var(--radius);
  cursor: pointer; user-select: none;
  border: 1px solid transparent; transition: all .12s;
  font-size: .75rem;
}
.cgroup-row:hover { background: var(--surface2); border-color: var(--border); }
.cgroup-row.sel { border-color: var(--accent); color: var(--accent); background: var(--surface2); }
.cgroup-row.partial { border-color: rgba(201,162,39,.4); color: rgba(201,162,39,.7); }
.cgroup-check {
  width: 13px; height: 13px; border: 1px solid var(--border); border-radius: 2px;
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 9px; transition: all .12s;
}
.cgroup-row.sel .cgroup-check { background: var(--accent); border-color: var(--accent); color: #000; }
.cgroup-row.partial .cgroup-check { background: rgba(201,162,39,.2); border-color: rgba(201,162,39,.4); color: var(--accent); font-size: 8px; }
.cgroup-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.cgroup-count { font-family: var(--mono); font-size: .62rem; color: var(--muted); flex-shrink: 0; cursor: pointer; padding: 2px 4px; border-radius: 3px; }
.cgroup-count:hover { color: var(--text); }
.cgroup-arrow {
  font-size: .7rem; color: var(--muted); flex-shrink: 0;
  transition: transform .15s; width: 18px; height: 18px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 3px; cursor: pointer;
}
.cgroup-arrow:hover { color: var(--accent); background: rgba(201,162,39,.08); }
.cgroup-arrow.open { transform: rotate(90deg); }
.cgroup-series {
  display: none; flex-direction: column; gap: 1px;
  padding: 2px 0 4px 20px;
}
.cgroup-series.open { display: flex; }
.cseries-row {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 7px; border-radius: var(--radius);
  cursor: pointer; user-select: none;
  border: 1px solid transparent; transition: all .12s;
  font-size: .7rem; color: var(--muted);
}
.cseries-row:hover { background: var(--surface2); color: var(--text); border-color: var(--border); }
.cseries-row.sel { border-color: rgba(201,162,39,.4); color: var(--accent); background: rgba(201,162,39,.05); }
.cseries-check {
  width: 11px; height: 11px; border: 1px solid var(--border); border-radius: 2px;
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 8px; transition: all .12s;
}
.cseries-row.sel .cseries-check { background: rgba(201,162,39,.3); border-color: var(--accent); color: var(--accent); }
.cseries-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cseries-count { font-family: var(--mono); font-size: .6rem; color: var(--border); flex-shrink: 0; }
.decade-list { display: flex; flex-wrap: wrap; gap: 4px; }
.decade-chip {
  padding: 3px 9px;
  border-radius: 12px;
  cursor: pointer;
  border: 1px solid var(--border);
  font-family: var(--mono);
  font-size: .66rem;
  transition: all .12s;
  user-select: none;
  color: var(--muted);
}
.decade-chip:hover { border-color: var(--accent); color: var(--accent); }
.decade-chip.sel { background: var(--accent); border-color: var(--accent); color: #000; font-weight: 500; }
.status-btns { display: flex; gap: 4px; }
.status-btn {
  flex: 1; padding: 5px 4px;
  font-family: var(--mono); font-size: .62rem; letter-spacing: .06em;
  text-transform: uppercase; cursor: pointer;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: transparent; color: var(--muted);
  transition: all .12s;
}
.status-btn:hover { border-color: var(--accent); color: var(--accent); }
.status-btn.sel { background: var(--accent); border-color: var(--accent); color: #000; font-weight: 500; }

/* ── Grid ── */
#gridArea {
  overflow-y: auto;
  padding: 12px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
#gridArea::-webkit-scrollbar { width: 3px; }
#results {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
}
.album-card {
  background: var(--surface);
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
  transition: border-color .15s, transform .12s;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}
.album-card:hover { border-color: #444; transform: translateY(-1px); }
.album-card.active-card { border-color: var(--accent); }
.album-card.heard-card { border-color: var(--accent); }
.cover-wrap { position: relative; aspect-ratio: 1; overflow: hidden; background: var(--surface2); }
.cover-wrap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.cover-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 2rem; color: var(--border); }
.badge-group {
  position: absolute; top: 4px; right: 4px;
  display: flex; flex-direction: column; gap: 2px; align-items: flex-end;
}
.u-badge {
  width: 8px; height: 8px; border-radius: 50%;
  opacity: .22; transition: opacity .12s;
}
.u-badge.heard { opacity: 1; box-shadow: 0 0 4px currentColor; }
.card-info { padding: 6px 7px; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.card-title {
  font-size: .75rem; font-weight: 600; line-height: 1.2;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.card-artist { font-size: .68rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#loading { padding: 3rem; text-align: center; color: var(--muted); font-family: var(--mono); font-size: .75rem; display: none; }
#moreBtn {
  display: none; margin: 1rem auto; padding: .45rem 1.6rem;
  background: var(--surface2); color: var(--muted);
  border: 1px solid var(--border); border-radius: var(--radius);
  cursor: pointer; font-family: var(--mono); font-size: .68rem;
}
#moreBtn:hover { border-color: var(--accent); color: var(--accent); }

/* ── Right detail panel ── */
#panel {
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex; flex-direction: column;
  overflow: hidden;
  position: relative;
}
.panel-topbar {
  height: 40px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 14px; flex-shrink: 0;
}
.panel-topbar-label {
  font-family: var(--mono); font-size: .55rem;
  letter-spacing: .2em; text-transform: uppercase; color: var(--muted);
}
.panel-cover {
  width: 100%; aspect-ratio: 1; flex-shrink: 0;
  position: relative; background: var(--surface2);
  max-height: 200px; overflow: hidden;
}
.panel-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.panel-cover-status {
  position: absolute; bottom: 7px; left: 7px;
  font-family: var(--mono); font-size: .55rem;
  letter-spacing: .14em; text-transform: uppercase;
  padding: 2px 7px; border-radius: 2px;
}
.panel-cover-status.heard   { background: var(--heard); color: #000; }
.panel-cover-status.pending { background: var(--pending); color: #fff; }
.panel-body {
  flex: 1; overflow-y: auto; padding: 14px;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
}
.panel-body::-webkit-scrollbar { width: 3px; }
.panel-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.panel-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 8px;
  font-family: var(--mono); font-size: .7rem; color: var(--muted); text-align: center;
}
.panel-empty-icon { font-size: 1.8rem; opacity: .2; margin-bottom: 4px; }
.panel-num    { font-family: var(--mono); font-size: .58rem; color: var(--accent); letter-spacing: .15em; margin-bottom: 3px; }
.panel-title-t { font-family: var(--display); font-size: 1.4rem; letter-spacing: .04em; color: var(--text); line-height: 1.05; margin-bottom: 2px; }
.panel-artist-t { font-size: .78rem; color: var(--muted); margin-bottom: 2px; }
.panel-year-t { font-family: var(--mono); font-size: .62rem; color: var(--muted); margin-bottom: 12px; }
.panel-genres { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 14px; }
.panel-genre-tag {
  font-family: var(--mono); font-size: .58rem;
  padding: 2px 8px; border-radius: 2px;
  background: rgba(201,162,39,.07); border: 1px solid rgba(201,162,39,.2);
  color: rgba(201,162,39,.7); letter-spacing: .04em;
}
.panel-divider { height: 1px; background: var(--border); margin: 12px 0; }
.panel-links { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.panel-link {
  font-family: var(--mono); font-size: .58rem;
  letter-spacing: .08em; text-transform: uppercase;
  padding: 3px 9px; border-radius: 2px;
  border: 1px solid var(--border); color: var(--muted);
  text-decoration: none; transition: all .12s;
}
.panel-link:hover { border-color: var(--text); color: var(--text); }
.panel-link.rym   { border-color: #5baadb; color: #5baadb; }
.panel-link.aoty  { border-color: #7b61ff; color: #7b61ff; }
.panel-link.sp    { border-color: #e8671b; color: #e8671b; }
.panel-section-label {
  font-family: var(--mono); font-size: .55rem;
  letter-spacing: .18em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px;
}
.panel-collections { display: flex; flex-wrap: wrap; gap: 4px; }
.panel-coll-tag {
  font-family: var(--mono); font-size: .56rem;
  padding: 2px 6px; border-radius: 2px;
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--muted); text-decoration: none;
  display: inline-flex; align-items: center; gap: 4px;
}
a.panel-coll-tag:hover { border-color: var(--accent); color: var(--accent); }
.panel-coll-rank {
  color: var(--accent); font-weight: 600; font-size: .58rem;
}
.panel-yt-wrap {
  margin-top: 14px; border-radius: 3px; overflow: hidden;
  background: var(--surface2); border: 1px solid var(--border);
}
.panel-yt-wrap iframe { display: block; width: 100%; height: 150px; border: none; }
.panel-yt-search {
  height: 60px; display: flex; align-items: center; justify-content: center;
}
.panel-yt-search a {
  font-family: var(--mono); font-size: .62rem; color: var(--accent);
  text-decoration: none; letter-spacing: .06em;
}
.panel-yt-search a:hover { text-decoration: underline; }
.panel-desc-block { margin-bottom: 10px; }
.panel-desc-label {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--mono); font-size: .52rem; letter-spacing: .12em;
  text-transform: uppercase; margin-bottom: 3px; color: var(--muted);
}
.panel-desc-label::before {
  content: ''; display: inline-block; width: 5px; height: 5px;
  border-radius: 50%; background: currentColor; flex-shrink: 0;
}
.panel-desc-label.lfm    { color: #d51007; }
.panel-desc-label.mb     { color: #ba478f; }
.panel-desc-label.artist { color: #6a9fb5; }
.panel-desc-text {
  font-size: .72rem; color: #aaa; line-height: 1.55;
  word-break: break-word;
}

/* ── Header nav ── */
.header-nav { display: flex; gap: 4px; margin-left: 10px; }
.header-nav-link {
  font-family: var(--mono);
  font-size: .58rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  color: var(--muted);
  text-decoration: none;
  transition: all .12s;
}
.header-nav-link:hover { border-color: var(--accent); color: var(--accent); }
.header-nav-link.active { border-color: var(--accent); color: var(--accent); background: rgba(201,162,39,.08); }

/* ── Para Ti (reco) buttons in sidebar ── */
.reco-btn {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 5px 6px; border-radius: 3px; cursor: pointer;
  background: none; border: none; text-align: left;
  font-family: var(--mono); font-size: .72rem; color: var(--muted);
  transition: background .1s, color .1s;
}
.reco-btn:hover { background: rgba(255,255,255,.04); color: var(--text); }
.reco-btn.active { background: rgba(255,255,255,.04); color: var(--text); }
.reco-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; opacity: .4; }
.reco-btn.active .reco-dot { opacity: 1; }
{{MH_MODAL_CSS}}

/* ── Welcome screen ── */
.welcome-msg {
  grid-column: 1/-1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 5rem 2rem; text-align: center; gap: 16px;
}
.welcome-icon { font-size: 3rem; opacity: .12; }
.welcome-title { font-family: var(--display); font-size: 1.8rem; letter-spacing: .06em; color: var(--accent); }
.welcome-body { font-family: var(--mono); font-size: .72rem; color: var(--muted); line-height: 2; max-width: 380px; }
.welcome-body strong { color: var(--text); }

/* ── Sidebar collection search ── */
.sidebar-search-wrap {
  padding: 8px 10px; border-bottom: 1px solid var(--border); flex-shrink: 0;
}
#sidebar-search {
  width: 100%; padding: 6px 10px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text);
  font-family: var(--mono); font-size: .72rem; outline: none;
  transition: border-color .12s;
}
#sidebar-search::placeholder { color: var(--muted); }
#sidebar-search:focus { border-color: var(--accent); }

/* ── RYM chart genre tree ── */
.rym-tree-row {
  display: flex; align-items: center; gap: 5px;
  padding: 3px 7px; border-radius: var(--radius);
  border: 1px solid transparent; transition: all .12s;
  font-size: .7rem; color: var(--muted); user-select: none;
}
.rym-tree-row.has-chart { cursor: pointer; }
.rym-tree-row.has-chart:hover { background: var(--surface2); color: var(--text); border-color: var(--border); }
.rym-tree-row.sel { border-color: rgba(201,162,39,.4); color: var(--accent); background: rgba(201,162,39,.05); }
.rym-tree-row.no-chart { font-weight: 500; font-size: .68rem; margin-top: 5px; cursor: default; }
.rym-tree-check {
  width: 11px; height: 11px; border: 1px solid var(--border); border-radius: 2px;
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 8px; transition: all .12s; visibility: hidden;
}
.rym-tree-row.has-chart .rym-tree-check { visibility: visible; }
.rym-tree-row.sel .rym-tree-check { background: rgba(201,162,39,.3); border-color: var(--accent); color: var(--accent); }
.rym-tree-caret { font-size: .5rem; color: var(--muted); flex-shrink: 0; width: 10px; text-align: center; cursor: pointer; }
.rym-tree-caret.open { transform: rotate(90deg); }
.rym-tree-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rym-tree-count { font-family: var(--mono); font-size: .6rem; color: var(--border); flex-shrink: 0; }
.rym-tree-children { display: none; flex-direction: column; gap: 0; }
.rym-tree-children.open { display: flex; }

/* ── Responsive ── */
#sidebar-toggle {
  display: none;
  position: fixed; bottom: 22px; left: 16px; z-index: 300;
  width: 50px; height: 50px;
  background: var(--accent); color: #000;
  border: none; border-radius: 50%;
  font-size: 1.25rem; cursor: pointer;
  align-items: center; justify-content: center;
  box-shadow: 0 3px 16px rgba(0,0,0,.7);
}
#sidebar-overlay {
  display: none; position: fixed; inset: 0; z-index: 190;
  background: rgba(0,0,0,.55);
}
#sidebar-overlay.vis { display: block; }
#panel-close-btn {
  display: none; background: none; border: 1px solid #444; border-radius: 4px;
  color: #bbb; padding: 3px 12px; cursor: pointer; font-size: .9rem;
  margin-left: auto; transition: color .12s, border-color .12s; flex-shrink: 0;
}
#panel-close-btn:hover { color: var(--accent); border-color: var(--accent); }
@media (max-width: 900px) {
  :root { --panel-w: 0px; --aside-w: 0px; }
  .body-wrap { grid-template-columns: 1fr; }
  /* Sidebar: fixed slide-in drawer */
  #sidebar {
    display: flex;
    position: fixed;
    top: var(--header-h); left: 0; bottom: 0;
    width: 280px;
    transform: translateX(-105%);
    transition: transform .25s ease;
    z-index: 200;
    box-shadow: 4px 0 20px rgba(0,0,0,.6);
  }
  #sidebar.open { transform: translateX(0); }
  #sidebar-toggle { display: flex; }
  /* Detail panel: full-screen slide-up from below header */
  #panel {
    display: flex;
    position: fixed;
    top: var(--header-h); left: 0; right: 0; bottom: 0;
    z-index: 400;
    transform: translateY(105%);
    transition: transform .28s ease;
  }
  #panel.mobile-open { transform: translateY(0); }
  #panel-close-btn { display: flex; align-items: center; }
  /* Header: horizontal scroll for nav links */
  header { overflow-x: auto; flex-wrap: nowrap; gap: 8px; }
  header::-webkit-scrollbar { display: none; }
  .header-nav { flex-wrap: nowrap; flex-shrink: 0; }
  .header-title, #statusBar { flex-shrink: 0; }
}
</style>
</head>
<body>
{{MH_MODAL_HTML}}
<header>
  <div class="header-title">Must Hear</div>
  <nav class="header-nav">
    <a class="header-nav-link active" href="index_alternativo.html">Explorador</a>
    <a class="header-nav-link" href="index.html">Colección</a>
    <a class="header-nav-link" href="rym_genre_tree.html">Géneros</a>
    <a class="header-nav-link" href="estadisticas.html">Estadísticas</a>
  </nav>
  <div id="statusBar">Cargando…</div>
  {{MH_MODAL_BTN}}
</header>

<button id="sidebar-toggle" onclick="toggleSidebar()">&#9776;</button>
<div id="sidebar-overlay" onclick="closeSidebar()"></div>

<div class="body-wrap">

  <!-- ── Left sidebar ── -->
  <aside id="sidebar">
    <div class="sidebar-search-wrap">
      <input id="sidebar-search" type="text" placeholder="Buscar colección…" autocomplete="off" oninput="filterSidebar(this.value)">
    </div>
    <div class="filter-scroll">
      <div class="panel">
        <div class="panel-title collapsible" data-target="panel-co">
          Colección
          <button class="panel-clear" data-panel="co">limpiar</button>
          <span class="collapse-arrow open">▾</span>
        </div>
        <div class="coll-tree panel-body-collapse open" id="panel-co"></div>
      </div>
      <div class="panel" id="reco-panel" style="display:none">
        <div class="panel-title collapsible" data-target="reco-user-btns">
          Recomendaciones
          <button class="panel-clear" data-panel="reco">limpiar</button>
          <span class="collapse-arrow open">▾</span>
        </div>
        <div class="panel-body-collapse open" id="reco-user-btns"></div>
      </div>
      <div class="panel">
        <div class="panel-title collapsible" data-target="panel-g">
          Género
          <button class="panel-clear" data-panel="g">limpiar</button>
          <span class="collapse-arrow">▾</span>
        </div>
        <div class="chip-list panel-body-collapse" id="panel-g"></div>
      </div>
      <div class="panel">
        <div class="panel-title collapsible" data-target="panel-d">
          Fecha
          <button class="panel-clear" data-panel="d">limpiar</button>
          <span class="collapse-arrow">▾</span>
        </div>
        <div class="decade-list panel-body-collapse" id="panel-d"></div>
      </div>
      <div class="panel">
        <div class="panel-title collapsible" data-target="panel-status">
          Estado
          <span class="collapse-arrow open">▾</span>
        </div>
        <div class="status-btns panel-body-collapse open" id="panel-status">
          <button class="status-btn sel" data-status="all">Todos</button>
          <button class="status-btn" data-status="heard">Escuchados</button>
          <button class="status-btn" data-status="pending">Pendientes</button>
        </div>
      </div>
    </div>
    <div class="filter-footer">
      <button id="filterBtn" disabled>Filtrar</button>
    </div>
  </aside>

  <!-- ── Album grid ── -->
  <div id="gridArea">
    <div id="loading">⏳ Cargando datos…</div>
    <div id="results"></div>
    <button id="moreBtn">Mostrar más</button>
  </div>

  <!-- ── Right detail panel ── -->
  <aside id="panel">
    <div class="panel-topbar">
      <span class="panel-topbar-label">Album detail</span>
      <button id="panel-close-btn" onclick="closeDetailPanel()">✕</button>
    </div>
    <div id="panel-cover-wrap" class="panel-cover" style="display:none">
      <img id="p-cover" src="" alt="">
      <span class="panel-cover-status" id="p-status"></span>
    </div>
    <div class="panel-body" id="panel-body">
      <div class="panel-empty">
        <div class="panel-empty-icon">◉</div>
        Selecciona un álbum para ver detalles
      </div>
    </div>
  </aside>

</div>

<script>
const DATA_URL = '{{DATA_URL}}';
const PAGE_SIZE = 80;
const RYM_GENRE_TREE = {{GENRE_TREE}};

const USER_COLORS = ['#c9a227','#6a9fb5','#78b56c','#b56c6c','#9b6cb5','#b59b6c','#6cb5b5','#b56ca0'];

let DB = null;
let selUsers      = new Set();  // selected user indices
let selCs         = new Set();  // selected collection indices (individual series)
let selG          = new Set();
let selD          = new Set();
let selStatus     = 'all';      // 'all' | 'heard' | 'pending'
let primaryUserIdx = -1;        // index into DB.users for primary user
let recoUser       = null;      // user index to filter "heard by them, not by primary"
let filtered = [];
let page = 0;
let currentAlbumId = null;

// ── Load data ──────────────────────────────────────────────────────────────
document.getElementById('loading').style.display = 'block';
fetch(DATA_URL)
  .then(r => r.json())
  .then(data => {
    DB = data;
    document.getElementById('loading').style.display = 'none';
    buildFilters();
    initPrimaryUser();
    document.getElementById('filterBtn').disabled = false;
    showWelcome();
  })
  .catch(e => {
    document.getElementById('loading').textContent = '❌ Error: ' + e;
    document.getElementById('loading').style.display = 'block';
  });

// ── RYM genre chart tree renderer ──────────────────────────────────────────
function buildRymChartPanel(nodes, container, indent, lookup) {
  nodes.forEach(node => {
    const info = lookup[node.s];
    const hasChart = node.h && info !== undefined;
    const hasKids  = node.c && node.c.length > 0;

    const wrap = document.createElement('div');

    const row = document.createElement('div');
    row.className = 'rym-tree-row ' + (hasChart ? 'has-chart' : 'no-chart');
    row.style.paddingLeft = (7 + indent * 14) + 'px';

    const check  = document.createElement('div');  check.className  = 'rym-tree-check';
    const caret  = document.createElement('span'); caret.className  = 'rym-tree-caret';
    caret.textContent = hasKids ? '▶' : '';
    const label  = document.createElement('span'); label.className  = 'rym-tree-label';
    label.textContent = node.n;
    const count  = document.createElement('span'); count.className  = 'rym-tree-count';
    if (hasChart && info.n) count.textContent = info.n.toLocaleString();

    row.dataset.name = node.n;
    row.dataset.slug = node.s;
    row.appendChild(check);
    row.appendChild(caret);
    row.appendChild(label);
    if (hasChart) row.appendChild(count);
    wrap.appendChild(row);

    if (hasKids) {
      const childEl = document.createElement('div');
      childEl.className = 'rym-tree-children';
      buildRymChartPanel(node.c, childEl, indent + 1, lookup);
      wrap.appendChild(childEl);

      caret.style.cursor = 'pointer';
      const toggleKids = (e) => {
        e.stopPropagation();
        const open = childEl.classList.toggle('open');
        caret.classList.toggle('open', open);
      };
      caret.addEventListener('click', toggleKids);
      if (!hasChart) row.addEventListener('click', toggleKids);
    }

    if (hasChart) {
      const ci = info.ci;
      row.addEventListener('click', (e) => {
        e.stopPropagation();
        if (selCs.has(ci)) { selCs.delete(ci); row.classList.remove('sel'); check.textContent = ''; }
        else               { selCs.add(ci);    row.classList.add('sel');    check.textContent = '✓'; }
      });
    }

    container.appendChild(wrap);
  });
}

// ── Filters ────────────────────────────────────────────────────────────────
function buildFilters() {
  // ── Collection tree ──
  // Group collections by group slug, preserving group order from DB.groups
  const groupOrder = DB.groups.map(g => g.slug);
  const collsByGroup = {};
  DB.groups.forEach(g => { collsByGroup[g.slug] = []; });
  DB.collections.forEach(c => {
    if (!collsByGroup[c.group]) collsByGroup[c.group] = [];
    collsByGroup[c.group].push(c);
  });

  // Build lookup: genre_slug → {ci, n} for RYM chart collections
  const chartSlugToInfo = {};
  DB.collections.forEach(c => {
    if (c.group === 'rym_charts') {
      const gs = c.slug.replace('rym_chart_all_time_', '').replace(/_/g, '-');
      chartSlugToInfo[gs] = { ci: c.i, n: c.n };
    }
  });

  const tree = document.getElementById('panel-co');
  DB.groups.forEach(g => {
    const series = collsByGroup[g.slug] || [];
    // Group header row
    const row = document.createElement('div');
    row.className = 'cgroup-row';
    row.dataset.name = g.name;
    row.dataset.slug = g.slug;
    row.innerHTML = `<div class="cgroup-check"></div><span class="cgroup-label">${esc(g.name)}</span><span class="cgroup-count">${g.n.toLocaleString()}</span><span class="cgroup-arrow">▶</span>`;
    const check  = row.querySelector('.cgroup-check');
    const arrow  = row.querySelector('.cgroup-arrow');

    // Series container (initially hidden)
    const seriesEl = document.createElement('div');
    seriesEl.className = 'cgroup-series';

    // Indices of all series in this group
    const groupIdxs = series.map(c => c.i);

    // Update group row state based on selection
    function updateGroupState() {
      const selCount = groupIdxs.filter(i => selCs.has(i)).length;
      row.classList.remove('sel', 'partial');
      check.textContent = '';
      if (selCount === 0) { /* nothing */ }
      else if (selCount === groupIdxs.length) { row.classList.add('sel'); check.textContent = '✓'; }
      else { row.classList.add('partial'); check.textContent = '–'; }
    }

    // Group header click: toggle all series in this group
    row.addEventListener('click', (e) => {
      if (g.slug === 'rym_charts') return;  // tree nodes handle their own selection
      // Left part (not arrow) toggles selection
      const allSel = groupIdxs.every(i => selCs.has(i));
      groupIdxs.forEach(i => allSel ? selCs.delete(i) : selCs.add(i));
      // Update individual series rows
      seriesEl.querySelectorAll('.cseries-row').forEach((sr, si) => {
        const idx = groupIdxs[si];
        if (selCs.has(idx)) { sr.classList.add('sel'); sr.querySelector('.cseries-check').textContent = '✓'; }
        else                { sr.classList.remove('sel'); sr.querySelector('.cseries-check').textContent = ''; }
      });
      updateGroupState();
    });

    // Arrow or count click: toggle expand (stop propagation so group click doesn't fire)
    function toggleExpand(e) {
      e.stopPropagation();
      const open = seriesEl.classList.toggle('open');
      arrow.classList.toggle('open', open);
    }
    arrow.addEventListener('click', toggleExpand);
    row.querySelector('.cgroup-count').addEventListener('click', toggleExpand);

    // Individual series rows (or RYM genre tree)
    if (g.slug === 'rym_charts' && RYM_GENRE_TREE && RYM_GENRE_TREE.length) {
      buildRymChartPanel(RYM_GENRE_TREE, seriesEl, 0, chartSlugToInfo);
    } else {
      series.forEach(c => {
        const sr = document.createElement('div');
        sr.className = 'cseries-row';
        sr.dataset.name = c.name;
        sr.dataset.slug = c.slug;
        sr.innerHTML = `<div class="cseries-check"></div><span class="cseries-label">${esc(c.name)}</span><span class="cseries-count">${c.n.toLocaleString()}</span>`;
        const sc = sr.querySelector('.cseries-check');
        sr.addEventListener('click', (e) => {
          e.stopPropagation();
          if (selCs.has(c.i)) { selCs.delete(c.i); sr.classList.remove('sel'); sc.textContent = ''; }
          else                { selCs.add(c.i);    sr.classList.add('sel');    sc.textContent = '✓'; }
          updateGroupState();
        });
        seriesEl.appendChild(sr);
      });
    }

    tree.appendChild(row);
    if (series.length > 1 || (g.slug === 'rym_charts' && RYM_GENRE_TREE && RYM_GENRE_TREE.length))
      tree.appendChild(seriesEl);
  });

  // ── Genres ──
  DB.genres.forEach(g => {
    document.getElementById('panel-g').appendChild(makeChip(g.i, g.name, g.n, selG));
  });

  // ── Decades ──
  DB.decades.forEach(d => {
    const el = document.createElement('div');
    el.className = 'decade-chip';
    el.textContent = d.label;
    el.addEventListener('click', () => {
      const v = d.d;
      selD.has(v) ? (selD.delete(v), el.classList.remove('sel')) : (selD.add(v), el.classList.add('sel'));
    });
    document.getElementById('panel-d').appendChild(el);
  });
}

function makeChip(val, label, count, set) {
  const el = document.createElement('div');
  el.className = 'chip';
  el.innerHTML = `<div class="chip-check"></div><span class="chip-label">${esc(label)}</span><span class="chip-count">${count.toLocaleString()}</span>`;
  el.addEventListener('click', () => {
    if (set.has(val)) {
      set.delete(val); el.classList.remove('sel'); el.querySelector('.chip-check').textContent = '';
    } else {
      set.add(val); el.classList.add('sel'); el.querySelector('.chip-check').textContent = '✓';
    }
  });
  return el;
}

document.querySelectorAll('.panel-clear').forEach(btn => {
  btn.addEventListener('click', () => {
    const p = btn.dataset.panel;
    if (p === 'co') {
      selCs.clear();
      document.querySelectorAll('#panel-co .cgroup-row').forEach(r => { r.classList.remove('sel','partial'); r.querySelector('.cgroup-check').textContent = ''; });
      document.querySelectorAll('#panel-co .cseries-row').forEach(r => { r.classList.remove('sel'); r.querySelector('.cseries-check').textContent = ''; });
    }
    if (p === 'g')  { selG.clear();  document.querySelectorAll('#panel-g .chip').forEach(c => { c.classList.remove('sel'); c.querySelector('.chip-check').textContent = ''; }); }
    if (p === 'd')  { selD.clear();  document.querySelectorAll('#panel-d .decade-chip').forEach(c => c.classList.remove('sel')); }
    if (p === 'reco') { recoUser = null; updateRecoPanel(); applyFilter(); }
  });
});

document.getElementById('filterBtn').addEventListener('click', applyFilter);

document.querySelectorAll('.status-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    selStatus = btn.dataset.status;
    document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('sel'));
    btn.classList.add('sel');
  });
});

function showWelcome() {
  const container = document.getElementById('results');
  const total = DB ? DB.albums.length : 0;
  container.innerHTML = `
    <div class="welcome-msg">
      <div class="welcome-icon">🎵</div>
      <div class="welcome-title">Must Hear Albums</div>
      <div class="welcome-body">
        <strong>${total}</strong> álbumes cargados.<br>
        Selecciona una <strong>colección</strong> en el panel izquierdo<br>
        o usa los filtros para explorar.<br>
        Haz clic en una portada para ver detalles y vídeos.
      </div>
    </div>`;
  document.getElementById('statusBar').textContent = '';
  document.getElementById('moreBtn').style.display = 'none';
}

function filterSidebar(q) {
  const tokens = q.toLowerCase().trim().split(/[ \t]+/).filter(Boolean);

  function elMatches(el) {
    const name = (el.dataset.name || '').toLowerCase();
    const slug = (el.dataset.slug || '').toLowerCase();
    return tokens.every(t => name.includes(t) || slug.includes(t));
  }

  // Recursively filter a rym-tree wrap div; returns true if this node or any descendant matches.
  function filterRymWrap(wrap) {
    const row      = wrap.querySelector(':scope > .rym-tree-row');
    const childCon = wrap.querySelector(':scope > .rym-tree-children');
    const self     = row ? elMatches(row) : false;
    let anyChild   = false;
    if (childCon) {
      childCon.querySelectorAll(':scope > div').forEach(child => {
        if (filterRymWrap(child)) anyChild = true;
      });
      // Force-open if a descendant matched, restore CSS otherwise
      childCon.style.display = anyChild ? 'flex' : '';
    }
    const visible = self || anyChild;
    wrap.style.display = visible ? '' : 'none';
    return visible;
  }

  // Reset rym-tree to natural state (CSS controls visibility)
  function resetRymWrap(wrap) {
    wrap.style.display = '';
    const childCon = wrap.querySelector(':scope > .rym-tree-children');
    if (childCon) {
      childCon.style.display = '';
      childCon.querySelectorAll(':scope > div').forEach(resetRymWrap);
    }
  }

  // cgroup-row and cgroup-series are siblings directly under #panel-co
  document.querySelectorAll('#panel-co > .cgroup-row').forEach(row => {
    const seriesEl = row.nextElementSibling; // .cgroup-series
    if (tokens.length === 0) {
      row.style.display = '';
      if (seriesEl) {
        seriesEl.style.display = '';
        seriesEl.querySelectorAll('.cseries-row').forEach(r => r.style.display = '');
        seriesEl.querySelectorAll(':scope > div').forEach(resetRymWrap);
      }
      return;
    }
    const groupMatch = elMatches(row);
    let anyChildMatch = false;
    if (seriesEl) {
      // Regular cseries rows
      seriesEl.querySelectorAll(':scope > .cseries-row').forEach(r => {
        const match = groupMatch || elMatches(r);
        r.style.display = match ? '' : 'none';
        if (match) anyChildMatch = true;
      });
      // RYM genre tree wrap divs (direct children that are not cseries-row)
      seriesEl.querySelectorAll(':scope > div:not(.cseries-row)').forEach(wrap => {
        if (groupMatch) { resetRymWrap(wrap); anyChildMatch = true; }
        else if (filterRymWrap(wrap)) anyChildMatch = true;
      });
    }
    const show = groupMatch || anyChildMatch;
    row.style.display = show ? '' : 'none';
    if (seriesEl) seriesEl.style.display = show ? '' : 'none';
  });
}

function applyFilter() {
  if (!DB) return;
  filtered = DB.albums.filter(a => {
    if (selCs.size && !a.cs.some(p => selCs.has(p[0]))) return false;
    if (selG.size  && !a.g.some(gi => selG.has(gi))) return false;
    if (selD.size  && !selD.has(a.d))                return false;
    // Reco filter: heard by secondary user, NOT by primary
    if (recoUser !== null && primaryUserIdx >= 0) {
      if (!a.h.includes(recoUser) || a.h.includes(primaryUserIdx)) return false;
    } else if (selStatus !== 'all') {
      if (selUsers.size === 0) return true; // no users selected — ignore status filter
      const heardBySome = [...selUsers].some(ui => a.h.includes(ui));
      if (selStatus === 'heard'   && !heardBySome) return false;
      if (selStatus === 'pending' &&  heardBySome) return false;
    }
    return true;
  });
  page = 0;
  renderResults(true);
}

// ── Render ─────────────────────────────────────────────────────────────────
function renderResults(reset) {
  const container = document.getElementById('results');
  if (reset) { container.innerHTML = ''; currentAlbumId = null; clearPanel(); }

  const genreMap = Object.fromEntries(DB.genres.map(g => [g.i, g.name]));
  const slice    = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  slice.forEach(a => {
    const heardBySome = selUsers.size > 0 && [...selUsers].some(ui => a.h.includes(ui));
    const card  = document.createElement('div');
    card.className = 'album-card' + (heardBySome ? ' heard-card' : '');
    card.dataset.id = a.id;

    const coverHtml = a.c
      ? `<img src="${thumbUrl(a.c)}" alt="" loading="lazy">`
      : `<div class="cover-placeholder">🎵</div>`;
    const dots = [...selUsers].map(ui =>
      `<div class="u-badge ${a.h.includes(ui) ? 'heard' : ''}" style="background:${USER_COLORS[ui % USER_COLORS.length]}"></div>`
    ).join('');
    const badgeHtml = dots ? `<div class="badge-group">${dots}</div>` : '';
    card.innerHTML = `
      <div class="cover-wrap">${coverHtml}${badgeHtml}</div>
      <div class="card-info">
        <div class="card-title">${esc(a.t)}</div>
        <div class="card-artist">${esc(a.a)}</div>
      </div>`;
    card.addEventListener('click', () => openPanel(a));
    container.appendChild(card);
  });

  const total = filtered.length;
  const shown = Math.min((page + 1) * PAGE_SIZE, total);
  document.getElementById('statusBar').textContent =
    total === 0 ? 'Sin resultados' : `${shown.toLocaleString()} / ${total.toLocaleString()} álbumes`;

  const moreBtn = document.getElementById('moreBtn');
  if (shown < total) {
    moreBtn.style.display = 'block';
    moreBtn.onclick = () => { page++; renderResults(false); };
  } else {
    moreBtn.style.display = 'none';
  }
}

function thumbUrl(url) {
  if (!url) return url;
  return url.replace(/e\\.snmc\\.io\\/i\\/\\d+\\//, 'e.snmc.io/i/150/');
}

// ── Detail panel ───────────────────────────────────────────────────────────
function openPanel(a) {
  currentAlbumId = a.id;
  // Highlight active card
  document.querySelectorAll('.album-card').forEach(c => c.classList.remove('active-card'));
  const activeCard = document.querySelector(`.album-card[data-id="${a.id}"]`);
  if (activeCard) activeCard.classList.add('active-card');

  const genreMap = Object.fromEntries(DB.genres.map(g => [g.i, g.name]));
  const collMap  = Object.fromEntries(DB.collections.map(c => [c.i, {name: c.name, slug: c.slug, group: c.group}]));
  const heardBySome = selUsers.size > 0 && [...selUsers].some(ui => a.h.includes(ui));

  // Cover
  const coverWrap = document.getElementById('panel-cover-wrap');
  if (a.c) {
    document.getElementById('p-cover').src = a.c;
    document.getElementById('p-status').textContent = heardBySome ? 'Heard' : 'Pending';
    document.getElementById('p-status').className = 'panel-cover-status ' + (heardBySome ? 'heard' : 'pending');
    coverWrap.style.display = 'block';
  } else {
    coverWrap.style.display = 'none';
  }

  // Body
  const genres = a.g.map(gi => `<span class="panel-genre-tag">${esc(genreMap[gi] || '')}</span>`).join('');
  const colls  = a.cs.map(([ci, rank]) => {
    const cd = collMap[ci] || {};
    const name = esc(cd.name || '');
    const rankStr = rank != null ? `<span class="panel-coll-rank">#${rank}</span>` : '';
    const href = cd.slug ? `${cd.group}/${cd.slug}/index.html` : null;
    if (href) return `<a class="panel-coll-tag" href="${href}" target="_blank">${rankStr}${name}</a>`;
    return `<span class="panel-coll-tag">${rankStr}${name}</span>`;
  }).join('');

  const links = [];
  if (a.u) {
    const isRym  = a.u.includes('rateyourmusic');
    const isAoty = a.u.includes('albumoftheyear');
    const isSp   = a.u.includes('sputnikmusic');
    const cls    = isRym ? 'rym' : isAoty ? 'aoty' : isSp ? 'sp' : '';
    const label  = isRym ? 'RYM' : isAoty ? 'AOTY' : isSp ? 'Sputnik' : 'Link';
    links.push(`<a class="panel-link ${cls}" href="${a.u}" target="_blank">${label} ↗</a>`);
  }

  const ytQuery = encodeURIComponent(a.a + ' ' + a.t + ' full album');
  const ytSearchUrl = `https://www.youtube.com/results?search_query=${ytQuery}`;
  const lfmArtistUrl = `https://www.last.fm/music/${encodeURIComponent(a.a)}`;
  const rymArtistUrl = `https://rateyourmusic.com/search?searchterm=${encodeURIComponent(a.a)}&searchtype=a`;

  // User heard status row
  const userStatusLine = selUsers.size > 0 ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin:7px 0;font-family:var(--mono);font-size:.6rem;">
    ${[...selUsers].map(ui => {
      const h = a.h.includes(ui);
      const col = USER_COLORS[ui % USER_COLORS.length];
      return `<span style="color:${h ? col : 'var(--muted)'};display:flex;align-items:center;gap:3px">
        <span style="width:7px;height:7px;border-radius:50%;background:${col};display:inline-block;opacity:${h?1:.25}"></span>
        ${esc(DB.users[ui].name)}: ${h ? '✓' : '○'}
      </span>`;
    }).join('')}
  </div>` : '';

  // Description blocks
  const descSources = [
    { key: 'dla', label: '💿 Álbum · Last.fm',         cls: 'lfm' },
    { key: 'dma', label: '💿 Álbum · MusicBrainz',     cls: 'mb' },
    { key: 'dar', label: '🎙 Artista · Last.fm',        cls: 'lfm artist' },
    { key: 'dmr', label: '🎙 Artista · MusicBrainz',   cls: 'mb artist' },
  ];
  const descBlocks = descSources
    .filter(s => a[s.key] && a[s.key].length > 30)
    .map(s => `<div class="panel-desc-block">
      <div class="panel-desc-label ${s.cls}">${s.label}</div>
      <div class="panel-desc-text">${esc(a[s.key])}</div>
    </div>`).join('');
  const descHtml = descBlocks ? `
    <div class="panel-divider"></div>
    <div class="panel-section-label">Información</div>
    ${descBlocks}
  ` : '';

  document.getElementById('panel-body').innerHTML = `
    <div class="panel-title-t">${esc(a.t)}</div>
    <div class="panel-artist-t">${esc(a.a)}</div>
    <div class="panel-year-t">${a.y || ''}${a.d ? ' · ' + a.d + 's' : ''}</div>
    ${userStatusLine}
    ${genres ? `<div class="panel-genres">${genres}</div>` : ''}
    <div class="panel-links">
      ${links.join('')}
      <a class="panel-link" href="${lfmArtistUrl}" target="_blank">Last.fm ↗</a>
      <a class="panel-link rym" href="${rymArtistUrl}" target="_blank">RYM artist ↗</a>
    </div>
    <div class="panel-yt-wrap">
      ${a.yt ? `<iframe src="https://www.youtube.com/embed/${a.yt}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>` : `<div class="panel-yt-search"><a href="${ytSearchUrl}" target="_blank">▶ Buscar en YouTube ↗</a></div>`}
    </div>
    ${descHtml}
    ${colls ? `<div class="panel-divider"></div>
      <div class="panel-section-label">Colecciones</div>
      <div class="panel-collections">${colls}</div>` : ''}
  `;

  // On mobile show panel as full-screen overlay
  if (window.innerWidth <= 900) {
    document.getElementById('panel').classList.add('mobile-open');
    closeSidebar();
  }
}

function clearPanel() {
  document.getElementById('panel-cover-wrap').style.display = 'none';
  document.getElementById('panel-body').innerHTML = `
    <div class="panel-empty">
      <div class="panel-empty-icon">◉</div>
      Selecciona un álbum para ver detalles
    </div>`;
}

// ── Primary user init ──────────────────────────────────────────────────────
function initPrimaryUser() {
  const stored = localStorage.getItem('mh_user');
  if (stored) {
    const pi = DB.users.findIndex(u => u.name === stored);
    if (pi >= 0) {
      primaryUserIdx = pi;
      selUsers = new Set([pi]);
      updateRecoPanel();
    }
  }
}

function setPrimaryUser(username) {
  primaryUserIdx = (username !== null && username !== undefined)
    ? DB.users.findIndex(u => u.name === username) : -1;
  selUsers = primaryUserIdx >= 0 ? new Set([primaryUserIdx]) : new Set();
  recoUser = null;
  updateRecoPanel();
  applyFilter();
}

function updateRecoPanel() {
  const panel = document.getElementById('reco-panel');
  const btns  = document.getElementById('reco-user-btns');
  if (!panel || !btns || !DB) return;
  if (primaryUserIdx < 0) { panel.style.display = 'none'; return; }
  panel.style.display = '';
  btns.innerHTML = '';
  DB.users.forEach((u, i) => {
    if (i === primaryUserIdx) return;
    const col = USER_COLORS[i % USER_COLORS.length];
    const btn = document.createElement('button');
    btn.className = 'reco-btn' + (recoUser === i ? ' active' : '');
    btn.innerHTML = `<span class="reco-dot" style="background:${col}"></span>${esc(u.name)}`;
    btn.onclick = () => {
      recoUser = recoUser === i ? null : i;
      updateRecoPanel();
      applyFilter();
    };
    btns.appendChild(btn);
  });
}

// ── Collapsible panels ─────────────────────────────────────────────────────
document.querySelectorAll('.panel-title.collapsible').forEach(title => {
  title.addEventListener('click', e => {
    if (e.target.closest('.panel-clear')) return;
    const body  = document.getElementById(title.dataset.target);
    const arrow = title.querySelector('.collapse-arrow');
    if (!body) return;
    body.classList.toggle('open');
    if (arrow) arrow.classList.toggle('open');
  });
});

function esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── Mobile sidebar ─────────────────────────────────────────────────────────
function toggleSidebar() {
  const s = document.getElementById('sidebar');
  const o = document.getElementById('sidebar-overlay');
  const open = s.classList.toggle('open');
  o.classList.toggle('vis', open);
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('vis');
}

// ── Mobile detail panel ────────────────────────────────────────────────────
function closeDetailPanel() {
  document.getElementById('panel').classList.remove('mobile-open');
}
</script>
{{MH_MODAL_JS}}
</body>
</html>
"""

def _prune_rym_tree(nodes: list[dict], chart_slugs: set[str]) -> list[dict]:
    """Return compact pruned genre tree keeping nodes that have a chart or chart-descendant."""
    result = []
    for n in nodes:
        cs = "rym_chart_all_time_" + n["slug"].replace("-", "_")
        children = _prune_rym_tree(n.get("subgenres", []), chart_slugs)
        if cs in chart_slugs or children:
            result.append({
                "s": n["slug"],
                "n": n["name"],
                "c": children,
                "h": cs in chart_slugs,  # has a direct chart
            })
    return result


def render_html(data_url: str, users: list = None, genre_tree: list = None) -> str:
    from html_must_hear import _mh_user_modal_css, _mh_user_modal_html, _mh_user_modal_btn, _mh_user_modal_js
    users = users or []
    on_select = "if (u !== null && u !== undefined) setPrimaryUser(u); else setPrimaryUser(null);"
    genre_tree_json = json.dumps(genre_tree or [], ensure_ascii=False, separators=(",", ":"))
    return (HTML_TEMPLATE
            .replace("{{DATA_URL}}", data_url)
            .replace("{{GENRE_TREE}}", genre_tree_json)
            .replace("{{MH_MODAL_CSS}}", _mh_user_modal_css())
            .replace("{{MH_MODAL_HTML}}", _mh_user_modal_html(users))
            .replace("{{MH_MODAL_BTN}}", _mh_user_modal_btn())
            .replace("{{MH_MODAL_JS}}", _mh_user_modal_js(users, on_select_js=on_select)))


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Must Hear Alternative Index Generator")
    parser.add_argument("--must-hear-db",  dest="mh_db",       default="db/must_hear_rym_new.db")
    parser.add_argument("--scrobbles-db",  dest="scr_db",      default=None)
    parser.add_argument("--genres-json",   dest="genres_json",  default=None)
    parser.add_argument("--out",                                default="docs/must_hear")
    parser.add_argument("--top-genres",    dest="top_genres",  type=int, default=50)
    args = parser.parse_args()

    out_dir  = Path(args.out)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if not Path(args.mh_db).exists():
        print(f"❌ DB no encontrada: {args.mh_db}", file=sys.stderr)
        sys.exit(1)

    print(f"📂 DB: {args.mh_db}")
    print(f"📊 Construyendo datos...")
    data = build_data(args.mh_db, args.scr_db, args.top_genres)

    total_albums = len(data["albums"])
    print(f"  🎵 {total_albums} álbumes | {len(data['genres'])} géneros | "
          f"{len(data['groups'])} grupos | {len(data['users'])} usuarios")

    # Load genre tree for RYM chart tree rendering
    rym_genre_tree = None
    if args.genres_json:
        gj = Path(args.genres_json)
    else:
        mh_db = Path(args.mh_db)
        candidates = [
            mh_db.parent.parent / "docs/must_hear/rym_charts/rym_genres.json",
            out_dir / "rym_charts/rym_genres.json",
            mh_db.parent / "rym_genres.json",
        ]
        gj = next((p for p in candidates if p.exists()), None)
    if gj and Path(gj).exists():
        try:
            raw_tree = json.loads(Path(gj).read_text(encoding="utf-8"))
            chart_slugs = {c["slug"] for c in data["collections"] if c["group"] == "rym_charts"}
            rym_genre_tree = _prune_rym_tree(raw_tree, chart_slugs)
            print(f"  🌳 Árbol RYM: {gj}")
        except Exception as e:
            print(f"  ⚠ No se pudo cargar rym_genres.json: {e}", file=sys.stderr)

    json_path = data_dir / "mh_index.json"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    size_kb = json_path.stat().st_size / 1024
    print(f"  💾 JSON: {json_path} ({size_kb:.0f} KB)")

    users = [u["name"] for u in data["users"]]
    html_path = out_dir / "index_alternativo.html"
    html_path.write_text(render_html("data/mh_index.json", users=users, genre_tree=rym_genre_tree), encoding="utf-8")
    print(f"  📋 HTML: {html_path}")
    print(f"✅ Generado: {args.out}/index_alternativo.html")


if __name__ == "__main__":
    main()

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
    album_rows = conn.execute("""
        SELECT a.id, a.name, ar.name as artist, a.year, a.cover_url,
               a.rateyourmusic_url, a.sputnikmusic_url, a.aoty_url,
               COALESCE(a.yt_id, '') as yt_id
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

        albums_out.append({
            "id": aid,
            "t":  r["name"],
            "a":  r["artist"],
            "y":  year,
            "d":  decade,
            "c":  cover,
            "u":  url,
            "yt": r["yt_id"],     # YouTube video ID (may be empty)
            "co": coll_groups,    # list of group slugs (for display in panel)
            "cs": coll_pairs,     # list of [collection_idx, rank_or_null] pairs
            "g":  genres,         # list of genre compact indices
            "h":  heard,          # list of user compact indices
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
}

/* ── Round user button ── */
#userBtn {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: var(--surface2);
  border: 1.5px solid var(--accent);
  color: var(--accent);
  font-family: var(--mono);
  font-size: .7rem;
  font-weight: 500;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s, transform .15s;
  flex-shrink: 0;
  letter-spacing: .04em;
}
#userBtn:hover { background: var(--accent); color: #000; transform: scale(1.06); }

/* ── User modal ── */
.modal-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,.75);
  z-index: 400;
  align-items: center; justify-content: center;
}
.modal-overlay.open { display: flex; }
.modal-box {
  background: var(--surface);
  border: 1px solid var(--border);
  border-top: 2px solid var(--accent);
  border-radius: var(--radius);
  padding: 1.4rem;
  width: min(320px, 92vw);
  max-height: 80vh;
  overflow-y: auto;
}
.modal-title {
  font-family: var(--mono);
  font-size: .6rem;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 1rem;
  text-align: center;
}
.user-opt {
  padding: 9px 12px;
  margin-bottom: 5px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all .15s;
  font-family: var(--mono);
  font-size: .75rem;
  letter-spacing: .04em;
  color: var(--muted);
}
.user-opt:hover { border-color: var(--accent); color: var(--text); }
.user-opt.active { border-color: var(--accent); color: var(--accent); background: rgba(201,162,39,.07); }
.modal-close {
  display: block; margin: 1rem auto 0;
  padding: 6px 18px;
  background: var(--surface2); color: var(--muted);
  border: 1px solid var(--border); border-radius: var(--radius);
  cursor: pointer; font-family: var(--mono); font-size: .68rem;
}
.modal-close:hover { color: var(--text); border-color: var(--border); }

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
.cgroup-count { font-family: var(--mono); font-size: .62rem; color: var(--muted); flex-shrink: 0; }
.cgroup-arrow {
  font-size: .55rem; color: var(--muted); flex-shrink: 0;
  transition: transform .15s; width: 10px; text-align: center;
}
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
  grid-template-columns: repeat(auto-fill, minmax(145px, 1fr));
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
.heard-badge {
  position: absolute; top: 4px; right: 4px;
  width: 20px; height: 20px; border-radius: 50%;
  font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.heard-yes { background: var(--heard); color: #000; box-shadow: 0 0 6px rgba(201,162,39,.5); }
.heard-no  { background: rgba(10,10,10,.8); color: #666; border: 1px solid #333; }
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
.panel-links { display: flex; gap: 6px; flex-wrap: wrap; }
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
  color: var(--muted);
  display: inline-flex; align-items: center; gap: 4px;
}
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
.panel-artist-links { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }

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

/* ── Responsive ── */
@media (max-width: 900px) {
  :root { --panel-w: 0px; }
  #panel { display: none; }
}
@media (max-width: 640px) {
  :root { --aside-w: 0px; }
  aside { display: none; }
  .body-wrap { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<div class="modal-overlay" id="userModal">
  <div class="modal-box">
    <div class="modal-title">Seleccionar usuario</div>
    <div id="userOpts"></div>
    <button class="modal-close" id="modalClose">Cerrar</button>
  </div>
</div>

<header>
  <div class="header-title">Must Hear</div>
  <nav class="header-nav">
    <a class="header-nav-link active" href="index_alternativo.html">Explorador</a>
    <a class="header-nav-link" href="index.html">Colección</a>
    <a class="header-nav-link" href="rym_genre_tree.html">Géneros RYM</a>
    <a class="header-nav-link" href="estadisticas.html">Estadísticas</a>
  </nav>
  <div id="statusBar">Cargando…</div>
  <button id="userBtn" title="Seleccionar usuario">👤</button>
</header>

<div class="body-wrap">

  <!-- ── Left sidebar ── -->
  <aside>
    <div class="filter-scroll">
      <div class="panel">
        <div class="panel-title">
          Colección
          <button class="panel-clear" data-panel="co">limpiar</button>
        </div>
        <div class="coll-tree" id="panel-co"></div>
      </div>
      <div class="panel">
        <div class="panel-title">
          Género
          <button class="panel-clear" data-panel="g">limpiar</button>
        </div>
        <div class="chip-list" id="panel-g"></div>
      </div>
      <div class="panel">
        <div class="panel-title">
          Fecha
          <button class="panel-clear" data-panel="d">limpiar</button>
        </div>
        <div class="decade-list" id="panel-d"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Estado</div>
        <div class="status-btns">
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

let DB = null;
let activeUser = null;
let selCs     = new Set();  // selected collection indices (individual series)
let selG      = new Set();
let selD      = new Set();
let selStatus = 'all';      // 'all' | 'heard' | 'pending'
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
    buildUserModal();
    document.getElementById('filterBtn').disabled = false;
    applyFilter();
  })
  .catch(e => {
    document.getElementById('loading').textContent = '❌ Error: ' + e;
    document.getElementById('loading').style.display = 'block';
  });

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

  const tree = document.getElementById('panel-co');
  DB.groups.forEach(g => {
    const series = collsByGroup[g.slug] || [];
    // Group header row
    const row = document.createElement('div');
    row.className = 'cgroup-row';
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

    // Arrow click: toggle expand (stop propagation so group click doesn't fire)
    arrow.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = seriesEl.classList.toggle('open');
      arrow.classList.toggle('open', open);
    });

    // Individual series rows
    series.forEach(c => {
      const sr = document.createElement('div');
      sr.className = 'cseries-row';
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

    tree.appendChild(row);
    if (series.length > 1) tree.appendChild(seriesEl);
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

function applyFilter() {
  if (!DB) return;
  filtered = DB.albums.filter(a => {
    if (selCs.size && !a.cs.some(p => selCs.has(p[0]))) return false;
    if (selG.size  && !a.g.some(gi => selG.has(gi))) return false;
    if (selD.size  && !selD.has(a.d))                return false;
    if (selStatus !== 'all') {
      if (activeUser === null) return true; // no user selected — ignore status filter
      const heard = a.h.includes(activeUser);
      if (selStatus === 'heard'   && !heard) return false;
      if (selStatus === 'pending' &&  heard) return false;
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
    const heard = activeUser !== null && a.h.includes(activeUser);
    const card  = document.createElement('div');
    card.className = 'album-card' + (heard ? ' heard-card' : '');
    card.dataset.id = a.id;

    const coverHtml = a.c
      ? `<img src="${thumbUrl(a.c)}" alt="" loading="lazy">`
      : `<div class="cover-placeholder">🎵</div>`;
    const badgeHtml = activeUser !== null
      ? `<div class="heard-badge ${heard ? 'heard-yes' : 'heard-no'}">${heard ? '✓' : '○'}</div>`
      : '';
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
  const collMap  = Object.fromEntries(DB.collections.map(c => [c.i, c.name]));
  const heard    = activeUser !== null && a.h.includes(activeUser);

  // Cover
  const coverWrap = document.getElementById('panel-cover-wrap');
  if (a.c) {
    document.getElementById('p-cover').src = a.c;
    document.getElementById('p-status').textContent = heard ? 'Heard' : 'Pending';
    document.getElementById('p-status').className = 'panel-cover-status ' + (heard ? 'heard' : 'pending');
    coverWrap.style.display = 'block';
  } else {
    coverWrap.style.display = 'none';
  }

  // Body
  const genres = a.g.map(gi => `<span class="panel-genre-tag">${esc(genreMap[gi] || '')}</span>`).join('');
  const colls  = a.cs.map(([ci, rank]) => {
    const name = esc(collMap[ci] || '');
    const rankStr = rank != null ? `<span class="panel-coll-rank">#${rank}</span>` : '';
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

  document.getElementById('panel-body').innerHTML = `
    <div class="panel-title-t">${esc(a.t)}</div>
    <div class="panel-artist-t">${esc(a.a)}</div>
    <div class="panel-year-t">${a.y || ''}${a.d ? ' · ' + a.d + 's' : ''}</div>
    ${genres ? `<div class="panel-genres">${genres}</div>` : ''}
    ${links.length ? `<div class="panel-links">${links.join('')}</div>` : ''}
    <div class="panel-artist-links">
      <a class="panel-link" href="${lfmArtistUrl}" target="_blank">Last.fm ↗</a>
      <a class="panel-link rym" href="${rymArtistUrl}" target="_blank">RYM artist ↗</a>
    </div>
    <div class="panel-yt-wrap">
      ${a.yt ? `<iframe src="https://www.youtube.com/embed/${a.yt}" allow="autoplay;encrypted-media" allowfullscreen></iframe>` : `<div class="panel-yt-search"><a href="${ytSearchUrl}" target="_blank">▶ Buscar en YouTube ↗</a></div>`}
    </div>
    ${colls ? `<div class="panel-divider"></div>
      <div class="panel-section-label">Colecciones</div>
      <div class="panel-collections">${colls}</div>` : ''}
  `;
}

function clearPanel() {
  document.getElementById('panel-cover-wrap').style.display = 'none';
  document.getElementById('panel-body').innerHTML = `
    <div class="panel-empty">
      <div class="panel-empty-icon">◉</div>
      Selecciona un álbum para ver detalles
    </div>`;
}

// ── User modal ─────────────────────────────────────────────────────────────
function buildUserModal() {
  const opts = document.getElementById('userOpts');
  const all  = document.createElement('div');
  all.className = 'user-opt active';
  all.textContent = 'Todos (sin filtro)';
  all.addEventListener('click', () => selectUser(null, all));
  opts.appendChild(all);
  DB.users.forEach((u, i) => {
    const el = document.createElement('div');
    el.className = 'user-opt';
    el.textContent = u.name;
    el.addEventListener('click', () => selectUser(i, el));
    opts.appendChild(el);
  });
  // Restore persisted user from localStorage
  const saved = localStorage.getItem('mh_user');
  if (saved) {
    const idx = DB.users.findIndex(u => u.name === saved);
    if (idx >= 0) {
      activeUser = idx;
      const els = opts.querySelectorAll('.user-opt');
      els[0].classList.remove('active');
      els[idx + 1].classList.add('active');
    }
  }
  updateUserBtn();
}

function selectUser(idx, el) {
  activeUser = idx;
  if (idx !== null) localStorage.setItem('mh_user', DB.users[idx].name);
  else localStorage.removeItem('mh_user');
  document.querySelectorAll('.user-opt').forEach(e => e.classList.remove('active'));
  el.classList.add('active');
  updateUserBtn();
  closeModal();
  if (filtered.length) renderResults(true);
}

function updateUserBtn() {
  const btn = document.getElementById('userBtn');
  if (activeUser !== null) {
    btn.textContent = DB.users[activeUser].name.slice(0, 3).toUpperCase();
    btn.title = DB.users[activeUser].name;
  } else {
    btn.textContent = '👤';
    btn.title = 'Seleccionar usuario';
  }
}

document.getElementById('userBtn').addEventListener('click', () => document.getElementById('userModal').classList.add('open'));
document.getElementById('modalClose').addEventListener('click', closeModal);
document.getElementById('userModal').addEventListener('click', e => { if (e.target.id === 'userModal') closeModal(); });
function closeModal() { document.getElementById('userModal').classList.remove('open'); }

function esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
</script>
</body>
</html>
"""

def render_html(data_url: str) -> str:
    return HTML_TEMPLATE.replace("{{DATA_URL}}", data_url)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Must Hear Alternative Index Generator")
    parser.add_argument("--must-hear-db",  dest="mh_db",       default="db/must_hear_rym_new.db")
    parser.add_argument("--scrobbles-db",  dest="scr_db",      default=None)
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

    json_path = data_dir / "mh_index.json"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    size_kb = json_path.stat().st_size / 1024
    print(f"  💾 JSON: {json_path} ({size_kb:.0f} KB)")

    html_path = out_dir / "index_alternativo.html"
    html_path.write_text(render_html("data/mh_index.json"), encoding="utf-8")
    print(f"  📋 HTML: {html_path}")
    print(f"✅ Generado: {args.out}/index_alternativo.html")


if __name__ == "__main__":
    main()

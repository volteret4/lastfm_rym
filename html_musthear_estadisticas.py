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


def _build_parent_map(meta_dir: Path) -> dict[str, str]:
    """Read .collections_meta.json + each collection's .series_meta.json to build
    {series_slug: parent_collection_name}.  Returns {} if files are missing."""
    meta_file = meta_dir / ".collections_meta.json"
    if not meta_file.exists():
        return {}
    result: dict[str, str] = {}
    try:
        for coll in json.loads(meta_file.read_text(encoding="utf-8")):
            slug = coll["slug"]
            name = coll["name"]
            result[slug] = name          # the parent collection maps to itself
            series_file = meta_dir / slug / ".series_meta.json"
            if series_file.exists():
                try:
                    for s in json.loads(series_file.read_text(encoding="utf-8")):
                        result[s["slug"]] = name   # child series → parent name
                except Exception:
                    pass
    except Exception:
        pass
    return result


def _coll_group(slug: str, name: str, parent_map: dict | None = None) -> str:
    s = slug.lower()
    if s.startswith("scaruffi"):        return "Scaruffi"
    if s.startswith("aoty"):            return "AOTY"
    if "1001" in s:                     return "1001 Albums"
    if "rolling_stone" in s:            return "Rolling Stone"
    if s.startswith("pitchfork"):       return "Pitchfork"
    if s.startswith("rym_chart"):       return "RYM Charts"
    if parent_map:
        parent = parent_map.get(slug)
        if parent:
            return parent
    return name   # unrecognised → its own group


# ── data gathering ────────────────────────────────────────────────────────────

def _backfill_user_heard(mh_conn: sqlite3.Connection,
                          scr_conn: sqlite3.Connection,
                          user_id: int, lastfm_u: str) -> int:
    """Populate user_heard for a user who has no entries yet.

    Matches all must-hear albums against the user's scrobble table using
    normalized (artist, album) names, then inserts (user_id, album_id,
    first_heard_at) rows.  Returns number of albums inserted.
    """
    table = f"scrobbles_{_safe(lastfm_u)}"
    exists = scr_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return 0

    # First-play timestamp per (artist_norm, album_norm) in user scrobbles
    try:
        scr_rows = scr_conn.execute(f"""
            SELECT LOWER(TRIM(ar.name)) AS an,
                   LOWER(TRIM(al.name)) AS bn,
                   MIN(s.timestamp)     AS ts
            FROM "{table}" s
            JOIN artists ar ON s.artist_id = ar.id
            JOIN albums  al ON s.album_id  = al.id
            WHERE s.timestamp > 0
            GROUP BY ar.id, al.id
        """).fetchall()
    except Exception as e:
        print(f"      scrobbles error: {e}")
        return 0

    lookup = {(r[0], r[1]): r[2] for r in scr_rows}
    if not lookup:
        return 0

    # All must-hear albums with their ids and normalized names
    mh_albums = mh_conn.execute("""
        SELECT a.id, LOWER(TRIM(ar.name)) AS an, LOWER(TRIM(a.name)) AS bn
        FROM albums a
        JOIN artists ar ON a.artist_id = ar.id
    """).fetchall()

    inserted = 0
    for alb_id, an, bn in mh_albums:
        ts = lookup.get((an, bn))
        if ts and ts > 0:
            mh_conn.execute(
                "INSERT OR IGNORE INTO user_heard (user_id, album_id, first_heard_at) VALUES (?,?,?)",
                (user_id, alb_id, ts)
            )
            inserted += 1

    mh_conn.commit()
    return inserted


def gather_data(mh_path: str, scr_path: str, meta_dir: Path | None = None) -> dict:
    conn = sqlite3.connect(mh_path)
    conn.row_factory = sqlite3.Row

    # Users
    users = [dict(r) for r in conn.execute(
        "SELECT id, username, lastfm_username FROM users ORDER BY username"
    ).fetchall()]

    # Backfill user_heard for any users with 0 entries (e.g. newly added users)
    if Path(scr_path).exists():
        heard_counts = {r[0]: r[1] for r in conn.execute(
            "SELECT user_id, COUNT(*) FROM user_heard GROUP BY user_id"
        ).fetchall()}
        scr_conn = sqlite3.connect(scr_path)
        for u in users:
            if heard_counts.get(u["id"], 0) == 0:
                lastfm_u = u.get("lastfm_username") or u["username"]
                print(f"    ↺ backfill {u['username']}…", end=" ", flush=True)
                n = _backfill_user_heard(conn, scr_conn, u["id"], lastfm_u)
                print(f"{n} álbumes")
        scr_conn.close()

    # Collections (only those with heard data)
    parent_map = _build_parent_map(meta_dir) if meta_dir else {}

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
        c["group"] = _coll_group(c["slug"], c["name"], parent_map)

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
    total_coll_albums = conn.execute(
        "SELECT COUNT(DISTINCT album_id) FROM collection_albums"
    ).fetchone()[0]

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

    # Popular albums — HAVING n_users >= 2, LIMIT 1000
    popular = [dict(r) for r in conn.execute("""
        SELECT a.name AS album, ar.name AS artist, a.year,
               COUNT(DISTINCT uh.user_id) AS n_users,
               GROUP_CONCAT(DISTINCT u.username ORDER BY u.username) AS who
        FROM user_heard uh
        JOIN albums a ON uh.album_id = a.id
        JOIN artists ar ON a.artist_id = ar.id
        JOIN users u ON uh.user_id = u.id
        GROUP BY uh.album_id
        HAVING n_users >= 2
        ORDER BY n_users DESC, a.year
        LIMIT 1000
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

    # ── Affinity / Jaccard similarity ─────────────────────────────────────────
    user_album_sets = {}
    for r in conn.execute("SELECT user_id, album_id FROM user_heard"):
        user_album_sets.setdefault(r[0], set()).add(r[1])

    uid_list = [u["id"] for u in users]
    similarity = {}
    for i, u1 in enumerate(uid_list):
        for u2 in uid_list[i:]:
            s1 = user_album_sets.get(u1, set())
            s2 = user_album_sets.get(u2, set())
            inter = len(s1 & s2)
            union = len(s1 | s2)
            j = round(inter / union * 100, 1) if union else 0
            similarity.setdefault(u1, {})[u2] = j
            similarity.setdefault(u2, {})[u1] = j

    # Per-user recommendations
    recommendations = {}
    for u in users:
        uid = u["id"]
        sim_users = sorted(
            [(other["id"], similarity.get(uid, {}).get(other["id"], 0))
             for other in users if other["id"] != uid],
            key=lambda x: x[1], reverse=True
        )[:4]
        total_sim = sum(s for _, s in sim_users) or 1

        recs = []
        for c in colls:
            my_pct = uc_heard.get(uid, {}).get(c["id"], 0) / c["total_albums"] * 100 if c["total_albums"] else 0
            weighted = sum(
                (uc_heard.get(ou, {}).get(c["id"], 0) / c["total_albums"] * 100 if c["total_albums"] else 0) * w
                for ou, w in sim_users
            ) / total_sim
            delta = weighted - my_pct
            if delta > 5 and weighted > 15:
                recs.append({
                    "slug": c["slug"], "name": c["name"],
                    "my_pct": round(my_pct, 1),
                    "sim_pct": round(weighted, 1),
                    "delta": round(delta, 1),
                })
        recommendations[uid] = sorted(recs, key=lambda r: r["delta"], reverse=True)[:6]

    # Pending albums (heard by most but not by me)
    pending_per_user = {}
    for u in users:
        uid = u["id"]
        rows_pending = conn.execute("""
            SELECT ar.name, a.name, a.year, COUNT(DISTINCT uh.user_id) AS n,
                   GROUP_CONCAT(DISTINCT us.username ORDER BY us.username) AS who
            FROM user_heard uh
            JOIN albums a ON uh.album_id = a.id
            JOIN artists ar ON a.artist_id = ar.id
            JOIN users us ON uh.user_id = us.id
            WHERE uh.album_id NOT IN (
                SELECT album_id FROM user_heard WHERE user_id = ?
            )
            GROUP BY uh.album_id
            ORDER BY n DESC
            LIMIT 200
        """, (uid,)).fetchall()
        pending_per_user[uid] = [
            {"artist": r[0], "title": r[1], "year": r[2], "n": r[3], "who": r[4]}
            for r in rows_pending
        ]

    conn.close()

    # Temporal progression from scrobbles
    print("  ⏱ Calculando progresión temporal…")
    temporal = gather_temporal(mh_path, scr_path, users)

    return {
        "users":             users,
        "colls":             colls,
        "uc_heard":          {str(k): v for k, v in uc_heard.items()},
        "total_heard":       total_heard,
        "total_unique_heard":  total_unique_heard,
        "total_albums_db":     total_albums_db,
        "total_coll_albums":   total_coll_albums,
        "top_genres":        top_genres,
        "genre_by_user":     {str(k): v for k, v in genre_by_user.items()},
        "popular":           popular,
        "unique_albums":     unique_albums,
        "temporal":          temporal,
        "similarity":        {str(k): {str(k2): v for k2, v in vd.items()} for k, vd in similarity.items()},
        "recommendations":   {str(k): v for k, v in recommendations.items()},
        "pending_per_user":  {str(k): v for k, v in pending_per_user.items()},
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
            # Min timestamp per (artist_norm, album_norm) in scrobbles, filter from 2007
            scr_rows = scr.execute(f"""
                SELECT LOWER(TRIM(ar.name)) AS an,
                       LOWER(TRIM(al.name)) AS bn,
                       MIN(s.timestamp) AS ts
                FROM "{table}" s
                JOIN artists ar ON s.artist_id = ar.id
                JOIN albums  al ON s.album_id  = al.id
                WHERE s.timestamp > 0 AND s.timestamp >= 1167609600
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
    similarity   = data.get("similarity", {})
    recommendations = data.get("recommendations", {})
    pending_per_user = data.get("pending_per_user", {})

    n_users       = len(users)
    n_total       = data["total_unique_heard"]
    n_db          = data["total_albums_db"]
    n_coll_albums = data["total_coll_albums"]

    # Sort users by total heard desc
    users_sorted = sorted(users, key=lambda u: total_heard.get(u["id"], 0), reverse=True)
    user_color   = {u["username"]: USER_COLORS[i % len(USER_COLORS)]
                    for i, u in enumerate(users_sorted)}

    # ── collection groups completion ──────────────────────────────────────────
    GROUP_ORDER = ["Scaruffi", "AOTY", "1001 Albums", "Rolling Stone",
                   "Pitchfork", "RYM Charts", "Otras"]

    from collections import defaultdict
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

    # Datasets for group charts (kept for accordion header stats)
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

    # ── collection total heard (for sorting) ──────────────────────────────────
    coll_total_heard = {}
    for uid, cdict in uc_heard.items():
        for cid, n in cdict.items():
            coll_total_heard[cid] = coll_total_heard.get(cid, 0) + n

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

    coll_header_cells = "".join(
        f'<th style="writing-mode:vertical-rl;transform:rotate(180deg);padding:8px 4px;font-size:.6rem;white-space:nowrap;color:var(--muted)">{u["username"]}</th>'
        for u in users_sorted
    )

    # ── accordion: all groups unified ─────────────────────────────────────────
    PINNED = ["Scaruffi", "AOTY", "1001 Albums", "Rolling Stone", "Pitchfork", "RYM Charts"]
    all_group_names = {c["group"] for c in colls}
    ordered_groups  = [g for g in PINNED if g in all_group_names]
    ordered_groups += sorted(g for g in all_group_names if g not in PINNED)

    def _acc_entry(gid, header_name, meta, user_bars_html, inner_rows_html):
        return f"""
<div class="acc-group" id="acc-{gid}">
  <div class="acc-header" onclick="toggleAcc('{gid}')">
    <span class="acc-caret">&#9658;</span>
    <span class="acc-name">{header_name}</span>
    <span class="acc-meta">{meta}</span>
    <div class="acc-usr-bars">{user_bars_html}</div>
  </div>
  <div class="acc-body" id="accb-{gid}" style="display:none">
    <div class="coll-table-wrap">
      <table class="coll-table">
        <thead><tr>
          <th>Colecci&oacute;n</th><th style="text-align:right">&Aacute;lb.</th>
          {coll_header_cells}
        </tr></thead>
        <tbody>{inner_rows_html}</tbody>
      </table>
    </div>
  </div>
</div>"""

    def _inner_rows(coll_list):
        rows = ""
        for c in sorted(coll_list, key=lambda c: coll_total_heard.get(c["id"], 0), reverse=True):
            row = f'<tr><td class="coll-name"><a href="{c["slug"]}/index.html" style="color:var(--muted);text-decoration:none">{c["name"]}</a></td>'
            row += f'<td class="coll-total">{c["total_albums"]}</td>'
            for u in users_sorted:
                h = uc_heard.get(u["id"], {}).get(c["id"], 0)
                pct = h / c["total_albums"] * 100 if c["total_albums"] else 0
                row += pct_cell(pct)
            row += "</tr>"
            rows += row
        return rows

    def _user_bars(g_heard_by_uid, total):
        bars = ""
        for u in users_sorted:
            h = g_heard_by_uid.get(u["id"], 0)
            pct = h / total * 100 if total else 0
            bars += (
                f'<span class="acc-usr-bar" title="{u["username"]}: {pct:.0f}%">'
                f'<span class="acc-usr-fill" style="width:{pct:.0f}%;background:{user_color[u["username"]]}"></span>'
                f'</span>'
            )
        return bars

    accordion_html = ""

    for g in ordered_groups:
        g_colls = [c for c in colls if c["group"] == g]
        if not g_colls:
            continue
        total   = grp_total_n[g]
        n_colls = len(g_colls)
        gid     = _safe(g)
        n_word  = "series" if n_colls != 1 else "serie"
        meta    = f"{n_colls} {n_word} &middot; {total} &aacute;lbumes"
        accordion_html += _acc_entry(
            gid, g, meta,
            _user_bars(grp_heard_n[g], total),
            _inner_rows(g_colls),
        )

    # ── genre chart data ──────────────────────────────────────────────────────
    genre_labels = [g for g, _ in top_genres[:20]]
    genre_values = [n for _, n in top_genres[:20]]

    # Per-user genre radar: top 12 genres overall, values per user
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

    # ── popular albums — JS-paginated, 30 per page ────────────────────────────
    pop_page_size = 30
    pop_data_js = json.dumps(
        [{"artist": p["artist"], "album": p["album"],
          "year": p["year"] or "", "n": p["n_users"],
          "who": (p["who"] or "").split(",")}
         for p in popular],
        ensure_ascii=False,
    )
    pop_colors_js = json.dumps(
        {u["username"]: user_color[u["username"]] for u in users_sorted},
        ensure_ascii=False,
    )
    pop_users_js = json.dumps([u["username"] for u in users_sorted], ensure_ascii=False)

    # ── pending albums per user — JS data for pagination ──────────────────────
    pend_data_js = json.dumps(
        {str(uid): lst for uid, lst in pending_per_user.items()},
        ensure_ascii=False,
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
        <div class="sum-n">{n_coll_albums:,}</div>
        <div class="sum-label">Álbumes en colecciones</div>
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

    # ── Afinidad section ──────────────────────────────────────────────────────

    # Similarity matrix HTML (static)
    sim_header = "".join(
        f'<th style="writing-mode:vertical-rl;transform:rotate(180deg);padding:6px 4px;font-size:.58rem;white-space:nowrap;color:var(--muted)">{u["username"]}</th>'
        for u in users_sorted
    )
    sim_rows = ""
    for u1 in users_sorted:
        uid1 = str(u1["id"])
        sim_rows += f'<tr><th style="text-align:left;white-space:nowrap;font-size:.58rem;color:var(--muted);padding:6px 10px">{u1["username"]}</th>'
        for u2 in users_sorted:
            uid2 = str(u2["id"])
            val = similarity.get(uid1, {}).get(uid2, 0)
            if u1["id"] == u2["id"]:
                bg = "#c9a227"
                fc = "#000"
            else:
                # Interpolate 0%=dark, 50%=mid-gold, 100%=accent
                t = min(val / 50.0, 1.0)
                r_c = int(0x11 + t * (0xc9 - 0x11))
                g_c = int(0x11 + t * (0xa2 - 0x11))
                b_c = int(0x11 + t * (0x27 - 0x11))
                bg = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                fc = "#ccc" if val < 25 else "#000"
            sim_rows += f'<td style="background:{bg};color:{fc};text-align:center;font-family:\'DM Mono\',monospace;font-size:.65rem;padding:6px 10px;border:1px solid #161616">{val:.0f}%</td>'
        sim_rows += "</tr>"

    # Para ti section: user buttons + panels
    para_ti_buttons = ""
    para_ti_panels  = ""
    for i, u in enumerate(users_sorted):
        uid_str = str(u["id"])
        color   = user_color[u["username"]]
        active_cls = " active" if i == 0 else ""
        para_ti_buttons += (
            f'<button class="para-ti-btn{active_cls}" '
            f'style="color:{color};border-color:{color}" '
            f'onclick="showParaTi(\'{uid_str}\')" id="ptbtn-{uid_str}">'
            f'{u["username"]}</button>'
        )

        recs = recommendations.get(uid_str, [])

        rec_cards = ""
        for rc in recs:
            my_w = min(rc["my_pct"], 100)
            sim_w = min(rc["sim_pct"], 100)
            rec_cards += f"""<div class="rec-card">
  <div class="rec-coll-name">{rc["name"]}</div>
  <div class="rec-bars">
    <div class="rec-bar-row">
      <span>Tú</span>
      <div class="rec-bar-track"><div class="rec-bar-fill" style="width:{my_w:.0f}%;background:{color}88"></div></div>
      <span>{rc["my_pct"]:.0f}%</span>
    </div>
    <div class="rec-bar-row">
      <span>Similares</span>
      <div class="rec-bar-track"><div class="rec-bar-fill" style="width:{sim_w:.0f}%;background:{color}"></div></div>
      <span>{rc["sim_pct"]:.0f}%</span>
    </div>
  </div>
  <div class="rec-delta">+{rc["delta"]:.0f}%</div>
</div>"""

        no_recs_placeholder = (
            '<div style="color:var(--muted);font-size:.72rem;padding:12px 0">Sin recomendaciones disponibles</div>'
            if not rec_cards else ""
        )
        panel_display = "block" if i == 0 else "none"
        btn_style = "font-family:'DM Mono',monospace;font-size:.62rem;padding:4px 12px;border:1px solid var(--border);border-radius:4px;background:none;color:var(--muted);cursor:pointer"
        para_ti_panels += f"""<div class="para-ti-panel" id="ptpanel-{uid_str}" style="display:{panel_display}">
  <h4 style="font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Colecciones que podr&#237;as explorar</h4>
  <div class="rec-grid">{rec_cards}{no_recs_placeholder}</div>
  <h4 style="font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;margin-top:4px">Álbumes pendientes (escuchados por otros)</h4>
  <div style="overflow-x:auto;border:1px solid var(--border);border-radius:6px">
    <table style="border-collapse:collapse;width:100%">
      <thead><tr>
        <th style="font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted);padding:5px 8px;border-bottom:1px solid var(--border);text-align:left">Artista</th>
        <th style="font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted);padding:5px 8px;border-bottom:1px solid var(--border);text-align:left">Álbum</th>
        <th style="font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted);padding:5px 8px;border-bottom:1px solid var(--border);text-align:left">Año</th>
        <th style="font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted);padding:5px 8px;border-bottom:1px solid var(--border);text-align:left">Escuchado por</th>
      </tr></thead>
      <tbody id="pendTbody-{uid_str}"></tbody>
    </table>
  </div>
  <div style="display:flex;align-items:center;gap:10px;margin-top:10px;font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted)">
    <button id="pendPrev-{uid_str}" onclick="pendChangePage('{uid_str}',-1)" style="{btn_style}">&#8592; Anterior</button>
    <span id="pendPageInfo-{uid_str}"></span>
    <button id="pendNext-{uid_str}" onclick="pendChangePage('{uid_str}',1)" style="{btn_style}">Siguiente &#8594;</button>
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
        x: {{ type: 'time', time: {{ unit: 'year' }}, min: new Date('2007-01-01').getTime(), grid: {{ color: '#1e1e1e' }}, ticks: {{ color: '#555' }} }},
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
  /* accordion */
  .acc-group {{ border:1px solid var(--border); border-radius:6px; margin-bottom:6px; overflow:hidden; }}
  .acc-header {{ display:flex; align-items:center; gap:10px; padding:10px 14px; cursor:pointer; background:var(--surface); user-select:none; transition:background .1s; }}
  .acc-header:hover {{ background:#161616; }}
  .acc-caret {{ font-size:.6rem; color:var(--muted); transition:transform .15s; flex-shrink:0; }}
  .acc-caret.open {{ transform:rotate(90deg); color:var(--accent); }}
  .acc-name {{ font-family:'Bebas Neue',sans-serif; font-size:1rem; letter-spacing:.06em; flex-shrink:0; }}
  .acc-meta {{ font-family:'DM Mono',monospace; font-size:.58rem; color:var(--muted); }}
  .acc-usr-bars {{ display:flex; gap:3px; margin-left:auto; align-items:center; }}
  .acc-usr-bar {{ width:32px; height:4px; background:#222; border-radius:2px; overflow:hidden; flex-shrink:0; }}
  .acc-usr-fill {{ display:block; height:100%; border-radius:2px; }}
  .acc-body {{ background:var(--bg); }}
  /* affinity */
  .sim-table {{ border-collapse:collapse; font-family:'DM Mono',monospace; font-size:.65rem; }}
  .sim-table th, .sim-table td {{ padding:6px 10px; text-align:center; border:1px solid #161616; }}
  .sim-table th {{ color:var(--muted); font-size:.58rem; }}
  .para-ti-users {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; }}
  .para-ti-btn {{ font-family:'DM Mono',monospace; font-size:.62rem; padding:4px 12px; border:1px solid; border-radius:3px; cursor:pointer; background:none; transition:all .12s; }}
  .para-ti-btn.active {{ opacity:1; }}
  .para-ti-btn:not(.active) {{ opacity:.4; }}
  .para-ti-panel {{ display:none; }}
  .para-ti-panel.active {{ display:block; }}
  .rec-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:10px; margin-bottom:20px; }}
  .rec-card {{ background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:12px; }}
  .rec-coll-name {{ font-size:.78rem; font-weight:500; margin-bottom:6px; line-height:1.3; }}
  .rec-bars {{ display:flex; flex-direction:column; gap:3px; margin-bottom:4px; }}
  .rec-bar-row {{ display:flex; align-items:center; gap:6px; font-family:'DM Mono',monospace; font-size:.58rem; color:var(--muted); }}
  .rec-bar-track {{ flex:1; height:4px; background:#222; border-radius:2px; }}
  .rec-bar-fill {{ height:100%; border-radius:2px; }}
  .rec-delta {{ font-family:'DM Mono',monospace; font-size:.68rem; color:var(--accent); font-weight:700; }}
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
  </section>

  <!-- collection groups accordion -->
  <section id="colecciones">
    <h2 class="sec-title">Progreso por colección</h2>
    <p class="sec-desc">% de álbumes escuchados por usuario en cada colección. Colores: 0% negro · &lt;25% oscuro · &lt;50% dorado oscuro · &lt;75% dorado medio · ≥75% dorado.</p>
    <div style="display:flex;gap:8px;margin-bottom:14px">
      <button onclick="expandAllAcc()" style="font-family:'DM Mono',monospace;font-size:.62rem;padding:5px 12px;border:1px solid var(--border);border-radius:4px;background:none;color:var(--muted);cursor:pointer;">Expandir todo</button>
      <button onclick="collapseAllAcc()" style="font-family:'DM Mono',monospace;font-size:.62rem;padding:5px 12px;border:1px solid var(--border);border-radius:4px;background:none;color:var(--muted);cursor:pointer;">Colapsar todo</button>
    </div>
    {accordion_html}
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
    <div style="overflow-x:auto">
      <table class="pop-table">
        <thead>
          <tr><th>#</th><th>Artista</th><th>Álbum</th><th>Año</th><th>Usuarios</th><th></th></tr>
        </thead>
        <tbody id="popTbody"></tbody>
      </table>
    </div>
    <div style="display:flex;align-items:center;gap:10px;margin-top:12px;font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted)">
      <button id="popPrev" onclick="popChangePage(-1)" style="font-family:'DM Mono',monospace;font-size:.62rem;padding:4px 12px;border:1px solid var(--border);border-radius:4px;background:none;color:var(--muted);cursor:pointer">&#8592; Anterior</button>
      <span id="popPageInfo"></span>
      <button id="popNext" onclick="popChangePage(1)" style="font-family:'DM Mono',monospace;font-size:.62rem;padding:4px 12px;border:1px solid var(--border);border-radius:4px;background:none;color:var(--muted);cursor:pointer">Siguiente &#8594;</button>
    </div>
  </section>

  <!-- unique discoveries -->
  <section id="descubrimientos">
    <h2 class="sec-title">Descubrimientos únicos</h2>
    <p class="sec-desc">Álbumes de las colecciones escuchados solo por ese usuario (nadie más los ha marcado).</p>
    <div class="uniq-grid">{unique_rows}</div>
  </section>

{temporal_section}

  <!-- afinidad -->
  <section id="afinidad">
    <h2 class="sec-title">Afinidad entre usuarios</h2>
    <p class="sec-desc">Similitud de gustos entre usuarios basada en álbumes escuchados en común (índice de Jaccard). También incluye recomendaciones personalizadas y álbumes pendientes.</p>

    <h3 style="font-family:'DM Mono',monospace;font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:12px">Similitud entre usuarios</h3>
    <div style="overflow-x:auto;margin-bottom:32px">
      <table class="sim-table">
        <thead><tr><th></th>{sim_header}</tr></thead>
        <tbody>{sim_rows}</tbody>
      </table>
    </div>

    <h3 style="font-family:'DM Mono',monospace;font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:12px">Para ti</h3>
    <div class="para-ti-users">
      {para_ti_buttons}
    </div>
    {para_ti_panels}
  </section>

</main>
<footer>Generado {generated} · Datos de MusicBrainz, Last.fm, RYM &amp; Scaruffi</footer>

<script>
Chart.defaults.color = '#555';
Chart.defaults.borderColor = '#1e1e1e';

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

// ── Accordion ──────────────────────────────────────────────────────────────
function toggleAcc(id) {{
  const body = document.getElementById('accb-' + id);
  const hdr  = body.previousElementSibling;
  const caret = hdr.querySelector('.acc-caret');
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  caret.classList.toggle('open', !open);
}}
function expandAllAcc() {{
  document.querySelectorAll('.acc-body').forEach(b => {{
    b.style.display = 'block';
    b.previousElementSibling.querySelector('.acc-caret').classList.add('open');
  }});
}}
function collapseAllAcc() {{
  document.querySelectorAll('.acc-body').forEach(b => {{
    b.style.display = 'none';
    b.previousElementSibling.querySelector('.acc-caret').classList.remove('open');
  }});
}}

// ── Popular albums pagination ──────────────────────────────────────────────
const POP_DATA = {pop_data_js};
const POP_COLORS = {pop_colors_js};
const POP_PAGE_SIZE = {pop_page_size};
let popCurrentPage = 0;

function renderPopPage(page) {{
  const total = POP_DATA.length;
  const maxPage = Math.max(0, Math.ceil(total / POP_PAGE_SIZE) - 1);
  page = Math.max(0, Math.min(page, maxPage));
  popCurrentPage = page;
  const start = page * POP_PAGE_SIZE;
  const slice = POP_DATA.slice(start, start + POP_PAGE_SIZE);
  const tbody = document.getElementById('popTbody');
  tbody.innerHTML = slice.map((r, i) => {{
    const dots = (r.who || []).map(u => {{
      const uu = u.trim();
      const c = POP_COLORS[uu] || '#555';
      return `<span title="${{uu}}" style="width:9px;height:9px;border-radius:50%;background:${{c}};display:inline-block;flex-shrink:0"></span>`;
    }}).join('');
    const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    return `<tr>
      <td class="pop-year">${{start + i + 1}}</td>
      <td class="pop-artist">${{esc(r.artist)}}</td>
      <td class="pop-album">${{esc(r.album)}}</td>
      <td class="pop-year">${{r.year || '—'}}</td>
      <td class="pop-n">${{r.n}}</td>
      <td><div class="pop-dots">${{dots}}</div></td>
    </tr>`;
  }}).join('');
  document.getElementById('popPageInfo').textContent =
    `Pág. ${{page + 1}} / ${{maxPage + 1}}  ·  ${{total}} álbumes`;
  document.getElementById('popPrev').disabled = page === 0;
  document.getElementById('popNext').disabled = page >= maxPage;
}}

function popChangePage(dir) {{
  renderPopPage(popCurrentPage + dir);
}}

// ── Pending albums pagination ──────────────────────────────────────────────
const PEND_DATA = {pend_data_js};
const PEND_PAGE_SIZE = 25;
const pendCurrentPage = {{}};

function renderPendPage(uid, page) {{
  const data = PEND_DATA[uid] || [];
  const maxPage = Math.max(0, Math.ceil(data.length / PEND_PAGE_SIZE) - 1);
  page = Math.max(0, Math.min(page, maxPage));
  pendCurrentPage[uid] = page;
  const start = page * PEND_PAGE_SIZE;
  const slice = data.slice(start, start + PEND_PAGE_SIZE);
  const tbody = document.getElementById('pendTbody-' + uid);
  if (!tbody) return;
  const esc = s => (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  tbody.innerHTML = slice.map(r => `<tr>
    <td style="color:var(--muted);font-size:.72rem;padding:5px 8px">${{esc(r.artist)}}</td>
    <td style="font-size:.75rem;padding:5px 8px">${{esc(r.title)}}</td>
    <td style="font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted);padding:5px 8px">${{r.year || '—'}}</td>
    <td style="font-family:'DM Mono',monospace;font-size:.65rem;color:var(--accent);padding:5px 8px">${{esc(r.who)}}</td>
  </tr>`).join('');
  const info = document.getElementById('pendPageInfo-' + uid);
  if (info) info.textContent = data.length
    ? `Pág. ${{page + 1}} / ${{maxPage + 1}}  ·  ${{data.length}} álbumes`
    : 'Sin álbumes pendientes';
  const prev = document.getElementById('pendPrev-' + uid);
  const next = document.getElementById('pendNext-' + uid);
  if (prev) prev.disabled = page === 0;
  if (next) next.disabled = page >= maxPage || data.length === 0;
}}

function pendChangePage(uid, dir) {{
  renderPendPage(uid, (pendCurrentPage[uid] || 0) + dir);
}}

// ── Para ti user tabs ──────────────────────────────────────────────────────
function showParaTi(uid) {{
  document.querySelectorAll('.para-ti-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.para-ti-btn').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('ptpanel-' + uid);
  const btn   = document.getElementById('ptbtn-' + uid);
  if (panel) panel.style.display = 'block';
  if (btn)   btn.classList.add('active');
}}

// ── Init on load ──────────────────────────────────────────────────────────
renderPopPage(0);
Object.keys(PEND_DATA).forEach(uid => renderPendPage(uid, 0));

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
    meta_dir  = Path(args.out).parent
    data = gather_data(args.mh_db, args.scr_db, meta_dir)

    html = render_html(data, generated)
    out  = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✅ {out}  ({len(html):,} bytes)")


if __name__ == "__main__":
    main()

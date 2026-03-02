#!/usr/bin/env python3
"""
Generador de estadísticas — lastfm_rym.db (schema multi-usuario)
================================================================
Lee una BD SQLite con la estructura lastfm_rym y genera para cada usuario:

  output/
    index.html                    ← portada con todos los usuarios
    {user}/
      index.html                  ← copia de estadisticas_lastfm.html
      lastfm_stats.json           ← datos principales (carga inicial)
      lastfm_detail.json          ← detalle por entidad (carga perezosa)

Uso:
    python generar_estadisticas.py --db lastfm_rym.db
    python generar_estadisticas.py --db lastfm_rym.db --users alice bob
    python generar_estadisticas.py --db lastfm_rym.db --out mi_carpeta

Requisitos:
    pip install tqdm          (opcional, barras de progreso)
"""

import sqlite3
import json
import os
import re
import shutil
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────
MATRIX_TOP_ARTISTS = 25
MATRIX_TOP_ALBUMS  = 25
MATRIX_TOP_GENRES  = 20

HTML_TEMPLATE = "docs/personales/estadisticas_lastfm.html"  # debe estar en el mismo directorio
OUTPUT_DIR    = "docs/personales"

GENRE_BLACKLIST = {
    "seen live", "albums i own", "favorite", "favourites", "beautiful",
    "music", "amazing", "best", "awesome", "love", "noisy", "catchy",
}

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def ts_to_iso(ts: int) -> str:
    """Unix timestamp → ISO-8601 UTC."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

def ts_to_month(ts: int) -> str:
    """Unix timestamp → 'YYYY-MM'."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m")

def ts_to_hour(ts: int) -> int:
    return datetime.fromtimestamp(ts, tz=timezone.utc).hour

def ts_to_weekday_num(ts: int) -> int:
    """0=Lun … 6=Dom  (isoweekday()-1)."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoweekday() - 1

def ts_to_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

WD_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]  # 0-6

# ─────────────────────────────────────────────
#  CARGA DE GÉNEROS (desde las tablas de la BD)
# ─────────────────────────────────────────────
def load_artist_genres(conn) -> dict[str, list[str]]:
    """
    Devuelve {artist_lower: [genre1, genre2, ...]}
    Prioridad: artist_genres_detailed (con peso) > artist_genres (texto plano).
    """
    genres: dict[str, list[str]] = {}

    # 1) artist_genres_detailed — filas individuales con weight
    rows = conn.execute(
        "SELECT artist, genre, weight FROM artist_genres_detailed ORDER BY artist, weight DESC"
    ).fetchall()
    if rows:
        for artist, genre, weight in rows:
            key = _normalize(artist)
            g = (genre or "").strip().lower()
            if g and g not in GENRE_BLACKLIST and len(g) > 1:
                genres.setdefault(key, [])
                if g.title() not in genres[key]:
                    genres[key].append(g.title())

    # 2) Fallback: artist_genres.genres (texto, puede ser CSV o JSON)
    if not genres:
        for artist, gs_text in conn.execute("SELECT artist, genres FROM artist_genres"):
            key = _normalize(artist)
            # Intentar JSON primero, luego CSV
            try:
                gs_list = json.loads(gs_text) if gs_text else []
            except Exception:
                gs_list = [g.strip() for g in (gs_text or "").split(",")]
            filtered = [
                g.strip().title() for g in gs_list
                if g.strip().lower() not in GENRE_BLACKLIST and len(g.strip()) > 1
            ]
            if filtered:
                genres[key] = filtered[:5]

    return genres

def load_album_genres(conn) -> dict[tuple[str, str], list[str]]:
    """Devuelve {(artist_lower, album_lower): [genre1, ...]}"""
    genres: dict[tuple[str, str], list[str]] = {}
    rows = conn.execute(
        "SELECT artist, album, genre, weight FROM album_genres ORDER BY artist, album, weight DESC"
    ).fetchall()
    for artist, album, genre, weight in rows:
        key = (_normalize(artist), _normalize(album))
        g = (genre or "").strip().lower()
        if g and g not in GENRE_BLACKLIST and len(g) > 1:
            genres.setdefault(key, [])
            if g.title() not in genres[key]:
                genres[key].append(g.title())
    return genres

def load_artist_details(conn) -> dict[str, dict]:
    """Carga metadatos extra de artistas: país, imagen, tipo, bio snippet."""
    details = {}
    try:
        for row in conn.execute(
            "SELECT artist, country, artist_type, begin_date, end_date, image_url, bio "
            "FROM artist_details"
        ):
            artist, country, atype, begin, end, img, bio = row
            details[_normalize(artist)] = {
                "country":  country,
                "type":     atype,
                "begin":    begin,
                "end":      end,
                "image":    img,
                "bio":      (bio or "")[:300].strip() if bio else None,
            }
    except Exception:
        pass
    return details

def load_album_release_years(conn) -> dict[tuple[str, str], int]:
    """Devuelve {(artist_lower, album_lower): release_year}"""
    years = {}
    try:
        for artist, album, year in conn.execute(
            "SELECT artist, album, release_year FROM album_release_dates WHERE release_year IS NOT NULL"
        ):
            years[(_normalize(artist), _normalize(album))] = year
    except Exception:
        pass
    return years

# ─────────────────────────────────────────────
#  CONSTRUCCIÓN DE ESTRUCTURAS IN-MEMORY
# ─────────────────────────────────────────────
def build_user_data(conn, user: str,
                    artist_genres_map: dict,
                    album_genres_map: dict,
                    artist_details_map: dict,
                    album_years_map: dict) -> tuple[list, list, dict]:
    """
    Para un usuario dado construye:
      - scrobbles_rows: list of dicts con todos sus scrobbles
      - artists_index:  {artist_lower: {"id": int, "name": str, ...}}
      - albums_index:   {(artist_lower, album_lower): {"id": int, ...}}
    Devuelve (scrobbles_rows, artists_index, albums_index).
    """
    print(f"    Cargando scrobbles de {user!r}...")
    rows = conn.execute(
        "SELECT artist, track, album, timestamp FROM scrobbles "
        "WHERE user = ? ORDER BY timestamp",
        (user,)
    ).fetchall()

    # Construir índices con IDs sintéticos (ordenados por popularidad al final)
    artist_counts: dict[str, int] = {}
    album_counts:  dict[tuple[str, str], int] = {}

    scrobbles = []
    for artist, track, album, ts in rows:
        if not artist or not ts:
            continue
        ak = _normalize(artist)
        artist_counts[ak] = artist_counts.get(ak, 0) + 1
        if album:
            abk = (_normalize(artist), _normalize(album))
            album_counts[abk] = album_counts.get(abk, 0) + 1
        scrobbles.append({
            "artist":  artist.strip(),
            "artist_k": ak,
            "track":   (track or "").strip(),
            "album":   (album or "").strip() if album else "",
            "album_k": (_normalize(artist), _normalize(album)) if album else None,
            "ts":      ts,
            "month":   ts_to_month(ts),
            "hour":    ts_to_hour(ts),
            "wd":      ts_to_weekday_num(ts),
            "date":    ts_to_date(ts),
            "ts_iso":  ts_to_iso(ts),
        })

    # Asignar IDs por orden de popularidad
    artists_index: dict[str, dict] = {}
    for idx, (ak, _) in enumerate(
        sorted(artist_counts.items(), key=lambda x: -x[1]), start=1
    ):
        # Recuperar nombre canónico del primer scrobble
        canonical = next((s["artist"] for s in scrobbles if s["artist_k"] == ak), ak)
        artists_index[ak] = {
            "id":      idx,
            "name":    canonical,
            "genres":  artist_genres_map.get(ak, []),
            "details": artist_details_map.get(ak, {}),
        }

    albums_index: dict[tuple[str, str], dict] = {}
    for idx, (abk, _) in enumerate(
        sorted(album_counts.items(), key=lambda x: -x[1]), start=1
    ):
        a_canon = next((s["artist"] for s in scrobbles if s["artist_k"] == abk[0]), abk[0])
        al_canon = next((s["album"] for s in scrobbles if s["album_k"] == abk), abk[1])
        artist_gs = artist_genres_map.get(abk[0], [])
        album_gs  = album_genres_map.get(abk, artist_gs[:2])
        albums_index[abk] = {
            "id":          idx,
            "artist":      a_canon,
            "artist_k":    abk[0],
            "name":        al_canon,
            "genres":      album_gs,
            "release_year": album_years_map.get(abk),
        }

    return scrobbles, artists_index, albums_index


# ─────────────────────────────────────────────
#  EXPORT_STATS_JSON
# ─────────────────────────────────────────────
def export_stats_json(scrobbles, artists_index, albums_index, username: str, path: str):
    print(f"    Construyendo stats JSON...")

    # ── Artistas ──────────────────────────────────────────────────────────
    artist_stats: dict[str, dict] = {}
    for s in scrobbles:
        ak = s["artist_k"]
        if ak not in artist_stats:
            ai = artists_index[ak]
            artist_stats[ak] = {
                "artist_id":      ai["id"],
                "artist":         ai["name"],
                "genres":         ", ".join(ai["genres"][:3]),
                "total_scrobbles": 0,
                "first_ts":       s["ts"],
                "last_ts":        s["ts"],
                "dates":          set(),
                # extra de artist_details
                "country":        ai["details"].get("country"),
                "image":          ai["details"].get("image"),
                "artist_type":    ai["details"].get("type"),
            }
        st = artist_stats[ak]
        st["total_scrobbles"] += 1
        st["dates"].add(s["date"])
        if s["ts"] < st["first_ts"]: st["first_ts"] = s["ts"]
        if s["ts"] > st["last_ts"]:  st["last_ts"]  = s["ts"]

    artists_out = []
    for ak, st in sorted(artist_stats.items(), key=lambda x: -x[1]["total_scrobbles"]):
        days = len(st["dates"])
        artists_out.append({
            "artist_id":        st["artist_id"],
            "artist":           st["artist"],
            "genres":           st["genres"],
            "total_scrobbles":  st["total_scrobbles"],
            "first_scrobble":   ts_to_iso(st["first_ts"]),
            "last_scrobble":    ts_to_iso(st["last_ts"]),
            "active_days_span": days,
            "avg_days_between": round(st["total_scrobbles"] / days, 1) if days else None,
            "country":          st.get("country"),
            "image":            st.get("image"),
            "artist_type":      st.get("artist_type"),
        })
        del st["dates"]  # liberar memoria

    # ── Álbumes ───────────────────────────────────────────────────────────
    album_stats: dict[tuple, dict] = {}
    for s in scrobbles:
        if not s["album_k"]: continue
        abk = s["album_k"]
        if abk not in album_stats:
            ai = albums_index[abk]
            album_stats[abk] = {
                "album_id":       ai["id"],
                "artist_id":      artists_index[abk[0]]["id"],
                "artist":         ai["artist"],
                "album":          ai["name"],
                "genres":         ", ".join(ai["genres"][:2]),
                "release_year":   ai["release_year"],
                "total_scrobbles": 0,
                "first_ts":       s["ts"],
                "last_ts":        s["ts"],
                "dates":          set(),
            }
        st = album_stats[abk]
        st["total_scrobbles"] += 1
        st["dates"].add(s["date"])
        if s["ts"] < st["first_ts"]: st["first_ts"] = s["ts"]
        if s["ts"] > st["last_ts"]:  st["last_ts"]  = s["ts"]

    albums_out = []
    for abk, st in sorted(album_stats.items(), key=lambda x: -x[1]["total_scrobbles"]):
        days = len(st["dates"])
        span = (st["last_ts"] - st["first_ts"]) // 86400
        albums_out.append({
            "album_id":         st["album_id"],
            "artist_id":        st["artist_id"],
            "artist":           st["artist"],
            "album":            st["album"],
            "genres":           st["genres"],
            "release_year":     st["release_year"],
            "total_scrobbles":  st["total_scrobbles"],
            "first_scrobble":   ts_to_iso(st["first_ts"]),
            "last_scrobble":    ts_to_iso(st["last_ts"]),
            "active_days_span": span,
            "days_listened":    days,
        })

    # ── Mensual ───────────────────────────────────────────────────────────
    monthly_counts: dict[str, int] = {}
    for s in scrobbles:
        monthly_counts[s["month"]] = monthly_counts.get(s["month"], 0) + 1
    monthly = [{"month": m, "scrobbles": c}
               for m, c in sorted(monthly_counts.items())]

    # ── Horaria ───────────────────────────────────────────────────────────
    hourly_counts = [0] * 24
    for s in scrobbles:
        hourly_counts[s["hour"]] += 1
    hourly = [{"hour": h, "scrobbles": c} for h, c in enumerate(hourly_counts) if c > 0]

    # ── Weekday (Lun-Dom) ─────────────────────────────────────────────────
    wd_counts = [0] * 7
    for s in scrobbles:
        wd_counts[s["wd"]] += 1
    weekday = [{"day": WD_LABELS[i], "scrobbles": wd_counts[i]} for i in range(7)]

    # ── Géneros globales ──────────────────────────────────────────────────
    genre_artist_counts: dict[str, set] = {}
    genre_scrobble_counts: dict[str, int] = {}
    for s in scrobbles:
        gs = artists_index[s["artist_k"]]["genres"]
        for g in gs[:3]:
            genre_artist_counts.setdefault(g, set()).add(s["artist_k"])
            genre_scrobble_counts[g] = genre_scrobble_counts.get(g, 0) + 1
    genres_out = sorted(
        [{"genre": g, "artists": len(genre_artist_counts[g]), "scrobbles": genre_scrobble_counts[g]}
         for g in genre_scrobble_counts],
        key=lambda x: -x["scrobbles"]
    )[:40]

    # ── Totales ───────────────────────────────────────────────────────────
    total = len(scrobbles)
    first_ts = scrobbles[0]["ts_iso"] if scrobbles else None
    last_ts  = scrobbles[-1]["ts_iso"] if scrobbles else None

    # ── Top 15 artistas por mes ───────────────────────────────────────────
    ma_counts: dict[str, dict[str, int]] = {}
    for s in scrobbles:
        ma_counts.setdefault(s["month"], {})
        ma_counts[s["month"]][s["artist"]] = ma_counts[s["month"]].get(s["artist"], 0) + 1
    monthly_artists = {
        m: sorted([{"a": a, "n": n} for a, n in ac.items()], key=lambda x: -x["n"])[:15]
        for m, ac in ma_counts.items()
    }

    # ── Top 15 artistas por día semana ────────────────────────────────────
    wd_artist_counts: dict[int, dict[str, int]] = {}
    for s in scrobbles:
        wd_artist_counts.setdefault(s["wd"], {})
        wd_artist_counts[s["wd"]][s["artist"]] = wd_artist_counts[s["wd"]].get(s["artist"], 0) + 1
    weekday_artists = {
        WD_LABELS[wd]: sorted(
            [{"a": a, "n": n} for a, n in ac.items()], key=lambda x: -x["n"]
        )[:15]
        for wd, ac in wd_artist_counts.items()
    }

    # ── Hourly matrix ─────────────────────────────────────────────────────
    hourly_matrix = build_hourly_matrix(scrobbles, artists_index, albums_index)

    out = {
        "generated_at":    datetime.now().isoformat(),
        "username":        username,
        "sources":         [{"source": "lastfm", "count": total}],
        "total_scrobbles": total,
        "first_scrobble":  first_ts,
        "last_scrobble":   last_ts,
        "artists":         artists_out,
        "albums":          albums_out,
        "monthly":         monthly,
        "hourly":          hourly,
        "weekday":         weekday,
        "genres":          genres_out,
        "monthly_artists": monthly_artists,
        "weekday_artists": weekday_artists,
        "hourly_matrix":   hourly_matrix,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"    → {path}  ({len(artists_out):,} artistas · {total:,} scrobbles)")


# ─────────────────────────────────────────────
#  HOURLY MATRIX
# ─────────────────────────────────────────────
def build_hourly_matrix(scrobbles, artists_index, albums_index) -> dict:
    print(f"    Construyendo matriz horaria...")

    # Contar scrobbles por artista
    art_total: dict[str, int] = {}
    for s in scrobbles:
        art_total[s["artist_k"]] = art_total.get(s["artist_k"], 0) + 1

    top_art_keys = sorted(art_total, key=lambda k: -art_total[k])[:MATRIX_TOP_ARTISTS]

    # Matriz artistas × 24h
    art_hourly: dict[str, list] = {ak: [0]*24 for ak in top_art_keys}
    for s in scrobbles:
        if s["artist_k"] in art_hourly:
            art_hourly[s["artist_k"]][s["hour"]] += 1

    art_labels  = [artists_index[ak]["name"] for ak in top_art_keys]
    art_totals  = [art_total[ak] for ak in top_art_keys]
    art_rows    = [art_hourly[ak] for ak in top_art_keys]
    art_peaks   = [row.index(max(row)) if any(row) else 0 for row in art_rows]

    # Contar scrobbles por álbum
    alb_total: dict[tuple, int] = {}
    for s in scrobbles:
        if s["album_k"]:
            alb_total[s["album_k"]] = alb_total.get(s["album_k"], 0) + 1

    top_alb_keys = sorted(alb_total, key=lambda k: -alb_total[k])[:MATRIX_TOP_ALBUMS]

    alb_hourly: dict[tuple, list] = {abk: [0]*24 for abk in top_alb_keys}
    for s in scrobbles:
        if s["album_k"] in alb_hourly:
            alb_hourly[s["album_k"]][s["hour"]] += 1

    alb_labels = [f"{albums_index[abk]['artist']} — {albums_index[abk]['name']}"
                  for abk in top_alb_keys]
    alb_totals = [alb_total[abk] for abk in top_alb_keys]
    alb_rows   = [alb_hourly[abk] for abk in top_alb_keys]
    alb_peaks  = [row.index(max(row)) if any(row) else 0 for row in alb_rows]

    # Géneros
    genre_total: dict[str, int] = {}
    for s in scrobbles:
        for g in artists_index[s["artist_k"]]["genres"][:3]:
            genre_total[g] = genre_total.get(g, 0) + 1

    top_genres = sorted(genre_total, key=lambda g: -genre_total[g])[:MATRIX_TOP_GENRES]

    genre_hourly: dict[str, list] = {g: [0]*24 for g in top_genres}
    for s in scrobbles:
        for g in artists_index[s["artist_k"]]["genres"][:3]:
            if g in genre_hourly:
                genre_hourly[g][s["hour"]] += 1

    gen_labels = top_genres
    gen_totals = [genre_total[g] for g in top_genres]
    gen_rows   = [genre_hourly[g] for g in top_genres]
    gen_peaks  = [row.index(max(row)) if any(row) else 0 for row in gen_rows]

    # Rankings por hora
    hour_rankings: dict = {"artists": [], "albums": [], "genres": []}
    for h in range(24):
        for key, labels, rows in [
            ("artists", art_labels, art_rows),
            ("albums",  alb_labels, alb_rows),
            ("genres",  gen_labels, gen_rows),
        ]:
            ranked = sorted(
                [(labels[i], rows[i][h]) for i in range(len(labels))],
                key=lambda x: -x[1]
            )[:15]
            hour_rankings[key].append(
                [{"name": r[0], "n": r[1]} for r in ranked if r[1] > 0]
            )

    return {
        "artists": {"labels": art_labels, "totals": art_totals,
                    "rows": art_rows, "peak_hours": art_peaks},
        "albums":  {"labels": alb_labels, "totals": alb_totals,
                    "rows": alb_rows, "peak_hours": alb_peaks},
        "genres":  {"labels": gen_labels, "totals": gen_totals,
                    "rows": gen_rows, "peak_hours": gen_peaks},
        "hour_rankings": hour_rankings,
    }


# ─────────────────────────────────────────────
#  EXPORT_DETAIL_JSON
# ─────────────────────────────────────────────
def export_detail_json(scrobbles, artists_index, albums_index, path: str):
    print(f"    Construyendo detail JSON...")

    # ── Datos por artista ─────────────────────────────────────────────────
    ad: dict[int, dict] = {}

    def _get_a(ak):
        aid = artists_index[ak]["id"]
        if aid not in ad:
            ad[aid] = {"monthly": {}, "top_tracks": {}, "top_albums": {},
                       "monthly_albums": {}, "hourly": [0]*24}
        return ad[aid]

    for s in scrobbles:
        d = _get_a(s["artist_k"])
        d["monthly"][s["month"]] = d["monthly"].get(s["month"], 0) + 1
        d["hourly"][s["hour"]] += 1
        if s["track"]:
            d["top_tracks"][s["track"]] = d["top_tracks"].get(s["track"], 0) + 1
        if s["album"]:
            d["top_albums"][s["album"]] = d["top_albums"].get(s["album"], 0) + 1
        if s["album"] and s["album_k"]:
            mm = s["month"]
            d["monthly_albums"].setdefault(mm, {})
            d["monthly_albums"][mm][s["album"]] = d["monthly_albums"][mm].get(s["album"], 0) + 1

    # Serializar artistas
    ad_out: dict[str, dict] = {}
    for aid, d in ad.items():
        monthly_sorted = [{"m": m, "n": n} for m, n in sorted(d["monthly"].items())]
        top_tracks = sorted(d["top_tracks"].items(), key=lambda x: -x[1])[:20]
        top_albums = sorted(d["top_albums"].items(), key=lambda x: -x[1])[:10]
        monthly_albums = {
            m: [{"al": al, "n": n}
                for al, n in sorted(ac.items(), key=lambda x: -x[1])[:5]]
            for m, ac in d["monthly_albums"].items()
        }
        ad_out[str(aid)] = {
            "monthly":        monthly_sorted,
            "top_tracks":     [{"t": t, "n": n} for t, n in top_tracks],
            "top_albums":     [{"a": a, "n": n} for a, n in top_albums],
            "monthly_albums": monthly_albums,
            "hourly":         d["hourly"],
        }

    # ── Datos por álbum ───────────────────────────────────────────────────
    ald: dict[int, dict] = {}

    def _get_al(abk):
        alid = albums_index[abk]["id"]
        if alid not in ald:
            ald[alid] = {"monthly": {}, "top_tracks": {}, "monthly_tracks": {}, "hourly": [0]*24}
        return ald[alid]

    for s in scrobbles:
        if not s["album_k"] or s["album_k"] not in albums_index:
            continue
        d = _get_al(s["album_k"])
        d["monthly"][s["month"]] = d["monthly"].get(s["month"], 0) + 1
        d["hourly"][s["hour"]] += 1
        if s["track"]:
            d["top_tracks"][s["track"]] = d["top_tracks"].get(s["track"], 0) + 1
            mm = s["month"]
            d["monthly_tracks"].setdefault(mm, {})
            d["monthly_tracks"][mm][s["track"]] = d["monthly_tracks"][mm].get(s["track"], 0) + 1

    ald_out: dict[str, dict] = {}
    for alid, d in ald.items():
        monthly_sorted = [{"m": m, "n": n} for m, n in sorted(d["monthly"].items())]
        top_tracks = sorted(d["top_tracks"].items(), key=lambda x: -x[1])[:20]
        monthly_tracks = {
            m: [{"t": t, "n": n}
                for t, n in sorted(tc.items(), key=lambda x: -x[1])[:5]]
            for m, tc in d["monthly_tracks"].items()
        }
        ald_out[str(alid)] = {
            "monthly":        monthly_sorted,
            "top_tracks":     [{"t": t, "n": n} for t, n in top_tracks],
            "monthly_tracks": monthly_tracks,
            "hourly":         d["hourly"],
        }

    # ── Datos por género ──────────────────────────────────────────────────
    gd: dict[str, dict] = {}

    for s in scrobbles:
        gs = artists_index[s["artist_k"]]["genres"][:3]
        for g in gs:
            if g not in gd:
                gd[g] = {"monthly": {}, "top_artists": {}, "monthly_artists": {}, "hourly": [0]*24}
            d = gd[g]
            d["monthly"][s["month"]] = d["monthly"].get(s["month"], 0) + 1
            d["hourly"][s["hour"]] += 1
            d["top_artists"][s["artist"]] = d["top_artists"].get(s["artist"], 0) + 1
            mm = s["month"]
            d["monthly_artists"].setdefault(mm, {})
            d["monthly_artists"][mm][s["artist"]] = d["monthly_artists"][mm].get(s["artist"], 0) + 1

    gd_out: dict[str, dict] = {}
    for g, d in gd.items():
        monthly_sorted = [{"m": m, "n": n} for m, n in sorted(d["monthly"].items())]
        top_artists = sorted(d["top_artists"].items(), key=lambda x: -x[1])[:15]
        monthly_artists = {
            m: [{"a": a, "n": n}
                for a, n in sorted(ac.items(), key=lambda x: -x[1])[:5]]
            for m, ac in d["monthly_artists"].items()
        }
        gd_out[g] = {
            "monthly":         monthly_sorted,
            "top_artists":     [{"a": a, "n": n} for a, n in top_artists],
            "monthly_artists": monthly_artists,
            "hourly":          d["hourly"],
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump({"artists": ad_out, "albums": ald_out, "genres": gd_out},
                  f, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(path) // 1024
    print(f"    → {path}  (~{size_kb} KB)")


# ─────────────────────────────────────────────
#  INDEX HTML
# ─────────────────────────────────────────────
def generate_index_html(users_meta: list[dict], output_dir: Path):
    """
    Genera un index.html con tarjetas para cada usuario.
    users_meta: [{"username": ..., "total": ..., "first": ..., "last": ...,
                  "top_artist": ..., "top_genre": ...}]
    """
    cards_html = ""
    for u in users_meta:
        first = u["first"][:10] if u["first"] else "—"
        last  = u["last"][:10]  if u["last"]  else "—"
        years = ""
        if u["first"] and u["last"]:
            try:
                fd = datetime.fromisoformat(u["first"].replace("Z",""))
                ld = datetime.fromisoformat(u["last"].replace("Z",""))
                yrs = (ld - fd).days / 365.25
                years = f"{yrs:.1f}a"
            except Exception:
                pass
        cards_html += f"""
        <a class="user-card" href="{u['username']}/index.html">
            <div class="uc-avatar">{u['username'][0].upper()}</div>
            <div class="uc-info">
                <div class="uc-name">{u['username']}</div>
                <div class="uc-meta">{u['total']:,} scrobbles · {years}</div>
                <div class="uc-range">{first} → {last}</div>
                {f'<div class="uc-top">♫ {u["top_artist"]}</div>' if u.get("top_artist") else ""}
            </div>
            <div class="uc-arrow">→</div>
        </a>"""

    html = f"""<!doctype html>
<html lang="es">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
    <title>Last.fm Stats — Usuarios</title>
    <link rel="preconnect" href="https://fonts.googleapis.com"/>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@300;400;600&display=swap" rel="stylesheet"/>
    <style>
        *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
        :root{{
            --bg:#0c0c0e;--bg2:#131316;--bg3:#1a1a1f;
            --red:#c05050;--red-dim:#6a2020;--red-bg:#1a0a0a;
            --gold:#c8a84b;--teal:#4a9e8e;
            --text:#e4ddd0;--text-dim:#7a7570;--border:#2a2a30;
            --font-serif:"Playfair Display",Georgia,serif;
            --font-mono:"JetBrains Mono","Courier New",monospace;
        }}
        body{{background:var(--bg);color:var(--text);font-family:var(--font-mono);
              font-size:13px;font-weight:300;min-height:100vh}}
        header{{border-bottom:1px solid var(--border);padding:28px 48px;
                background:linear-gradient(180deg,#161619 0%,transparent 100%)}}
        header h1{{font-family:var(--font-serif);font-size:2rem;font-weight:400}}
        header h1 em{{color:var(--red);font-style:italic}}
        .sub{{color:var(--text-dim);font-size:11px;letter-spacing:.1em;
              text-transform:uppercase;margin-top:6px}}
        main{{padding:40px 48px;max-width:900px}}
        .section-title{{font-family:var(--font-serif);font-size:1.1rem;
                         margin-bottom:20px;padding-bottom:10px;
                         border-bottom:1px solid var(--border);color:var(--text)}}
        .users-grid{{display:flex;flex-direction:column;gap:2px}}
        .user-card{{display:flex;align-items:center;gap:18px;padding:18px 20px;
                    background:var(--bg2);border:1px solid var(--border);
                    text-decoration:none;color:var(--text);
                    transition:border-color .2s,background .2s}}
        .user-card:hover{{border-color:var(--red);background:var(--bg3)}}
        .uc-avatar{{width:44px;height:44px;border-radius:50%;
                    background:var(--red-bg);border:1px solid var(--red-dim);
                    display:flex;align-items:center;justify-content:center;
                    font-family:var(--font-serif);font-size:1.3rem;
                    color:var(--red);flex-shrink:0}}
        .uc-info{{flex:1;min-width:0}}
        .uc-name{{font-family:var(--font-serif);font-size:1.05rem;margin-bottom:3px}}
        .uc-meta{{font-size:12px;color:var(--gold)}}
        .uc-range{{font-size:11px;color:var(--text-dim);margin-top:2px}}
        .uc-top{{font-size:11px;color:var(--text-dim);margin-top:3px;
                 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
        .uc-arrow{{color:var(--text-dim);font-size:16px;flex-shrink:0}}
        .gen-time{{color:var(--text-dim);font-size:10px;margin-top:24px;
                   letter-spacing:.08em}}
        @media(max-width:640px){{header,main{{padding:18px}}}}
    </style>
</head>
<body>
    <header>
        <h1><em>Last.fm</em> Stats</h1>
        <div class="sub">{len(users_meta)} usuarios · {sum(u["total"] for u in users_meta):,} scrobbles en total</div>
    </header>
    <main>
        <div class="section-title">Usuarios</div>
        <div class="users-grid">{cards_html}</div>
        <div class="gen-time">Generado: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
    </main>
</body>
</html>"""

    idx_path = output_dir / "index.html"
    idx_path.write_text(html, encoding="utf-8")
    print(f"  → {idx_path}")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Genera estadísticas HTML/JSON desde lastfm_rym.db"
    )
    parser.add_argument("--db",    default="db/lastfm_rym.db",
                        help="Ruta a la base de datos SQLite (default: db/lastfm_rym.db)")
    parser.add_argument("--out",   default=OUTPUT_DIR,
                        help=f"Carpeta de salida (default: {OUTPUT_DIR})")
    parser.add_argument("--users", nargs="*",
                        help="Usuarios a procesar (default: todos)")
    parser.add_argument("--index-only", action="store_true",
                        help="Solo regenera el index.html leyendo los JSONs ya existentes en --out")
    parser.add_argument("--html",  default=HTML_TEMPLATE,
                        help=f"HTML template (default: {HTML_TEMPLATE})")
    args = parser.parse_args()

    print(f"🎵 Generador de estadísticas — {args.db or 'lastfm_rym.db'}")
    print("=" * 52)

    output_dir = Path(args.out)

    # ── Modo solo índice ──────────────────────────────────────────────────
    if args.index_only:
        print(f"\n📄 Modo --index-only: leyendo JSONs existentes en {output_dir} ...")
        if not output_dir.exists():
            print(f"❌  La carpeta de salida no existe: {output_dir}")
            return
        users_meta = []
        filter_users = set(args.users) if args.users else set()
        seen_usernames: set[str] = set()
        for entry in sorted(output_dir.iterdir()):
            if not entry.is_dir():
                continue
            stats_file = entry / "lastfm_stats.json"
            if not stats_file.exists():
                continue
            try:
                with open(stats_file, encoding="utf-8") as f:
                    data = json.load(f)
                username = data.get("username", entry.name)
                # ✅ Fix 1: el directorio debe coincidir con el username del JSON
                if username != entry.name:
                    print(f"   ⚠️  Omitiendo {entry.name}: username='{username}' no coincide")
                    continue
                # ✅ Fix 2: respetar --users también en modo --index-only
                if filter_users and username not in filter_users:
                    continue
                # ✅ Fix 3: evitar duplicados
                if username in seen_usernames:
                    print(f"   ⚠️  Duplicado omitido: {username}")
                    continue
                seen_usernames.add(username)
                top_artist = data["artists"][0]["artist"] if data.get("artists") else None
                users_meta.append({
                    "username":   username,
                    "total":      data.get("total_scrobbles", 0),
                    "first":      data.get("first_scrobble"),
                    "last":       data.get("last_scrobble"),
                    "top_artist": top_artist,
                })
                print(f"   ✓ {entry.name}")
            except Exception as e:
                print(f"   ⚠️  No se pudo leer {stats_file}: {e}")
        if not users_meta:
            print("❌  No se encontró ningún lastfm_stats.json en la carpeta de salida.")
            return
        users_meta.sort(key=lambda u: u["username"].lower())
        print(f"\n{'─'*52}")
        print("📄 Generando index.html...")
        generate_index_html(users_meta, output_dir)
        print(f"\n✅  ¡Listo! {output_dir}/index.html actualizado con {len(users_meta)} usuarios.")
        return

    # ── Verificaciones ────────────────────────────────────────────────────
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌  No se encontró la BD: {db_path}")
        return

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"❌  No se encontró el template HTML: {html_path}")
        print(f"    Asegúrate de que '{html_path.name}' esté en el mismo directorio.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Abrir BD ──────────────────────────────────────────────────────────
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA query_only = ON")

    # ── Cargar metadatos globales (costosos, se hacen una vez) ────────────
    print("\n📚 Cargando metadatos globales...")
    artist_genres_map  = load_artist_genres(conn)
    album_genres_map   = load_album_genres(conn)
    artist_details_map = load_artist_details(conn)
    album_years_map    = load_album_release_years(conn)
    print(f"   Géneros: {len(artist_genres_map):,} artistas  |  "
          f"Detalles: {len(artist_details_map):,} artistas  |  "
          f"Años álbumes: {len(album_years_map):,}")

    # ── Obtener lista de usuarios ─────────────────────────────────────────
    all_users = [r[0] for r in conn.execute(
        "SELECT DISTINCT user FROM scrobbles WHERE user IS NOT NULL ORDER BY user"
    )]
    if args.users:
        selected = [u for u in args.users if u in all_users]
        missing  = [u for u in args.users if u not in all_users]
        if missing:
            print(f"⚠️   Usuarios no encontrados: {missing}")
        users = selected
    else:
        users = all_users

    if not users:
        print("❌  No hay usuarios para procesar.")
        return

    print(f"\n👥 Usuarios a procesar: {users}")

    # ── Procesar cada usuario ─────────────────────────────────────────────
    users_meta = []
    for user in users:
        print(f"\n{'─'*52}")
        print(f"👤 {user}")

        user_dir = output_dir / user
        user_dir.mkdir(parents=True, exist_ok=True)

        # Construir estructuras en memoria
        scrobbles, artists_index, albums_index = build_user_data(
            conn, user,
            artist_genres_map, album_genres_map,
            artist_details_map, album_years_map
        )

        if not scrobbles:
            print(f"   ⚠️  Sin scrobbles, saltando.")
            continue

        # Exportar JSONs
        stats_path  = user_dir / "lastfm_stats.json"
        detail_path = user_dir / "lastfm_detail.json"

        export_stats_json(scrobbles, artists_index, albums_index,
                          user, str(stats_path))
        export_detail_json(scrobbles, artists_index, albums_index,
                           str(detail_path))

        # Copiar HTML template
        shutil.copy(html_path, user_dir / "index.html")
        print(f"    → {user_dir}/index.html  (copia del template)")

        # Recopilar metadatos para el índice
        top_artist = None
        if artists_index:
            top_artist = sorted(
                artists_index.values(), key=lambda x: -x.get("id", 9999)
            )[0]["name"]
            # El id=1 es el más escuchado
            top_artist = next(
                (v["name"] for v in artists_index.values() if v["id"] == 1), None
            )

        users_meta.append({
            "username":   user,
            "total":      len(scrobbles),
            "first":      scrobbles[0]["ts_iso"] if scrobbles else None,
            "last":       scrobbles[-1]["ts_iso"] if scrobbles else None,
            "top_artist": top_artist,
        })

    conn.close()

    # ── Incorporar usuarios existentes no procesados en este lanzamiento ──
    processed_users = {m["username"] for m in users_meta}
    if output_dir.exists():
        for entry in sorted(output_dir.iterdir()):
            if not entry.is_dir() or entry.name in processed_users:
                continue
            stats_file = entry / "lastfm_stats.json"
            if not stats_file.exists():
                continue
            try:
                with open(stats_file, encoding="utf-8") as f:
                    data = json.load(f)
                username = data.get("username", entry.name)
                if username != entry.name:          # ← línea añadida
                    continue
                top_artist = data["artists"][0]["artist"] if data.get("artists") else None
                users_meta.append({
                    "username":   username,
                    "total":      data.get("total_scrobbles", 0),
                    "first":      data.get("first_scrobble"),
                    "last":       data.get("last_scrobble"),
                    "top_artist": top_artist,
                })
                print(f"   ↺ Usuario existente incorporado al índice: {entry.name}")
            except Exception as e:
                print(f"   ⚠️  No se pudo leer {stats_file}: {e}")

    # Ordenar todos los usuarios alfabéticamente en el índice
    users_meta.sort(key=lambda u: u["username"].lower())

    # ── Generar index ─────────────────────────────────────────────────────
    if users_meta:
        print(f"\n{'─'*52}")
        print("📄 Generando index.html...")
        generate_index_html(users_meta, output_dir)

    print(f"\n✅  ¡Listo! Abre {output_dir}/index.html")
    print(f"   Estructura generada:")
    print(f"   {output_dir}/")
    print(f"     index.html")
    for u in users:
        print(f"     {u}/")
        print(f"       index.html")
        print(f"       lastfm_stats.json")
        print(f"       lastfm_detail.json")


if __name__ == "__main__":
    main()

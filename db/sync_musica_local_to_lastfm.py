#!/usr/bin/env python3
"""
sync_musica_local_to_lastfm.py
──────────────────────────────
Migración one-off: sincroniza metadatos ricos de musica_local.sqlite
(URLs, Wikipedia, bio, Discogs, RYM, producciones...) hacia
lastfm_cache.db en las tablas album_details y artist_details.

Solo rellena campos vacíos (COALESCE / NULLIF): nunca sobreescribe
lo que ya existe en lastfm_cache.

Uso:
    python sync_musica_local_to_lastfm.py \
        --local   /ruta/a/musica_local.sqlite \
        --cache   /ruta/a/lastfm_cache.db \
        [--dry-run] [--only albums|artists|both]

Estrategia de matching:
    Álbumes:  1º por musicbrainz_releasegroupid (mbid exacto)
              2º por _norm(artist) + _norm(album) (fuzzy-text)
    Artistas: 1º por mbid
              2º por _norm(artist_name)
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path


# ── Normalización ─────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())


# ── Columnas nuevas para album_details ───────────────────────────────────────
# Las mismas que migrate_jsons_to_db.py, más las que vienen de musica_local.
# Si ya existen (por haber corrido el otro script antes) se ignoran.
ALBUM_NEW_COLS = [
    ("desc_lfm_album",    "TEXT"),
    ("desc_lfm_artist",   "TEXT"),
    ("desc_mb_album",     "TEXT"),
    ("desc_mb_artist",    "TEXT"),
    ("genres_json",       "TEXT"),
    ("yt_id",             "TEXT"),
    ("cover_url",         "TEXT"),
    ("rym_url",           "TEXT"),
    ("spotify_id",        "TEXT"),
    ("spotify_url",       "TEXT"),
    ("bandcamp_url",      "TEXT"),
    ("youtube_url",       "TEXT"),
    ("discogs_url",       "TEXT"),
    ("wikipedia_url",     "TEXT"),
    ("wikipedia_content", "TEXT"),
    ("producers",         "TEXT"),
    ("engineers",         "TEXT"),
    ("credits",           "TEXT"),
    ("scaruffi_rating",   "REAL"),
    ("scaruffi_note",     "TEXT"),
    ("source_collection", "TEXT"),
    # Extra desde musica_local
    ("aoty_user_score",   "INTEGER"),
    ("aoty_critic_score", "INTEGER"),
    ("aoty_url",          "TEXT"),
    ("metacritic_score",  "INTEGER"),
    ("metacritic_url",    "TEXT"),
    ("allmusic_url",      "TEXT"),
    ("apple_url",         "TEXT"),
    ("deezer_url",        "TEXT"),
    ("amazon_url",        "TEXT"),
    ("genius_url",        "TEXT"),
    ("originalyear",      "INTEGER"),
    ("media",             "TEXT"),
    ("releasecountry",    "TEXT"),
    ("catalognumber",     "TEXT"),
]

# Columnas nuevas para artist_details
ARTIST_NEW_COLS = [
    ("spotify_url",     "TEXT"),
    ("youtube_url",     "TEXT"),
    ("discogs_url",     "TEXT"),
    ("bandcamp_url",    "TEXT"),
    ("wikipedia_url",   "TEXT"),
    ("wikipedia_content","TEXT"),
    ("rateyourmusic_url","TEXT"),
    ("website",         "TEXT"),
    ("origin",          "TEXT"),
    ("formed_year",     "INTEGER"),
    ("aliases",         "TEXT"),
    ("member_of",       "TEXT"),
    ("allmusic_url",    "TEXT"),
    ("setlistfm_url",   "TEXT"),
    ("soundcloud_url",  "TEXT"),
    ("instagram_url",   "TEXT"),
    ("img_url",         "TEXT"),
]


# ── DDL helpers ───────────────────────────────────────────────────────────────
def ensure_columns(conn: sqlite3.Connection, table: str,
                   col_defs: list, dry_run: bool) -> set:
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for col_name, col_type in col_defs:
        if col_name not in existing:
            sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
            print(f"  + ADD COLUMN {table}.{col_name} {col_type}")
            if not dry_run:
                conn.execute(sql)
            existing.add(col_name)
    if not dry_run:
        conn.commit()
    return existing


# ── Update helper ─────────────────────────────────────────────────────────────
def update_row(conn: sqlite3.Connection, table: str,
               where_col: str, where_val,
               fields: dict, existing_cols: set,
               dry_run: bool) -> bool:
    """
    UPDATE tabla SET col = COALESCE(NULLIF(col,''), ?)
    Solo para campos con valor y columna existente.
    """
    valid = {k: v for k, v in fields.items()
             if v not in (None, "", [], {}) and k in existing_cols}
    if not valid:
        return False
    if dry_run:
        return True

    ts = int(time.time())
    set_parts = []
    params = []
    for col, val in valid.items():
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        set_parts.append(f"{col} = COALESCE(NULLIF(CAST({col} AS TEXT),''), ?)")
        params.append(str(val) if not isinstance(val, str) else val)

    set_parts.append("last_updated = ?")
    params.append(ts)
    params.append(where_val)

    conn.execute(
        f"UPDATE {table} SET {', '.join(set_parts)} WHERE {where_col}=?",
        params
    )
    return True


# ── Álbumes ───────────────────────────────────────────────────────────────────
def sync_albums(local: sqlite3.Connection, cache: sqlite3.Connection,
                dry_run: bool):
    print("\n─── Sincronizando álbumes ───")
    existing_cols = ensure_columns(cache, "album_details", ALBUM_NEW_COLS, dry_run)

    # Consulta rica de musica_local: álbumes + scores + urls
    query = """
        SELECT
            ar.name                         AS artist_name,
            al.name                         AS album_name,
            al.musicbrainz_releasegroupid   AS rg_mbid,
            al.spotify_url,
            al.spotify_id,
            al.youtube_url,
            al.discogs_url,
            al.rateyourmusic_url            AS rym_url,
            al.bandcamp_url,
            al.wikipedia_url,
            al.wikipedia_content,
            al.producers,
            al.engineers,
            al.mastering_engineers,
            al.credits,
            al.originalyear,
            al.media,
            al.releasecountry,
            al.catalognumber,
            -- AOTY
            aoty.user_score                 AS aoty_user_score,
            aoty.critic_score               AS aoty_critic_score,
            aoty.aoty_url,
            -- Metacritic
            mc.metascore                    AS metacritic_score,
            mc.metacritic_url,
            -- mb_release_group extra URLs
            rg.allmusic_url,
            rg.apple_url,
            rg.deezer_url,
            rg.amazon_url,
            rg.genius_url
        FROM albums al
        JOIN artists ar ON ar.id = al.artist_id
        LEFT JOIN album_aoty    aoty ON aoty.album_id = al.id
        LEFT JOIN album_metacritic mc ON mc.album_id  = al.id
        LEFT JOIN mb_release_group rg ON rg.album_id  = al.id
        WHERE al.name IS NOT NULL AND ar.name IS NOT NULL
    """
    rows = local.execute(query).fetchall()
    cols = [d[0] for d in local.execute(query).description] if rows else []
    # Re-fetch with description
    cur = local.execute(query)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()

    print(f"  📦 {len(rows)} álbumes en musica_local")

    matched_mbid = 0
    matched_norm = 0
    no_match     = 0

    for row in rows:
        r = dict(zip(cols, row))
        artist = r["artist_name"] or ""
        album  = r["album_name"]  or ""
        rg_mbid = r.get("rg_mbid") or ""

        fields = {
            "spotify_url":       r.get("spotify_url"),
            "spotify_id":        r.get("spotify_id"),
            "youtube_url":       r.get("youtube_url"),
            "discogs_url":       r.get("discogs_url"),
            "rym_url":           r.get("rym_url"),
            "bandcamp_url":      r.get("bandcamp_url"),
            "wikipedia_url":     r.get("wikipedia_url"),
            "wikipedia_content": r.get("wikipedia_content"),
            "producers":         r.get("producers"),
            "engineers":         (r.get("engineers") or "") + (
                                  (" / " + r["mastering_engineers"])
                                  if r.get("mastering_engineers") else ""),
            "credits":           r.get("credits"),
            "originalyear":      r.get("originalyear"),
            "media":             r.get("media"),
            "releasecountry":    r.get("releasecountry"),
            "catalognumber":     r.get("catalognumber"),
            "aoty_user_score":   r.get("aoty_user_score"),
            "aoty_critic_score": r.get("aoty_critic_score"),
            "aoty_url":          r.get("aoty_url"),
            "metacritic_score":  r.get("metacritic_score"),
            "metacritic_url":    r.get("metacritic_url"),
            "allmusic_url":      r.get("allmusic_url"),
            "apple_url":         r.get("apple_url"),
            "deezer_url":        r.get("deezer_url"),
            "amazon_url":        r.get("amazon_url"),
            "genius_url":        r.get("genius_url"),
        }

        # Quitar vacíos
        fields = {k: v for k, v in fields.items() if v not in (None, "", 0)}

        updated = False

        # ── Intento 1: match por release_group_mbid ──
        if rg_mbid:
            hit = cache.execute(
                "SELECT artist, album FROM album_details WHERE release_group_mbid=? LIMIT 1",
                (rg_mbid,)
            ).fetchone()
            if hit:
                ok = update_row(cache, "album_details", "release_group_mbid", rg_mbid,
                                fields, existing_cols, dry_run)
                if ok:
                    matched_mbid += 1
                    updated = True

        # ── Intento 2: match por nombre normalizado ──
        if not updated:
            na = _norm(artist)
            nt = _norm(album)
            # Buscar en cache por nombre exacto (sin normalizar, SQLite no tiene _norm)
            hit = cache.execute(
                "SELECT artist, album FROM album_details WHERE artist=? AND album=? LIMIT 1",
                (artist, album)
            ).fetchone()
            if hit:
                ok = update_row(cache, "album_details",
                                "rowid",
                                cache.execute(
                                    "SELECT rowid FROM album_details WHERE artist=? AND album=?",
                                    (artist, album)
                                ).fetchone()[0],
                                fields, existing_cols, dry_run)
                if ok:
                    matched_norm += 1
                    updated = True

        if not updated:
            no_match += 1

    if not dry_run:
        cache.commit()

    print(f"  ✅ Match por MBID:  {matched_mbid}")
    print(f"  ✅ Match por nombre: {matched_norm}")
    print(f"  ⚠  Sin match:       {no_match}")


# ── Artistas ──────────────────────────────────────────────────────────────────
def sync_artists(local: sqlite3.Connection, cache: sqlite3.Connection,
                 dry_run: bool):
    print("\n─── Sincronizando artistas ───")
    existing_cols = ensure_columns(cache, "artist_details", ARTIST_NEW_COLS, dry_run)

    query = """
        SELECT
            ar.name,
            ar.mbid,
            ar.spotify_url,
            ar.youtube_url,
            ar.discogs_url,
            ar.rateyourmusic_url,
            ar.bandcamp_url,
            ar.wikipedia_url,
            ar.wikipedia_content,
            ar.website,
            ar.origin,
            ar.formed_year,
            ar.aliases,
            ar.member_of,
            ar.img_urls,
            -- redes desde artists_networks
            an.allmusic,
            an.setlist_fm     AS setlistfm_url,
            an.soundcloud,
            an.instagram
        FROM artists ar
        LEFT JOIN artists_networks an ON an.artist_id = ar.id
        WHERE ar.name IS NOT NULL
    """
    cur = local.execute(query)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(f"  📦 {len(rows)} artistas en musica_local")

    matched_mbid = 0
    matched_norm = 0
    no_match     = 0

    for row in rows:
        r = dict(zip(cols, row))
        name = r["name"] or ""
        mbid = r.get("mbid") or ""

        # img_url: tomar primera URL del JSON array
        img_url = ""
        if r.get("img_urls"):
            try:
                imgs = json.loads(r["img_urls"])
                img_url = imgs[0] if isinstance(imgs, list) and imgs else ""
            except Exception:
                pass

        fields = {
            "spotify_url":      r.get("spotify_url"),
            "youtube_url":      r.get("youtube_url"),
            "discogs_url":      r.get("discogs_url"),
            "rateyourmusic_url":r.get("rateyourmusic_url"),
            "bandcamp_url":     r.get("bandcamp_url"),
            "wikipedia_url":    r.get("wikipedia_url"),
            "wikipedia_content":r.get("wikipedia_content"),
            "website":          r.get("website"),
            "origin":           r.get("origin"),
            "formed_year":      r.get("formed_year"),
            "aliases":          r.get("aliases"),
            "member_of":        r.get("member_of"),
            "img_url":          img_url,
            "allmusic_url":     r.get("allmusic"),
            "setlistfm_url":    r.get("setlistfm_url"),
            "soundcloud_url":   r.get("soundcloud"),
            "instagram_url":    r.get("instagram"),
        }
        fields = {k: v for k, v in fields.items() if v not in (None, "", 0)}

        updated = False

        # ── Match por mbid ──
        if mbid:
            hit = cache.execute(
                "SELECT 1 FROM artist_details WHERE mbid=? LIMIT 1", (mbid,)
            ).fetchone()
            if hit:
                ok = update_row(cache, "artist_details", "mbid", mbid,
                                fields, existing_cols, dry_run)
                if ok:
                    matched_mbid += 1
                    updated = True

        # ── Match por nombre exacto ──
        if not updated:
            hit = cache.execute(
                "SELECT 1 FROM artist_details WHERE artist=? LIMIT 1", (name,)
            ).fetchone()
            if hit:
                ok = update_row(cache, "artist_details", "artist", name,
                                fields, existing_cols, dry_run)
                if ok:
                    matched_norm += 1
                    updated = True

        if not updated:
            no_match += 1

    if not dry_run:
        cache.commit()

    print(f"  ✅ Match por MBID:   {matched_mbid}")
    print(f"  ✅ Match por nombre:  {matched_norm}")
    print(f"  ⚠  Sin match:        {no_match}")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Sincroniza musica_local.sqlite → lastfm_cache.db (one-off)"
    )
    ap.add_argument("--local",  required=True, help="Ruta a musica_local.sqlite")
    ap.add_argument("--cache",  required=True, help="Ruta a lastfm_cache.db")
    ap.add_argument("--dry-run", action="store_true",
                    help="Mostrar qué se haría sin escribir nada")
    ap.add_argument("--only", choices=["albums", "artists", "both"],
                    default="both", help="Qué sincronizar (default: both)")
    args = ap.parse_args()

    local_path = Path(args.local)
    cache_path = Path(args.cache)

    for p in (local_path, cache_path):
        if not p.exists():
            print(f"ERROR: No existe {p}", file=sys.stderr)
            sys.exit(1)

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Conectando bases de datos...")
    local = sqlite3.connect(str(local_path))
    cache = sqlite3.connect(str(cache_path))
    cache.execute("PRAGMA journal_mode=WAL")
    cache.execute("PRAGMA synchronous=NORMAL")
    # musica_local en modo solo lectura
    local.execute("PRAGMA query_only=ON")

    if args.only in ("albums", "both"):
        sync_albums(local, cache, args.dry_run)

    if args.only in ("artists", "both"):
        sync_artists(local, cache, args.dry_run)

    local.close()
    cache.close()
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}✅ Sincronización completada.")


if __name__ == "__main__":
    main()

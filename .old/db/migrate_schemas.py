#!/usr/bin/env python3
"""
migrate_schemas.py
==================
Migra las bases de datos musicales al schema v2 optimizado.

Cambios en must_hear_rym.db  →  must_hear_rym_new.db:
  - Extrae texto largo de albums → album_metadata (desc_*, wikipedia_content,
    producers, engineers, credits)
  - Elimina genres_json (redundante con la M2M genres/album_genres)
  - El resto del schema queda idéntico

Cambios en lastfm_normalized.db  →  lastfm_cache_rym_new_normalized.db:
  - artists: url → lastfm_url; añade columnas de enriquecimiento
  - albums:  release_year → year; añade columnas de enriquecimiento
  - Crea album_metadata (texto largo)
  - Convierte genres_lastfm/genres_musicbrainz/genres_discogs (JSON)
    a tablas M2M: genres + album_genres + artist_genres
  - Crea group_stats (caché pre-calculada)

Uso:
  python3 db/migrate_schemas.py --all
  python3 db/migrate_schemas.py --must-hear
  python3 db/migrate_schemas.py --lastfm
  python3 db/migrate_schemas.py --all --db-dir /ruta/a/db/
"""

import argparse
import json
import os
import re
import sqlite3
import time
from pathlib import Path


def _user_table(username: str) -> str:
    """Nombre de la tabla de scrobbles para un usuario (igual que en db_new/update_database.py)."""
    safe = re.sub(r'[^a-z0-9]', '_', username.lower()).strip('_')
    return f"scrobbles_{safe}"


# ── Campos que salen de albums y van a album_metadata ─────────────────────────
METADATA_FIELDS = {
    "desc_lfm_album", "desc_lfm_artist",
    "desc_mb_album",  "desc_mb_artist",
    "wikipedia_content",
    "producers", "engineers", "credits",
}


# ══════════════════════════════════════════════════════════════════════════════
# MUST HEAR
# ══════════════════════════════════════════════════════════════════════════════

def create_must_hear_schema(conn: sqlite3.Connection):
    conn.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;

    CREATE TABLE artists (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        name              TEXT    NOT NULL,
        mbid              TEXT    UNIQUE,
        bio               TEXT,
        tags              TEXT,
        similar_artists   TEXT,
        begin_date        TEXT,
        end_date          TEXT,
        artist_type       TEXT,
        country           TEXT,
        disambiguation    TEXT,
        origin            TEXT,
        formed_year       INTEGER,
        aliases           TEXT,
        member_of         TEXT,
        spotify_url       TEXT,
        youtube_url       TEXT,
        discogs_url       TEXT,
        bandcamp_url      TEXT,
        rateyourmusic_url TEXT,
        wikipedia_url     TEXT,
        wikipedia_content TEXT,
        lastfm_url        TEXT,
        musicbrainz_url   TEXT,
        website           TEXT,
        allmusic_url      TEXT,
        setlistfm_url     TEXT,
        soundcloud_url    TEXT,
        instagram_url     TEXT,
        img_url           TEXT,
        img_urls          TEXT,
        listeners         TEXT,
        playcount         TEXT,
        last_updated      INTEGER,
        added_timestamp   INTEGER
    );
    CREATE INDEX idx_mh_artists_name ON artists(name);
    CREATE INDEX idx_mh_artists_mbid ON artists(mbid);

    CREATE TABLE albums (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        artist_id          INTEGER REFERENCES artists(id),
        name               TEXT    NOT NULL,
        year               INTEGER,
        originalyear       INTEGER,
        mbid               TEXT,
        release_group_mbid TEXT    UNIQUE,
        label              TEXT,
        genre              TEXT,
        total_tracks       INTEGER,
        media              TEXT,
        releasecountry     TEXT,
        catalognumber      TEXT,
        album_type         TEXT,
        spotify_url        TEXT,
        spotify_id         TEXT,
        youtube_url        TEXT,
        yt_id              TEXT,
        discogs_url        TEXT,
        bandcamp_url       TEXT,
        rateyourmusic_url  TEXT,
        wikipedia_url      TEXT,
        lastfm_url         TEXT,
        musicbrainz_url    TEXT,
        allmusic_url       TEXT,
        apple_url          TEXT,
        deezer_url         TEXT,
        amazon_url         TEXT,
        genius_url         TEXT,
        metacritic_url     TEXT,
        aoty_url           TEXT,
        scaruffi_rating    REAL,
        scaruffi_note      TEXT,
        aoty_user_score    INTEGER,
        aoty_critic_score  INTEGER,
        metacritic_score   INTEGER,
        cover_url          TEXT,
        album_art_path     TEXT,
        last_updated       INTEGER,
        added_timestamp    INTEGER
    );
    CREATE INDEX idx_mh_albums_artist ON albums(artist_id);
    CREATE INDEX idx_mh_albums_year   ON albums(year);

    -- Texto largo separado (solo se carga en vista de detalle)
    CREATE TABLE album_metadata (
        album_id           INTEGER PRIMARY KEY REFERENCES albums(id),
        desc_lfm_album     TEXT,
        desc_lfm_artist    TEXT,
        desc_mb_album      TEXT,
        desc_mb_artist     TEXT,
        wikipedia_content  TEXT,
        producers          TEXT,
        engineers          TEXT,
        credits            TEXT
    );

    CREATE TABLE genres (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT    NOT NULL UNIQUE,
        source       TEXT,
        last_updated INTEGER
    );

    CREATE TABLE album_genres (
        album_id INTEGER NOT NULL REFERENCES albums(id),
        genre_id INTEGER NOT NULL REFERENCES genres(id),
        weight   REAL    DEFAULT 1.0,
        PRIMARY KEY (album_id, genre_id)
    );
    CREATE INDEX idx_mh_ag_genre ON album_genres(genre_id);

    CREATE TABLE collections (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        slug            TEXT    NOT NULL UNIQUE,
        name            TEXT    NOT NULL,
        total_albums    INTEGER DEFAULT 0,
        source_url      TEXT,
        source_type     TEXT,
        last_updated    INTEGER,
        added_timestamp INTEGER
    );

    CREATE TABLE collection_albums (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        collection_id INTEGER NOT NULL REFERENCES collections(id),
        album_id      INTEGER NOT NULL REFERENCES albums(id),
        rank          INTEGER,
        UNIQUE (collection_id, album_id)
    );
    CREATE INDEX idx_mh_ca_collection ON collection_albums(collection_id);
    CREATE INDEX idx_mh_ca_album      ON collection_albums(album_id);

    CREATE TABLE users (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        username         TEXT    NOT NULL UNIQUE,
        lastfm_username  TEXT,
        added_timestamp  INTEGER
    );

    CREATE TABLE user_heard (
        user_id       INTEGER NOT NULL REFERENCES users(id),
        album_id      INTEGER NOT NULL REFERENCES albums(id),
        first_heard_at INTEGER,
        PRIMARY KEY (user_id, album_id)
    );
    CREATE INDEX idx_mh_uh_album ON user_heard(album_id);
    """)
    conn.commit()


def migrate_must_hear(src_path: Path, dst_path: Path):
    print(f"\n{'='*60}")
    print(f"  must_hear:  {src_path.name}  →  {dst_path.name}")
    print(f"{'='*60}")

    if dst_path.exists():
        dst_path.unlink()
        print(f"  (borrado {dst_path.name} previo)")

    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(dst_path))

    create_must_hear_schema(dst)

    # ── Artists ──────────────────────────────────────────────────────────────
    artist_id_map = {}
    rows = src.execute("SELECT * FROM artists").fetchall()
    print(f"  artists: {len(rows):,}")
    cols = [d[0] for d in src.execute("SELECT * FROM artists LIMIT 0").description]
    for row in rows:
        d = dict(zip(cols, row))
        dst.execute("""
            INSERT INTO artists (
                id, name, mbid, bio, tags, similar_artists,
                begin_date, end_date, artist_type, country, disambiguation,
                origin, formed_year, aliases, member_of,
                spotify_url, youtube_url, discogs_url, bandcamp_url,
                rateyourmusic_url, wikipedia_url, wikipedia_content,
                lastfm_url, musicbrainz_url, website, allmusic_url,
                setlistfm_url, soundcloud_url, instagram_url,
                img_url, img_urls, listeners, playcount,
                last_updated, added_timestamp
            ) VALUES (
                :id,:name,:mbid,:bio,:tags,:similar_artists,
                :begin_date,:end_date,:artist_type,:country,:disambiguation,
                :origin,:formed_year,:aliases,:member_of,
                :spotify_url,:youtube_url,:discogs_url,:bandcamp_url,
                :rateyourmusic_url,:wikipedia_url,:wikipedia_content,
                :lastfm_url,:musicbrainz_url,:website,:allmusic_url,
                :setlistfm_url,:soundcloud_url,:instagram_url,
                :img_url,:img_urls,:listeners,:playcount,
                :last_updated,:added_timestamp
            )
        """, d)
        artist_id_map[d["id"]] = d["id"]
    dst.commit()

    # ── Albums + album_metadata ───────────────────────────────────────────────
    album_rows = src.execute("SELECT * FROM albums").fetchall()
    album_cols = [d[0] for d in src.execute("SELECT * FROM albums LIMIT 0").description]
    print(f"  albums: {len(album_rows):,}")

    meta_count = 0
    for row in album_rows:
        d = dict(zip(album_cols, row))
        dst.execute("""
            INSERT INTO albums (
                id, artist_id, name, year, originalyear,
                mbid, release_group_mbid,
                label, genre, total_tracks, media, releasecountry,
                catalognumber, album_type,
                spotify_url, spotify_id, youtube_url, yt_id,
                discogs_url, bandcamp_url, rateyourmusic_url, wikipedia_url,
                lastfm_url, musicbrainz_url, allmusic_url, apple_url,
                deezer_url, amazon_url, genius_url, metacritic_url, aoty_url,
                scaruffi_rating, scaruffi_note,
                aoty_user_score, aoty_critic_score, metacritic_score,
                cover_url, album_art_path, last_updated, added_timestamp
            ) VALUES (
                :id,:artist_id,:name,:year,:originalyear,
                :mbid,:release_group_mbid,
                :label,:genre,:total_tracks,:media,:releasecountry,
                :catalognumber,:album_type,
                :spotify_url,:spotify_id,:youtube_url,:yt_id,
                :discogs_url,:bandcamp_url,:rateyourmusic_url,:wikipedia_url,
                :lastfm_url,:musicbrainz_url,:allmusic_url,:apple_url,
                :deezer_url,:amazon_url,:genius_url,:metacritic_url,:aoty_url,
                :scaruffi_rating,:scaruffi_note,
                :aoty_user_score,:aoty_critic_score,:metacritic_score,
                :cover_url,:album_art_path,:last_updated,:added_timestamp
            )
        """, d)

        # Solo insertar album_metadata si hay al menos un campo no vacío
        meta = {f: d.get(f) for f in METADATA_FIELDS}
        if any(v for v in meta.values()):
            dst.execute("""
                INSERT INTO album_metadata (
                    album_id, desc_lfm_album, desc_lfm_artist,
                    desc_mb_album, desc_mb_artist, wikipedia_content,
                    producers, engineers, credits
                ) VALUES (
                    :album_id,:desc_lfm_album,:desc_lfm_artist,
                    :desc_mb_album,:desc_mb_artist,:wikipedia_content,
                    :producers,:engineers,:credits
                )
            """, {"album_id": d["id"], **meta})
            meta_count += 1

    dst.commit()
    print(f"  album_metadata: {meta_count:,} filas con datos")

    # ── Genres + album_genres ─────────────────────────────────────────────────
    genre_rows = src.execute("SELECT * FROM genres").fetchall()
    genre_cols = [d[0] for d in src.execute("SELECT * FROM genres LIMIT 0").description]
    print(f"  genres: {len(genre_rows):,}")
    for row in genre_rows:
        d = dict(zip(genre_cols, row))
        dst.execute(
            "INSERT INTO genres (id, name, source, last_updated) VALUES (?,?,?,?)",
            (d["id"], d["name"], d.get("source"), d.get("last_updated"))
        )

    ag_rows = src.execute("SELECT * FROM album_genres").fetchall()
    ag_cols = [d[0] for d in src.execute("SELECT * FROM album_genres LIMIT 0").description]
    print(f"  album_genres: {len(ag_rows):,}")
    for row in ag_rows:
        d = dict(zip(ag_cols, row))
        dst.execute(
            "INSERT OR IGNORE INTO album_genres (album_id, genre_id, weight) VALUES (?,?,?)",
            (d["album_id"], d["genre_id"], d.get("weight", 1.0))
        )
    dst.commit()

    # ── Collections + collection_albums ───────────────────────────────────────
    coll_cols = [d[0] for d in src.execute("SELECT * FROM collections LIMIT 0").description]
    for row in src.execute("SELECT * FROM collections").fetchall():
        d = dict(zip(coll_cols, row))
        dst.execute(
            "INSERT INTO collections (id, slug, name, total_albums, "
            "source_url, source_type, last_updated, added_timestamp) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (d.get("id"), d.get("slug"), d.get("name"), d.get("total_albums"),
             d.get("source_url"), d.get("source_type"),
             d.get("last_updated"), d.get("added_timestamp"))
        )

    ca_cols = [d[0] for d in src.execute("SELECT * FROM collection_albums LIMIT 0").description]
    for row in src.execute("SELECT * FROM collection_albums").fetchall():
        d = dict(zip(ca_cols, row))
        dst.execute(
            "INSERT INTO collection_albums (id, collection_id, album_id, rank) "
            "VALUES (?,?,?,?)",
            (d.get("id"), d.get("collection_id"), d.get("album_id"), d.get("rank"))
        )
    dst.commit()
    print(f"  collections: {dst.execute('SELECT COUNT(*) FROM collections').fetchone()[0]}")
    print(f"  collection_albums: {dst.execute('SELECT COUNT(*) FROM collection_albums').fetchone()[0]:,}")

    # ── Users + user_heard ────────────────────────────────────────────────────
    user_cols = [d[0] for d in src.execute("SELECT * FROM users LIMIT 0").description]
    for row in src.execute("SELECT * FROM users").fetchall():
        d = dict(zip(user_cols, row))
        dst.execute(
            "INSERT INTO users (id, username, lastfm_username, added_timestamp) "
            "VALUES (?,?,?,?)",
            (d.get("id"), d.get("username"),
             d.get("lastfm_username"), d.get("added_timestamp"))
        )

    uh_rows = src.execute("SELECT * FROM user_heard").fetchall()
    uh_cols = [d[0] for d in src.execute("SELECT * FROM user_heard LIMIT 0").description]
    for row in uh_rows:
        d = dict(zip(uh_cols, row))
        dst.execute(
            "INSERT OR IGNORE INTO user_heard (user_id, album_id, first_heard_at) "
            "VALUES (?,?,?)", (d["user_id"], d["album_id"], d.get("first_heard_at"))
        )
    dst.commit()
    print(f"  users: {dst.execute('SELECT COUNT(*) FROM users').fetchone()[0]}")
    print(f"  user_heard: {dst.execute('SELECT COUNT(*) FROM user_heard').fetchone()[0]:,}")

    src.close()
    dst.execute("PRAGMA optimize")
    dst.close()
    size = dst_path.stat().st_size / 1024 / 1024
    print(f"\n  ✅ {dst_path.name}  ({size:.1f} MB)")


# ══════════════════════════════════════════════════════════════════════════════
# LASTFM NORMALIZED
# ══════════════════════════════════════════════════════════════════════════════

def create_lastfm_schema(conn: sqlite3.Connection):
    conn.executescript("""
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;

    CREATE TABLE users (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT    NOT NULL UNIQUE,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );

    CREATE TABLE artists (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        name              TEXT    NOT NULL UNIQUE,
        mbid              TEXT,
        -- Last.fm
        listeners         INTEGER,
        playcount         INTEGER,
        lastfm_url        TEXT,
        img_url           TEXT,
        img_urls          TEXT,
        -- Descripción
        bio               TEXT,
        -- Identidad
        country           TEXT,
        begin_date        TEXT,
        end_date          TEXT,
        formed_year       INTEGER,
        artist_type       TEXT,
        disambiguation    TEXT,
        aliases           TEXT,
        member_of         TEXT,
        -- URLs
        spotify_url       TEXT,
        youtube_url       TEXT,
        discogs_url       TEXT,
        bandcamp_url      TEXT,
        rateyourmusic_url TEXT,
        wikipedia_url     TEXT,
        musicbrainz_url   TEXT,
        -- Timestamps
        created_at        INTEGER DEFAULT (strftime('%s','now')),
        last_updated      INTEGER DEFAULT (strftime('%s','now')),
        added_timestamp   INTEGER
    );
    CREATE UNIQUE INDEX idx_lfm_artists_mbid ON artists(mbid) WHERE mbid IS NOT NULL;
    CREATE INDEX        idx_lfm_artists_name ON artists(name);

    CREATE TABLE albums (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT    NOT NULL,
        artist_id          INTEGER NOT NULL REFERENCES artists(id),
        mbid               TEXT,
        -- Catálogo
        year               INTEGER,
        originalyear       INTEGER,
        release_date       TEXT,
        release_group_mbid TEXT,
        album_type         TEXT,
        status             TEXT,
        country            TEXT,
        barcode            TEXT,
        total_tracks       INTEGER,
        label              TEXT,
        -- URLs (acceso rápido en paneles HTML)
        spotify_id         TEXT,
        spotify_url        TEXT,
        yt_id              TEXT,
        rateyourmusic_url  TEXT,
        cover_url          TEXT,
        wikipedia_url      TEXT,
        lastfm_url         TEXT,
        musicbrainz_url    TEXT,
        -- Scores
        scaruffi_rating    REAL,
        scaruffi_note      TEXT,
        aoty_user_score    INTEGER,
        aoty_critic_score  INTEGER,
        metacritic_score   INTEGER,
        -- Timestamps
        created_at         INTEGER DEFAULT (strftime('%s','now')),
        last_updated       INTEGER DEFAULT (strftime('%s','now')),
        added_timestamp    INTEGER,
        UNIQUE (name, artist_id)
    );
    CREATE UNIQUE INDEX idx_lfm_albums_mbid    ON albums(mbid) WHERE mbid IS NOT NULL;
    CREATE INDEX        idx_lfm_albums_rg_mbid ON albums(release_group_mbid);
    CREATE INDEX        idx_lfm_albums_artist  ON albums(artist_id);
    CREATE INDEX        idx_lfm_albums_year    ON albums(year);

    -- Texto largo: solo se carga en vista de detalle
    CREATE TABLE album_metadata (
        album_id          INTEGER PRIMARY KEY REFERENCES albums(id),
        desc_lfm_album    TEXT,
        desc_lfm_artist   TEXT,
        desc_mb_album     TEXT,
        desc_mb_artist    TEXT,
        wikipedia_content TEXT,
        producers         TEXT,
        engineers         TEXT,
        credits           TEXT
    );

    CREATE TABLE tracks (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT    NOT NULL,
        artist_id    INTEGER NOT NULL REFERENCES artists(id),
        album_id     INTEGER          REFERENCES albums(id),
        mbid         TEXT,
        duration_ms  INTEGER,
        track_number INTEGER,
        isrc         TEXT,
        created_at   INTEGER DEFAULT (strftime('%s','now')),
        last_updated INTEGER DEFAULT (strftime('%s','now')),
        UNIQUE (name, artist_id)
    );
    CREATE UNIQUE INDEX idx_lfm_tracks_mbid   ON tracks(mbid)    WHERE mbid IS NOT NULL;
    CREATE INDEX        idx_lfm_tracks_artist ON tracks(artist_id);
    CREATE INDEX        idx_lfm_tracks_album  ON tracks(album_id);

    -- Géneros normalizados
    CREATE TABLE genres (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT    NOT NULL UNIQUE,
        source       TEXT,
        last_updated INTEGER
    );

    CREATE TABLE album_genres (
        album_id INTEGER NOT NULL REFERENCES albums(id),
        genre_id INTEGER NOT NULL REFERENCES genres(id),
        weight   REAL    DEFAULT 1.0,
        PRIMARY KEY (album_id, genre_id)
    );
    CREATE INDEX idx_lfm_ag_genre ON album_genres(genre_id);

    CREATE TABLE artist_genres (
        artist_id INTEGER NOT NULL REFERENCES artists(id),
        genre_id  INTEGER NOT NULL REFERENCES genres(id),
        weight    REAL    DEFAULT 1.0,
        PRIMARY KEY (artist_id, genre_id)
    );
    CREATE INDEX idx_lfm_artg_genre ON artist_genres(genre_id);

    -- Las tablas de scrobbles son por usuario: scrobbles_<username>
    -- Se crean dinámicamente en migrate_lastfm() y en db_new/update_database.py

    CREATE TABLE user_first_artist_listen (
        user_id         INTEGER NOT NULL REFERENCES users(id),
        artist_id       INTEGER NOT NULL REFERENCES artists(id),
        first_timestamp INTEGER,
        PRIMARY KEY (user_id, artist_id)
    );

    CREATE TABLE user_first_album_listen (
        user_id         INTEGER NOT NULL REFERENCES users(id),
        album_id        INTEGER NOT NULL REFERENCES albums(id),
        first_timestamp INTEGER,
        PRIMARY KEY (user_id, album_id)
    );

    CREATE TABLE user_first_track_listen (
        user_id         INTEGER NOT NULL REFERENCES users(id),
        track_id        INTEGER NOT NULL REFERENCES tracks(id),
        first_timestamp INTEGER,
        PRIMARY KEY (user_id, track_id)
    );

    CREATE TABLE user_first_label_listen (
        user_id         INTEGER NOT NULL REFERENCES users(id),
        label           TEXT    NOT NULL,
        first_timestamp INTEGER,
        PRIMARY KEY (user_id, label)
    );

    -- Caché de estadísticas de grupo (pre-computadas por html_grupo.py)
    CREATE TABLE group_stats (
        stat_type      TEXT    NOT NULL,
        stat_key       TEXT    NOT NULL,
        from_year      INTEGER,
        to_year        INTEGER,
        user_count     INTEGER,
        total_scrobbles INTEGER,
        shared_by_users TEXT,
        data_json      TEXT,
        last_updated   INTEGER,
        PRIMARY KEY (stat_type, stat_key, from_year, to_year)
    );
    """)
    conn.commit()


def _get_or_create_genre(dst: sqlite3.Connection,
                          genre_cache: dict, name: str, source: str) -> int:
    key = name.lower().strip()
    if not key:
        return None
    if key not in genre_cache:
        dst.execute(
            "INSERT OR IGNORE INTO genres (name, source, last_updated) VALUES (?,?,?)",
            (key, source, int(time.time()))
        )
        row = dst.execute("SELECT id FROM genres WHERE name=?", (key,)).fetchone()
        genre_cache[key] = row[0]
    return genre_cache[key]


def _migrate_genres_json(src_col: str, album_id: int, dst: sqlite3.Connection,
                          genre_cache: dict, source: str):
    """Parsea un JSON array de géneros y los inserta en genres/album_genres."""
    if not src_col:
        return
    try:
        names = json.loads(src_col)
        if not isinstance(names, list):
            return
        for name in names:
            if not name or not isinstance(name, str):
                continue
            gid = _get_or_create_genre(dst, genre_cache, name, source)
            if gid:
                dst.execute(
                    "INSERT OR IGNORE INTO album_genres (album_id, genre_id) VALUES (?,?)",
                    (album_id, gid)
                )
    except (json.JSONDecodeError, TypeError):
        pass


def _migrate_artist_genres_json(src_col: str, artist_id: int, dst: sqlite3.Connection,
                                  genre_cache: dict, source: str):
    if not src_col:
        return
    try:
        names = json.loads(src_col)
        if not isinstance(names, list):
            return
        for name in names:
            if not name or not isinstance(name, str):
                continue
            gid = _get_or_create_genre(dst, genre_cache, name, source)
            if gid:
                dst.execute(
                    "INSERT OR IGNORE INTO artist_genres (artist_id, genre_id) VALUES (?,?)",
                    (artist_id, gid)
                )
    except (json.JSONDecodeError, TypeError):
        pass


def _batch(iterable, size=5000):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def migrate_lastfm(src_path: Path, dst_path: Path):
    print(f"\n{'='*60}")
    print(f"  lastfm:  {src_path.name}  →  {dst_path.name}")
    print(f"{'='*60}")

    if dst_path.exists():
        dst_path.unlink()
        print(f"  (borrado {dst_path.name} previo)")

    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(dst_path))
    dst.execute("PRAGMA synchronous = NORMAL")

    create_lastfm_schema(dst)

    genre_cache: dict = {}   # name_lower → id en dst

    # ── Users ─────────────────────────────────────────────────────────────────
    rows = src.execute("SELECT id, username, created_at FROM users").fetchall()
    print(f"  users: {len(rows)}")
    for r in rows:
        dst.execute(
            "INSERT INTO users (id, username, created_at) VALUES (?,?,?)",
            (r["id"], r["username"], r["created_at"])
        )
    dst.commit()

    # ── Artists ───────────────────────────────────────────────────────────────
    # La tabla origen puede tener 'url' o 'lastfm_url' según la versión
    src_artist_cols = {d[0] for d in src.execute("SELECT * FROM artists LIMIT 0").description}
    url_col = "lastfm_url" if "lastfm_url" in src_artist_cols else "url"

    rows = src.execute(f"""
        SELECT id, name, mbid, listeners, playcount,
               {url_col} AS lastfm_url, image_url AS img_url,
               genres_lastfm, genres_musicbrainz,
               country, begin_date, end_date, created_at, last_updated
        FROM artists
    """).fetchall()
    print(f"  artists: {len(rows):,}")
    for r in rows:
        dst.execute("""
            INSERT INTO artists (
                id, name, mbid, listeners, playcount, lastfm_url, img_url,
                country, begin_date, end_date, created_at, last_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (r["id"], r["name"], r["mbid"], r["listeners"], r["playcount"],
              r["lastfm_url"], r["img_url"],
              r["country"], r["begin_date"], r["end_date"],
              r["created_at"], r["last_updated"]))

        _migrate_artist_genres_json(r["genres_lastfm"],     r["id"], dst, genre_cache, "lastfm")
        _migrate_artist_genres_json(r["genres_musicbrainz"], r["id"], dst, genre_cache, "musicbrainz")
    dst.commit()
    print(f"  artist_genres: {dst.execute('SELECT COUNT(*) FROM artist_genres').fetchone()[0]:,}")

    # ── Albums ────────────────────────────────────────────────────────────────
    src_album_cols = {d[0] for d in src.execute("SELECT * FROM albums LIMIT 0").description}
    year_col = "year" if "year" in src_album_cols else "release_year"

    rows = src.execute(f"""
        SELECT id, name, artist_id, mbid,
               {year_col} AS year, release_date, release_group_mbid,
               album_type, status, country, barcode, total_tracks, label,
               genres_lastfm, genres_musicbrainz, genres_discogs,
               created_at, last_updated
        FROM albums
    """).fetchall()
    print(f"  albums: {len(rows):,}")
    for r in rows:
        dst.execute("""
            INSERT INTO albums (
                id, name, artist_id, mbid,
                year, release_date, release_group_mbid,
                album_type, status, country, barcode, total_tracks, label,
                created_at, last_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (r["id"], r["name"], r["artist_id"], r["mbid"],
              r["year"], r["release_date"], r["release_group_mbid"],
              r["album_type"], r["status"], r["country"], r["barcode"],
              r["total_tracks"], r["label"],
              r["created_at"], r["last_updated"]))

        _migrate_genres_json(r["genres_lastfm"],     r["id"], dst, genre_cache, "lastfm")
        _migrate_genres_json(r["genres_musicbrainz"], r["id"], dst, genre_cache, "musicbrainz")
        _migrate_genres_json(r["genres_discogs"],     r["id"], dst, genre_cache, "discogs")

        # album_metadata vacío: se rellenará con enrichment futuro
        dst.execute(
            "INSERT INTO album_metadata (album_id) VALUES (?)", (r["id"],)
        )
    dst.commit()
    print(f"  genres:       {dst.execute('SELECT COUNT(*) FROM genres').fetchone()[0]:,}")
    print(f"  album_genres: {dst.execute('SELECT COUNT(*) FROM album_genres').fetchone()[0]:,}")

    # ── Tracks ────────────────────────────────────────────────────────────────
    total_tracks = src.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    print(f"  tracks: {total_tracks:,}  (en lotes de 5.000)")
    migrated = 0
    for batch in _batch(src.execute(
        "SELECT id, name, artist_id, album_id, mbid, "
        "duration_ms, track_number, isrc, created_at, last_updated "
        "FROM tracks"
    ), 5000):
        dst.executemany("""
            INSERT OR IGNORE INTO tracks (
                id, name, artist_id, album_id, mbid,
                duration_ms, track_number, isrc, created_at, last_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """, [(r["id"], r["name"], r["artist_id"], r["album_id"], r["mbid"],
               r["duration_ms"], r["track_number"], r["isrc"],
               r["created_at"], r["last_updated"]) for r in batch])
        migrated += len(batch)
        print(f"    tracks: {migrated:,}/{total_tracks:,}", end="\r")
    dst.commit()
    print()

    # ── Scrobbles (tablas por usuario) ────────────────────────────────────────
    # Obtener mapa user_id → username del origen
    user_map = {r["id"]: r["username"]
                for r in src.execute("SELECT id, username FROM users").fetchall()}

    def _ensure_scrobble_table(username: str) -> str:
        tbl = _user_table(username)
        dst.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl} (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_id INTEGER NOT NULL REFERENCES artists(id),
                track_id  INTEGER NOT NULL REFERENCES tracks(id),
                album_id  INTEGER          REFERENCES albums(id),
                timestamp INTEGER NOT NULL,
                UNIQUE (timestamp, artist_id, track_id)
            )
        """)
        dst.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_ts     ON {tbl}(timestamp)")
        dst.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_artist ON {tbl}(artist_id)")
        dst.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_album  ON {tbl}(album_id)")
        return tbl

    # Crear tabla para cada usuario conocido
    user_tables = {}
    for uid, username in user_map.items():
        user_tables[uid] = _ensure_scrobble_table(username)
    dst.commit()
    print(f"  tablas scrobbles creadas: {len(user_tables)}")

    total_sc = src.execute("SELECT COUNT(*) FROM scrobbles").fetchone()[0]
    print(f"  scrobbles: {total_sc:,}  (en lotes de 10.000, separadas por usuario)")
    migrated = 0
    for batch in _batch(src.execute(
        "SELECT user_id, artist_id, track_id, album_id, timestamp FROM scrobbles"
    ), 10000):
        # Agrupar por usuario dentro del lote
        by_user: dict = {}
        for r in batch:
            uid = r["user_id"]
            by_user.setdefault(uid, []).append(r)
        for uid, rows in by_user.items():
            tbl = user_tables.get(uid)
            if not tbl:
                continue
            dst.executemany(
                f"INSERT OR IGNORE INTO {tbl} "
                f"(artist_id, track_id, album_id, timestamp) VALUES (?,?,?,?)",
                [(r["artist_id"], r["track_id"], r["album_id"], r["timestamp"])
                 for r in rows]
            )
        migrated += len(batch)
        print(f"    scrobbles: {migrated:,}/{total_sc:,}", end="\r")
    dst.commit()
    print()

    # ── user_first_* ──────────────────────────────────────────────────────────
    for tbl, fk in [
        ("user_first_artist_listen", "artist_id"),
        ("user_first_album_listen",  "album_id"),
        ("user_first_track_listen",  "track_id"),
        ("user_first_label_listen",  "label"),
    ]:
        # Comprobamos que la tabla existe en origen
        exists = src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not exists:
            print(f"  {tbl}: no existe en origen, saltando")
            continue
        rows = src.execute(f"SELECT * FROM {tbl}").fetchall()
        cols_ = [d[0] for d in src.execute(f"SELECT * FROM {tbl} LIMIT 0").description]
        for r in rows:
            d = dict(zip(cols_, r))
            dst.execute(
                f"INSERT OR IGNORE INTO {tbl} (user_id, {fk}, first_timestamp) "
                f"VALUES (?,?,?)",
                (d["user_id"], d[fk], d.get("first_timestamp"))
            )
        dst.commit()
        count = dst.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl}: {count:,}")

    src.close()
    dst.execute("PRAGMA optimize")
    dst.close()
    size = dst_path.stat().st_size / 1024 / 1024
    print(f"\n  ✅ {dst_path.name}  ({size:.1f} MB)")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Migra las DBs musicales al schema v2 optimizado"
    )
    parser.add_argument("--all",       action="store_true", help="Migrar ambas bases")
    parser.add_argument("--must-hear", action="store_true", help="Migrar must_hear_rym.db")
    parser.add_argument("--lastfm",    action="store_true", help="Migrar lastfm_normalized.db")
    parser.add_argument(
        "--db-dir", default=None,
        help="Directorio con las DBs (por defecto: el directorio de este script)"
    )
    args = parser.parse_args()

    if not any([args.all, args.must_hear, args.lastfm]):
        parser.print_help()
        return

    db_dir = Path(args.db_dir) if args.db_dir else Path(__file__).parent

    if args.all or args.must_hear:
        src = db_dir / "must_hear_rym.db"
        dst = db_dir / "must_hear_rym_new.db"
        if not src.exists():
            print(f"❌ No encontrado: {src}")
        else:
            migrate_must_hear(src, dst)

    if args.all or args.lastfm:
        src = db_dir / "lastfm_normalized.db"
        dst = db_dir / "lastfm_cache_rym_new_normalized.db"
        if not src.exists():
            print(f"❌ No encontrado: {src}")
        else:
            migrate_lastfm(src, dst)


if __name__ == "__main__":
    main()

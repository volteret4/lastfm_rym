#!/usr/bin/env python3
"""
NormalizedDB — Lector de lastfm_cache_rym_new_normalized.db
============================================================
Reside en db/db_reader.py. Importar desde cualquier módulo:
    from db.db_reader import NormalizedDB, is_normalized_db

La clase NormalizedDB expone los MISMOS nombres de método que las
antiguas clases Database / UserStatsDatabase / GroupStatsDatabase
para minimizar los cambios en el resto del código.
"""

import re
import sqlite3
import json
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Optional, Tuple

_DEFAULT_DB = "db/lastfm_cache_rym_new_normalized.db"


# ── Helpers ────────────────────────────────────────────────────────────────

def _user_table(username: str) -> str:
    """Nombre de la tabla de scrobbles para un usuario (mismo criterio que update_database.py)."""
    safe = re.sub(r'[^a-z0-9]', '_', username.lower()).strip('_')
    return f"scrobbles_{safe}"


def is_normalized_db(conn: sqlite3.Connection) -> bool:
    """True si la conexión apunta al schema normalizado (tiene tabla 'artists', no 'scrobbles' plana)."""
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    return 'artists' in tables and 'scrobbles' not in tables


# ══════════════════════════════════════════════════════════════════════════════
# NormalizedDB
# ══════════════════════════════════════════════════════════════════════════════

class NormalizedDB:
    """
    Lector del schema normalizado v2.

    Implementa los mismos métodos públicos que:
      - tools/temp/temp_database.Database
      - tools/users/user_stats_database.UserStatsDatabase (y Extended)
      - tools/group/group_stats_database.GroupStatsDatabase  (subset)

    para que los módulos de análisis (*_analyzer.py) puedan usarlo sin cambios.
    """

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        # cache para evitar N queries lookup por username
        self._user_id_cache: Dict[str, Optional[int]] = {}
        # cache de géneros de artistas (nombre → lista)
        self._artist_genres_cache: Optional[Dict[str, List[str]]] = None

    # ── Internos ────────────────────────────────────────────────────────────

    def _uid(self, username: str) -> Optional[int]:
        if username not in self._user_id_cache:
            row = self.conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            self._user_id_cache[username] = row["id"] if row else None
        return self._user_id_cache[username]

    def _scrobble_tables(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'scrobbles_%'"
        ).fetchall()
        return [r["name"] for r in rows]

    def _year_ts(self, year: int) -> Tuple[int, int]:
        return (int(datetime(year, 1, 1).timestamp()),
                int(datetime(year + 1, 1, 1).timestamp()) - 1)

    # ── Usuarios ────────────────────────────────────────────────────────────

    def get_users(self) -> List[str]:
        return [r["username"] for r in self.conn.execute(
            "SELECT username FROM users ORDER BY username"
        ).fetchall()]

    # ── Scrobbles ────────────────────────────────────────────────────────────
    # Retorna lista de dicts con claves: user, artist, track, album, timestamp
    # (mismo formato que el schema antiguo para compatibilidad con los analyzers)

    def get_scrobbles(
        self, user: str, from_timestamp: int = 0, to_timestamp: Optional[int] = None
    ) -> List[Dict]:
        """Scrobbles de un usuario en rango de tiempo. Misma firma que Database.get_scrobbles."""
        tbl = _user_table(user)
        # Comprobación rápida de existencia
        exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not exists:
            return []

        conds = []
        params: List = []
        if from_timestamp:
            conds.append("s.timestamp >= ?")
            params.append(from_timestamp)
        if to_timestamp is not None:
            conds.append("s.timestamp <= ?")
            params.append(to_timestamp)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""

        rows = self.conn.execute(f"""
            SELECT ar.name  AS artist,
                   COALESCE(tr.name, '') AS track,
                   COALESCE(al.name, '') AS album,
                   s.timestamp
            FROM {tbl} s
            JOIN artists ar ON ar.id = s.artist_id
            LEFT JOIN tracks tr ON tr.id = s.track_id
            LEFT JOIN albums  al ON al.id = s.album_id
            {where}
            ORDER BY s.timestamp DESC
        """, params).fetchall()
        return [dict(r) | {"user": user} for r in rows]

    # ── Géneros ──────────────────────────────────────────────────────────────

    def get_artist_genres(self, artist: str) -> List[str]:
        """Lista de géneros de un artista (por nombre). Compatible con Database.get_artist_genres."""
        rows = self.conn.execute("""
            SELECT g.name FROM genres g
            JOIN artist_genres ag ON ag.genre_id = g.id
            JOIN artists ar ON ar.id = ag.artist_id
            WHERE ar.name = ?
            ORDER BY g.name
        """, (artist,)).fetchall()
        return [r["name"] for r in rows]

    def get_artist_genres_map(self) -> Dict[str, List[str]]:
        """
        {artist_name_lower: [genre, ...]} para TODOS los artistas de una vez.
        Para html_personales.py (carga bulk eficiente).
        """
        if self._artist_genres_cache is not None:
            return self._artist_genres_cache
        rows = self.conn.execute("""
            SELECT ar.name AS artist, g.name AS genre
            FROM artist_genres ag
            JOIN artists ar ON ar.id = ag.artist_id
            JOIN genres g   ON g.id  = ag.genre_id
        """).fetchall()
        result: Dict[str, List[str]] = {}
        for r in rows:
            key = r["artist"].strip().lower()
            title = r["genre"].title()
            lst = result.setdefault(key, [])
            if title not in lst:
                lst.append(title)
        self._artist_genres_cache = result
        return result

    def get_album_genres_map(self) -> Dict[Tuple[str, str], List[str]]:
        """{(artist_lower, album_lower): [genre, ...]} para todos los álbumes."""
        rows = self.conn.execute("""
            SELECT ar.name AS artist, al.name AS album, g.name AS genre
            FROM album_genres ag
            JOIN albums  al ON al.id = ag.album_id
            JOIN artists ar ON ar.id = al.artist_id
            JOIN genres  g  ON g.id  = ag.genre_id
        """).fetchall()
        result: Dict[Tuple[str, str], List[str]] = {}
        for r in rows:
            key = (r["artist"].strip().lower(), r["album"].strip().lower())
            title = r["genre"].title()
            lst = result.setdefault(key, [])
            if title not in lst:
                lst.append(title)
        return result

    def get_top_genres_for_user(
        self, user: str, from_ts: int, to_ts: int,
        limit: int = 40, entity: str = "artist"
    ) -> List[Dict]:
        """
        [{genre, plays}] para un usuario en un rango de tiempo.
        entity='artist' → artist_genres; entity='album' → album_genres.
        """
        tbl = _user_table(user)
        if entity == "artist":
            sql = f"""
                SELECT g.name AS genre, COUNT(*) AS plays
                FROM {tbl} s
                JOIN artist_genres ag ON ag.artist_id = s.artist_id
                JOIN genres g ON g.id = ag.genre_id
                WHERE s.timestamp BETWEEN ? AND ?
                GROUP BY g.id ORDER BY plays DESC LIMIT ?
            """
        else:
            sql = f"""
                SELECT g.name AS genre, COUNT(*) AS plays
                FROM {tbl} s
                JOIN album_genres ag ON ag.album_id = s.album_id
                JOIN genres g ON g.id = ag.genre_id
                WHERE s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                GROUP BY g.id ORDER BY plays DESC LIMIT ?
            """
        rows = self.conn.execute(sql, (from_ts, to_ts, limit)).fetchall()
        return [{"genre": r["genre"], "plays": r["plays"]} for r in rows]

    # ── Artistas ─────────────────────────────────────────────────────────────

    def get_artist_details_map(self) -> Dict[str, Dict]:
        """{artist_lower: {country, type, begin, end, image, bio}}. Para html_personales.py."""
        rows = self.conn.execute(
            "SELECT name, country, artist_type, begin_date, end_date, img_url, bio FROM artists"
        ).fetchall()
        result = {}
        for r in rows:
            result[r["name"].strip().lower()] = {
                "country": r["country"],
                "type":    r["artist_type"],
                "begin":   r["begin_date"],
                "end":     r["end_date"],
                "image":   r["img_url"],
                "bio":     (r["bio"] or "")[:300].strip() if r["bio"] else None,
            }
        return result

    def get_top_artists(
        self, user: str, from_ts: int, to_ts: int, limit: Optional[int] = None
    ) -> List[Tuple[str, int]]:
        """[(artist_name, plays)] ordenado por plays DESC."""
        tbl = _user_table(user)
        lim = f"LIMIT {limit}" if limit else ""
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, COUNT(*) AS plays
            FROM {tbl} s
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.timestamp BETWEEN ? AND ?
            GROUP BY s.artist_id ORDER BY plays DESC {lim}
        """, (from_ts, to_ts)).fetchall()
        return [(r["artist"], r["plays"]) for r in rows]

    # ── Álbumes ──────────────────────────────────────────────────────────────

    def get_album_release_year(self, artist: str, album: str) -> Optional[int]:
        """Año de publicación de un álbum. Compatible con Database.get_album_release_year."""
        row = self.conn.execute("""
            SELECT al.year FROM albums al
            JOIN artists ar ON ar.id = al.artist_id
            WHERE ar.name = ? AND al.name = ?
        """, (artist, album)).fetchone()
        return row["year"] if row and row["year"] else None

    def get_album_release_years_map(self) -> Dict[Tuple[str, str], int]:
        """{(artist_lower, album_lower): year}. Para html_personales.py."""
        rows = self.conn.execute("""
            SELECT ar.name AS artist, al.name AS album, al.year
            FROM albums al
            JOIN artists ar ON ar.id = al.artist_id
            WHERE al.year IS NOT NULL
        """).fetchall()
        return {
            (r["artist"].strip().lower(), r["album"].strip().lower()): r["year"]
            for r in rows
        }

    def get_album_label(self, artist: str, album: str) -> Optional[str]:
        """Sello discográfico de un álbum. Compatible con Database.get_album_label."""
        row = self.conn.execute("""
            SELECT al.label FROM albums al
            JOIN artists ar ON ar.id = al.artist_id
            WHERE ar.name = ? AND al.name = ?
        """, (artist, album)).fetchone()
        return row["label"] if row and row["label"] else None

    def get_top_albums(
        self, user: str, from_ts: int, to_ts: int, limit: Optional[int] = None
    ) -> List[Tuple[str, int]]:
        """[("Artist - Album", plays)] ordenado por plays DESC."""
        tbl = _user_table(user)
        lim = f"LIMIT {limit}" if limit else ""
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, al.name AS album, COUNT(*) AS plays
            FROM {tbl} s
            JOIN albums  al ON al.id = s.album_id
            JOIN artists ar ON ar.id = al.artist_id
            WHERE s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.album_id ORDER BY plays DESC {lim}
        """, (from_ts, to_ts)).fetchall()
        return [(f"{r['artist']} - {r['album']}", r["plays"]) for r in rows]

    # ── Tracks ───────────────────────────────────────────────────────────────

    def get_top_tracks(
        self, user: str, from_ts: int, to_ts: int, limit: Optional[int] = None
    ) -> List[Tuple[str, int]]:
        """[("Artist - Track", plays)] ordenado por plays DESC."""
        tbl = _user_table(user)
        lim = f"LIMIT {limit}" if limit else ""
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, tr.name AS track, COUNT(*) AS plays
            FROM {tbl} s
            JOIN tracks  tr ON tr.id = s.track_id
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.track_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.track_id ORDER BY plays DESC {lim}
        """, (from_ts, to_ts)).fetchall()
        return [(f"{r['artist']} - {r['track']}", r["plays"]) for r in rows]

    # ── Sellos ───────────────────────────────────────────────────────────────

    def get_top_labels(
        self, user: str, from_ts: int, to_ts: int, limit: Optional[int] = None
    ) -> List[Tuple[str, int]]:
        """[(label, plays)] ordenado por plays DESC."""
        tbl = _user_table(user)
        lim = f"LIMIT {limit}" if limit else ""
        rows = self.conn.execute(f"""
            SELECT al.label, COUNT(*) AS plays
            FROM {tbl} s
            JOIN albums al ON al.id = s.album_id
            WHERE s.album_id IS NOT NULL
              AND al.label IS NOT NULL AND al.label != ''
              AND s.timestamp BETWEEN ? AND ?
            GROUP BY al.label ORDER BY plays DESC {lim}
        """, (from_ts, to_ts)).fetchall()
        return [(r["label"], r["plays"]) for r in rows]

    # ── Primeras escuchas ────────────────────────────────────────────────────

    def get_first_scrobble_date(
        self, user: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        track: Optional[str] = None,
    ) -> Optional[int]:
        """
        Primer scrobble de un usuario para un elemento.
        Compatible con Database.get_first_scrobble_date.
        Usa user_first_* si disponibles, sino MIN(timestamp).
        """
        uid = self._uid(user)
        tbl = _user_table(user)

        if track and artist:
            if uid is not None:
                row = self.conn.execute("""
                    SELECT uft.first_timestamp
                    FROM user_first_track_listen uft
                    JOIN tracks  tr ON tr.id = uft.track_id
                    JOIN artists ar ON ar.id = tr.artist_id
                    WHERE uft.user_id = ? AND tr.name = ? AND ar.name = ?
                """, (uid, track, artist)).fetchone()
                if row:
                    return row["first_timestamp"]
            row = self.conn.execute(f"""
                SELECT MIN(s.timestamp) FROM {tbl} s
                JOIN tracks  tr ON tr.id = s.track_id
                JOIN artists ar ON ar.id = s.artist_id
                WHERE tr.name = ? AND ar.name = ?
            """, (track, artist)).fetchone()
            return row[0] if row else None

        if album and artist:
            if uid is not None:
                row = self.conn.execute("""
                    SELECT ufa.first_timestamp
                    FROM user_first_album_listen ufa
                    JOIN albums  al ON al.id = ufa.album_id
                    JOIN artists ar ON ar.id = al.artist_id
                    WHERE ufa.user_id = ? AND al.name = ? AND ar.name = ?
                """, (uid, album, artist)).fetchone()
                if row:
                    return row["first_timestamp"]
            row = self.conn.execute(f"""
                SELECT MIN(s.timestamp) FROM {tbl} s
                JOIN albums  al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE al.name = ? AND ar.name = ?
            """, (album, artist)).fetchone()
            return row[0] if row else None

        if artist:
            if uid is not None:
                row = self.conn.execute("""
                    SELECT ufa.first_timestamp
                    FROM user_first_artist_listen ufa
                    JOIN artists ar ON ar.id = ufa.artist_id
                    WHERE ufa.user_id = ? AND ar.name = ?
                """, (uid, artist)).fetchone()
                if row:
                    return row["first_timestamp"]
            row = self.conn.execute(f"""
                SELECT MIN(s.timestamp) FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE ar.name = ?
            """, (artist,)).fetchone()
            return row[0] if row else None

        return None

    def get_global_first_scrobble_date(
        self,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        track: Optional[str] = None,
    ) -> Optional[int]:
        """
        Primer scrobble global (cualquier usuario) para un elemento.
        Compatible con Database.get_global_first_scrobble_date.
        """
        tbls = self._scrobble_tables()
        if not tbls:
            return None

        if track and artist:
            parts = [f"""
                SELECT MIN(s.timestamp) FROM {t} s
                JOIN tracks  tr ON tr.id = s.track_id
                JOIN artists ar ON ar.id = s.artist_id
                WHERE tr.name = ? AND ar.name = ?
            """ for t in tbls]
            params = [v for _ in tbls for v in (track, artist)]
        elif album and artist:
            parts = [f"""
                SELECT MIN(s.timestamp) FROM {t} s
                JOIN albums  al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE al.name = ? AND ar.name = ?
            """ for t in tbls]
            params = [v for _ in tbls for v in (album, artist)]
        elif artist:
            parts = [f"""
                SELECT MIN(s.timestamp) FROM {t} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE ar.name = ?
            """ for t in tbls]
            params = [artist for _ in tbls]
        else:
            return None

        union = " UNION ALL ".join(parts)
        row = self.conn.execute(
            f"SELECT MIN(ts) FROM ({union}) sub(ts)", params
        ).fetchone()
        return row[0] if row else None

    # ── Conteos / totales ────────────────────────────────────────────────────

    def get_user_total_scrobbles(
        self, user: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        track: Optional[str] = None,
    ) -> int:
        """
        Número total de scrobbles de un usuario (opcionalmente filtrado).
        Compatible con Database.get_user_total_scrobbles.
        """
        tbl = _user_table(user)
        if track and artist:
            row = self.conn.execute(f"""
                SELECT COUNT(*) FROM {tbl} s
                JOIN tracks  tr ON tr.id = s.track_id
                JOIN artists ar ON ar.id = s.artist_id
                WHERE tr.name = ? AND ar.name = ?
            """, (track, artist)).fetchone()
        elif album and artist:
            row = self.conn.execute(f"""
                SELECT COUNT(*) FROM {tbl} s
                JOIN albums  al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE al.name = ? AND ar.name = ?
            """, (album, artist)).fetchone()
        elif artist:
            row = self.conn.execute(f"""
                SELECT COUNT(*) FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE ar.name = ?
            """, (artist,)).fetchone()
        else:
            row = self.conn.execute(
                f"SELECT COUNT(*) FROM {tbl}", ()
            ).fetchone()
        return row[0] if row else 0

    def count_unique(
        self, user: str, from_ts: int, to_ts: int, entity: str
    ) -> int:
        """Artistas/álbumes/tracks/sellos/géneros únicos en un período."""
        tbl = _user_table(user)
        if entity == "artists":
            row = self.conn.execute(f"""
                SELECT COUNT(DISTINCT artist_id) FROM {tbl}
                WHERE timestamp BETWEEN ? AND ?
            """, (from_ts, to_ts)).fetchone()
        elif entity == "albums":
            row = self.conn.execute(f"""
                SELECT COUNT(DISTINCT album_id) FROM {tbl}
                WHERE album_id IS NOT NULL AND timestamp BETWEEN ? AND ?
            """, (from_ts, to_ts)).fetchone()
        elif entity == "tracks":
            row = self.conn.execute(f"""
                SELECT COUNT(DISTINCT track_id) FROM {tbl}
                WHERE track_id IS NOT NULL AND timestamp BETWEEN ? AND ?
            """, (from_ts, to_ts)).fetchone()
        elif entity == "labels":
            row = self.conn.execute(f"""
                SELECT COUNT(DISTINCT al.label) FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                WHERE s.album_id IS NOT NULL
                  AND al.label IS NOT NULL AND al.label != ''
                  AND s.timestamp BETWEEN ? AND ?
            """, (from_ts, to_ts)).fetchone()
        elif entity == "genres_artist":
            row = self.conn.execute(f"""
                SELECT COUNT(DISTINCT ag.genre_id) FROM {tbl} s
                JOIN artist_genres ag ON ag.artist_id = s.artist_id
                WHERE s.timestamp BETWEEN ? AND ?
            """, (from_ts, to_ts)).fetchone()
        elif entity == "genres_album":
            row = self.conn.execute(f"""
                SELECT COUNT(DISTINCT ag.genre_id) FROM {tbl} s
                JOIN album_genres ag ON ag.album_id = s.album_id
                WHERE s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            """, (from_ts, to_ts)).fetchone()
        else:
            return 0
        return row[0] if row else 0

    # ── Compatibilidad UserStatsDatabase ─────────────────────────────────────
    # Las siguientes firmas son compatibles con user_stats_database.py

    def _get_mbid_filter(self, mbid_only: bool, table_alias: str = 's') -> str:
        """En el nuevo schema no hay columnas *_mbid en scrobbles, así que siempre vacío."""
        return ""

    def get_user_scrobbles_by_year(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[int, int]:
        from_ts, to_ts = int(datetime(from_year, 1, 1).timestamp()), \
                         int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        tbl = _user_table(user)
        rows = self.conn.execute(f"""
            SELECT strftime('%Y', datetime(timestamp, 'unixepoch')) AS year,
                   COUNT(*) AS cnt
            FROM {tbl}
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY year ORDER BY year
        """, (from_ts, to_ts)).fetchall()
        return {int(r["year"]): r["cnt"] for r in rows}

    def get_user_top_genres_by_provider(
        self, user: str, from_year: int, to_year: int,
        provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False
    ) -> List[Tuple[str, int]]:
        """
        Géneros por proveedor. En el nuevo schema, todos los géneros están en
        artist_genres/album_genres — se ignora provider (no hay separación por fuente).
        """
        from_ts, to_ts = self._year_ts(from_year)
        to_ts = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        entity = "artist" if provider == "lastfm" else "album"
        items = self.get_top_genres_for_user(user, from_ts, to_ts, limit, entity)
        return [(i["genre"], i["plays"]) for i in items]

    def get_user_top_artists(
        self, user: str, from_year: int, to_year: int,
        limit: Optional[int] = 15, mbid_only: bool = False
    ) -> List[Tuple[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.get_top_artists(user, from_ts, to_ts, limit)

    def get_user_top_albums(
        self, user: str, from_year: int, to_year: int,
        limit: Optional[int] = 15, mbid_only: bool = False
    ) -> List[Tuple[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.get_top_albums(user, from_ts, to_ts, limit)

    def get_user_top_tracks(
        self, user: str, from_year: int, to_year: int,
        limit: Optional[int] = 15, mbid_only: bool = False
    ) -> List[Tuple[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.get_top_tracks(user, from_ts, to_ts, limit)

    def get_user_unique_count_artists(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> int:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.count_unique(user, from_ts, to_ts, "artists")

    def get_user_unique_count_albums(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> int:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.count_unique(user, from_ts, to_ts, "albums")

    def get_user_unique_count_tracks(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> int:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.count_unique(user, from_ts, to_ts, "tracks")

    def get_user_unique_count_genres_by_provider(
        self, user: str, from_year: int, to_year: int,
        provider: str = 'lastfm', mbid_only: bool = False
    ) -> int:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        entity = "genres_artist" if provider == "lastfm" else "genres_album"
        return self.count_unique(user, from_ts, to_ts, entity)

    def get_user_unique_count_labels(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> int:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.count_unique(user, from_ts, to_ts, "labels")

    def get_new_items_for_user_year(
        self, user: str, year: int, item_type: str, mbid_only: bool = False
    ) -> List[Dict]:
        """
        Elementos escuchados por primera vez en un año.
        Compatible con UserStatsDatabaseExtended.get_new_items_for_user_year.
        item_type: 'artist' | 'album' | 'track' | 'label'
        """
        tbl = _user_table(user)
        year_start = int(datetime(year, 1, 1).timestamp())
        year_end   = int(datetime(year + 1, 1, 1).timestamp()) - 1

        if item_type == "artist":
            rows = self.conn.execute(f"""
                SELECT ar.name, COUNT(*) AS plays
                FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE s.timestamp BETWEEN ? AND ?
                  AND NOT EXISTS (
                    SELECT 1 FROM {tbl} s2
                    WHERE s2.artist_id = s.artist_id AND s2.timestamp < ?
                  )
                GROUP BY s.artist_id ORDER BY plays DESC LIMIT 10
            """, (year_start, year_end, year_start)).fetchall()
            return [{"name": r["name"], "period_plays": r["plays"],
                     "first_year": year, "type": "artist"} for r in rows]

        elif item_type == "album":
            rows = self.conn.execute(f"""
                SELECT ar.name AS artist, al.name AS album, COUNT(*) AS plays
                FROM {tbl} s
                JOIN albums  al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                  AND NOT EXISTS (
                    SELECT 1 FROM {tbl} s2
                    WHERE s2.album_id = s.album_id AND s2.timestamp < ?
                  )
                GROUP BY s.album_id ORDER BY plays DESC LIMIT 10
            """, (year_start, year_end, year_start)).fetchall()
            return [{"name": f"{r['artist']} - {r['album']}",
                     "period_plays": r["plays"], "first_year": year,
                     "type": "album"} for r in rows]

        elif item_type == "track":
            rows = self.conn.execute(f"""
                SELECT ar.name AS artist, tr.name AS track, COUNT(*) AS plays
                FROM {tbl} s
                JOIN tracks  tr ON tr.id = s.track_id
                JOIN artists ar ON ar.id = s.artist_id
                WHERE s.track_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                  AND NOT EXISTS (
                    SELECT 1 FROM {tbl} s2
                    WHERE s2.track_id = s.track_id AND s2.timestamp < ?
                  )
                GROUP BY s.track_id ORDER BY plays DESC LIMIT 10
            """, (year_start, year_end, year_start)).fetchall()
            return [{"name": f"{r['artist']} - {r['track']}",
                     "period_plays": r["plays"], "first_year": year,
                     "type": "track"} for r in rows]

        elif item_type == "label":
            rows = self.conn.execute(f"""
                SELECT al.label, COUNT(*) AS plays
                FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                WHERE s.album_id IS NOT NULL
                  AND al.label IS NOT NULL AND al.label != ''
                  AND s.timestamp BETWEEN ? AND ?
                  AND NOT EXISTS (
                    SELECT 1 FROM {tbl} s2
                    JOIN albums al2 ON al2.id = s2.album_id
                    WHERE al2.label = al.label AND s2.timestamp < ?
                  )
                GROUP BY al.label ORDER BY plays DESC LIMIT 10
            """, (year_start, year_end, year_start)).fetchall()
            return [{"name": r["label"], "period_plays": r["plays"],
                     "first_year": year, "type": "label"} for r in rows]

        return []

    def get_top_artists_for_genre_by_provider(
        self, user: str, genre: str, from_year: int, to_year: int,
        provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False
    ) -> List[Dict]:
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, COUNT(*) AS total_plays
            FROM {tbl} s
            JOIN artists ar ON ar.id = s.artist_id
            JOIN artist_genres ag ON ag.artist_id = s.artist_id
            JOIN genres g ON g.id = ag.genre_id
            WHERE g.name = ? AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.artist_id ORDER BY total_plays DESC LIMIT ?
        """, (genre, from_ts, to_ts, limit)).fetchall()

        artists_data = []
        for row in rows:
            yearly_data = {}
            for year in range(from_year, to_year + 1):
                ys, ye = self._year_ts(year)
                yr = self.conn.execute(f"""
                    SELECT COUNT(*) FROM {tbl} s
                    JOIN artist_genres ag ON ag.artist_id = s.artist_id
                    JOIN genres g ON g.id = ag.genre_id
                    WHERE s.artist_id = (SELECT id FROM artists WHERE name = ?)
                      AND g.name = ? AND s.timestamp BETWEEN ? AND ?
                """, (row["artist"], genre, ys, ye)).fetchone()
                yearly_data[year] = yr[0] if yr else 0
            artists_data.append({
                "artist": row["artist"],
                "yearly_data": yearly_data,
                "total_plays": row["total_plays"],
            })
        return artists_data

    def get_user_top_album_genres_by_provider(
        self, user: str, from_year: int, to_year: int,
        provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False
    ) -> List[Tuple[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        items = self.get_top_genres_for_user(user, from_ts, to_ts, limit, entity="album")
        return [(i["genre"], i["plays"]) for i in items]

    def get_top_albums_for_genre_by_provider(
        self, user: str, genre: str, from_year: int, to_year: int,
        provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False
    ) -> List[Dict]:
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, al.name AS album, COUNT(*) AS total_plays
            FROM {tbl} s
            JOIN albums  al ON al.id = s.album_id
            JOIN artists ar ON ar.id = al.artist_id
            JOIN album_genres ag ON ag.album_id = s.album_id
            JOIN genres g ON g.id = ag.genre_id
            WHERE s.album_id IS NOT NULL AND g.name = ?
              AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.album_id ORDER BY total_plays DESC LIMIT ?
        """, (genre, from_ts, to_ts, limit)).fetchall()

        albums_data = []
        for row in rows:
            yearly_data = {}
            for year in range(from_year, to_year + 1):
                ys, ye = self._year_ts(year)
                yr = self.conn.execute(f"""
                    SELECT COUNT(*) FROM {tbl} s
                    JOIN album_genres ag ON ag.album_id = s.album_id
                    JOIN genres g ON g.id = ag.genre_id
                    WHERE s.album_id = (
                        SELECT al2.id FROM albums al2
                        JOIN artists ar2 ON ar2.id = al2.artist_id
                        WHERE ar2.name = ? AND al2.name = ?
                    ) AND g.name = ? AND s.timestamp BETWEEN ? AND ?
                """, (row["artist"], row["album"], genre, ys, ye)).fetchone()
                yearly_data[year] = yr[0] if yr else 0
            albums_data.append({
                "album": f"{row['artist']} - {row['album']}",
                "yearly_data": yearly_data,
                "total_plays": row["total_plays"],
            })
        return albums_data

    # ── Compatibilidad GroupStatsDatabase ─────────────────────────────────────

    def get_total_shared_counts(
        self, users: List[str], from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict:
        """Totales y únicos por tipo de entidad para estadísticas grupales."""
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        result = {}
        for user in users:
            tbl = _user_table(user)
            total = self.conn.execute(f"""
                SELECT COUNT(*) FROM {tbl} WHERE timestamp BETWEEN ? AND ?
            """, (from_ts, to_ts)).fetchone()[0]
            result[user] = {
                "total_scrobbles": total,
                "unique_artists":  self.count_unique(user, from_ts, to_ts, "artists"),
                "unique_albums":   self.count_unique(user, from_ts, to_ts, "albums"),
                "unique_tracks":   self.count_unique(user, from_ts, to_ts, "tracks"),
            }
        return result

    def get_user_artists_data(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> List[Dict]:
        """[{artist, plays}] para estadísticas grupales."""
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return [{"artist": a, "plays": p}
                for a, p in self.get_top_artists(user, from_ts, to_ts)]

    def get_user_albums_data(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> List[Dict]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        tbl = _user_table(user)
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, al.name AS album, COUNT(*) AS plays
            FROM {tbl} s
            JOIN albums  al ON al.id = s.album_id
            JOIN artists ar ON ar.id = al.artist_id
            WHERE s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.album_id ORDER BY plays DESC
        """, (from_ts, to_ts)).fetchall()
        return [{"artist": r["artist"], "album": r["album"], "plays": r["plays"]}
                for r in rows]

    def get_user_tracks_data(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> List[Dict]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        tbl = _user_table(user)
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, tr.name AS track, COUNT(*) AS plays
            FROM {tbl} s
            JOIN tracks  tr ON tr.id = s.track_id
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.track_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.track_id ORDER BY plays DESC
        """, (from_ts, to_ts)).fetchall()
        return [{"artist": r["artist"], "track": r["track"], "plays": r["plays"]}
                for r in rows]

    def get_user_genres_data(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> List[Dict]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.get_top_genres_for_user(user, from_ts, to_ts, entity="artist")

    def get_user_labels_data(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> List[Dict]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return [{"label": l, "plays": p}
                for l, p in self.get_top_labels(user, from_ts, to_ts)]

    def get_user_scrobbles_evolution(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[int, int]:
        return self.get_user_scrobbles_by_year(user, from_year, to_year)

    # ── Group stats cache (stub) ──────────────────────────────────────────────
    # group_stats_database usa una tabla group_stats para caché. El nuevo schema
    # también tiene esa tabla; los métodos de caché se pueden añadir si se necesitan.

    def _create_group_stats_table(self):
        """No-op: la tabla ya existe en el schema normalizado."""
        pass

    # ── Métodos adicionales de UserStatsDatabase ──────────────────────────────

    def get_user_top_labels(
        self, user: str, from_year: int, to_year: int,
        limit: int = 15, mbid_only: bool = False
    ) -> List[Tuple[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        return self.get_top_labels(user, from_ts, to_ts, limit)

    def get_top_artists_for_label(
        self, user: str, label: str, from_year: int, to_year: int,
        limit: int = 15, mbid_only: bool = False
    ) -> List[Dict]:
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, COUNT(*) AS total_plays
            FROM {tbl} s
            JOIN albums  al ON al.id = s.album_id
            JOIN artists ar ON ar.id = al.artist_id
            WHERE al.label = ? AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.artist_id ORDER BY total_plays DESC LIMIT ?
        """, (label, from_ts, to_ts, limit)).fetchall()
        artists_data = []
        for row in rows:
            yearly_data = {}
            for year in range(from_year, to_year + 1):
                ys, ye = self._year_ts(year)
                yr = self.conn.execute(f"""
                    SELECT COUNT(*) FROM {tbl} s
                    JOIN albums al ON al.id = s.album_id
                    JOIN artists ar ON ar.id = al.artist_id
                    WHERE ar.name = ? AND al.label = ? AND s.timestamp BETWEEN ? AND ?
                """, (row["artist"], label, ys, ye)).fetchone()
                yearly_data[year] = yr[0] if yr else 0
            artists_data.append({
                "artist": row["artist"],
                "yearly_data": yearly_data,
                "total_plays": row["total_plays"],
            })
        return artists_data

    def get_user_top_genres(
        self, user: str, from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> List[Tuple[str, int]]:
        """Alias de get_user_top_genres_by_provider para compatibilidad."""
        return self.get_user_top_genres_by_provider(user, from_year, to_year, 'lastfm', limit)

    def get_top_artists_for_genre(
        self, user: str, genre: str, from_year: int, to_year: int,
        limit: int = 5, mbid_only: bool = False
    ) -> List[Dict]:
        """Alias de get_top_artists_for_genre_by_provider."""
        return self.get_top_artists_for_genre_by_provider(
            user, genre, from_year, to_year, 'lastfm', limit)

    def _get_user_artist_set(self, user: str, from_ts: int, to_ts: int) -> Dict[str, int]:
        tbl = _user_table(user)
        rows = self.conn.execute(f"""
            SELECT ar.name, COUNT(*) AS plays FROM {tbl} s
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.timestamp BETWEEN ? AND ?
            GROUP BY s.artist_id
        """, (from_ts, to_ts)).fetchall()
        return {r["name"]: r["plays"] for r in rows}

    def get_common_artists_with_users(
        self, user: str, other_users: List[str],
        from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[str, Dict[str, int]]:
        """Artistas que el usuario tiene en común con cada otro usuario."""
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        user_artists = self._get_user_artist_set(user, from_ts, to_ts)
        result = {}
        for other in other_users:
            if other == user:
                continue
            other_artists = self._get_user_artist_set(other, from_ts, to_ts)
            common = {a: user_artists[a] for a in user_artists if a in other_artists}
            result[other] = common
        return result

    def _get_user_album_set(self, user: str, from_ts: int, to_ts: int) -> Dict[str, int]:
        tbl = _user_table(user)
        rows = self.conn.execute(f"""
            SELECT ar.name || ' - ' || al.name AS key, COUNT(*) AS plays
            FROM {tbl} s
            JOIN albums  al ON al.id = s.album_id
            JOIN artists ar ON ar.id = al.artist_id
            WHERE s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.album_id
        """, (from_ts, to_ts)).fetchall()
        return {r["key"]: r["plays"] for r in rows}

    def get_common_albums_with_users(
        self, user: str, other_users: List[str],
        from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[str, Dict[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        user_set = self._get_user_album_set(user, from_ts, to_ts)
        result = {}
        for other in other_users:
            if other == user:
                continue
            other_set = self._get_user_album_set(other, from_ts, to_ts)
            result[other] = {k: user_set[k] for k in user_set if k in other_set}
        return result

    def _get_user_track_set(self, user: str, from_ts: int, to_ts: int) -> Dict[str, int]:
        tbl = _user_table(user)
        rows = self.conn.execute(f"""
            SELECT ar.name || ' - ' || tr.name AS key, COUNT(*) AS plays
            FROM {tbl} s
            JOIN tracks  tr ON tr.id = s.track_id
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.track_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            GROUP BY s.track_id
        """, (from_ts, to_ts)).fetchall()
        return {r["key"]: r["plays"] for r in rows}

    def get_common_tracks_with_users(
        self, user: str, other_users: List[str],
        from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[str, Dict[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        user_set = self._get_user_track_set(user, from_ts, to_ts)
        result = {}
        for other in other_users:
            if other == user:
                continue
            other_set = self._get_user_track_set(other, from_ts, to_ts)
            result[other] = {k: user_set[k] for k in user_set if k in other_set}
        return result

    def _get_user_genre_set(self, user: str, from_ts: int, to_ts: int) -> Dict[str, int]:
        return {i["genre"]: i["plays"]
                for i in self.get_top_genres_for_user(user, from_ts, to_ts, limit=9999)}

    def get_common_genres_with_users(
        self, user: str, other_users: List[str],
        from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[str, Dict[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        user_set = self._get_user_genre_set(user, from_ts, to_ts)
        result = {}
        for other in other_users:
            if other == user:
                continue
            other_set = self._get_user_genre_set(other, from_ts, to_ts)
            result[other] = {k: user_set[k] for k in user_set if k in other_set}
        return result

    def _get_user_label_set(self, user: str, from_ts: int, to_ts: int) -> Dict[str, int]:
        return {l: p for l, p in self.get_top_labels(user, from_ts, to_ts)}

    def get_common_labels_with_users(
        self, user: str, other_users: List[str],
        from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[str, Dict[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        user_set = self._get_user_label_set(user, from_ts, to_ts)
        result = {}
        for other in other_users:
            if other == user:
                continue
            other_set = self._get_user_label_set(other, from_ts, to_ts)
            result[other] = {k: user_set[k] for k in user_set if k in other_set}
        return result

    def _get_user_year_set(self, user: str, from_ts: int, to_ts: int) -> Dict[str, int]:
        tbl = _user_table(user)
        rows = self.conn.execute(f"""
            SELECT al.year AS yr, COUNT(*) AS plays
            FROM {tbl} s
            JOIN albums al ON al.id = s.album_id
            WHERE s.album_id IS NOT NULL AND al.year IS NOT NULL
              AND s.timestamp BETWEEN ? AND ?
            GROUP BY al.year
        """, (from_ts, to_ts)).fetchall()
        return {str(r["yr"]): r["plays"] for r in rows}

    def get_common_release_years_with_users(
        self, user: str, other_users: List[str],
        from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[str, Dict[str, int]]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        user_set = self._get_user_year_set(user, from_ts, to_ts)
        result = {}
        for other in other_users:
            if other == user:
                continue
            other_set = self._get_user_year_set(other, from_ts, to_ts)
            result[other] = {k: user_set[k] for k in user_set if k in other_set}
        return result

    def get_common_album_release_years_with_users(
        self, user: str, other_users: List[str],
        from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict[str, Dict[str, int]]:
        return self.get_common_release_years_with_users(
            user, other_users, from_year, to_year, mbid_only)

    def get_top_albums_for_artists(
        self, user: str, artists: List[str],
        from_year: int, to_year: int, limit: int = 5
    ) -> Dict[str, List]:
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        result = {}
        for artist in artists:
            rows = self.conn.execute(f"""
                SELECT al.name AS album, COUNT(*) AS plays
                FROM {tbl} s
                JOIN albums  al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE ar.name = ? AND s.album_id IS NOT NULL
                  AND s.timestamp BETWEEN ? AND ?
                GROUP BY s.album_id ORDER BY plays DESC LIMIT ?
            """, (artist, from_ts, to_ts, limit)).fetchall()
            result[artist] = [{"album": r["album"], "plays": r["plays"]} for r in rows]
        return result

    def get_top_tracks_for_albums(
        self, user: str, albums: List[str],
        from_year: int, to_year: int, limit: int = 5
    ) -> Dict[str, List]:
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        result = {}
        for album_key in albums:
            # album_key might be "Artist - Album"
            if ' - ' in album_key:
                artist, album = album_key.split(' - ', 1)
            else:
                continue
            rows = self.conn.execute(f"""
                SELECT tr.name AS track, COUNT(*) AS plays
                FROM {tbl} s
                JOIN tracks  tr ON tr.id = s.track_id
                JOIN albums  al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE ar.name = ? AND al.name = ?
                  AND s.track_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                GROUP BY s.track_id ORDER BY plays DESC LIMIT ?
            """, (artist, album, from_ts, to_ts, limit)).fetchall()
            result[album_key] = [{"track": r["track"], "plays": r["plays"]} for r in rows]
        return result

    def get_top_artists_by_scrobbles(
        self, users: List[str], from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> Dict[str, List]:
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        result = {}
        for user in users:
            top = self.get_top_artists(user, from_ts, to_ts, limit)
            result[user] = [{"artist": a, "plays": p} for a, p in top]
        return result

    def get_top_artists_by_days(
        self, users: List[str], from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> Dict[str, List]:
        """Top artistas por días únicos de escucha."""
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        result = {}
        for user in users:
            tbl = _user_table(user)
            rows = self.conn.execute(f"""
                SELECT ar.name AS artist,
                       COUNT(DISTINCT date(timestamp, 'unixepoch')) AS days
                FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE s.timestamp BETWEEN ? AND ?
                GROUP BY s.artist_id ORDER BY days DESC LIMIT ?
            """, (from_ts, to_ts, limit)).fetchall()
            result[user] = [{"artist": r["artist"], "days": r["days"]} for r in rows]
        return result

    def get_top_artists_by_track_count(
        self, users: List[str], from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> Dict[str, List]:
        """Top artistas por número de canciones distintas escuchadas."""
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        result = {}
        for user in users:
            tbl = _user_table(user)
            rows = self.conn.execute(f"""
                SELECT ar.name AS artist,
                       COUNT(DISTINCT s.track_id) AS track_count
                FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE s.track_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                GROUP BY s.artist_id ORDER BY track_count DESC LIMIT ?
            """, (from_ts, to_ts, limit)).fetchall()
            result[user] = [{"artist": r["artist"], "track_count": r["track_count"]}
                            for r in rows]
        return result

    def get_top_artists_by_streaks(
        self, users: List[str], from_year: int, to_year: int,
        limit: int = 5, mbid_only: bool = False
    ) -> Dict[str, List]:
        """Simplificado: top artistas por días únicos consecutivos (aprox: días totales)."""
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        result = {}
        for user in users:
            tbl = _user_table(user)
            rows = self.conn.execute(f"""
                SELECT ar.name AS artist,
                       COUNT(DISTINCT date(s.timestamp, 'unixepoch')) AS days
                FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE s.timestamp BETWEEN ? AND ?
                GROUP BY s.artist_id ORDER BY days DESC LIMIT ?
            """, (from_ts, to_ts, limit)).fetchall()
            result[user] = [{"artist": r["artist"], "max_streak": r["days"],
                             "streak_days": r["days"]} for r in rows]
        return result

    def get_user_individual_evolution_data(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict:
        """
        Evolución temporal del usuario: géneros, artistas, álbumes, sellos, años de lanzamiento.
        Versión simplificada para el schema normalizado.
        """
        tbl = _user_table(user)
        years = list(range(from_year, to_year + 1))

        # Top géneros globales del período
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        top_genres_raw = self.get_top_genres_for_user(user, from_ts, to_ts, 10)
        top_genre_names = [i["genre"] for i in top_genres_raw]

        genres_evolution = {}
        genres_details   = {}
        for genre in top_genre_names:
            genres_evolution[genre] = {}
            genres_details[genre]   = {}
            for year in years:
                ys, ye = self._year_ts(year)
                row = self.conn.execute(f"""
                    SELECT COUNT(*) AS plays FROM {tbl} s
                    JOIN artist_genres ag ON ag.artist_id = s.artist_id
                    JOIN genres g ON g.id = ag.genre_id
                    WHERE g.name = ? AND s.timestamp BETWEEN ? AND ?
                """, (genre, ys, ye)).fetchone()
                genres_evolution[genre][year] = row["plays"] if row else 0
                # Top 5 artistas en ese género/año
                rows = self.conn.execute(f"""
                    SELECT ar.name, COUNT(*) AS plays FROM {tbl} s
                    JOIN artists ar ON ar.id = s.artist_id
                    JOIN artist_genres ag ON ag.artist_id = s.artist_id
                    JOIN genres g ON g.id = ag.genre_id
                    WHERE g.name = ? AND s.timestamp BETWEEN ? AND ?
                    GROUP BY s.artist_id ORDER BY plays DESC LIMIT 5
                """, (genre, ys, ye)).fetchall()
                genres_details[genre][year] = [{"artist": r["name"], "plays": r["plays"]}
                                               for r in rows]

        # Top artistas globales del período
        top_artists_raw = self.get_top_artists(user, from_ts, to_ts, 15)
        top_artist_names = [a for a, _ in top_artists_raw]

        artists_evolution = {}
        for artist in top_artist_names:
            artists_evolution[artist] = {}
            for year in years:
                ys, ye = self._year_ts(year)
                row = self.conn.execute(f"""
                    SELECT COUNT(*) AS plays FROM {tbl} s
                    JOIN artists ar ON ar.id = s.artist_id
                    WHERE ar.name = ? AND s.timestamp BETWEEN ? AND ?
                """, (artist, ys, ye)).fetchone()
                artists_evolution[artist][year] = row["plays"] if row else 0

        # Labels
        top_labels_raw = self.get_top_labels(user, from_ts, to_ts, 10)
        top_label_names = [l for l, _ in top_labels_raw]
        labels_evolution = {}
        for label in top_label_names:
            labels_evolution[label] = {}
            for year in years:
                ys, ye = self._year_ts(year)
                row = self.conn.execute(f"""
                    SELECT COUNT(*) AS plays FROM {tbl} s
                    JOIN albums al ON al.id = s.album_id
                    WHERE al.label = ? AND s.album_id IS NOT NULL
                      AND s.timestamp BETWEEN ? AND ?
                """, (label, ys, ye)).fetchone()
                labels_evolution[label][year] = row["plays"] if row else 0

        # Release years distribution
        release_years = {}
        for year in years:
            ys, ye = self._year_ts(year)
            rows = self.conn.execute(f"""
                SELECT al.year AS yr, COUNT(*) AS plays FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                WHERE s.album_id IS NOT NULL AND al.year IS NOT NULL
                  AND s.timestamp BETWEEN ? AND ?
                GROUP BY al.year ORDER BY plays DESC LIMIT 20
            """, (ys, ye)).fetchall()
            release_years[year] = {r["yr"]: r["plays"] for r in rows}

        return {
            "genres_evolution":  genres_evolution,
            "genres_details":    genres_details,
            "artists_evolution": artists_evolution,
            "labels_evolution":  labels_evolution,
            "release_years":     release_years,
            "years":             years,
        }

    def get_user_individual_evolution_data_cumulative(
        self, user: str, from_year: int, to_year: int, mbid_only: bool = False
    ) -> Dict:
        """
        Datos acumulativos de evolución: totales desde inicio hasta cada año.
        Versión simplificada.
        """
        tbl = _user_table(user)
        years = list(range(from_year, to_year + 1))
        all_start = 0  # desde siempre

        cumulative = {}
        for year in years:
            _, ye = self._year_ts(year)
            cumulative[year] = {
                "artists": self.conn.execute(f"""
                    SELECT COUNT(DISTINCT artist_id) FROM {tbl}
                    WHERE timestamp <= ?
                """, (ye,)).fetchone()[0],
                "albums": self.conn.execute(f"""
                    SELECT COUNT(DISTINCT album_id) FROM {tbl}
                    WHERE album_id IS NOT NULL AND timestamp <= ?
                """, (ye,)).fetchone()[0],
                "tracks": self.conn.execute(f"""
                    SELECT COUNT(DISTINCT track_id) FROM {tbl}
                    WHERE track_id IS NOT NULL AND timestamp <= ?
                """, (ye,)).fetchone()[0],
                "scrobbles": self.conn.execute(f"""
                    SELECT COUNT(*) FROM {tbl} WHERE timestamp <= ?
                """, (ye,)).fetchone()[0],
            }

        return {"cumulative": cumulative, "years": years}

    def get_user_genres_by_year(
        self, user: str, from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> Dict[int, Dict[str, int]]:
        result = {}
        for year in range(from_year, to_year + 1):
            ys, ye = self._year_ts(year)
            items = self.get_top_genres_for_user(user, ys, ye, limit)
            result[year] = {i["genre"]: i["plays"] for i in items}
        return result

    def get_one_hit_wonders_for_user(
        self, user: str, from_year: int, to_year: int,
        min_scrobbles: int = 25, limit: int = 10, mbid_only: bool = False
    ) -> List[Dict]:
        """Artistas con solo un álbum escuchado."""
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, COUNT(*) AS plays,
                   COUNT(DISTINCT s.album_id) AS album_count
            FROM {tbl} s
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.timestamp BETWEEN ? AND ?
            GROUP BY s.artist_id
            HAVING album_count = 1 AND plays >= ?
            ORDER BY plays DESC LIMIT ?
        """, (from_ts, to_ts, min_scrobbles, limit)).fetchall()
        return [{"artist": r["artist"], "plays": r["plays"]} for r in rows]

    def get_new_artists_for_user(
        self, user: str, from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> List[Dict]:
        """Artistas escuchados por primera vez en el período."""
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist, COUNT(*) AS plays
            FROM {tbl} s
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.timestamp BETWEEN ? AND ?
              AND NOT EXISTS (
                SELECT 1 FROM {tbl} s2
                WHERE s2.artist_id = s.artist_id AND s2.timestamp < ?
              )
            GROUP BY s.artist_id ORDER BY plays DESC LIMIT ?
        """, (from_ts, to_ts, from_ts, limit)).fetchall()
        return [{"artist": r["artist"], "plays": r["plays"]} for r in rows]

    def get_artist_monthly_ranks(
        self, user: str, from_year: int, to_year: int,
        min_monthly_scrobbles: int = 50, mbid_only: bool = False
    ) -> Dict[str, Dict]:
        """Rankings mensuales por artista."""
        tbl = _user_table(user)
        from_ts = int(datetime(from_year, 1, 1).timestamp())
        to_ts   = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        rows = self.conn.execute(f"""
            SELECT ar.name AS artist,
                   strftime('%Y-%m', datetime(s.timestamp, 'unixepoch')) AS month,
                   COUNT(*) AS plays
            FROM {tbl} s
            JOIN artists ar ON ar.id = s.artist_id
            WHERE s.timestamp BETWEEN ? AND ?
            GROUP BY s.artist_id, month
            HAVING plays >= ?
            ORDER BY artist, month
        """, (from_ts, to_ts, min_monthly_scrobbles)).fetchall()
        result: Dict[str, Dict] = {}
        for r in rows:
            result.setdefault(r["artist"], {})[r["month"]] = r["plays"]
        return result

    def get_fastest_rising_artists(
        self, user: str, from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> List[Dict]:
        """Artistas con mayor crecimiento de scrobbles entre primer y último año."""
        from_ts_first, to_ts_first = self._year_ts(from_year)
        from_ts_last, to_ts_last   = self._year_ts(to_year)
        first_year = {a: p for a, p in self.get_top_artists(user, from_ts_first, to_ts_first)}
        last_year  = {a: p for a, p in self.get_top_artists(user, from_ts_last, to_ts_last)}
        all_artists = set(first_year) | set(last_year)
        rising = []
        for a in all_artists:
            delta = last_year.get(a, 0) - first_year.get(a, 0)
            if delta > 0:
                rising.append({"artist": a, "delta": delta,
                               "first_year": first_year.get(a, 0),
                               "last_year":  last_year.get(a, 0)})
        rising.sort(key=lambda x: -x["delta"])
        return rising[:limit]

    def get_fastest_falling_artists(
        self, user: str, from_year: int, to_year: int,
        limit: int = 10, mbid_only: bool = False
    ) -> List[Dict]:
        from_ts_first, to_ts_first = self._year_ts(from_year)
        from_ts_last, to_ts_last   = self._year_ts(to_year)
        first_year = {a: p for a, p in self.get_top_artists(user, from_ts_first, to_ts_first)}
        last_year  = {a: p for a, p in self.get_top_artists(user, from_ts_last, to_ts_last)}
        all_artists = set(first_year) | set(last_year)
        falling = []
        for a in all_artists:
            delta = first_year.get(a, 0) - last_year.get(a, 0)
            if delta > 0 and first_year.get(a, 0) > 0:
                falling.append({"artist": a, "delta": delta,
                                "first_year": first_year.get(a, 0),
                                "last_year":  last_year.get(a, 0)})
        falling.sort(key=lambda x: -x["delta"])
        return falling[:limit]

    # ── Datos multi-usuario para group_data_analyzer.py ──────────────────────

    def get_multi_user_entity_data(
        self, users: List[str], from_ts: int, to_ts: int, entity_type: str
    ) -> List[Dict]:
        """
        Devuelve [{entity, user, plays, ...}] para TODOS los usuarios,
        para un tipo de entidad ('artist'|'album'|'track'|'genre'|'label'|'decade'|'year').
        Usado por group_data_analyzer.py cuando el schema es normalizado.
        """
        results = []
        for user in users:
            tbl = _user_table(user)
            exists = self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone()
            if not exists:
                continue

            if entity_type == 'artist':
                rows = self.conn.execute(f"""
                    SELECT ar.name AS entity, COUNT(*) AS plays
                    FROM {tbl} s JOIN artists ar ON ar.id = s.artist_id
                    WHERE s.timestamp BETWEEN ? AND ?
                    GROUP BY s.artist_id
                """, (from_ts, to_ts)).fetchall()
                for r in rows:
                    results.append({'entity': r['entity'], 'user': user,
                                    'plays': r['plays'], 'extra': {}})

            elif entity_type == 'album':
                rows = self.conn.execute(f"""
                    SELECT ar.name AS artist, al.name AS album, COUNT(*) AS plays
                    FROM {tbl} s
                    JOIN albums  al ON al.id = s.album_id
                    JOIN artists ar ON ar.id = al.artist_id
                    WHERE s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                    GROUP BY s.album_id
                """, (from_ts, to_ts)).fetchall()
                for r in rows:
                    results.append({
                        'entity': f"{r['artist']} - {r['album']}",
                        'user': user, 'plays': r['plays'],
                        'extra': {'artist': r['artist'], 'album': r['album']},
                    })

            elif entity_type == 'track':
                rows = self.conn.execute(f"""
                    SELECT ar.name AS artist, tr.name AS track, COUNT(*) AS plays
                    FROM {tbl} s
                    JOIN tracks  tr ON tr.id = s.track_id
                    JOIN artists ar ON ar.id = s.artist_id
                    WHERE s.track_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                    GROUP BY s.track_id
                """, (from_ts, to_ts)).fetchall()
                for r in rows:
                    results.append({
                        'entity': f"{r['artist']} - {r['track']}",
                        'user': user, 'plays': r['plays'],
                        'extra': {'artist': r['artist'], 'track': r['track']},
                    })

            elif entity_type == 'genre':
                rows = self.conn.execute(f"""
                    SELECT g.name AS genre, COUNT(*) AS plays
                    FROM {tbl} s
                    JOIN artist_genres ag ON ag.artist_id = s.artist_id
                    JOIN genres g ON g.id = ag.genre_id
                    WHERE s.timestamp BETWEEN ? AND ?
                    GROUP BY g.id
                """, (from_ts, to_ts)).fetchall()
                for r in rows:
                    results.append({'entity': r['genre'], 'user': user,
                                    'plays': r['plays'], 'extra': {}})

            elif entity_type == 'label':
                rows = self.conn.execute(f"""
                    SELECT al.label AS label, COUNT(*) AS plays
                    FROM {tbl} s JOIN albums al ON al.id = s.album_id
                    WHERE s.album_id IS NOT NULL
                      AND al.label IS NOT NULL AND al.label != ''
                      AND s.timestamp BETWEEN ? AND ?
                    GROUP BY al.label
                """, (from_ts, to_ts)).fetchall()
                for r in rows:
                    results.append({'entity': r['label'], 'user': user,
                                    'plays': r['plays'], 'extra': {}})

            elif entity_type in ('decade', 'year'):
                rows = self.conn.execute(f"""
                    SELECT al.year AS yr, COUNT(*) AS plays
                    FROM {tbl} s JOIN albums al ON al.id = s.album_id
                    WHERE s.album_id IS NOT NULL AND al.year IS NOT NULL
                      AND s.timestamp BETWEEN ? AND ?
                    GROUP BY al.year
                """, (from_ts, to_ts)).fetchall()
                for r in rows:
                    if entity_type == 'year':
                        results.append({'entity': str(r['yr']), 'user': user,
                                        'plays': r['plays'], 'extra': {}})
                    else:
                        decade = self._year_to_decade(r['yr'])
                        results.append({'entity': decade, 'user': user,
                                        'plays': r['plays'], 'extra': {}})
        return results

    def _year_to_decade(self, year: int) -> str:
        if year < 1950:
            return "Antes de 1950"
        elif year >= 2020:
            return "2020s+"
        return f"{(year // 10) * 10}s"

    # ── Group stats methods (GroupStatsDatabase interface) ────────────────────

    def _ts_from_years(self, from_year: int, to_year: int):
        from datetime import datetime as _dt
        return int(_dt(from_year, 1, 1).timestamp()), int(_dt(to_year + 1, 1, 1).timestamp()) - 1

    def _build_group_stats(self, rows: List[Dict], min_users: int = None,
                           exact_users: int = None, sort_by_users: bool = False,
                           limit: int = None) -> List[Dict]:
        """Aggregates multi-user entity rows into group stats dicts."""
        stats: Dict = defaultdict(lambda: {
            'users': set(), 'total_scrobbles': 0,
            'user_plays': defaultdict(int), 'extra': {}
        })
        for r in rows:
            e = r['entity']
            stats[e]['users'].add(r['user'])
            stats[e]['total_scrobbles'] += r['plays']
            stats[e]['user_plays'][r['user']] += r['plays']
            if r.get('extra'):
                stats[e]['extra'].update(r['extra'])
        result = []
        for name, s in stats.items():
            uc = len(s['users'])
            if min_users is not None and uc < min_users:
                continue
            if exact_users is not None and uc != exact_users:
                continue
            item = {
                'name': name, 'user_count': uc,
                'total_scrobbles': s['total_scrobbles'],
                'shared_users': list(s['users']),
                'user_plays': dict(s['user_plays']),
            }
            item.update(s['extra'])
            result.append(item)
        if sort_by_users:
            result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        else:
            result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit] if limit else result

    # Compat stubs used by GroupStatsDatabase
    def _create_group_stats_table(self): pass
    def _get_mbid_filter(self, mbid_only: bool, table_alias: str = 's') -> str: return ""

    # ── Top by shared users ────────────────────────────────────────────────────

    def get_top_artists_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                        limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'artist')
        return self._build_group_stats(rows, min_users=2, sort_by_users=True, limit=limit)

    def get_top_albums_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'album')
        return self._build_group_stats(rows, min_users=2, sort_by_users=True, limit=limit)

    def get_top_tracks_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'track')
        return self._build_group_stats(rows, min_users=2, sort_by_users=True, limit=limit)

    def get_top_genres_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'genre')
        return self._build_group_stats(rows, min_users=2, sort_by_users=True, limit=limit)

    def get_top_labels_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'label')
        return self._build_group_stats(rows, min_users=2, sort_by_users=True, limit=limit)

    def get_top_release_years_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                              limit: int = 15, mbid_only: bool = False,
                                              use_decades: bool = True) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'decade' if use_decades else 'year')
        return self._build_group_stats(rows, min_users=2, sort_by_users=True, limit=limit)

    def get_top_release_decades_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                                limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        return self.get_top_release_years_by_shared_users(users, from_year, to_year, limit, mbid_only, True)

    def get_top_individual_years_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                                 limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        return self.get_top_release_years_by_shared_users(users, from_year, to_year, limit, mbid_only, False)

    # ── Top by scrobbles only ──────────────────────────────────────────────────

    def get_top_artists_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                          limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'artist')
        return self._build_group_stats(rows, limit=limit)

    def get_top_albums_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                         limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'album')
        return self._build_group_stats(rows, limit=limit)

    def get_top_tracks_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                         limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'track')
        return self._build_group_stats(rows, limit=limit)

    def get_top_genres_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                         limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'genre')
        return self._build_group_stats(rows, limit=limit)

    def get_top_labels_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                         limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'label')
        return self._build_group_stats(rows, limit=limit)

    def get_top_release_years_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                                limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'decade')
        return self._build_group_stats(rows, limit=limit)

    def get_top_individual_release_years_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                                           limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'year')
        return self._build_group_stats(rows, limit=limit)

    # ── Exact users scatter ────────────────────────────────────────────────────

    def get_top_artists_by_exact_users_scatter(self, users: List[str], from_year: int, to_year: int,
                                               mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'artist')
        return self._build_group_stats(rows, exact_users=len(users))

    def get_top_albums_by_exact_users_scatter(self, users: List[str], from_year: int, to_year: int,
                                              mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'album')
        return self._build_group_stats(rows, exact_users=len(users))

    def get_top_tracks_by_exact_users_scatter(self, users: List[str], from_year: int, to_year: int,
                                              mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'track')
        return self._build_group_stats(rows, exact_users=len(users))

    def get_top_genres_by_exact_users_scatter(self, users: List[str], from_year: int, to_year: int,
                                              mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'genre')
        return self._build_group_stats(rows, exact_users=len(users))

    def get_top_labels_by_exact_users_scatter(self, users: List[str], from_year: int, to_year: int,
                                              mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'label')
        return self._build_group_stats(rows, exact_users=len(users))

    def get_top_release_decades_by_exact_users_scatter(self, users: List[str], from_year: int, to_year: int,
                                                       mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        rows = self.get_multi_user_entity_data(users, from_ts, to_ts, 'decade')
        return self._build_group_stats(rows, exact_users=len(users))

    # ── Total shared counts ────────────────────────────────────────────────────

    def get_total_shared_counts(self, users: List[str], from_year: int, to_year: int,
                                mbid_only: bool = False) -> Dict[str, int]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        n = len(users)
        results = {}
        for entity_type, key in [
            ('artist', 'shared_artists'), ('album', 'shared_albums'),
            ('track', 'shared_tracks'), ('genre', 'shared_genres'),
            ('label', 'shared_labels'), ('decade', 'shared_release_years'),
        ]:
            rows = self.get_multi_user_entity_data(users, from_ts, to_ts, entity_type)
            results[key] = len(self._build_group_stats(rows, exact_users=n))
        return results

    # ── Genre / label / period detail ──────────────────────────────────────────

    def get_top_artists_for_genre(self, genre: str, users: List[str], from_year: int, to_year: int,
                                  limit: int = 5, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        stats: Dict = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0})
        for user in users:
            tbl = _user_table(user)
            if not self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone():
                continue
            for r in self.conn.execute(f"""
                SELECT ar.name AS artist, COUNT(*) AS plays
                FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                JOIN artist_genres ag ON ag.artist_id = s.artist_id
                JOIN genres g ON g.id = ag.genre_id
                WHERE g.name = ? AND s.timestamp BETWEEN ? AND ?
                GROUP BY s.artist_id
            """, (genre, from_ts, to_ts)).fetchall():
                stats[r['artist']]['users'].add(user)
                stats[r['artist']]['total_scrobbles'] += r['plays']
        result = [
            {'name': a, 'user_count': len(s['users']), 'total_scrobbles': s['total_scrobbles'],
             'shared_users': list(s['users'])}
            for a, s in stats.items() if len(s['users']) >= 2
        ]
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_albums_for_label(self, label: str, users: List[str], from_year: int, to_year: int,
                                 limit: int = 5, mbid_only: bool = False) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        stats: Dict = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'artist': '', 'album': ''})
        for user in users:
            tbl = _user_table(user)
            if not self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone():
                continue
            for r in self.conn.execute(f"""
                SELECT ar.name AS artist, al.name AS album,
                       (ar.name || ' - ' || al.name) AS album_key, COUNT(*) AS plays
                FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE al.label = ? AND s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                GROUP BY s.album_id
            """, (label, from_ts, to_ts)).fetchall():
                k = r['album_key']
                stats[k]['users'].add(user)
                stats[k]['total_scrobbles'] += r['plays']
                stats[k]['artist'] = r['artist']
                stats[k]['album'] = r['album']
        result = [
            {'name': n, 'artist': s['artist'], 'album': s['album'],
             'user_count': len(s['users']), 'total_scrobbles': s['total_scrobbles'],
             'shared_users': list(s['users'])}
            for n, s in stats.items() if len(s['users']) >= 2
        ]
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_artists_for_period(self, period: str, users: List[str], from_year: int, to_year: int,
                                   limit: int = 5, mbid_only: bool = False,
                                   use_decades: bool = True) -> List[Dict]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        if use_decades:
            if period == "Antes de 1950":
                year_cond, params = "al.year < 1950", []
            elif period == "2020s+":
                year_cond, params = "al.year >= 2020", []
            else:
                ds = int(period.replace('s', ''))
                year_cond, params = "al.year BETWEEN ? AND ?", [ds, ds + 9]
        else:
            year_cond, params = "al.year = ?", [int(period)]
        stats: Dict = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0})
        for user in users:
            tbl = _user_table(user)
            if not self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone():
                continue
            for r in self.conn.execute(f"""
                SELECT ar.name AS artist, COUNT(*) AS plays
                FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                JOIN artists ar ON ar.id = s.artist_id
                WHERE al.year IS NOT NULL AND {year_cond}
                  AND s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
                GROUP BY s.artist_id
            """, params + [from_ts, to_ts]).fetchall():
                stats[r['artist']]['users'].add(user)
                stats[r['artist']]['total_scrobbles'] += r['plays']
        result = [
            {'name': a, 'user_count': len(s['users']), 'total_scrobbles': s['total_scrobbles'],
             'shared_users': list(s['users'])}
            for a, s in stats.items() if len(s['users']) >= 2
        ]
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    # ── User breakdown helpers ─────────────────────────────────────────────────

    def _get_user_breakdown_for_artist(self, users: List[str], artist: str,
                                       from_year: int, to_year: int,
                                       mbid_only: bool = False) -> Dict[str, int]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        result = {}
        for user in users:
            tbl = _user_table(user)
            row = self.conn.execute(f"""
                SELECT COUNT(*) AS plays FROM {tbl} s
                JOIN artists ar ON ar.id = s.artist_id
                WHERE ar.name = ? AND s.timestamp BETWEEN ? AND ?
            """, (artist, from_ts, to_ts)).fetchone()
            if row and row['plays']:
                result[user] = row['plays']
        return result

    def _get_user_breakdown_for_album(self, users: List[str], artist: str, album: str,
                                      from_year: int, to_year: int,
                                      mbid_only: bool = False) -> Dict[str, int]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        result = {}
        for user in users:
            tbl = _user_table(user)
            row = self.conn.execute(f"""
                SELECT COUNT(*) AS plays FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE ar.name = ? AND al.name = ? AND s.album_id IS NOT NULL
                  AND s.timestamp BETWEEN ? AND ?
            """, (artist, album, from_ts, to_ts)).fetchone()
            if row and row['plays']:
                result[user] = row['plays']
        return result

    def _get_user_breakdown_for_track(self, users: List[str], artist: str, track: str,
                                      from_year: int, to_year: int,
                                      mbid_only: bool = False) -> Dict[str, int]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        result = {}
        for user in users:
            tbl = _user_table(user)
            row = self.conn.execute(f"""
                SELECT COUNT(*) AS plays FROM {tbl} s
                JOIN tracks tr ON tr.id = s.track_id
                JOIN artists ar ON ar.id = s.artist_id
                WHERE ar.name = ? AND tr.name = ? AND s.track_id IS NOT NULL
                  AND s.timestamp BETWEEN ? AND ?
            """, (artist, track, from_ts, to_ts)).fetchone()
            if row and row['plays']:
                result[user] = row['plays']
        return result

    def _get_user_breakdown_for_genre(self, users: List[str], genre: str,
                                      from_year: int, to_year: int,
                                      mbid_only: bool = False) -> Dict[str, int]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        result = {}
        for user in users:
            tbl = _user_table(user)
            row = self.conn.execute(f"""
                SELECT COUNT(*) AS plays FROM {tbl} s
                JOIN artist_genres ag ON ag.artist_id = s.artist_id
                JOIN genres g ON g.id = ag.genre_id
                WHERE g.name = ? AND s.timestamp BETWEEN ? AND ?
            """, (genre, from_ts, to_ts)).fetchone()
            if row and row['plays']:
                result[user] = row['plays']
        return result

    def _get_user_breakdown_for_label(self, users: List[str], label: str,
                                      from_year: int, to_year: int,
                                      mbid_only: bool = False) -> Dict[str, int]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        result = {}
        for user in users:
            tbl = _user_table(user)
            row = self.conn.execute(f"""
                SELECT COUNT(*) AS plays FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                WHERE al.label = ? AND s.album_id IS NOT NULL
                  AND s.timestamp BETWEEN ? AND ?
            """, (label, from_ts, to_ts)).fetchone()
            if row and row['plays']:
                result[user] = row['plays']
        return result

    def _get_user_breakdown_for_release_year(self, users: List[str], period: str,
                                             from_year: int, to_year: int,
                                             mbid_only: bool = False) -> Dict[str, int]:
        from_ts, to_ts = self._ts_from_years(from_year, to_year)
        if period == "Antes de 1950":
            year_cond, params = "al.year < 1950", []
        elif period == "2020s+":
            year_cond, params = "al.year >= 2020", []
        else:
            ds = int(period.replace('s', ''))
            year_cond, params = "al.year BETWEEN ? AND ?", [ds, ds + 9]
        result = {}
        for user in users:
            tbl = _user_table(user)
            row = self.conn.execute(f"""
                SELECT COUNT(*) AS plays FROM {tbl} s
                JOIN albums al ON al.id = s.album_id
                WHERE al.year IS NOT NULL AND {year_cond}
                  AND s.album_id IS NOT NULL AND s.timestamp BETWEEN ? AND ?
            """, params + [from_ts, to_ts]).fetchone()
            if row and row['plays']:
                result[user] = row['plays']
        return result

    # ── Cierre ───────────────────────────────────────────────────────────────

    def close(self):
        if self.conn:
            self.conn.close()

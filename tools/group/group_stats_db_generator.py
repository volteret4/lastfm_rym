#!/usr/bin/env python3
"""
GroupStatsDBGenerator - Genera una pequeña base de datos SQLite con estadísticas
pre-agregadas por usuario y año para consultas dinámicas en el navegador.

Reemplaza la generación de ~4000 archivos JSON por un único archivo SQLite
consultable con sql.js desde el frontend estático.
"""
import os
import sqlite3
import json
from datetime import datetime
from typing import List


class GroupStatsDBGenerator:

    def __init__(self, database, years_back: int = 5, mbid_only: bool = False):
        self.database = database
        self.years_back = years_back
        self.mbid_only = mbid_only
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def generate_stats_db(self, users: List[str], output_path: str) -> None:
        """
        Genera grupo_stats.db con plays por usuario/año para cada categoría.
        El frontend SQL computa dinámicamente cualquier combinación de usuarios.
        """
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        if os.path.exists(output_path):
            os.remove(output_path)

        print(f"      • Creando {output_path}...")
        out = sqlite3.connect(output_path)
        self._create_schema(out)

        years = list(range(self.from_year, self.to_year + 1))

        for user in users:
            print(f"        • Procesando {user}...")
            for year in years:
                self._insert_user_year(out, user, year)

        # Metadata
        out.execute("INSERT INTO metadata VALUES (?,?)", ('users', json.dumps(users)))
        out.execute("INSERT INTO metadata VALUES (?,?)", ('from_year', str(self.from_year)))
        out.execute("INSERT INTO metadata VALUES (?,?)", ('to_year', str(self.to_year)))
        out.execute("INSERT INTO metadata VALUES (?,?)",
                    ('generated_at', datetime.now().isoformat()))
        out.execute("INSERT INTO metadata VALUES (?,?)",
                    ('mbid_only', str(self.mbid_only)))

        # Indexes para búsquedas rápidas por usuario y año
        out.executescript("""
            CREATE INDEX idx_ap ON artist_plays(user, year);
            CREATE INDEX idx_alp ON album_plays(user, year);
            CREATE INDEX idx_tp ON track_plays(user, year);
            CREATE INDEX idx_gp ON genre_plays(user, year);
            CREATE INDEX idx_lp ON label_plays(user, year);
            CREATE INDEX idx_ryp ON release_year_plays(user, year);
        """)

        out.commit()
        out.close()

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"      • ✅ DB generada: {size_mb:.1f} MB (vs ~141 MB de JSONs)")

    def _insert_user_year(self, out: sqlite3.Connection, user: str, year: int) -> None:
        """Inserta todos los datos de un usuario para un año dado."""
        m = self.mbid_only

        # Artistas
        rows = self.database.get_top_artists_by_scrobbles_only([user], year, year, 500, m)
        out.executemany(
            "INSERT INTO artist_plays VALUES (?,?,?,?)",
            [(user, r['name'], year, r['total_scrobbles']) for r in rows]
        )

        # Álbumes
        rows = self.database.get_top_albums_by_scrobbles_only([user], year, year, 300, m)
        out.executemany(
            "INSERT INTO album_plays VALUES (?,?,?,?,?,?)",
            [(user, r['name'], r.get('artist', ''), r.get('album', ''), year,
              r['total_scrobbles']) for r in rows]
        )

        # Canciones
        rows = self.database.get_top_tracks_by_scrobbles_only([user], year, year, 300, m)
        out.executemany(
            "INSERT INTO track_plays VALUES (?,?,?,?,?,?)",
            [(user, r['name'], r.get('artist', ''), r.get('track', ''), year,
              r['total_scrobbles']) for r in rows]
        )

        # Géneros
        rows = self.database.get_top_genres_by_scrobbles_only([user], year, year, 100, m)
        out.executemany(
            "INSERT INTO genre_plays VALUES (?,?,?,?)",
            [(user, r['name'], year, r['total_scrobbles']) for r in rows]
        )

        # Sellos
        rows = self.database.get_top_labels_by_scrobbles_only([user], year, year, 100, m)
        out.executemany(
            "INSERT INTO label_plays VALUES (?,?,?,?)",
            [(user, r['name'], year, r['total_scrobbles']) for r in rows]
        )

        # Años de lanzamiento (individuales, el JS calcula décadas)
        rows = self.database.get_top_individual_release_years_by_scrobbles_only(
            [user], year, year, 100, m
        )
        out.executemany(
            "INSERT INTO release_year_plays VALUES (?,?,?,?)",
            [(user, r['name'], year, r['total_scrobbles']) for r in rows]
        )

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE artist_plays (
                user TEXT NOT NULL, artist TEXT NOT NULL,
                year INTEGER NOT NULL, plays INTEGER NOT NULL
            );
            CREATE TABLE album_plays (
                user TEXT NOT NULL, album_key TEXT NOT NULL,
                artist TEXT NOT NULL, album TEXT NOT NULL,
                year INTEGER NOT NULL, plays INTEGER NOT NULL
            );
            CREATE TABLE track_plays (
                user TEXT NOT NULL, track_key TEXT NOT NULL,
                artist TEXT NOT NULL, track TEXT NOT NULL,
                year INTEGER NOT NULL, plays INTEGER NOT NULL
            );
            CREATE TABLE genre_plays (
                user TEXT NOT NULL, genre TEXT NOT NULL,
                year INTEGER NOT NULL, plays INTEGER NOT NULL
            );
            CREATE TABLE label_plays (
                user TEXT NOT NULL, label TEXT NOT NULL,
                year INTEGER NOT NULL, plays INTEGER NOT NULL
            );
            CREATE TABLE release_year_plays (
                user TEXT NOT NULL, release_year TEXT NOT NULL,
                year INTEGER NOT NULL, plays INTEGER NOT NULL
            );
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
        """)

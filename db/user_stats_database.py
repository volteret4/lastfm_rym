#!/usr/bin/env python3
"""
UserStatsDatabase - Clase para manejar consultas específicas de estadísticas de usuarios
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class UserStatsDatabase:
    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_user_scrobbles_by_year(self, user: str, from_year: int, to_year: int) -> Dict[int, List[Dict]]:
        """Obtiene scrobbles del usuario agrupados por año"""
        cursor = self.conn.cursor()

        # Convertir años a timestamps
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT user, artist, track, album, timestamp,
                   strftime('%Y', datetime(timestamp, 'unixepoch')) as year
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
        ''', (user, from_timestamp, to_timestamp))

        scrobbles_by_year = defaultdict(list)
        for row in cursor.fetchall():
            year = int(row['year'])
            scrobbles_by_year[year].append(dict(row))

        return dict(scrobbles_by_year)

    def get_user_top_artists_by_year(self, user: str, from_year: int, to_year: int, limit: int = 50) -> Dict[int, List[Tuple[str, int]]]:
        """Obtiene top artistas del usuario por año"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT artist,
                   strftime('%Y', datetime(timestamp, 'unixepoch')) as year,
                   COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist, year
            ORDER BY year, plays DESC
        ''', (user, from_timestamp, to_timestamp))

        artists_by_year = defaultdict(list)
        for row in cursor.fetchall():
            year = int(row['year'])
            artists_by_year[year].append((row['artist'], row['plays']))

        # Limitar resultados
        for year in artists_by_year:
            artists_by_year[year] = artists_by_year[year][:limit]

        return dict(artists_by_year)

    def get_user_genres_by_year(self, user: str, from_year: int, to_year: int) -> Dict[int, Dict[str, int]]:
        """Obtiene géneros del usuario por año con conteo de reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Consulta compleja que une scrobbles con géneros
        cursor.execute('''
            SELECT ag.genres,
                   strftime('%Y', datetime(s.timestamp, 'unixepoch')) as year,
                   COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
            GROUP BY ag.genres, year
            ORDER BY year, plays DESC
        ''', (user, from_timestamp, to_timestamp))

        genres_by_year = defaultdict(lambda: defaultdict(int))

        for row in cursor.fetchall():
            year = int(row['year'])
            genres_json = row['genres']
            plays = row['plays']

            try:
                genres_list = json.loads(genres_json) if genres_json else []
                for genre in genres_list:
                    genres_by_year[year][genre] += plays
            except json.JSONDecodeError:
                continue

        return dict(genres_by_year)

    def get_common_artists_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene artistas comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener artistas del usuario principal
        cursor.execute('''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist
        ''', (user, from_timestamp, to_timestamp))

        user_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

        # Obtener artistas comunes con cada otro usuario
        common_artists = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT artist, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND artist IN ({})
                GROUP BY artist
            '''.format(','.join(['?'] * len(user_artists))),
            [other_user, from_timestamp, to_timestamp] + list(user_artists.keys()))

            other_user_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias
            common = {}
            for artist in user_artists:
                if artist in other_user_artists:
                    common[artist] = {
                        'user_plays': user_artists[artist],
                        'other_plays': other_user_artists[artist],
                        'total_plays': user_artists[artist] + other_user_artists[artist]
                    }

            if common:
                common_artists[other_user] = common

        return common_artists

    def get_common_albums_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene álbumes comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener álbumes del usuario principal (concatenando artista - álbum)
        cursor.execute('''
            SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ? AND album IS NOT NULL AND album != ''
            GROUP BY album_key
        ''', (user, from_timestamp, to_timestamp))

        user_albums = {row['album_key']: row['plays'] for row in cursor.fetchall()}

        # Obtener álbumes comunes con cada otro usuario
        common_albums = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND album IS NOT NULL AND album != ''
                  AND (artist || ' - ' || album) IN ({})
                GROUP BY album_key
            '''.format(','.join(['?'] * len(user_albums))),
            [other_user, from_timestamp, to_timestamp] + list(user_albums.keys()))

            other_user_albums = {row['album_key']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias
            common = {}
            for album in user_albums:
                if album in other_user_albums:
                    common[album] = {
                        'user_plays': user_albums[album],
                        'other_plays': other_user_albums[album],
                        'total_plays': user_albums[album] + other_user_albums[album]
                    }

            if common:
                common_albums[other_user] = common

        return common_albums

    def get_artist_release_years_for_user(self, user: str, from_year: int, to_year: int) -> Dict[str, int]:
        """Obtiene años de lanzamiento de álbumes escuchados por el usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT DISTINCT s.artist, s.album, ard.release_year, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.album IS NOT NULL AND s.album != ''
              AND ard.release_year IS NOT NULL
            GROUP BY s.artist, s.album, ard.release_year
            ORDER BY plays DESC
        ''', (user, from_timestamp, to_timestamp))

        release_years = {}
        for row in cursor.fetchall():
            album_key = f"{row['artist']} - {row['album']}"
            release_years[album_key] = {
                'release_year': row['release_year'],
                'plays': row['plays']
            }

        return release_years

    def get_artist_formation_years_for_user(self, user: str, from_year: int, to_year: int) -> Dict[str, int]:
        """Obtiene años de formación de artistas escuchados por el usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT s.artist, ad.begin_date, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN artist_details ad ON s.artist = ad.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ad.begin_date IS NOT NULL
            GROUP BY s.artist, ad.begin_date
            ORDER BY plays DESC
        ''', (user, from_timestamp, to_timestamp))

        formation_years = {}
        for row in cursor.fetchall():
            begin_date = row['begin_date']
            # Extraer año de la fecha (formato puede ser YYYY, YYYY-MM-DD, etc.)
            try:
                if begin_date:
                    year = int(begin_date.split('-')[0])
                    formation_years[row['artist']] = {
                        'formation_year': year,
                        'plays': row['plays']
                    }
            except (ValueError, AttributeError):
                continue

        return formation_years

    def get_user_top_genres(self, user: str, from_year: int, to_year: int, limit: int = 10) -> List[Tuple[str, int]]:
        """Obtiene los géneros más escuchados por el usuario"""
        genres_by_year = self.get_user_genres_by_year(user, from_year, to_year)

        # Sumar todos los años
        total_genres = defaultdict(int)
        for year_genres in genres_by_year.values():
            for genre, plays in year_genres.items():
                total_genres[genre] += plays

        # Ordenar y limitar
        sorted_genres = sorted(total_genres.items(), key=lambda x: x[1], reverse=True)
        return sorted_genres[:limit]

    def close(self):
        """Cerrar conexión a la base de datos"""
        self.conn.close()

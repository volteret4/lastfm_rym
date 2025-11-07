#!/usr/bin/env python3
"""
UserStatsDatabase - Versión optimizada con límites para evitar archivos HTML enormes
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

    def get_user_scrobbles_by_year(self, user: str, from_year: int, to_year: int) -> Dict[int, int]:
        """Obtiene conteo de scrobbles del usuario agrupados por año - optimizado"""
        cursor = self.conn.cursor()

        # Convertir años a timestamps
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Solo contar, no obtener todos los datos
        cursor.execute('''
            SELECT strftime('%Y', datetime(timestamp, 'unixepoch')) as year,
                   COUNT(*) as count
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY year
            ORDER BY year
        ''', (user, from_timestamp, to_timestamp))

        scrobbles_by_year = {}
        for row in cursor.fetchall():
            year = int(row['year'])
            scrobbles_by_year[year] = row['count']

        return scrobbles_by_year

    def get_user_top_artists_by_year(self, user: str, from_year: int, to_year: int, limit: int = 10) -> Dict[int, List[Tuple[str, int]]]:
        """Obtiene top artistas del usuario por año - limitado"""
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
            if len(artists_by_year[year]) < limit:
                artists_by_year[year].append((row['artist'], row['plays']))

        return dict(artists_by_year)

    def get_user_genres_by_year(self, user: str, from_year: int, to_year: int, limit: int = 10) -> Dict[int, Dict[str, int]]:
        """Obtiene géneros del usuario por año - limitado"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Solo obtener los top artistas para reducir carga
        cursor.execute('''
            SELECT DISTINCT s.artist
            FROM scrobbles s
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
            GROUP BY s.artist
            ORDER BY COUNT(*) DESC
            LIMIT 100
        ''', (user, from_timestamp, to_timestamp))

        top_artists = [row['artist'] for row in cursor.fetchall()]

        if not top_artists:
            return {}

        # Obtener géneros solo para estos artistas
        cursor.execute('''
            SELECT ag.genres,
                   strftime('%Y', datetime(s.timestamp, 'unixepoch')) as year,
                   COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.artist IN ({})
            GROUP BY ag.genres, year
            ORDER BY year, plays DESC
        '''.format(','.join(['?'] * len(top_artists))),
        [user, from_timestamp, to_timestamp] + top_artists)

        genres_by_year = defaultdict(lambda: defaultdict(int))

        for row in cursor.fetchall():
            year = int(row['year'])
            genres_json = row['genres']
            plays = row['plays']

            try:
                genres_list = json.loads(genres_json) if genres_json else []
                for genre in genres_list[:3]:  # Solo primeros 3 géneros por artista
                    genres_by_year[year][genre] += plays
            except json.JSONDecodeError:
                continue

        # Limitar géneros por año
        limited_genres_by_year = {}
        for year, genres in genres_by_year.items():
            sorted_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)
            limited_genres_by_year[year] = dict(sorted_genres[:limit])

        return limited_genres_by_year

    def get_common_artists_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, limit: int = 50) -> Dict[str, Dict[str, int]]:
        """Obtiene artistas comunes entre el usuario y otros usuarios - limitado a top 10 por usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener solo los top artistas del usuario principal
        cursor.execute('''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, limit))

        user_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

        if not user_artists:
            return {}

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

            # Calcular coincidencias - solo top 10 por usuario
            common_sorted = []
            for artist in user_artists:
                if artist in other_user_artists:
                    total_plays = user_artists[artist] + other_user_artists[artist]
                    common_sorted.append((artist, {
                        'user_plays': user_artists[artist],
                        'other_plays': other_user_artists[artist],
                        'total_plays': total_plays
                    }))

            # Ordenar por total de reproducciones y tomar solo top 10
            common_sorted.sort(key=lambda x: x[1]['total_plays'], reverse=True)
            common = dict(common_sorted[:10])

            if common:
                common_artists[other_user] = common

        return common_artists

    def get_common_albums_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, limit: int = 30) -> Dict[str, Dict[str, int]]:
        """Obtiene álbumes comunes entre el usuario y otros usuarios - limitado a top 8 por usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener solo los top álbumes del usuario principal
        cursor.execute('''
            SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND album IS NOT NULL AND album != ''
            GROUP BY album_key
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, limit))

        user_albums = {row['album_key']: row['plays'] for row in cursor.fetchall()}

        if not user_albums:
            return {}

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

            # Calcular coincidencias - solo top 8 por usuario
            common_sorted = []
            for album in user_albums:
                if album in other_user_albums:
                    total_plays = user_albums[album] + other_user_albums[album]
                    common_sorted.append((album, {
                        'user_plays': user_albums[album],
                        'other_plays': other_user_albums[album],
                        'total_plays': total_plays
                    }))

            common_sorted.sort(key=lambda x: x[1]['total_plays'], reverse=True)
            common = dict(common_sorted[:8])

            if common:
                common_albums[other_user] = common

        return common_albums

    def get_common_tracks_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, limit: int = 20) -> Dict[str, Dict[str, int]]:
        """Obtiene canciones comunes entre el usuario y otros usuarios - limitado a top 6 por usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener solo las top canciones del usuario principal
        cursor.execute('''
            SELECT (artist || ' - ' || track) as track_key, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY track_key
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, limit))

        user_tracks = {row['track_key']: row['plays'] for row in cursor.fetchall()}

        if not user_tracks:
            return {}

        common_tracks = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT (artist || ' - ' || track) as track_key, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND (artist || ' - ' || track) IN ({})
                GROUP BY track_key
            '''.format(','.join(['?'] * len(user_tracks))),
            [other_user, from_timestamp, to_timestamp] + list(user_tracks.keys()))

            other_user_tracks = {row['track_key']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias - solo top 6 por usuario
            common_sorted = []
            for track in user_tracks:
                if track in other_user_tracks:
                    total_plays = user_tracks[track] + other_user_tracks[track]
                    common_sorted.append((track, {
                        'user_plays': user_tracks[track],
                        'other_plays': other_user_tracks[track],
                        'total_plays': total_plays
                    }))

            common_sorted.sort(key=lambda x: x[1]['total_plays'], reverse=True)
            common = dict(common_sorted[:6])

            if common:
                common_tracks[other_user] = common

        return common_tracks

    def get_artist_release_years_for_user(self, user: str, from_year: int, to_year: int, limit: int = 50) -> Dict[str, int]:
        """Obtiene años de lanzamiento de álbumes escuchados por el usuario - limitado"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT s.artist, s.album, ard.release_year, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.album IS NOT NULL AND s.album != ''
              AND ard.release_year IS NOT NULL
            GROUP BY s.artist, s.album, ard.release_year
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, limit))

        release_years = {}
        for row in cursor.fetchall():
            album_key = f"{row['artist']} - {row['album']}"
            release_years[album_key] = {
                'release_year': row['release_year'],
                'plays': row['plays']
            }

        return release_years

    def get_artist_formation_years_for_user(self, user: str, from_year: int, to_year: int, limit: int = 50) -> Dict[str, int]:
        """Obtiene años de formación de artistas escuchados por el usuario - limitado"""
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
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, limit))

        formation_years = {}
        for row in cursor.fetchall():
            begin_date = row['begin_date']
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
        """Obtiene los géneros más escuchados por el usuario - limitado"""
        genres_by_year = self.get_user_genres_by_year(user, from_year, to_year, limit=20)

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

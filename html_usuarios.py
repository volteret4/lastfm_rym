#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Version Corregida
Genera estadísticas individuales de usuarios con gráficos de coincidencias y evolución
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import argparse

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass


class UserStatsDatabase:
    """Versión optimizada con límites para evitar archivos HTML enormes"""

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

        # Obtener álbumes del usuario principal
        cursor.execute('''
            SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND album IS NOT NULL AND album != ''
            GROUP BY album_key
        ''', (user, from_timestamp, to_timestamp))

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

    def get_common_tracks_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene canciones comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener canciones del usuario principal
        cursor.execute('''
            SELECT (artist || ' - ' || track) as track_key, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY track_key
        ''', (user, from_timestamp, to_timestamp))

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

            # Calcular coincidencias
            common = {}
            for track in user_tracks:
                if track in other_user_tracks:
                    common[track] = {
                        'user_plays': user_tracks[track],
                        'other_plays': other_user_tracks[track],
                        'total_plays': user_tracks[track] + other_user_tracks[track]
                    }

            if common:
                common_tracks[other_user] = common

        return common_tracks

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

    def get_user_release_years_distribution(self, user: str, from_year: int, to_year: int) -> Dict[str, Dict]:
        """Obtiene distribución de años de lanzamiento para el usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT ard.release_year, s.artist, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.album IS NOT NULL AND s.album != ''
              AND ard.release_year IS NOT NULL
            GROUP BY ard.release_year, s.artist
            ORDER BY ard.release_year, plays DESC
        ''', (user, from_timestamp, to_timestamp))

        years_data = defaultdict(lambda: {'total': 0, 'artists': []})

        for row in cursor.fetchall():
            year = row['release_year']
            decade = self._get_decade(year)
            years_data[decade]['total'] += row['plays']
            if len(years_data[decade]['artists']) < 5:  # Solo top 5 artistas por década
                years_data[decade]['artists'].append({
                    'name': row['artist'],
                    'plays': row['plays']
                })

        return dict(years_data)

    def get_user_labels_distribution(self, user: str, from_year: int, to_year: int, limit: int = 30) -> Dict[str, Dict]:
        """Obtiene distribución de sellos discográficos para el usuario - limitado a top 30"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT al.label, s.artist, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.album IS NOT NULL AND s.album != ''
              AND al.label IS NOT NULL AND al.label != ''
            GROUP BY al.label, s.artist
            ORDER BY al.label, plays DESC
        ''', (user, from_timestamp, to_timestamp))

        labels_data = defaultdict(lambda: {'total': 0, 'artists': []})

        for row in cursor.fetchall():
            label = row['label']
            labels_data[label]['total'] += row['plays']
            if len(labels_data[label]['artists']) < 5:  # Solo top 5 artistas por sello
                labels_data[label]['artists'].append({
                    'name': row['artist'],
                    'plays': row['plays']
                })

        # Limitar a top 30 sellos
        sorted_labels = sorted(labels_data.items(), key=lambda x: x[1]['total'], reverse=True)
        return dict(sorted_labels[:limit])

    def get_top_artists_by_scrobbles(self, users: List[str], from_year: int, to_year: int, limit: int = 10) -> Dict[str, List]:
        """Obtiene top artistas por scrobbles para cada usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        users_top_artists = {}

        for user in users:
            cursor.execute('''
                SELECT artist, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                GROUP BY artist
                ORDER BY plays DESC
                LIMIT ?
            ''', (user, from_timestamp, to_timestamp, limit))

            users_top_artists[user] = [{'name': row['artist'], 'plays': row['plays']} for row in cursor.fetchall()]

        return users_top_artists

    def get_top_artists_by_days(self, users: List[str], from_year: int, to_year: int, limit: int = 10) -> Dict[str, List]:
        """Obtiene top artistas por número de días diferentes en que fueron escuchados"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        users_top_artists = {}

        for user in users:
            cursor.execute('''
                SELECT artist, COUNT(DISTINCT date(datetime(timestamp, 'unixepoch'))) as days_count
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                GROUP BY artist
                ORDER BY days_count DESC
                LIMIT ?
            ''', (user, from_timestamp, to_timestamp, limit))

            users_top_artists[user] = [{'name': row['artist'], 'days': row['days_count']} for row in cursor.fetchall()]

        return users_top_artists

    def get_top_artists_by_track_count(self, users: List[str], from_year: int, to_year: int, limit: int = 10) -> Dict[str, List]:
        """Obtiene top artistas por número de canciones diferentes escuchadas"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        users_top_artists = {}

        for user in users:
            cursor.execute('''
                SELECT artist, COUNT(DISTINCT track) as track_count, COUNT(*) as total_plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                GROUP BY artist
                ORDER BY track_count DESC
                LIMIT ?
            ''', (user, from_timestamp, to_timestamp, limit))

            users_top_artists[user] = [
                {'name': row['artist'], 'track_count': row['track_count'], 'plays': row['total_plays']}
                for row in cursor.fetchall()
            ]

        return users_top_artists

    def get_top_artists_by_streaks(self, users: List[str], from_year: int, to_year: int, limit: int = 5) -> Dict[str, List]:
        """Obtiene top artistas por streaks (días consecutivos)"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        users_top_artists = {}

        for user in users:
            # Obtener todas las fechas por artista
            cursor.execute('''
                SELECT artist, date(datetime(timestamp, 'unixepoch')) as play_date, COUNT(*) as daily_plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                GROUP BY artist, play_date
                ORDER BY artist, play_date
            ''', (user, from_timestamp, to_timestamp))

            artist_dates = defaultdict(list)
            artist_plays = defaultdict(int)

            for row in cursor.fetchall():
                artist_dates[row['artist']].append(row['play_date'])
                artist_plays[row['artist']] += row['daily_plays']

            # Calcular streaks para cada artista
            artist_streaks = {}
            for artist, dates in artist_dates.items():
                if len(dates) < 2:
                    artist_streaks[artist] = {'max_streak': 1, 'total_days': len(dates), 'plays': artist_plays[artist]}
                    continue

                # Convertir fechas a objetos datetime y ordenar
                date_objects = sorted([datetime.strptime(d, '%Y-%m-%d').date() for d in dates])

                max_streak = 1
                current_streak = 1

                for i in range(1, len(date_objects)):
                    if (date_objects[i] - date_objects[i-1]).days == 1:
                        current_streak += 1
                        max_streak = max(max_streak, current_streak)
                    else:
                        current_streak = 1

                artist_streaks[artist] = {
                    'max_streak': max_streak,
                    'total_days': len(dates),
                    'plays': artist_plays[artist]
                }

            # Ordenar por max_streak y tomar top limit
            sorted_artists = sorted(
                artist_streaks.items(),
                key=lambda x: (x[1]['max_streak'], x[1]['total_days']),
                reverse=True
            )[:limit]

            users_top_artists[user] = [
                {
                    'name': artist,
                    'max_streak': data['max_streak'],
                    'total_days': data['total_days'],
                    'plays': data['plays']
                }
                for artist, data in sorted_artists
            ]

        return users_top_artists

    def get_top_tracks_for_artist(self, users: List[str], artist: str, from_year: int, to_year: int, limit: int = 10) -> Dict[str, List]:
        """Obtiene top canciones de un artista para cada usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        users_tracks = {}

        for user in users:
            cursor.execute('''
                SELECT track, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND artist = ? AND timestamp >= ? AND timestamp <= ?
                GROUP BY track
                ORDER BY plays DESC
                LIMIT ?
            ''', (user, artist, from_timestamp, to_timestamp, limit))

            users_tracks[user] = [{'name': row['track'], 'plays': row['plays']} for row in cursor.fetchall()]

        return users_tracks

    def get_common_genres_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene géneros comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener géneros del usuario principal
        cursor.execute('''
            SELECT ag.genres, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
            GROUP BY ag.genres
        ''', (user, from_timestamp, to_timestamp))

        user_genres = defaultdict(int)
        for row in cursor.fetchall():
            genres_json = row['genres']
            try:
                genres_list = json.loads(genres_json) if genres_json else []
                for genre in genres_list[:3]:  # Solo primeros 3 géneros por artista
                    user_genres[genre] += row['plays']
            except json.JSONDecodeError:
                continue

        if not user_genres:
            return {}

        common_genres = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT ag.genres, COUNT(*) as plays
                FROM scrobbles s
                JOIN artist_genres ag ON s.artist = ag.artist
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                GROUP BY ag.genres
            ''', (other_user, from_timestamp, to_timestamp))

            other_user_genres = defaultdict(int)
            for row in cursor.fetchall():
                genres_json = row['genres']
                try:
                    genres_list = json.loads(genres_json) if genres_json else []
                    for genre in genres_list[:3]:
                        other_user_genres[genre] += row['plays']
                except json.JSONDecodeError:
                    continue

            # Calcular coincidencias
            common = {}
            for genre in user_genres:
                if genre in other_user_genres:
                    common[genre] = {
                        'user_plays': user_genres[genre],
                        'other_plays': other_user_genres[genre],
                        'total_plays': user_genres[genre] + other_user_genres[genre]
                    }

            if common:
                common_genres[other_user] = common

        return common_genres

    def get_common_labels_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene sellos comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener sellos del usuario principal
        cursor.execute('''
            SELECT al.label, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            GROUP BY al.label
        ''', (user, from_timestamp, to_timestamp))

        user_labels = {row['label']: row['plays'] for row in cursor.fetchall()}

        if not user_labels:
            return {}

        common_labels = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT al.label, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND al.label IS NOT NULL AND al.label != ''
                  AND al.label IN ({})
                GROUP BY al.label
            '''.format(','.join(['?'] * len(user_labels))),
            [other_user, from_timestamp, to_timestamp] + list(user_labels.keys()))

            other_user_labels = {row['label']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias
            common = {}
            for label in user_labels:
                if label in other_user_labels:
                    common[label] = {
                        'user_plays': user_labels[label],
                        'other_plays': other_user_labels[label],
                        'total_plays': user_labels[label] + other_user_labels[label]
                    }

            if common:
                common_labels[other_user] = common

        return common_labels

    def get_common_release_years_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene décadas de lanzamiento comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener décadas del usuario principal
        cursor.execute('''
            SELECT ard.release_year, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ard.release_year IS NOT NULL
            GROUP BY ard.release_year
        ''', (user, from_timestamp, to_timestamp))

        user_decades = defaultdict(int)
        for row in cursor.fetchall():
            decade = self._get_decade(row['release_year'])
            user_decades[decade] += row['plays']

        if not user_decades:
            return {}

        common_decades = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT ard.release_year, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND ard.release_year IS NOT NULL
                GROUP BY ard.release_year
            ''', (other_user, from_timestamp, to_timestamp))

            other_user_decades = defaultdict(int)
            for row in cursor.fetchall():
                decade = self._get_decade(row['release_year'])
                other_user_decades[decade] += row['plays']

            # Calcular coincidencias
            common = {}
            for decade in user_decades:
                if decade in other_user_decades:
                    common[decade] = {
                        'user_plays': user_decades[decade],
                        'other_plays': other_user_decades[decade],
                        'total_plays': user_decades[decade] + other_user_decades[decade]
                    }

            if common:
                common_decades[other_user] = common

        return common_decades

    def get_top_albums_for_artists(self, user: str, artists: List[str], from_year: int, to_year: int, limit: int = 5) -> Dict[str, List]:
        """Obtiene top álbumes para artistas específicos"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        albums_data = {}
        for artist in artists[:10]:  # Limitar artistas
            cursor.execute('''
                SELECT album, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND artist = ? AND timestamp >= ? AND timestamp <= ?
                  AND album IS NOT NULL AND album != ''
                GROUP BY album
                ORDER BY plays DESC
                LIMIT ?
            ''', (user, artist, from_timestamp, to_timestamp, limit))

            albums_data[artist] = [{'name': row['album'], 'plays': row['plays']} for row in cursor.fetchall()]

        return albums_data

    def get_top_tracks_for_albums(self, user: str, albums: List[str], from_year: int, to_year: int, limit: int = 5) -> Dict[str, List]:
        """Obtiene top canciones para álbumes específicos"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        tracks_data = {}
        for album in albums[:10]:  # Limitar álbumes
            # Separar artista y álbum
            if ' - ' in album:
                artist, album_name = album.split(' - ', 1)
                cursor.execute('''
                    SELECT track, COUNT(*) as plays
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND album = ? AND timestamp >= ? AND timestamp <= ?
                    GROUP BY track
                    ORDER BY plays DESC
                    LIMIT ?
                ''', (user, artist, album_name, from_timestamp, to_timestamp, limit))

                tracks_data[album] = [{'name': row['track'], 'plays': row['plays']} for row in cursor.fetchall()]

        return tracks_data

    def get_top_artists_for_genre(self, user: str, genre: str, from_year: int, to_year: int, limit: int = 5) -> List[Dict]:
        """Obtiene top artistas para un género específico"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT s.artist, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ag.genres LIKE ?
            GROUP BY s.artist
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, f'%"{genre}"%', limit))

        return [{'name': row['artist'], 'plays': row['plays']} for row in cursor.fetchall()]

    def get_one_hit_wonders_for_user(self, user: str, from_year: int, to_year: int, min_scrobbles: int = 25, limit: int = 10) -> List[Dict]:
        """Obtiene artistas con una sola canción y más de min_scrobbles reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT artist, COUNT(DISTINCT track) as track_count, COUNT(*) as total_plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist
            HAVING track_count = 1 AND total_plays >= ?
            ORDER BY total_plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, min_scrobbles, limit))

        return [{'name': row['artist'], 'plays': row['total_plays'], 'tracks': row['track_count']} for row in cursor.fetchall()]

    def get_new_artists_for_user(self, user: str, from_year: int, to_year: int, limit: int = 10) -> List[Dict]:
        """Obtiene artistas nuevos (sin scrobbles antes del período) con más reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener artistas del período actual
        cursor.execute('''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist
        ''', (user, from_timestamp, to_timestamp))

        current_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

        # Obtener artistas de períodos anteriores
        cursor.execute('''
            SELECT DISTINCT artist
            FROM scrobbles
            WHERE user = ? AND timestamp < ?
        ''', (user, from_timestamp))

        previous_artists = set(row['artist'] for row in cursor.fetchall())

        # Filtrar artistas nuevos
        new_artists = []
        for artist, plays in current_artists.items():
            if artist not in previous_artists:
                new_artists.append({'name': artist, 'plays': plays})

        # Ordenar por reproducciones y tomar top
        new_artists.sort(key=lambda x: x['plays'], reverse=True)
        return new_artists[:limit]

    def get_artist_monthly_ranks(self, user: str, from_year: int, to_year: int, min_monthly_scrobbles: int = 50) -> Dict[str, Dict]:
        """Obtiene rankings mensuales de artistas para calcular cambios de ranking"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT artist,
                   strftime('%Y-%m', datetime(timestamp, 'unixepoch')) as month,
                   COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist, month
            HAVING plays >= ?
            ORDER BY month, plays DESC
        ''', (user, from_timestamp, to_timestamp, min_monthly_scrobbles))

        monthly_data = defaultdict(list)
        for row in cursor.fetchall():
            monthly_data[row['month']].append({
                'artist': row['artist'],
                'plays': row['plays']
            })

        # Calcular rankings por mes
        artist_rankings = defaultdict(dict)
        for month, artists in monthly_data.items():
            for rank, artist_data in enumerate(artists, 1):
                artist_rankings[artist_data['artist']][month] = {
                    'rank': rank,
                    'plays': artist_data['plays']
                }

        return dict(artist_rankings)

    def get_fastest_rising_artists(self, user: str, from_year: int, to_year: int, limit: int = 10) -> List[Dict]:
        """Obtiene artistas que más rápido han subido en rankings mensuales"""
        rankings = self.get_artist_monthly_ranks(user, from_year, to_year)

        rising_artists = []
        for artist, monthly_ranks in rankings.items():
            months = sorted(monthly_ranks.keys())
            if len(months) < 2:
                continue

            # Calcular mayor mejora de ranking
            max_improvement = 0
            best_period = None

            for i in range(1, len(months)):
                prev_rank = monthly_ranks[months[i-1]]['rank']
                curr_rank = monthly_ranks[months[i]]['rank']

                # Mejora = rank anterior - rank actual (positivo es mejor)
                improvement = prev_rank - curr_rank
                if improvement > max_improvement:
                    max_improvement = improvement
                    best_period = f"{months[i-1]} → {months[i]}"

            if max_improvement > 0:
                rising_artists.append({
                    'name': artist,
                    'improvement': max_improvement,
                    'period': best_period,
                    'total_months': len(months)
                })

        rising_artists.sort(key=lambda x: x['improvement'], reverse=True)
        return rising_artists[:limit]

    def get_fastest_falling_artists(self, user: str, from_year: int, to_year: int, limit: int = 10) -> List[Dict]:
        """Obtiene artistas que más rápido han bajado en rankings mensuales"""
        rankings = self.get_artist_monthly_ranks(user, from_year, to_year)

        falling_artists = []
        for artist, monthly_ranks in rankings.items():
            months = sorted(monthly_ranks.keys())
            if len(months) < 2:
                continue

            # Calcular mayor caída de ranking
            max_decline = 0
            worst_period = None

            for i in range(1, len(months)):
                prev_rank = monthly_ranks[months[i-1]]['rank']
                curr_rank = monthly_ranks[months[i]]['rank']

                # Caída = rank actual - rank anterior (positivo es peor)
                decline = curr_rank - prev_rank
                if decline > max_decline:
                    max_decline = decline
                    worst_period = f"{months[i-1]} → {months[i]}"

            if max_decline > 0:
                falling_artists.append({
                    'name': artist,
                    'decline': max_decline,
                    'period': worst_period,
                    'total_months': len(months)
                })

        falling_artists.sort(key=lambda x: x['decline'], reverse=True)
        return falling_artists[:limit]

    def get_user_individual_evolution_data(self, user: str, from_year: int, to_year: int) -> Dict:
        """Obtiene todos los datos de evolución individual del usuario"""
        cursor = self.conn.cursor()

        evolution_data = {}
        years = list(range(from_year, to_year + 1))

        # 1. Top 10 géneros por año
        top_genres = self.get_user_top_genres(user, from_year, to_year, 10)
        top_genre_names = [genre for genre, _ in top_genres]

        genres_evolution = {}
        for genre in top_genre_names:
            genres_evolution[genre] = {}
            for year in years:
                cursor.execute('''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND ag.genres LIKE ?
                ''', (user, str(year), f'%"{genre}"%'))
                result = cursor.fetchone()
                genres_evolution[genre][year] = result['plays'] if result else 0

        evolution_data['genres'] = {
            'data': genres_evolution,
            'years': years,
            'names': top_genre_names
        }

        # 2. Top 10 sellos por año
        cursor.execute('''
            SELECT al.label, COUNT(*) as total_plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            GROUP BY al.label
            ORDER BY total_plays DESC
            LIMIT 10
        ''', (user, int(datetime(from_year, 1, 1).timestamp()), int(datetime(to_year + 1, 1, 1).timestamp()) - 1))

        top_labels = [row['label'] for row in cursor.fetchall()]

        labels_evolution = {}
        for label in top_labels:
            labels_evolution[label] = {}
            for year in years:
                cursor.execute('''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND al.label = ?
                ''', (user, str(year), label))
                result = cursor.fetchone()
                labels_evolution[label][year] = result['plays'] if result else 0

        evolution_data['labels'] = {
            'data': labels_evolution,
            'years': years,
            'names': top_labels
        }

        # 3. Top 10 artistas por año
        cursor.execute('''
            SELECT artist, COUNT(*) as total_plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist
            ORDER BY total_plays DESC
            LIMIT 10
        ''', (user, int(datetime(from_year, 1, 1).timestamp()), int(datetime(to_year + 1, 1, 1).timestamp()) - 1))

        top_artists = [row['artist'] for row in cursor.fetchall()]

        artists_evolution = {}
        for artist in top_artists:
            artists_evolution[artist] = {}
            for year in years:
                cursor.execute('''
                    SELECT COUNT(*) as plays
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                artists_evolution[artist][year] = result['plays'] if result else 0

        evolution_data['artists'] = {
            'data': artists_evolution,
            'years': years,
            'names': top_artists
        }

        # 4. One hit wonders, 5. Streaks, 6. Track counts, 7. New artists
        one_hit_wonders = self.get_one_hit_wonders_for_user(user, from_year, to_year, 25, 10)
        top_streak_artists = [artist['name'] for artist in self.get_top_artists_by_streaks([user], from_year, to_year, 10).get(user, [])[:10]]
        top_track_count_artists = [artist['name'] for artist in self.get_top_artists_by_track_count([user], from_year, to_year, 10).get(user, [])[:10]]
        new_artists = self.get_new_artists_for_user(user, from_year, to_year, 10)

        # Procesar evolution para estas categorías especiales
        for category, artists_list in [
            ('one_hit_wonders', [artist['name'] for artist in one_hit_wonders]),
            ('streak_artists', top_streak_artists),
            ('track_count_artists', top_track_count_artists),
            ('new_artists', [artist['name'] for artist in new_artists])
        ]:
            category_evolution = {}
            for artist in artists_list:
                category_evolution[artist] = {}
                for year in years:
                    cursor.execute('''
                        SELECT COUNT(*) as plays
                        FROM scrobbles
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    ''', (user, artist, str(year)))
                    result = cursor.fetchone()
                    category_evolution[artist][year] = result['plays'] if result else 0

            evolution_data[category] = {
                'data': category_evolution,
                'years': years,
                'names': artists_list
            }

        # 8. & 9. Rising and falling artists evolution
        rising_artists = self.get_fastest_rising_artists(user, from_year, to_year, 10)
        falling_artists = self.get_fastest_falling_artists(user, from_year, to_year, 10)

        for category, artists_list in [
            ('rising_artists', [artist['name'] for artist in rising_artists]),
            ('falling_artists', [artist['name'] for artist in falling_artists])
        ]:
            category_evolution = {}
            for artist in artists_list:
                category_evolution[artist] = {}
                for year in years:
                    cursor.execute('''
                        SELECT COUNT(*) as plays
                        FROM scrobbles
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    ''', (user, artist, str(year)))
                    result = cursor.fetchone()
                    category_evolution[artist][year] = result['plays'] if result else 0

            evolution_data[category] = {
                'data': category_evolution,
                'years': years,
                'names': artists_list
            }

        return evolution_data

    def _get_decade(self, year: int) -> str:
        """Convierte un año a etiqueta de década"""
        if year < 1950:
            return "Antes de 1950"
        elif year >= 2020:
            return "2020s+"
        else:
            decade_start = (year // 10) * 10
            return f"{decade_start}s"

    def close(self):
        """Cerrar conexión a la base de datos"""
        self.conn.close()


class UserStatsAnalyzer:
    """Clase para analizar y procesar estadísticas de usuarios"""

    def __init__(self, database, years_back: int = 5):
        self.database = database
        self.years_back = years_back
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def analyze_user(self, user: str, all_users: List[str]) -> Dict:
        """Analiza completamente un usuario y devuelve todas sus estadísticas"""
        print(f"    • Analizando scrobbles...")
        yearly_scrobbles = self._analyze_yearly_scrobbles(user)

        print(f"    • Analizando coincidencias...")
        coincidences_stats = self._analyze_coincidences(user, all_users)

        print(f"    • Analizando evolución...")
        evolution_stats = self._analyze_evolution(user, all_users)

        print(f"    • Analizando datos individuales...")
        individual_stats = self._analyze_individual(user)

        return {
            'user': user,
            'period': f"{self.from_year}-{self.to_year}",
            'yearly_scrobbles': yearly_scrobbles,
            'coincidences': coincidences_stats,
            'evolution': evolution_stats,
            'individual': individual_stats,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _analyze_individual(self, user: str) -> Dict:
        """Analiza datos individuales del usuario para la vista 'yomimeconmigo'"""
        individual_data = self.database.get_user_individual_evolution_data(
            user, self.from_year, self.to_year
        )

        return individual_data

    def _analyze_yearly_scrobbles(self, user: str) -> Dict[int, int]:
        """Analiza el número de scrobbles por año - optimizado"""
        scrobbles_by_year = self.database.get_user_scrobbles_by_year(
            user, self.from_year, self.to_year
        )

        yearly_counts = {}
        for year in range(self.from_year, self.to_year + 1):
            yearly_counts[year] = scrobbles_by_year.get(year, 0)

        return yearly_counts

    def _analyze_coincidences(self, user: str, all_users: List[str]) -> Dict:
        """Analiza coincidencias del usuario con otros usuarios"""
        other_users = [u for u in all_users if u != user]

        # Coincidencias básicas
        artist_coincidences = self.database.get_common_artists_with_users(
            user, other_users, self.from_year, self.to_year
        )

        album_coincidences = self.database.get_common_albums_with_users(
            user, other_users, self.from_year, self.to_year
        )

        track_coincidences = self.database.get_common_tracks_with_users(
            user, other_users, self.from_year, self.to_year
        )

        # Coincidencias de géneros, sellos y años (ahora como coincidencias)
        genre_coincidences = self.database.get_common_genres_with_users(
            user, other_users, self.from_year, self.to_year
        )

        label_coincidences = self.database.get_common_labels_with_users(
            user, other_users, self.from_year, self.to_year
        )

        release_year_coincidences = self.database.get_common_release_years_with_users(
            user, other_users, self.from_year, self.to_year
        )

        # Estadísticas de géneros del usuario (mantener para gráfico individual)
        user_genres = self.database.get_user_top_genres(
            user, self.from_year, self.to_year, limit=20
        )

        # Nuevos gráficos especiales
        special_charts = self._prepare_special_charts_data(user, all_users)

        # Procesar datos para gráficos circulares con popups optimizados
        charts_data = self._prepare_coincidence_charts_data(
            user, other_users, artist_coincidences, album_coincidences,
            track_coincidences, user_genres, genre_coincidences,
            label_coincidences, release_year_coincidences, special_charts
        )

        return {
            'charts': charts_data
        }

    def _prepare_special_charts_data(self, user: str, all_users: List[str]) -> Dict:
        """Prepara datos para los 4 nuevos gráficos especiales"""
        other_users = [u for u in all_users if u != user]

        # Top 10 artistas por escuchas
        top_scrobbles = self.database.get_top_artists_by_scrobbles(
            all_users, self.from_year, self.to_year, 10
        )

        # Top 10 artistas por días
        top_days = self.database.get_top_artists_by_days(
            all_users, self.from_year, self.to_year, 10
        )

        # Top 10 artistas por número de canciones
        top_tracks = self.database.get_top_artists_by_track_count(
            all_users, self.from_year, self.to_year, 10
        )

        # Top 5 artistas por streaks
        top_streaks = self.database.get_top_artists_by_streaks(
            all_users, self.from_year, self.to_year, 5
        )

        # Procesar coincidencias para cada métrica especial
        special_data = {}

        # Gráfico 1: Top artistas por escuchas
        user_top_artists = {artist['name']: artist['plays'] for artist in top_scrobbles.get(user, [])}
        scrobbles_coincidences = {}
        for other_user in other_users:
            other_top_artists = {artist['name']: artist['plays'] for artist in top_scrobbles.get(other_user, [])}
            common_artists = set(user_top_artists.keys()) & set(other_top_artists.keys())
            if common_artists:
                total_plays = sum(user_top_artists[artist] + other_top_artists[artist] for artist in common_artists)
                scrobbles_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_plays': total_plays,
                    'artists': {artist: {'user_plays': user_top_artists[artist], 'other_plays': other_top_artists[artist]}
                              for artist in common_artists}
                }

        special_data['top_scrobbles'] = {
            'title': 'Top 10 Artistas por Escuchas',
            'data': {user: data['count'] for user, data in scrobbles_coincidences.items()},
            'total': sum(data['count'] for data in scrobbles_coincidences.values()),
            'details': scrobbles_coincidences,
            'type': 'top_scrobbles'
        }

        # Gráfico 2: Vuelve a casa (días)
        user_top_days = {artist['name']: artist['days'] for artist in top_days.get(user, [])}
        days_coincidences = {}
        for other_user in other_users:
            other_top_days = {artist['name']: artist['days'] for artist in top_days.get(other_user, [])}
            common_artists = set(user_top_days.keys()) & set(other_top_days.keys())
            if common_artists:
                total_days = sum(user_top_days[artist] + other_top_days[artist] for artist in common_artists)
                days_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_days': total_days,
                    'artists': {artist: {'user_days': user_top_days[artist], 'other_days': other_top_days[artist]}
                              for artist in common_artists}
                }

        special_data['top_days'] = {
            'title': 'Vuelve a Casa (Días de Escucha)',
            'data': {user: data['total_days'] for user, data in days_coincidences.items()},
            'total': sum(data['total_days'] for data in days_coincidences.values()),
            'details': days_coincidences,
            'type': 'top_days'
        }

        # Gráfico 3: Discografía completada
        user_top_tracks = {artist['name']: artist for artist in top_tracks.get(user, [])}
        tracks_coincidences = {}
        for other_user in other_users:
            other_top_tracks = {artist['name']: artist for artist in top_tracks.get(other_user, [])}
            common_artists = set(user_top_tracks.keys()) & set(other_top_tracks.keys())
            if common_artists:
                total_track_count = sum(user_top_tracks[artist]['track_count'] + other_top_tracks[artist]['track_count'] for artist in common_artists)
                tracks_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_track_count': total_track_count,
                    'artists': {artist: {
                        'user_tracks': user_top_tracks[artist]['track_count'],
                        'other_tracks': other_top_tracks[artist]['track_count'],
                        'user_plays': user_top_tracks[artist]['plays'],
                        'other_plays': other_top_tracks[artist]['plays']
                    } for artist in common_artists}
                }

        special_data['top_discography'] = {
            'title': 'Discografía Completada (Canciones)',
            'data': {user: data['total_track_count'] for user, data in tracks_coincidences.items()},
            'total': sum(data['total_track_count'] for data in tracks_coincidences.values()),
            'details': tracks_coincidences,
            'type': 'top_discography'
        }

        # Gráfico 4: Streaks
        user_top_streaks = {artist['name']: artist for artist in top_streaks.get(user, [])}
        streaks_coincidences = {}
        for other_user in other_users:
            other_top_streaks = {artist['name']: artist for artist in top_streaks.get(other_user, [])}
            common_artists = set(user_top_streaks.keys()) & set(other_top_streaks.keys())
            if common_artists:
                total_streak_days = sum(user_top_streaks[artist]['total_days'] + other_top_streaks[artist]['total_days'] for artist in common_artists)
                streaks_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_streak_days': total_streak_days,
                    'artists': {artist: {
                        'user_streak': user_top_streaks[artist]['max_streak'],
                        'other_streak': other_top_streaks[artist]['max_streak'],
                        'user_days': user_top_streaks[artist]['total_days'],
                        'other_days': other_top_streaks[artist]['total_days'],
                        'user_plays': user_top_streaks[artist]['plays'],
                        'other_plays': other_top_streaks[artist]['plays']
                    } for artist in common_artists}
                }

        special_data['top_streaks'] = {
            'title': 'Streaks (Días Consecutivos)',
            'data': {user: data['total_streak_days'] for user, data in streaks_coincidences.items()},
            'total': sum(data['total_streak_days'] for data in streaks_coincidences.values()),
            'details': streaks_coincidences,
            'type': 'top_streaks'
        }

        return special_data

    def _prepare_coincidence_charts_data(self, user: str, other_users: List[str],
                                       artist_coincidences: Dict, album_coincidences: Dict,
                                       track_coincidences: Dict, user_genres: List[Tuple],
                                       genre_coincidences: Dict, label_coincidences: Dict,
                                       release_year_coincidences: Dict, special_charts: Dict) -> Dict:
        """Prepara datos para gráficos circulares de coincidencias"""

        # Gráficos básicos de coincidencias
        artist_chart = self._prepare_coincidences_pie_data(
            "Artistas", artist_coincidences, other_users, user, 'artists'
        )

        album_chart = self._prepare_coincidences_pie_data(
            "Álbumes", album_coincidences, other_users, user, 'albums'
        )

        track_chart = self._prepare_coincidences_pie_data(
            "Canciones", track_coincidences, other_users, user, 'tracks'
        )

        # Gráfico de géneros del usuario (individual)
        genres_chart = self._prepare_genres_pie_data(user_genres, user)

        # Nuevos gráficos de coincidencias (ahora géneros, sellos y años son coincidencias)
        genre_coincidences_chart = self._prepare_coincidences_pie_data(
            "Géneros", genre_coincidences, other_users, user, 'genres'
        )

        label_coincidences_chart = self._prepare_coincidences_pie_data(
            "Sellos Discográficos", label_coincidences, other_users, user, 'labels'
        )

        release_year_coincidences_chart = self._prepare_coincidences_pie_data(
            "Años de Lanzamiento", release_year_coincidences, other_users, user, 'release_years'
        )

        return {
            'artists': artist_chart,
            'albums': album_chart,
            'tracks': track_chart,
            'genres': genres_chart,  # Individual del usuario
            'genre_coincidences': genre_coincidences_chart,  # Coincidencias
            'labels': label_coincidences_chart,  # Coincidencias
            'release_years': release_year_coincidences_chart,  # Coincidencias
            **special_charts  # Gráficos especiales
        }

    def _prepare_coincidences_pie_data(self, chart_type: str, coincidences: Dict,
                                     other_users: List[str], user: str, data_type: str) -> Dict:
        """Prepara datos para gráfico circular de coincidencias con popups optimizados"""
        user_data = {}
        popup_details = {}

        for other_user in other_users:
            if other_user in coincidences:
                count = len(coincidences[other_user])
                user_data[other_user] = count

                # Para popups: obtener datos específicos según el tipo
                if count > 0:
                    if data_type == 'artists':
                        # Top 5 álbumes de estos artistas
                        artists = list(coincidences[other_user].keys())[:10]
                        popup_details[other_user] = self.database.get_top_albums_for_artists(
                            user, artists, self.from_year, self.to_year, 5
                        )
                    elif data_type == 'albums':
                        # Top 5 canciones de estos álbumes
                        albums = list(coincidences[other_user].keys())[:10]
                        popup_details[other_user] = self.database.get_top_tracks_for_albums(
                            user, albums, self.from_year, self.to_year, 5
                        )
                    else:  # tracks
                        # Solo mostrar las top 5 canciones más escuchadas
                        sorted_tracks = sorted(
                            coincidences[other_user].items(),
                            key=lambda x: x[1]['user_plays'],
                            reverse=True
                        )[:5]
                        popup_details[other_user] = dict(sorted_tracks)
                else:
                    popup_details[other_user] = {}
            else:
                user_data[other_user] = 0
                popup_details[other_user] = {}

        # Solo incluir usuarios con coincidencias
        filtered_data = {user: count for user, count in user_data.items() if count > 0}
        filtered_details = {user: details for user, details in popup_details.items() if user_data.get(user, 0) > 0}

        return {
            'title': f'Coincidencias en {chart_type}',
            'data': filtered_data,
            'total': sum(filtered_data.values()) if filtered_data else 0,
            'details': filtered_details,
            'type': data_type
        }

    def _prepare_genres_pie_data(self, user_genres: List[Tuple], user: str) -> Dict:
        """Prepara datos para gráfico circular de géneros con artistas top"""
        # Tomar solo los top 8 géneros para visualización
        top_genres = dict(user_genres[:8])
        total_plays = sum(top_genres.values()) if top_genres else 0

        # Para popup: obtener top 5 artistas por género
        popup_details = {}
        for genre, plays in user_genres[:8]:
            artists = self.database.get_top_artists_for_genre(
                user, genre, self.from_year, self.to_year, 5
            )
            popup_details[genre] = artists

        return {
            'title': 'Distribución de Géneros',
            'data': top_genres,
            'total': total_plays,
            'details': popup_details,
            'type': 'genres'
        }

    def _prepare_years_labels_pie_data(self, chart_type: str, data: Dict) -> Dict:
        """Prepara datos para gráfico circular de años/sellos con artistas top"""
        chart_data = {}
        popup_details = {}

        for category, info in data.items():
            chart_data[category] = info['total']
            popup_details[category] = info['artists']  # Ya limitados a top 5

        return {
            'title': chart_type,
            'data': chart_data,
            'total': sum(chart_data.values()) if chart_data else 0,
            'details': popup_details,
            'type': 'years_labels'
        }

    def _analyze_evolution(self, user: str, all_users: List[str]) -> Dict:
        """Analiza la evolución temporal de COINCIDENCIAS del usuario"""
        other_users = [u for u in all_users if u != user]

        # Evolución de coincidencias de géneros por año
        genres_evolution = self._analyze_genres_coincidences_evolution(user, other_users)

        # Evolución de coincidencias de sellos por año
        labels_evolution = self._analyze_labels_coincidences_evolution(user, other_users)

        # Evolución de coincidencias de años de lanzamiento por año
        release_years_evolution = self._analyze_release_years_coincidences_evolution(user, other_users)

        # Evolución de coincidencias básicas por año - con datos detallados para popups
        coincidences_evolution = self._analyze_coincidences_evolution_with_details(user, other_users)

        return {
            'genres': genres_evolution,
            'labels': labels_evolution,
            'release_years': release_years_evolution,
            'coincidences': coincidences_evolution
        }

    def _analyze_genres_coincidences_evolution(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias de géneros por año"""
        evolution_data = {}
        evolution_details = {}

        for other_user in other_users:
            evolution_data[other_user] = {}
            evolution_details[other_user] = {}

            for year in range(self.from_year, self.to_year + 1):
                genre_coincidences = self.database.get_common_genres_with_users(
                    user, [other_user], year, year
                )

                if other_user in genre_coincidences:
                    count = len(genre_coincidences[other_user])
                    evolution_data[other_user][year] = count

                    # Top 5 géneros con más coincidencias
                    top_genres = sorted(
                        genre_coincidences[other_user].items(),
                        key=lambda x: x[1]['total_plays'],
                        reverse=True
                    )[:5]
                    evolution_details[other_user][year] = [
                        {'name': name, 'plays': data['total_plays']}
                        for name, data in top_genres
                    ]
                else:
                    evolution_data[other_user][year] = 0
                    evolution_details[other_user][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

    def _analyze_labels_coincidences_evolution(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias de sellos por año"""
        evolution_data = {}
        evolution_details = {}

        for other_user in other_users:
            evolution_data[other_user] = {}
            evolution_details[other_user] = {}

            for year in range(self.from_year, self.to_year + 1):
                label_coincidences = self.database.get_common_labels_with_users(
                    user, [other_user], year, year
                )

                if other_user in label_coincidences:
                    count = len(label_coincidences[other_user])
                    evolution_data[other_user][year] = count

                    # Top 5 sellos con más coincidencias
                    top_labels = sorted(
                        label_coincidences[other_user].items(),
                        key=lambda x: x[1]['total_plays'],
                        reverse=True
                    )[:5]
                    evolution_details[other_user][year] = [
                        {'name': name, 'plays': data['total_plays']}
                        for name, data in top_labels
                    ]
                else:
                    evolution_data[other_user][year] = 0
                    evolution_details[other_user][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

    def _analyze_release_years_coincidences_evolution(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias de décadas por año"""
        evolution_data = {}
        evolution_details = {}

        for other_user in other_users:
            evolution_data[other_user] = {}
            evolution_details[other_user] = {}

            for year in range(self.from_year, self.to_year + 1):
                decade_coincidences = self.database.get_common_release_years_with_users(
                    user, [other_user], year, year
                )

                if other_user in decade_coincidences:
                    count = len(decade_coincidences[other_user])
                    evolution_data[other_user][year] = count

                    # Top 5 décadas con más coincidencias
                    top_decades = sorted(
                        decade_coincidences[other_user].items(),
                        key=lambda x: x[1]['total_plays'],
                        reverse=True
                    )[:5]
                    evolution_details[other_user][year] = [
                        {'name': name, 'plays': data['total_plays']}
                        for name, data in top_decades
                    ]
                else:
                    evolution_data[other_user][year] = 0
                    evolution_details[other_user][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

    def _analyze_labels_evolution_limited(self, user: str) -> Dict:
        """Analiza la evolución de sellos por año - solo top 10"""
        cursor = self.database.conn.cursor()

        labels_by_year = {}

        for year in range(self.from_year, self.to_year + 1):
            from_timestamp = int(datetime(year, 1, 1).timestamp())
            to_timestamp = int(datetime(year + 1, 1, 1).timestamp()) - 1

            cursor.execute('''
                SELECT al.label, s.artist, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND al.label IS NOT NULL AND al.label != ''
                GROUP BY al.label, s.artist
                ORDER BY al.label, plays DESC
            ''', (user, from_timestamp, to_timestamp))

            year_labels = defaultdict(lambda: {'plays': 0, 'artists': []})
            for row in cursor.fetchall():
                label = row['label']
                year_labels[label]['plays'] += row['plays']
                if len(year_labels[label]['artists']) < 5:
                    year_labels[label]['artists'].append({
                        'name': row['artist'],
                        'plays': row['plays']
                    })

            labels_by_year[year] = dict(year_labels)

        # Obtener los top 10 sellos de todo el período
        all_labels = defaultdict(int)
        for year_data in labels_by_year.values():
            for label, data in year_data.items():
                all_labels[label] += data['plays']

        top_labels = sorted(all_labels.items(), key=lambda x: x[1], reverse=True)[:10]
        top_label_names = [label for label, _ in top_labels]

        # Crear datos para el gráfico lineal
        evolution_data = {}
        evolution_details = {}

        for label in top_label_names:
            evolution_data[label] = {}
            evolution_details[label] = {}
            for year in range(self.from_year, self.to_year + 1):
                year_data = labels_by_year.get(year, {})
                if label in year_data:
                    evolution_data[label][year] = year_data[label]['plays']
                    evolution_details[label][year] = year_data[label]['artists']
                else:
                    evolution_data[label][year] = 0
                    evolution_details[label][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'top_labels': top_label_names
        }

    def _analyze_release_years_evolution_limited(self, user: str) -> Dict:
        """Analiza la evolución de décadas de lanzamiento por año - solo top 8"""
        cursor = self.database.conn.cursor()

        decades_by_year = {}

        for year in range(self.from_year, self.to_year + 1):
            from_timestamp = int(datetime(year, 1, 1).timestamp())
            to_timestamp = int(datetime(year + 1, 1, 1).timestamp()) - 1

            cursor.execute('''
                SELECT ard.release_year, s.artist, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND ard.release_year IS NOT NULL
                GROUP BY ard.release_year, s.artist
                ORDER BY ard.release_year, plays DESC
            ''', (user, from_timestamp, to_timestamp))

            year_decades = defaultdict(lambda: {'plays': 0, 'artists': []})
            for row in cursor.fetchall():
                decade = self.database._get_decade(row['release_year'])
                year_decades[decade]['plays'] += row['plays']
                if len(year_decades[decade]['artists']) < 5:
                    year_decades[decade]['artists'].append({
                        'name': row['artist'],
                        'plays': row['plays']
                    })

            decades_by_year[year] = dict(year_decades)

        # Obtener las top 8 décadas de todo el período
        all_decades = defaultdict(int)
        for year_data in decades_by_year.values():
            for decade, data in year_data.items():
                all_decades[decade] += data['plays']

        top_decades = sorted(all_decades.items(), key=lambda x: x[1], reverse=True)[:8]
        top_decade_names = [decade for decade, _ in top_decades]

        # Crear datos para el gráfico lineal
        evolution_data = {}
        evolution_details = {}

        for decade in top_decade_names:
            evolution_data[decade] = {}
            evolution_details[decade] = {}
            for year in range(self.from_year, self.to_year + 1):
                year_data = decades_by_year.get(year, {})
                if decade in year_data:
                    evolution_data[decade][year] = year_data[decade]['plays']
                    evolution_details[decade][year] = year_data[decade]['artists']
                else:
                    evolution_data[decade][year] = 0
                    evolution_details[decade][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'top_decades': top_decade_names
        }

    def _analyze_coincidences_evolution_with_details(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias por año - con datos detallados para popups"""
        evolution_data = {
            'artists': {},
            'albums': {},
            'tracks': {}
        }

        evolution_details = {
            'artists': {},
            'albums': {},
            'tracks': {}
        }

        # Para cada año, calcular coincidencias con detalles
        for year in range(self.from_year, self.to_year + 1):
            # Obtener coincidencias detalladas
            artist_coincidences = self.database.get_common_artists_with_users(
                user, other_users, year, year
            )
            album_coincidences = self.database.get_common_albums_with_users(
                user, other_users, year, year
            )
            track_coincidences = self.database.get_common_tracks_with_users(
                user, other_users, year, year
            )

            # Preparar datos por usuario
            for other_user in other_users:
                if other_user not in evolution_data['artists']:
                    evolution_data['artists'][other_user] = {}
                    evolution_data['albums'][other_user] = {}
                    evolution_data['tracks'][other_user] = {}
                    evolution_details['artists'][other_user] = {}
                    evolution_details['albums'][other_user] = {}
                    evolution_details['tracks'][other_user] = {}

                # Artistas
                artist_data = artist_coincidences.get(other_user, {})
                evolution_data['artists'][other_user][year] = len(artist_data)
                # Top 5 artistas con más coincidencias
                top_artists = sorted(
                    artist_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['artists'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_artists
                ]

                # Álbumes
                album_data = album_coincidences.get(other_user, {})
                evolution_data['albums'][other_user][year] = len(album_data)
                # Top 5 álbumes con más coincidencias
                top_albums = sorted(
                    album_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['albums'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_albums
                ]

                # Canciones
                track_data = track_coincidences.get(other_user, {})
                evolution_data['tracks'][other_user][year] = len(track_data)
                # Top 5 canciones con más coincidencias
                top_tracks = sorted(
                    track_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['tracks'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_tracks
                ]

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

    def _analyze_genres_evolution_limited(self, user: str) -> Dict:
        """Analiza la evolución de géneros por año - solo top 10 con detalles"""
        genres_by_year = self.database.get_user_genres_by_year(
            user, self.from_year, self.to_year, limit=10
        )

        # Obtener los top 10 géneros de todo el período
        top_genres = self.database.get_user_top_genres(
            user, self.from_year, self.to_year, limit=10
        )

        top_genre_names = [genre for genre, _ in top_genres]

        # Crear datos para el gráfico lineal
        evolution_data = {}
        evolution_details = {}

        for genre in top_genre_names:
            evolution_data[genre] = {}
            evolution_details[genre] = {}
            for year in range(self.from_year, self.to_year + 1):
                year_genres = genres_by_year.get(year, {})
                evolution_data[genre][year] = year_genres.get(genre, 0)

                # Para cada género/año, obtener top 5 artistas
                if year_genres.get(genre, 0) > 0:
                    artists = self.database.get_top_artists_for_genre(
                        user, genre, year, year, 5
                    )
                    evolution_details[genre][year] = artists
                else:
                    evolution_details[genre][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'top_genres': top_genre_names
        }


class UserStatsHTMLGenerator:
    """Clase para generar HTML con gráficos interactivos de estadísticas de usuarios"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, all_user_stats: Dict, users: List[str], years_back: int) -> str:
        """Genera el HTML completo para estadísticas de usuarios"""
        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(all_user_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Usuarios - Estadísticas Individuales</title>
    <link rel="icon" type="image/png" href="images/music.png">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: #181825;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: #1e1e2e;
            padding: 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        h1 {{
            font-size: 2em;
            color: #cba6f7;
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: #a6adc8;
            font-size: 1em;
        }}

        .controls {{
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .control-group {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}

        label {{
            color: #cba6f7;
            font-weight: 600;
        }}

        select {{
            padding: 8px 15px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
        }}

        select:hover {{
            border-color: #cba6f7;
        }}

        select:focus {{
            outline: none;
            border-color: #cba6f7;
            box-shadow: 0 0 0 3px rgba(203, 166, 247, 0.2);
        }}

        .view-buttons {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .view-btn {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }}

        .view-btn:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .view-btn.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .user-header {{
            background: #1e1e2e;
            padding: 25px 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        .user-header h2 {{
            color: #cba6f7;
            font-size: 1.5em;
            margin-bottom: 8px;
        }}

        .user-info {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .stats-container {{
            padding: 30px;
        }}

        .view {{
            display: none;
        }}

        .view.active {{
            display: block;
        }}

        .coincidences-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 25px;
            margin-bottom: 30px;
        }}

        .chart-container {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }}

        .chart-container h3 {{
            color: #cba6f7;
            font-size: 1.2em;
            margin-bottom: 15px;
            text-align: center;
        }}

        .chart-wrapper {{
            position: relative;
            height: 300px;
            margin-bottom: 10px;
        }}

        .chart-info {{
            text-align: center;
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .evolution-section {{
            margin-bottom: 40px;
        }}

        .evolution-section h3 {{
            color: #cba6f7;
            font-size: 1.3em;
            margin-bottom: 20px;
            border-bottom: 2px solid #cba6f7;
            padding-bottom: 10px;
        }}

        .evolution-charts {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 25px;
        }}

        .evolution-chart {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }}

        .evolution-chart h4 {{
            color: #cba6f7;
            font-size: 1.1em;
            margin-bottom: 15px;
            text-align: center;
        }}

        .line-chart-wrapper {{
            position: relative;
            height: 400px;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
        }}

        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            background: #1e1e2e;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #313244;
            text-align: center;
        }}

        .summary-card .number {{
            font-size: 1.8em;
            font-weight: 600;
            color: #cba6f7;
            margin-bottom: 5px;
        }}

        .summary-card .label {{
            font-size: 0.9em;
            color: #a6adc8;
        }}

        .popup-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 999;
        }}

        .popup {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e1e2e;
            border: 2px solid #cba6f7;
            border-radius: 12px;
            padding: 20px;
            max-width: 500px;
            max-height: 400px;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }}

        .popup-header {{
            color: #cba6f7;
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 15px;
            border-bottom: 1px solid #313244;
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .popup-close {{
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.2em;
            cursor: pointer;
            padding: 0;
        }}

        .popup-close:hover {{
            color: #cba6f7;
        }}

        .popup-content {{
            max-height: 300px;
            overflow-y: auto;
        }}

        .popup-item {{
            padding: 8px 12px;
            background: #181825;
            margin-bottom: 5px;
            border-radius: 6px;
            border-left: 3px solid #45475a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .popup-item .name {{
            color: #cdd6f4;
            font-weight: 600;
        }}

        .popup-item .count {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .coincidences-grid {{
                grid-template-columns: 1fr;
            }}

            .evolution-charts {{
                grid-template-columns: 1fr;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .view-buttons {{
                justify-content: center;
            }}

            .summary-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>👤 Estadísticas Individuales</h1>
            <p class="subtitle">Análisis detallado por usuario</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Usuario:</label>
                <select id="userSelect">
                    <!-- Se llenará dinámicamente -->
                </select>
            </div>

            <div class="control-group">
                <label>Vista:</label>
                <div class="view-buttons">
                    <button class="view-btn active" data-view="individual">YoMiMeConMigo</button>
                    <button class="view-btn" data-view="coincidences">Coincidencias</button>
                    <button class="view-btn" data-view="evolution">Evolución</button>
                </div>
            </div>
        </div>

        <div id="userHeader" class="user-header">
            <h2 id="userName">Selecciona un usuario</h2>
            <p class="user-info" id="userInfo">Período de análisis: {years_back + 1} años</p>
        </div>

        <div class="stats-container">
            <!-- Resumen de estadísticas -->
            <div id="summaryStats" class="summary-stats">
                <!-- Se llenará dinámicamente -->
            </div>

            <!-- Vista Individual (YoMiMeConMigo) -->
            <div id="individualView" class="view active">
                <div class="evolution-section">
                    <h3>🎵 Evolución de Géneros Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualGenresChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🏷️ Evolución de Sellos Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Sellos por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualLabelsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🎤 Evolución de Artistas Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualArtistsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>💫 One Hit Wonders</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con 1 Canción (+25 scrobbles)</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualOneHitChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🔥 Artistas con Mayor Streak</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con Más Días Consecutivos</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualStreakChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📚 Artistas con Mayor Discografía</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con Más Canciones Únicas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualTrackCountChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🌟 Artistas Nuevos</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas Nuevos (Sin Escuchas Previas)</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualNewArtistsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📈 Artistas en Ascenso</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas que Más Rápido Subieron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualRisingChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📉 Artistas en Declive</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas que Más Rápido Bajaron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualFallingChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Vista de Coincidencias -->
            <div id="coincidencesView" class="view">
                <div class="coincidences-grid">
                    <div class="chart-container">
                        <h3>Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="artistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="artistsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Álbumes</h3>
                        <div class="chart-wrapper">
                            <canvas id="albumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="albumsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Canciones</h3>
                        <div class="chart-wrapper">
                            <canvas id="tracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="tracksInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Géneros (Individual)</h3>
                        <div class="chart-wrapper">
                            <canvas id="genresChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Géneros (Coincidencias)</h3>
                        <div class="chart-wrapper">
                            <canvas id="genreCoincidencesChart"></canvas>
                        </div>
                        <div class="chart-info" id="genreCoincidencesInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Sellos Discográficos</h3>
                        <div class="chart-wrapper">
                            <canvas id="labelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Años de Lanzamiento</h3>
                        <div class="chart-wrapper">
                            <canvas id="releaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="releaseYearsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>📈 Top 10 Artistas por Escuchas</h3>
                        <div class="chart-wrapper">
                            <canvas id="topScrobblesChart"></canvas>
                        </div>
                        <div class="chart-info" id="topScrobblesInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>🏠 Vuelve a Casa</h3>
                        <div class="chart-wrapper">
                            <canvas id="topDaysChart"></canvas>
                        </div>
                        <div class="chart-info" id="topDaysInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>📚 Discografía Completada</h3>
                        <div class="chart-wrapper">
                            <canvas id="topDiscographyChart"></canvas>
                        </div>
                        <div class="chart-info" id="topDiscographyInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>💫 Streaks</h3>
                        <div class="chart-wrapper">
                            <canvas id="topStreaksChart"></canvas>
                        </div>
                        <div class="chart-info" id="topStreaksInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista de Evolución -->
            <div id="evolutionView" class="view">
                <div class="evolution-section">
                    <h3>🎵 Evolución de Géneros (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="genresEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🏷️ Evolución de Sellos (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Sellos por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="labelsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📅 Evolución de Décadas (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Décadas por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="releaseYearsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🤝 Evolución de Coincidencias Básicas</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Artistas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="artistsEvolutionChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Coincidencias en Álbumes</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="albumsEvolutionChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Coincidencias en Canciones</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="tracksEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        <!-- Popup para mostrar detalles -->
        <div id="popupOverlay" class="popup-overlay" style="display: none;"></div>
        <div id="popup" class="popup" style="display: none;">
            <div class="popup-header">
                <span id="popupTitle">Detalles</span>
                <button id="popupClose" class="popup-close">×</button>
            </div>
            <div id="popupContent" class="popup-content"></div>
        </div>
        </div>
    </div>

    <script>
        const users = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};

        let currentUser = null;
        let currentView = 'individual';
        let charts = {{}};

        // Inicialización simple sin DOMContentLoaded - siguiendo el patrón de html_anual.py
        const userSelect = document.getElementById('userSelect');

        // Llenar selector de usuarios
        users.forEach(user => {{
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        }});

        // Manejar botones de vista
        const viewButtons = document.querySelectorAll('.view-btn');
        viewButtons.forEach(btn => {{
            btn.addEventListener('click', function() {{
                const view = this.dataset.view;
                switchView(view);
            }});
        }});

        function switchView(view) {{
            currentView = view;

            // Update buttons
            document.querySelectorAll('.view-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            document.querySelector(`[data-view="${{view}}"]`).classList.add('active');

            // Update views
            document.querySelectorAll('.view').forEach(v => {{
                v.classList.remove('active');
            }});
            document.getElementById(view + 'View').classList.add('active');

            // Render appropriate charts
            if (currentUser && allStats[currentUser]) {{
                const userStats = allStats[currentUser];
                if (view === 'individual') {{
                    renderIndividualCharts(userStats);
                }} else if (view === 'coincidences') {{
                    renderCoincidenceCharts(userStats);
                }} else if (view === 'evolution') {{
                    renderEvolutionCharts(userStats);
                }}
            }}
        }}

        function selectUser(username) {{
            currentUser = username;
            const userStats = allStats[username];

            if (!userStats) {{
                console.error('No stats found for user:', username);
                return;
            }}

            updateUserHeader(username, userStats);
            updateSummaryStats(userStats);

            if (currentView === 'individual') {{
                renderIndividualCharts(userStats);
            }} else if (currentView === 'coincidences') {{
                renderCoincidenceCharts(userStats);
            }} else if (currentView === 'evolution') {{
                renderEvolutionCharts(userStats);
            }}
        }}

        function updateUserHeader(username, userStats) {{
            document.getElementById('userName').textContent = username;
            document.getElementById('userInfo').innerHTML =
                `Período: ${{userStats.period}} | Generado: ${{userStats.generated_at}}`;
        }}

        function updateSummaryStats(userStats) {{
            const totalScrobbles = Object.values(userStats.yearly_scrobbles).reduce((a, b) => a + b, 0);

            const artistsChart = userStats.coincidences.charts.artists;
            const albumsChart = userStats.coincidences.charts.albums;
            const tracksChart = userStats.coincidences.charts.tracks;
            const genresChart = userStats.coincidences.charts.genres;
            const releaseYearsChart = userStats.coincidences.charts.release_years;
            const labelsChart = userStats.coincidences.charts.labels;

            const totalArtistCoincidences = Object.keys(artistsChart.data || {{}}).length;
            const totalAlbumCoincidences = Object.keys(albumsChart.data || {{}}).length;
            const totalTrackCoincidences = Object.keys(tracksChart.data || {{}}).length;
            const totalGenres = Object.keys(genresChart.data || {{}}).length;
            const totalReleaseYears = Object.keys(releaseYearsChart.data || {{}}).length;
            const totalLabels = Object.keys(labelsChart.data || {{}}).length;

            const summaryHTML = `
                <div class="summary-card">
                    <div class="number">${{totalScrobbles.toLocaleString()}}</div>
                    <div class="label">Scrobbles</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalArtistCoincidences}}</div>
                    <div class="label">Usuarios (Artistas)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalAlbumCoincidences}}</div>
                    <div class="label">Usuarios (Álbumes)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalGenres}}</div>
                    <div class="label">Géneros</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalReleaseYears}}</div>
                    <div class="label">Décadas</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalLabels}}</div>
                    <div class="label">Sellos</div>
                </div>
            `;

            document.getElementById('summaryStats').innerHTML = summaryHTML;
        }}

        function renderCoincidenceCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Gráficos básicos
            renderPieChart('artistsChart', userStats.coincidences.charts.artists, 'artistsInfo');
            renderPieChart('albumsChart', userStats.coincidences.charts.albums, 'albumsInfo');
            renderPieChart('tracksChart', userStats.coincidences.charts.tracks, 'tracksInfo');
            renderPieChart('genresChart', userStats.coincidences.charts.genres, 'genresInfo');

            // Nuevos gráficos de coincidencias
            renderPieChart('genreCoincidencesChart', userStats.coincidences.charts.genre_coincidences, 'genreCoincidencesInfo');
            renderPieChart('labelsChart', userStats.coincidences.charts.labels, 'labelsInfo');
            renderPieChart('releaseYearsChart', userStats.coincidences.charts.release_years, 'releaseYearsInfo');

            // Gráficos especiales
            renderPieChart('topScrobblesChart', userStats.coincidences.charts.top_scrobbles, 'topScrobblesInfo');
            renderPieChart('topDaysChart', userStats.coincidences.charts.top_days, 'topDaysInfo');
            renderPieChart('topDiscographyChart', userStats.coincidences.charts.top_discography, 'topDiscographyInfo');
            renderPieChart('topStreaksChart', userStats.coincidences.charts.top_streaks, 'topStreaksInfo');
        }}

        function renderEvolutionCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Ahora todos son de coincidencias
            renderCoincidencesEvolution('genres', userStats.evolution.genres);
            renderCoincidencesEvolution('labels', userStats.evolution.labels);
            renderCoincidencesEvolution('release_years', userStats.evolution.release_years);
            renderCoincidencesEvolution('artists', userStats.evolution.coincidences);
            renderCoincidencesEvolution('albums', userStats.evolution.coincidences);
            renderCoincidencesEvolution('tracks', userStats.evolution.coincidences);
        }}

        function renderPieChart(canvasId, chartData, infoId) {{
            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';
            info.innerHTML = `Total: ${{chartData.total.toLocaleString()}} | Click en una porción para ver detalles`;

            const data = {{
                labels: Object.keys(chartData.data),
                datasets: [{{
                    data: Object.values(chartData.data),
                    backgroundColor: colors.slice(0, Object.keys(chartData.data).length),
                    borderColor: '#181825',
                    borderWidth: 2
                }}]
            }};

            const config = {{
                type: 'pie',
                data: data,
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 15,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const index = elements[0].index;
                            const label = data.labels[index];
                            showSmartPopup(chartData, label);
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function showSmartPopup(chartData, selectedLabel) {{
            const details = chartData.details[selectedLabel];
            const chartType = chartData.type;

            if (!details) return;

            let title = '';
            let content = '';

            if (chartType === 'artists') {{
                // Mostrar álbumes top para estos artistas
                title = `Top Álbumes - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(artist => {{
                    if (details[artist] && details[artist].length > 0) {{
                        content += `<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">${{artist}}</h4>`;
                        details[artist].forEach(album => {{
                            content += `<div class="popup-item">
                                <span class="name">${{album.name}}</span>
                                <span class="count">${{album.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }});
            }} else if (chartType === 'albums') {{
                // Mostrar canciones top para estos álbumes
                title = `Top Canciones - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(album => {{
                    if (details[album] && details[album].length > 0) {{
                        content += `<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">${{album}}</h4>`;
                        details[album].forEach(track => {{
                            content += `<div class="popup-item">
                                <span class="name">${{track.name}}</span>
                                <span class="count">${{track.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }});
            }} else if (chartType === 'tracks') {{
                // Mostrar canciones más escuchadas
                title = `Top Canciones - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(track => {{
                    const trackData = details[track];
                    content += `<div class="popup-item">
                        <span class="name">${{track}}</span>
                        <span class="count">${{trackData.user_plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'genres') {{
                // Mostrar artistas top para este género
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'years_labels') {{
                // Mostrar artistas top para esta década/sello
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'top_scrobbles') {{
                // Mostrar top canciones del artista para ambos usuarios
                title = `Top Artistas Coincidentes - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">${{artistData.user_plays + artistData.other_plays}} plays totales</span>
                        </div>`;
                    }});
                }}
            }} else if (chartType === 'top_days') {{
                // Mostrar artistas coincidentes con días
                title = `Artistas "Vuelve a Casa" - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">${{artistData.user_days + artistData.other_days}} días totales</span>
                        </div>`;
                    }});
                }}
            }} else if (chartType === 'top_discography') {{
                // Mostrar artistas coincidentes con número de canciones
                title = `Discografía Completada - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">${{artistData.user_tracks + artistData.other_tracks}} canciones</span>
                        </div>`;
                    }});
                }}
            }} else if (chartType === 'top_streaks') {{
                // Mostrar artistas coincidentes con streaks
                title = `Streaks Coincidentes - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">Max: ${{Math.max(artistData.user_streak, artistData.other_streak)}} días</span>
                        </div>`;
                    }});
                }}
            }}

            if (content) {{
                document.getElementById('popupTitle').textContent = title;
                document.getElementById('popupContent').innerHTML = content;
                document.getElementById('popupOverlay').style.display = 'block';
                document.getElementById('popup').style.display = 'block';
            }}
        }}

        // Configurar cierre de popup
        document.getElementById('popupClose').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});

        document.getElementById('popupOverlay').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});

        function renderCoincidencesEvolution(type, evolutionData) {{
            let canvas, chartId;

            // Mapear tipos a canvas IDs
            if (type === 'genres') {{
                canvas = document.getElementById('genresEvolutionChart');
                chartId = 'genresEvolutionChart';
            }} else if (type === 'labels') {{
                canvas = document.getElementById('labelsEvolutionChart');
                chartId = 'labelsEvolutionChart';
            }} else if (type === 'release_years') {{
                canvas = document.getElementById('releaseYearsEvolutionChart');
                chartId = 'releaseYearsEvolutionChart';
            }} else {{
                canvas = document.getElementById(type + 'EvolutionChart');
                chartId = type + 'EvolutionChart';
            }}

            if (!evolutionData || !evolutionData.data) {{
                return;
            }}

            // Para tipos básicos (artists, albums, tracks), usar evolutionData.data[type]
            // Para nuevos tipos (genres, labels, release_years), usar directamente evolutionData.data
            let typeData, detailsData;
            if (['artists', 'albums', 'tracks'].includes(type)) {{
                typeData = evolutionData.data[type];
                detailsData = evolutionData.details[type];
            }} else {{
                typeData = evolutionData.data;
                detailsData = evolutionData.details;
            }}

            if (!typeData) return;

            const datasets = [];
            let colorIndex = 0;

            Object.keys(typeData).forEach(user => {{
                datasets.push({{
                    label: user,
                    data: evolutionData.years.map(year => typeData[user][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: evolutionData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const user = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const coincidences = this.data.datasets[datasetIndex].data[pointIndex];

                            if (coincidences > 0 && detailsData && detailsData[user] && detailsData[user][year]) {{
                                const typeLabel = type === 'artists' ? 'Artistas' :
                                               type === 'albums' ? 'Álbumes' :
                                               type === 'tracks' ? 'Canciones' :
                                               type === 'genres' ? 'Géneros' :
                                               type === 'labels' ? 'Sellos' :
                                               type === 'release_years' ? 'Décadas' : type;

                                // Para gráficos básicos, mostrar top 10; para otros, top 5
                                const limit = ['artists', 'albums', 'tracks'].includes(type) ? 10 : 5;
                                const limitedDetails = detailsData[user][year].slice(0, limit);
                                showLinearPopup(`Top ${{limit}} ${{typeLabel}} - ${{user}} (${{year}})`, limitedDetails);
                            }}
                        }}
                    }}
                }}
            }};

            charts[chartId] = new Chart(canvas, config);
        }}

        function showLinearPopup(title, details) {{
            if (!details || details.length === 0) return;

            let content = '';
            details.slice(0, 5).forEach(item => {{
                content += `<div class="popup-item">
                    <span class="name">${{item.name}}</span>
                    <span class="count">${{item.plays}} plays</span>
                </div>`;
            }});

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function renderIndividualCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar todos los gráficos individuales
            if (userStats.individual) {{
                renderIndividualLineChart('individualGenresChart', userStats.individual.genres, 'Géneros');
                renderIndividualLineChart('individualLabelsChart', userStats.individual.labels, 'Sellos');
                renderIndividualLineChart('individualArtistsChart', userStats.individual.artists, 'Artistas');
                renderIndividualLineChart('individualOneHitChart', userStats.individual.one_hit_wonders, 'One Hit Wonders');
                renderIndividualLineChart('individualStreakChart', userStats.individual.streak_artists, 'Artistas con Mayor Streak');
                renderIndividualLineChart('individualTrackCountChart', userStats.individual.track_count_artists, 'Artistas con Mayor Discografía');
                renderIndividualLineChart('individualNewArtistsChart', userStats.individual.new_artists, 'Artistas Nuevos');
                renderIndividualLineChart('individualRisingChart', userStats.individual.rising_artists, 'Artistas en Ascenso');
                renderIndividualLineChart('individualFallingChart', userStats.individual.falling_artists, 'Artistas en Declive');
            }}
        }}

        function renderIndividualLineChart(canvasId, chartData, title) {{
            const canvas = document.getElementById(canvasId);

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                return;
            }}

            const datasets = [];
            let colorIndex = 0;

            Object.keys(chartData.data).forEach(item => {{
                datasets.push({{
                    label: item,
                    data: chartData.years.map(year => chartData.data[item][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: chartData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const item = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const plays = this.data.datasets[datasetIndex].data[pointIndex];

                            if (plays > 0) {{
                                showIndividualPopup(title, item, year, plays);
                            }}
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function showIndividualPopup(category, item, year, plays) {{
            const title = `${{category}} - ${{item}} (${{year}})`;
            const content = `<div class="popup-item">
                <span class="name">${{item}} en ${{year}}</span>
                <span class="count">${{plays}} reproducciones</span>
            </div>`;

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function showEvolutionPopup(dataType, item, year, value) {{
            const title = `${{dataType.charAt(0).toUpperCase() + dataType.slice(1)}} - ${{item}} (${{year}})`;
            const content = `<div class="popup-item">
                <span class="name">${{item}} en ${{year}}</span>
                <span class="count">${{value}} ${{dataType.includes('coincidencias') ? 'coincidencias' : 'reproducciones'}}</span>
            </div>`;

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        // Siguiendo el patrón de html_anual.py: eventos directos al final
        userSelect.addEventListener('change', function() {{
            selectUser(this.value);
        }});

        // Seleccionar primer usuario automáticamente si hay usuarios
        if (users.length > 0) {{
            selectUser(users[0]);
        }}
    </script>
</body>
</html>"""


def main():
    """Función principal para generar estadísticas de usuarios"""
    parser = argparse.ArgumentParser(description='Generador de estadísticas individuales de usuarios de Last.fm')
    parser.add_argument('--years-back', type=int, default=5,
                       help='Número de años hacia atrás para analizar (por defecto: 5)')
    parser.add_argument('--output', type=str, default=None,
                       help='Archivo de salida HTML (por defecto: auto-generado con fecha)')
    args = parser.parse_args()

    # Auto-generar nombre de archivo si no se especifica
    if args.output is None:
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        args.output = f'docs/usuarios_{from_year}-{current_year}.html'

    try:
        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        if not users:
            raise ValueError("LASTFM_USERS no encontrada en las variables de entorno")

        print("📊 Iniciando análisis de usuarios...")

        # Inicializar componentes
        database = UserStatsDatabase()
        analyzer = UserStatsAnalyzer(database, years_back=args.years_back)
        html_generator = UserStatsHTMLGenerator()

        # Analizar estadísticas para todos los usuarios
        print(f"👤 Analizando {len(users)} usuarios...")
        all_user_stats = {}

        for user in users:
            print(f"  • Procesando {user}...")
            user_stats = analyzer.analyze_user(user, users)
            all_user_stats[user] = user_stats

        # Generar HTML
        print("🎨 Generando HTML...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Guardar archivo
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Archivo generado: {args.output}")
        print(f"📊 Optimización aplicada:")
        print(f"  • Análisis: Datos completos procesados en Python")
        print(f"  • HTML: Solo datos necesarios para gráficos")
        print(f"  • Resultado: Archivo HTML ligero con funcionalidad completa")

        # Mostrar resumen
        print("\n📈 Resumen:")
        for user, stats in all_user_stats.items():
            total_scrobbles = sum(stats['yearly_scrobbles'].values())
            print(f"  • {user}: {total_scrobbles:,} scrobbles analizados")

        database.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

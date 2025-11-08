#!/usr/bin/env python3
"""
UserStatsDatabase - Versión corregida con mejores popups y datos para YoMiMeConMigo
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from collections import defaultdict



class UserStatsDatabase:
    """Versión corregida con mejores popups y datos específicos para cada gráfico"""

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
            SELECT artist, track, COUNT(*) as total_plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist
            HAVING COUNT(DISTINCT track) = 1 AND total_plays >= ?
            ORDER BY total_plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, min_scrobbles, limit))

        return [{'name': row['artist'], 'track': row['track'], 'plays': row['total_plays']} for row in cursor.fetchall()]

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
        """Obtiene artistas que más rápido han bajado en rankings mensuales - ALGORITMO CORREGIDO"""
        rankings = self.get_artist_monthly_ranks(user, from_year, to_year)

        falling_artists = []
        for artist, monthly_ranks in rankings.items():
            months = sorted(monthly_ranks.keys())
            if len(months) < 2:
                continue

            # Algoritmo diferente: calcular la peor caída consecutiva
            max_decline = 0
            worst_streak = 0
            current_decline = 0
            worst_period = None

            for i in range(1, len(months)):
                prev_rank = monthly_ranks[months[i-1]]['rank']
                curr_rank = monthly_ranks[months[i]]['rank']

                # Si empeoró el ranking
                if curr_rank > prev_rank:
                    current_decline += (curr_rank - prev_rank)
                    worst_streak += 1

                    # Si es la peor caída hasta ahora
                    if current_decline > max_decline:
                        max_decline = current_decline
                        worst_period = f"{months[i-worst_streak]} → {months[i]}"
                else:
                    # Reset streak si mejoró
                    current_decline = 0
                    worst_streak = 0

            if max_decline > 0:
                falling_artists.append({
                    'name': artist,
                    'decline': max_decline,
                    'period': worst_period,
                    'total_months': len(months),
                    'streak_months': worst_streak
                })

        # Ordenar por caída total y luego por duración del streak
        falling_artists.sort(key=lambda x: (x['decline'], x['streak_months']), reverse=True)
        return falling_artists[:limit]

    def get_user_individual_evolution_data(self, user: str, from_year: int, to_year: int) -> Dict:
        """Obtiene todos los datos de evolución individual del usuario con detalles mejorados"""
        cursor = self.conn.cursor()

        evolution_data = {}
        years = list(range(from_year, to_year + 1))

        # 1. Top 10 géneros por año - CON ARTISTAS QUE CONTRIBUYEN
        top_genres = self.get_user_top_genres(user, from_year, to_year, 10)
        top_genre_names = [genre for genre, _ in top_genres]

        genres_evolution = {}
        genres_details = {}
        for genre in top_genre_names:
            genres_evolution[genre] = {}
            genres_details[genre] = {}
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

                # Obtener top 5 artistas para este género en este año
                cursor.execute('''
                    SELECT s.artist, COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND ag.genres LIKE ?
                    GROUP BY s.artist
                    ORDER BY plays DESC
                    LIMIT 5
                ''', (user, str(year), f'%"{genre}"%'))
                genres_details[genre][year] = [{'name': row['artist'], 'plays': row['plays']} for row in cursor.fetchall()]

        evolution_data['genres'] = {
            'data': genres_evolution,
            'details': genres_details,
            'years': years,
            'names': top_genre_names
        }

        # 2. Top 10 sellos por año - CON ARTISTAS QUE CONTRIBUYEN
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
        labels_details = {}
        for label in top_labels:
            labels_evolution[label] = {}
            labels_details[label] = {}
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

                # Obtener top 5 artistas para este sello en este año
                cursor.execute('''
                    SELECT s.artist, COUNT(*) as plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND al.label = ?
                    GROUP BY s.artist
                    ORDER BY plays DESC
                    LIMIT 5
                ''', (user, str(year), label))
                labels_details[label][year] = [{'name': row['artist'], 'plays': row['plays']} for row in cursor.fetchall()]

        evolution_data['labels'] = {
            'data': labels_evolution,
            'details': labels_details,
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

        # 4. One hit wonders con detalles de la canción ESPECÍFICA
        one_hit_wonders = self.get_one_hit_wonders_for_user(user, from_year, to_year, 25, 10)
        one_hit_evolution = {}
        one_hit_details = {}
        for artist_data in one_hit_wonders:
            artist = artist_data['name']
            one_hit_evolution[artist] = {}
            one_hit_details[artist] = {}
            for year in years:
                cursor.execute('''
                    SELECT COUNT(*) as plays
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                one_hit_evolution[artist][year] = result['plays'] if result else 0

                # Obtener la canción única
                cursor.execute('''
                    SELECT track, COUNT(*) as plays
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    GROUP BY track
                    ORDER BY plays DESC
                    LIMIT 1
                ''', (user, artist, str(year)))
                track_result = cursor.fetchone()
                if track_result:
                    one_hit_details[artist][year] = {'track': track_result['track'], 'plays': track_result['plays']}
                else:
                    one_hit_details[artist][year] = {'track': artist_data.get('track', 'N/A'), 'plays': 0}

        evolution_data['one_hit_wonders'] = {
            'data': one_hit_evolution,
            'details': one_hit_details,
            'years': years,
            'names': [artist['name'] for artist in one_hit_wonders]
        }

        # 5. Streaks - datos en DÍAS, no scrobbles
        top_streak_artists_data = self.get_top_artists_by_streaks([user], from_year, to_year, 10).get(user, [])[:10]
        streak_evolution = {}
        streak_details = {}
        for artist_data in top_streak_artists_data:
            artist = artist_data['name']
            streak_evolution[artist] = {}
            streak_details[artist] = {}
            for year in years:
                # Calcular días únicos por año
                cursor.execute('''
                    SELECT COUNT(DISTINCT date(datetime(timestamp, 'unixepoch'))) as days_count
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                days_count = result['days_count'] if result else 0
                streak_evolution[artist][year] = days_count
                streak_details[artist][year] = {
                    'days': days_count,
                    'max_streak': artist_data.get('max_streak', 0),
                    'total_days': artist_data.get('total_days', 0)
                }

        evolution_data['streak_artists'] = {
            'data': streak_evolution,
            'details': streak_details,
            'years': years,
            'names': [artist['name'] for artist in top_streak_artists_data]
        }

        # 6. Track count - datos en número de canciones ÚNICAS, no scrobbles
        top_track_count_artists_data = self.get_top_artists_by_track_count([user], from_year, to_year, 10).get(user, [])[:10]
        track_count_evolution = {}
        track_count_details = {}
        for artist_data in top_track_count_artists_data:
            artist = artist_data['name']
            track_count_evolution[artist] = {}
            track_count_details[artist] = {}
            for year in years:
                cursor.execute('''
                    SELECT COUNT(DISTINCT track) as track_count
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                track_count = result['track_count'] if result else 0
                track_count_evolution[artist][year] = track_count

                # Obtener top 10 álbumes para este año
                cursor.execute('''
                    SELECT album, COUNT(*) as plays
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                      AND album IS NOT NULL AND album != ''
                    GROUP BY album
                    ORDER BY plays DESC
                    LIMIT 10
                ''', (user, artist, str(year)))
                albums = [{'name': row['album'], 'plays': row['plays']} for row in cursor.fetchall()]
                track_count_details[artist][year] = {'track_count': track_count, 'albums': albums}

        evolution_data['track_count_artists'] = {
            'data': track_count_evolution,
            'details': track_count_details,
            'years': years,
            'names': [artist['name'] for artist in top_track_count_artists_data]
        }

        # 7. New artists
        new_artists = self.get_new_artists_for_user(user, from_year, to_year, 10)
        new_artists_evolution = {}
        for artist_data in new_artists:
            artist = artist_data['name']
            new_artists_evolution[artist] = {}
            for year in years:
                cursor.execute('''
                    SELECT COUNT(*) as plays
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                new_artists_evolution[artist][year] = result['plays'] if result else 0

        evolution_data['new_artists'] = {
            'data': new_artists_evolution,
            'years': years,
            'names': [artist['name'] for artist in new_artists]
        }

        # 8. & 9. Rising and falling artists evolution con detalles de canciones TOP
        rising_artists = self.get_fastest_rising_artists(user, from_year, to_year, 10)
        falling_artists = self.get_fastest_falling_artists(user, from_year, to_year, 10)

        for category, artists_list in [
            ('rising_artists', rising_artists),
            ('falling_artists', falling_artists)
        ]:
            category_evolution = {}
            category_details = {}
            for artist_data in artists_list:
                artist = artist_data['name']
                category_evolution[artist] = {}
                category_details[artist] = {}
                for year in years:
                    cursor.execute('''
                        SELECT COUNT(*) as plays
                        FROM scrobbles
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    ''', (user, artist, str(year)))
                    result = cursor.fetchone()
                    category_evolution[artist][year] = result['plays'] if result else 0

                    # Obtener top 10 canciones para este año
                    cursor.execute('''
                        SELECT track, COUNT(*) as plays
                        FROM scrobbles
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                        GROUP BY track
                        ORDER BY plays DESC
                        LIMIT 10
                    ''', (user, artist, str(year)))
                    tracks = [{'name': row['track'], 'plays': row['plays']} for row in cursor.fetchall()]
                    category_details[artist][year] = tracks

            evolution_data[category] = {
                'data': category_evolution,
                'details': category_details,
                'years': years,
                'names': [artist['name'] for artist in artists_list]
            }

        return evolution_data

    def get_detailed_coincidences_for_popup(self, user: str, other_user: str, year: int, coincidence_type: str) -> List[Dict]:
        """Obtiene coincidencias detalladas para popups de evolución - MEJORADO PARA MOSTRAR COINCIDENCIAS REALES"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(year, 1, 1).timestamp())
        to_timestamp = int(datetime(year + 1, 1, 1).timestamp()) - 1

        if coincidence_type == 'artists':
            # Obtener artistas comunes con detalles
            cursor.execute('''
                SELECT s1.artist,
                       GROUP_CONCAT(DISTINCT s1.track) as tracks_user1,
                       GROUP_CONCAT(DISTINCT s1.album) as albums_user1,
                       COUNT(DISTINCT s1.track) as user1_tracks,
                       COUNT(DISTINCT s2.track) as user2_tracks,
                       COUNT(s1.artist) as user1_plays,
                       COUNT(s2.artist) as user2_plays
                FROM scrobbles s1
                JOIN scrobbles s2 ON s1.artist = s2.artist
                WHERE s1.user = ? AND s2.user = ?
                  AND s1.timestamp >= ? AND s1.timestamp <= ?
                  AND s2.timestamp >= ? AND s2.timestamp <= ?
                GROUP BY s1.artist
                ORDER BY (user1_plays + user2_plays) DESC
                LIMIT 10
            ''', (user, other_user, from_timestamp, to_timestamp, from_timestamp, to_timestamp))

            return [{'artist': row['artist'],
                    'tracks': row['tracks_user1'][:100] if row['tracks_user1'] else '',
                    'albums': row['albums_user1'][:100] if row['albums_user1'] else '',
                    'user1_plays': row['user1_plays'], 'user2_plays': row['user2_plays']}
                    for row in cursor.fetchall()]

        elif coincidence_type == 'albums':
            # Obtener álbumes comunes con canciones
            cursor.execute('''
                SELECT s1.artist,
                       s1.album,
                       GROUP_CONCAT(DISTINCT s1.track) as common_tracks,
                       COUNT(DISTINCT s1.track) as user1_tracks,
                       COUNT(DISTINCT s2.track) as user2_tracks,
                       COUNT(s1.album) as user1_plays,
                       COUNT(s2.album) as user2_plays
                FROM scrobbles s1
                JOIN scrobbles s2 ON s1.artist = s2.artist AND s1.album = s2.album
                WHERE s1.user = ? AND s2.user = ?
                  AND s1.timestamp >= ? AND s1.timestamp <= ?
                  AND s2.timestamp >= ? AND s2.timestamp <= ?
                  AND s1.album IS NOT NULL AND s1.album != ''
                GROUP BY s1.artist, s1.album
                ORDER BY (user1_plays + user2_plays) DESC
                LIMIT 10
            ''', (user, other_user, from_timestamp, to_timestamp, from_timestamp, to_timestamp))

            return [{'artist': row['artist'], 'album': row['album'],
                    'tracks': row['common_tracks'][:100] if row['common_tracks'] else '',
                    'user1_plays': row['user1_plays'], 'user2_plays': row['user2_plays']}
                    for row in cursor.fetchall()]

        elif coincidence_type == 'tracks':
            # Obtener canciones comunes
            cursor.execute('''
                SELECT s1.artist,
                       s1.track,
                       s1.album,
                       COUNT(s1.track) as user1_plays,
                       COUNT(s2.track) as user2_plays
                FROM scrobbles s1
                JOIN scrobbles s2 ON s1.artist = s2.artist AND s1.track = s2.track
                WHERE s1.user = ? AND s2.user = ?
                  AND s1.timestamp >= ? AND s1.timestamp <= ?
                  AND s2.timestamp >= ? AND s2.timestamp <= ?
                GROUP BY s1.artist, s1.track, s1.album
                ORDER BY (user1_plays + user2_plays) DESC
                LIMIT 10
            ''', (user, other_user, from_timestamp, to_timestamp, from_timestamp, to_timestamp))

            return [{'artist': row['artist'], 'track': row['track'], 'album': row['album'],
                    'user1_plays': row['user1_plays'], 'user2_plays': row['user2_plays']}
                    for row in cursor.fetchall()]

        elif coincidence_type == 'genres':
            # Obtener coincidencias de géneros con artistas y canciones comunes
            cursor.execute('''
                SELECT s1.artist,
                       GROUP_CONCAT(DISTINCT s1.track) as common_tracks,
                       GROUP_CONCAT(DISTINCT s1.album) as common_albums,
                       ag.genres,
                       COUNT(s1.artist) as user1_plays,
                       COUNT(s2.artist) as user2_plays
                FROM scrobbles s1
                JOIN scrobbles s2 ON s1.artist = s2.artist
                JOIN artist_genres ag ON s1.artist = ag.artist
                WHERE s1.user = ? AND s2.user = ?
                  AND s1.timestamp >= ? AND s1.timestamp <= ?
                  AND s2.timestamp >= ? AND s2.timestamp <= ?
                GROUP BY s1.artist, ag.genres
                ORDER BY (user1_plays + user2_plays) DESC
                LIMIT 10
            ''', (user, other_user, from_timestamp, to_timestamp, from_timestamp, to_timestamp))

            results = []
            for row in cursor.fetchall():
                try:
                    genres_list = json.loads(row['genres']) if row['genres'] else []
                    genre_str = ', '.join(genres_list[:3])
                except:
                    genre_str = 'Unknown'

                results.append({
                    'artist': row['artist'],
                    'tracks': row['common_tracks'][:100] if row['common_tracks'] else '',
                    'albums': row['common_albums'][:100] if row['common_albums'] else '',
                    'genres': genre_str,
                    'user1_plays': row['user1_plays'],
                    'user2_plays': row['user2_plays']
                })
            return results

        elif coincidence_type == 'labels':
            # Obtener coincidencias de sellos con artistas y álbumes comunes
            cursor.execute('''
                SELECT s1.artist,
                       GROUP_CONCAT(DISTINCT s1.track) as common_tracks,
                       GROUP_CONCAT(DISTINCT s1.album) as common_albums,
                       al.label,
                       COUNT(s1.artist) as user1_plays,
                       COUNT(s2.artist) as user2_plays
                FROM scrobbles s1
                JOIN scrobbles s2 ON s1.artist = s2.artist AND s1.album = s2.album
                LEFT JOIN album_labels al ON s1.artist = al.artist AND s1.album = al.album
                WHERE s1.user = ? AND s2.user = ?
                  AND s1.timestamp >= ? AND s1.timestamp <= ?
                  AND s2.timestamp >= ? AND s2.timestamp <= ?
                  AND al.label IS NOT NULL AND al.label != ''
                GROUP BY s1.artist, s1.album, al.label
                ORDER BY (user1_plays + user2_plays) DESC
                LIMIT 10
            ''', (user, other_user, from_timestamp, to_timestamp, from_timestamp, to_timestamp))

            return [{'artist': row['artist'],
                    'tracks': row['common_tracks'][:100] if row['common_tracks'] else '',
                    'albums': row['common_albums'][:100] if row['common_albums'] else '',
                    'label': row['label'], 'user1_plays': row['user1_plays'], 'user2_plays': row['user2_plays']}
                    for row in cursor.fetchall()]

        elif coincidence_type == 'release_years':
            # Obtener coincidencias de décadas con artistas y álbumes comunes
            cursor.execute('''
                SELECT s1.artist,
                       GROUP_CONCAT(DISTINCT s1.track) as common_tracks,
                       GROUP_CONCAT(DISTINCT s1.album) as common_albums,
                       ard.release_year,
                       COUNT(s1.artist) as user1_plays,
                       COUNT(s2.artist) as user2_plays
                FROM scrobbles s1
                JOIN scrobbles s2 ON s1.artist = s2.artist AND s1.album = s2.album
                LEFT JOIN album_release_dates ard ON s1.artist = ard.artist AND s1.album = ard.album
                WHERE s1.user = ? AND s2.user = ?
                  AND s1.timestamp >= ? AND s1.timestamp <= ?
                  AND s2.timestamp >= ? AND s2.timestamp <= ?
                  AND ard.release_year IS NOT NULL
                GROUP BY s1.artist, s1.album, ard.release_year
                ORDER BY (user1_plays + user2_plays) DESC
                LIMIT 10
            ''', (user, other_user, from_timestamp, to_timestamp, from_timestamp, to_timestamp))

            results = []
            for row in cursor.fetchall():
                decade = self._get_decade(row['release_year'])
                results.append({
                    'artist': row['artist'],
                    'tracks': row['common_tracks'][:100] if row['common_tracks'] else '',
                    'albums': row['common_albums'][:100] if row['common_albums'] else '',
                    'decade': decade,
                    'year': row['release_year'],
                    'user1_plays': row['user1_plays'],
                    'user2_plays': row['user2_plays']
                })
            return results

        return []

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

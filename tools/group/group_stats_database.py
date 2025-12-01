#!/usr/bin/env python3
"""
GroupStatsDatabase - Base de datos para estadÃƒÆ’Ã‚Â­sticas grupales
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class GroupStatsDatabase:
    """Base de datos para estadÃƒÆ’Ã‚Â­sticas grupales con optimizaciones y caching"""

    def __init__(self, db_path='db/lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_group_stats_table()

    def _create_group_stats_table(self):
        """Crear tabla para almacenar estadÃƒÆ’Ã‚Â­sticas grupales pre-calculadas"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS group_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_type TEXT NOT NULL,
                stat_key TEXT NOT NULL,
                from_year INTEGER NOT NULL,
                to_year INTEGER NOT NULL,
                user_count INTEGER DEFAULT 0,
                total_scrobbles INTEGER DEFAULT 0,
                shared_by_users TEXT,
                data_json TEXT,
                created_at INTEGER NOT NULL,
                UNIQUE(stat_type, stat_key, from_year, to_year)
            )
        ''')
        self.conn.commit()

    def _get_mbid_filter(self, mbid_only: bool, table_alias: str = 's') -> str:
        """Genera filtro MBID segÃƒÆ’Ã‚Âºn los parÃƒÆ’Ã‚Â¡metros"""
        if not mbid_only:
            return ""
        return f"""AND (
            ({table_alias}.artist_mbid IS NOT NULL AND {table_alias}.artist_mbid != '') OR
            ({table_alias}.album_mbid IS NOT NULL AND {table_alias}.album_mbid != '') OR
            ({table_alias}.track_mbid IS NOT NULL AND {table_alias}.track_mbid != '')
        )"""

    def get_top_artists_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                      limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """
        Top artistas ordenados por:
        1. NÃƒÆ’Ã‚Âºmero de usuarios que lo escuchan (prioridad)
        2. Total de scrobbles (desempate)
        """
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT artist, user, COUNT(*) as plays
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist, user
        ''', users + [from_timestamp, to_timestamp])

        # Procesar por artista con user_plays
        artist_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            artist = row['artist']
            user = row['user']
            plays = row['plays']
            artist_stats[artist]['users'].add(user)
            artist_stats[artist]['total_scrobbles'] += plays
            artist_stats[artist]['user_plays'][user] += plays

        # Filtrar y ordenar
        result = []
        max_users = len(users)

        for artist, stats in artist_stats.items():
            if len(stats['users']) >= 2:  # Solo artistas compartidos
                result.append({
                    'name': artist,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        # Ordenar: primero por usuarios compartidos (desc), luego por scrobbles (desc)
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_albums_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                     limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top ÃƒÆ’Ã‚Â¡lbumes por usuarios compartidos y scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT (artist || ' - ' || album) as album_name,
                   artist,
                   album,
                   user,
                   COUNT(*) as plays
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND timestamp >= ? AND timestamp <= ?
              AND album IS NOT NULL AND album != ''
            {mbid_filter}
            GROUP BY artist, album, user
        ''', users + [from_timestamp, to_timestamp])

        # Procesar por ÃƒÆ’Ã‚Â¡lbum con user_plays
        album_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int), 'artist': '', 'album': ''})

        for row in cursor.fetchall():
            album_key = row['album_name']
            user = row['user']
            plays = row['plays']
            album_stats[album_key]['users'].add(user)
            album_stats[album_key]['total_scrobbles'] += plays
            album_stats[album_key]['user_plays'][user] += plays
            album_stats[album_key]['artist'] = row['artist']
            album_stats[album_key]['album'] = row['album']

        # Filtrar y ordenar
        result = []
        for album_name, stats in album_stats.items():
            if len(stats['users']) >= 2:  # Solo ÃƒÆ’Ã‚Â¡lbumes compartidos
                result.append({
                    'name': album_name,
                    'artist': stats['artist'],
                    'album': stats['album'],
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        # Ordenar: primero por usuarios compartidos (desc), luego por scrobbles (desc)
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_tracks_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                     limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top canciones por usuarios compartidos y scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT (artist || ' - ' || track) as track_name,
                   artist,
                   track,
                   user,
                   COUNT(*) as plays
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist, track, user
        ''', users + [from_timestamp, to_timestamp])

        # Procesar por canciÃƒÆ’Ã‚Â³n con user_plays
        track_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int), 'artist': '', 'track': ''})

        for row in cursor.fetchall():
            track_key = row['track_name']
            user = row['user']
            plays = row['plays']
            track_stats[track_key]['users'].add(user)
            track_stats[track_key]['total_scrobbles'] += plays
            track_stats[track_key]['user_plays'][user] += plays
            track_stats[track_key]['artist'] = row['artist']
            track_stats[track_key]['track'] = row['track']

        # Filtrar y ordenar
        result = []
        for track_name, stats in track_stats.items():
            if len(stats['users']) >= 2:  # Solo canciones compartidas
                result.append({
                    'name': track_name,
                    'artist': stats['artist'],
                    'track': stats['track'],
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        # Ordenar: primero por usuarios compartidos (desc), luego por scrobbles (desc)
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_genres_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                     limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top gÃƒÆ’Ã‚Â©neros por usuarios compartidos y scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT ag.genres, user, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
            {mbid_filter}
            GROUP BY ag.genres, user
        ''', users + [from_timestamp, to_timestamp])

        # Procesar gÃƒÆ’Ã‚Â©neros JSON
        genre_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            try:
                genres_list = json.loads(row['genres']) if row['genres'] else []
                for genre in genres_list[:3]:  # Solo primeros 3 gÃƒÆ’Ã‚Â©neros por artista
                    genre_stats[genre]['users'].add(row['user'])
                    genre_stats[genre]['total_scrobbles'] += row['plays']
                    genre_stats[genre]['user_plays'][row['user']] += row['plays']
            except json.JSONDecodeError:
                continue

        # Filtrar y ordenar
        result = []
        for genre, stats in genre_stats.items():
            if len(stats['users']) >= 2:  # Solo gÃƒÆ’Ã‚Â©neros compartidos
                result.append({
                    'name': genre,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        # Ordenar: primero por usuarios compartidos (desc), luego por scrobbles (desc)
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_labels_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                     limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top sellos por usuarios compartidos y scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT al.label, s.user, COUNT(*) as plays
            FROM scrobbles s
            JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            {mbid_filter}
            GROUP BY al.label, s.user
        ''', users + [from_timestamp, to_timestamp])

        # Procesar por sello con user_plays
        label_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            label = row['label']
            user = row['user']
            plays = row['plays']
            label_stats[label]['users'].add(user)
            label_stats[label]['total_scrobbles'] += plays
            label_stats[label]['user_plays'][user] += plays

        # Filtrar y ordenar
        result = []
        for label, stats in label_stats.items():
            if len(stats['users']) >= 2:  # Solo sellos compartidos
                result.append({
                    'name': label,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        # Ordenar: primero por usuarios compartidos (desc), luego por scrobbles (desc)
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_release_years_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                            limit: int = 15, mbid_only: bool = False, use_decades: bool = True) -> List[Dict]:
        """Top aÃƒÆ’Ã‚Â±os/dÃƒÆ’Ã‚Â©cadas de lanzamiento por usuarios compartidos y scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT ard.release_year, user, COUNT(*) as plays
            FROM scrobbles s
            JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND ard.release_year IS NOT NULL
            {mbid_filter}
            GROUP BY ard.release_year, user
        ''', users + [from_timestamp, to_timestamp])

        if use_decades:
            # Procesar por dÃƒÆ’Ã‚Â©cadas
            period_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

            for row in cursor.fetchall():
                decade = self._get_decade(row['release_year'])
                period_stats[decade]['users'].add(row['user'])
                period_stats[decade]['total_scrobbles'] += row['plays']
                period_stats[decade]['user_plays'][row['user']] += row['plays']
        else:
            # Procesar por aÃƒÆ’Ã‚Â±os individuales
            period_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

            for row in cursor.fetchall():
                year = str(row['release_year'])
                period_stats[year]['users'].add(row['user'])
                period_stats[year]['total_scrobbles'] += row['plays']
                period_stats[year]['user_plays'][row['user']] += row['plays']

        # Filtrar y ordenar por usuarios compartidos primero, luego por scrobbles
        result = []
        max_users = len(users)

        for period, stats in period_stats.items():
            if len(stats['users']) >= 2:  # Solo perÃƒÆ’Ã‚Â­odos compartidos
                result.append({
                    'name': period,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        # Ordenar: primero por usuarios compartidos (desc), luego por scrobbles (desc)
        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_release_decades_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                              limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top dÃƒÆ’Ã‚Â©cadas de lanzamiento por usuarios compartidos"""
        return self.get_top_release_years_by_shared_users(users, from_year, to_year, limit, mbid_only, use_decades=True)

    def get_top_individual_years_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                                limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top aÃƒÆ’Ã‚Â±os individuales de lanzamiento por usuarios compartidos"""
        return self.get_top_release_years_by_shared_users(users, from_year, to_year, limit, mbid_only, use_decades=False)

    def get_top_by_total_scrobbles(self, users: List[str], from_year: int, to_year: int,
                                 limit: int = 15, mbid_only: bool = False) -> Dict[str, List[Dict]]:
        """
        Top 15 de todo (artistas, ÃƒÆ’Ã‚Â¡lbumes, canciones) ordenado solo por scrobbles totales
        """
        results = {
            'artists': self.get_top_artists_by_scrobbles_only(users, from_year, to_year, limit, mbid_only),
            'albums': self.get_top_albums_by_scrobbles_only(users, from_year, to_year, limit, mbid_only),
            'tracks': self.get_top_tracks_by_scrobbles_only(users, from_year, to_year, limit, mbid_only),
            'genres': self.get_top_genres_by_scrobbles_only(users, from_year, to_year, limit, mbid_only),
            'labels': self.get_top_labels_by_scrobbles_only(users, from_year, to_year, limit, mbid_only),
            'release_years': self.get_top_release_years_by_scrobbles_only(users, from_year, to_year, limit, mbid_only)
        }
        return results

    def get_top_artists_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                        limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top artistas solo por scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT artist,
                   COUNT(DISTINCT user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT user) as shared_users
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
            ORDER BY total_scrobbles DESC
            LIMIT ?
        ''', users + [from_timestamp, to_timestamp, limit])

        return [
            {
                'name': row['artist'],
                'user_count': row['user_count'],
                'total_scrobbles': row['total_scrobbles'],
                'shared_users': row['shared_users'].split(',') if row['shared_users'] else []
            }
            for row in cursor.fetchall()
        ]

    def get_top_albums_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top ÃƒÆ’Ã‚Â¡lbumes solo por scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT (artist || ' - ' || album) as album_name,
                   artist,
                   album,
                   COUNT(DISTINCT user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT user) as shared_users
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND timestamp >= ? AND timestamp <= ?
              AND album IS NOT NULL AND album != ''
            {mbid_filter}
            GROUP BY artist, album
            ORDER BY total_scrobbles DESC
            LIMIT ?
        ''', users + [from_timestamp, to_timestamp, limit])

        return [
            {
                'name': row['album_name'],
                'artist': row['artist'],
                'album': row['album'],
                'user_count': row['user_count'],
                'total_scrobbles': row['total_scrobbles'],
                'shared_users': row['shared_users'].split(',') if row['shared_users'] else []
            }
            for row in cursor.fetchall()
        ]

    def get_top_tracks_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top canciones solo por scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT (artist || ' - ' || track) as track_name,
                   artist,
                   track,
                   COUNT(DISTINCT user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT user) as shared_users
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist, track
            ORDER BY total_scrobbles DESC
            LIMIT ?
        ''', users + [from_timestamp, to_timestamp, limit])

        return [
            {
                'name': row['track_name'],
                'artist': row['artist'],
                'track': row['track'],
                'user_count': row['user_count'],
                'total_scrobbles': row['total_scrobbles'],
                'shared_users': row['shared_users'].split(',') if row['shared_users'] else []
            }
            for row in cursor.fetchall()
        ]

    def get_top_genres_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top gÃƒÆ’Ã‚Â©neros solo por scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT ag.genres, user, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
            {mbid_filter}
            GROUP BY ag.genres, user
        ''', users + [from_timestamp, to_timestamp])

        # Procesar gÃƒÆ’Ã‚Â©neros JSON
        genre_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0})

        for row in cursor.fetchall():
            try:
                genres_list = json.loads(row['genres']) if row['genres'] else []
                for genre in genres_list[:3]:
                    genre_stats[genre]['users'].add(row['user'])
                    genre_stats[genre]['total_scrobbles'] += row['plays']
            except json.JSONDecodeError:
                continue

        # Convertir y ordenar solo por scrobbles
        result = []
        for genre, stats in genre_stats.items():
            result.append({
                'name': genre,
                'user_count': len(stats['users']),
                'total_scrobbles': stats['total_scrobbles'],
                'shared_users': list(stats['users'])
            })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def get_top_labels_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                       limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top sellos solo por scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT al.label,
                   COUNT(DISTINCT s.user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT s.user) as shared_users
            FROM scrobbles s
            JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            {mbid_filter}
            GROUP BY al.label
            ORDER BY total_scrobbles DESC
            LIMIT ?
        ''', users + [from_timestamp, to_timestamp, limit])

        return [
            {
                'name': row['label'],
                'user_count': row['user_count'],
                'total_scrobbles': row['total_scrobbles'],
                'shared_users': row['shared_users'].split(',') if row['shared_users'] else []
            }
            for row in cursor.fetchall()
        ]

    def get_top_release_years_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                              limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top dÃƒÆ’Ã‚Â©cadas solo por scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT ard.release_year, user, COUNT(*) as plays
            FROM scrobbles s
            JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND ard.release_year IS NOT NULL
            {mbid_filter}
            GROUP BY ard.release_year, user
        ''', users + [from_timestamp, to_timestamp])

        decade_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0})

        for row in cursor.fetchall():
            decade = self._get_decade(row['release_year'])
            decade_stats[decade]['users'].add(row['user'])
            decade_stats[decade]['total_scrobbles'] += row['plays']

        result = []
        for decade, stats in decade_stats.items():
            result.append({
                'name': decade,
                'user_count': len(stats['users']),
                'total_scrobbles': stats['total_scrobbles'],
                'shared_users': list(stats['users'])
            })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def get_top_individual_release_years_by_scrobbles_only(self, users: List[str], from_year: int, to_year: int,
                                                         limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top aÃ±os individuales de lanzamiento solo por scrobbles totales"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT ard.release_year, user, COUNT(*) as plays
            FROM scrobbles s
            JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND ard.release_year IS NOT NULL
            {mbid_filter}
            GROUP BY ard.release_year, user
        ''', users + [from_timestamp, to_timestamp])

        year_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0})

        for row in cursor.fetchall():
            year = str(row['release_year'])
            year_stats[year]['users'].add(row['user'])
            year_stats[year]['total_scrobbles'] += row['plays']

        result = []
        for year, stats in year_stats.items():
            result.append({
                'name': year,
                'user_count': len(stats['users']),
                'total_scrobbles': stats['total_scrobbles'],
                'shared_users': list(stats['users'])
            })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def get_evolution_data(self, users: List[str], from_year: int, to_year: int,
                         mbid_only: bool = False) -> Dict:
        """Obtiene datos de evoluciÃƒÆ’Ã‚Â³n temporal para grÃƒÆ’Ã‚Â¡ficos lineales"""
        years = list(range(from_year, to_year + 1))

        evolution = {
            'artists': {},
            'albums': {},
            'tracks': {},
            'genres': {},
            'labels': {},
            'release_years': {},
            'years': years
        }

        # Recopilar todos los elementos ÃƒÂºnicos por categorÃƒÂ­a primero
        all_items = {
            'artists': set(),
            'albums': set(),
            'tracks': set(),
            'genres': set(),
            'labels': set(),
            'release_years': set()
        }

        # Para cada aÃƒÂ±o, obtener tops y recopilar elementos ÃƒÂºnicos
        for year in years:
            # Artistas
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_artists:
                all_items['artists'].add(item['name'])

            # ÃƒÂlbumes
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_albums:
                all_items['albums'].add(item['name'])

            # Canciones
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_tracks:
                all_items['tracks'].add(item['name'])

            # GÃƒÂ©neros
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_genres:
                all_items['genres'].add(item['name'])

            # Sellos
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_labels:
                all_items['labels'].add(item['name'])

            # AÃƒÂ±os de lanzamiento
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_years:
                all_items['release_years'].add(item['name'])

        # Inicializar estructura completa para todos los elementos
        for category in ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']:
            for item_name in all_items[category]:
                evolution[category][item_name] = {y: {'total': 0, 'users': {}} for y in years}

        # Ahora llenar con datos reales aÃƒÂ±o por aÃƒÂ±o
        for year in years:
            # Procesar artistas para este aÃƒÂ±o
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_artists:
                if item['name'] in evolution['artists']:
                    evolution['artists'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_artist(users, item['name'], year, year, mbid_only)
                    evolution['artists'][item['name']][year]['users'] = user_details

            # Procesar ÃƒÂ¡lbumes para este aÃƒÂ±o
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_albums:
                if item['name'] in evolution['albums']:
                    evolution['albums'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_album(users, item['artist'], item['album'], year, year, mbid_only)
                    evolution['albums'][item['name']][year]['users'] = user_details

            # Procesar canciones para este aÃƒÂ±o
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_tracks:
                if item['name'] in evolution['tracks']:
                    evolution['tracks'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_track(users, item['artist'], item['track'], year, year, mbid_only)
                    evolution['tracks'][item['name']][year]['users'] = user_details

            # Procesar gÃƒÂ©neros para este aÃƒÂ±o
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_genres:
                if item['name'] in evolution['genres']:
                    evolution['genres'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_genre(users, item['name'], year, year, mbid_only)
                    evolution['genres'][item['name']][year]['users'] = user_details

            # Procesar sellos para este aÃƒÂ±o
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_labels:
                if item['name'] in evolution['labels']:
                    evolution['labels'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_label(users, item['name'], year, year, mbid_only)
                    evolution['labels'][item['name']][year]['users'] = user_details

            # Procesar aÃƒÂ±os de lanzamiento para este aÃƒÂ±o
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_years:
                if item['name'] in evolution['release_years']:
                    evolution['release_years'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_release_year(users, item['name'], year, year, mbid_only)
                    evolution['release_years'][item['name']][year]['users'] = user_details

        # Reducir a top 15 por categorÃƒÂ­a para visualizaciÃƒÂ³n
        for category in ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']:
            # Calcular total por elemento
            totals = {}
            for item, year_data in evolution[category].items():
                totals[item] = sum(year_data[y]['total'] for y in years)

            # Quedarse con top 15
            top_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:15]
            evolution[category] = {item: evolution[category][item] for item, _ in top_items}

        return evolution

    def get_total_shared_counts(self, users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, int]:
        """Obtiene el nÃƒÆ’Ã‚Âºmero total real de elementos compartidos por TODOS los usuarios"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        results = {}

        # Total artistas compartidos por TODOS los usuarios
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM (
                SELECT artist
                FROM scrobbles s
                WHERE user IN ({','.join(['?'] * len(users))})
                  AND timestamp >= ? AND timestamp <= ?
                {mbid_filter}
                GROUP BY artist
                HAVING COUNT(DISTINCT user) = ?
            )
        ''', users + [from_timestamp, to_timestamp, len(users)])

        result = cursor.fetchone()
        results['shared_artists'] = result['count'] if result else 0

        # Total ÃƒÂ¡lbumes compartidos por TODOS los usuarios
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM (
                SELECT artist, album
                FROM scrobbles s
                WHERE user IN ({','.join(['?'] * len(users))})
                  AND timestamp >= ? AND timestamp <= ?
                  AND album IS NOT NULL AND album != ''
                {mbid_filter}
                GROUP BY artist, album
                HAVING COUNT(DISTINCT user) = ?
            )
        ''', users + [from_timestamp, to_timestamp, len(users)])

        result = cursor.fetchone()
        results['shared_albums'] = result['count'] if result else 0

        # Total canciones compartidas por TODOS los usuarios
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM (
                SELECT artist, track
                FROM scrobbles s
                WHERE user IN ({','.join(['?'] * len(users))})
                  AND timestamp >= ? AND timestamp <= ?
                {mbid_filter}
                GROUP BY artist, track
                HAVING COUNT(DISTINCT user) = ?
            )
        ''', users + [from_timestamp, to_timestamp, len(users)])

        result = cursor.fetchone()
        results['shared_tracks'] = result['count'] if result else 0

        # Total gÃƒÂ©neros compartidos por TODOS los usuarios
        cursor.execute(f'''
            SELECT ag.genres, COUNT(DISTINCT s.user) as user_count
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
            {mbid_filter}
            GROUP BY ag.genres
            HAVING user_count = ?
        ''', users + [from_timestamp, to_timestamp, len(users)])

        genre_count = 0
        for row in cursor.fetchall():
            try:
                genres_list = json.loads(row['genres']) if row['genres'] else []
                genre_count += len(genres_list[:3])  # Contar hasta 3 gÃƒÂ©neros por artista
            except json.JSONDecodeError:
                continue
        results['shared_genres'] = genre_count

        # Total sellos compartidos por TODOS los usuarios
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM (
                SELECT al.label
                FROM scrobbles s
                JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                WHERE s.user IN ({','.join(['?'] * len(users))})
                  AND s.timestamp >= ? AND s.timestamp <= ?
                  AND al.label IS NOT NULL AND al.label != ''
                {mbid_filter}
                GROUP BY al.label
                HAVING COUNT(DISTINCT s.user) = ?
            )
        ''', users + [from_timestamp, to_timestamp, len(users)])

        result = cursor.fetchone()
        results['shared_labels'] = result['count'] if result else 0

        # Total aÃƒÂ±os de lanzamiento compartidos por TODOS los usuarios
        cursor.execute(f'''
            SELECT ard.release_year, COUNT(DISTINCT s.user) as user_count
            FROM scrobbles s
            JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND ard.release_year IS NOT NULL
            {mbid_filter}
            GROUP BY ard.release_year
            HAVING user_count = ?
        ''', users + [from_timestamp, to_timestamp, len(users)])

        decade_count = set()
        for row in cursor.fetchall():
            decade = self._get_decade(row['release_year'])
            decade_count.add(decade)
        results['shared_release_years'] = len(decade_count)

        return results

    def get_top_artists_for_genre(self, genre: str, users: List[str], from_year: int, to_year: int,
                                 limit: int = 5, mbid_only: bool = False) -> List[Dict]:
        """Obtiene top artistas que mÃƒÆ’Ã‚Â¡s contribuyen a un gÃƒÆ’Ã‚Â©nero especÃƒÆ’Ã‚Â­fico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT s.artist,
                   COUNT(DISTINCT s.user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT s.user) as shared_users
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND ag.genres LIKE ?
            {mbid_filter}
            GROUP BY s.artist
            HAVING user_count >= 2
            ORDER BY user_count DESC, total_scrobbles DESC
            LIMIT ?
        ''', users + [from_timestamp, to_timestamp, f'%"{genre}"%', limit])

        return [
            {
                'name': row['artist'],
                'user_count': row['user_count'],
                'total_scrobbles': row['total_scrobbles'],
                'shared_users': row['shared_users'].split(',') if row['shared_users'] else []
            }
            for row in cursor.fetchall()
        ]

    def get_top_albums_for_label(self, label: str, users: List[str], from_year: int, to_year: int,
                                limit: int = 5, mbid_only: bool = False) -> List[Dict]:
        """Obtiene top ÃƒÆ’Ã‚Â¡lbumes que mÃƒÆ’Ã‚Â¡s contribuyen a un sello especÃƒÆ’Ã‚Â­fico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT (s.artist || ' - ' || s.album) as album_name,
                   s.artist,
                   s.album,
                   COUNT(DISTINCT s.user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT s.user) as shared_users
            FROM scrobbles s
            JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label = ?
              AND s.album IS NOT NULL AND s.album != ''
            {mbid_filter}
            GROUP BY s.artist, s.album
            HAVING user_count >= 2
            ORDER BY user_count DESC, total_scrobbles DESC
            LIMIT ?
        ''', users + [from_timestamp, to_timestamp, label, limit])

        return [
            {
                'name': row['album_name'],
                'artist': row['artist'],
                'album': row['album'],
                'user_count': row['user_count'],
                'total_scrobbles': row['total_scrobbles'],
                'shared_users': row['shared_users'].split(',') if row['shared_users'] else []
            }
            for row in cursor.fetchall()
        ]

    def get_top_artists_for_period(self, period: str, users: List[str], from_year: int, to_year: int,
                                  limit: int = 5, mbid_only: bool = False, use_decades: bool = True) -> List[Dict]:
        """Obtiene top artistas que mÃƒÆ’Ã‚Â¡s contribuyen a un perÃƒÆ’Ã‚Â­odo especÃƒÆ’Ã‚Â­fico (dÃƒÆ’Ã‚Â©cada o aÃƒÆ’Ã‚Â±o)"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        if use_decades:
            # Convertir dÃƒÆ’Ã‚Â©cada a rango de aÃƒÆ’Ã‚Â±os
            if period == "Antes de 1950":
                year_condition = "ard.release_year < 1950"
            elif period == "2020s+":
                year_condition = "ard.release_year >= 2020"
            else:
                decade_start = int(period.replace('s', ''))
                decade_end = decade_start + 9
                year_condition = f"ard.release_year BETWEEN {decade_start} AND {decade_end}"
        else:
            # AÃƒÆ’Ã‚Â±o individual
            year_condition = f"ard.release_year = {int(period)}"

        cursor.execute(f'''
            SELECT s.artist,
                   COUNT(DISTINCT s.user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT s.user) as shared_users
            FROM scrobbles s
            JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND {year_condition}
            {mbid_filter}
            GROUP BY s.artist
            HAVING user_count >= 2
            ORDER BY user_count DESC, total_scrobbles DESC
            LIMIT ?
        ''', users + [from_timestamp, to_timestamp, limit])

        return [
            {
                'name': row['artist'],
                'user_count': row['user_count'],
                'total_scrobbles': row['total_scrobbles'],
                'shared_users': row['shared_users'].split(',') if row['shared_users'] else []
            }
            for row in cursor.fetchall()
        ]


    def _get_user_breakdown_for_artist(self, users: List[str], artist: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, int]:
        """Obtiene el desglose de scrobbles por usuario para un artista especÃƒÂ­fico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT user, COUNT(*) as plays
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND artist = ?
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY user
        ''', users + [artist, from_timestamp, to_timestamp])

        return {row['user']: row['plays'] for row in cursor.fetchall()}

    def _get_user_breakdown_for_album(self, users: List[str], artist: str, album: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, int]:
        """Obtiene el desglose de scrobbles por usuario para un ÃƒÂ¡lbum especÃƒÂ­fico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT user, COUNT(*) as plays
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND artist = ? AND album = ?
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY user
        ''', users + [artist, album, from_timestamp, to_timestamp])

        return {row['user']: row['plays'] for row in cursor.fetchall()}

    def _get_user_breakdown_for_track(self, users: List[str], artist: str, track: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, int]:
        """Obtiene el desglose de scrobbles por usuario para una canciÃƒÂ³n especÃƒÂ­fica"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT user, COUNT(*) as plays
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND artist = ? AND track = ?
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY user
        ''', users + [artist, track, from_timestamp, to_timestamp])

        return {row['user']: row['plays'] for row in cursor.fetchall()}

    def _get_user_breakdown_for_genre(self, users: List[str], genre: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, int]:
        """Obtiene el desglose de scrobbles por usuario para un gÃƒÂ©nero especÃƒÂ­fico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT s.user, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND ag.genres LIKE ?
            {mbid_filter}
            GROUP BY s.user
        ''', users + [from_timestamp, to_timestamp, f'%"{genre}"%'])

        return {row['user']: row['plays'] for row in cursor.fetchall()}

    def _get_user_breakdown_for_label(self, users: List[str], label: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, int]:
        """Obtiene el desglose de scrobbles por usuario para un sello especÃƒÂ­fico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT s.user, COUNT(*) as plays
            FROM scrobbles s
            JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label = ?
            {mbid_filter}
            GROUP BY s.user
        ''', users + [from_timestamp, to_timestamp, label])

        return {row['user']: row['plays'] for row in cursor.fetchall()}

    def _get_user_breakdown_for_release_year(self, users: List[str], period: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, int]:
        """Obtiene el desglose de scrobbles por usuario para un perÃƒÂ­odo de lanzamiento especÃƒÂ­fico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        # Convertir perÃƒÂ­odo a condiciÃƒÂ³n de aÃƒÂ±o
        if period == "Antes de 1950":
            year_condition = "ard.release_year < 1950"
        elif period == "2020s+":
            year_condition = "ard.release_year >= 2020"
        else:
            decade_start = int(period.replace('s', ''))
            decade_end = decade_start + 9
            year_condition = f"ard.release_year BETWEEN {decade_start} AND {decade_end}"

        cursor.execute(f'''
            SELECT s.user, COUNT(*) as plays
            FROM scrobbles s
            JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
              AND {year_condition}
            {mbid_filter}
            GROUP BY s.user
        ''', users + [from_timestamp, to_timestamp])

        return {row['user']: row['plays'] for row in cursor.fetchall()}



    def get_evolution_scatter_data(self, users: List[str], from_year: int, to_year: int,
                                mbid_only: bool = False) -> Dict:
        """Obtiene datos de evolución temporal para gráficos scatter (top 5 por año)"""
        years = list(range(from_year, to_year + 1))

        evolution_scatter = {
            'artists': {},
            'albums': {},
            'tracks': {},
            'genres': {},
            'labels': {},
            'release_years': {},
            'years': years
        }

        # Para cada año, obtener el top 5 de ese año específico
        for year in years:
            # Top 5 artistas del año
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 5, mbid_only)
            evolution_scatter['artists'][year] = []
            for idx, item in enumerate(top_artists):
                evolution_scatter['artists'][year].append({
                    'name': item['name'],
                    'scrobbles': item['total_scrobbles'],
                    'users': item['shared_users'],
                    'position': idx + 1
                })

            # Top 5 álbumes del año
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 5, mbid_only)
            evolution_scatter['albums'][year] = []
            for idx, item in enumerate(top_albums):
                evolution_scatter['albums'][year].append({
                    'name': item['name'],
                    'scrobbles': item['total_scrobbles'],
                    'users': item['shared_users'],
                    'position': idx + 1,
                    'artist': item.get('artist', ''),
                    'album': item.get('album', '')
                })

            # Top 5 canciones del año
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 5, mbid_only)
            evolution_scatter['tracks'][year] = []
            for idx, item in enumerate(top_tracks):
                evolution_scatter['tracks'][year].append({
                    'name': item['name'],
                    'scrobbles': item['total_scrobbles'],
                    'users': item['shared_users'],
                    'position': idx + 1,
                    'artist': item.get('artist', ''),
                    'track': item.get('track', '')
                })

            # Top 5 géneros del año
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 5, mbid_only)
            evolution_scatter['genres'][year] = []
            for idx, item in enumerate(top_genres):
                evolution_scatter['genres'][year].append({
                    'name': item['name'],
                    'scrobbles': item['total_scrobbles'],
                    'users': item['shared_users'],
                    'position': idx + 1
                })

            # Top 5 sellos del año
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 5, mbid_only)
            evolution_scatter['labels'][year] = []
            for idx, item in enumerate(top_labels):
                evolution_scatter['labels'][year].append({
                    'name': item['name'],
                    'scrobbles': item['total_scrobbles'],
                    'users': item['shared_users'],
                    'position': idx + 1
                })

            # Top 5 años de lanzamiento del año
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 5, mbid_only)
            evolution_scatter['release_years'][year] = []
            for idx, item in enumerate(top_years):
                evolution_scatter['release_years'][year].append({
                    'name': item['name'],
                    'scrobbles': item['total_scrobbles'],
                    'users': item['shared_users'],
                    'position': idx + 1
                })

        return evolution_scatter

    def _get_decade(self, year: int) -> str:
        """Convierte un aÃƒÆ’Ã‚Â±o a etiqueta de dÃƒÆ’Ã‚Â©cada"""
        if year < 1950:
            return "Antes de 1950"
        elif year >= 2020:
            return "2020s+"
        else:
            decade_start = (year // 10) * 10
            return f"{decade_start}s"

    def close(self):
        """Cerrar conexiÃƒÆ’Ã‚Â³n a la base de datos"""
        self.conn.close()

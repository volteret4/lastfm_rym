#!/usr/bin/env python3
"""
GroupStatsDatabase - Base de datos para estadÃ­sticas grupales
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class GroupStatsDatabase:
    """Base de datos para estadÃ­sticas grupales con optimizaciones y caching"""

    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_group_stats_table()

    def _create_group_stats_table(self):
        """Crear tabla para almacenar estadÃ­sticas grupales pre-calculadas"""
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
        """Genera filtro MBID segÃºn los parÃ¡metros"""
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
        1. NÃºmero de usuarios que lo escuchan (prioridad)
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
        """Top Ã¡lbumes por usuarios compartidos y scrobbles totales"""
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

        # Procesar por Ã¡lbum con user_plays
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
            if len(stats['users']) >= 2:  # Solo Ã¡lbumes compartidos
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

        # Procesar por canciÃ³n con user_plays
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
        """Top gÃ©neros por usuarios compartidos y scrobbles totales"""
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

        # Procesar gÃ©neros JSON
        genre_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            try:
                genres_list = json.loads(row['genres']) if row['genres'] else []
                for genre in genres_list[:3]:  # Solo primeros 3 gÃ©neros por artista
                    genre_stats[genre]['users'].add(row['user'])
                    genre_stats[genre]['total_scrobbles'] += row['plays']
                    genre_stats[genre]['user_plays'][row['user']] += row['plays']
            except json.JSONDecodeError:
                continue

        # Filtrar y ordenar
        result = []
        for genre, stats in genre_stats.items():
            if len(stats['users']) >= 2:  # Solo gÃ©neros compartidos
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
        """Top aÃ±os/dÃ©cadas de lanzamiento por usuarios compartidos y scrobbles totales"""
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
            # Procesar por dÃ©cadas
            period_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

            for row in cursor.fetchall():
                decade = self._get_decade(row['release_year'])
                period_stats[decade]['users'].add(row['user'])
                period_stats[decade]['total_scrobbles'] += row['plays']
                period_stats[decade]['user_plays'][row['user']] += row['plays']
        else:
            # Procesar por aÃ±os individuales
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
            if len(stats['users']) >= 2:  # Solo perÃ­odos compartidos
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
        """Top dÃ©cadas de lanzamiento por usuarios compartidos"""
        return self.get_top_release_years_by_shared_users(users, from_year, to_year, limit, mbid_only, use_decades=True)

    def get_top_individual_years_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                                limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top aÃ±os individuales de lanzamiento por usuarios compartidos"""
        return self.get_top_release_years_by_shared_users(users, from_year, to_year, limit, mbid_only, use_decades=False)

    def get_top_by_total_scrobbles(self, users: List[str], from_year: int, to_year: int,
                                 limit: int = 15, mbid_only: bool = False) -> Dict[str, List[Dict]]:
        """
        Top 15 de todo (artistas, Ã¡lbumes, canciones) ordenado solo por scrobbles totales
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
        """Top Ã¡lbumes solo por scrobbles totales"""
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
        """Top gÃ©neros solo por scrobbles totales"""
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

        # Procesar gÃ©neros JSON
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
        """Top dÃ©cadas solo por scrobbles totales"""
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

    def get_evolution_data(self, users: List[str], from_year: int, to_year: int,
                         mbid_only: bool = False) -> Dict:
        """Obtiene datos de evoluciÃ³n temporal para grÃ¡ficos lineales"""
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

        # Recopilar todos los elementos únicos por categoría primero
        all_items = {
            'artists': set(),
            'albums': set(),
            'tracks': set(),
            'genres': set(),
            'labels': set(),
            'release_years': set()
        }

        # Para cada año, obtener tops y recopilar elementos únicos
        for year in years:
            # Artistas
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_artists:
                all_items['artists'].add(item['name'])

            # Álbumes
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_albums:
                all_items['albums'].add(item['name'])

            # Canciones
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_tracks:
                all_items['tracks'].add(item['name'])

            # Géneros
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_genres:
                all_items['genres'].add(item['name'])

            # Sellos
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_labels:
                all_items['labels'].add(item['name'])

            # Años de lanzamiento
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_years:
                all_items['release_years'].add(item['name'])

        # Inicializar estructura completa para todos los elementos
        for category in ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']:
            for item_name in all_items[category]:
                evolution[category][item_name] = {y: {'total': 0, 'users': {}} for y in years}

        # Ahora llenar con datos reales año por año
        for year in years:
            # Procesar artistas para este año
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_artists:
                if item['name'] in evolution['artists']:
                    evolution['artists'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_artist(users, item['name'], year, year, mbid_only)
                    evolution['artists'][item['name']][year]['users'] = user_details

            # Procesar álbumes para este año
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_albums:
                if item['name'] in evolution['albums']:
                    evolution['albums'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_album(users, item['artist'], item['album'], year, year, mbid_only)
                    evolution['albums'][item['name']][year]['users'] = user_details

            # Procesar canciones para este año
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_tracks:
                if item['name'] in evolution['tracks']:
                    evolution['tracks'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_track(users, item['artist'], item['track'], year, year, mbid_only)
                    evolution['tracks'][item['name']][year]['users'] = user_details

            # Procesar géneros para este año
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_genres:
                if item['name'] in evolution['genres']:
                    evolution['genres'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_genre(users, item['name'], year, year, mbid_only)
                    evolution['genres'][item['name']][year]['users'] = user_details

            # Procesar sellos para este año
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_labels:
                if item['name'] in evolution['labels']:
                    evolution['labels'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_label(users, item['name'], year, year, mbid_only)
                    evolution['labels'][item['name']][year]['users'] = user_details

            # Procesar años de lanzamiento para este año
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_years:
                if item['name'] in evolution['release_years']:
                    evolution['release_years'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_release_year(users, item['name'], year, year, mbid_only)
                    evolution['release_years'][item['name']][year]['users'] = user_details

        # Reducir a top 15 por categoría para visualización
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
        """Obtiene el nÃºmero total real de elementos compartidos por TODOS los usuarios"""
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

        # Total álbumes compartidos por TODOS los usuarios
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

        # Total géneros compartidos por TODOS los usuarios
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
                genre_count += len(genres_list[:3])  # Contar hasta 3 géneros por artista
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

        # Total años de lanzamiento compartidos por TODOS los usuarios
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
        """Obtiene top artistas que mÃ¡s contribuyen a un gÃ©nero especÃ­fico"""
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
        """Obtiene top Ã¡lbumes que mÃ¡s contribuyen a un sello especÃ­fico"""
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
        """Obtiene top artistas que mÃ¡s contribuyen a un perÃ­odo especÃ­fico (dÃ©cada o aÃ±o)"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        if use_decades:
            # Convertir dÃ©cada a rango de aÃ±os
            if period == "Antes de 1950":
                year_condition = "ard.release_year < 1950"
            elif period == "2020s+":
                year_condition = "ard.release_year >= 2020"
            else:
                decade_start = int(period.replace('s', ''))
                decade_end = decade_start + 9
                year_condition = f"ard.release_year BETWEEN {decade_start} AND {decade_end}"
        else:
            # AÃ±o individual
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
        """Obtiene el desglose de scrobbles por usuario para un artista específico"""
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
        """Obtiene el desglose de scrobbles por usuario para un álbum específico"""
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
        """Obtiene el desglose de scrobbles por usuario para una canción específica"""
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
        """Obtiene el desglose de scrobbles por usuario para un género específico"""
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
        """Obtiene el desglose de scrobbles por usuario para un sello específico"""
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
        """Obtiene el desglose de scrobbles por usuario para un período de lanzamiento específico"""
        cursor = self.conn.cursor()
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self._get_mbid_filter(mbid_only)

        # Convertir período a condición de año
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


    def _get_decade(self, year: int) -> str:
        """Convierte un aÃ±o a etiqueta de dÃ©cada"""
        if year < 1950:
            return "Antes de 1950"
        elif year >= 2020:
            return "2020s+"
        else:
            decade_start = (year // 10) * 10
            return f"{decade_start}s"

    def close(self):
        """Cerrar conexiÃ³n a la base de datos"""
        self.conn.close()

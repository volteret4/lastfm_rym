#!/usr/bin/env python3
"""
GroupStatsDatabase - Base de datos para estadísticas grupales
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class GroupStatsDatabase:
    """Base de datos para estadísticas grupales con optimizaciones y caching"""

    def __init__(self, db_path='db/lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_group_stats_table()

    def _create_group_stats_table(self):
        """Crear tabla para almacenar estadísticas grupales pre-calculadas"""
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
        """Genera filtro MBID según los parámetros"""
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
        1. Número de usuarios que lo escuchan (prioridad)
        2. Total de scrobbles (desempate)
        """
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

    def get_top_albums_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                     limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top álbumes por usuarios compartidos y scrobbles totales"""
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
            HAVING user_count >= 2
            ORDER BY user_count DESC, total_scrobbles DESC
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
                   COUNT(DISTINCT user) as user_count,
                   COUNT(*) as total_scrobbles,
                   GROUP_CONCAT(DISTINCT user) as shared_users
            FROM scrobbles s
            WHERE user IN ({','.join(['?'] * len(users))})
              AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist, track
            HAVING user_count >= 2
            ORDER BY user_count DESC, total_scrobbles DESC
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

    def get_top_genres_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                     limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top géneros por usuarios compartidos y scrobbles totales"""
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

        # Procesar géneros JSON
        genre_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            try:
                genres_list = json.loads(row['genres']) if row['genres'] else []
                for genre in genres_list[:3]:  # Solo primeros 3 géneros
                    genre_stats[genre]['users'].add(row['user'])
                    genre_stats[genre]['total_scrobbles'] += row['plays']
                    genre_stats[genre]['user_plays'][row['user']] += row['plays']
            except json.JSONDecodeError:
                continue

        # Filtrar y ordenar
        result = []
        for genre, stats in genre_stats.items():
            if len(stats['users']) >= 2:  # Solo géneros compartidos
                result.append({
                    'name': genre,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users'])
                })

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
            HAVING user_count >= 2
            ORDER BY user_count DESC, total_scrobbles DESC
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

    def get_top_release_years_by_shared_users(self, users: List[str], from_year: int, to_year: int,
                                            limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Top décadas de lanzamiento por usuarios compartidos y scrobbles totales"""
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

        # Procesar por décadas
        decade_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0})

        for row in cursor.fetchall():
            decade = self._get_decade(row['release_year'])
            decade_stats[decade]['users'].add(row['user'])
            decade_stats[decade]['total_scrobbles'] += row['plays']

        # Filtrar y ordenar
        result = []
        for decade, stats in decade_stats.items():
            if len(stats['users']) >= 2:  # Solo décadas compartidas
                result.append({
                    'name': decade,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users'])
                })

        result.sort(key=lambda x: (x['user_count'], x['total_scrobbles']), reverse=True)
        return result[:limit]

    def get_top_by_total_scrobbles(self, users: List[str], from_year: int, to_year: int,
                                 limit: int = 15, mbid_only: bool = False) -> Dict[str, List[Dict]]:
        """
        Top 15 de todo (artistas, álbumes, canciones) ordenado solo por scrobbles totales
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
        """Top álbumes solo por scrobbles totales"""
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
        """Top géneros solo por scrobbles totales"""
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

        # Procesar géneros JSON
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
        """Top décadas solo por scrobbles totales"""
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
        """Obtiene datos de evolución temporal para gráficos lineales"""
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

        # Para cada año, obtener top 15 y construir evolución
        for year in years:
            # Artistas
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_artists:
                if item['name'] not in evolution['artists']:
                    evolution['artists'][item['name']] = {y: 0 for y in years}
                evolution['artists'][item['name']][year] = item['total_scrobbles']

            # Álbumes
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_albums:
                if item['name'] not in evolution['albums']:
                    evolution['albums'][item['name']] = {y: 0 for y in years}
                evolution['albums'][item['name']][year] = item['total_scrobbles']

            # Canciones
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_tracks:
                if item['name'] not in evolution['tracks']:
                    evolution['tracks'][item['name']] = {y: 0 for y in years}
                evolution['tracks'][item['name']][year] = item['total_scrobbles']

            # Géneros
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_genres:
                if item['name'] not in evolution['genres']:
                    evolution['genres'][item['name']] = {y: 0 for y in years}
                evolution['genres'][item['name']][year] = item['total_scrobbles']

            # Sellos
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_labels:
                if item['name'] not in evolution['labels']:
                    evolution['labels'][item['name']] = {y: 0 for y in years}
                evolution['labels'][item['name']][year] = item['total_scrobbles']

            # Años de lanzamiento
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_years:
                if item['name'] not in evolution['release_years']:
                    evolution['release_years'][item['name']] = {y: 0 for y in years}
                evolution['release_years'][item['name']][year] = item['total_scrobbles']

        # Reducir a top 15 por categoría para visualización
        for category in ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']:
            # Calcular total por elemento
            totals = {}
            for item, year_data in evolution[category].items():
                totals[item] = sum(year_data.values())

            # Quedarse con top 15
            top_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:15]
            evolution[category] = {item: evolution[category][item] for item, _ in top_items}

        return evolution

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

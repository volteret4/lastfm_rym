#!/usr/bin/env python3
"""
GroupDataAnalyzer - Analizador para datos de coincidencias por nivel de usuarios CORREGIDO
Permite obtener TOPs de elementos compartidos por N usuarios EXACTAMENTE
"""

from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict
import json


class GroupDataAnalyzer:
    """Clase para analizar datos de coincidencias por nivel de usuarios"""

    def __init__(self, database, years_back: int = 5, mbid_only: bool = False):
        self.database = database
        self.years_back = years_back
        self.mbid_only = mbid_only
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def analyze_data_by_user_levels(self, users: List[str]) -> Dict:
        """Analiza datos para diferentes niveles de coincidencia de usuarios"""
        print(f"    • Analizando datos por niveles de usuarios...")

        total_users = len(users)
        data_by_levels = {}

        # Generar datos para cada nivel de usuarios (todos, todos-1, todos-2, etc.)
        for min_users in range(total_users, 1, -1):  # Desde todos hasta 2 usuarios mínimo
            level_key = self._get_level_key(min_users, total_users)
            print(f"      • Nivel: {level_key}")

            level_data = self._get_data_for_level(users, min_users)
            data_by_levels[level_key] = level_data

        return {
            'period': f"{self.from_year}-{self.to_year}",
            'users': users,
            'user_count': len(users),
            'data_by_levels': data_by_levels,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _get_level_key(self, min_users: int, total_users: int) -> str:
        """Genera la clave descriptiva para el nivel de usuarios"""
        if min_users == total_users:
            return "total_usuarios"
        else:
            missing = total_users - min_users
            return f"total_menos_{missing}"

    def _get_level_label(self, level_key: str, total_users: int) -> str:
        """Genera la etiqueta descriptiva para mostrar en el HTML"""
        if level_key == "total_usuarios":
            return f"Total de usuarios ({total_users})"
        else:
            missing = int(level_key.replace("total_menos_", ""))
            remaining = total_users - missing
            return f"Total menos {missing} ({remaining} usuarios)"

    def _get_data_for_level(self, users: List[str], min_users: int) -> Dict:
        """Obtiene datos para un nivel específico de usuarios"""

        # CORRIGIDO: Usar las funciones específicas para niveles exactos
        # Top 25 artistas con exactamente min_users
        top_artists = self._get_top_artists_by_exact_users(users, min_users, 25)

        # Top 25 álbumes con exactamente min_users
        top_albums = self._get_top_albums_by_exact_users(users, min_users, 25)

        # Top 25 canciones con exactamente min_users
        top_tracks = self._get_top_tracks_by_exact_users(users, min_users, 25)

        # Top 25 géneros con exactamente min_users
        top_genres = self._get_top_genres_by_exact_users(users, min_users, 25)

        # Top 25 sellos con exactamente min_users
        top_labels = self._get_top_labels_by_exact_users(users, min_users, 25)

        # Top 25 décadas con exactamente min_users
        top_decades = self._get_top_release_decades_by_exact_users(users, min_users, 25)

        return {
            'min_users': min_users,
            'artists': self._prepare_data_items(top_artists),
            'albums': self._prepare_data_items(top_albums),
            'tracks': self._prepare_data_items(top_tracks),
            'genres': self._prepare_data_items(top_genres),
            'labels': self._prepare_data_items(top_labels),
            'decades': self._prepare_data_items(top_decades),
            'counts': {
                'artists': len(top_artists),
                'albums': len(top_albums),
                'tracks': len(top_tracks),
                'genres': len(top_genres),
                'labels': len(top_labels),
                'decades': len(top_decades)
            }
        }

    def _get_top_artists_by_exact_users(self, users: List[str], exact_users: int, limit: int = 25) -> List[Dict]:
        """Obtiene artistas compartidos por EXACTAMENTE el número especificado de usuarios"""
        cursor = self.database.conn.cursor()
        from_timestamp = int(datetime(self.from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(self.to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self.database._get_mbid_filter(self.mbid_only)

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

        # Filtrar por número EXACTO de usuarios
        result = []
        for artist, stats in artist_stats.items():
            if len(stats['users']) == exact_users:  # EXACTAMENTE el número de usuarios
                result.append({
                    'name': artist,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        # Ordenar por scrobbles totales (descendente)
        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def _get_top_albums_by_exact_users(self, users: List[str], exact_users: int, limit: int = 25) -> List[Dict]:
        """Obtiene álbumes compartidos por EXACTAMENTE el número especificado de usuarios"""
        cursor = self.database.conn.cursor()
        from_timestamp = int(datetime(self.from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(self.to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self.database._get_mbid_filter(self.mbid_only)

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

        result = []
        for album_name, stats in album_stats.items():
            if len(stats['users']) == exact_users:
                result.append({
                    'name': album_name,
                    'artist': stats['artist'],
                    'album': stats['album'],
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def _get_top_tracks_by_exact_users(self, users: List[str], exact_users: int, limit: int = 25) -> List[Dict]:
        """Obtiene canciones compartidas por EXACTAMENTE el número especificado de usuarios"""
        cursor = self.database.conn.cursor()
        from_timestamp = int(datetime(self.from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(self.to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self.database._get_mbid_filter(self.mbid_only)

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

        result = []
        for track_name, stats in track_stats.items():
            if len(stats['users']) == exact_users:
                result.append({
                    'name': track_name,
                    'artist': stats['artist'],
                    'track': stats['track'],
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def _get_top_genres_by_exact_users(self, users: List[str], exact_users: int, limit: int = 25) -> List[Dict]:
        """Obtiene géneros compartidos por EXACTAMENTE el número especificado de usuarios"""
        cursor = self.database.conn.cursor()
        from_timestamp = int(datetime(self.from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(self.to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self.database._get_mbid_filter(self.mbid_only)

        cursor.execute(f'''
            SELECT ag.genres, user, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user IN ({','.join(['?'] * len(users))})
              AND s.timestamp >= ? AND s.timestamp <= ?
            {mbid_filter}
            GROUP BY ag.genres, user
        ''', users + [from_timestamp, to_timestamp])

        genre_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            try:
                genres_list = json.loads(row['genres']) if row['genres'] else []
                for genre in genres_list[:3]:  # Solo primeros 3 géneros por artista
                    genre_stats[genre]['users'].add(row['user'])
                    genre_stats[genre]['total_scrobbles'] += row['plays']
                    genre_stats[genre]['user_plays'][row['user']] += row['plays']
            except json.JSONDecodeError:
                continue

        result = []
        for genre, stats in genre_stats.items():
            if len(stats['users']) == exact_users:
                result.append({
                    'name': genre,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def _get_top_labels_by_exact_users(self, users: List[str], exact_users: int, limit: int = 25) -> List[Dict]:
        """Obtiene sellos compartidos por EXACTAMENTE el número especificado de usuarios"""
        cursor = self.database.conn.cursor()
        from_timestamp = int(datetime(self.from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(self.to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self.database._get_mbid_filter(self.mbid_only)

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

        label_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            label = row['label']
            user = row['user']
            plays = row['plays']
            label_stats[label]['users'].add(user)
            label_stats[label]['total_scrobbles'] += plays
            label_stats[label]['user_plays'][user] += plays

        result = []
        for label, stats in label_stats.items():
            if len(stats['users']) == exact_users:
                result.append({
                    'name': label,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def _get_top_release_decades_by_exact_users(self, users: List[str], exact_users: int, limit: int = 25) -> List[Dict]:
        """Obtiene décadas compartidas por EXACTAMENTE el número especificado de usuarios"""
        cursor = self.database.conn.cursor()
        from_timestamp = int(datetime(self.from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(self.to_year + 1, 1, 1).timestamp()) - 1
        mbid_filter = self.database._get_mbid_filter(self.mbid_only)

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

        decade_stats = defaultdict(lambda: {'users': set(), 'total_scrobbles': 0, 'user_plays': defaultdict(int)})

        for row in cursor.fetchall():
            decade = self._get_decade(row['release_year'])
            decade_stats[decade]['users'].add(row['user'])
            decade_stats[decade]['total_scrobbles'] += row['plays']
            decade_stats[decade]['user_plays'][row['user']] += row['plays']

        result = []
        for decade, stats in decade_stats.items():
            if len(stats['users']) == exact_users:
                result.append({
                    'name': decade,
                    'user_count': len(stats['users']),
                    'total_scrobbles': stats['total_scrobbles'],
                    'shared_users': list(stats['users']),
                    'user_plays': dict(stats['user_plays'])
                })

        result.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        return result[:limit]

    def _get_decade(self, year: int) -> str:
        """Convierte un año a etiqueta de década"""
        if year < 1950:
            return "Antes de 1950"
        elif year >= 2020:
            return "2020s+"
        else:
            decade_start = (year // 10) * 10
            return f"{decade_start}s"

    def _prepare_data_items(self, raw_data: List[Dict]) -> List[Dict]:
        """Prepara los elementos para mostrar en formato compatible con html_semanal.py"""
        if not raw_data:
            return []

        result = []
        for item in raw_data:
            prepared_item = {
                'name': item['name'],
                'count': item['total_scrobbles'],  # Usar total_scrobbles como "count"
                'users': item['shared_users'],
                'user_counts': item.get('user_plays', {}),  # Scrobbles por usuario
                'user_count': item['user_count']
            }

            # Agregar información adicional si está disponible
            if 'artist' in item:
                prepared_item['artist'] = item['artist']
            if 'album' in item:
                prepared_item['album'] = item['album']
            if 'track' in item:
                prepared_item['track'] = item['track']

            result.append(prepared_item)

        return result

    def get_level_labels(self, users: List[str]) -> Dict[str, str]:
        """Obtiene las etiquetas para todos los niveles disponibles"""
        total_users = len(users)
        labels = {}

        for min_users in range(total_users, 1, -1):
            level_key = self._get_level_key(min_users, total_users)
            labels[level_key] = self._get_level_label(level_key, total_users)

        return labels

    def get_summary_for_level(self, level_data: Dict) -> Dict:
        """Obtiene resumen de estadísticas para un nivel específico"""
        return {
            'total_items': sum(level_data['counts'].values()),
            'artists_count': level_data['counts']['artists'],
            'albums_count': level_data['counts']['albums'],
            'tracks_count': level_data['counts']['tracks'],
            'genres_count': level_data['counts']['genres'],
            'labels_count': level_data['counts']['labels'],
            'decades_count': level_data['counts']['decades'],
            'min_users': level_data['min_users']
        }

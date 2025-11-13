#!/usr/bin/env python3
"""
UserStatsDatabase - Versión optimizada con soporte MBID y mejor rendimiento
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from collections import defaultdict



class UserStatsDatabase:
    """Versión optimizada con soporte para filtros MBID y mejor rendimiento"""

    def __init__(self, db_path='db/lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def _get_mbid_filter(self, mbid_only: bool, table_alias: str = 's') -> str:
        """Genera filtro MBID según los parámetros"""
        if not mbid_only:
            return ""

        return f"""AND (
            ({table_alias}.artist_mbid IS NOT NULL AND {table_alias}.artist_mbid != '') OR
            ({table_alias}.album_mbid IS NOT NULL AND {table_alias}.album_mbid != '') OR
            ({table_alias}.track_mbid IS NOT NULL AND {table_alias}.track_mbid != '')
        )"""

    def get_user_scrobbles_by_year(self, user: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict[int, int]:
        """Obtiene conteo de scrobbles del usuario agrupados por año - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT strftime('%Y', datetime(timestamp, 'unixepoch')) as year,
                   COUNT(*) as count
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY year
            ORDER BY year
        ''', (user, from_timestamp, to_timestamp))

        scrobbles_by_year = {}
        for row in cursor.fetchall():
            year = int(row['year'])
            scrobbles_by_year[year] = row['count']

        return scrobbles_by_year

    def get_common_artists_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, Dict[str, int]]:
        """Obtiene artistas comunes entre el usuario y otros usuarios - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's1')

        # Obtener artistas del usuario principal
        cursor.execute(f'''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles s1
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
        ''', (user, from_timestamp, to_timestamp))

        user_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

        if not user_artists:
            return {}

        common_artists = {}

        for other_user in other_users:
            if other_user == user:
                continue

            mbid_filter2 = self._get_mbid_filter(mbid_only, 's2')

            cursor.execute(f'''
                SELECT artist, COUNT(*) as plays
                FROM scrobbles s2
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND artist IN ({','.join(['?'] * len(user_artists))})
                {mbid_filter2}
                GROUP BY artist
            ''', [other_user, from_timestamp, to_timestamp] + list(user_artists.keys()))

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

    def get_common_albums_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, Dict[str, int]]:
        """Obtiene álbumes comunes entre el usuario y otros usuarios - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's1')

        # Obtener álbumes del usuario principal
        cursor.execute(f'''
            SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
            FROM scrobbles s1
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND album IS NOT NULL AND album != ''
            {mbid_filter}
            GROUP BY album_key
        ''', (user, from_timestamp, to_timestamp))

        user_albums = {row['album_key']: row['plays'] for row in cursor.fetchall()}

        if not user_albums:
            return {}

        common_albums = {}

        for other_user in other_users:
            if other_user == user:
                continue

            mbid_filter2 = self._get_mbid_filter(mbid_only, 's2')

            cursor.execute(f'''
                SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
                FROM scrobbles s2
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND album IS NOT NULL AND album != ''
                  AND (artist || ' - ' || album) IN ({','.join(['?'] * len(user_albums))})
                {mbid_filter2}
                GROUP BY album_key
            ''', [other_user, from_timestamp, to_timestamp] + list(user_albums.keys()))

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

    def get_common_tracks_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, Dict[str, int]]:
        """Obtiene canciones comunes entre el usuario y otros usuarios - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's1')

        # Obtener canciones del usuario principal
        cursor.execute(f'''
            SELECT (artist || ' - ' || track) as track_key, COUNT(*) as plays
            FROM scrobbles s1
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY track_key
        ''', (user, from_timestamp, to_timestamp))

        user_tracks = {row['track_key']: row['plays'] for row in cursor.fetchall()}

        if not user_tracks:
            return {}

        common_tracks = {}

        for other_user in other_users:
            if other_user == user:
                continue

            mbid_filter2 = self._get_mbid_filter(mbid_only, 's2')

            cursor.execute(f'''
                SELECT (artist || ' - ' || track) as track_key, COUNT(*) as plays
                FROM scrobbles s2
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND (artist || ' - ' || track) IN ({','.join(['?'] * len(user_tracks))})
                {mbid_filter2}
                GROUP BY track_key
            ''', [other_user, from_timestamp, to_timestamp] + list(user_tracks.keys()))

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

    def get_common_genres_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, Dict[str, int]]:
        """Obtiene géneros comunes entre el usuario y otros usuarios - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener géneros del usuario principal
        cursor.execute(f'''
            SELECT ag.genres, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
            {mbid_filter}
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

            cursor.execute(f'''
                SELECT ag.genres, COUNT(*) as plays
                FROM scrobbles s
                JOIN artist_genres ag ON s.artist = ag.artist
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                {mbid_filter}
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

    def get_common_labels_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, Dict[str, int]]:
        """Obtiene sellos comunes entre el usuario y otros usuarios - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener sellos del usuario principal
        cursor.execute(f'''
            SELECT al.label, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            {mbid_filter}
            GROUP BY al.label
        ''', (user, from_timestamp, to_timestamp))

        user_labels = {row['label']: row['plays'] for row in cursor.fetchall()}

        if not user_labels:
            return {}

        common_labels = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute(f'''
                SELECT al.label, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND al.label IS NOT NULL AND al.label != ''
                  AND al.label IN ({','.join(['?'] * len(user_labels))})
                {mbid_filter}
                GROUP BY al.label
            ''', [other_user, from_timestamp, to_timestamp] + list(user_labels.keys()))

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

    def get_common_release_years_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, Dict[str, int]]:
        """Obtiene décadas de lanzamiento comunes entre el usuario y otros usuarios - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener décadas del usuario principal
        cursor.execute(f'''
            SELECT ard.release_year, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ard.release_year IS NOT NULL
            {mbid_filter}
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

            cursor.execute(f'''
                SELECT ard.release_year, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND ard.release_year IS NOT NULL
                {mbid_filter}
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

    # NUEVOS MÉTODOS PARA GÉNEROS POR PROVEEDOR

    def get_user_top_genres_by_provider(self, user: str, from_year: int, to_year: int, provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """
        Obtiene los géneros más escuchados por el usuario según el proveedor especificado

        Args:
            user: Usuario
            from_year: Año inicial
            to_year: Año final
            provider: 'lastfm', 'musicbrainz', o 'discogs'
            limit: Límite de géneros
            mbid_only: Solo scrobbles con MBID

        Returns:
            Lista de tuplas (género, reproducciones)
        """
        genres_by_year = self.get_user_genres_by_year_by_provider(user, from_year, to_year, provider, limit=50, mbid_only=mbid_only)

        # Sumar todos los años
        total_genres = defaultdict(int)
        for year_genres in genres_by_year.values():
            for genre, plays in year_genres.items():
                total_genres[genre] += plays

        # Ordenar y limitar
        sorted_genres = sorted(total_genres.items(), key=lambda x: x[1], reverse=True)
        return sorted_genres[:limit]

    def get_user_genres_by_year_by_provider(self, user: str, from_year: int, to_year: int, provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False) -> Dict[int, Dict[str, int]]:
        """
        Obtiene géneros del usuario por año según el proveedor especificado

        Args:
            user: Usuario
            from_year: Año inicial
            to_year: Año final
            provider: 'lastfm', 'musicbrainz', o 'discogs'
            limit: Límite de géneros por año
            mbid_only: Solo scrobbles con MBID

        Returns:
            Dict con datos por año {año: {género: reproducciones}}
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Determinar la columna de géneros según el proveedor
        if provider == 'lastfm':
            genres_column = 'ag.genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'
        elif provider == 'musicbrainz':
            # Asumir que existe una tabla artist_genres_mb o columna mb_genres
            genres_column = 'ag.mb_genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'
        elif provider == 'discogs':
            # Asumir que existe una tabla artist_genres_discogs o columna discogs_genres
            genres_column = 'ag.discogs_genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'
        else:
            # Default a lastfm
            genres_column = 'ag.genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'

        # Solo obtener los top artistas para reducir carga
        cursor.execute(f'''
            SELECT DISTINCT s.artist
            FROM scrobbles s
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
            {mbid_filter}
            GROUP BY s.artist
            ORDER BY COUNT(*) DESC
            LIMIT 200
        ''', (user, from_timestamp, to_timestamp))

        top_artists = [row['artist'] for row in cursor.fetchall()]

        if not top_artists:
            return {}

        # Obtener géneros solo para estos artistas
        try:
            cursor.execute(f'''
                SELECT {genres_column} as genres,
                       strftime('%Y', datetime(s.timestamp, 'unixepoch')) as year,
                       COUNT(*) as plays
                FROM scrobbles s
                {table_join}
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND s.artist IN ({','.join(['?'] * len(top_artists))})
                  AND {genres_column} IS NOT NULL AND {genres_column} != ''
                {mbid_filter}
                GROUP BY {genres_column}, year
                ORDER BY year, plays DESC
            ''', [user, from_timestamp, to_timestamp] + top_artists)

            genres_by_year = defaultdict(lambda: defaultdict(int))

            for row in cursor.fetchall():
                year = int(row['year'])
                genres_json = row['genres']
                plays = row['plays']

                try:
                    genres_list = json.loads(genres_json) if genres_json else []
                    for genre in genres_list[:3]:  # Solo primeros 3 géneros por artista
                        genres_by_year[year][genre] += plays
                except (json.JSONDecodeError, TypeError):
                    # Si no es JSON, asumir que es un género simple
                    if genres_json:
                        genres_by_year[year][genres_json] += plays
                    continue

            # Limitar géneros por año
            limited_genres_by_year = {}
            for year, genres in genres_by_year.items():
                sorted_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)
                limited_genres_by_year[year] = dict(sorted_genres[:limit])

            return limited_genres_by_year

        except sqlite3.OperationalError:
            # Si la columna no existe, fallback a lastfm
            if provider != 'lastfm':
                return self.get_user_genres_by_year_by_provider(user, from_year, to_year, 'lastfm', limit, mbid_only)
            else:
                return {}

    def get_top_artists_for_genre_by_provider(self, user: str, genre: str, from_year: int, to_year: int, provider: str = 'lastfm', limit: int = 25, mbid_only: bool = False) -> List[Dict]:
        """
        Obtiene top artistas para un género específico según el proveedor

        Args:
            user: Usuario
            genre: Género
            from_year: Año inicial
            to_year: Año final
            provider: 'lastfm', 'musicbrainz', o 'discogs'
            limit: Límite de artistas
            mbid_only: Solo scrobbles con MBID

        Returns:
            Lista de diccionarios con artista y reproducciones por año
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Determinar la columna de géneros según el proveedor
        if provider == 'lastfm':
            genres_column = 'ag.genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'
        elif provider == 'musicbrainz':
            genres_column = 'ag.mb_genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'
        elif provider == 'discogs':
            genres_column = 'ag.discogs_genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'
        else:
            genres_column = 'ag.genres'
            table_join = 'JOIN artist_genres ag ON s.artist = ag.artist'

        try:
            # Obtener artistas y reproducciones por año para el género específico
            cursor.execute(f'''
                SELECT s.artist,
                       strftime('%Y', datetime(s.timestamp, 'unixepoch')) as year,
                       COUNT(*) as plays
                FROM scrobbles s
                {table_join}
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND ({genres_column} LIKE ? OR {genres_column} LIKE ?)
                {mbid_filter}
                GROUP BY s.artist, year
                ORDER BY s.artist, year
            ''', (user, from_timestamp, to_timestamp, f'%"{genre}"%', f'%{genre}%'))

            # Organizar datos por artista y año
            artist_data = defaultdict(lambda: defaultdict(int))
            total_plays_by_artist = defaultdict(int)

            for row in cursor.fetchall():
                artist = row['artist']
                year = int(row['year'])
                plays = row['plays']

                artist_data[artist][year] = plays
                total_plays_by_artist[artist] += plays

            # Obtener top artistas por total de reproducciones
            top_artists = sorted(total_plays_by_artist.items(), key=lambda x: x[1], reverse=True)[:limit]

            result = []
            for artist_name, total_plays in top_artists:
                artist_yearly_data = {}
                for year in range(from_year, to_year + 1):
                    artist_yearly_data[year] = artist_data[artist_name].get(year, 0)

                result.append({
                    'artist': artist_name,
                    'total_plays': total_plays,
                    'yearly_data': artist_yearly_data
                })

            return result

        except sqlite3.OperationalError:
            # Si la columna no existe, fallback a lastfm
            if provider != 'lastfm':
                return self.get_top_artists_for_genre_by_provider(user, genre, from_year, to_year, 'lastfm', limit, mbid_only)
            else:
                return []

    def get_user_top_genres(self, user: str, from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene los géneros más escuchados por el usuario - con filtro MBID"""
        genres_by_year = self.get_user_genres_by_year(user, from_year, to_year, limit=20, mbid_only=mbid_only)

        # Sumar todos los años
        total_genres = defaultdict(int)
        for year_genres in genres_by_year.values():
            for genre, plays in year_genres.items():
                total_genres[genre] += plays

        # Ordenar y limitar
        sorted_genres = sorted(total_genres.items(), key=lambda x: x[1], reverse=True)
        return sorted_genres[:limit]

    def get_user_genres_by_year(self, user: str, from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> Dict[int, Dict[str, int]]:
        """Obtiene géneros del usuario por año - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Solo obtener los top artistas para reducir carga
        cursor.execute(f'''
            SELECT DISTINCT s.artist
            FROM scrobbles s
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
            {mbid_filter}
            GROUP BY s.artist
            ORDER BY COUNT(*) DESC
            LIMIT 100
        ''', (user, from_timestamp, to_timestamp))

        top_artists = [row['artist'] for row in cursor.fetchall()]

        if not top_artists:
            return {}

        # Obtener géneros solo para estos artistas
        cursor.execute(f'''
            SELECT ag.genres,
                   strftime('%Y', datetime(s.timestamp, 'unixepoch')) as year,
                   COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.artist IN ({','.join(['?'] * len(top_artists))})
            {mbid_filter}
            GROUP BY ag.genres, year
            ORDER BY year, plays DESC
        ''', [user, from_timestamp, to_timestamp] + top_artists)

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

    def get_top_artists_by_scrobbles(self, users: List[str], from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> Dict[str, List]:
        """Obtiene top artistas por scrobbles para cada usuario - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        users_top_artists = {}

        for user in users:
            cursor.execute(f'''
                SELECT artist, COUNT(*) as plays
                FROM scrobbles s
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                {mbid_filter}
                GROUP BY artist
                ORDER BY plays DESC
                LIMIT ?
            ''', (user, from_timestamp, to_timestamp, limit))

            users_top_artists[user] = [{'name': row['artist'], 'plays': row['plays']} for row in cursor.fetchall()]

        return users_top_artists

    def get_top_artists_by_days(self, users: List[str], from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> Dict[str, List]:
        """Obtiene top artistas por número de días diferentes en que fueron escuchados - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        users_top_artists = {}

        for user in users:
            cursor.execute(f'''
                SELECT artist, COUNT(DISTINCT date(datetime(timestamp, 'unixepoch'))) as days_count
                FROM scrobbles s
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                {mbid_filter}
                GROUP BY artist
                ORDER BY days_count DESC
                LIMIT ?
            ''', (user, from_timestamp, to_timestamp, limit))

            users_top_artists[user] = [{'name': row['artist'], 'days': row['days_count']} for row in cursor.fetchall()]

        return users_top_artists

    def get_top_artists_by_track_count(self, users: List[str], from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> Dict[str, List]:
        """Obtiene top artistas por número de canciones diferentes escuchadas - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        users_top_artists = {}

        for user in users:
            cursor.execute(f'''
                SELECT artist, COUNT(DISTINCT track) as track_count, COUNT(*) as total_plays
                FROM scrobbles s
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                {mbid_filter}
                GROUP BY artist
                ORDER BY track_count DESC
                LIMIT ?
            ''', (user, from_timestamp, to_timestamp, limit))

            users_top_artists[user] = [
                {'name': row['artist'], 'track_count': row['track_count'], 'plays': row['total_plays']}
                for row in cursor.fetchall()
            ]

        return users_top_artists

    def get_top_artists_by_streaks(self, users: List[str], from_year: int, to_year: int, limit: int = 5, mbid_only: bool = False) -> Dict[str, List]:
        """Obtiene top artistas por streaks (días consecutivos) - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        users_top_artists = {}

        for user in users:
            # Obtener todas las fechas por artista
            cursor.execute(f'''
                SELECT artist, date(datetime(timestamp, 'unixepoch')) as play_date, COUNT(*) as daily_plays
                FROM scrobbles s
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                {mbid_filter}
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

    def get_top_artists_for_genre(self, user: str, genre: str, from_year: int, to_year: int, limit: int = 5, mbid_only: bool = False) -> List[Dict]:
        """Obtiene top artistas para un género específico - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        cursor.execute(f'''
            SELECT s.artist, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ag.genres LIKE ?
            {mbid_filter}
            GROUP BY s.artist
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, f'%"{genre}"%', limit))

        return [{'name': row['artist'], 'plays': row['plays']} for row in cursor.fetchall()]

    def get_one_hit_wonders_for_user(self, user: str, from_year: int, to_year: int, min_scrobbles: int = 25, limit: int = 10, mbid_only: bool = False) -> List[Dict]:
        """Obtiene artistas con una sola canción y más de min_scrobbles reproducciones - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        cursor.execute(f'''
            SELECT artist, track, COUNT(*) as total_plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
            HAVING COUNT(DISTINCT track) = 1 AND total_plays >= ?
            ORDER BY total_plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, min_scrobbles, limit))

        return [{'name': row['artist'], 'track': row['track'], 'plays': row['total_plays']} for row in cursor.fetchall()]

    def get_new_artists_for_user(self, user: str, from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> List[Dict]:
        """Obtiene artistas nuevos (sin scrobbles antes del período) - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener artistas del período actual
        cursor.execute(f'''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
        ''', (user, from_timestamp, to_timestamp))

        current_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

        # Obtener artistas de períodos anteriores
        cursor.execute(f'''
            SELECT DISTINCT artist
            FROM scrobbles s
            WHERE user = ? AND timestamp < ?
            {mbid_filter}
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

    def get_artist_monthly_ranks(self, user: str, from_year: int, to_year: int, min_monthly_scrobbles: int = 50, mbid_only: bool = False) -> Dict[str, Dict]:
        """Obtiene rankings mensuales de artistas para calcular cambios de ranking - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        cursor.execute(f'''
            SELECT artist,
                   strftime('%Y-%m', datetime(timestamp, 'unixepoch')) as month,
                   COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
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

    def get_fastest_rising_artists(self, user: str, from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> List[Dict]:
        """Obtiene artistas que más rápido han subido en rankings mensuales - con filtro MBID"""
        rankings = self.get_artist_monthly_ranks(user, from_year, to_year, mbid_only=mbid_only)

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

    def get_fastest_falling_artists(self, user: str, from_year: int, to_year: int, limit: int = 10, mbid_only: bool = False) -> List[Dict]:
        """Obtiene artistas que más rápido han bajado en rankings mensuales - con filtro MBID"""
        rankings = self.get_artist_monthly_ranks(user, from_year, to_year, mbid_only=mbid_only)

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

    def get_user_individual_evolution_data(self, user: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict:
        """Obtiene todos los datos de evolución individual del usuario con detalles mejorados - con filtro MBID"""
        cursor = self.conn.cursor()

        evolution_data = {}
        years = list(range(from_year, to_year + 1))

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # 1. Top 10 géneros por año - CON ARTISTAS QUE CONTRIBUYEN
        top_genres = self.get_user_top_genres(user, from_year, to_year, 10, mbid_only)
        top_genre_names = [genre for genre, _ in top_genres]

        genres_evolution = {}
        genres_details = {}
        for genre in top_genre_names:
            genres_evolution[genre] = {}
            genres_details[genre] = {}
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND ag.genres LIKE ?
                    {mbid_filter}
                ''', (user, str(year), f'%"{genre}"%'))
                result = cursor.fetchone()
                genres_evolution[genre][year] = result['plays'] if result else 0

                # Obtener top 5 artistas para este género en este año
                cursor.execute(f'''
                    SELECT s.artist, COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND ag.genres LIKE ?
                    {mbid_filter}
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
        cursor.execute(f'''
            SELECT al.label, COUNT(*) as total_plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            {mbid_filter}
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
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND al.label = ?
                    {mbid_filter}
                ''', (user, str(year), label))
                result = cursor.fetchone()
                labels_evolution[label][year] = result['plays'] if result else 0

                # Obtener top 5 artistas para este sello en este año
                cursor.execute(f'''
                    SELECT s.artist, COUNT(*) as plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND al.label = ?
                    {mbid_filter}
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
        cursor.execute(f'''
            SELECT artist, COUNT(*) as total_plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
            ORDER BY total_plays DESC
            LIMIT 10
        ''', (user, int(datetime(from_year, 1, 1).timestamp()), int(datetime(to_year + 1, 1, 1).timestamp()) - 1))

        top_artists = [row['artist'] for row in cursor.fetchall()]

        artists_evolution = {}
        for artist in top_artists:
            artists_evolution[artist] = {}
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                artists_evolution[artist][year] = result['plays'] if result else 0

        evolution_data['artists'] = {
            'data': artists_evolution,
            'years': years,
            'names': top_artists
        }

        # 4. One hit wonders con detalles de la canción ESPECÍFICA
        one_hit_wonders = self.get_one_hit_wonders_for_user(user, from_year, to_year, 25, 10, mbid_only)
        one_hit_evolution = {}
        one_hit_details = {}
        for artist_data in one_hit_wonders:
            artist = artist_data['name']
            one_hit_evolution[artist] = {}
            one_hit_details[artist] = {}
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                one_hit_evolution[artist][year] = result['plays'] if result else 0

                # Obtener la canción única
                cursor.execute(f'''
                    SELECT track, COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                    GROUP BY track
                    ORDER BY plays DESC
                    LIMIT 1
                ''', (user, artist, str(year)))
                track_result = cursor.fetchone()
                if track_result:
                    one_hit_details[artist][year] = {
                        'track': track_result['track'],
                        'plays': track_result['plays'],
                        'artist': artist
                    }
                else:
                    one_hit_details[artist][year] = {
                        'track': artist_data.get('track', 'N/A'),
                        'plays': 0,
                        'artist': artist
                    }

        evolution_data['one_hit_wonders'] = {
            'data': one_hit_evolution,
            'details': one_hit_details,
            'years': years,
            'names': [artist['name'] for artist in one_hit_wonders]
        }

        # 5. Streaks - datos en DÍAS, no scrobbles
        top_streak_artists_data = self.get_top_artists_by_streaks([user], from_year, to_year, 10, mbid_only).get(user, [])[:10]
        streak_evolution = {}
        streak_details = {}
        for artist_data in top_streak_artists_data:
            artist = artist_data['name']
            streak_evolution[artist] = {}
            streak_details[artist] = {}
            for year in years:
                # Calcular días únicos por año
                cursor.execute(f'''
                    SELECT COUNT(DISTINCT date(datetime(timestamp, 'unixepoch'))) as days_count
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
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
        top_track_count_artists_data = self.get_top_artists_by_track_count([user], from_year, to_year, 10, mbid_only).get(user, [])[:10]
        track_count_evolution = {}
        track_count_details = {}
        for artist_data in top_track_count_artists_data:
            artist = artist_data['name']
            track_count_evolution[artist] = {}
            track_count_details[artist] = {}
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(DISTINCT track) as track_count
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                track_count = result['track_count'] if result else 0
                track_count_evolution[artist][year] = track_count

                # Obtener top 10 álbumes para este año
                cursor.execute(f'''
                    SELECT album, COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                      AND album IS NOT NULL AND album != ''
                    {mbid_filter}
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
        new_artists = self.get_new_artists_for_user(user, from_year, to_year, 10, mbid_only)
        new_artists_evolution = {}
        for artist_data in new_artists:
            artist = artist_data['name']
            new_artists_evolution[artist] = {}
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                new_artists_evolution[artist][year] = result['plays'] if result else 0

        evolution_data['new_artists'] = {
            'data': new_artists_evolution,
            'years': years,
            'names': [artist['name'] for artist in new_artists]
        }

        # 8. & 9. Rising and falling artists evolution con detalles de canciones TOP
        rising_artists = self.get_fastest_rising_artists(user, from_year, to_year, 10, mbid_only)
        falling_artists = self.get_fastest_falling_artists(user, from_year, to_year, 10, mbid_only)

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
                    cursor.execute(f'''
                        SELECT COUNT(*) as plays
                        FROM scrobbles s
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                        {mbid_filter}
                    ''', (user, artist, str(year)))
                    result = cursor.fetchone()
                    category_evolution[artist][year] = result['plays'] if result else 0

                    # Obtener top 10 canciones para este año
                    cursor.execute(f'''
                        SELECT track, COUNT(*) as plays
                        FROM scrobbles s
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                        {mbid_filter}
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

    def get_user_individual_evolution_data_cumulative(self, user: str, from_year: int, to_year: int, mbid_only: bool = False) -> Dict:
        """Obtiene todos los datos de evolución individual del usuario de forma ACUMULATIVA - con filtro MBID"""
        cursor = self.conn.cursor()

        evolution_data = {}
        years = list(range(from_year, to_year + 1))

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # 1. Top 10 géneros por año - ACUMULATIVO
        top_genres = self.get_user_top_genres(user, from_year, to_year, 10, mbid_only)
        top_genre_names = [genre for genre, _ in top_genres]

        genres_evolution = {}
        genres_details = {}
        for genre in top_genre_names:
            genres_evolution[genre] = {}
            genres_details[genre] = {}
            cumulative_count = 0
            for year in years:
                # Obtener datos del año actual
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND ag.genres LIKE ?
                    {mbid_filter}
                ''', (user, str(year), f'%"{genre}"%'))
                result = cursor.fetchone()
                year_plays = result['plays'] if result else 0

                # Acumular
                cumulative_count += year_plays
                genres_evolution[genre][year] = cumulative_count

                # Obtener top 5 artistas para este género en este año (no acumulativo)
                cursor.execute(f'''
                    SELECT s.artist, COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND ag.genres LIKE ?
                    {mbid_filter}
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

        # 2. Top 10 sellos por año - ACUMULATIVO
        cursor.execute(f'''
            SELECT al.label, COUNT(*) as total_plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            {mbid_filter}
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
            cumulative_count = 0
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND al.label = ?
                    {mbid_filter}
                ''', (user, str(year), label))
                result = cursor.fetchone()
                year_plays = result['plays'] if result else 0

                # Acumular
                cumulative_count += year_plays
                labels_evolution[label][year] = cumulative_count

                # Obtener top 5 artistas para este sello en este año (no acumulativo)
                cursor.execute(f'''
                    SELECT s.artist, COUNT(*) as plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND strftime('%Y', datetime(s.timestamp, 'unixepoch')) = ?
                      AND al.label = ?
                    {mbid_filter}
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

        # 3. Top 10 artistas por año - ACUMULATIVO
        cursor.execute(f'''
            SELECT artist, COUNT(*) as total_plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
            ORDER BY total_plays DESC
            LIMIT 10
        ''', (user, int(datetime(from_year, 1, 1).timestamp()), int(datetime(to_year + 1, 1, 1).timestamp()) - 1))

        top_artists = [row['artist'] for row in cursor.fetchall()]

        artists_evolution = {}
        for artist in top_artists:
            artists_evolution[artist] = {}
            cumulative_count = 0
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                year_plays = result['plays'] if result else 0

                # Acumular
                cumulative_count += year_plays
                artists_evolution[artist][year] = cumulative_count

        evolution_data['artists'] = {
            'data': artists_evolution,
            'years': years,
            'names': top_artists
        }

        # 4. One hit wonders - ACUMULATIVO
        one_hit_wonders = self.get_one_hit_wonders_for_user(user, from_year, to_year, 25, 10, mbid_only)
        one_hit_evolution = {}
        one_hit_details = {}
        for artist_data in one_hit_wonders:
            artist = artist_data['name']
            one_hit_evolution[artist] = {}
            one_hit_details[artist] = {}
            cumulative_count = 0
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                year_plays = result['plays'] if result else 0

                # Acumular
                cumulative_count += year_plays
                one_hit_evolution[artist][year] = cumulative_count

                # Obtener la canción única
                cursor.execute(f'''
                    SELECT track, COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                    GROUP BY track
                    ORDER BY plays DESC
                    LIMIT 1
                ''', (user, artist, str(year)))
                track_result = cursor.fetchone()
                if track_result:
                    one_hit_details[artist][year] = {
                        'track': track_result['track'],
                        'plays': track_result['plays'],
                        'artist': artist
                    }
                else:
                    one_hit_details[artist][year] = {
                        'track': artist_data.get('track', 'N/A'),
                        'plays': 0,
                        'artist': artist
                    }

        evolution_data['one_hit_wonders'] = {
            'data': one_hit_evolution,
            'details': one_hit_details,
            'years': years,
            'names': [artist['name'] for artist in one_hit_wonders]
        }

        # 5. Streaks - ACUMULATIVO (días únicos)
        top_streak_artists_data = self.get_top_artists_by_streaks([user], from_year, to_year, 10, mbid_only).get(user, [])[:10]
        streak_evolution = {}
        streak_details = {}
        for artist_data in top_streak_artists_data:
            artist = artist_data['name']
            streak_evolution[artist] = {}
            streak_details[artist] = {}
            cumulative_days = 0
            for year in years:
                # Calcular días únicos por año
                cursor.execute(f'''
                    SELECT COUNT(DISTINCT date(datetime(timestamp, 'unixepoch'))) as days_count
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                year_days = result['days_count'] if result else 0

                # Acumular días únicos
                cumulative_days += year_days
                streak_evolution[artist][year] = cumulative_days

                streak_details[artist][year] = {
                    'days': year_days,
                    'max_streak': artist_data.get('max_streak', 0),
                    'total_days': artist_data.get('total_days', 0)
                }

        evolution_data['streak_artists'] = {
            'data': streak_evolution,
            'details': streak_details,
            'years': years,
            'names': [artist['name'] for artist in top_streak_artists_data]
        }

        # 6. Track count - ACUMULATIVO (canciones únicas)
        top_track_count_artists_data = self.get_top_artists_by_track_count([user], from_year, to_year, 10, mbid_only).get(user, [])[:10]
        track_count_evolution = {}
        track_count_details = {}
        for artist_data in top_track_count_artists_data:
            artist = artist_data['name']
            track_count_evolution[artist] = {}
            track_count_details[artist] = {}
            # Para track count acumulativo, necesitamos contar todas las canciones únicas hasta ese año
            all_tracks_so_far = set()
            for year in years:
                # Obtener canciones de este año
                cursor.execute(f'''
                    SELECT DISTINCT track
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                year_tracks = {row['track'] for row in cursor.fetchall()}

                # Agregar al conjunto acumulativo
                all_tracks_so_far.update(year_tracks)
                track_count_evolution[artist][year] = len(all_tracks_so_far)

                # Obtener top 10 álbumes para este año
                cursor.execute(f'''
                    SELECT album, COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                      AND album IS NOT NULL AND album != ''
                    {mbid_filter}
                    GROUP BY album
                    ORDER BY plays DESC
                    LIMIT 10
                ''', (user, artist, str(year)))
                albums = [{'name': row['album'], 'plays': row['plays']} for row in cursor.fetchall()]
                track_count_details[artist][year] = {'track_count': len(year_tracks), 'albums': albums}

        evolution_data['track_count_artists'] = {
            'data': track_count_evolution,
            'details': track_count_details,
            'years': years,
            'names': [artist['name'] for artist in top_track_count_artists_data]
        }

        # 7. New artists - ACUMULATIVO
        new_artists = self.get_new_artists_for_user(user, from_year, to_year, 10, mbid_only)
        new_artists_evolution = {}
        for artist_data in new_artists:
            artist = artist_data['name']
            new_artists_evolution[artist] = {}
            cumulative_count = 0
            for year in years:
                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                    {mbid_filter}
                ''', (user, artist, str(year)))
                result = cursor.fetchone()
                year_plays = result['plays'] if result else 0

                # Acumular
                cumulative_count += year_plays
                new_artists_evolution[artist][year] = cumulative_count

        evolution_data['new_artists'] = {
            'data': new_artists_evolution,
            'years': years,
            'names': [artist['name'] for artist in new_artists]
        }

        # 8. & 9. Rising and falling artists - ACUMULATIVO
        rising_artists = self.get_fastest_rising_artists(user, from_year, to_year, 10, mbid_only)
        falling_artists = self.get_fastest_falling_artists(user, from_year, to_year, 10, mbid_only)

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
                cumulative_count = 0
                for year in years:
                    cursor.execute(f'''
                        SELECT COUNT(*) as plays
                        FROM scrobbles s
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                        {mbid_filter}
                    ''', (user, artist, str(year)))
                    result = cursor.fetchone()
                    year_plays = result['plays'] if result else 0

                    # Acumular
                    cumulative_count += year_plays
                    category_evolution[artist][year] = cumulative_count

                    # Obtener top 10 canciones para este año
                    cursor.execute(f'''
                        SELECT track, COUNT(*) as plays
                        FROM scrobbles s
                        WHERE user = ? AND artist = ? AND strftime('%Y', datetime(timestamp, 'unixepoch')) = ?
                        {mbid_filter}
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

    def get_user_top_genres_by_provider(self, user: str, from_year: int, to_year: int, provider: str, limit: int = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene los géneros más escuchados por el usuario según el proveedor usando artists_genres_detailed - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        cursor.execute(f'''
            SELECT agd.genre, COUNT(*) as plays
            FROM scrobbles s
            JOIN artists_genres_detailed agd ON s.artist = agd.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND agd.source = ?
            {mbid_filter}
            GROUP BY agd.genre
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, provider, limit))

        return [(row['genre'], row['plays']) for row in cursor.fetchall()]

    def get_top_artists_for_genre_by_provider(self, user: str, genre: str, from_year: int, to_year: int, provider: str, limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Obtiene top artistas para un género específico por proveedor con datos temporales usando artists_genres_detailed - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener top artistas para este género
        cursor.execute(f'''
            SELECT s.artist, COUNT(*) as total_plays
            FROM scrobbles s
            JOIN artists_genres_detailed agd ON s.artist = agd.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND agd.genre = ? AND agd.source = ?
            {mbid_filter}
            GROUP BY s.artist
            ORDER BY total_plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, genre, provider, limit))

        artists = cursor.fetchall()
        artists_data = []

        for artist_row in artists:
            artist_name = artist_row['artist']

            # Obtener datos por año
            yearly_data = {}
            for year in range(from_year, to_year + 1):
                year_start = int(datetime(year, 1, 1).timestamp())
                year_end = int(datetime(year + 1, 1, 1).timestamp()) - 1

                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artists_genres_detailed agd ON s.artist = agd.artist
                    WHERE s.user = ? AND s.artist = ?
                      AND s.timestamp >= ? AND s.timestamp <= ?
                      AND agd.genre = ? AND agd.source = ?
                    {mbid_filter}
                ''', (user, artist_name, year_start, year_end, genre, provider))

                year_result = cursor.fetchone()
                yearly_data[year] = year_result['plays'] if year_result else 0

            artists_data.append({
                'artist': artist_name,
                'yearly_data': yearly_data,
                'total_plays': artist_row['total_plays']
            })

        return artists_data

    def get_user_top_album_genres_by_provider(self, user: str, from_year: int, to_year: int, provider: str, limit: int = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene los géneros de álbumes más escuchados por el usuario según el proveedor usando album_genres - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        cursor.execute(f'''
            SELECT ag.genre, COUNT(*) as plays
            FROM scrobbles s
            JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ag.source = ?
              AND s.album IS NOT NULL AND s.album != ''
            {mbid_filter}
            GROUP BY ag.genre
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, provider, limit))

        return [(row['genre'], row['plays']) for row in cursor.fetchall()]

    def get_top_albums_for_genre_by_provider(self, user: str, genre: str, from_year: int, to_year: int, provider: str, limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Obtiene top álbumes para un género específico por proveedor con datos temporales usando album_genres - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener top álbumes para este género
        cursor.execute(f'''
            SELECT s.artist, s.album, COUNT(*) as total_plays
            FROM scrobbles s
            JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ag.genre = ? AND ag.source = ?
              AND s.album IS NOT NULL AND s.album != ''
            {mbid_filter}
            GROUP BY s.artist, s.album
            ORDER BY total_plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, genre, provider, limit))

        albums = cursor.fetchall()
        albums_data = []

        for album_row in albums:
            artist_name = album_row['artist']
            album_name = album_row['album']
            album_key = f"{artist_name} - {album_name}"

            # Obtener datos por año
            yearly_data = {}
            for year in range(from_year, to_year + 1):
                year_start = int(datetime(year, 1, 1).timestamp())
                year_end = int(datetime(year + 1, 1, 1).timestamp()) - 1

                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
                    WHERE s.user = ? AND s.artist = ? AND s.album = ?
                      AND s.timestamp >= ? AND s.timestamp <= ?
                      AND ag.genre = ? AND ag.source = ?
                    {mbid_filter}
                ''', (user, artist_name, album_name, year_start, year_end, genre, provider))

                year_result = cursor.fetchone()
                yearly_data[year] = year_result['plays'] if year_result else 0

            albums_data.append({
                'album': album_key,
                'yearly_data': yearly_data,
                'total_plays': album_row['total_plays']
            })

        return albums_data

    def get_user_top_labels(self, user: str, from_year: int, to_year: int, limit: int = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene los sellos más escuchados por el usuario usando album_labels - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        cursor.execute(f'''
            SELECT al.label, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
              AND s.album IS NOT NULL AND s.album != ''
            {mbid_filter}
            GROUP BY al.label
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, limit))

        return [(row['label'], row['plays']) for row in cursor.fetchall()]

    def get_top_artists_for_label(self, user: str, label: str, from_year: int, to_year: int, limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """Obtiene top artistas para un sello específico con datos temporales usando album_labels - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener top artistas para este sello
        cursor.execute(f'''
            SELECT s.artist, COUNT(*) as total_plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label = ?
              AND s.album IS NOT NULL AND s.album != ''
            {mbid_filter}
            GROUP BY s.artist
            ORDER BY total_plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, label, limit))

        artists = cursor.fetchall()
        artists_data = []

        for artist_row in artists:
            artist_name = artist_row['artist']

            # Obtener datos por año
            yearly_data = {}
            for year in range(from_year, to_year + 1):
                year_start = int(datetime(year, 1, 1).timestamp())
                year_end = int(datetime(year + 1, 1, 1).timestamp()) - 1

                cursor.execute(f'''
                    SELECT COUNT(*) as plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND s.artist = ?
                      AND s.timestamp >= ? AND s.timestamp <= ?
                      AND al.label = ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                ''', (user, artist_name, year_start, year_end, label))

                year_result = cursor.fetchone()
                yearly_data[year] = year_result['plays'] if year_result else 0

            artists_data.append({
                'artist': artist_name,
                'yearly_data': yearly_data,
                'total_plays': artist_row['total_plays']
            })

        return artists_data

    def get_common_album_release_years_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int, mbid_only: bool = False) -> Dict[str, Dict[str, int]]:
        """Obtiene años de lanzamiento de álbumes comunes entre el usuario y otros usuarios - con filtro MBID"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        # Obtener años de lanzamiento del usuario principal
        cursor.execute(f'''
            SELECT ard.release_year, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ard.release_year IS NOT NULL
              AND s.album IS NOT NULL AND s.album != ''
            {mbid_filter}
            GROUP BY ard.release_year
        ''', (user, from_timestamp, to_timestamp))

        user_years = {row['release_year']: row['plays'] for row in cursor.fetchall()}

        if not user_years:
            return {}

        common_years = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute(f'''
                SELECT ard.release_year, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND ard.release_year IS NOT NULL
                  AND s.album IS NOT NULL AND s.album != ''
                  AND ard.release_year IN ({','.join(['?'] * len(user_years))})
                {mbid_filter}
                GROUP BY ard.release_year
            ''', [other_user, from_timestamp, to_timestamp] + list(user_years.keys()))

            other_user_years = {row['release_year']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias
            common = {}
            for year in user_years:
                if year in other_user_years:
                    common[str(year)] = {  # Convertir a string para consistencia
                        'user_plays': user_years[year],
                        'other_plays': other_user_years[year],
                        'total_plays': user_years[year] + other_user_years[year]
                    }

            if common:
                common_years[other_user] = common

        return common_years

    def close(self):
        """Cerrar conexión a la base de datos"""
        self.conn.close()

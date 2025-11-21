#!/usr/bin/env python3
"""
UserStatsDatabase - VersiÃ³n extendida con funciones faltantes para conteos Ãºnicos
AÃ±ade: get_user_top_artists, get_user_top_albums, get_user_top_tracks
Hereda de la clase original para mantener TODA la funcionalidad
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# Importar la clase original del proyecto
from .user_stats_database import UserStatsDatabase


class UserStatsDatabaseExtended(UserStatsDatabase):
    """VersiÃ³n extendida con funciones adicionales para conteos Ãºnicos"""

    def get_user_top_artists(self, user: str, from_year: int, to_year: int,
                           limit: Optional[int] = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene top artistas del usuario con conteo de reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        limit_clause = f"LIMIT {limit}" if limit else ""

        cursor.execute(f'''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
            ORDER BY plays DESC
            {limit_clause}
        ''', (user, from_timestamp, to_timestamp))

        return [(row['artist'], row['plays']) for row in cursor.fetchall()]

    def get_user_top_albums(self, user: str, from_year: int, to_year: int,
                          limit: Optional[int] = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene top Ã¡lbumes del usuario con conteo de reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        limit_clause = f"LIMIT {limit}" if limit else ""

        cursor.execute(f'''
            SELECT CASE
                WHEN album IS NULL OR album = '' THEN artist || ' - [Unknown Album]'
                ELSE artist || ' - ' || album
            END as album_display,
            COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist, album
            ORDER BY plays DESC
            {limit_clause}
        ''', (user, from_timestamp, to_timestamp))

        return [(row['album_display'], row['plays']) for row in cursor.fetchall()]

    def get_user_top_tracks(self, user: str, from_year: int, to_year: int,
                          limit: Optional[int] = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene top canciones del usuario con conteo de reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        limit_clause = f"LIMIT {limit}" if limit else ""

        cursor.execute(f'''
            SELECT artist || ' - ' || track as track_display, COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND track IS NOT NULL AND track != ''
            {mbid_filter}
            GROUP BY artist, track
            ORDER BY plays DESC
            {limit_clause}
        ''', (user, from_timestamp, to_timestamp))

        return [(row['track_display'], row['plays']) for row in cursor.fetchall()]

    def get_user_unique_count_artists(self, user: str, from_year: int, to_year: int,
                                    mbid_only: bool = False) -> int:
        """Obtiene el nÃºmero total de artistas Ãºnicos del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT artist) as unique_artists
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_artists'] if result else 0

    def get_user_unique_count_albums(self, user: str, from_year: int, to_year: int,
                                   mbid_only: bool = False) -> int:
        """Obtiene el nÃºmero total de Ã¡lbumes Ãºnicos del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT artist || '|' || COALESCE(album, '[Unknown Album]')) as unique_albums
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_albums'] if result else 0

    def get_user_unique_count_tracks(self, user: str, from_year: int, to_year: int,
                                   mbid_only: bool = False) -> int:
        """Obtiene el nÃºmero total de canciones Ãºnicas del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT artist || '|' || track) as unique_tracks
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND track IS NOT NULL AND track != ''
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_tracks'] if result else 0

    def get_user_unique_count_genres_by_provider(self, user: str, from_year: int, to_year: int,
                                               provider: str = 'lastfm', mbid_only: bool = False) -> int:
        """Obtiene el nÃºmero total de gÃ©neros Ãºnicos del usuario por proveedor"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        # Primero intentar con la tabla de gÃ©neros detallados
        cursor.execute(f'''
            SELECT COUNT(DISTINCT agd.genre) as unique_genres
            FROM scrobbles s
            JOIN artist_genres_detailed agd ON s.artist = agd.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND agd.source = ?
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp, provider))

        result = cursor.fetchone()
        count = result['unique_genres'] if result else 0

        # Si no hay datos, intentar con tabla antigua (fallback para Last.fm)
        if count == 0 and provider == 'lastfm':
            cursor.execute(f'''
                SELECT COUNT(DISTINCT genre_extracted.value) as unique_genres
                FROM scrobbles s
                JOIN artist_genres ag ON s.artist = ag.artist,
                json_each(ag.genres) AS genre_extracted
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND json_valid(ag.genres)
                {mbid_filter}
            ''', (user, from_timestamp, to_timestamp))

            result = cursor.fetchone()
            count = result['unique_genres'] if result else 0

        return count

    def get_user_unique_count_labels(self, user: str, from_year: int, to_year: int,
                                   mbid_only: bool = False) -> int:
        """Obtiene el nÃºmero total de sellos Ãºnicos del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT al.label) as unique_labels
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_labels'] if result else 0

    def get_user_discoveries_by_year(self, user: str, from_year: int, to_year: int,
                                   discovery_type: str = 'artists', mbid_only: bool = False) -> Dict[int, List[Dict]]:
        """
        Obtiene las novedades (primeras escuchas) del usuario por año

        Args:
            user: Usuario
            from_year: Año inicial
            to_year: Año final
            discovery_type: 'artists', 'albums', 'tracks', 'labels'
            mbid_only: Solo scrobbles con MBID

        Returns:
            Dict con año: [{'name': str, 'first_timestamp': int}]
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        discoveries_by_year = {}

        if discovery_type == 'artists':
            # Obtener primeras escuchas de artistas dentro del periodo
            cursor.execute('''
                SELECT artist, first_timestamp
                FROM user_first_artist_listen
                WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                ORDER BY first_timestamp ASC
            ''', (user, from_timestamp, to_timestamp))

            for row in cursor.fetchall():
                # Convertir timestamp a año
                first_date = datetime.fromtimestamp(row['first_timestamp'])
                year = first_date.year

                if year not in discoveries_by_year:
                    discoveries_by_year[year] = []

                discoveries_by_year[year].append({
                    'name': row['artist'],
                    'first_timestamp': row['first_timestamp'],
                    'first_date': first_date.strftime('%Y-%m-%d')
                })

        elif discovery_type == 'albums':
            cursor.execute('''
                SELECT artist, album, first_timestamp
                FROM user_first_album_listen
                WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                ORDER BY first_timestamp ASC
            ''', (user, from_timestamp, to_timestamp))

            for row in cursor.fetchall():
                first_date = datetime.fromtimestamp(row['first_timestamp'])
                year = first_date.year

                if year not in discoveries_by_year:
                    discoveries_by_year[year] = []

                album_display = f"{row['artist']} - {row['album']}" if row['album'] else f"{row['artist']} - [Unknown Album]"
                discoveries_by_year[year].append({
                    'name': album_display,
                    'first_timestamp': row['first_timestamp'],
                    'first_date': first_date.strftime('%Y-%m-%d')
                })

        elif discovery_type == 'tracks':
            cursor.execute('''
                SELECT artist, track, first_timestamp
                FROM user_first_track_listen
                WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                ORDER BY first_timestamp ASC
            ''', (user, from_timestamp, to_timestamp))

            for row in cursor.fetchall():
                first_date = datetime.fromtimestamp(row['first_timestamp'])
                year = first_date.year

                if year not in discoveries_by_year:
                    discoveries_by_year[year] = []

                discoveries_by_year[year].append({
                    'name': f"{row['artist']} - {row['track']}",
                    'first_timestamp': row['first_timestamp'],
                    'first_date': first_date.strftime('%Y-%m-%d')
                })

        elif discovery_type == 'labels':
            cursor.execute('''
                SELECT label, first_timestamp
                FROM user_first_label_listen
                WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                ORDER BY first_timestamp ASC
            ''', (user, from_timestamp, to_timestamp))

            for row in cursor.fetchall():
                first_date = datetime.fromtimestamp(row['first_timestamp'])
                year = first_date.year

                if year not in discoveries_by_year:
                    discoveries_by_year[year] = []

                discoveries_by_year[year].append({
                    'name': row['label'],
                    'first_timestamp': row['first_timestamp'],
                    'first_date': first_date.strftime('%Y-%m-%d')
                })

        return discoveries_by_year

    def get_user_discoveries_stats_by_year(self, user: str, from_year: int, to_year: int,
                                         discovery_type: str = 'artists', mbid_only: bool = False) -> Dict[int, int]:
        """
        Obtiene estadísticas de novedades por año (solo conteos)

        Returns:
            Dict con año: número_de_novedades
        """
        discoveries = self.get_user_discoveries_by_year(user, from_year, to_year, discovery_type, mbid_only)

        stats = {}
        for year in range(from_year, to_year + 1):
            stats[year] = len(discoveries.get(year, []))

        return stats

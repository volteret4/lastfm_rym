#!/usr/bin/env python3
"""
UserStatsDatabase - Versión extendida con funciones faltantes para conteos únicos
Añade: get_user_top_artists, get_user_top_albums, get_user_top_tracks
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
    """Versión extendida con funciones adicionales para conteos únicos"""

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
        """Obtiene top álbumes del usuario con conteo de reproducciones"""
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
        """Obtiene el número total de artistas únicos del usuario"""
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
        """Obtiene el número total de álbumes únicos del usuario"""
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
        """Obtiene el número total de canciones únicas del usuario"""
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

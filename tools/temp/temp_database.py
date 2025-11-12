#!/usr/bin/env python3
"""
Database module for Last.fm statistics
Módulo de base de datos para estadísticas de Last.fm
"""

import sqlite3
import json
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_path='db/lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_scrobbles(self, user: str, from_timestamp: int, to_timestamp: int) -> List[Dict]:
        """Obtiene scrobbles de un usuario en un rango de tiempo"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user, artist, track, album, timestamp
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
        ''', (user, from_timestamp, to_timestamp))
        return [dict(row) for row in cursor.fetchall()]

    def get_artist_genres(self, artist: str) -> List[str]:
        """Obtiene géneros de un artista"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT genres FROM artist_genres WHERE artist = ?', (artist,))
        result = cursor.fetchone()
        if result and result['genres']:
            return json.loads(result['genres'])
        return []

    def get_album_label(self, artist: str, album: str) -> Optional[str]:
        """Obtiene el sello discográfico de un álbum"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT label FROM album_labels WHERE artist = ? AND album = ?', (artist, album))
        result = cursor.fetchone()
        return result['label'] if result and result['label'] else None

    def get_album_release_year(self, artist: str, album: str) -> Optional[int]:
        """Obtiene el año de lanzamiento de un álbum"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT release_year FROM album_release_dates WHERE artist = ? AND album = ?', (artist, album))
        result = cursor.fetchone()
        return result['release_year'] if result and result['release_year'] else None

    def get_first_scrobble_date(self, user: str, artist: str = None, album: str = None, track: str = None) -> Optional[int]:
        """Obtiene la fecha del primer scrobble de un usuario para un elemento específico"""
        cursor = self.conn.cursor()

        if track and artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE user = ? AND artist = ? AND track = ?
            ''', (user, artist, track))
        elif album and artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE user = ? AND artist = ? AND album = ?
            ''', (user, artist, album))
        elif artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE user = ? AND artist = ?
            ''', (user, artist))
        else:
            return None

        result = cursor.fetchone()
        return result['first_scrobble'] if result and result['first_scrobble'] else None

    def get_global_first_scrobble_date(self, artist: str = None, album: str = None, track: str = None) -> Optional[int]:
        """Obtiene la fecha del primer scrobble global (cualquier usuario) para un elemento específico"""
        cursor = self.conn.cursor()

        if track and artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE artist = ? AND track = ?
            ''', (artist, track))
        elif album and artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE artist = ? AND album = ?
            ''', (artist, album))
        elif artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE artist = ?
            ''', (artist,))
        else:
            return None

        result = cursor.fetchone()
        return result['first_scrobble'] if result and result['first_scrobble'] else None

    def get_user_total_scrobbles(self, user: str, artist: str = None, album: str = None, track: str = None) -> int:
        """Obtiene el total de scrobbles de un usuario para un elemento específico"""
        cursor = self.conn.cursor()

        if track and artist:
            cursor.execute('''
                SELECT COUNT(*) as total_scrobbles
                FROM scrobbles
                WHERE user = ? AND artist = ? AND track = ?
            ''', (user, artist, track))
        elif album and artist:
            cursor.execute('''
                SELECT COUNT(*) as total_scrobbles
                FROM scrobbles
                WHERE user = ? AND artist = ? AND album = ?
            ''', (user, artist, album))
        elif artist:
            cursor.execute('''
                SELECT COUNT(*) as total_scrobbles
                FROM scrobbles
                WHERE user = ? AND artist = ?
            ''', (user, artist))
        else:
            return 0

        result = cursor.fetchone()
        return result['total_scrobbles'] if result else 0

    def close(self):
        """Cierra la conexión a la base de datos"""
        if self.conn:
            self.conn.close()

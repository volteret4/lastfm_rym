#!/usr/bin/env python3
"""
Last.fm Database Updater - Improved Version
Actualiza la base de datos con múltiples APIs de forma paralela y más eficiente
Mejoras: normalización de texto, búsquedas más precisas, backfill estable, actualización de géneros
"""

import os
import sys
import requests
import json
import sqlite3
import time
import argparse
import threading
import queue
import re
import unicodedata
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import urllib.parse

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_API_KEY') or not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass


@dataclass
class ScrobbleData:
    """Estructura de datos para un scrobble enriquecido"""
    user: str
    artist: str
    track: str
    album: str
    timestamp: int
    artist_mbid: Optional[str] = None
    album_mbid: Optional[str] = None
    track_mbid: Optional[str] = None


@dataclass
class ApiTask:
    """Estructura para tareas de API"""
    task_type: str
    entity_type: str  # 'artist', 'album', 'track'
    entity_id: str
    mbid: Optional[str] = None
    extra_data: Optional[Dict] = None


class TextNormalizer:
    """Utilidades para normalización de texto para búsquedas más efectivas"""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normaliza texto para comparación"""
        if not text:
            return ""

        # Convertir a minúsculas
        text = text.lower()

        # Normalizar unicode (NFD) y remover diacríticos
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

        # Remover caracteres especiales y espacios extra
        text = re.sub(r'[^\w\s]', ' ', text)
        text = ' '.join(text.split())

        return text.strip()

    @staticmethod
    def clean_for_search(text: str) -> Tuple[str, str]:
        """Limpia texto para búsqueda, devuelve versión limpia y original"""
        if not text:
            return "", ""

        original = text
        cleaned = text

        # Remover información entre paréntesis, corchetes, llaves
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
        cleaned = re.sub(r'\{[^}]*\}', '', cleaned)

        # Remover versiones especiales comunes
        special_versions = [
            r'\b(remaster(?:ed)?|deluxe|expanded|special|anniversary|edition|version)\b',
            r'\b(feat(?:uring)?|ft\.?|with)\s+[^-]*',
            r'\b(remix|mix|radio\s+edit|extended|acoustic)\b',
            r'\b\d+th\s+anniversary\b',
            r'\b(mono|stereo)\b'
        ]

        for pattern in special_versions:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Limpiar espacios extra y caracteres especiales
        cleaned = re.sub(r'[^\w\s\-]', ' ', cleaned)
        cleaned = ' '.join(cleaned.split())
        cleaned = cleaned.strip()

        return cleaned, original

    @staticmethod
    def generate_search_variants(text: str) -> List[str]:
        """Genera variantes de búsqueda para un texto"""
        if not text:
            return []

        variants = []
        cleaned, original = TextNormalizer.clean_for_search(text)

        # Versión original
        variants.append(original.strip())

        # Versión limpia si es diferente
        if cleaned != original and cleaned:
            variants.append(cleaned)

        # Versión súper limpia (solo alfanuméricos y espacios)
        super_clean = re.sub(r'[^\w\s]', ' ', cleaned)
        super_clean = ' '.join(super_clean.split())
        if super_clean and super_clean not in variants:
            variants.append(super_clean)

        return [v for v in variants if v]


class OptimizedDatabase:
    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()

        # Tabla de scrobbles existente
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrobbles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                artist TEXT NOT NULL,
                track TEXT NOT NULL,
                album TEXT,
                timestamp INTEGER NOT NULL,
                UNIQUE(user, timestamp, artist, track)
            )
        ''')

        # Índices existentes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_user_timestamp
            ON scrobbles(user, timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_artist_album
            ON scrobbles(artist, album)
        ''')

        # NUEVO: Índice para consultas de artistas escuchados por usuario (sugerido)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_user_artist
            ON scrobbles(user, artist)
        ''')

        # NUEVO: Índice para análisis temporales por artista
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_artist_timestamp
            ON scrobbles(artist, timestamp)
        ''')

        # NUEVO: Índice para consultas de tracks por usuario
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_user_track
            ON scrobbles(user, track)
        ''')

        # NUEVO: Índice compuesto para análisis detallados
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_user_artist_timestamp
            ON scrobbles(user, artist, timestamp)
        ''')

        # NUEVO: Índice para búsquedas de álbumes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_album_artist
            ON scrobbles(album, artist)
        ''')

        # NUEVO: Índice para análisis de tracks por artista
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_track_artist
            ON scrobbles(track, artist)
        ''')

        # Tablas existentes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_genres (
                artist TEXT PRIMARY KEY,
                genres TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_labels (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                label TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (artist, album)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_release_dates (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                release_year INTEGER,
                release_date TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (artist, album)
            )
        ''')

        # NUEVAS TABLAS - Añadir MBIDs a scrobbles
        try:
            cursor.execute('ALTER TABLE scrobbles ADD COLUMN artist_mbid TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE scrobbles ADD COLUMN album_mbid TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE scrobbles ADD COLUMN track_mbid TEXT')
        except sqlite3.OperationalError:
            pass

        # Nueva tabla: Información detallada de artistas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_details (
                artist TEXT PRIMARY KEY,
                mbid TEXT,
                begin_date TEXT,
                end_date TEXT,
                artist_type TEXT,
                country TEXT,
                disambiguation TEXT,
                similar_artists TEXT,
                last_updated INTEGER NOT NULL
            )
        ''')

        # Nueva tabla: Información detallada de álbumes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_details (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                mbid TEXT,
                release_group_mbid TEXT,
                original_release_date TEXT,
                album_type TEXT,
                status TEXT,
                packaging TEXT,
                country TEXT,
                barcode TEXT,
                catalog_number TEXT,
                total_tracks INTEGER,
                last_updated INTEGER NOT NULL,
                PRIMARY KEY (artist, album)
            )
        ''')

        # Nueva tabla: Información detallada de tracks
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS track_details (
                artist TEXT NOT NULL,
                track TEXT NOT NULL,
                mbid TEXT,
                duration_ms INTEGER,
                track_number INTEGER,
                album TEXT,
                isrc TEXT,
                last_updated INTEGER NOT NULL,
                PRIMARY KEY (artist, track)
            )
        ''')

        # Nueva tabla: Géneros por fuente
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_genres_detailed (
                artist TEXT NOT NULL,
                source TEXT NOT NULL,
                genre TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                last_updated INTEGER NOT NULL,
                PRIMARY KEY (artist, source, genre)
            )
        ''')

        # Nueva tabla: Géneros de álbumes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_genres (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                source TEXT NOT NULL,
                genre TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                last_updated INTEGER NOT NULL,
                PRIMARY KEY (artist, album, source, genre)
            )
        ''')

        # Nueva tabla: Cache de API requests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                response_data TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER
            )
        ''')

        # Índices para las nuevas tablas
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_artist_details_mbid ON artist_details(mbid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_album_details_mbid ON album_details(mbid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_track_details_mbid ON track_details(mbid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrobbles_artist_mbid ON scrobbles(artist_mbid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_cache_expires ON api_cache(expires_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_album_genres_artist_album ON album_genres(artist, album)')

        self.conn.commit()

    def get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Obtiene respuesta cacheada de API"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT response_data FROM api_cache WHERE cache_key = ? AND (expires_at IS NULL OR expires_at > ?)',
                (cache_key, int(time.time()))
            )
            result = cursor.fetchone()
            return json.loads(result['response_data']) if result else None

    def cache_response(self, cache_key: str, response_data: Dict, expires_in_seconds: Optional[int] = None):
        """Cachea respuesta de API"""
        with self.lock:
            expires_at = int(time.time()) + expires_in_seconds if expires_in_seconds else None
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO api_cache (cache_key, response_data, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (cache_key, json.dumps(response_data), int(time.time()), expires_at))
            self.conn.commit()

    def save_scrobbles_enhanced(self, scrobbles: List[ScrobbleData]):
        """Guarda scrobbles con MBIDs"""
        with self.lock:
            cursor = self.conn.cursor()
            for scrobble in scrobbles:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO scrobbles
                        (user, artist, track, album, timestamp, artist_mbid, album_mbid, track_mbid)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        scrobble.user,
                        scrobble.artist,
                        scrobble.track,
                        scrobble.album,
                        scrobble.timestamp,
                        scrobble.artist_mbid,
                        scrobble.album_mbid,
                        scrobble.track_mbid
                    ))
                except sqlite3.IntegrityError:
                    pass
            self.conn.commit()

    def save_artist_details(self, artist: str, details: Dict):
        """Guarda información detallada de artista"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO artist_details
                (artist, mbid, begin_date, end_date, artist_type, country,
                 disambiguation, similar_artists, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                artist,
                details.get('mbid'),
                details.get('begin_date'),
                details.get('end_date'),
                details.get('type'),
                details.get('country'),
                details.get('disambiguation'),
                json.dumps(details.get('similar_artists', [])),
                int(time.time())
            ))
            self.conn.commit()

    def save_album_details(self, artist: str, album: str, details: Dict):
        """Guarda información detallada de álbum"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_details
                (artist, album, mbid, release_group_mbid, original_release_date,
                 album_type, status, packaging, country, barcode, catalog_number,
                 total_tracks, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                artist, album,
                details.get('mbid'),
                details.get('release_group_mbid'),
                details.get('release_date'),
                details.get('type'),
                details.get('status'),
                details.get('packaging'),
                details.get('country'),
                details.get('barcode'),
                details.get('catalog_number'),
                details.get('total_tracks'),
                int(time.time())
            ))
            self.conn.commit()

    def save_track_details(self, artist: str, track: str, details: Dict):
        """Guarda información detallada de track"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO track_details
                (artist, track, mbid, duration_ms, track_number, album, isrc, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                artist, track,
                details.get('mbid'),
                details.get('duration_ms'),
                details.get('track_number'),
                details.get('album'),
                details.get('isrc'),
                int(time.time())
            ))
            self.conn.commit()

    def save_detailed_genres(self, artist: str, source: str, genres: List[Dict]):
        """Guarda géneros detallados por fuente"""
        with self.lock:
            cursor = self.conn.cursor()
            # Limpiar géneros existentes de esta fuente para este artista
            cursor.execute('DELETE FROM artist_genres_detailed WHERE artist = ? AND source = ?', (artist, source))

            for genre_info in genres:
                cursor.execute('''
                    INSERT INTO artist_genres_detailed (artist, source, genre, weight, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    artist, source,
                    genre_info.get('name', genre_info) if isinstance(genre_info, dict) else str(genre_info),
                    genre_info.get('weight', 1.0) if isinstance(genre_info, dict) else 1.0,
                    int(time.time())
                ))
            self.conn.commit()

    def save_album_genres(self, artist: str, album: str, source: str, genres: List[Dict]):
        """Guarda géneros de álbum por fuente"""
        with self.lock:
            cursor = self.conn.cursor()
            # Limpiar géneros existentes de esta fuente para este álbum
            cursor.execute('DELETE FROM album_genres WHERE artist = ? AND album = ? AND source = ?',
                         (artist, album, source))

            for genre_info in genres:
                cursor.execute('''
                    INSERT INTO album_genres (artist, album, source, genre, weight, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    artist, album, source,
                    genre_info.get('name', genre_info) if isinstance(genre_info, dict) else str(genre_info),
                    genre_info.get('weight', 1.0) if isinstance(genre_info, dict) else 1.0,
                    int(time.time())
                ))
            self.conn.commit()

    def get_scrobble_context_for_album(self, artist: str, album: str) -> Optional[str]:
        """Obtiene un track representativo para mejorar búsquedas de álbum"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT track FROM scrobbles
            WHERE artist = ? AND album = ?
            GROUP BY track
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ''', (artist, album))
        result = cursor.fetchone()
        return result['track'] if result else None

    def get_scrobble_context_for_track(self, artist: str, track: str) -> Optional[str]:
        """Obtiene un álbum representativo para mejorar búsquedas de track"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT album FROM scrobbles
            WHERE artist = ? AND track = ? AND album IS NOT NULL AND album != ""
            GROUP BY album
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ''', (artist, track))
        result = cursor.fetchone()
        return result['album'] if result else None

    # Métodos heredados de la clase Database original
    def save_album_label(self, artist: str, album: str, label: Optional[str]):
        """Guarda el sello de un álbum en la cache"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_labels (artist, album, label, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (artist, album, label, int(time.time())))
            self.conn.commit()

    def save_album_release_date(self, artist: str, album: str, release_year: Optional[int], release_date: Optional[str]):
        """Guarda la fecha de lanzamiento de un álbum en la cache"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_release_dates (artist, album, release_year, release_date, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (artist, album, release_year, release_date, int(time.time())))
            self.conn.commit()

    def save_artist_genres(self, artist: str, genres: List[str]):
        """Guarda géneros de un artista en la cache (formato original) - FIXED"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO artist_genres (artist, genres, updated_at)
                VALUES (?, ?, ?)
            ''', (artist, json.dumps(genres), int(time.time())))
            self.conn.commit()

    def get_artist_genres(self, artist: str) -> Optional[List[str]]:
        """Obtiene géneros de un artista desde la cache"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT genres FROM artist_genres WHERE artist = ?',
            (artist,)
        )
        result = cursor.fetchone()
        if result:
            return json.loads(result['genres'])
        return None

    def get_album_label(self, artist: str, album: str) -> Optional[str]:
        """Obtiene el sello de un álbum desde la cache"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT label FROM album_labels WHERE artist = ? AND album = ?',
            (artist, album)
        )
        result = cursor.fetchone()
        return result['label'] if result else None

    def get_album_release_date(self, artist: str, album: str) -> Optional[Dict]:
        """Obtiene la fecha de lanzamiento de un álbum desde la cache"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT release_year, release_date FROM album_release_dates WHERE artist = ? AND album = ?',
            (artist, album)
        )
        result = cursor.fetchone()
        if result:
            return {
                'year': result['release_year'],
                'date': result['release_date']
            }
        return None

    def get_all_artists(self) -> List[str]:
        """Obtiene todos los artistas únicos de la base de datos"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist FROM scrobbles')
        return [row['artist'] for row in cursor.fetchall()]

    def get_all_albums(self) -> List[Dict]:
        """Obtiene todos los álbumes únicos de la base de datos"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist, album FROM scrobbles WHERE album IS NOT NULL AND album != ""')
        return [{'artist': row['artist'], 'album': row['album']} for row in cursor.fetchall()]

    def get_albums_without_dates(self) -> List[Dict]:
        """Obtiene álbumes que no tienen fecha de lanzamiento"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist, s.album
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.album IS NOT NULL
            AND s.album != ''
            AND ard.release_year IS NULL
        ''')
        return [{'artist': row[0], 'album': row[1]} for row in cursor.fetchall()]

    def save_scrobbles(self, scrobbles: List[Dict]):
        """Guarda scrobbles en formato original (sin MBIDs)"""
        with self.lock:
            cursor = self.conn.cursor()
            for scrobble in scrobbles:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO scrobbles (user, artist, track, album, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        scrobble['user'],
                        scrobble['artist'],
                        scrobble['track'],
                        scrobble['album'],
                        scrobble['timestamp']
                    ))
                except sqlite3.IntegrityError:
                    pass
            self.conn.commit()

    def get_entities_needing_enrichment(self, limit: int = 1000) -> Dict[str, Set[str]]:
        """Obtiene entidades que necesitan enriquecimiento"""
        with self.lock:
            cursor = self.conn.cursor()

            # Artistas sin detalles
            cursor.execute('''
                SELECT DISTINCT s.artist
                FROM scrobbles s
                LEFT JOIN artist_details ad ON s.artist = ad.artist
                WHERE ad.artist IS NULL
                LIMIT ?
            ''', (limit,))
            artists = {row[0] for row in cursor.fetchall()}

            # Álbumes sin detalles
            cursor.execute('''
                SELECT DISTINCT s.artist, s.album
                FROM scrobbles s
                LEFT JOIN album_details ald ON s.artist = ald.artist AND s.album = ald.album
                WHERE s.album IS NOT NULL AND s.album != '' AND ald.artist IS NULL
                LIMIT ?
            ''', (limit,))
            albums = {f"{row[0]}|||{row[1]}" for row in cursor.fetchall()}

            # Tracks sin detalles
            cursor.execute('''
                SELECT DISTINCT s.artist, s.track
                FROM scrobbles s
                LEFT JOIN track_details td ON s.artist = td.artist AND s.track = td.track
                WHERE td.artist IS NULL
                LIMIT ?
            ''', (limit,))
            tracks = {f"{row[0]}|||{row[1]}" for row in cursor.fetchall()}

            return {
                'artists': artists,
                'albums': albums,
                'tracks': tracks
            }

    # Métodos existentes del Database original
    def get_last_scrobble_timestamp(self, user: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT MAX(timestamp) as max_ts FROM scrobbles WHERE user = ?',
            (user,)
        )
        result = cursor.fetchone()
        return result['max_ts'] if result['max_ts'] else 0

    def get_first_scrobble_timestamp(self, user: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT MIN(timestamp) as min_ts FROM scrobbles WHERE user = ?',
            (user,)
        )
        result = cursor.fetchone()
        return result['min_ts'] if result['min_ts'] else 0

    def get_user_scrobble_count(self, user: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) as count FROM scrobbles WHERE user = ?',
            (user,)
        )
        result = cursor.fetchone()
        return result['count'] if result else 0

    def clear_user_scrobbles(self, user: str):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM scrobbles WHERE user = ?', (user,))
            self.conn.commit()
            print(f"   🗑️ Scrobbles anteriores de {user} eliminados")

    def close(self):
        self.conn.close()


class ApiClient:
    """Cliente base para APIs con mejor manejo de errores"""
    def __init__(self, base_url: str, rate_limit_delay: float = 0.2):
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.last_request_time = 0
        self.lock = threading.Lock()
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5

    def _rate_limit(self):
        """Implementa rate limiting"""
        with self.lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
            self.last_request_time = time.time()

    def get(self, url: str, params: Dict = None, headers: Dict = None, timeout: int = 15) -> Optional[Dict]:
        """Realiza request con rate limiting y mejor manejo de errores"""
        if self.consecutive_errors >= self.max_consecutive_errors:
            print(f"   ⚠️ Demasiados errores consecutivos en {self.base_url}. Saltando...")
            return None

        self._rate_limit()
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=timeout)

            if response.status_code == 200:
                self.consecutive_errors = 0  # Reset error counter on success
                return response.json()
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"   ⏳ Rate limit en {self.base_url}. Esperando {retry_after}s...")
                time.sleep(retry_after)
                return self.get(url, params, headers, timeout)
            elif response.status_code in [502, 503, 504]:
                # Server errors - retry once after delay
                print(f"   ⚠️ Error de servidor ({response.status_code}) en {self.base_url}. Reintentando...")
                time.sleep(5)
                response = self.session.get(url, params=params, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    self.consecutive_errors = 0
                    return response.json()

            self.consecutive_errors += 1
            return None

        except requests.exceptions.Timeout:
            print(f"   ⏱️ Timeout en {self.base_url}")
            self.consecutive_errors += 1
            return None
        except requests.exceptions.ConnectionError:
            print(f"   🔌 Error de conexión en {self.base_url}")
            self.consecutive_errors += 1
            time.sleep(2)  # Brief pause before next attempt
            return None
        except Exception as e:
            print(f"   ⚠️ Error en {self.base_url}: {e}")
            self.consecutive_errors += 1
            return None


class LastFMClient(ApiClient):
    def __init__(self, api_key: str):
        super().__init__("http://ws.audioscrobbler.com/2.0/", 0.25)
        self.api_key = api_key

    def get_recent_tracks_enhanced(self, user: str, page: int = 1, limit: int = 200,
                                 from_timestamp: Optional[int] = None,
                                 to_timestamp: Optional[int] = None) -> Optional[Dict]:
        """Obtiene tracks recientes con MBIDs"""
        params = {
            'method': 'user.getrecenttracks',
            'user': user,
            'api_key': self.api_key,
            'format': 'json',
            'page': str(page),
            'limit': str(limit),
            'extended': '1'  # Para obtener MBIDs
        }

        if from_timestamp:
            params['from'] = str(from_timestamp)
        if to_timestamp:
            params['to'] = str(to_timestamp)

        return self.get(self.base_url, params)

    def get_artist_info(self, artist: str, mbid: Optional[str] = None) -> Optional[Dict]:
        """Obtiene información detallada del artista"""
        params = {
            'method': 'artist.getinfo',
            'api_key': self.api_key,
            'format': 'json'
        }

        if mbid:
            params['mbid'] = mbid
        else:
            params['artist'] = artist

        return self.get(self.base_url, params)

    def get_album_info(self, artist: str, album: str, mbid: Optional[str] = None) -> Optional[Dict]:
        """Obtiene información detallada del álbum"""
        params = {
            'method': 'album.getinfo',
            'api_key': self.api_key,
            'format': 'json'
        }

        if mbid:
            params['mbid'] = mbid
        else:
            params['artist'] = artist
            params['album'] = album

        return self.get(self.base_url, params)

    def get_track_info(self, artist: str, track: str, mbid: Optional[str] = None) -> Optional[Dict]:
        """Obtiene información detallada del track"""
        params = {
            'method': 'track.getinfo',
            'api_key': self.api_key,
            'format': 'json'
        }

        if mbid:
            params['mbid'] = mbid
        else:
            params['artist'] = artist
            params['track'] = track

        return self.get(self.base_url, params)

    def get_similar_artists(self, artist: str, mbid: Optional[str] = None) -> Optional[Dict]:
        """Obtiene artistas similares"""
        params = {
            'method': 'artist.getsimilar',
            'api_key': self.api_key,
            'format': 'json'
        }

        if mbid:
            params['mbid'] = mbid
        else:
            params['artist'] = artist

        return self.get(self.base_url, params)


class MusicBrainzClient(ApiClient):
    def __init__(self):
        super().__init__("https://musicbrainz.org/ws/2/", 1.1)  # Rate limit más estricto
        self.session.headers.update({
            'User-Agent': 'LastFM-Database-Updater/2.0 (contact@example.com)'
        })

    def search_artist(self, artist_name: str) -> Optional[Dict]:
        """Busca artista en MusicBrainz con múltiples estrategias"""
        search_variants = TextNormalizer.generate_search_variants(artist_name)

        for variant in search_variants:
            params = {
                'query': f'artist:"{variant}"',
                'fmt': 'json',
                'limit': 5
            }
            result = self.get(f"{self.base_url}artist/", params)
            if result and result.get('artists'):
                return result

        return None

    def get_artist_by_mbid(self, mbid: str) -> Optional[Dict]:
        """Obtiene artista por MBID"""
        params = {'fmt': 'json', 'inc': 'genres+tags'}
        return self.get(f"{self.base_url}artist/{mbid}", params)

    def search_release(self, artist: str, album: str, track_hint: Optional[str] = None) -> Optional[Dict]:
        """Busca release en MusicBrainz con contexto mejorado"""
        album_variants = TextNormalizer.generate_search_variants(album)
        artist_variants = TextNormalizer.generate_search_variants(artist)

        for album_variant in album_variants:
            for artist_variant in artist_variants:
                # Búsqueda básica
                query = f'release:"{album_variant}" AND artist:"{artist_variant}"'
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': 5
                }
                result = self.get(f"{self.base_url}release/", params)
                if result and result.get('releases'):
                    return result

                # Si tenemos un track como contexto, usarlo también
                if track_hint:
                    track_clean, _ = TextNormalizer.clean_for_search(track_hint)
                    if track_clean:
                        query_with_track = f'release:"{album_variant}" AND artist:"{artist_variant}" AND recording:"{track_clean}"'
                        params['query'] = query_with_track
                        result = self.get(f"{self.base_url}release/", params)
                        if result and result.get('releases'):
                            return result

        return None

    def get_release_by_mbid(self, mbid: str) -> Optional[Dict]:
        """Obtiene release por MBID"""
        params = {'fmt': 'json', 'inc': 'release-groups+labels+recordings+genres+tags'}
        return self.get(f"{self.base_url}release/{mbid}", params)

    def search_recording(self, artist: str, track: str, album_hint: Optional[str] = None) -> Optional[Dict]:
        """Busca recording en MusicBrainz con contexto mejorado"""
        track_variants = TextNormalizer.generate_search_variants(track)
        artist_variants = TextNormalizer.generate_search_variants(artist)

        for track_variant in track_variants:
            for artist_variant in artist_variants:
                # Búsqueda básica
                query = f'recording:"{track_variant}" AND artist:"{artist_variant}"'
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': 5
                }
                result = self.get(f"{self.base_url}recording/", params)
                if result and result.get('recordings'):
                    return result

                # Si tenemos un álbum como contexto, usarlo también
                if album_hint:
                    album_clean, _ = TextNormalizer.clean_for_search(album_hint)
                    if album_clean:
                        query_with_album = f'recording:"{track_variant}" AND artist:"{artist_variant}" AND release:"{album_clean}"'
                        params['query'] = query_with_album
                        result = self.get(f"{self.base_url}recording/", params)
                        if result and result.get('recordings'):
                            return result

        return None

    def get_recording_by_mbid(self, mbid: str) -> Optional[Dict]:
        """Obtiene recording por MBID"""
        params = {'fmt': 'json', 'inc': 'releases+genres+tags'}
        return self.get(f"{self.base_url}recording/{mbid}", params)


class DiscogsClient(ApiClient):
    def __init__(self, token: str):
        super().__init__("https://api.discogs.com/", 1.0)
        self.token = token
        if token:
            self.session.headers.update({
                'Authorization': f'Discogs token={token}'
            })

    def search_release(self, artist: str, album: str) -> Optional[Dict]:
        """Busca release en Discogs con múltiples variantes"""
        if not self.token:
            return None

        artist_variants = TextNormalizer.generate_search_variants(artist)
        album_variants = TextNormalizer.generate_search_variants(album)

        for artist_variant in artist_variants[:2]:  # Limitar variantes para evitar exceso de requests
            for album_variant in album_variants[:2]:
                params = {
                    'q': f'{artist_variant} {album_variant}',
                    'type': 'release',
                    'per_page': 5
                }
                result = self.get(f"{self.base_url}database/search", params)
                if result and result.get('results'):
                    return result

        return None

    def get_release_details(self, release_id: str) -> Optional[Dict]:
        """Obtiene detalles de release"""
        if not self.token:
            return None

        return self.get(f"{self.base_url}releases/{release_id}")


class OptimizedLastFMUpdater:
    def __init__(self):
        # Configuración
        self.lastfm_api_key = os.getenv('LASTFM_API_KEY')
        self.discogs_token = os.getenv('DISCOGS_TOKEN', '')
        self.users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]

        if not self.lastfm_api_key:
            raise ValueError("LASTFM_API_KEY no encontrada")
        if not self.users:
            raise ValueError("LASTFM_USERS no encontrada")

        # Clientes API
        self.lastfm = LastFMClient(self.lastfm_api_key)
        self.musicbrainz = MusicBrainzClient()
        self.discogs = DiscogsClient(self.discogs_token)

        # Base de datos
        self.db = OptimizedDatabase()

    def parse_enhanced_scrobbles(self, track_data: List[Dict], user: str, fetch_name_from_mb_if_missing: bool = True) -> List[ScrobbleData]:
        """Convierte datos de Last.fm a ScrobbleData con MBIDs.
        Más tolerante ante diferentes formas de respuesta de la API.
        Si fetch_name_from_mb_if_missing=True, intenta recuperar el nombre desde MusicBrainz si sólo hay MBID.
        """
        def extract_text(obj, prefer_keys=('#text', 'name', 'title')):
            # obj puede ser dict o string. Intentamos varias claves en orden.
            if isinstance(obj, dict):
                for k in prefer_keys:
                    v = obj.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                # a veces Last.fm devuelve {'#text': '', 'mbid': '...'}
                # en ese caso devolvemos '' y el llamador podrá intentar otro fallback
                return ''
            elif obj is None:
                return ''
            else:
                return str(obj).strip()

        scrobbles = []

        for track in track_data:
            # Saltar "now playing"
            if '@attr' in track and 'nowplaying' in track['@attr']:
                continue
            if 'date' not in track:
                continue

            artist_data = track.get('artist', {})
            album_data = track.get('album', {})

            # Extraer MBIDs primero porque a veces '#text' está vacío
            artist_mbid = None
            album_mbid = None
            if isinstance(artist_data, dict):
                artist_mbid = artist_data.get('mbid')
            if isinstance(album_data, dict):
                album_mbid = album_data.get('mbid')
            track_mbid = track.get('mbid')

            # Normalizar MBIDs vacíos
            artist_mbid = artist_mbid if isinstance(artist_mbid, str) and artist_mbid.strip() else None
            album_mbid = album_mbid if isinstance(album_mbid, str) and album_mbid.strip() else None
            track_mbid = track_mbid if isinstance(track_mbid, str) and track_mbid.strip() else None

            # Extraer nombres (varias posibilidades)
            artist = extract_text(artist_data)
            album = extract_text(album_data)
            track_name = track.get('name') or extract_text(track.get('name') if isinstance(track.get('name'), (dict, str)) else None)
            if isinstance(track_name, dict):
                track_name = extract_text(track_name)

            # Si no hay nombre de artista pero sí MBID, intentar MusicBrainz (opcional)
            if (not artist) and artist_mbid and fetch_name_from_mb_if_missing:
                try:
                    mb = self.musicbrainz.get_artist_by_mbid(artist_mbid)
                    if mb and isinstance(mb, dict):
                        # MusicBrainz devuelve 'name'
                        maybe_name = mb.get('name') or mb.get('sort-name')
                        if isinstance(maybe_name, str) and maybe_name.strip():
                            artist = maybe_name.strip()
                except Exception:
                    # No queremos que falle el parsing por una caída externa
                    pass

            # Si aún está vacío, como último recurso usar el mbid (útil para debug)
            if not artist and artist_mbid:
                artist = artist_mbid

            # timestamp - safe parse
            try:
                timestamp = int(track['date']['uts'])
            except Exception:
                # si por alguna razón no existe, saltamos
                continue

            scrobble = ScrobbleData(
                user=user,
                artist=artist,
                track=track_name or '',
                album=album,
                timestamp=timestamp,
                artist_mbid=artist_mbid,
                album_mbid=album_mbid,
                track_mbid=track_mbid
            )
            scrobbles.append(scrobble)

        return scrobbles

    def update_user_scrobbles_enhanced(self, user: str, download_all: bool = False, backfill: bool = False):
        """Actualiza scrobbles con datos enriquecidos y mejor estabilidad para backfill"""
        print(f"\n👤 Actualizando scrobbles para: {user}")

        if download_all:
            self.db.clear_user_scrobbles(user)
            from_timestamp = None
            to_timestamp = None
            mode = "Descarga completa"
        elif backfill:
            first_scrobble = self.db.get_first_scrobble_timestamp(user)
            if first_scrobble == 0:
                print(f"   ℹ️ No hay scrobbles. Usa --all primero.")
                return
            to_timestamp = first_scrobble - 1
            from_timestamp = None
            mode = "Backfill histórico"
        else:
            from_timestamp = self.db.get_last_scrobble_timestamp(user)
            to_timestamp = None
            mode = "Actualización incremental"

        print(f"   🔄 Modo: {mode}")

        all_scrobbles = []
        page = 1
        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                data = self.lastfm.get_recent_tracks_enhanced(
                    user, page, 200, from_timestamp, to_timestamp
                )

                if not data or 'recenttracks' not in data:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"   ⚠️ Demasiados errores consecutivos. Guardando datos obtenidos...")
                        break
                    print(f"   ⚠️ Error en página {page}. Reintentando en 5s...")
                    time.sleep(5)
                    continue

                # Reset error counter on success
                consecutive_errors = 0

                total_pages = int(data['recenttracks']['@attr']['totalPages'])

                if page == 1:
                    total_tracks = int(data['recenttracks']['@attr']['total'])
                    print(f"   🎵 {total_tracks} scrobbles a procesar ({total_pages} páginas)")

                if page > total_pages:
                    break

                track_data = data['recenttracks'].get('track', [])
                if isinstance(track_data, dict):
                    track_data = [track_data]

                # Convertir a ScrobbleData
                page_scrobbles = self.parse_enhanced_scrobbles(track_data, user)
                all_scrobbles.extend(page_scrobbles)

                # Para backfill con muchas páginas, guardar cada cierto número de páginas
                if backfill and len(all_scrobbles) >= 2000:  # Guardar cada 2000 scrobbles
                    self.db.save_scrobbles_enhanced(all_scrobbles)
                    print(f"   💾 Guardados {len(all_scrobbles)} scrobbles (página {page}/{total_pages})")
                    all_scrobbles = []

                if total_pages > 10 and page % 25 == 0:
                    print(f"   📄 Página {page}/{total_pages} procesada")

                page += 1

                # Para usuarios con miles de páginas, añadir pequeña pausa cada 100 páginas
                if page % 100 == 0:
                    print(f"   ⏸️ Pausa breve en página {page}...")
                    time.sleep(2)

            except KeyboardInterrupt:
                print(f"\n   ⚠️ Interrumpido por el usuario. Guardando datos obtenidos...")
                break
            except Exception as e:
                consecutive_errors += 1
                print(f"   ⚠️ Error en página {page}: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    print(f"   ❌ Demasiados errores. Guardando datos obtenidos...")
                    break
                time.sleep(5)

        # Guardar scrobbles restantes
        if all_scrobbles:
            self.db.save_scrobbles_enhanced(all_scrobbles)
            print(f"   ✅ {len(all_scrobbles)} scrobbles guardados con MBIDs")

    def enrich_entities_parallel(self, max_workers: int = 3, limit: int = 1000):
        """Enriquece entidades usando múltiples APIs en paralelo"""
        print(f"\n🔍 Enriqueciendo datos de entidades (límite: {limit})...")

        entities = self.db.get_entities_needing_enrichment(limit=limit)

        print(f"   👥 {len(entities['artists'])} artistas por enriquecer")
        print(f"   💿 {len(entities['albums'])} álbumes por enriquecer")
        print(f"   🎵 {len(entities['tracks'])} tracks por enriquecer")

        if not any(entities.values()):
            print(f"   ✅ Todas las entidades ya están enriquecidas")
            return

        # Crear tareas
        tasks = []

        # Tareas de artistas (prioridad alta)
        for artist in entities['artists']:
            tasks.append(ApiTask('artist', 'artist', artist))

        # Tareas de álbumes
        for album_key in entities['albums']:
            artist, album = album_key.split('|||')
            tasks.append(ApiTask('album', 'album', f"{artist}|||{album}"))

        # Tareas de tracks
        for track_key in entities['tracks']:
            artist, track = track_key.split('|||')
            tasks.append(ApiTask('track', 'track', f"{artist}|||{track}"))

        # Procesar en paralelo
        completed_count = 0
        total_tasks = len(tasks)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.process_entity_task, task) for task in tasks]

            for future in as_completed(futures):
                completed_count += 1
                if completed_count % 50 == 0 or completed_count == total_tasks:
                    print(f"   📄 {completed_count}/{total_tasks} entidades procesadas")
                try:
                    future.result()
                except Exception as e:
                    print(f"   ⚠️ Error procesando entidad: {e}")

        print(f"   ✅ Enriquecimiento completado")

    def process_entity_task(self, task: ApiTask):
        """Procesa una tarea de enriquecimiento"""
        try:
            if task.task_type == 'artist':
                self.enrich_artist(task.entity_id)
            elif task.task_type == 'album':
                artist, album = task.entity_id.split('|||')
                self.enrich_album(artist, album)
            elif task.task_type == 'track':
                artist, track = task.entity_id.split('|||')
                self.enrich_track(artist, track)
        except Exception as e:
            print(f"   ⚠️ Error en tarea {task.task_type}: {e}")

    def enrich_artist(self, artist_name: str):
        """Enriquece datos de artista usando múltiples APIs con mejor búsqueda"""
        cache_key = f"artist_enrich_v2_{artist_name}"

        # Verificar cache
        cached = self.db.get_cached_response(cache_key)
        if cached:
            return

        details = {}
        found_genres = False

        # 1. Last.fm para géneros y similares
        lastfm_data = self.lastfm.get_artist_info(artist_name)
        if lastfm_data and 'artist' in lastfm_data:
            artist_info = lastfm_data['artist']

            # Géneros de Last.fm - FIXED: Actualizar tabla artist_genres
            if 'tags' in artist_info and 'tag' in artist_info['tags']:
                lastfm_genres = [
                    {'name': tag['name'], 'weight': float(tag.get('count', 1))}
                    for tag in artist_info['tags']['tag'][:10]
                ]
                self.db.save_detailed_genres(artist_name, 'lastfm', lastfm_genres)

                # FIXED: También actualizar la tabla artist_genres original
                genre_names = [genre['name'] for genre in lastfm_genres]
                if genre_names:
                    self.db.save_artist_genres(artist_name, genre_names)
                    found_genres = True

            # Artistas similares
            similar_data = self.lastfm.get_similar_artists(artist_name)
            if similar_data and 'similarartists' in similar_data:
                similar_artists = [
                    a['name'] for a in similar_data['similarartists'].get('artist', [])[:10]
                ]
                details['similar_artists'] = similar_artists

            # MBID de Last.fm
            if 'mbid' in artist_info and artist_info['mbid']:
                details['mbid'] = artist_info['mbid']

        # 2. MusicBrainz para datos oficiales
        mb_data = None
        if 'mbid' in details:
            mb_data = self.musicbrainz.get_artist_by_mbid(details['mbid'])
        else:
            # Búsqueda mejorada en MusicBrainz
            search_result = self.musicbrainz.search_artist(artist_name)
            if search_result and 'artists' in search_result and search_result['artists']:
                best_match = search_result['artists'][0]
                details['mbid'] = best_match['id']
                mb_data = self.musicbrainz.get_artist_by_mbid(details['mbid'])

        if mb_data:
            details.update({
                'begin_date': mb_data.get('life-span', {}).get('begin'),
                'end_date': mb_data.get('life-span', {}).get('end'),
                'type': mb_data.get('type'),
                'country': mb_data.get('country'),
                'disambiguation': mb_data.get('disambiguation')
            })

            # Géneros de MusicBrainz
            mb_genres = []
            if 'genres' in mb_data and mb_data['genres']:
                mb_genres = [
                    {'name': g['name'], 'weight': 1.0}
                    for g in mb_data['genres']
                ]
            elif 'tags' in mb_data and mb_data['tags']:
                # Si no hay géneros, usar tags
                mb_genres = [
                    {'name': t['name'], 'weight': float(t.get('count', 1))}
                    for t in mb_data['tags'][:10]
                ]

            if mb_genres:
                self.db.save_detailed_genres(artist_name, 'musicbrainz', mb_genres)

                # Si no encontramos géneros en Last.fm, usar los de MusicBrainz para la tabla original
                if not found_genres:
                    genre_names = [genre['name'] for genre in mb_genres]
                    self.db.save_artist_genres(artist_name, genre_names)

        # Guardar detalles del artista
        self.db.save_artist_details(artist_name, details)

        # Cachear resultado
        self.db.cache_response(cache_key, {'processed': True}, 86400)  # 24 horas

    def enrich_album(self, artist: str, album: str):
        """Enriquece datos de álbum con búsqueda mejorada"""
        cache_key = f"album_enrich_v2_{artist}_{album}"

        if self.db.get_cached_response(cache_key):
            return

        details = {}

        # Obtener contexto de track para mejorar búsquedas
        track_hint = self.db.get_scrobble_context_for_album(artist, album)

        # 1. Last.fm
        lastfm_data = self.lastfm.get_album_info(artist, album)
        if lastfm_data and 'album' in lastfm_data:
            album_info = lastfm_data['album']
            if 'mbid' in album_info and album_info['mbid']:
                details['mbid'] = album_info['mbid']

        # 2. MusicBrainz con búsqueda mejorada
        mb_data = None
        if 'mbid' in details:
            mb_data = self.musicbrainz.get_release_by_mbid(details['mbid'])
        else:
            # Búsqueda mejorada con contexto de track
            search_result = self.musicbrainz.search_release(artist, album, track_hint)
            if search_result and 'releases' in search_result and search_result['releases']:
                best_match = search_result['releases'][0]
                details['mbid'] = best_match['id']
                mb_data = self.musicbrainz.get_release_by_mbid(details['mbid'])

        if mb_data:
            details.update({
                'release_group_mbid': mb_data.get('release-group', {}).get('id'),
                'release_date': mb_data.get('date'),
                'type': mb_data.get('release-group', {}).get('primary-type'),
                'status': mb_data.get('status'),
                'packaging': mb_data.get('packaging'),
                'country': mb_data.get('country'),
                'barcode': mb_data.get('barcode'),
                'total_tracks': len(mb_data.get('media', [{}])[0].get('tracks', []))
            })

            # Labels de MusicBrainz
            if 'label-info' in mb_data and mb_data['label-info']:
                label = mb_data['label-info'][0]['label']['name']
                self.db.save_album_label(artist, album, label)

            # Géneros del álbum de MusicBrainz
            mb_album_genres = []
            if 'genres' in mb_data and mb_data['genres']:
                mb_album_genres = [
                    {'name': g['name'], 'weight': 1.0}
                    for g in mb_data['genres']
                ]
            elif 'tags' in mb_data and mb_data['tags']:
                mb_album_genres = [
                    {'name': t['name'], 'weight': float(t.get('count', 1))}
                    for t in mb_data['tags'][:10]
                ]

            if mb_album_genres:
                self.db.save_album_genres(artist, album, 'musicbrainz', mb_album_genres)

            # Guardar fecha de lanzamiento en el formato original también
            if mb_data.get('date'):
                try:
                    release_year = int(mb_data.get('date')[:4])
                    self.db.save_album_release_date(artist, album, release_year, mb_data.get('date'))
                except (ValueError, TypeError):
                    pass

        # 3. Discogs como fallback
        if not details.get('release_date') and self.discogs.token:
            discogs_data = self.discogs.search_release(artist, album)
            if discogs_data and 'results' in discogs_data and discogs_data['results']:
                result = discogs_data['results'][0]

                if result.get('year'):
                    details['release_date'] = str(result.get('year'))
                    # Guardar fecha de lanzamiento de Discogs en formato original
                    try:
                        release_year = int(result.get('year'))
                        self.db.save_album_release_date(artist, album, release_year, str(release_year))
                    except (ValueError, TypeError):
                        pass

                if 'label' in result and result['label']:
                    self.db.save_album_label(artist, album, result['label'][0])

                # Géneros de Discogs
                if 'genre' in result and result['genre']:
                    discogs_genres = [
                        {'name': genre, 'weight': 1.0}
                        for genre in result['genre'][:10]
                    ]
                    self.db.save_album_genres(artist, album, 'discogs', discogs_genres)

        self.db.save_album_details(artist, album, details)
        self.db.cache_response(cache_key, {'processed': True}, 86400)

    def enrich_track(self, artist: str, track: str):
        """Enriquece datos de track con búsqueda mejorada"""
        cache_key = f"track_enrich_v2_{artist}_{track}"

        if self.db.get_cached_response(cache_key):
            return

        details = {}

        # Obtener contexto de álbum para mejorar búsquedas
        album_hint = self.db.get_scrobble_context_for_track(artist, track)

        # Last.fm
        lastfm_data = self.lastfm.get_track_info(artist, track)
        if lastfm_data and 'track' in lastfm_data:
            track_info = lastfm_data['track']
            details.update({
                'mbid': track_info.get('mbid') if track_info.get('mbid') else None,
                'duration_ms': int(track_info.get('duration', 0)),
                'album': track_info.get('album', {}).get('title') if 'album' in track_info else None
            })

        # MusicBrainz con búsqueda mejorada
        if not details.get('mbid'):
            search_result = self.musicbrainz.search_recording(artist, track, album_hint)
            if search_result and 'recordings' in search_result and search_result['recordings']:
                recording = search_result['recordings'][0]
                details.update({
                    'mbid': recording['id'],
                    'duration_ms': recording.get('length'),
                    'isrc': recording.get('isrcs', [None])[0] if recording.get('isrcs') else None
                })

        self.db.save_track_details(artist, track, details)
        self.db.cache_response(cache_key, {'processed': True}, 86400)

    def run(self, download_all: bool = False, backfill: bool = False,
        enrich_only: bool = False, limit: int = 1000):
        """Ejecuta el proceso optimizado"""
        print("=" * 60)
        print("🚀 ACTUALIZADOR OPTIMIZADO DE LAST.FM v2.0")
        print("=" * 60)

        if enrich_only:
            self.enrich_entities_parallel(limit=limit)
        else:
            for user in self.users:
                self.update_user_scrobbles_enhanced(user, download_all, backfill)
            self.enrich_entities_parallel(limit=limit)

        print("\n" + "=" * 60)
        print("✅ PROCESO COMPLETADO")
        print("=" * 60)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    parser = argparse.ArgumentParser(description='Actualizador optimizado de Last.fm v2.0')
    parser.add_argument('--all', action='store_true',
                       help='Descargar TODOS los scrobbles')
    parser.add_argument('--backfill', action='store_true',
                       help='Completar historial hacia atrás')
    parser.add_argument('--enrich', action='store_true',
                       help='Solo enriquecer datos existentes')
    parser.add_argument('--limit', type=int, default=1000,
                       help='Número máximo de entidades a enriquecer por tipo (default: 1000)')

    args = parser.parse_args()

    if args.all and args.backfill:
        print("❌ No puedes usar --all y --backfill simultáneamente")
        sys.exit(1)

    try:
        updater = OptimizedLastFMUpdater()
        updater.run(download_all=args.all, backfill=args.backfill, enrich_only=args.enrich, limit=args.limit)
    except KeyboardInterrupt:
        print("\n⚠️ Interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Last.fm Database Updater - Multithreaded with Proxy Support
Actualiza la base de datos con múltiples APIs de forma paralela y eficiente usando proxies
Mejoras: multihilo optimizado, soporte de proxies, rotación de tokens, mejor rate limiting
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
import random
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


class ProxyManager:
    """Gestor de proxies para rotación automática con soporte de autenticación"""

    def __init__(self, use_proxies: bool = False):
        self.use_proxies = use_proxies
        self.proxies = []
        self.current_proxy_index = 0
        self.failed_proxies = set()
        self.lock = threading.Lock()

        if use_proxies:
            self._load_proxies()

    def _load_proxies(self):
        """Carga proxies desde variables de entorno con soporte de autenticación"""
        # Buscar proxies en diferentes formatos
        proxy_list = os.getenv('PROXIES', '')

        # Limpiar comillas si existen
        proxy_list = proxy_list.strip().strip('"').strip("'")

        if not proxy_list:
            # Buscar proxies numerados con posible autenticación
            i = 1
            while True:
                proxy = os.getenv(f'PROXY_{i}', '')
                if not proxy:
                    break
                # Limpiar comillas y espacios
                proxy_clean = proxy.strip().strip('"').strip("'")
                if proxy_clean:
                    parsed_proxy = self._parse_proxy(proxy_clean)
                    if parsed_proxy:
                        self.proxies.append(parsed_proxy)
                i += 1
        else:
            # Lista separada por comas
            raw_proxies = [p.strip().strip('"').strip("'") for p in proxy_list.split(',') if p.strip()]
            for proxy_str in raw_proxies:
                parsed_proxy = self._parse_proxy(proxy_str)
                if parsed_proxy:
                    self.proxies.append(parsed_proxy)

        if not self.proxies:
            print("⚠️ Flag --proxied especificado pero no se encontraron proxies válidos en .env")
            print("   Formatos soportados:")
            print("   PROXIES=host:port,user:pass@host:port")
            print("   PROXY_1=host:port")
            print("   PROXY_2=user:pass@host:port")
            print("   PROXY_USER=usuario (para todos los proxies)")
            print("   PROXY_PASS=contraseña (para todos los proxies)")
            self.use_proxies = False
        else:
            print(f"🔄 Cargados {len(self.proxies)} proxies para rotación:")
            for i, proxy in enumerate(self.proxies, 1):
                # Ocultar contraseña en el log
                display_proxy = self._mask_proxy_auth(proxy)
                print(f"   {i}. {display_proxy}")

    def _parse_proxy(self, proxy_string: str) -> Optional[Dict[str, str]]:
        """Parse proxy string with optional authentication"""
        if not proxy_string:
            return None

        # Formato: [usuario:contraseña@]host:puerto
        auth = None
        host_port = proxy_string

        if '@' in proxy_string:
            auth_part, host_port = proxy_string.rsplit('@', 1)
            if ':' in auth_part:
                auth = auth_part

        # Si no hay auth explícita, usar credenciales globales
        global_user = os.getenv('PROXY_USER', '').strip().strip('"').strip("'")
        global_pass = os.getenv('PROXY_PASS', '').strip().strip('"').strip("'")

        if not auth and global_user and global_pass:
            auth = f"{global_user}:{global_pass}"

        # Validar formato host:puerto
        if ':' not in host_port:
            print(f"⚠️ Formato de proxy inválido: {proxy_string}")
            return None

        try:
            host, port = host_port.rsplit(':', 1)
            int(port)  # Validar que el puerto sea numérico
        except ValueError:
            print(f"⚠️ Puerto inválido en proxy: {proxy_string}")
            return None

        # Construir URLs del proxy
        if auth:
            proxy_url = f"http://{auth}@{host}:{port}"
        else:
            proxy_url = f"http://{host}:{port}"

        return {
            'http': proxy_url,
            'https': proxy_url,
            '_display': f"{host}:{port}" + (" (auth)" if auth else "")
        }

    def _mask_proxy_auth(self, proxy_config: Dict[str, str]) -> str:
        """Enmascara las credenciales para logging seguro"""
        return proxy_config.get('_display', 'proxy_desconocido')

    def get_proxy_config(self) -> Optional[Dict[str, str]]:
        """Obtiene configuración de proxy actual"""
        if not self.use_proxies or not self.proxies:
            return None

        with self.lock:
            available_proxies = [p for p in self.proxies if p.get('_display') not in self.failed_proxies]

            if not available_proxies:
                # Resetear proxies fallidos y reintentar
                print("🔄 Reseteando proxies fallidos...")
                self.failed_proxies.clear()
                available_proxies = self.proxies

            if not available_proxies:
                return None

            proxy = available_proxies[self.current_proxy_index % len(available_proxies)]
            self.current_proxy_index += 1

            return {
                'http': proxy['http'],
                'https': proxy['https'],
                '_display': proxy['_display']
            }

    def mark_proxy_failed(self, proxy_config: Dict[str, str]):
        """Marca un proxy como fallido"""
        if proxy_config and '_display' in proxy_config:
            with self.lock:
                failed_proxy = proxy_config['_display']
                self.failed_proxies.add(failed_proxy)
                print(f"❌ Proxy marcado como fallido: {failed_proxy}")


class ApiClient:
    """Cliente base para APIs con soporte de proxies y rate limiting"""
    def __init__(self, base_url: str, rate_limit_delay: float = 0.2, proxy_manager: Optional[ProxyManager] = None, debug_mode: bool = False):
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
        self.proxy_manager = proxy_manager
        self.debug_mode = debug_mode
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
        """Realiza request con rate limiting, proxies y mejor manejo de errores"""
        if self.consecutive_errors >= self.max_consecutive_errors:
            if self.debug_mode:
                print(f"   ⚠️ Demasiados errores consecutivos en {self.base_url}. Saltando...")
            return None

        self._rate_limit()

        # Configurar proxy si está habilitado
        proxy_config = None
        proxy_info = "Sin proxy"
        if self.proxy_manager and self.proxy_manager.use_proxies:
            proxy_config = self.proxy_manager.get_proxy_config()
            if proxy_config:
                proxy_info = proxy_config.get('_display', 'proxy_desconocido')

        # Log de debug con información del proxy
        thread_name = threading.current_thread().name
        if self.debug_mode:
            print(f"🌐 [{thread_name}] {self.base_url} via {proxy_info}")

        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                proxies={'http': proxy_config.get('http'), 'https': proxy_config.get('https')} if proxy_config else None
            )

            if response.status_code == 200:
                self.consecutive_errors = 0
                return response.json()
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                if self.debug_mode:
                    print(f"   ⏳ Rate limit en {self.base_url} via {proxy_info}. Esperando {retry_after}s...")
                time.sleep(retry_after)
                return self.get(url, params, headers, timeout)
            elif response.status_code in [502, 503, 504]:
                if self.debug_mode:
                    print(f"   ⚠️ Error de servidor ({response.status_code}) en {self.base_url} via {proxy_info}. Reintentando...")
                time.sleep(5)
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                    proxies={'http': proxy_config.get('http'), 'https': proxy_config.get('https')} if proxy_config else None
                )
                if response.status_code == 200:
                    self.consecutive_errors = 0
                    return response.json()

            self.consecutive_errors += 1
            return None

        except requests.exceptions.ProxyError:
            if proxy_config and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(proxy_config)
            self.consecutive_errors += 1
            return None
        except requests.exceptions.Timeout:
            if self.debug_mode:
                print(f"   ⏱️ Timeout en {self.base_url} via {proxy_info}")
            if proxy_config and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(proxy_config)
            self.consecutive_errors += 1
            return None
        except requests.exceptions.ConnectionError:
            if self.debug_mode:
                print(f"   🔌 Error de conexión en {self.base_url} via {proxy_info}")
            if proxy_config and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(proxy_config)
            self.consecutive_errors += 1
            time.sleep(2)
            return None
        except Exception as e:
            if self.debug_mode:
                print(f"   ⚠️ Error en {self.base_url} via {proxy_info}: {e}")
            self.consecutive_errors += 1
            return None


class LastFMClient(ApiClient):
    def __init__(self, api_key: str, proxy_manager: Optional[ProxyManager] = None, debug_mode: bool = False):
        super().__init__("https://ws.audioscrobbler.com/2.0/", 0.2, proxy_manager, debug_mode)
        self.api_key = api_key

    def get_user_scrobbles(self, username: str, limit: int = 200, from_timestamp: int = None, to_timestamp: int = None) -> Optional[Dict]:
        """Obtiene scrobbles de usuario con paginación mejorada"""
        params = {
            'method': 'user.getRecentTracks',
            'user': username,
            'api_key': self.api_key,
            'format': 'json',
            'limit': limit
        }

        if from_timestamp:
            params['from'] = from_timestamp
        if to_timestamp:
            params['to'] = to_timestamp

        return self.get(self.base_url, params)

    def get_artist_info(self, artist_name: str) -> Optional[Dict]:
        """Obtiene información de artista"""
        params = {
            'method': 'artist.getInfo',
            'artist': artist_name,
            'api_key': self.api_key,
            'format': 'json',
            'autocorrect': 1
        }
        return self.get(self.base_url, params)

    def get_album_info(self, artist: str, album: str) -> Optional[Dict]:
        """Obtiene información de álbum"""
        params = {
            'method': 'album.getInfo',
            'artist': artist,
            'album': album,
            'api_key': self.api_key,
            'format': 'json',
            'autocorrect': 1
        }
        return self.get(self.base_url, params)

    def get_track_info(self, artist: str, track: str) -> Optional[Dict]:
        """Obtiene información de track"""
        params = {
            'method': 'track.getInfo',
            'artist': artist,
            'track': track,
            'api_key': self.api_key,
            'format': 'json',
            'autocorrect': 1
        }
        return self.get(self.base_url, params)


class MusicBrainzClient(ApiClient):
    def __init__(self, proxy_manager: Optional[ProxyManager] = None, debug_mode: bool = False):
        super().__init__("https://musicbrainz.org/ws/2/", 1.1, proxy_manager, debug_mode)
        self.session.headers.update({
            'User-Agent': 'LastFM-Database-Updater/2.0 (contact@example.com)'
        })

    def search_artist(self, artist_name: str) -> Optional[Dict]:
        """Busca artista con múltiples variantes"""
        search_variants = TextNormalizer.generate_search_variants(artist_name)

        for variant in search_variants[:2]:  # Limitar para evitar exceso de requests
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
        """Busca release con contexto mejorado"""
        album_variants = TextNormalizer.generate_search_variants(album)
        artist_variants = TextNormalizer.generate_search_variants(artist)

        for album_variant in album_variants[:2]:
            for artist_variant in artist_variants[:2]:
                query = f'release:"{album_variant}" AND artist:"{artist_variant}"'
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': 5
                }
                result = self.get(f"{self.base_url}release/", params)
                if result and result.get('releases'):
                    return result

        return None

    def get_release_by_mbid(self, mbid: str) -> Optional[Dict]:
        """Obtiene release por MBID"""
        params = {'fmt': 'json', 'inc': 'release-groups+labels+recordings+genres+tags'}
        return self.get(f"{self.base_url}release/{mbid}", params)

    def search_recording(self, artist: str, track: str, album_hint: Optional[str] = None) -> Optional[Dict]:
        """Busca recording con contexto de álbum"""
        artist_variants = TextNormalizer.generate_search_variants(artist)
        track_variants = TextNormalizer.generate_search_variants(track)

        for artist_variant in artist_variants[:2]:
            for track_variant in track_variants[:2]:
                query = f'recording:"{track_variant}" AND artist:"{artist_variant}"'
                if album_hint:
                    album_clean, _ = TextNormalizer.clean_for_search(album_hint)
                    if album_clean:
                        query += f' AND release:"{album_clean}"'

                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': 5
                }
                result = self.get(f"{self.base_url}recording/", params)
                if result and result.get('recordings'):
                    return result

        return None


class DiscogsClient(ApiClient):
    def __init__(self, token: str, proxy_manager: Optional[ProxyManager] = None, debug_mode: bool = False):
        super().__init__("https://api.discogs.com/", 1.2, proxy_manager, debug_mode)
        self.token = token
        if token:
            self.session.headers.update({
                'Authorization': f'Discogs token={token}',
                'User-Agent': 'LastFM-Database-Updater/2.0'
            })

    def search_artist(self, artist_name: str) -> Optional[Dict]:
        """Busca artista en Discogs"""
        if not self.token:
            return None

        artist_variants = TextNormalizer.generate_search_variants(artist_name)

        for variant in artist_variants[:2]:
            params = {
                'q': variant,
                'type': 'artist',
                'per_page': 5
            }
            result = self.get(f"{self.base_url}database/search", params)
            if result and result.get('results'):
                return result

        return None

    def search_release(self, artist: str, album: str) -> Optional[Dict]:
        """Busca release en Discogs"""
        if not self.token:
            return None

        artist_variants = TextNormalizer.generate_search_variants(artist)
        album_variants = TextNormalizer.generate_search_variants(album)

        for artist_variant in artist_variants[:2]:
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

    def get_artist_details(self, artist_id: str) -> Optional[Dict]:
        """Obtiene detalles de artista"""
        if not self.token:
            return None

        return self.get(f"{self.base_url}artists/{artist_id}")

    def get_release_details(self, release_id: str) -> Optional[Dict]:
        """Obtiene detalles de release"""
        if not self.token:
            return None

        return self.get(f"{self.base_url}releases/{release_id}")


# El resto del archivo se mantiene similar al original pero con las mejoras de multihilo y proxies aplicadas...
# Continuará en la siguiente parte para no exceder el límite


class OptimizedDatabase:
    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.pending_commits = 0
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

        # Índices optimizados
        indices = [
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_user_timestamp ON scrobbles(user, timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_artist_album ON scrobbles(artist, album)',
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_user_artist ON scrobbles(user, artist)',
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_artist_timestamp ON scrobbles(artist, timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_user_track ON scrobbles(user, track)',
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_user_artist_timestamp ON scrobbles(user, artist, timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_album_artist ON scrobbles(album, artist)',
            'CREATE INDEX IF NOT EXISTS idx_scrobbles_track_artist ON scrobbles(track, artist)'
        ]

        for index in indices:
            cursor.execute(index)

        # Tablas de metadatos mejoradas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_details (
                artist TEXT PRIMARY KEY,
                mbid TEXT,
                bio TEXT,
                tags TEXT,
                similar_artists TEXT,
                listeners INTEGER,
                playcount INTEGER,
                url TEXT,
                image_url TEXT,
                last_updated INTEGER NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_details (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                mbid TEXT,
                release_group_mbid TEXT,
                release_date TEXT,
                type TEXT,
                status TEXT,
                packaging TEXT,
                country TEXT,
                barcode TEXT,
                total_tracks INTEGER,
                last_updated INTEGER NOT NULL,
                PRIMARY KEY (artist, album)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS track_details (
                artist TEXT NOT NULL,
                track TEXT NOT NULL,
                mbid TEXT,
                duration_ms INTEGER,
                album TEXT,
                isrc TEXT,
                last_updated INTEGER NOT NULL,
                PRIMARY KEY (artist, track)
            )
        ''')

        # Nuevas tablas para géneros detallados
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_genres_detailed (
                artist TEXT NOT NULL,
                source TEXT NOT NULL,
                genre TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                last_updated INTEGER,
                PRIMARY KEY (artist, source, genre)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_genres (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                source TEXT NOT NULL,
                genre TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                last_updated INTEGER,
                PRIMARY KEY (artist, album, source, genre)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_release_dates (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                release_year INTEGER,
                release_date TEXT,
                updated_at INTEGER,
                PRIMARY KEY (artist, album)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_labels (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                label TEXT,
                updated_at INTEGER,
                PRIMARY KEY (artist, album)
            )
        ''')

        # Tablas legacy para compatibilidad
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_genres (
                artist TEXT PRIMARY KEY,
                genres TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_responses (
                cache_key TEXT PRIMARY KEY,
                response_data TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
        ''')

        self.conn.commit()

    def save_scrobbles_batch(self, scrobbles: List[ScrobbleData], force_commit: bool = False):
        """Guarda múltiples scrobbles de forma eficiente"""
        with self.lock:
            cursor = self.conn.cursor()

            for scrobble in scrobbles:
                cursor.execute('''
                    INSERT OR IGNORE INTO scrobbles (user, artist, track, album, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (scrobble.user, scrobble.artist, scrobble.track, scrobble.album, scrobble.timestamp))

            self.pending_commits += len(scrobbles)

            if force_commit or self.pending_commits >= 100:
                self.conn.commit()
                self.pending_commits = 0

    def save_artist_details(self, artist: str, details: Dict, force_commit: bool = False):
        """Guarda detalles de artista"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO artist_details
                (artist, mbid, bio, tags, similar_artists, listeners, playcount, url, image_url, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                artist,
                details.get('mbid'),
                details.get('bio'),
                json.dumps(details.get('tags', [])) if details.get('tags') else None,
                json.dumps(details.get('similar', [])) if details.get('similar') else None,
                details.get('listeners'),
                details.get('playcount'),
                details.get('url'),
                details.get('image_url'),
                int(time.time())
            ))

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def save_album_details(self, artist: str, album: str, details: Dict, force_commit: bool = False):
        """Guarda detalles de álbum"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_details
                (artist, album, mbid, release_group_mbid, album_type, status, packaging,
                 country, barcode, total_tracks, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                artist, album,
                details.get('mbid'),
                details.get('release_group_mbid'),
                details.get('type'),
                details.get('status'),
                details.get('packaging'),
                details.get('country'),
                details.get('barcode'),
                details.get('total_tracks'),
                int(time.time())
            ))
            cursor.execute('''
                INSERT OR REPLACE INTO album_release_dates
                (artist, album, release_date, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (
                artist,




                album,
                details.get('release_date'),
                int(time.time())
            ))


            self.pending_commits += 1
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def save_track_details(self, artist: str, track: str, details: Dict, force_commit: bool = False):
        """Guarda detalles de track"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO track_details
                (artist, track, mbid, duration_ms, album, isrc, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                artist, track,
                details.get('mbid'),
                details.get('duration_ms'),
                details.get('album'),
                details.get('isrc'),
                int(time.time())
            ))

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def save_detailed_genres(self, artist: str, source: str, genres: List[Dict], force_commit: bool = False):
        """Guarda géneros detallados por fuente"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM artist_genres_detailed WHERE artist = ? AND source = ?', (artist, source))

            for genre_info in genres:
                genre_name = genre_info.get('name', genre_info) if isinstance(genre_info, dict) else str(genre_info)
                weight = genre_info.get('weight', 1.0) if isinstance(genre_info, dict) else 1.0

                cursor.execute('''
                    INSERT INTO artist_genres_detailed (artist, source, genre, weight, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (artist, source, genre_name, weight, int(time.time())))

            self.pending_commits += len(genres)
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def save_album_genres(self, artist: str, album: str, source: str, genres: List[Dict], force_commit: bool = False):
        """Guarda géneros de álbum por fuente"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM album_genres WHERE artist = ? AND album = ? AND source = ?',
                         (artist, album, source))

            for genre_info in genres:
                genre_name = genre_info.get('name', genre_info) if isinstance(genre_info, dict) else str(genre_info)
                weight = genre_info.get('weight', 1.0) if isinstance(genre_info, dict) else 1.0

                cursor.execute('''
                    INSERT INTO album_genres (artist, album, source, genre, weight, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (artist, album, source, genre_name, weight, int(time.time())))

            self.pending_commits += len(genres)
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def save_album_release_date(self, artist: str, album: str, release_year: Optional[int], release_date: Optional[str], force_commit: bool = False):
        """Guarda fecha de lanzamiento de álbum"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_release_dates (artist, album, release_year, release_date, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (artist, album, release_year, release_date, int(time.time())))

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def save_album_label(self, artist: str, album: str, label: Optional[str], force_commit: bool = False):
        """Guarda sello discográfico"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_labels (artist, album, label, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (artist, album, label, int(time.time())))

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def save_artist_genres(self, artist: str, genres: List[str], force_commit: bool = False):
        """Guarda géneros de artista (tabla legacy)"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO artist_genres (artist, genres, updated_at)
                VALUES (?, ?, ?)
            ''', (artist, json.dumps(genres), int(time.time())))

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 20:
                self.conn.commit()
                self.pending_commits = 0

    def cache_response(self, cache_key: str, response_data: Dict, ttl_seconds: int):
        """Cachea respuesta de API"""
        with self.lock:
            cursor = self.conn.cursor()
            expires_at = int(time.time()) + ttl_seconds
            cursor.execute('''
                INSERT OR REPLACE INTO cache_responses (cache_key, response_data, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (cache_key, json.dumps(response_data), int(time.time()), expires_at))

            self.pending_commits += 1
            if self.pending_commits >= 10:
                self.conn.commit()
                self.pending_commits = 0

    def get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Obtiene respuesta cacheada si no ha expirado"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT response_data FROM cache_responses
            WHERE cache_key = ? AND expires_at > ?
        ''', (cache_key, int(time.time())))

        result = cursor.fetchone()
        if result:
            return json.loads(result['response_data'])
        return None

    def get_entities_to_enrich(self, entity_type: str, limit: int = 1000) -> List[Tuple]:
        """Obtiene entidades que necesitan enriquecimiento"""
        cursor = self.conn.cursor()

        if entity_type == 'artist':
            cursor.execute('''
                SELECT DISTINCT s.artist
                FROM scrobbles s
                LEFT JOIN artist_details ad ON s.artist = ad.artist
                WHERE ad.artist IS NULL
                ORDER BY (
                    SELECT COUNT(*)
                    FROM scrobbles s2
                    WHERE s2.artist = s.artist
                ) DESC
                LIMIT ?
            ''', (limit,))
            return [(row['artist'],) for row in cursor.fetchall()]

        elif entity_type == 'album':
            cursor.execute('''
                SELECT DISTINCT s.artist, s.album FROM scrobbles s
                LEFT JOIN album_details ad ON s.artist = ad.artist AND s.album = ad.album
                WHERE s.album IS NOT NULL AND s.album != '' AND ad.artist IS NULL
                ORDER BY (
                    SELECT COUNT(*) FROM scrobbles s2 WHERE s2.artist = s.artist AND s2.album = s.album
                ) DESC
                LIMIT ?
            ''', (limit,))
            return [(row['artist'], row['album']) for row in cursor.fetchall()]

        elif entity_type == 'track':
            cursor.execute('''
                SELECT DISTINCT s.artist, s.track FROM scrobbles s
                LEFT JOIN track_details td ON s.artist = td.artist AND s.track = td.track
                WHERE td.artist IS NULL
                ORDER BY (
                    SELECT COUNT(*) FROM scrobbles s2 WHERE s2.artist = s.artist AND s2.track = s.track
                ) DESC
                LIMIT ?
            ''', (limit,))
            return [(row['artist'], row['track']) for row in cursor.fetchall()]

        return []

    def get_scrobble_context_for_album(self, artist: str, album: str) -> Optional[str]:
        """Obtiene track representativo para búsquedas de álbum"""
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
        """Obtiene álbum representativo para búsquedas de track"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT album FROM scrobbles
            WHERE artist = ? AND track = ? AND album IS NOT NULL AND album != ''
            GROUP BY album
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ''', (artist, track))
        result = cursor.fetchone()
        return result['album'] if result else None

    def force_commit(self):
        """Fuerza commit de cambios pendientes"""
        with self.lock:
            self.conn.commit()
            self.pending_commits = 0

    def close(self):
        """Cierra la conexión a la base de datos"""
        self.force_commit()
        self.conn.close()


class MultithreadedLastFMUpdater:
    def __init__(self, debug_mode: bool = False, use_proxies: bool = False, max_workers: int = 8):
        # Configuración
        self.debug_mode = debug_mode
        self.use_proxies = use_proxies
        self.max_workers = max_workers

        # Configurar proxy manager
        self.proxy_manager = ProxyManager(use_proxies) if use_proxies else None

        # Cargar configuración
        self.lastfm_api_key = os.getenv('LASTFM_API_KEY')
        self.discogs_tokens = self._load_discogs_tokens()
        self.current_token_index = 0

        if not self.lastfm_api_key:
            raise ValueError("LASTFM_API_KEY no encontrado en variables de entorno")

        # Usuarios de Last.fm
        users_env = os.getenv('LASTFM_USERS', '')
        self.users = [u.strip() for u in users_env.split(',') if u.strip()]

        if not self.users:
            raise ValueError("LASTFM_USERS no encontrado en variables de entorno")

        # Base de datos
        self.db = OptimizedDatabase()

        # Contadores thread-safe
        self.stats_lock = threading.Lock()
        self.stats = {
            'scrobbles_added': 0,
            'artists_enriched': 0,
            'albums_enriched': 0,
            'tracks_enriched': 0,
            'api_errors': 0
        }

        if self.debug_mode:
            print(f"🔧 DEBUG MODE ACTIVADO")
            print(f"🔄 Proxies: {'✅ Habilitados' if use_proxies else '❌ Deshabilitados'}")
            print(f"🧵 Workers: {max_workers}")
            print(f"👥 Usuarios: {len(self.users)}")

    def _load_discogs_tokens(self) -> List[str]:
        """Carga múltiples tokens de Discogs"""
        tokens = []

        main_token = os.getenv('DISCOGS_TOKEN', '')
        if main_token:
            tokens.append(main_token)

        i = 2
        while True:
            token = os.getenv(f'DISCOGS_TOKEN_{i}', '')
            if not token:
                break
            tokens.append(token)
            i += 1

        return tokens

    def _create_worker_clients(self) -> Tuple[LastFMClient, MusicBrainzClient, DiscogsClient]:
        """Crea clientes API únicos para cada worker"""
        with self.stats_lock:
            token_index = self.current_token_index % len(self.discogs_tokens) if self.discogs_tokens else 0
            self.current_token_index = (self.current_token_index + 1) % max(len(self.discogs_tokens), 1)

        lastfm_client = LastFMClient(self.lastfm_api_key, self.proxy_manager, self.debug_mode)
        mb_client = MusicBrainzClient(self.proxy_manager, self.debug_mode)

        discogs_token = self.discogs_tokens[token_index] if self.discogs_tokens else ''
        discogs_client = DiscogsClient(discogs_token, self.proxy_manager, self.debug_mode)

        return lastfm_client, mb_client, discogs_client

    def _update_stats(self, stat_name: str, increment: int = 1):
        """Thread-safe update de estadísticas"""
        with self.stats_lock:
            self.stats[stat_name] = self.stats.get(stat_name, 0) + increment

    def enrich_artist_worker(self, artist_name: str) -> bool:
        """Worker para enriquecer un artista"""
        try:
            lastfm, mb, discogs = self._create_worker_clients()

            cache_key = f"artist_enrich_v2_{artist_name}"
            if self.db.get_cached_response(cache_key):
                return False

            details = {}
            found_genres = False

            # 1. Last.fm
            lastfm_data = lastfm.get_artist_info(artist_name)
            if lastfm_data and 'artist' in lastfm_data:
                artist_info = lastfm_data['artist']
                details.update({
                    'mbid': artist_info.get('mbid') if artist_info.get('mbid') else None,
                    'bio': artist_info.get('bio', {}).get('summary', '').strip(),
                    'listeners': int(artist_info.get('stats', {}).get('listeners', 0)),
                    'playcount': int(artist_info.get('stats', {}).get('playcount', 0)),
                    'url': artist_info.get('url', ''),
                    'image_url': artist_info.get('image', [{}])[-1].get('#text', '') if artist_info.get('image') else ''
                })

                # Géneros y tags de Last.fm
                if 'tags' in artist_info and 'tag' in artist_info['tags']:
                    tags = artist_info['tags']['tag']
                    if isinstance(tags, list):
                        details['tags'] = [tag.get('name', '') for tag in tags[:10]]
                        genre_names = [tag.get('name', '') for tag in tags[:5]]
                        self.db.save_artist_genres(artist_name, genre_names)
                        found_genres = True

                # Artistas similares
                if 'similar' in artist_info and 'artist' in artist_info['similar']:
                    similar = artist_info['similar']['artist']
                    if isinstance(similar, list):
                        details['similar'] = [artist.get('name', '') for artist in similar[:5]]

            # 2. MusicBrainz
            mb_data = None
            if details.get('mbid'):
                mb_data = mb.get_artist_by_mbid(details['mbid'])
            else:
                search_result = mb.search_artist(artist_name)
                if search_result and search_result.get('artists'):
                    best_match = search_result['artists'][0]
                    details['mbid'] = best_match['id']
                    mb_data = mb.get_artist_by_mbid(details['mbid'])

            if mb_data:
                mb_genres = []
                if 'genres' in mb_data and mb_data['genres']:
                    mb_genres = [
                        {'name': g['name'], 'weight': 1.0}
                        for g in mb_data['genres']
                    ]
                elif 'tags' in mb_data and mb_data['tags']:
                    mb_genres = [
                        {'name': t['name'], 'weight': float(t.get('count', 1))}
                        for t in mb_data['tags'][:10]
                    ]

                if mb_genres:
                    self.db.save_detailed_genres(artist_name, 'musicbrainz', mb_genres)

                    if not found_genres:
                        genre_names = [genre['name'] for genre in mb_genres]
                        self.db.save_artist_genres(artist_name, genre_names)

            self.db.save_artist_details(artist_name, details)
            self.db.cache_response(cache_key, {'processed': True}, 86400)

            self._update_stats('artists_enriched')
            return True

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Error enriqueciendo artista {artist_name}: {e}")
            self._update_stats('api_errors')
            return False

    def enrich_album_worker(self, artist: str, album: str) -> bool:
        """Worker para enriquecer un álbum"""
        try:
            lastfm, mb, discogs = self._create_worker_clients()

            cache_key = f"album_enrich_v2_{artist}_{album}"
            if self.db.get_cached_response(cache_key):
                return False

            details = {}
            track_hint = self.db.get_scrobble_context_for_album(artist, album)

            # 1. Last.fm
            lastfm_data = lastfm.get_album_info(artist, album)
            if lastfm_data and 'album' in lastfm_data:
                album_info = lastfm_data['album']
                if 'mbid' in album_info and album_info['mbid']:
                    details['mbid'] = album_info['mbid']

            # 2. MusicBrainz
            mb_data = None
            if 'mbid' in details:
                mb_data = mb.get_release_by_mbid(details['mbid'])
            else:
                search_result = mb.search_release(artist, album, track_hint)
                if search_result and search_result.get('releases'):
                    best_match = search_result['releases'][0]
                    details['mbid'] = best_match['id']
                    mb_data = mb.get_release_by_mbid(details['mbid'])

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
                # --- FECHAS SOLO A album_release_dates ---
                if mb_data.get('date'):
                    try:
                        release_year = int(mb_data['date'][:4])
                    except:
                        release_year = None

                    self.db.save_album_release_date(
                        artist,
                        album,
                        release_year,
                        mb_data.get('date')
                    )
                # Labels
                if 'label-info' in mb_data and mb_data['label-info']:
                    label = mb_data['label-info'][0]['label']['name']
                    self.db.save_album_label(artist, album, label)

                # Géneros del álbum
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

                # Fecha de lanzamiento
                if mb_data.get('date'):
                    try:
                        release_year = int(mb_data.get('date')[:4])
                        self.db.save_album_release_date(artist, album, release_year, mb_data.get('date'))
                    except (ValueError, TypeError):
                        pass

            # 3. Discogs como fallback
            if not details.get('release_date') and discogs.token:
                discogs_data = discogs.search_release(artist, album)
                if discogs_data and discogs_data.get('results'):
                    result = discogs_data['results'][0]

                    if result.get('year'):
                        year = result.get('year')
                        try:
                            release_year = int(year)
                        except:
                            release_year = None

                        self.db.save_album_release_date(
                            artist,
                            album,
                            release_year,
                            str(year)
                        )

                    if 'label' in result and result['label']:
                        self.db.save_album_label(artist, album, result['label'][0])

                    # Géneros de Discogs
                    if 'genre' in result and result['genre']:
                        discogs_genres = [
                            {'name': genre, 'weight': 1.0}
                            for genre in result['genre'][:10]
                            if genre and genre.strip()
                        ]
                        if discogs_genres:
                            self.db.save_album_genres(artist, album, 'discogs', discogs_genres)

            self.db.save_album_details(artist, album, details)
            self.db.cache_response(cache_key, {'processed': True}, 86400)

            self._update_stats('albums_enriched')
            return True

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Error enriqueciendo álbum {artist} - {album}: {e}")
            self._update_stats('api_errors')
            return False

    def enrich_track_worker(self, artist: str, track: str) -> bool:
        """Worker para enriquecer un track"""
        try:
            lastfm, mb, discogs = self._create_worker_clients()

            cache_key = f"track_enrich_v2_{artist}_{track}"
            if self.db.get_cached_response(cache_key):
                return False

            details = {}
            album_hint = self.db.get_scrobble_context_for_track(artist, track)

            # Last.fm
            lastfm_data = lastfm.get_track_info(artist, track)
            if lastfm_data and 'track' in lastfm_data:
                track_info = lastfm_data['track']
                details.update({
                    'mbid': track_info.get('mbid') if track_info.get('mbid') else None,
                    'duration_ms': int(track_info.get('duration', 0)),
                    'album': track_info.get('album', {}).get('title') if 'album' in track_info else None
                })

            # MusicBrainz
            if not details.get('mbid'):
                search_result = mb.search_recording(artist, track, album_hint)
                if search_result and search_result.get('recordings'):
                    recording = search_result['recordings'][0]
                    details.update({
                        'mbid': recording['id'],
                        'duration_ms': recording.get('length'),
                        'isrc': recording.get('isrcs', [None])[0] if recording.get('isrcs') else None
                    })

            self.db.save_track_details(artist, track, details)
            self.db.cache_response(cache_key, {'processed': True}, 86400)

            self._update_stats('tracks_enriched')
            return True

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Error enriqueciendo track {artist} - {track}: {e}")
            self._update_stats('api_errors')
            return False

    def enrich_entities_parallel(self, limit: int = 1000):
        """Enriquece entidades usando multihilo"""
        print(f"\n🧵 Enriquecimiento paralelo con {self.max_workers} workers")

        # Obtener entidades a enriquecer
        artists_to_enrich = self.db.get_entities_to_enrich('artist', limit)
        albums_to_enrich = self.db.get_entities_to_enrich('album', limit)
        tracks_to_enrich = self.db.get_entities_to_enrich('track', limit)

        print(f"📊 Entidades pendientes:")
        print(f"   • Artistas: {len(artists_to_enrich)}")
        print(f"   • Álbumes: {len(albums_to_enrich)}")
        print(f"   • Tracks: {len(tracks_to_enrich)}")

        # Procesar artistas
        if artists_to_enrich:
            print(f"\n🎤 Enriqueciendo {len(artists_to_enrich)} artistas...")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [
                    executor.submit(self.enrich_artist_worker, artist[0])
                    for artist in artists_to_enrich
                ]

                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    if completed % 50 == 0:
                        print(f"   📊 {completed}/{len(artists_to_enrich)} artistas procesados")
                        self.db.force_commit()

            self.db.force_commit()
            print(f"   ✅ Artistas completados")

        # Procesar álbumes
        if albums_to_enrich:
            print(f"\n💿 Enriqueciendo {len(albums_to_enrich)} álbumes...")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [
                    executor.submit(self.enrich_album_worker, album[0], album[1])
                    for album in albums_to_enrich
                ]

                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    if completed % 25 == 0:
                        print(f"   📊 {completed}/{len(albums_to_enrich)} álbumes procesados")
                        self.db.force_commit()

            self.db.force_commit()
            print(f"   ✅ Álbumes completados")

        # Procesar tracks
        if tracks_to_enrich:
            print(f"\n🎵 Enriqueciendo {len(tracks_to_enrich)} tracks...")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [
                    executor.submit(self.enrich_track_worker, track[0], track[1])
                    for track in tracks_to_enrich
                ]

                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    if completed % 100 == 0:
                        print(f"   📊 {completed}/{len(tracks_to_enrich)} tracks procesados")
                        self.db.force_commit()

            self.db.force_commit()
            print(f"   ✅ Tracks completados")

    def update_user_scrobbles_enhanced(self, username: str, download_all: bool = False, backfill: bool = False):
        """Actualiza scrobbles de usuario con mejoras"""
        print(f"\n👤 Actualizando usuario: {username}")

        lastfm, _, _ = self._create_worker_clients()

        # Determinar timestamp de inicio
        from_timestamp = None
        if not download_all:
            cursor = self.db.conn.cursor()
            cursor.execute('''
                SELECT MAX(timestamp) as last_timestamp FROM scrobbles WHERE user = ?
            ''', (username,))
            result = cursor.fetchone()

            if result['last_timestamp']:
                if backfill:
                    cursor.execute('''
                        SELECT MIN(timestamp) as first_timestamp FROM scrobbles WHERE user = ?
                    ''', (username,))
                    first_result = cursor.fetchone()
                    from_timestamp = first_result['first_timestamp'] - 86400 if first_result['first_timestamp'] else None
                else:
                    from_timestamp = result['last_timestamp'] + 1

        page = 1
        total_pages = 1
        new_scrobbles = 0

        while page <= total_pages:
            if self.debug_mode:
                print(f"   📄 Página {page}/{total_pages}")

            data = lastfm.get_user_scrobbles(
                username,
                limit=200,
                from_timestamp=from_timestamp
            )

            if not data or 'recenttracks' not in data:
                break

            tracks_data = data['recenttracks']
            total_pages = int(tracks_data['@attr'].get('totalPages', 1))

            if 'track' not in tracks_data:
                break

            tracks = tracks_data['track']
            if not isinstance(tracks, list):
                tracks = [tracks]

            batch_scrobbles = []
            for track in tracks:
                # Saltar tracks que están "now playing"
                if '@attr' in track and 'nowplaying' in track['@attr']:
                    continue

                if 'date' not in track:
                    continue

                timestamp = int(track['date']['uts'])

                scrobble = ScrobbleData(
                    user=username,
                    artist=track.get('artist', {}).get('#text', '') if isinstance(track.get('artist'), dict) else track.get('artist', ''),
                    track=track.get('name', ''),
                    album=track.get('album', {}).get('#text', '') if isinstance(track.get('album'), dict) else track.get('album', ''),
                    timestamp=timestamp
                )

                batch_scrobbles.append(scrobble)

            if batch_scrobbles:
                self.db.save_scrobbles_batch(batch_scrobbles)
                new_scrobbles += len(batch_scrobbles)
                self._update_stats('scrobbles_added', len(batch_scrobbles))

            page += 1

            # Para backfill, parar cuando alcancemos datos existentes
            if backfill and batch_scrobbles:
                latest_timestamp = max(s.timestamp for s in batch_scrobbles)
                cursor = self.db.conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) as count FROM scrobbles
                    WHERE user = ? AND timestamp >= ?
                ''', (username, latest_timestamp))

                if cursor.fetchone()['count'] > len(batch_scrobbles):
                    print(f"   🔄 Backfill completado - datos existentes encontrados")
                    break

        self.db.force_commit()
        print(f"   ✅ {new_scrobbles} nuevos scrobbles agregados")

    def run(self, download_all: bool = False, backfill: bool = False, enrich_only: bool = False, limit: int = 1000):
        """Ejecuta el proceso optimizado"""
        print("=" * 60)
        print("🚀 ACTUALIZADOR MULTITHREADED DE LAST.FM v3.0")
        print("=" * 60)
        print(f"🧵 Workers: {self.max_workers}")
        print(f"🔄 Proxies: {'Habilitados' if self.use_proxies else 'Deshabilitados'}")

        start_time = time.time()

        try:
            if enrich_only:
                self.enrich_entities_parallel(limit=limit)
            else:
                # Actualizar scrobbles para cada usuario
                for user in self.users:
                    self.update_user_scrobbles_enhanced(user, download_all, backfill)

                # Enriquecer entidades
                self.enrich_entities_parallel(limit=limit)

            # Estadísticas finales
            elapsed = time.time() - start_time
            print("\n" + "=" * 60)
            print("✅ PROCESO COMPLETADO")
            print("=" * 60)
            print(f"⏱️ Tiempo transcurrido: {elapsed:.1f} segundos")
            print(f"📊 Estadísticas:")
            print(f"   • Scrobbles añadidos: {self.stats['scrobbles_added']}")
            print(f"   • Artistas enriquecidos: {self.stats['artists_enriched']}")
            print(f"   • Álbumes enriquecidos: {self.stats['albums_enriched']}")
            print(f"   • Tracks enriquecidos: {self.stats['tracks_enriched']}")
            print(f"   • Errores de API: {self.stats['api_errors']}")

        finally:
            self.db.close()


def main():
    parser = argparse.ArgumentParser(description='Actualizador multithreaded de Last.fm v3.0')
    parser.add_argument('--all', action='store_true',
                       help='Descargar TODOS los scrobbles')
    parser.add_argument('--backfill', action='store_true',
                       help='Completar historial hacia atrás')
    parser.add_argument('--enrich', action='store_true',
                       help='Solo enriquecer datos existentes')
    parser.add_argument('--limit', type=int, default=1000,
                       help='Número máximo de entidades a enriquecer por tipo (default: 1000)')
    parser.add_argument('--workers', type=int, default=8,
                       help='Número de hilos concurrentes (default: 8)')
    parser.add_argument('--proxied', action='store_true',
                       help='Usar proxies para las consultas (lee del .env)')
    parser.add_argument('--debug', action='store_true',
                       help='Activar modo debug con logging detallado')

    args = parser.parse_args()

    if args.all and args.backfill:
        print("❌ No puedes usar --all y --backfill simultáneamente")
        sys.exit(1)

    # Validar número de workers
    if args.workers < 1:
        print("❌ El número de workers debe ser al menos 1")
        sys.exit(1)
    elif args.workers > 20:
        print("⚠️ Más de 20 workers puede sobrecargar las APIs")
        response = input("¿Continuar? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)

    try:
        updater = MultithreadedLastFMUpdater(
            debug_mode=args.debug,
            use_proxies=args.proxied,
            max_workers=args.workers
        )
        updater.run(
            download_all=args.all,
            backfill=args.backfill,
            enrich_only=args.enrich,
            limit=args.limit
        )
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

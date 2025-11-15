#!/usr/bin/env python3
"""
Metadata Enhancement and Status Script - FIXED VERSION
Busca y actualiza metadatos faltantes para artistas y álbumes usando MusicBrainz y Discogs
Proporciona estadísticas detalladas del estado de la base de datos

MEJORAS:
- Soluciona problema con géneros de Discogs
- Añade guardado periódico de progreso
- Mejor logging y debugging
- Manejo mejorado de errores
"""

import os
import sys
import requests
import json
import sqlite3
import time
import argparse
import threading
import random
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import unicodedata
import re

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_API_KEY') or not os.getenv('DISCOGS_TOKEN_2'):
        load_dotenv()
except ImportError:
    pass


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


class MetadataDatabase:
    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.pending_commits = 0

    def get_all_artists(self) -> Set[str]:
        """Obtiene todos los artistas únicos de scrobbles"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist FROM scrobbles WHERE artist IS NOT NULL AND artist != ""')
        return {row['artist'] for row in cursor.fetchall()}

    def get_all_albums(self) -> Set[Tuple[str, str]]:
        """Obtiene todos los álbumes únicos de scrobbles"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist, album FROM scrobbles WHERE album IS NOT NULL AND album != ""')
        return {(row['artist'], row['album']) for row in cursor.fetchall()}

    def get_all_tracks(self) -> Set[Tuple[str, str]]:
        """Obtiene todos los tracks únicos de scrobbles"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist, track FROM scrobbles WHERE track IS NOT NULL AND track != ""')
        return {(row['artist'], row['track']) for row in cursor.fetchall()}

    def get_artists_without_musicbrainz_genres(self) -> Set[str]:
        """Artistas sin géneros de MusicBrainz"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist
            FROM scrobbles s
            LEFT JOIN artist_genres_detailed agd ON s.artist = agd.artist AND agd.source = 'musicbrainz'
            WHERE agd.artist IS NULL AND s.artist IS NOT NULL AND s.artist != ""
        ''')
        return {row['artist'] for row in cursor.fetchall()}

    def get_artists_without_discogs_genres(self) -> Set[str]:
        """Artistas sin géneros de Discogs"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist
            FROM scrobbles s
            LEFT JOIN artist_genres_detailed agd ON s.artist = agd.artist AND agd.source = 'discogs'
            WHERE agd.artist IS NULL AND s.artist IS NOT NULL AND s.artist != ""
        ''')
        return {row['artist'] for row in cursor.fetchall()}

    def get_albums_without_release_dates(self) -> Set[Tuple[str, str]]:
        """Álbumes sin fecha de lanzamiento"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist, s.album
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.album IS NOT NULL AND s.album != "" AND ard.release_year IS NULL
        ''')
        return {(row['artist'], row['album']) for row in cursor.fetchall()}

    def get_albums_without_labels(self) -> Set[Tuple[str, str]]:
        """Álbumes sin sello discográfico"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist, s.album
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.album IS NOT NULL AND s.album != "" AND al.label IS NULL
        ''')
        return {(row['artist'], row['album']) for row in cursor.fetchall()}

    def get_albums_without_genres(self) -> Set[Tuple[str, str]]:
        """Álbumes sin géneros en la tabla album_genres"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist, s.album
            FROM scrobbles s
            LEFT JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
            WHERE s.album IS NOT NULL AND s.album != "" AND ag.artist IS NULL
        ''')
        return {(row['artist'], row['album']) for row in cursor.fetchall()}

    def get_album_mbid(self, artist: str, album: str) -> Optional[Tuple[str, str]]:
        """Obtiene MBID y release_group_mbid de un álbum desde album_details"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT mbid, release_group_mbid
            FROM album_details
            WHERE artist = ? AND album = ?
        ''', (artist, album))
        result = cursor.fetchone()
        if result:
            return result['mbid'], result['release_group_mbid']
        return None, None

    def get_artists_in_details_table(self) -> Set[str]:
        """Artistas en la tabla artist_details"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist FROM artist_details WHERE artist IS NOT NULL AND artist != ""')
        return {row['artist'] for row in cursor.fetchall()}

    def get_albums_in_details_table(self) -> Set[Tuple[str, str]]:
        """Álbumes en la tabla album_details"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist, album FROM album_details WHERE artist IS NOT NULL AND album IS NOT NULL AND artist != "" AND album != ""')
        return {(row['artist'], row['album']) for row in cursor.fetchall()}

    def get_tracks_in_details_table(self) -> Set[Tuple[str, str]]:
        """Tracks en la tabla track_details"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist, track FROM track_details WHERE artist IS NOT NULL AND track IS NOT NULL AND artist != "" AND track != ""')
        return {(row['artist'], row['track']) for row in cursor.fetchall()}

    def save_artist_genres_detailed(self, artist: str, source: str, genres: List[Dict], force_commit: bool = False):
        """Guarda géneros detallados por fuente"""
        with self.lock:
            cursor = self.conn.cursor()
            # Limpiar géneros existentes de esta fuente para este artista
            cursor.execute('DELETE FROM artist_genres_detailed WHERE artist = ? AND source = ?', (artist, source))

            genres_added = 0
            for genre_info in genres:
                genre_name = genre_info.get('name', genre_info) if isinstance(genre_info, dict) else str(genre_info)
                weight = genre_info.get('weight', 1.0) if isinstance(genre_info, dict) else 1.0

                cursor.execute('''
                    INSERT INTO artist_genres_detailed (artist, source, genre, weight, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (artist, source, genre_name, weight, int(time.time())))
                genres_added += 1

            self.pending_commits += 1

            # Commit periódico o forzado
            if force_commit or self.pending_commits >= 10:
                self.conn.commit()
                self.pending_commits = 0

            return genres_added

    def save_album_release_date(self, artist: str, album: str, release_year: Optional[int], release_date: Optional[str], force_commit: bool = False):
        """Guarda la fecha de lanzamiento de un álbum"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_release_dates (artist, album, release_year, release_date, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (artist, album, release_year, release_date, int(time.time())))

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 10:
                self.conn.commit()
                self.pending_commits = 0

    def save_album_label(self, artist: str, album: str, label: Optional[str], force_commit: bool = False):
        """Guarda el sello de un álbum"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_labels (artist, album, label, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (artist, album, label, int(time.time())))

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 10:
                self.conn.commit()
                self.pending_commits = 0

    def save_album_genres(self, artist: str, album: str, source: str, genres: List[Dict], force_commit: bool = False):
        """Guarda géneros de álbum por fuente"""
        with self.lock:
            cursor = self.conn.cursor()
            # Limpiar géneros existentes de esta fuente para este álbum
            cursor.execute('DELETE FROM album_genres WHERE artist = ? AND album = ? AND source = ?',
                         (artist, album, source))

            genres_added = 0
            for genre_info in genres:
                genre_name = genre_info.get('name', genre_info) if isinstance(genre_info, dict) else str(genre_info)
                weight = genre_info.get('weight', 1.0) if isinstance(genre_info, dict) else 1.0

                cursor.execute('''
                    INSERT INTO album_genres (artist, album, source, genre, weight, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (artist, album, source, genre_name, weight, int(time.time())))
                genres_added += 1

            self.pending_commits += 1
            if force_commit or self.pending_commits >= 10:
                self.conn.commit()
                self.pending_commits = 0

            return genres_added

    def get_albums_stats_for_genres(self) -> Dict[str, int]:
        """Estadísticas de álbumes para géneros"""
        cursor = self.conn.cursor()

        # Álbumes sin géneros
        cursor.execute('''
            SELECT COUNT(DISTINCT s.artist, s.album) as count
            FROM scrobbles s
            LEFT JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
            WHERE s.album IS NOT NULL AND s.album != "" AND ag.artist IS NULL
        ''')
        without_genres = cursor.fetchone()['count']

        # Álbumes con MBIDs disponibles pero sin géneros
        cursor.execute('''
            SELECT COUNT(DISTINCT s.artist, s.album) as count
            FROM scrobbles s
            LEFT JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
            INNER JOIN album_details ad ON s.artist = ad.artist AND s.album = ad.album
            WHERE s.album IS NOT NULL AND s.album != ""
            AND ag.artist IS NULL
            AND ad.mbid IS NOT NULL
        ''')
        with_mbid_no_genres = cursor.fetchone()['count']

        return {
            'without_genres': without_genres,
            'with_mbid_no_genres': with_mbid_no_genres,
            'without_mbid_no_genres': without_genres - with_mbid_no_genres
        }

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

    def force_commit(self):
        """Fuerza un commit de la base de datos"""
        with self.lock:
            self.conn.commit()
            self.pending_commits = 0

    def close(self):
        self.force_commit()  # Asegurar que todos los cambios se guarden
        self.conn.close()


class ProxyManager:
    """Gestor de proxies para rotación automática con soporte de autenticación"""

    def __init__(self, use_proxies: bool = False):
        self.use_proxies = use_proxies
        self.proxies = []
        self.current_proxy_index = 0
        self.failed_proxies = set()

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
                    self.proxies.append(self._parse_proxy(proxy_clean))
                i += 1
        else:
            # Lista separada por comas
            raw_proxies = [p.strip().strip('"').strip("'") for p in proxy_list.split(',') if p.strip()]
            self.proxies = [self._parse_proxy(p) for p in raw_proxies if p]

        # Filtrar proxies válidos
        self.proxies = [p for p in self.proxies if p]

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
            failed_proxy = proxy_config['_display']
            self.failed_proxies.add(failed_proxy)
            print(f"❌ Proxy marcado como fallido: {failed_proxy}")

    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Obtiene un proxy aleatorio (útil para casos específicos)"""
        if not self.use_proxies or not self.proxies:
            return None

        available_proxies = [p for p in self.proxies if p.get('_display') not in self.failed_proxies]
        if not available_proxies:
            available_proxies = self.proxies
            self.failed_proxies.clear()

        if available_proxies:
            proxy = random.choice(available_proxies)
            return {
                'http': proxy['http'],
                'https': proxy['https'],
                '_display': proxy['_display']
            }

        return None


class ApiClient:
    """Cliente base para APIs con mejor manejo de errores y soporte de proxies"""
    def __init__(self, base_url: str, rate_limit_delay: float = 0.2, proxy_manager: Optional[ProxyManager] = None):
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
        self.proxy_manager = proxy_manager
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
        if hasattr(self, '_debug_mode') and getattr(self, '_debug_mode', False):
            print(f"🌐 [{thread_name}] {self.base_url} via {proxy_info}")

        try:
            # Hacer request con o sin proxy
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                proxies={'http': proxy_config.get('http'), 'https': proxy_config.get('https')} if proxy_config else None
            )

            if response.status_code == 200:
                self.consecutive_errors = 0  # Reset error counter on success
                return response.json()
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"   ⏳ Rate limit en {self.base_url} via {proxy_info}. Esperando {retry_after}s...")
                time.sleep(retry_after)
                return self.get(url, params, headers, timeout)
            elif response.status_code in [502, 503, 504]:
                # Server errors - retry once after delay
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
            if proxy_config:
                print(f"   🚫 Error de proxy: {proxy_info}")
                self.proxy_manager.mark_proxy_failed(proxy_config)
            self.consecutive_errors += 1
            return None
        except requests.exceptions.Timeout:
            print(f"   ⏱️ Timeout en {self.base_url} via {proxy_info}")
            if proxy_config and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(proxy_config)
            self.consecutive_errors += 1
            return None
        except requests.exceptions.ConnectionError:
            print(f"   🔌 Error de conexión en {self.base_url} via {proxy_info}")
            if proxy_config and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(proxy_config)
            self.consecutive_errors += 1
            time.sleep(2)
            return None
        except Exception as e:
            print(f"   ⚠️ Error en {self.base_url} via {proxy_info}: {e}")
            self.consecutive_errors += 1
            return None


class MusicBrainzClient(ApiClient):
    def __init__(self, proxy_manager: Optional[ProxyManager] = None, debug_mode: bool = False):
        super().__init__("https://musicbrainz.org/ws/2/", 1.1, proxy_manager)  # Rate limit más estricto
        self._debug_mode = debug_mode
        self.session.headers.update({
            'User-Agent': 'LastFM-Metadata-Enhancer/2.0 (contact@example.com)'
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


class DiscogsClient(ApiClient):
    def __init__(self, token: str, proxy_manager: Optional[ProxyManager] = None, debug_mode: bool = False):
        super().__init__("https://api.discogs.com/", 1.2, proxy_manager)  # Rate limit más conservador
        self.token = token
        self._debug_mode = debug_mode
        if token:
            self.session.headers.update({
                'Authorization': f'Discogs token={token}',
                'User-Agent': 'LastFM-Metadata-Enhancer/2.0'
            })

    def search_artist(self, artist_name: str) -> Optional[Dict]:
        """Busca artista en Discogs"""
        if not self.token:
            return None

        artist_variants = TextNormalizer.generate_search_variants(artist_name)

        for variant in artist_variants[:2]:  # Limitar variantes
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

    def get_artist_details(self, artist_id: str) -> Optional[Dict]:
        """Obtiene detalles de artista"""
        if not self.token:
            return None

        return self.get(f"{self.base_url}artists/{artist_id}")


class MetadataEnhancer:
    def __init__(self, debug_mode: bool = False, use_proxies: bool = False, max_workers: int = 5):
        # Configuración
        self.debug_mode = debug_mode
        self.use_proxies = use_proxies
        self.max_workers = max_workers

        # Configurar proxy manager
        self.proxy_manager = ProxyManager(use_proxies) if use_proxies else None

        # Configurar tokens (soporte para múltiples tokens de Discogs)
        self.discogs_tokens = self._load_discogs_tokens()
        self.current_token_index = 0

        # Base de datos
        self.db = MetadataDatabase()

        # Contadores para estadísticas (thread-safe)
        self.stats_lock = threading.Lock()
        self.stats = {
            'musicbrainz_found': 0,
            'musicbrainz_not_found': 0,
            'discogs_found': 0,
            'discogs_not_found': 0,
            'total_processed': 0,
            'proxy_failures': 0,
            'concurrent_errors': 0
        }

        if self.debug_mode:
            print(f"🔧 DEBUG MODE ACTIVADO")
            print(f"🎯 Tokens de Discogs: {len(self.discogs_tokens)} configurados")
            print(f"🔄 Proxies: {'✅ Habilitados' if use_proxies else '❌ Deshabilitados'}")
            print(f"🧵 Hilos concurrentes: {max_workers}")

    def _load_discogs_tokens(self) -> List[str]:
        """Carga múltiples tokens de Discogs desde .env"""
        tokens = []

        # Token principal
        main_token = os.getenv('DISCOGS_TOKEN', '')
        if main_token:
            tokens.append(main_token)

        # Tokens adicionales numerados
        i = 2
        while True:
            token = os.getenv(f'DISCOGS_TOKEN_{i}', '')
            if not token:
                break
            tokens.append(token)
            i += 1

        if not tokens:
            print("⚠️ No se encontraron tokens de Discogs")
        elif len(tokens) > 1:
            print(f"🔑 Cargados {len(tokens)} tokens de Discogs para rotación")

        return tokens

    def _get_current_discogs_token(self) -> str:
        """Obtiene el token actual de Discogs"""
        if not self.discogs_tokens:
            return ''
        return self.discogs_tokens[self.current_token_index % len(self.discogs_tokens)]

    def _create_worker_clients(self) -> Tuple['MusicBrainzClient', 'DiscogsClient']:
        """Crea clientes API únicos para cada worker thread"""
        # Cada thread tiene sus propios clientes para evitar conflictos
        mb_client = MusicBrainzClient(self.proxy_manager, self.debug_mode)

        # Rotar token para este worker
        with self.stats_lock:
            token_index = self.current_token_index % len(self.discogs_tokens) if self.discogs_tokens else 0
            self.current_token_index = (self.current_token_index + 1) % max(len(self.discogs_tokens), 1)

        token = self.discogs_tokens[token_index] if self.discogs_tokens else ''
        dc_client = DiscogsClient(token, self.proxy_manager, self.debug_mode)

        if self.debug_mode:
            thread_id = threading.current_thread().name
            print(f"🧵 Worker {thread_id} usando token #{token_index + 1}")

        return mb_client, dc_client

    def _handle_rate_limit_or_error(self, source: str):
        """Maneja rate limits rotando tokens o proxies"""
        if source == 'discogs' and len(self.discogs_tokens) > 1:
            time.sleep(2)  # Breve pausa tras rotación de token
        elif self.proxy_manager and self.proxy_manager.use_proxies:
            # Forzar rotación de proxy en siguiente request
            pass

    def _update_stats(self, stat_name: str, increment: int = 1):
        """Thread-safe update de estadísticas"""
        with self.stats_lock:
            self.stats[stat_name] = self.stats.get(stat_name, 0) + increment

    def _search_artist_genres_worker(self, artist_name: str, source: str) -> bool:
        """Worker function para búsqueda de géneros de artista (solo MusicBrainz)"""
        try:
            mb_client, _ = self._create_worker_clients()

            # Solo MusicBrainz para géneros de artista
            if self._search_artist_genres_musicbrainz_worker(artist_name, mb_client):
                self._update_stats('musicbrainz_found')
                return True
            else:
                self._update_stats('musicbrainz_not_found')

            return False

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Error en worker para {artist_name}: {e}")
            self._update_stats('concurrent_errors')
            return False

    def _search_artist_genres_musicbrainz_worker(self, artist_name: str, mb_client: 'MusicBrainzClient') -> bool:
        """Búsqueda de géneros en MusicBrainz (worker version)"""
        if self.debug_mode:
            print(f"🔍 MB: Buscando {artist_name} [Thread: {threading.current_thread().name}]")

        search_result = mb_client.search_artist(artist_name)
        if not search_result or not search_result.get('artists'):
            if self.debug_mode:
                print(f"❌ MB: No se encontró {artist_name}")
            return False

        best_match = search_result['artists'][0]
        mbid = best_match['id']

        mb_data = mb_client.get_artist_by_mbid(mbid)
        if not mb_data:
            if self.debug_mode:
                print(f"❌ MB: No se pudieron obtener detalles para {artist_name}")
            return False

        # Géneros de MusicBrainz
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
            genres_saved = self.db.save_artist_genres_detailed(artist_name, 'musicbrainz', mb_genres)
            if self.debug_mode:
                print(f"✅ MB: {artist_name} - {genres_saved} géneros guardados [Thread: {threading.current_thread().name}]")
            return True

        if self.debug_mode:
            print(f"❌ MB: {artist_name} - sin géneros disponibles")
        return False

    def enhance_artist_genres(self, artists: Set[str], source: str = 'both'):
        """Busca géneros de artistas SOLO en MusicBrainz (Discogs no tiene géneros para artistas)"""
        if source == 'discogs':
            print("⚠️ Discogs no proporciona géneros para artistas, solo para álbumes")
            print("🔄 Cambiando a MusicBrainz...")
            source = 'musicbrainz'
        elif source == 'both':
            print("ℹ️ Nota: Solo buscando en MusicBrainz (Discogs no tiene géneros de artista)")
            source = 'musicbrainz'

        print(f"\n🎵 Buscando géneros de artistas en {source.upper()}...")
        print(f"🧵 Usando {self.max_workers} hilos concurrentes")

        processed = 0
        total = len(artists)
        found_count = 0
        artists_list = list(artists)

        # Función wrapper para el pool
        def process_artist(artist):
            self._update_stats('total_processed')
            return self._search_artist_genres_worker(artist, source)

        # Usar ThreadPoolExecutor para procesamiento concurrente
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_artist = {executor.submit(process_artist, artist): artist for artist in artists_list}

            # Process results as they complete
            for future in as_completed(future_to_artist):
                artist = future_to_artist[future]
                processed += 1

                try:
                    if future.result():
                        found_count += 1
                except Exception as e:
                    if self.debug_mode:
                        print(f"⚠️ Error procesando {artist}: {e}")

                # Reporte de progreso cada 25 elementos
                if processed % 25 == 0:
                    print(f"   📊 {processed}/{total} artistas procesados ({found_count} con géneros encontrados)")
                    self.db.force_commit()  # Commit periódico

        # Commit final
        self.db.force_commit()
        print(f"   ✅ Completado: {found_count}/{total} artistas con géneros encontrados")

    def enhance_album_metadata_concurrent(self, albums: Set[Tuple[str, str]], metadata_type: str = 'all'):
        """Busca metadatos de álbumes usando multihilo"""
        print(f"\n💿 Buscando metadatos de álbumes ({metadata_type})...")
        print(f"🧵 Usando {self.max_workers} hilos concurrentes")

        processed = 0
        total = len(albums)
        found_count = 0
        albums_list = list(albums)

        def process_album(album_data):
            artist, album = album_data
            try:
                mb_client, dc_client = self._create_worker_clients()
                album_found = False

                if metadata_type in ['release_date', 'all']:
                    if self._search_album_release_date_worker(artist, album, mb_client, dc_client):
                        album_found = True

                if metadata_type in ['label', 'all']:
                    if self._search_album_label_worker(artist, album, mb_client, dc_client):
                        album_found = True

                if metadata_type in ['genres', 'all']:
                    if self._search_album_genres_worker(artist, album, mb_client, dc_client):
                        album_found = True

                return album_found
            except Exception as e:
                if self.debug_mode:
                    print(f"⚠️ Error procesando álbum {artist} - {album}: {e}")
                return False

        # Usar ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_album = {executor.submit(process_album, album): album for album in albums_list}

            for future in as_completed(future_to_album):
                album = future_to_album[future]
                processed += 1

                try:
                    if future.result():
                        found_count += 1
                except Exception as e:
                    if self.debug_mode:
                        print(f"⚠️ Error procesando {album}: {e}")

                if processed % 15 == 0:
                    print(f"   📊 {processed}/{total} álbumes procesados ({found_count} con datos encontrados)")
                    self.db.force_commit()

        self.db.force_commit()
        print(f"   ✅ Completado: {found_count}/{total} álbumes con metadatos encontrados")

    def _search_artist_genres_musicbrainz(self, artist_name: str) -> bool:
        """Busca géneros de artista en MusicBrainz - retorna True si encuentra algo"""
        if self.debug_mode:
            print(f"🔍 MB: Buscando {artist_name}")

        search_result = self.musicbrainz.search_artist(artist_name)
        if not search_result or not search_result.get('artists'):
            if self.debug_mode:
                print(f"❌ MB: No se encontró {artist_name}")
            return False

        best_match = search_result['artists'][0]
        mbid = best_match['id']

        mb_data = self.musicbrainz.get_artist_by_mbid(mbid)
        if not mb_data:
            if self.debug_mode:
                print(f"❌ MB: No se pudieron obtener detalles para {artist_name}")
            return False

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
            genres_saved = self.db.save_artist_genres_detailed(artist_name, 'musicbrainz', mb_genres)
            if self.debug_mode:
                print(f"✅ MB: {artist_name} - {genres_saved} géneros guardados")
            return True

        if self.debug_mode:
            print(f"❌ MB: {artist_name} - sin géneros disponibles")
        return False

    def _search_album_release_date_worker(self, artist: str, album: str, mb_client: 'MusicBrainzClient', dc_client: 'DiscogsClient') -> bool:
        """Worker para búsqueda de fecha de lanzamiento"""
        track_hint = self.db.get_scrobble_context_for_album(artist, album)

        # Intentar MusicBrainz primero
        search_result = mb_client.search_release(artist, album, track_hint)
        if search_result and search_result.get('releases'):
            release = search_result['releases'][0]
            if 'date' in release and release['date']:
                try:
                    release_year = int(release['date'][:4])
                    self.db.save_album_release_date(artist, album, release_year, release['date'])
                    return True
                except (ValueError, TypeError):
                    pass

        # Fallback a Discogs
        if dc_client.token:
            discogs_result = dc_client.search_release(artist, album)
            if discogs_result and discogs_result.get('results'):
                for result in discogs_result['results'][:3]:
                    if result.get('year'):
                        try:
                            release_year = int(result.get('year'))
                            self.db.save_album_release_date(artist, album, release_year, str(release_year))
                            return True
                        except (ValueError, TypeError):
                            continue

        return False

    def _search_album_label_worker(self, artist: str, album: str, mb_client: 'MusicBrainzClient', dc_client: 'DiscogsClient') -> bool:
        """Worker para búsqueda de sello discográfico"""
        track_hint = self.db.get_scrobble_context_for_album(artist, album)

        # Intentar MusicBrainz primero
        search_result = mb_client.search_release(artist, album, track_hint)
        if search_result and search_result.get('releases'):
            release = search_result['releases'][0]
            mbid = release['id']

            mb_data = mb_client.get_release_by_mbid(mbid)
            if mb_data and 'label-info' in mb_data and mb_data['label-info']:
                label = mb_data['label-info'][0]['label']['name']
                self.db.save_album_label(artist, album, label)
                return True

        # Fallback a Discogs
        if dc_client.token:
            discogs_result = dc_client.search_release(artist, album)
            if discogs_result and discogs_result.get('results'):
                for result in discogs_result['results'][:3]:
                    if 'label' in result and result['label']:
                        label = result['label'][0] if isinstance(result['label'], list) else result['label']
                        self.db.save_album_label(artist, album, label)
                        return True

        return False

    def _search_album_genres_worker(self, artist: str, album: str, mb_client: 'MusicBrainzClient', dc_client: 'DiscogsClient') -> bool:
        """Worker para búsqueda de géneros de álbum usando MBIDs existentes cuando sea posible"""
        found_genres = False

        # Primero intentar usar MBID existente de album_details
        mbid, release_group_mbid = self.db.get_album_mbid(artist, album)

        if mbid:
            if self.debug_mode:
                print(f"🔍 Usando MBID existente para {artist} - {album}: {mbid}")

            # Usar MBID directo para obtener géneros
            mb_data = mb_client.get_release_by_mbid(mbid)
            if mb_data:
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
                    genres_saved = self.db.save_album_genres(artist, album, 'musicbrainz', mb_album_genres)
                    if self.debug_mode:
                        print(f"✅ MB (MBID directo): {artist} - {album} - {genres_saved} géneros guardados")
                    found_genres = True
        else:
            # Fallback a búsqueda por nombre si no hay MBID
            if self.debug_mode:
                print(f"🔍 No hay MBID, buscando por nombre: {artist} - {album}")

            track_hint = self.db.get_scrobble_context_for_album(artist, album)
            search_result = mb_client.search_release(artist, album, track_hint)

            if search_result and search_result.get('releases'):
                release = search_result['releases'][0]
                found_mbid = release['id']

                mb_data = mb_client.get_release_by_mbid(found_mbid)
                if mb_data:
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
                        genres_saved = self.db.save_album_genres(artist, album, 'musicbrainz', mb_album_genres)
                        if self.debug_mode:
                            print(f"✅ MB (búsqueda): {artist} - {album} - {genres_saved} géneros guardados")
                        found_genres = True

        # Buscar también en Discogs
        if dc_client.token:
            discogs_result = dc_client.search_release(artist, album)
            if discogs_result and discogs_result.get('results'):
                for result in discogs_result['results'][:3]:
                    if 'genre' in result and result['genre']:
                        discogs_genres = [
                            {'name': genre, 'weight': 1.0}
                            for genre in result['genre'][:10]
                            if genre and genre.strip()
                        ]
                        if discogs_genres:
                            genres_saved = self.db.save_album_genres(artist, album, 'discogs', discogs_genres)
                            if self.debug_mode:
                                print(f"✅ DISCOGS: {artist} - {album} - {genres_saved} géneros guardados")
                            found_genres = True
                            break

        return found_genres

    def _search_artist_genres_musicbrainz(self, artist_name: str) -> bool:
        """Busca géneros de artista en MusicBrainz - versión legacy"""
        # Crear cliente temporal para compatibilidad
        mb_client, _ = self._create_worker_clients()
        return self._search_artist_genres_musicbrainz_worker(artist_name, mb_client)

    def enhance_album_metadata(self, albums: Set[Tuple[str, str]], metadata_type: str = 'all'):
        """Wrapper que elige entre versión concurrente o secuencial"""
        if self.max_workers > 1:
            self.enhance_album_metadata_concurrent(albums, metadata_type)
        else:
            self.enhance_album_metadata_sequential(albums, metadata_type)

    def enhance_album_metadata_sequential(self, albums: Set[Tuple[str, str]], metadata_type: str = 'all'):
        """Versión secuencial para compatibilidad o debug"""
        print(f"\n💿 Buscando metadatos de álbumes ({metadata_type})...")

        processed = 0
        total = len(albums)
        found_count = 0

        for artist, album in albums:
            processed += 1
            if processed % 15 == 0:
                print(f"   📊 {processed}/{total} álbumes procesados ({found_count} con datos encontrados)")
                self.db.force_commit()

            try:
                album_found = False

                if metadata_type in ['release_date', 'all']:
                    if self._search_album_release_date(artist, album):
                        album_found = True

                if metadata_type in ['label', 'all']:
                    if self._search_album_label(artist, album):
                        album_found = True

                if metadata_type in ['genres', 'all']:
                    if self._search_album_genres(artist, album):
                        album_found = True

                if album_found:
                    found_count += 1

            except Exception as e:
                print(f"   ⚠️ Error procesando álbum {artist} - {album}: {e}")
                continue

        self.db.force_commit()
        print(f"   ✅ Completado: {found_count}/{total} álbumes con metadatos encontrados")
        """Busca géneros de artista en Discogs - retorna True si encuentra algo"""
        if not self.discogs_tokens:
            if self.debug_mode:
                print("❌ DISCOGS: No hay tokens configurados")
            return False

        if self.debug_mode:
            print(f"🔍 DISCOGS: Buscando {artist_name}")

        search_result = self.discogs.search_artist(artist_name)

        # Si hay error (posible rate limit), intentar rotar
        if not search_result:
            if self.debug_mode:
                print(f"⚠️ DISCOGS: Error en búsqueda, intentando rotar...")
            self._handle_rate_limit_or_error('discogs')
            # Reintentar una vez con nuevo token/proxy
            search_result = self.discogs.search_artist(artist_name)

        if not search_result or not search_result.get('results'):
            if self.debug_mode:
                print(f"❌ DISCOGS: No se encontró {artist_name}")
            return False

        if self.debug_mode:
            print(f"📝 DISCOGS: {len(search_result['results'])} resultados para {artist_name}")

        for i, result in enumerate(search_result['results'][:3]):  # Revisar top 3 resultados
            if 'id' not in result:
                if self.debug_mode:
                    print(f"⚠️ DISCOGS: Resultado {i+1} sin ID")
                continue

            try:
                artist_details = self.discogs.get_artist_details(result['id'])

                # Si hay error, intentar rotar y reintentar
                if not artist_details:
                    if self.debug_mode:
                        print(f"⚠️ DISCOGS: Error obteniendo detalles, rotando...")
                    self._handle_rate_limit_or_error('discogs')
                    artist_details = self.discogs.get_artist_details(result['id'])

                if not artist_details:
                    if self.debug_mode:
                        print(f"⚠️ DISCOGS: No se pudieron obtener detalles para ID {result['id']}")
                    continue

                if self.debug_mode:
                    print(f"🔍 DISCOGS: Detalles obtenidos para {artist_name}")
                    print(f"    Campos disponibles: {list(artist_details.keys())}")

                # Buscar géneros en diferentes campos posibles
                discogs_genres = []

                # Campo 'genres' (lista)
                if 'genres' in artist_details and artist_details['genres']:
                    discogs_genres.extend([
                        {'name': genre, 'weight': 1.0}
                        for genre in artist_details['genres']
                        if genre and genre.strip()
                    ])

                # Campo 'styles' (subestilos)
                if 'styles' in artist_details and artist_details['styles']:
                    discogs_genres.extend([
                        {'name': style, 'weight': 0.8}
                        for style in artist_details['styles']
                        if style and style.strip()
                    ])

                if discogs_genres:
                    genres_saved = self.db.save_artist_genres_detailed(artist_name, 'discogs', discogs_genres)
                    if self.debug_mode:
                        print(f"✅ DISCOGS: {artist_name} - {genres_saved} géneros guardados")
                        print(f"    Géneros: {[g['name'] for g in discogs_genres]}")
                    return True

            except Exception as e:
                if self.debug_mode:
                    print(f"⚠️ DISCOGS: Error procesando detalles para {artist_name}: {e}")
                # En caso de error, intentar rotar
                self._handle_rate_limit_or_error('discogs')
                continue

        if self.debug_mode:
            print(f"❌ DISCOGS: {artist_name} - sin géneros disponibles")
        return False

    def enhance_album_metadata(self, albums: Set[Tuple[str, str]], metadata_type: str = 'all'):
        """Busca metadatos de álbumes (fecha, sello, géneros)"""
        print(f"\n💿 Buscando metadatos de álbumes ({metadata_type})...")

        processed = 0
        total = len(albums)
        found_count = 0

        for artist, album in albums:
            processed += 1
            if processed % 15 == 0:  # Reporte más frecuente
                print(f"   📊 {processed}/{total} álbumes procesados ({found_count} con datos encontrados)")
                self.db.force_commit()  # Commit periódico

            try:
                album_found = False

                if metadata_type in ['release_date', 'all']:
                    if self._search_album_release_date(artist, album):
                        album_found = True

                if metadata_type in ['label', 'all']:
                    if self._search_album_label(artist, album):
                        album_found = True

                if metadata_type in ['genres', 'all']:
                    if self._search_album_genres(artist, album):
                        album_found = True

                if album_found:
                    found_count += 1

            except Exception as e:
                print(f"   ⚠️ Error procesando álbum {artist} - {album}: {e}")
                continue

        # Commit final
        self.db.force_commit()
        print(f"   ✅ Completado: {found_count}/{total} álbumes con metadatos encontrados")

    def _search_album_release_date(self, artist: str, album: str) -> bool:
        """Busca fecha de lanzamiento en MusicBrainz y Discogs (versión legacy)"""
        mb_client, dc_client = self._create_worker_clients()
        return self._search_album_release_date_worker(artist, album, mb_client, dc_client)

    def _search_album_label(self, artist: str, album: str) -> bool:
        """Busca sello discográfico en MusicBrainz y Discogs (versión legacy)"""
        mb_client, dc_client = self._create_worker_clients()
        return self._search_album_label_worker(artist, album, mb_client, dc_client)

    def _search_album_genres(self, artist: str, album: str) -> bool:
        """Busca géneros de álbum usando MBIDs existentes cuando sea posible (versión legacy)"""
        mb_client, dc_client = self._create_worker_clients()
        return self._search_album_genres_worker(artist, album, mb_client, dc_client)

    def print_status_report(self):
        """Imprime reporte de estado detallado"""
        print("\n" + "="*80)
        print("📊 REPORTE DE ESTADO DE METADATOS")
        print("="*80)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Obtener estadísticas
        all_artists_scrobbles = self.db.get_all_artists()
        all_albums_scrobbles = self.db.get_all_albums()
        all_tracks_scrobbles = self.db.get_all_tracks()

        artists_in_details = self.db.get_artists_in_details_table()
        albums_in_details = self.db.get_albums_in_details_table()
        tracks_in_details = self.db.get_tracks_in_details_table()

        artists_missing_mb_genres = self.db.get_artists_without_musicbrainz_genres()
        artists_missing_discogs_genres = self.db.get_artists_without_discogs_genres()

        albums_missing_dates = self.db.get_albums_without_release_dates()
        albums_missing_labels = self.db.get_albums_without_labels()
        albums_missing_genres = self.db.get_albums_without_genres()
        album_genre_stats = self.db.get_albums_stats_for_genres()

        # ARTISTAS
        print("\n👥 ARTISTAS:")
        print(f"   • Total en scrobbles: {len(all_artists_scrobbles)}")
        print(f"   • Total en artist_details: {len(artists_in_details)}")
        print(f"   • Sin géneros de MusicBrainz: {len(artists_missing_mb_genres)} ({len(artists_missing_mb_genres)/len(all_artists_scrobbles)*100:.1f}%)")
        print(f"   • Sin géneros de Discogs: {len(artists_missing_discogs_genres)} ({len(artists_missing_discogs_genres)/len(all_artists_scrobbles)*100:.1f}%)")

        # ÁLBUMES
        print("\n💿 ÁLBUMES:")
        print(f"   • Total en scrobbles: {len(all_albums_scrobbles)}")
        print(f"   • Total en album_details: {len(albums_in_details)}")
        print(f"   • Sin fecha de lanzamiento: {len(albums_missing_dates)} ({len(albums_missing_dates)/len(all_albums_scrobbles)*100:.1f}%)")
        print(f"   • Sin sello discográfico: {len(albums_missing_labels)} ({len(albums_missing_labels)/len(all_albums_scrobbles)*100:.1f}%)")
        print(f"   • Sin géneros: {len(albums_missing_genres)} ({len(albums_missing_genres)/len(all_albums_scrobbles)*100:.1f}%)")
        print(f"     - Con MBID disponible: {album_genre_stats['with_mbid_no_genres']}")
        print(f"     - Sin MBID: {album_genre_stats['without_mbid_no_genres']}")

        # TRACKS
        print("\n🎵 TRACKS:")
        print(f"   • Total en scrobbles: {len(all_tracks_scrobbles)}")
        print(f"   • Total en track_details: {len(tracks_in_details)}")
        print(f"   • Sin detalles: {len(all_tracks_scrobbles) - len(tracks_in_details)} ({(len(all_tracks_scrobbles) - len(tracks_in_details))/len(all_tracks_scrobbles)*100:.1f}%)")

        # ESTADÍSTICAS DE PROCESAMIENTO
        if self.stats['total_processed'] > 0:
            print("\n📈 ESTADÍSTICAS DE PROCESAMIENTO:")
            print(f"   • Total procesados: {self.stats['total_processed']}")
            print(f"   • MusicBrainz encontrados: {self.stats['musicbrainz_found']}")
            print(f"   • MusicBrainz no encontrados: {self.stats['musicbrainz_not_found']}")
            print(f"   • Discogs encontrados (solo álbumes): {self.stats['discogs_found']}")
            print(f"   • Discogs no encontrados: {self.stats['discogs_not_found']}")
            if self.use_proxies:
                print(f"   • Fallos de proxy: {self.stats['proxy_failures']}")
                if self.proxy_manager:
                    print(f"   • Proxies disponibles: {len(self.proxy_manager.proxies)}")
                    print(f"   • Proxies fallidos: {len(self.proxy_manager.failed_proxies)}")
            if len(self.discogs_tokens) > 1:
                print(f"   • Tokens de Discogs disponibles: {len(self.discogs_tokens)}")
            if self.max_workers > 1:
                print(f"   • Hilos concurrentes: {self.max_workers}")
                print(f"   • Errores de concurrencia: {self.stats['concurrent_errors']}")

        print("\n" + "="*80)

    def run_enhancement(self, mode: str = 'all', limit: Optional[int] = None):
        """Ejecuta el proceso de mejora de metadatos"""
        print("🚀 INICIANDO MEJORA DE METADATOS")
        print("="*60)

        if mode in ['artists', 'all']:
            # Géneros de artistas (solo MusicBrainz)
            artists_mb = self.db.get_artists_without_musicbrainz_genres()

            if limit:
                artists_mb = set(list(artists_mb)[:limit])

            if artists_mb:
                print(f"\n🎯 Procesando {len(artists_mb)} artistas sin géneros de MusicBrainz")
                self.enhance_artist_genres(artists_mb, 'musicbrainz')

        if mode in ['albums', 'all']:
            # Metadatos de álbumes
            albums_dates = self.db.get_albums_without_release_dates()
            albums_labels = self.db.get_albums_without_labels()
            albums_genres = self.db.get_albums_without_genres()

            if limit:
                albums_dates = set(list(albums_dates)[:limit])
                albums_labels = set(list(albums_labels)[:limit])
                albums_genres = set(list(albums_genres)[:limit])

            if albums_dates:
                print(f"\n🎯 Procesando {len(albums_dates)} álbumes sin fechas de lanzamiento")
                self.enhance_album_metadata(albums_dates, 'release_date')

            if albums_labels:
                print(f"\n🎯 Procesando {len(albums_labels)} álbumes sin sellos discográficos")
                self.enhance_album_metadata(albums_labels, 'label')

            if albums_genres:
                print(f"\n🎯 Procesando {len(albums_genres)} álbumes sin géneros")
                self.enhance_album_metadata(albums_genres, 'genres')

        print("\n✅ MEJORA DE METADATOS COMPLETADA")

    def close(self):
        self.db.close()


def main():
    parser = argparse.ArgumentParser(description='Mejora de metadatos de Last.fm')
    parser.add_argument('--status', action='store_true',
                       help='Muestra reporte de estado de metadatos')
    parser.add_argument('--enhance', choices=['artists', 'albums', 'all'],
                       help='Mejora metadatos específicos')
    parser.add_argument('--limit', type=int,
                       help='Límite de elementos a procesar por tipo')
    parser.add_argument('--debug', action='store_true',
                       help='Activa modo debug con logging detallado')
    parser.add_argument('--proxied', action='store_true',
                       help='Usa proxies para las consultas (lee del .env)')
    parser.add_argument('--workers', type=int, default=5,
                       help='Número de hilos concurrentes (default: 5)')

    args = parser.parse_args()

    if not args.status and not args.enhance:
        print("❌ Debes especificar --status o --enhance")
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
        enhancer = MetadataEnhancer(
            debug_mode=args.debug,
            use_proxies=args.proxied,
            max_workers=args.workers
        )

        if args.status:
            enhancer.print_status_report()

        if args.enhance:
            enhancer.run_enhancement(args.enhance, args.limit)

        enhancer.close()

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

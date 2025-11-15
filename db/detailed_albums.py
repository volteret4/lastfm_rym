#!/usr/bin/env python3
"""
High-Performance Metadata Enhancement Script
Rate limiting per-proxy para aprovechar al máximo múltiples proxies
Optimizado para velocidad máxima con MusicBrainz (sin tokens) y Discogs (con tokens limitados)
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
import unicodedata
import re
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

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
        if not text:
            return ""
        text = text.lower()
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        text = re.sub(r'[^\w\s]', ' ', text)
        text = ' '.join(text.split())
        return text.strip()

    @staticmethod
    def clean_for_search(text: str) -> Tuple[str, str]:
        if not text:
            return "", ""
        original = text
        cleaned = text
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
        cleaned = re.sub(r'\{[^}]*\}', '', cleaned)

        special_versions = [
            r'\b(remaster(?:ed)?|deluxe|expanded|special|anniversary|edition|version)\b',
            r'\b(feat(?:uring)?|ft\.?|with)\s+[^-]*',
            r'\b(remix|mix|radio\s+edit|extended|acoustic)\b',
            r'\b\d+th\s+anniversary\b',
            r'\b(mono|stereo)\b'
        ]

        for pattern in special_versions:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r'[^\w\s\-]', ' ', cleaned)
        cleaned = ' '.join(cleaned.split())
        cleaned = cleaned.strip()
        return cleaned, original

    @staticmethod
    def generate_search_variants(text: str) -> List[str]:
        if not text:
            return []
        variants = []
        cleaned, original = TextNormalizer.clean_for_search(text)
        variants.append(original.strip())
        if cleaned != original and cleaned:
            variants.append(cleaned)
        super_clean = re.sub(r'[^\w\s]', ' ', cleaned)
        super_clean = ' '.join(super_clean.split())
        if super_clean and super_clean not in variants:
            variants.append(super_clean)
        return [v for v in variants if v]


class HighPerformanceProxyManager:
    """Gestor de proxies optimizado para máximo rendimiento"""

    def __init__(self, use_proxies: bool = False):
        self.use_proxies = use_proxies
        self.proxies = []
        self.current_proxy_index = 0
        self.failed_proxies = set()
        self.lock = threading.Lock()

        # Rate limiting per-proxy - cada proxy puede hacer ~1 req/sec independientemente
        self.proxy_last_request = {}  # proxy_id -> timestamp
        self.proxy_locks = {}  # proxy_id -> Lock

        if use_proxies:
            self._load_proxies()

    def _load_proxies(self):
        """Carga proxies optimizado para máximo throughput"""
        proxy_list = os.getenv('PROXIES', '').strip().strip('"').strip("'")

        if not proxy_list:
            i = 1
            while True:
                proxy = os.getenv(f'PROXY_{i}', '')
                if not proxy:
                    break
                proxy_clean = proxy.strip().strip('"').strip("'")
                if proxy_clean:
                    parsed = self._parse_proxy(proxy_clean, i)
                    if parsed:
                        self.proxies.append(parsed)
                i += 1
        else:
            for i, proxy_str in enumerate(proxy_list.split(','), 1):
                proxy_clean = proxy_str.strip().strip('"').strip("'")
                if proxy_clean:
                    parsed = self._parse_proxy(proxy_clean, i)
                    if parsed:
                        self.proxies.append(parsed)

        if not self.proxies:
            print("⚠️ No se encontraron proxies válidos")
            self.use_proxies = False
        else:
            print(f"🚀 Sistema HIGH-PERFORMANCE: {len(self.proxies)} proxies cargados")
            print(f"📊 Throughput teórico: ~{len(self.proxies)} requests/segundo")
            for i, proxy in enumerate(self.proxies, 1):
                print(f"   {i}. {proxy['display']}")

    def _parse_proxy(self, proxy_string: str, proxy_id: int) -> Optional[Dict]:
        """Parse proxy con ID único para tracking"""
        if not proxy_string:
            return None

        auth = None
        host_port = proxy_string

        if '@' in proxy_string:
            auth_part, host_port = proxy_string.rsplit('@', 1)
            if ':' in auth_part:
                auth = auth_part

        # Credenciales globales
        global_user = os.getenv('PROXY_USER', '').strip().strip('"').strip("'")
        global_pass = os.getenv('PROXY_PASS', '').strip().strip('"').strip("'")

        if not auth and global_user and global_pass:
            auth = f"{global_user}:{global_pass}"

        if ':' not in host_port:
            return None

        try:
            host, port = host_port.rsplit(':', 1)
            int(port)
        except ValueError:
            return None

        proxy_url = f"http://{auth}@{host}:{port}" if auth else f"http://{host}:{port}"

        return {
            'id': f"proxy_{proxy_id}",
            'http': proxy_url,
            'https': proxy_url,
            'display': f"{host}:{port}" + (" (auth)" if auth else ""),
            'host_port': f"{host}:{port}"
        }

    def get_proxy_for_thread(self, thread_id: str) -> Optional[Dict]:
        """Obtiene proxy específico para un thread - distribución round-robin"""
        if not self.use_proxies or not self.proxies:
            return None

        with self.lock:
            available_proxies = [p for p in self.proxies if p['id'] not in self.failed_proxies]

            if not available_proxies:
                print("🔄 Reseteando proxies fallidos...")
                self.failed_proxies.clear()
                available_proxies = self.proxies

            if not available_proxies:
                return None

            # Round robin para distribución uniforme
            proxy = available_proxies[self.current_proxy_index % len(available_proxies)]
            self.current_proxy_index += 1

            return proxy

    def wait_for_proxy_rate_limit(self, proxy_id: str, min_delay: float = 0.8):
        """Rate limiting específico per-proxy - permite máximo throughput"""
        if not proxy_id:
            return

        # Crear lock específico para este proxy si no existe
        if proxy_id not in self.proxy_locks:
            with self.lock:
                if proxy_id not in self.proxy_locks:
                    self.proxy_locks[proxy_id] = threading.Lock()

        proxy_lock = self.proxy_locks[proxy_id]

        with proxy_lock:
            last_request = self.proxy_last_request.get(proxy_id, 0)
            elapsed = time.time() - last_request

            if elapsed < min_delay:
                sleep_time = min_delay - elapsed
                time.sleep(sleep_time)

            self.proxy_last_request[proxy_id] = time.time()

    def mark_proxy_failed(self, proxy_id: str):
        """Marca proxy como fallido"""
        if proxy_id:
            with self.lock:
                self.failed_proxies.add(proxy_id)
                print(f"❌ Proxy {proxy_id} marcado como fallido")


class HighPerformanceApiClient:
    """Cliente API optimizado para máximo throughput con rate limiting per-proxy"""

    def __init__(self, base_url: str, proxy_manager: Optional[HighPerformanceProxyManager] = None,
                 default_delay: float = 0.8, debug: bool = False):
        self.base_url = base_url
        self.proxy_manager = proxy_manager
        self.default_delay = default_delay
        self.debug = debug
        self.session = requests.Session()
        self.consecutive_errors = 0
        self.max_errors = 5

    def get(self, url: str, params: Dict = None, headers: Dict = None, timeout: int = 10) -> Optional[Dict]:
        """Request optimizado con rate limiting per-proxy"""
        if self.consecutive_errors >= self.max_errors:
            return None

        thread_id = threading.current_thread().name
        proxy_config = None
        proxy_id = "direct"
        proxy_display = "direct"

        # Obtener proxy específico para este thread
        if self.proxy_manager and self.proxy_manager.use_proxies:
            proxy_data = self.proxy_manager.get_proxy_for_thread(thread_id)
            if proxy_data:
                proxy_config = {'http': proxy_data['http'], 'https': proxy_data['https']}
                proxy_id = proxy_data['id']
                proxy_display = proxy_data['display']

        # Rate limiting específico para este proxy
        if self.proxy_manager:
            self.proxy_manager.wait_for_proxy_rate_limit(proxy_id, self.default_delay)
        else:
            time.sleep(self.default_delay)  # Fallback global

        if self.debug:
            print(f"🌐 [{thread_id}] {self.base_url} -> {proxy_display}")

        try:
            response = self.session.get(url, params=params, headers=headers,
                                      timeout=timeout, proxies=proxy_config)

            if response.status_code == 200:
                self.consecutive_errors = 0
                return response.json()
            elif response.status_code == 429:
                # Rate limit hit - esperar y reintentar
                retry_after = int(response.headers.get('Retry-After', 30))
                print(f"   ⏳ Rate limit {proxy_display}: esperando {retry_after}s")
                time.sleep(retry_after)
                return self.get(url, params, headers, timeout)
            elif response.status_code in [502, 503, 504]:
                print(f"   ⚠️ Server error {response.status_code} via {proxy_display}")
                time.sleep(1)
                return None

            self.consecutive_errors += 1
            return None

        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError):
            if self.proxy_manager and proxy_id != "direct":
                self.proxy_manager.mark_proxy_failed(proxy_id)
            self.consecutive_errors += 1
            return None
        except requests.exceptions.Timeout:
            print(f"   ⏱️ Timeout via {proxy_display}")
            self.consecutive_errors += 1
            return None
        except Exception as e:
            if self.debug:
                print(f"   ❌ Error via {proxy_display}: {e}")
            self.consecutive_errors += 1
            return None


class MusicBrainzHighPerformanceClient(HighPerformanceApiClient):
    """Cliente MusicBrainz optimizado - SIN rate limiting agresivo ya que no usa tokens"""

    def __init__(self, proxy_manager: Optional[HighPerformanceProxyManager] = None, debug: bool = False):
        # MusicBrainz permite ~1 req/sec por IP, con proxies podemos hacer muchas más
        super().__init__("https://musicbrainz.org/ws/2/", proxy_manager, 0.8, debug)
        self.session.headers.update({
            'User-Agent': 'HighPerformance-Metadata-Enhancer/1.0'
        })

    def search_artist(self, artist_name: str) -> Optional[Dict]:
        search_variants = TextNormalizer.generate_search_variants(artist_name)
        for variant in search_variants[:2]:
            params = {'query': f'artist:"{variant}"', 'fmt': 'json', 'limit': 3}
            result = self.get(f"{self.base_url}artist/", params)
            if result and result.get('artists'):
                return result
        return None

    def get_artist_by_mbid(self, mbid: str) -> Optional[Dict]:
        params = {'fmt': 'json', 'inc': 'genres+tags'}
        return self.get(f"{self.base_url}artist/{mbid}", params)

    def search_release(self, artist: str, album: str, track_hint: Optional[str] = None) -> Optional[Dict]:
        album_variants = TextNormalizer.generate_search_variants(album)
        artist_variants = TextNormalizer.generate_search_variants(artist)

        for album_variant in album_variants[:2]:
            for artist_variant in artist_variants[:2]:
                query = f'release:"{album_variant}" AND artist:"{artist_variant}"'
                params = {'query': query, 'fmt': 'json', 'limit': 3}
                result = self.get(f"{self.base_url}release/", params)
                if result and result.get('releases'):
                    return result
        return None

    def get_release_by_mbid(self, mbid: str) -> Optional[Dict]:
        params = {'fmt': 'json', 'inc': 'release-groups+labels+recordings+genres+tags'}
        return self.get(f"{self.base_url}release/{mbid}", params)


class DiscogsHighPerformanceClient(HighPerformanceApiClient):
    """Cliente Discogs con rate limiting más estricto por tokens limitados"""

    def __init__(self, token: str, proxy_manager: Optional[HighPerformanceProxyManager] = None, debug: bool = False):
        # Discogs es más estricto con rate limiting
        super().__init__("https://api.discogs.com/", proxy_manager, 1.0, debug)
        self.token = token
        if token:
            self.session.headers.update({
                'Authorization': f'Discogs token={token}',
                'User-Agent': 'HighPerformance-Metadata-Enhancer/1.0'
            })

    def search_release(self, artist: str, album: str) -> Optional[Dict]:
        if not self.token:
            return None

        artist_variants = TextNormalizer.generate_search_variants(artist)
        album_variants = TextNormalizer.generate_search_variants(album)

        for artist_variant in artist_variants[:2]:
            for album_variant in album_variants[:2]:
                params = {
                    'q': f'{artist_variant} {album_variant}',
                    'type': 'release',
                    'per_page': 3
                }
                result = self.get(f"{self.base_url}database/search", params)
                if result and result.get('results'):
                    return result
        return None


class MetadataDatabase:
    """Database con commits optimizados para high-throughput"""

    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.pending_commits = 0
        self.max_pending = 50  # Commits más frecuentes

    def get_albums_without_genres(self) -> Set[Tuple[str, str]]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist, s.album
            FROM scrobbles s
            LEFT JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
            WHERE s.album IS NOT NULL AND s.album != "" AND ag.artist IS NULL
        ''')
        return {(row['artist'], row['album']) for row in cursor.fetchall()}

    def get_album_mbid(self, artist: str, album: str) -> Optional[Tuple[str, str]]:
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

    def save_album_genres(self, artist: str, album: str, source: str, genres: List[Dict]):
        """Optimizado para high-throughput"""
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
            if self.pending_commits >= self.max_pending:
                self.conn.commit()
                self.pending_commits = 0

    def force_commit(self):
        with self.lock:
            self.conn.commit()
            self.pending_commits = 0

    def close(self):
        self.force_commit()
        self.conn.close()


class HighPerformanceEnhancer:
    """Enhancer optimizado para máximo throughput"""

    def __init__(self, debug: bool = False, use_proxies: bool = False, max_workers: int = 20):
        self.debug = debug
        self.max_workers = max_workers

        # Proxy manager optimizado
        self.proxy_manager = HighPerformanceProxyManager(use_proxies) if use_proxies else None

        # Tokens de Discogs
        self.discogs_tokens = self._load_discogs_tokens()
        self.token_index = 0
        self.token_lock = threading.Lock()

        # Database
        self.db = MetadataDatabase()

        # Stats thread-safe
        self.stats_lock = threading.Lock()
        self.stats = {
            'processed': 0,
            'found_mb': 0,
            'found_discogs': 0,
            'errors': 0
        }

        print(f"🚀 HIGH-PERFORMANCE ENHANCER")
        print(f"   Workers: {max_workers}")
        print(f"   Proxies: {'Enabled' if use_proxies else 'Disabled'}")
        print(f"   Discogs tokens: {len(self.discogs_tokens)}")

        if use_proxies and self.proxy_manager:
            expected_throughput = len(self.proxy_manager.proxies) * 1.2  # ~1.2 req/sec per proxy
            print(f"   Expected throughput: ~{expected_throughput:.1f} req/sec")

    def _load_discogs_tokens(self) -> List[str]:
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

    def _get_next_discogs_token(self) -> str:
        """Rotación thread-safe de tokens"""
        if not self.discogs_tokens:
            return ''

        with self.token_lock:
            token = self.discogs_tokens[self.token_index % len(self.discogs_tokens)]
            self.token_index = (self.token_index + 1) % len(self.discogs_tokens)
            return token

    def _update_stats(self, stat: str, value: int = 1):
        with self.stats_lock:
            self.stats[stat] = self.stats.get(stat, 0) + value

    def process_album_worker(self, album_data: Tuple[str, str]) -> bool:
        """Worker optimizado para procesar álbum"""
        artist, album = album_data

        try:
            # Crear clientes para este thread
            mb_client = MusicBrainzHighPerformanceClient(self.proxy_manager, self.debug)
            discogs_token = self._get_next_discogs_token()
            discogs_client = DiscogsHighPerformanceClient(discogs_token, self.proxy_manager, self.debug)

            found_genres = False

            # 1. Intentar con MBID existente (más rápido)
            mbid, release_group_mbid = self.db.get_album_mbid(artist, album)
            if mbid:
                if self.debug:
                    print(f"🔍 Usando MBID directo: {artist} - {album}")

                mb_data = mb_client.get_release_by_mbid(mbid)
                if mb_data:
                    mb_genres = []
                    if 'genres' in mb_data and mb_data['genres']:
                        mb_genres = [{'name': g['name'], 'weight': 1.0} for g in mb_data['genres']]
                    elif 'tags' in mb_data and mb_data['tags']:
                        mb_genres = [{'name': t['name'], 'weight': float(t.get('count', 1))} for t in mb_data['tags'][:8]]

                    if mb_genres:
                        self.db.save_album_genres(artist, album, 'musicbrainz', mb_genres)
                        found_genres = True

            # 2. Búsqueda por nombre en MusicBrainz
            if not found_genres:
                search_result = mb_client.search_release(artist, album)
                if search_result and search_result.get('releases'):
                    release = search_result['releases'][0]
                    found_mbid = release['id']

                    mb_data = mb_client.get_release_by_mbid(found_mbid)
                    if mb_data:
                        mb_genres = []
                        if 'genres' in mb_data and mb_data['genres']:
                            mb_genres = [{'name': g['name'], 'weight': 1.0} for g in mb_data['genres']]
                        elif 'tags' in mb_data and mb_data['tags']:
                            mb_genres = [{'name': t['name'], 'weight': float(t.get('count', 1))} for t in mb_data['tags'][:8]]

                        if mb_genres:
                            self.db.save_album_genres(artist, album, 'musicbrainz', mb_genres)
                            found_genres = True
                            self._update_stats('found_mb')

            # 3. Discogs como complemento
            if discogs_token:
                discogs_result = discogs_client.search_release(artist, album)
                if discogs_result and discogs_result.get('results'):
                    result = discogs_result['results'][0]
                    if 'genre' in result and result['genre']:
                        discogs_genres = [
                            {'name': genre, 'weight': 1.0}
                            for genre in result['genre'][:8]
                            if genre and genre.strip()
                        ]
                        if discogs_genres:
                            self.db.save_album_genres(artist, album, 'discogs', discogs_genres)
                            found_genres = True
                            self._update_stats('found_discogs')

            self._update_stats('processed')
            return found_genres

        except Exception as e:
            if self.debug:
                print(f"❌ Error en {artist} - {album}: {e}")
            self._update_stats('errors')
            return False

    def enhance_albums_high_performance(self, limit: int = 1000):
        """Procesamiento de álbumes optimizado para máximo throughput"""
        albums = list(self.db.get_albums_without_genres())[:limit]

        if not albums:
            print("✅ No hay álbumes pendientes")
            return

        print(f"\n🚀 PROCESANDO {len(albums)} ÁLBUMES")
        print(f"📊 Workers: {self.max_workers}")

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.process_album_worker, album) for album in albums]

            completed = 0
            for future in as_completed(futures):
                completed += 1

                if completed % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"   📊 {completed}/{len(albums)} - {rate:.1f} albums/sec")
                    self.db.force_commit()

        self.db.force_commit()

        # Stats finales
        elapsed = time.time() - start_time
        total_rate = len(albums) / elapsed if elapsed > 0 else 0

        print(f"\n✅ COMPLETADO EN {elapsed:.1f}s")
        print(f"📊 ESTADÍSTICAS:")
        print(f"   • Procesados: {self.stats['processed']}")
        print(f"   • MusicBrainz encontrados: {self.stats['found_mb']}")
        print(f"   • Discogs encontrados: {self.stats['found_discogs']}")
        print(f"   • Errores: {self.stats['errors']}")
        print(f"   • Rate promedio: {total_rate:.1f} albums/sec")

    def close(self):
        self.db.close()


def main():
    parser = argparse.ArgumentParser(description='High-Performance Metadata Enhancer')
    parser.add_argument('--limit', type=int, default=1000, help='Límite de álbumes a procesar')
    parser.add_argument('--workers', type=int, default=20, help='Número de workers (default: 20)')
    parser.add_argument('--proxied', action='store_true', help='Usar proxies')
    parser.add_argument('--debug', action='store_true', help='Debug mode')

    args = parser.parse_args()

    if args.workers > 50:
        print("⚠️ Más de 50 workers puede ser contraproducente")
        response = input("¿Continuar? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)

    try:
        enhancer = HighPerformanceEnhancer(
            debug=args.debug,
            use_proxies=args.proxied,
            max_workers=args.workers
        )

        enhancer.enhance_albums_high_performance(args.limit)
        enhancer.close()

    except KeyboardInterrupt:
        print("\n⚠️ Interrumpido")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

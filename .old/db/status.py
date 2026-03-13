#!/usr/bin/env python3
"""
Metadata Enhancement and Status Script
Busca y actualiza metadatos faltantes para artistas y álbumes usando MusicBrainz y Discogs
Proporciona estadísticas detalladas del estado de la base de datos
"""

import os
import sys
import requests
import json
import sqlite3
import time
import argparse
import threading
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import unicodedata
import re

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_API_KEY') or not os.getenv('DISCOGS_TOKEN'):
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
        """Álbumes sin géneros"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist, s.album
            FROM scrobbles s
            LEFT JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
            WHERE s.album IS NOT NULL AND s.album != "" AND ag.artist IS NULL
        ''')
        return {(row['artist'], row['album']) for row in cursor.fetchall()}

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

    def save_artist_genres_detailed(self, artist: str, source: str, genres: List[Dict]):
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

    def save_album_release_date(self, artist: str, album: str, release_year: Optional[int], release_date: Optional[str]):
        """Guarda la fecha de lanzamiento de un álbum"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_release_dates (artist, album, release_year, release_date, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (artist, album, release_year, release_date, int(time.time())))
            self.conn.commit()

    def save_album_label(self, artist: str, album: str, label: Optional[str]):
        """Guarda el sello de un álbum"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO album_labels (artist, album, label, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (artist, album, label, int(time.time())))
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
            time.sleep(2)
            return None
        except Exception as e:
            print(f"   ⚠️ Error en {self.base_url}: {e}")
            self.consecutive_errors += 1
            return None


class MusicBrainzClient(ApiClient):
    def __init__(self):
        super().__init__("https://musicbrainz.org/ws/2/", 1.1)  # Rate limit más estricto
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
    def __init__(self, token: str):
        super().__init__("https://api.discogs.com/", 1.0)
        self.token = token
        if token:
            self.session.headers.update({
                'Authorization': f'Discogs token={token}'
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
    def __init__(self):
        # Configuración
        self.discogs_token = os.getenv('DISCOGS_TOKEN', '')

        # Clientes API
        self.musicbrainz = MusicBrainzClient()
        self.discogs = DiscogsClient(self.discogs_token)

        # Base de datos
        self.db = MetadataDatabase()

    def enhance_artist_genres(self, artists: Set[str], source: str = 'both'):
        """Busca géneros de artistas en MusicBrainz y/o Discogs"""
        print(f"\n🎵 Buscando géneros de artistas en {source.upper()}...")

        processed = 0
        total = len(artists)

        for artist in artists:
            processed += 1
            if processed % 50 == 0:
                print(f"   📊 {processed}/{total} artistas procesados")

            try:
                if source in ['musicbrainz', 'both']:
                    self._search_artist_genres_musicbrainz(artist)

                if source in ['discogs', 'both']:
                    self._search_artist_genres_discogs(artist)

            except Exception as e:
                print(f"   ⚠️ Error procesando artista {artist}: {e}")
                continue

    def _search_artist_genres_musicbrainz(self, artist_name: str):
        """Busca géneros de artista en MusicBrainz"""
        search_result = self.musicbrainz.search_artist(artist_name)
        if not search_result or not search_result.get('artists'):
            return

        best_match = search_result['artists'][0]
        mbid = best_match['id']

        mb_data = self.musicbrainz.get_artist_by_mbid(mbid)
        if not mb_data:
            return

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
            self.db.save_artist_genres_detailed(artist_name, 'musicbrainz', mb_genres)

    def _search_artist_genres_discogs(self, artist_name: str):
        """Busca géneros de artista en Discogs"""
        if not self.discogs.token:
            return

        search_result = self.discogs.search_artist(artist_name)
        if not search_result or not search_result.get('results'):
            return

        for result in search_result['results'][:3]:  # Revisar top 3 resultados
            if 'id' in result:
                artist_details = self.discogs.get_artist_details(result['id'])
                if artist_details and 'genres' in artist_details:
                    discogs_genres = [
                        {'name': genre, 'weight': 1.0}
                        for genre in artist_details['genres']
                    ]
                    if discogs_genres:
                        self.db.save_artist_genres_detailed(artist_name, 'discogs', discogs_genres)
                        return  # Tomar el primer match válido

    def enhance_album_metadata(self, albums: Set[Tuple[str, str]], metadata_type: str = 'all'):
        """Busca metadatos de álbumes (fecha, sello, géneros)"""
        print(f"\n💿 Buscando metadatos de álbumes ({metadata_type})...")

        processed = 0
        total = len(albums)

        for artist, album in albums:
            processed += 1
            if processed % 25 == 0:
                print(f"   📊 {processed}/{total} álbumes procesados")

            try:
                if metadata_type in ['release_date', 'all']:
                    self._search_album_release_date(artist, album)

                if metadata_type in ['label', 'all']:
                    self._search_album_label(artist, album)

                if metadata_type in ['genres', 'all']:
                    self._search_album_genres(artist, album)

            except Exception as e:
                print(f"   ⚠️ Error procesando álbum {artist} - {album}: {e}")
                continue

    def _search_album_release_date(self, artist: str, album: str):
        """Busca fecha de lanzamiento en MusicBrainz y Discogs"""
        track_hint = self.db.get_scrobble_context_for_album(artist, album)

        # Intentar MusicBrainz primero
        search_result = self.musicbrainz.search_release(artist, album, track_hint)
        if search_result and search_result.get('releases'):
            release = search_result['releases'][0]
            if 'date' in release and release['date']:
                try:
                    release_year = int(release['date'][:4])
                    self.db.save_album_release_date(artist, album, release_year, release['date'])
                    return
                except (ValueError, TypeError):
                    pass

        # Fallback a Discogs
        if self.discogs.token:
            discogs_result = self.discogs.search_release(artist, album)
            if discogs_result and discogs_result.get('results'):
                for result in discogs_result['results'][:3]:
                    if result.get('year'):
                        try:
                            release_year = int(result.get('year'))
                            self.db.save_album_release_date(artist, album, release_year, str(release_year))
                            return
                        except (ValueError, TypeError):
                            continue

    def _search_album_label(self, artist: str, album: str):
        """Busca sello discográfico en MusicBrainz y Discogs"""
        track_hint = self.db.get_scrobble_context_for_album(artist, album)

        # Intentar MusicBrainz primero
        search_result = self.musicbrainz.search_release(artist, album, track_hint)
        if search_result and search_result.get('releases'):
            release = search_result['releases'][0]
            mbid = release['id']

            mb_data = self.musicbrainz.get_release_by_mbid(mbid)
            if mb_data and 'label-info' in mb_data and mb_data['label-info']:
                label = mb_data['label-info'][0]['label']['name']
                self.db.save_album_label(artist, album, label)
                return

        # Fallback a Discogs
        if self.discogs.token:
            discogs_result = self.discogs.search_release(artist, album)
            if discogs_result and discogs_result.get('results'):
                for result in discogs_result['results'][:3]:
                    if 'label' in result and result['label']:
                        label = result['label'][0] if isinstance(result['label'], list) else result['label']
                        self.db.save_album_label(artist, album, label)
                        return

    def _search_album_genres(self, artist: str, album: str):
        """Busca géneros de álbum en MusicBrainz y Discogs"""
        track_hint = self.db.get_scrobble_context_for_album(artist, album)

        # MusicBrainz
        search_result = self.musicbrainz.search_release(artist, album, track_hint)
        if search_result and search_result.get('releases'):
            release = search_result['releases'][0]
            mbid = release['id']

            mb_data = self.musicbrainz.get_release_by_mbid(mbid)
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
                    self.db.save_album_genres(artist, album, 'musicbrainz', mb_album_genres)

        # Discogs
        if self.discogs.token:
            discogs_result = self.discogs.search_release(artist, album)
            if discogs_result and discogs_result.get('results'):
                for result in discogs_result['results'][:3]:
                    if 'genre' in result and result['genre']:
                        discogs_genres = [
                            {'name': genre, 'weight': 1.0}
                            for genre in result['genre'][:10]
                        ]
                        if discogs_genres:
                            self.db.save_album_genres(artist, album, 'discogs', discogs_genres)
                            return

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

        # TRACKS
        print("\n🎵 TRACKS:")
        print(f"   • Total en scrobbles: {len(all_tracks_scrobbles)}")
        print(f"   • Total en track_details: {len(tracks_in_details)}")
        print(f"   • Sin detalles: {len(all_tracks_scrobbles) - len(tracks_in_details)} ({(len(all_tracks_scrobbles) - len(tracks_in_details))/len(all_tracks_scrobbles)*100:.1f}%)")

        print("\n" + "="*80)

    def run_enhancement(self, mode: str = 'all', limit: Optional[int] = None):
        """Ejecuta el proceso de mejora de metadatos"""
        print("🚀 INICIANDO MEJORA DE METADATOS")
        print("="*60)

        if mode in ['artists', 'all']:
            # Géneros de artistas
            artists_mb = self.db.get_artists_without_musicbrainz_genres()
            artists_discogs = self.db.get_artists_without_discogs_genres()

            if limit:
                artists_mb = set(list(artists_mb)[:limit])
                artists_discogs = set(list(artists_discogs)[:limit])

            if artists_mb:
                self.enhance_artist_genres(artists_mb, 'musicbrainz')
            if artists_discogs:
                self.enhance_artist_genres(artists_discogs, 'discogs')

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
                self.enhance_album_metadata(albums_dates, 'release_date')
            if albums_labels:
                self.enhance_album_metadata(albums_labels, 'label')
            if albums_genres:
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

    args = parser.parse_args()

    if not args.status and not args.enhance:
        print("❌ Debes especificar --status o --enhance")
        sys.exit(1)

    try:
        enhancer = MetadataEnhancer()

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

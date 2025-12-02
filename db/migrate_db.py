#!/usr/bin/env python3
"""
MIGRADOR ULTRA-OPTIMIZADO A BASE DE DATOS NORMALIZADA
====================================================

REDUCCIÓN AGRESIVA: 1.4GB → ~200-300MB (80-85% menos)

ESTRATEGIAS DE OPTIMIZACIÓN:
- Solo migra entidades con MBID válido (calidad > cantidad)
- Consolida metadatos directamente en tablas principales
- Busca MBIDs faltantes en MusicBrainz antes de migrar
- Limpia nombres (sin paréntesis, feat., etc.)
- Elimina todas las tablas de metadatos separadas

ANTES: 1.4GB con 9 usuarios, 61k artistas, 120k albums, 400k tracks
DESPUÉS: ~200-300MB con entidades de alta calidad con MBID
"""

import os
import sys
import sqlite3
import time
import shutil
import requests
import json
import re
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_API_KEY'):
        load_dotenv()
except ImportError:
    pass




class NameCleaner:
    """Utilidades para limpiar nombres de entidades y buscar MBIDs"""

    @staticmethod
    def clean_artist_name(name: str) -> str:
        """Limpia nombre de artista removiendo colaboraciones y extras"""
        if not name:
            return ""

        # Remover patrones comunes de colaboración
        patterns_to_remove = [
            r'\s*\(feat\.?\s+[^)]+\)',
            r'\s*\(featuring\s+[^)]+\)',
            r'\s*\(ft\.?\s+[^)]+\)',
            r'\s*\(with\s+[^)]+\)',
            r'\s*feat\.?\s+.*$',
            r'\s*featuring\s+.*$',
            r'\s*ft\.?\s+.*$',
            r'\s*with\s+.*$',
            r'\s*\([^)]*remix[^)]*\)',
            r'\s*\([^)]*mix[^)]*\)',
            r'\s*\([^)]*edit[^)]*\)',
            r'\s*\([^)]*version[^)]*\)',
        ]

        cleaned = name
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Limpiar espacios extra
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()

    @staticmethod
    def clean_track_name(name: str) -> str:
        """Limpia nombre de track removiendo versiones y extras"""
        if not name:
            return ""

        patterns_to_remove = [
            r'\s*\(feat\.?\s+[^)]+\)',
            r'\s*\(featuring\s+[^)]+\)',
            r'\s*\(ft\.?\s+[^)]+\)',
            r'\s*\([^)]*remix[^)]*\)',
            r'\s*\([^)]*mix[^)]*\)',
            r'\s*\([^)]*edit[^)]*\)',
            r'\s*\([^)]*radio[^)]*\)',
            r'\s*\([^)]*acoustic[^)]*\)',
            r'\s*\([^)]*live[^)]*\)',
            r'\s*\([^)]*instrumental[^)]*\)',
            r'\s*\([^)]*demo[^)]*\)',
            r'\s*\([^)]*remaster[^)]*\)',
            r'\s*\([^)]*version[^)]*\)',
        ]

        cleaned = name
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()

    @staticmethod
    def clean_album_name(name: str) -> str:
        """Limpia nombre de álbum removiendo ediciones especiales"""
        if not name:
            return ""

        patterns_to_remove = [
            r'\s*\([^)]*deluxe[^)]*\)',
            r'\s*\([^)]*expanded[^)]*\)',
            r'\s*\([^)]*special[^)]*\)',
            r'\s*\([^)]*anniversary[^)]*\)',
            r'\s*\([^)]*edition[^)]*\)',
            r'\s*\([^)]*remaster[^)]*\)',
            r'\s*\([^)]*bonus[^)]*\)',
            r'\s*\([^)]*collector[^)]*\)',
            r'\s*\([^)]*limited[^)]*\)',
            r'\s*\([^)]*mono[^)]*\)',
            r'\s*\([^)]*stereo[^)]*\)',
        ]

        cleaned = name
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()


class MusicBrainzLookup:
    """Cliente para buscar MBIDs faltantes en MusicBrainz"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LastFM-Normalizer/1.0 (contact@example.com)'
        })
        self.last_request = 0
        self.lock = threading.Lock()
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5  # Pausar después de 5 errores consecutivos

    def _rate_limit(self):
        """Rate limiting para MusicBrainz (1 request/second)"""
        with self.lock:
            elapsed = time.time() - self.last_request
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
            self.last_request = time.time()

    def search_artist_mbid(self, artist_name: str, max_retries: int = 2) -> Optional[str]:
        """Busca MBID de artista en MusicBrainz con manejo robusto de errores"""
        # Si hay muchos errores consecutivos, pausar búsquedas
        if self.consecutive_errors >= self.max_consecutive_errors:
            return None

        for attempt in range(max_retries + 1):
            try:
                self._rate_limit()

                cleaned_name = NameCleaner.clean_artist_name(artist_name)

                params = {
                    'query': f'artist:"{cleaned_name}"',
                    'fmt': 'json',
                    'limit': 1
                }

                response = self.session.get(
                    'https://musicbrainz.org/ws/2/artist/',
                    params=params,
                    timeout=15  # Timeout más largo
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('artists') and len(data['artists']) > 0:
                        self.consecutive_errors = 0  # Reset en éxito
                        return data['artists'][0]['id']
                elif response.status_code == 503:
                    # Servicio temporalmente no disponible
                    if attempt < max_retries:
                        wait_time = 2 ** attempt  # Backoff exponencial
                        print(f"      🔄 MusicBrainz sobrecargado, esperando {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                self.consecutive_errors = 0  # Reset si no hay error de conexión
                return None

            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                self.consecutive_errors += 1

                if self.consecutive_errors >= self.max_consecutive_errors:
                    print(f"      ⚠️ Demasiados errores de conexión a MusicBrainz ({self.consecutive_errors}). Pausando búsquedas...")
                    return None

                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Backoff exponencial: 1s, 2s, 4s
                    print(f"      🔄 Error conexión para {artist_name}, reintentando en {wait_time}s... (intento {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    # Fallo final, no mostrar error detallado
                    return None

            except requests.exceptions.RequestException:
                self.consecutive_errors += 1
                return None

            except Exception as e:
                self.consecutive_errors += 1
                print(f"      ⚠️ Error inesperado buscando MBID para {artist_name}: {type(e).__name__}")
                return None

        return None

    def search_release_mbid(self, artist_name: str, album_name: str, max_retries: int = 2) -> Optional[str]:
        """Busca MBID de release en MusicBrainz con manejo robusto de errores"""
        # Si hay muchos errores consecutivos, pausar búsquedas
        if self.consecutive_errors >= self.max_consecutive_errors:
            return None

        for attempt in range(max_retries + 1):
            try:
                self._rate_limit()

                cleaned_artist = NameCleaner.clean_artist_name(artist_name)
                cleaned_album = NameCleaner.clean_album_name(album_name)

                params = {
                    'query': f'release:"{cleaned_album}" AND artist:"{cleaned_artist}"',
                    'fmt': 'json',
                    'limit': 1
                }

                response = self.session.get(
                    'https://musicbrainz.org/ws/2/release/',
                    params=params,
                    timeout=15  # Timeout más largo
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('releases') and len(data['releases']) > 0:
                        self.consecutive_errors = 0  # Reset en éxito
                        return data['releases'][0]['id']
                elif response.status_code == 503:
                    # Servicio temporalmente no disponible
                    if attempt < max_retries:
                        wait_time = 2 ** attempt
                        print(f"      🔄 MusicBrainz sobrecargado para álbum, esperando {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                self.consecutive_errors = 0  # Reset si no hay error de conexión
                return None

            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                self.consecutive_errors += 1

                if self.consecutive_errors >= self.max_consecutive_errors:
                    print(f"      ⚠️ Demasiados errores de conexión a MusicBrainz. Pausando búsquedas de álbumes...")
                    return None

                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    print(f"      🔄 Error conexión para álbum {artist_name} - {album_name}, reintentando en {wait_time}s... (intento {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    return None

            except requests.exceptions.RequestException:
                self.consecutive_errors += 1
                return None

            except Exception as e:
                self.consecutive_errors += 1
                print(f"      ⚠️ Error inesperado buscando MBID para álbum {artist_name} - {album_name}: {type(e).__name__}")
                return None

        return None



    def search_recording_mbid(self, artist_name: str, track_name: str) -> Optional[str]:
        """Busca MBID de recording en MusicBrainz"""
        try:
            self._rate_limit()

            cleaned_artist = NameCleaner.clean_artist_name(artist_name)
            cleaned_track = NameCleaner.clean_track_name(track_name)

            params = {
                'query': f'recording:"{cleaned_track}" AND artist:"{cleaned_artist}"',
                'fmt': 'json',
                'limit': 1
            }

            response = self.session.get(
                'https://musicbrainz.org/ws/2/recording/',
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('recordings') and len(data['recordings']) > 0:
                    return data['recordings'][0]['id']

            return None

        except Exception as e:
            print(f"      ⚠️ Error buscando MBID para {artist_name} - {track_name}: {e}")
            return None


class UltraOptimizedNormalizer:
    def __init__(self, source_db: str = 'lastfm_cache.db', target_db: str = 'lastfm_normalized.db', mbid_only: bool = False):
        self.source_db = source_db
        self.target_db = target_db
        self.source_conn = None
        self.target_conn = None
        self.mbid_only = mbid_only

        # Cliente MusicBrainz para buscar MBIDs faltantes (solo si mbid_only=True)
        self.mb_lookup = MusicBrainzLookup() if mbid_only else None

        # Contadores para estadísticas
        self.stats = {
            'users_migrated': 0,
            'artists_migrated': 0,
            'albums_migrated': 0,
            'tracks_migrated': 0,
            'scrobbles_migrated': 0,
            'artists_with_mbid_from_source': 0,
            'artists_with_mbid_from_musicbrainz': 0,
            'albums_with_mbid_from_source': 0,
            'albums_with_mbid_from_musicbrainz': 0,
            'tracks_with_mbid_from_source': 0,
            'tracks_with_mbid_from_musicbrainz': 0,
            'artists_without_mbid_skipped': 0,
            'albums_without_mbid_skipped': 0,
            'tracks_without_mbid_skipped': 0
        }

    def connect_databases(self):
        """Conecta a ambas bases de datos"""
        if not os.path.exists(self.source_db):
            raise FileNotFoundError(f"Base de datos fuente no encontrada: {self.source_db}")

        print(f"📂 Conectando a base de datos fuente: {self.source_db}")
        self.source_conn = sqlite3.connect(self.source_db)
        self.source_conn.row_factory = sqlite3.Row

        # Crear backup de la base original
        backup_name = f"{self.source_db}.backup_{int(time.time())}"
        print(f"💾 Creando backup: {backup_name}")
        shutil.copy2(self.source_db, backup_name)

        print(f"📂 Creando base de datos normalizada: {self.target_db}")
        self.target_conn = sqlite3.connect(self.target_db)
        self.target_conn.row_factory = sqlite3.Row

    def create_ultra_optimized_schema(self):
        """Crea esquema ultra-optimizado con metadatos integrados"""
        print("🏗️ Creando esquema ultra-optimizado...")

        cursor = self.target_conn.cursor()

        # ==== TABLAS DE LOOKUP OPTIMIZADAS ====

        # Usuarios (sin cambios)
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')

        # Artistas CON metadatos integrados
        cursor.execute('''
            CREATE TABLE artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                mbid TEXT,

                -- Metadatos de Last.fm
                listeners INTEGER,
                playcount INTEGER,
                url TEXT,
                image_url TEXT,

                -- Géneros consolidados (JSON de todas las fuentes)
                genres_lastfm TEXT,     -- JSON array de tags de Last.fm
                genres_musicbrainz TEXT, -- JSON array de géneros de MusicBrainz

                -- Metadatos adicionales
                country TEXT,
                begin_date TEXT,
                end_date TEXT,

                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                last_updated INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')

        # Crear índice único para mbid solo cuando no es NULL
        cursor.execute('''
            CREATE UNIQUE INDEX idx_artists_mbid_unique
            ON artists(mbid) WHERE mbid IS NOT NULL
        ''')

        # Álbumes CON metadatos integrados
        cursor.execute('''
            CREATE TABLE albums (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                artist_id INTEGER NOT NULL,
                mbid TEXT,

                -- Metadatos integrados
                release_year INTEGER,
                release_date TEXT,
                release_group_mbid TEXT,
                album_type TEXT,
                status TEXT,
                country TEXT,
                barcode TEXT,
                total_tracks INTEGER,

                -- Sello discográfico
                label TEXT,

                -- Géneros consolidados
                genres_lastfm TEXT,     -- JSON array
                genres_musicbrainz TEXT, -- JSON array
                genres_discogs TEXT,    -- JSON array

                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                last_updated INTEGER DEFAULT (strftime('%s', 'now')),

                UNIQUE(name, artist_id),
                FOREIGN KEY (artist_id) REFERENCES artists(id)
            )
        ''')

        # Crear índice único para mbid solo cuando no es NULL
        cursor.execute('''
            CREATE UNIQUE INDEX idx_albums_mbid_unique
            ON albums(mbid) WHERE mbid IS NOT NULL
        ''')

        # Tracks CON metadatos integrados
        cursor.execute('''
            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                artist_id INTEGER NOT NULL,
                album_id INTEGER,
                mbid TEXT,

                -- Metadatos integrados
                duration_ms INTEGER,
                track_number INTEGER,
                isrc TEXT,

                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                last_updated INTEGER DEFAULT (strftime('%s', 'now')),

                UNIQUE(name, artist_id),
                FOREIGN KEY (artist_id) REFERENCES artists(id),
                FOREIGN KEY (album_id) REFERENCES albums(id)
            )
        ''')

        # Crear índice único para mbid solo cuando no es NULL
        cursor.execute('''
            CREATE UNIQUE INDEX idx_tracks_mbid_unique
            ON tracks(mbid) WHERE mbid IS NOT NULL
        ''')

        # ==== TABLA PRINCIPAL DE SCROBBLES (SIN CAMBIOS) ====
        cursor.execute('''
            CREATE TABLE scrobbles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                artist_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                album_id INTEGER,
                timestamp INTEGER NOT NULL,
                UNIQUE(user_id, timestamp, artist_id, track_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (artist_id) REFERENCES artists(id),
                FOREIGN KEY (track_id) REFERENCES tracks(id),
                FOREIGN KEY (album_id) REFERENCES albums(id)
            )
        ''')

        # ==== TABLAS DE PRIMERAS ESCUCHAS (SIMPLIFICADAS) ====

        cursor.execute('''
            CREATE TABLE user_first_artist_listen (
                user_id INTEGER NOT NULL,
                artist_id INTEGER NOT NULL,
                first_timestamp INTEGER,
                PRIMARY KEY (user_id, artist_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (artist_id) REFERENCES artists(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE user_first_album_listen (
                user_id INTEGER NOT NULL,
                album_id INTEGER NOT NULL,
                first_timestamp INTEGER,
                PRIMARY KEY (user_id, album_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (album_id) REFERENCES albums(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE user_first_track_listen (
                user_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                first_timestamp INTEGER,
                PRIMARY KEY (user_id, track_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (track_id) REFERENCES tracks(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE user_first_label_listen (
                user_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                first_timestamp INTEGER,
                PRIMARY KEY (user_id, label),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        self.target_conn.commit()
        print("✅ Esquema ultra-optimizado creado")

    def normalize_text(self, text: str) -> str:
        """Normaliza texto para búsquedas eficientes"""
        if not text:
            return ""
        return text.lower().strip()

    def migrate_entities(self):
        """Migra entidades según el modo seleccionado (con o sin filtro MBID)"""
        if self.mbid_only:
            print("\n📋 Modo MBID-ONLY: Solo migrando entidades con MBID válido...")
            self.migrate_entities_with_mbid_only()
        else:
            print("\n📋 Modo COMPLETO: Migrando todas las entidades...")
            self.migrate_entities_complete()

    def migrate_entities_complete(self):
        """Migra todas las entidades (modo original)"""
        print("📊 Migrando tablas de lookup completas...")

        source_cursor = self.source_conn.cursor()
        target_cursor = self.target_conn.cursor()

        # Mapas para tracking de IDs
        user_map = {}
        artist_map = {}
        album_map = {}
        track_map = {}

        # 1. USUARIOS (sin cambios)
        print("👥 Migrando usuarios...")
        source_cursor.execute('SELECT DISTINCT user FROM scrobbles ORDER BY user')
        users = [row['user'] for row in source_cursor.fetchall()]

        for username in users:
            target_cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
            user_id = target_cursor.lastrowid
            user_map[username] = user_id
            self.stats['users_migrated'] += 1

        print(f"  ✅ {len(users)} usuarios migrados")

        # 2. ARTISTAS (todos, con metadatos si están disponibles)
        print("🎤 Migrando artistas (todos)...")
        source_cursor.execute('SELECT DISTINCT artist FROM scrobbles WHERE artist IS NOT NULL ORDER BY artist')
        all_artists = [row['artist'] for row in source_cursor.fetchall()]

        print(f"  📊 Total artistas únicos: {len(all_artists):,}")

        # Obtener metadatos existentes (con verificación de MBIDs únicos)
        existing_metadata = {}
        mbid_to_artist_complete = {}  # Para detectar MBIDs duplicados en modo completo

        try:
            # Obtener géneros detallados de artistas por fuente
            source_cursor.execute('''
                SELECT agd.artist, agd.source, GROUP_CONCAT(agd.genre, '|') as genres
                FROM artist_genres_detailed agd
                GROUP BY agd.artist, agd.source
            ''')

            artist_detailed_genres = {}
            for row in source_cursor.fetchall():
                artist_name = row['artist']
                source_name = row['source']
                genres = row['genres'].split('|') if row['genres'] else []

                if artist_name not in artist_detailed_genres:
                    artist_detailed_genres[artist_name] = {}
                artist_detailed_genres[artist_name][source_name] = genres

            source_cursor.execute('''
                SELECT DISTINCT ad.artist, ad.mbid, ad.listeners, ad.playcount, ad.url,
                       ad.image_url, ad.country, ad.begin_date, ad.end_date,
                       ag.genres as lastfm_genres
                FROM artist_details ad
                LEFT JOIN artist_genres ag ON ad.artist = ag.artist
                ORDER BY ad.artist
            ''')

            for row in source_cursor.fetchall():
                artist_name = row['artist']
                mbid = row['mbid']

                # Si hay MBID, verificar que sea único
                if mbid and mbid.strip():
                    mbid = mbid.strip()
                    if mbid in mbid_to_artist_complete:
                        existing_artist = mbid_to_artist_complete[mbid]
                        print(f"  ⚠️ MBID duplicado {mbid}: '{existing_artist}' vs '{artist_name}' - usando sin MBID para '{artist_name}'")
                        mbid = None  # No usar MBID duplicado
                    else:
                        mbid_to_artist_complete[mbid] = artist_name
                else:
                    mbid = None

                # Obtener géneros de todas las fuentes
                detailed_genres = artist_detailed_genres.get(artist_name, {})

                existing_metadata[artist_name] = {
                    'mbid': mbid,
                    'listeners': row['listeners'],
                    'playcount': row['playcount'],
                    'url': row['url'],
                    'image_url': row['image_url'],
                    'country': row['country'],
                    'begin_date': row['begin_date'],
                    'end_date': row['end_date'],
                    'genres_lastfm': row['lastfm_genres'],
                    'genres_musicbrainz': json.dumps(detailed_genres.get('musicbrainz', [])) if detailed_genres.get('musicbrainz') else None
                }
        except sqlite3.OperationalError as e:
            print(f"  ⚠️ Error obteniendo metadatos de artistas: {e}")

        # Migrar todos los artistas (con MBIDs únicos)
        mbids_inserted_complete = set()  # Track de MBIDs ya insertados
        for artist_name in all_artists:
            cleaned_name = NameCleaner.clean_artist_name(artist_name)
            metadata = existing_metadata.get(artist_name, {})
            mbid = metadata.get('mbid')

            # Verificar si ya insertamos este MBID (solo si no es None)
            if mbid and mbid in mbids_inserted_complete:
                print(f"  ⚠️ MBID {mbid} ya insertado, insertando '{artist_name}' sin MBID")
                mbid = None

            try:
                target_cursor.execute('''
                    INSERT INTO artists (
                        name, mbid, listeners, playcount, url, image_url,
                        country, begin_date, end_date, genres_lastfm, genres_musicbrainz
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cleaned_name,
                    mbid,
                    metadata.get('listeners'),
                    metadata.get('playcount'),
                    metadata.get('url'),
                    metadata.get('image_url'),
                    metadata.get('country'),
                    metadata.get('begin_date'),
                    metadata.get('end_date'),
                    metadata.get('genres_lastfm'),
                    metadata.get('genres_musicbrainz')
                ))

                artist_id = target_cursor.lastrowid
                artist_map[artist_name] = artist_id
                if mbid:
                    mbids_inserted_complete.add(mbid)
                self.stats['artists_migrated'] += 1

            except sqlite3.IntegrityError as e:
                if 'mbid' in str(e):
                    # MBID ya existe en destino, intentar sin MBID
                    try:
                        target_cursor.execute('''
                            INSERT INTO artists (
                                name, listeners, playcount, url, image_url,
                                country, begin_date, end_date, genres_lastfm, genres_musicbrainz
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            cleaned_name,
                            metadata.get('listeners'),
                            metadata.get('playcount'),
                            metadata.get('url'),
                            metadata.get('image_url'),
                            metadata.get('country'),
                            metadata.get('begin_date'),
                            metadata.get('end_date'),
                            metadata.get('genres_lastfm'),
                            metadata.get('genres_musicbrainz')
                        ))

                        artist_id = target_cursor.lastrowid
                        artist_map[artist_name] = artist_id
                        self.stats['artists_migrated'] += 1
                        print(f"  ⚠️ MBID {mbid} ya existe en destino, insertado '{artist_name}' sin MBID")

                    except sqlite3.IntegrityError as e2:
                        if 'name' in str(e2):
                            # Nombre duplicado, obtener ID existente
                            target_cursor.execute('SELECT id, mbid FROM artists WHERE name = ?', (cleaned_name,))
                            result = target_cursor.fetchone()
                            if result:
                                artist_id = result['id']
                                existing_mbid = result['mbid']
                                artist_map[artist_name] = artist_id
                                print(f"  ℹ️ Nombre limpio '{cleaned_name}' ya existe (MBID: {existing_mbid}), usando ID existente para: {artist_name}")
                        else:
                            print(f"  ❌ Error insertando artista {artist_name}: {e2}")
                            continue

                elif 'name' in str(e):
                    # Nombre duplicado, obtener ID existente
                    target_cursor.execute('SELECT id, mbid FROM artists WHERE name = ?', (cleaned_name,))
                    result = target_cursor.fetchone()
                    if result:
                        artist_id = result['id']
                        existing_mbid = result['mbid']
                        artist_map[artist_name] = artist_id
                        print(f"  ℹ️ Nombre limpio '{cleaned_name}' ya existe (MBID: {existing_mbid}), usando ID existente para: {artist_name}")
                else:
                    print(f"  ❌ Error insertando artista {artist_name}: {e}")
                    continue

        print(f"  ✅ {len(all_artists):,} artistas migrados")

        # 3. ÁLBUMES (todos)
        print("💿 Migrando álbumes (todos)...")
        source_cursor.execute('''
            SELECT DISTINCT artist, album FROM scrobbles
            WHERE album IS NOT NULL AND album != ""
            ORDER BY artist, album
        ''')
        all_albums = source_cursor.fetchall()

        # Obtener metadatos de álbumes
        album_metadata = {}
        try:
            # Obtener géneros de álbumes por fuente
            source_cursor.execute('''
                SELECT ag.artist, ag.album, ag.source, GROUP_CONCAT(ag.genre, '|') as genres
                FROM album_genres ag
                GROUP BY ag.artist, ag.album, ag.source
            ''')

            album_genres_by_source_complete = {}
            for row in source_cursor.fetchall():
                album_key = (row['artist'], row['album'])
                source_name = row['source']
                genres = row['genres'].split('|') if row['genres'] else []

                if album_key not in album_genres_by_source_complete:
                    album_genres_by_source_complete[album_key] = {}
                album_genres_by_source_complete[album_key][source_name] = genres

            source_cursor.execute('''
                SELECT DISTINCT ad.artist, ad.album, ad.mbid, ad.release_group_mbid,
                       ad.original_release_date, ad.album_type, ad.status, ad.country,
                       ad.barcode, ad.total_tracks,
                       ard.release_year, ard.release_date,
                       al.label
                FROM album_details ad
                LEFT JOIN album_release_dates ard ON ad.artist = ard.artist AND ad.album = ard.album
                LEFT JOIN album_labels al ON ad.artist = al.artist AND ad.album = al.album
            ''')

            for row in source_cursor.fetchall():
                key = (row['artist'], row['album'])
                album_genres = album_genres_by_source_complete.get(key, {})

                album_metadata[key] = {
                    'mbid': row['mbid'],
                    'release_group_mbid': row['release_group_mbid'],
                    'original_release_date': row['original_release_date'],
                    'release_year': row['release_year'],
                    'release_date': row['release_date'],
                    'album_type': row['album_type'],
                    'status': row['status'],
                    'country': row['country'],
                    'barcode': row['barcode'],
                    'total_tracks': row['total_tracks'],
                    'label': row['label'],
                    'genres_lastfm': json.dumps(album_genres.get('lastfm', [])) if album_genres.get('lastfm') else None,
                    'genres_musicbrainz': json.dumps(album_genres.get('musicbrainz', [])) if album_genres.get('musicbrainz') else None,
                    'genres_discogs': json.dumps(album_genres.get('discogs', [])) if album_genres.get('discogs') else None
                }
        except sqlite3.OperationalError:
            print("  ⚠️ Tablas de metadatos de álbumes no encontradas")

        for row in all_albums:
            artist_name = row['artist']
            album_name = row['album']
            artist_id = artist_map.get(artist_name)

            if artist_id:
                cleaned_album_name = NameCleaner.clean_album_name(album_name)
                metadata = album_metadata.get((artist_name, album_name), {})

                try:
                    target_cursor.execute('''
                        INSERT OR IGNORE INTO albums (
                            name, artist_id, mbid, release_year, release_date, release_group_mbid,
                            album_type, status, country, barcode, total_tracks, label,
                            genres_lastfm, genres_musicbrainz, genres_discogs
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        cleaned_album_name, artist_id,
                        metadata.get('mbid'), metadata.get('release_year'),
                        metadata.get('release_date'), metadata.get('release_group_mbid'),
                        metadata.get('album_type'), metadata.get('status'),
                        metadata.get('country'), metadata.get('barcode'),
                        metadata.get('total_tracks'), metadata.get('label'),
                        metadata.get('genres_lastfm'), metadata.get('genres_musicbrainz'),
                        metadata.get('genres_discogs')
                    ))

                    # Obtener ID del álbum (puede ser nuevo o existente por OR IGNORE)
                    target_cursor.execute('''
                        SELECT id FROM albums WHERE name = ? AND artist_id = ?
                    ''', (cleaned_album_name, artist_id))
                    album_result = target_cursor.fetchone()
                    if album_result:
                        album_id = album_result['id']
                        album_map[(artist_name, album_name)] = album_id
                        self.stats['albums_migrated'] += 1

                except sqlite3.IntegrityError as e:
                    if 'mbid' in str(e):
                        # MBID duplicado, intentar sin MBID
                        try:
                            target_cursor.execute('''
                                INSERT OR IGNORE INTO albums (
                                    name, artist_id, release_year, release_date, release_group_mbid,
                                    album_type, status, country, barcode, total_tracks, label,
                                    genres_lastfm, genres_musicbrainz, genres_discogs
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                cleaned_album_name, artist_id,
                                metadata.get('release_year'),
                                metadata.get('release_date'), metadata.get('release_group_mbid'),
                                metadata.get('album_type'), metadata.get('status'),
                                metadata.get('country'), metadata.get('barcode'),
                                metadata.get('total_tracks'), metadata.get('label'),
                                metadata.get('genres_lastfm'), metadata.get('genres_musicbrainz'),
                                metadata.get('genres_discogs')
                            ))

                            target_cursor.execute('''
                                SELECT id FROM albums WHERE name = ? AND artist_id = ?
                            ''', (cleaned_album_name, artist_id))
                            album_result = target_cursor.fetchone()
                            if album_result:
                                album_id = album_result['id']
                                album_map[(artist_name, album_name)] = album_id
                                self.stats['albums_migrated'] += 1
                                print(f"  ⚠️ MBID duplicado para álbum {album_name}, insertado sin MBID")

                        except sqlite3.IntegrityError as e2:
                            print(f"  ❌ Error insertando álbum {album_name}: {e2}")
                            continue
                    else:
                        print(f"  ❌ Error insertando álbum {album_name}: {e}")
                        continue

        print(f"  ✅ {len(all_albums):,} álbumes procesados")

        # 4. TRACKS (todos)
        print("🎵 Migrando tracks (todos)...")
        source_cursor.execute('''
            SELECT DISTINCT artist, track, album FROM scrobbles
            WHERE track IS NOT NULL
            ORDER BY artist, track
        ''')
        all_tracks = source_cursor.fetchall()

        # Obtener metadatos de tracks
        track_metadata = {}
        try:
            source_cursor.execute('''
                SELECT DISTINCT td.artist, td.track, td.mbid, td.duration_ms,
                       td.track_number, td.isrc
                FROM track_details td
            ''')

            for row in source_cursor.fetchall():
                key = (row['artist'], row['track'])
                track_metadata[key] = {
                    'mbid': row['mbid'],
                    'duration_ms': row['duration_ms'],
                    'track_number': row['track_number'],
                    'isrc': row['isrc']
                }
        except sqlite3.OperationalError:
            print("  ⚠️ Tabla track_details no encontrada")

        for row in all_tracks:
            artist_name = row['artist']
            track_name = row['track']
            album_name = row['album'] if row['album'] else None

            artist_id = artist_map.get(artist_name)
            album_id = album_map.get((artist_name, album_name)) if album_name else None

            if artist_id:
                cleaned_track_name = NameCleaner.clean_track_name(track_name)
                metadata = track_metadata.get((artist_name, track_name), {})

                try:
                    target_cursor.execute('''
                        INSERT OR IGNORE INTO tracks (
                            name, artist_id, album_id, mbid, duration_ms, track_number, isrc
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        cleaned_track_name, artist_id, album_id,
                        metadata.get('mbid'), metadata.get('duration_ms'),
                        metadata.get('track_number'), metadata.get('isrc')
                    ))

                    # Obtener ID del track
                    target_cursor.execute('''
                        SELECT id FROM tracks WHERE name = ? AND artist_id = ?
                    ''', (cleaned_track_name, artist_id))
                    track_result = target_cursor.fetchone()
                    if track_result:
                        track_id = track_result['id']
                        track_map[(artist_name, track_name)] = track_id
                        self.stats['tracks_migrated'] += 1

                except sqlite3.IntegrityError as e:
                    if 'mbid' in str(e):
                        # MBID duplicado, intentar sin MBID
                        try:
                            target_cursor.execute('''
                                INSERT OR IGNORE INTO tracks (
                                    name, artist_id, album_id, duration_ms, track_number, isrc
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                cleaned_track_name, artist_id, album_id,
                                metadata.get('duration_ms'),
                                metadata.get('track_number'), metadata.get('isrc')
                            ))

                            target_cursor.execute('''
                                SELECT id FROM tracks WHERE name = ? AND artist_id = ?
                            ''', (cleaned_track_name, artist_id))
                            track_result = target_cursor.fetchone()
                            if track_result:
                                track_id = track_result['id']
                                track_map[(artist_name, track_name)] = track_id
                                self.stats['tracks_migrated'] += 1
                                print(f"  ⚠️ MBID duplicado para track {track_name}, insertado sin MBID")

                        except sqlite3.IntegrityError as e2:
                            print(f"  ❌ Error insertando track {track_name}: {e2}")
                            continue
                    else:
                        print(f"  ❌ Error insertando track {track_name}: {e}")
                        continue

        print(f"  ✅ {len(all_tracks):,} tracks procesados")

        self.target_conn.commit()

        # Guardar mapas para uso posterior
        self.user_map = user_map
        self.artist_map = artist_map
        self.album_map = album_map
        self.track_map = track_map
    def migrate_entities_with_mbid_only(self):
        """Migra solo entidades que tienen MBID válido, buscando MBIDs faltantes"""
        print("\n📋 Migrando solo entidades con MBID válido...")

        source_cursor = self.source_conn.cursor()
        target_cursor = self.target_conn.cursor()

        # Mapas para tracking de IDs
        user_map = {}
        artist_map = {}
        album_map = {}
        track_map = {}

        # 1. USUARIOS (sin cambios - todos se migran)
        print("👥 Migrando usuarios...")
        source_cursor.execute('SELECT DISTINCT user FROM scrobbles ORDER BY user')
        users = [row['user'] for row in source_cursor.fetchall()]

        for username in users:
            target_cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
            user_id = target_cursor.lastrowid
            user_map[username] = user_id
            self.stats['users_migrated'] += 1

        print(f"  ✅ {len(users)} usuarios migrados")

        # 2. ARTISTAS - Solo los que tienen MBID
        print("🎤 Migrando artistas (solo con MBID)...")

        # Obtener artistas únicos de scrobbles
        source_cursor.execute('SELECT DISTINCT artist FROM scrobbles WHERE artist IS NOT NULL ORDER BY artist')
        all_artists = [row['artist'] for row in source_cursor.fetchall()]

        print(f"  📊 Total artistas únicos en scrobbles: {len(all_artists):,}")

        # Buscar artistas que ya tienen MBID en artist_details
        artists_with_existing_mbid = {}
        try:
            source_cursor.execute('''
                SELECT DISTINCT ad.artist, ad.mbid, ad.listeners, ad.playcount, ad.url,
                       ad.image_url, ad.country, ad.begin_date, ad.end_date,
                       ag.genres as lastfm_genres
                FROM artist_details ad
                LEFT JOIN artist_genres ag ON ad.artist = ag.artist
                WHERE ad.mbid IS NOT NULL AND ad.mbid != "" AND TRIM(ad.mbid) != ""
                ORDER BY ad.artist
            ''')

            # Obtener géneros detallados de artistas por fuente
            source_cursor.execute('''
                SELECT agd.artist, agd.source, GROUP_CONCAT(agd.genre, '|') as genres
                FROM artist_genres_detailed agd
                GROUP BY agd.artist, agd.source
            ''')

            artist_detailed_genres = {}
            for row in source_cursor.fetchall():
                artist_name = row['artist']
                source_name = row['source']
                genres = row['genres'].split('|') if row['genres'] else []

                if artist_name not in artist_detailed_genres:
                    artist_detailed_genres[artist_name] = {}
                artist_detailed_genres[artist_name][source_name] = genres

            mbid_to_artist = {}  # Para detectar MBIDs duplicados

            # Volver a ejecutar la consulta principal para procesar los datos
            source_cursor.execute('''
                SELECT DISTINCT ad.artist, ad.mbid, ad.listeners, ad.playcount, ad.url,
                       ad.image_url, ad.country, ad.begin_date, ad.end_date,
                       ag.genres as lastfm_genres
                FROM artist_details ad
                LEFT JOIN artist_genres ag ON ad.artist = ag.artist
                WHERE ad.mbid IS NOT NULL AND ad.mbid != "" AND TRIM(ad.mbid) != ""
                ORDER BY ad.artist
            ''')

            for row in source_cursor.fetchall():
                artist_name = row['artist']
                mbid = row['mbid'].strip()

                # Verificar si este MBID ya está asignado a otro artista
                if mbid in mbid_to_artist:
                    existing_artist = mbid_to_artist[mbid]
                    print(f"  ⚠️ MBID duplicado {mbid}: '{existing_artist}' vs '{artist_name}' - saltando '{artist_name}'")
                    continue

                # Solo incluir si el artista está en scrobbles
                if artist_name in all_artists:
                    cleaned_name = NameCleaner.clean_artist_name(artist_name)

                    # Obtener géneros de todas las fuentes
                    detailed_genres = artist_detailed_genres.get(artist_name, {})

                    artists_with_existing_mbid[artist_name] = {
                        'mbid': mbid,
                        'listeners': row['listeners'],
                        'playcount': row['playcount'],
                        'url': row['url'],
                        'image_url': row['image_url'],
                        'country': row['country'],
                        'begin_date': row['begin_date'],
                        'end_date': row['end_date'],
                        'genres_lastfm': row['lastfm_genres'],
                        'genres_musicbrainz': json.dumps(detailed_genres.get('musicbrainz', [])) if detailed_genres.get('musicbrainz') else None,
                        'genres_discogs': json.dumps(detailed_genres.get('discogs', [])) if detailed_genres.get('discogs') else None
                    }

                    mbid_to_artist[mbid] = artist_name
                    self.stats['artists_with_mbid_from_source'] += 1

            print(f"  ✅ Artistas únicos con MBID en source: {len(artists_with_existing_mbid):,}")

        except sqlite3.OperationalError as e:
            print(f"  ⚠️ Error obteniendo datos de artistas: {e}")

        # Buscar MBIDs faltantes en MusicBrainz para artistas importantes
        artists_needing_mbid = set(all_artists) - set(artists_with_existing_mbid.keys())

        # Solo buscar MBIDs para artistas con muchos scrobbles (optimización)
        if artists_needing_mbid:
            print(f"  🔍 Buscando MBIDs faltantes para {len(artists_needing_mbid):,} artistas...")

            # Obtener artistas por popularidad (número de scrobbles)
            placeholders = ','.join(['?' for _ in artists_needing_mbid])
            source_cursor.execute(f'''
                SELECT artist, COUNT(*) as scrobble_count
                FROM scrobbles
                WHERE artist IN ({placeholders})
                GROUP BY artist
                ORDER BY scrobble_count DESC
            ''', list(artists_needing_mbid))

            popular_artists = source_cursor.fetchall()

            # Obtener MBIDs ya usados para evitar duplicados
            existing_mbids = set(metadata['mbid'] for metadata in artists_with_existing_mbid.values())

            # Buscar MBIDs solo para los top N artistas más populares
            max_musicbrainz_lookups = 200  # Reducido para ser más conservador con problemas SSL

            for i, row in enumerate(popular_artists[:max_musicbrainz_lookups]):
                artist_name = row['artist']
                scrobble_count = row['scrobble_count']

                if (i + 1) % 50 == 0:
                    print(f"    🔍 Progreso: {i + 1}/{min(len(popular_artists), max_musicbrainz_lookups)} ({scrobble_count} scrobbles)")

                cleaned_name = NameCleaner.clean_artist_name(artist_name)
                mbid = self.mb_lookup.search_artist_mbid(cleaned_name)

                if mbid:
                    # Verificar que este MBID no esté ya usado
                    if mbid in existing_mbids:
                        print(f"    ℹ️ MBID {mbid} ya existe, relacionando {artist_name} con artista existente")
                        # Buscar el ID del artista existente con este MBID
                        target_cursor.execute('SELECT id, name FROM artists WHERE mbid = ?', (mbid,))
                        existing_result = target_cursor.fetchone()
                        if existing_result:
                            existing_artist_id = existing_result['id']
                            existing_name = existing_result['name']
                            artist_map[artist_name] = existing_artist_id
                            print(f"    ✅ {artist_name} → relacionado con '{existing_name}' (ID: {existing_artist_id})")
                            self.stats['artists_migrated'] += 1  # Contar como migrado (relacionado)
                        continue

                    artists_with_existing_mbid[artist_name] = {
                        'mbid': mbid,
                        'listeners': None,
                        'playcount': None,
                        'url': None,
                        'image_url': None,
                        'country': None,
                        'begin_date': None,
                        'end_date': None,
                        'genres_lastfm': None,
                        'genres_musicbrainz': None
                    }
                    existing_mbids.add(mbid)  # Añadir a la lista de MBIDs usados
                    self.stats['artists_with_mbid_from_musicbrainz'] += 1
                else:
                    self.stats['artists_without_mbid_skipped'] += 1

        # Migrar artistas con MBID (rechazar duplicados completamente)
        mbids_inserted = set()  # Track de MBIDs ya insertados

        for artist_name, metadata in artists_with_existing_mbid.items():
            cleaned_name = NameCleaner.clean_artist_name(artist_name)
            mbid = metadata['mbid']

            # Verificar si ya insertamos este MBID
            if mbid in mbids_inserted:
                print(f"  ⚠️ MBID {mbid} duplicado, saltando artista: {artist_name}")
                continue

            try:
                target_cursor.execute('''
                    INSERT INTO artists (
                        name, mbid, listeners, playcount, url, image_url,
                        country, begin_date, end_date, genres_lastfm, genres_musicbrainz
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cleaned_name, mbid, metadata['listeners'], metadata['playcount'],
                    metadata['url'], metadata['image_url'], metadata['country'],
                    metadata['begin_date'], metadata['end_date'], metadata['genres_lastfm'],
                    metadata['genres_musicbrainz']
                ))

                artist_id = target_cursor.lastrowid
                artist_map[artist_name] = artist_id
                mbids_inserted.add(mbid)
                self.stats['artists_migrated'] += 1

            except sqlite3.IntegrityError as e:
                if 'mbid' in str(e):
                    # MBID ya existe, buscar el artista existente y relacionarlo
                    target_cursor.execute('SELECT id, name FROM artists WHERE mbid = ?', (mbid,))
                    existing_result = target_cursor.fetchone()
                    if existing_result:
                        existing_artist_id = existing_result['id']
                        existing_name = existing_result['name']
                        artist_map[artist_name] = existing_artist_id
                        print(f"  ℹ️ MBID {mbid} ya existe, relacionando '{artist_name}' con '{existing_name}' (ID: {existing_artist_id})")
                        self.stats['artists_migrated'] += 1  # Contar como relacionado
                    continue
                elif 'name' in str(e):
                    # Nombre duplicado después de limpieza, obtener ID existente
                    target_cursor.execute('SELECT id, mbid FROM artists WHERE name = ?', (cleaned_name,))
                    result = target_cursor.fetchone()
                    if result:
                        artist_id = result['id']
                        existing_mbid = result['mbid']
                        artist_map[artist_name] = artist_id
                        print(f"  ℹ️ Nombre limpio '{cleaned_name}' ya existe (MBID: {existing_mbid}), relacionando '{artist_name}' (ID: {artist_id})")
                        self.stats['artists_migrated'] += 1  # Contar como relacionado
                else:
                    print(f"  ❌ Error insertando artista {artist_name}: {e}")
                    continue

        total_artists_with_mbid = len(artists_with_existing_mbid)
        total_artists_skipped = len(all_artists) - total_artists_with_mbid

        print(f"  ✅ Artistas con MBID migrados: {total_artists_with_mbid:,}")
        print(f"  ⚠️ Artistas sin MBID saltados: {total_artists_skipped:,}")
        print(f"  📈 % de artistas retenidos: {(total_artists_with_mbid/len(all_artists))*100:.1f}%")

        # 3. ÁLBUMES - Solo los de artistas con MBID
        print("💿 Migrando álbumes (solo de artistas con MBID)...")

        # Obtener álbumes de artistas que sí fueron migrados
        migrated_artist_names = set(artist_map.keys())
        placeholders = ','.join(['?' for _ in migrated_artist_names])

        source_cursor.execute(f'''
            SELECT DISTINCT artist, album FROM scrobbles
            WHERE album IS NOT NULL AND album != "" AND artist IN ({placeholders})
            ORDER BY artist, album
        ''', list(migrated_artist_names))

        potential_albums = source_cursor.fetchall()
        print(f"  📊 Álbumes potenciales (de artistas con MBID): {len(potential_albums):,}")

        # Buscar álbumes que ya tienen MBID
        albums_with_existing_mbid = {}
        try:
            source_cursor.execute('''
                SELECT DISTINCT ad.artist, ad.album, ad.mbid, ad.release_group_mbid,
                       ad.original_release_date, ad.album_type, ad.status, ad.country,
                       ad.barcode, ad.total_tracks,
                       ard.release_year, ard.release_date,
                       al.label
                FROM album_details ad
                LEFT JOIN album_release_dates ard ON ad.artist = ard.artist AND ad.album = ard.album
                LEFT JOIN album_labels al ON ad.artist = al.artist AND ad.album = al.album
                WHERE ad.mbid IS NOT NULL AND ad.mbid != "" AND TRIM(ad.mbid) != ""
                ORDER BY ad.artist, ad.album
            ''')

            # Obtener géneros de álbumes por fuente
            source_cursor.execute('''
                SELECT ag.artist, ag.album, ag.source, GROUP_CONCAT(ag.genre, '|') as genres
                FROM album_genres ag
                GROUP BY ag.artist, ag.album, ag.source
            ''')

            album_genres_by_source = {}
            for row in source_cursor.fetchall():
                album_key = (row['artist'], row['album'])
                source_name = row['source']
                genres = row['genres'].split('|') if row['genres'] else []

                if album_key not in album_genres_by_source:
                    album_genres_by_source[album_key] = {}
                album_genres_by_source[album_key][source_name] = genres

            mbid_to_album = {}  # Para detectar MBIDs duplicados

            # Volver a ejecutar la consulta principal
            source_cursor.execute('''
                SELECT DISTINCT ad.artist, ad.album, ad.mbid, ad.release_group_mbid,
                       ad.original_release_date, ad.album_type, ad.status, ad.country,
                       ad.barcode, ad.total_tracks,
                       ard.release_year, ard.release_date,
                       al.label
                FROM album_details ad
                LEFT JOIN album_release_dates ard ON ad.artist = ard.artist AND ad.album = ard.album
                LEFT JOIN album_labels al ON ad.artist = al.artist AND ad.album = al.album
                WHERE ad.mbid IS NOT NULL AND ad.mbid != "" AND TRIM(ad.mbid) != ""
                ORDER BY ad.artist, ad.album
            ''')

            for row in source_cursor.fetchall():
                artist_name = row['artist']
                album_name = row['album']
                mbid = row['mbid'].strip()

                # Solo procesar si el artista fue migrado
                if artist_name not in migrated_artist_names:
                    continue

                # Verificar si este MBID ya está asignado a otro álbum
                if mbid in mbid_to_album:
                    existing_album = mbid_to_album[mbid]
                    print(f"  ⚠️ MBID de álbum duplicado {mbid}: '{existing_album}' vs '{artist_name} - {album_name}' - saltando")
                    continue

                cleaned_album_name = NameCleaner.clean_album_name(album_name)

                # Obtener géneros de todas las fuentes para este álbum
                album_key = (artist_name, album_name)
                album_genres = album_genres_by_source.get(album_key, {})

                albums_with_existing_mbid[(artist_name, album_name)] = {
                    'mbid': mbid,
                    'release_group_mbid': row['release_group_mbid'],
                    'original_release_date': row['original_release_date'],
                    'release_year': row['release_year'],
                    'release_date': row['release_date'],
                    'album_type': row['album_type'],
                    'status': row['status'],
                    'country': row['country'],
                    'barcode': row['barcode'],
                    'total_tracks': row['total_tracks'],
                    'label': row['label'],
                    'genres_lastfm': json.dumps(album_genres.get('lastfm', [])) if album_genres.get('lastfm') else None,
                    'genres_musicbrainz': json.dumps(album_genres.get('musicbrainz', [])) if album_genres.get('musicbrainz') else None,
                    'genres_discogs': json.dumps(album_genres.get('discogs', [])) if album_genres.get('discogs') else None
                }

                mbid_to_album[mbid] = f"{artist_name} - {album_name}"
                self.stats['albums_with_mbid_from_source'] += 1

            print(f"  ✅ Álbumes únicos con MBID en source: {len(albums_with_existing_mbid):,}")

        except sqlite3.OperationalError as e:
            print(f"  ⚠️ Error obteniendo datos de álbumes: {e}")

        # Buscar MBIDs faltantes para álbumes importantes
        albums_needing_mbid = []
        for row in potential_albums:
            artist_name = row['artist']
            album_name = row['album']
            if (artist_name, album_name) not in albums_with_existing_mbid:
                albums_needing_mbid.append((artist_name, album_name))

        # Obtener MBIDs ya usados para evitar duplicados
        existing_album_mbids = set(metadata['mbid'] for metadata in albums_with_existing_mbid.values())

        if albums_needing_mbid:
            print(f"  🔍 Buscando MBIDs faltantes para {len(albums_needing_mbid):,} álbumes...")

            # Limitar búsquedas de MusicBrainz para álbumes
            max_album_lookups = 100  # Muy limitado por problemas de conectividad

            for i, (artist_name, album_name) in enumerate(albums_needing_mbid[:max_album_lookups]):
                if (i + 1) % 25 == 0:
                    print(f"    🔍 Progreso: {i + 1}/{min(len(albums_needing_mbid), max_album_lookups)}")

                mbid = self.mb_lookup.search_release_mbid(artist_name, album_name)

                if mbid and mbid not in existing_album_mbids:
                    cleaned_album_name = NameCleaner.clean_album_name(album_name)
                    albums_with_existing_mbid[(artist_name, album_name)] = {
                        'mbid': mbid,
                        'release_group_mbid': None,
                        'original_release_date': None,
                        'release_year': None,
                        'release_date': None,
                        'album_type': None,
                        'status': None,
                        'country': None,
                        'barcode': None,
                        'total_tracks': None,
                        'label': None,
                        'genres_lastfm': None,
                        'genres_musicbrainz': None,
                        'genres_discogs': None
                    }
                    existing_album_mbids.add(mbid)
                    self.stats['albums_with_mbid_from_musicbrainz'] += 1
                elif mbid:
                    print(f"    ℹ️ MBID de álbum {mbid} ya existe, relacionando {artist_name} - {album_name} con álbum existente")
                    # Buscar el álbum existente con este MBID
                    target_cursor.execute('SELECT id, name, artist_id FROM albums WHERE mbid = ?', (mbid,))
                    existing_result = target_cursor.fetchone()
                    if existing_result:
                        existing_album_id = existing_result['id']
                        existing_name = existing_result['name']
                        album_map[(artist_name, album_name)] = existing_album_id
                        print(f"    ✅ {artist_name} - {album_name} → relacionado con álbum existente '{existing_name}' (ID: {existing_album_id})")
                        self.stats['albums_migrated'] += 1
                    self.stats['albums_without_mbid_skipped'] += 1
                else:
                    self.stats['albums_without_mbid_skipped'] += 1

        # Migrar álbumes con MBID (rechazar duplicados completamente)
        album_mbids_inserted = set()  # Track de MBIDs ya insertados

        for (artist_name, album_name), metadata in albums_with_existing_mbid.items():
            artist_id = artist_map.get(artist_name)
            if not artist_id:
                continue

            cleaned_album_name = NameCleaner.clean_album_name(album_name)
            mbid = metadata['mbid']

            # Verificar si ya insertamos este MBID
            if mbid in album_mbids_inserted:
                print(f"  ℹ️ MBID de álbum {mbid} ya procesado, relacionando: {artist_name} - {album_name}")
                # Buscar el álbum existente
                target_cursor.execute('SELECT id, name FROM albums WHERE mbid = ?', (mbid,))
                existing_result = target_cursor.fetchone()
                if existing_result:
                    existing_album_id = existing_result['id']
                    existing_name = existing_result['name']
                    album_map[(artist_name, album_name)] = existing_album_id
                    print(f"  ✅ Relacionado con álbum existente '{existing_name}' (ID: {existing_album_id})")
                    self.stats['albums_migrated'] += 1
                continue

            try:
                target_cursor.execute('''
                    INSERT INTO albums (
                        name, artist_id, mbid, release_year, release_date, release_group_mbid,
                        album_type, status, country, barcode, total_tracks, label,
                        genres_lastfm, genres_musicbrainz, genres_discogs
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cleaned_album_name, artist_id, mbid, metadata['release_year'],
                    metadata['release_date'], metadata['release_group_mbid'], metadata['album_type'],
                    metadata['status'], metadata['country'], metadata['barcode'],
                    metadata['total_tracks'], metadata['label'], metadata['genres_lastfm'],
                    metadata['genres_musicbrainz'], metadata['genres_discogs']
                ))

                album_id = target_cursor.lastrowid
                album_map[(artist_name, album_name)] = album_id
                album_mbids_inserted.add(mbid)
                self.stats['albums_migrated'] += 1

            except sqlite3.IntegrityError as e:
                if 'mbid' in str(e):
                    # MBID ya existe, buscar el álbum existente y relacionarlo
                    target_cursor.execute('SELECT id, name FROM albums WHERE mbid = ?', (mbid,))
                    existing_result = target_cursor.fetchone()
                    if existing_result:
                        existing_album_id = existing_result['id']
                        existing_name = existing_result['name']
                        album_map[(artist_name, album_name)] = existing_album_id
                        print(f"  ℹ️ MBID {mbid} ya existe, relacionando '{artist_name} - {album_name}' con '{existing_name}' (ID: {existing_album_id})")
                        self.stats['albums_migrated'] += 1
                    continue
                elif 'name' in str(e) and 'artist_id' in str(e):
                    # Álbum ya existe para este artista
                    target_cursor.execute('SELECT id, mbid FROM albums WHERE name = ? AND artist_id = ?',
                                        (cleaned_album_name, artist_id))
                    result = target_cursor.fetchone()
                    if result:
                        album_id = result['id']
                        existing_mbid = result['mbid']
                        album_map[(artist_name, album_name)] = album_id
                        print(f"  ℹ️ Álbum '{cleaned_album_name}' ya existe (MBID: {existing_mbid}), relacionando '{artist_name} - {album_name}' (ID: {album_id})")
                        self.stats['albums_migrated'] += 1
                else:
                    print(f"  ❌ Error insertando álbum {album_name}: {e}")
                    continue

        total_albums_with_mbid = len(albums_with_existing_mbid)
        total_albums_skipped = len(potential_albums) - total_albums_with_mbid

        print(f"  ✅ Álbumes con MBID migrados: {total_albums_with_mbid:,}")
        print(f"  ⚠️ Álbumes sin MBID saltados: {total_albums_skipped:,}")

        # 4. TRACKS - Solo los de artistas con MBID
        print("🎵 Migrando tracks (solo de artistas con MBID)...")

        source_cursor.execute(f'''
            SELECT DISTINCT artist, track, album FROM scrobbles
            WHERE track IS NOT NULL AND artist IN ({placeholders})
            ORDER BY artist, track
        ''', list(migrated_artist_names))

        potential_tracks = source_cursor.fetchall()
        print(f"  📊 Tracks potenciales (de artistas con MBID): {len(potential_tracks):,}")

        # Tracks - Solo buscaremos algunos MBIDs por eficiencia
        tracks_with_existing_mbid = {}
        try:
            source_cursor.execute('''
                SELECT DISTINCT td.artist, td.track, td.mbid, td.duration_ms,
                       td.track_number, td.isrc
                FROM track_details td
                WHERE td.mbid IS NOT NULL AND td.mbid != "" AND TRIM(td.mbid) != ""
                ORDER BY td.artist, td.track
            ''')

            mbid_to_track = {}  # Para detectar MBIDs duplicados

            for row in source_cursor.fetchall():
                artist_name = row['artist']
                track_name = row['track']
                mbid = row['mbid'].strip()

                # Solo procesar si el artista fue migrado
                if artist_name not in migrated_artist_names:
                    continue

                # Verificar si este MBID ya está asignado a otro track
                if mbid in mbid_to_track:
                    existing_track = mbid_to_track[mbid]
                    print(f"  ⚠️ MBID de track duplicado {mbid}: '{existing_track}' vs '{artist_name} - {track_name}' - saltando")
                    continue

                cleaned_track_name = NameCleaner.clean_track_name(track_name)

                tracks_with_existing_mbid[(artist_name, track_name)] = {
                    'mbid': mbid,
                    'duration_ms': row['duration_ms'],
                    'track_number': row['track_number'],
                    'isrc': row['isrc']
                }

                mbid_to_track[mbid] = f"{artist_name} - {track_name}"
                self.stats['tracks_with_mbid_from_source'] += 1

            print(f"  ✅ Tracks únicos con MBID en source: {len(tracks_with_existing_mbid):,}")

        except sqlite3.OperationalError:
            print("  ⚠️ Tabla track_details no encontrada en source")

        # Para tracks, buscar MBIDs solo para los más populares
        tracks_needing_mbid = []
        for row in potential_tracks:
            artist_name = row['artist']
            track_name = row['track']
            if (artist_name, track_name) not in tracks_with_existing_mbid:
                tracks_needing_mbid.append((artist_name, track_name, row['album']))

        if tracks_needing_mbid:
            print(f"  🔍 Buscando MBIDs para tracks más populares...")

            # Obtener tracks por popularidad
            track_popularity = {}
            for artist_name, track_name, album_name in tracks_needing_mbid:
                source_cursor.execute('''
                    SELECT COUNT(*) as count FROM scrobbles
                    WHERE artist = ? AND track = ?
                ''', (artist_name, track_name))
                count = source_cursor.fetchone()['count']
                track_popularity[(artist_name, track_name)] = count

            # Ordenar por popularidad y buscar solo los top
            sorted_tracks = sorted(tracks_needing_mbid,
                                 key=lambda x: track_popularity.get((x[0], x[1]), 0),
                                 reverse=True)

            max_track_lookups = 200  # Muy limitado por eficiencia

            for i, (artist_name, track_name, album_name) in enumerate(sorted_tracks[:max_track_lookups]):
                if (i + 1) % 10 == 0:
                    print(f"    🔍 Progreso: {i + 1}/{min(len(sorted_tracks), max_track_lookups)}")

                mbid = self.mb_lookup.search_recording_mbid(artist_name, track_name)

                if mbid:
                    cleaned_track_name = NameCleaner.clean_track_name(track_name)
                    tracks_with_existing_mbid[(artist_name, track_name)] = {
                        'mbid': mbid,
                        'duration_ms': None,
                        'track_number': None,
                        'isrc': None
                    }
                    self.stats['tracks_with_mbid_from_musicbrainz'] += 1
                else:
                    self.stats['tracks_without_mbid_skipped'] += 1

        # Migrar tracks con MBID (rechazar duplicados completamente)
        track_mbids_inserted = set()  # Track de MBIDs ya insertados

        for (artist_name, track_name), metadata in tracks_with_existing_mbid.items():
            artist_id = artist_map.get(artist_name)
            if not artist_id:
                continue

            # Buscar album_id si existe
            album_id = None
            for row in potential_tracks:
                if row['artist'] == artist_name and row['track'] == track_name:
                    album_name = row['album']
                    if album_name:
                        album_id = album_map.get((artist_name, album_name))
                    break

            cleaned_track_name = NameCleaner.clean_track_name(track_name)
            mbid = metadata['mbid']

            # Verificar si ya insertamos este MBID
            if mbid in track_mbids_inserted:
                print(f"  ℹ️ MBID de track {mbid} ya procesado, relacionando: {artist_name} - {track_name}")
                # Buscar el track existente
                target_cursor.execute('SELECT id, name FROM tracks WHERE mbid = ?', (mbid,))
                existing_result = target_cursor.fetchone()
                if existing_result:
                    existing_track_id = existing_result['id']
                    existing_name = existing_result['name']
                    track_map[(artist_name, track_name)] = existing_track_id
                    print(f"  ✅ Relacionado con track existente '{existing_name}' (ID: {existing_track_id})")
                    self.stats['tracks_migrated'] += 1
                continue

            try:
                target_cursor.execute('''
                    INSERT INTO tracks (
                        name, artist_id, album_id, mbid, duration_ms, track_number, isrc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cleaned_track_name, artist_id, album_id, mbid,
                    metadata['duration_ms'], metadata['track_number'], metadata['isrc']
                ))

                track_id = target_cursor.lastrowid
                track_map[(artist_name, track_name)] = track_id
                track_mbids_inserted.add(mbid)
                self.stats['tracks_migrated'] += 1

            except sqlite3.IntegrityError as e:
                if 'mbid' in str(e):
                    # MBID ya existe, buscar el track existente y relacionarlo
                    target_cursor.execute('SELECT id, name FROM tracks WHERE mbid = ?', (mbid,))
                    existing_result = target_cursor.fetchone()
                    if existing_result:
                        existing_track_id = existing_result['id']
                        existing_name = existing_result['name']
                        track_map[(artist_name, track_name)] = existing_track_id
                        print(f"  ℹ️ MBID {mbid} ya existe, relacionando '{artist_name} - {track_name}' con '{existing_name}' (ID: {existing_track_id})")
                        self.stats['tracks_migrated'] += 1
                    continue
                elif 'name' in str(e) and 'artist_id' in str(e):
                    # Track ya existe para este artista
                    target_cursor.execute('SELECT id, mbid FROM tracks WHERE name = ? AND artist_id = ?',
                                        (cleaned_track_name, artist_id))
                    result = target_cursor.fetchone()
                    if result:
                        track_id = result['id']
                        existing_mbid = result['mbid']
                        track_map[(artist_name, track_name)] = track_id
                        print(f"  ℹ️ Track '{cleaned_track_name}' ya existe (MBID: {existing_mbid}), relacionando '{artist_name} - {track_name}' (ID: {track_id})")
                        self.stats['tracks_migrated'] += 1
                else:
                    print(f"  ❌ Error insertando track {track_name}: {e}")
                    continue

        total_tracks_with_mbid = len(tracks_with_existing_mbid)
        total_tracks_skipped = len(potential_tracks) - total_tracks_with_mbid

        print(f"  ✅ Tracks con MBID migrados: {total_tracks_with_mbid:,}")
        print(f"  ⚠️ Tracks sin MBID saltados: {total_tracks_skipped:,}")

        self.target_conn.commit()

        # Guardar mapas para uso posterior
        self.user_map = user_map
        self.artist_map = artist_map
        self.album_map = album_map
        self.track_map = track_map

    def migrate_scrobbles(self):
        """Migra scrobbles según el modo seleccionado"""
        if self.mbid_only:
            self.migrate_scrobbles_mbid_only()
        else:
            self.migrate_scrobbles_complete()

    def migrate_scrobbles_complete(self):
        """Migra todos los scrobbles (modo normal)"""
        print("\n🎧 Migrando scrobbles (todos)...")

        source_cursor = self.source_conn.cursor()
        target_cursor = self.target_conn.cursor()

        # Procesar en lotes para eficiencia
        batch_size = 10000
        offset = 0
        total_processed = 0

        while True:
            source_cursor.execute('''
                SELECT user, artist, track, album, timestamp
                FROM scrobbles
                ORDER BY timestamp
                LIMIT ? OFFSET ?
            ''', (batch_size, offset))

            batch = source_cursor.fetchall()
            if not batch:
                break

            scrobbles_batch = []

            for row in batch:
                user_id = self.user_map.get(row['user'])
                artist_id = self.artist_map.get(row['artist'])
                track_id = self.track_map.get((row['artist'], row['track']))
                album_id = self.album_map.get((row['artist'], row['album'])) if row['album'] else None

                if user_id and artist_id and track_id:
                    scrobbles_batch.append((
                        user_id, artist_id, track_id, album_id, row['timestamp']
                    ))

            if scrobbles_batch:
                target_cursor.executemany('''
                    INSERT OR IGNORE INTO scrobbles (user_id, artist_id, track_id, album_id, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', scrobbles_batch)

                total_processed += len(scrobbles_batch)
                self.stats['scrobbles_migrated'] += len(scrobbles_batch)

                if total_processed % 50000 == 0:
                    print(f"  📊 {total_processed:,} scrobbles procesados...")
                    self.target_conn.commit()

            offset += batch_size

        self.target_conn.commit()
        print(f"  ✅ {total_processed:,} scrobbles migrados")
    def migrate_scrobbles_mbid_only(self):
        """Migra solo scrobbles de entidades con MBID válido"""
        print("\n🎧 Migrando scrobbles (solo de entidades con MBID)...")

        source_cursor = self.source_conn.cursor()
        target_cursor = self.target_conn.cursor()

        # Procesar en lotes para eficiencia
        batch_size = 10000
        offset = 0
        total_processed = 0
        total_migrated = 0

        while True:
            source_cursor.execute('''
                SELECT user, artist, track, album, timestamp
                FROM scrobbles
                ORDER BY timestamp
                LIMIT ? OFFSET ?
            ''', (batch_size, offset))

            batch = source_cursor.fetchall()
            if not batch:
                break

            scrobbles_batch = []

            for row in batch:
                total_processed += 1

                user_id = self.user_map.get(row['user'])
                artist_id = self.artist_map.get(row['artist'])
                track_id = self.track_map.get((row['artist'], row['track']))
                album_id = self.album_map.get((row['artist'], row['album'])) if row['album'] else None

                # Solo migrar si tenemos user_id, artist_id Y track_id (todos con MBID)
                if user_id and artist_id and track_id:
                    scrobbles_batch.append((
                        user_id, artist_id, track_id, album_id, row['timestamp']
                    ))

            if scrobbles_batch:
                target_cursor.executemany('''
                    INSERT OR IGNORE INTO scrobbles (user_id, artist_id, track_id, album_id, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', scrobbles_batch)

                total_migrated += len(scrobbles_batch)
                self.stats['scrobbles_migrated'] += len(scrobbles_batch)

                if total_processed % 100000 == 0:
                    retention_rate = (total_migrated / total_processed) * 100
                    print(f"  📊 {total_processed:,} procesados, {total_migrated:,} migrados ({retention_rate:.1f}% retenidos)")
                    self.target_conn.commit()

            offset += batch_size

        self.target_conn.commit()

        retention_rate = (total_migrated / total_processed) * 100 if total_processed > 0 else 0

        print(f"  ✅ Scrobbles migrados: {total_migrated:,} de {total_processed:,} ({retention_rate:.1f}%)")
        print(f"  📉 Scrobbles filtrados: {total_processed - total_migrated:,}")

        # Mostrar impacto del filtrado
        if total_migrated < total_processed:
            reduction = ((total_processed - total_migrated) / total_processed) * 100
            print(f"  🎯 Reducción por filtro MBID: {reduction:.1f}% menos scrobbles")

    def migrate_first_listen_tables(self):
        """Migra las tablas de primeras escuchas (solo para entidades con MBID)"""
        print("\n🎯 Migrando tablas de primeras escuchas...")

        source_cursor = self.source_conn.cursor()
        target_cursor = self.target_conn.cursor()

        tables_to_migrate = [
            ('user_first_artist_listen', 'artist'),
            ('user_first_album_listen', 'album'),
            ('user_first_track_listen', 'track')
        ]

        for table_name, entity_type in tables_to_migrate:
            try:
                if entity_type == 'artist':
                    source_cursor.execute(f'SELECT * FROM {table_name}')
                    migrated_count = 0
                    for row in source_cursor.fetchall():
                        user_id = self.user_map.get(row['user'])
                        artist_id = self.artist_map.get(row['artist'])
                        if user_id and artist_id:
                            target_cursor.execute(f'''
                                INSERT OR REPLACE INTO {table_name}
                                (user_id, artist_id, first_timestamp)
                                VALUES (?, ?, ?)
                            ''', (user_id, artist_id, row['first_timestamp']))
                            migrated_count += 1

                elif entity_type == 'album':
                    source_cursor.execute(f'SELECT * FROM {table_name}')
                    migrated_count = 0
                    for row in source_cursor.fetchall():
                        user_id = self.user_map.get(row['user'])
                        album_id = self.album_map.get((row['artist'], row['album']))
                        if user_id and album_id:
                            target_cursor.execute(f'''
                                INSERT OR REPLACE INTO {table_name}
                                (user_id, album_id, first_timestamp)
                                VALUES (?, ?, ?)
                            ''', (user_id, album_id, row['first_timestamp']))
                            migrated_count += 1

                elif entity_type == 'track':
                    source_cursor.execute(f'SELECT * FROM {table_name}')
                    migrated_count = 0
                    for row in source_cursor.fetchall():
                        user_id = self.user_map.get(row['user'])
                        track_id = self.track_map.get((row['artist'], row['track']))
                        if user_id and track_id:
                            target_cursor.execute(f'''
                                INSERT OR REPLACE INTO {table_name}
                                (user_id, track_id, first_timestamp)
                                VALUES (?, ?, ?)
                            ''', (user_id, track_id, row['first_timestamp']))
                            migrated_count += 1

                print(f"  ✅ {table_name}: {migrated_count} registros migrados")

            except sqlite3.OperationalError as e:
                print(f"  ⚠️ {table_name} no encontrada: {e}")

        # Migrar user_first_label_listen (solo las que tienen álbumes con MBID)
        try:
            source_cursor.execute('SELECT * FROM user_first_label_listen')
            migrated_count = 0
            for row in source_cursor.fetchall():
                user_id = self.user_map.get(row['user'])
                if user_id:
                    target_cursor.execute('''
                        INSERT OR REPLACE INTO user_first_label_listen
                        (user_id, label, first_timestamp)
                        VALUES (?, ?, ?)
                    ''', (user_id, row['label'], row['first_timestamp']))
                    migrated_count += 1
            print(f"  ✅ user_first_label_listen: {migrated_count} registros migrados")
        except sqlite3.OperationalError:
            print("  ⚠️ user_first_label_listen no encontrada")

        self.target_conn.commit()

    def create_optimized_indexes(self):
        """Crea índices optimizados para la nueva estructura"""
        print("\n📈 Creando índices optimizados...")

        cursor = self.target_conn.cursor()

        indexes = [
            # Índices principales para scrobbles
            'CREATE INDEX idx_scrobbles_user_timestamp ON scrobbles(user_id, timestamp)',
            'CREATE INDEX idx_scrobbles_artist_timestamp ON scrobbles(artist_id, timestamp)',
            'CREATE INDEX idx_scrobbles_user_artist ON scrobbles(user_id, artist_id)',
            'CREATE INDEX idx_scrobbles_user_track ON scrobbles(user_id, track_id)',
            'CREATE INDEX idx_scrobbles_timestamp ON scrobbles(timestamp)',

            # Índices para lookup tables
            'CREATE INDEX idx_artists_normalized ON artists(name_normalized)',
            'CREATE INDEX idx_albums_artist ON albums(artist_id)',
            'CREATE INDEX idx_tracks_artist ON tracks(artist_id)',
            'CREATE INDEX idx_tracks_album ON tracks(album_id)',

            # Índices para metadatos
            'CREATE INDEX idx_artist_details_mbid ON artist_details(mbid)',
            'CREATE INDEX idx_album_details_mbid ON album_details(mbid)',
            'CREATE INDEX idx_track_details_mbid ON track_details(mbid)',

            # Índices para géneros
            'CREATE INDEX idx_artist_genres_detailed_artist ON artist_genres_detailed(artist_id)',
            'CREATE INDEX idx_album_genres_album ON album_genres(album_id)',

            # Índices para primeras escuchas
            'CREATE INDEX idx_first_artist_user ON user_first_artist_listen(user_id)',
            'CREATE INDEX idx_first_album_user ON user_first_album_listen(user_id)',
            'CREATE INDEX idx_first_track_user ON user_first_track_listen(user_id)'
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.OperationalError as e:
                print(f"  ⚠️ Error creando índice: {e}")

        self.target_conn.commit()
        print("  ✅ Índices creados")

    def analyze_and_vacuum(self):
        """Optimiza la nueva base de datos"""
        print("\n🧹 Optimizando base de datos...")

        cursor = self.target_conn.cursor()

        print("  📊 Analizando estadísticas...")
        cursor.execute('ANALYZE')

        print("  🗜️ Compactando base de datos...")
        cursor.execute('VACUUM')

        self.target_conn.commit()
        print("  ✅ Optimización completada")

    def compare_sizes(self):
        """Compara tamaños de bases de datos"""
        print("\n📊 COMPARACIÓN DE TAMAÑOS")
        print("=" * 50)

        source_size = os.path.getsize(self.source_db) / (1024 * 1024)  # MB
        target_size = os.path.getsize(self.target_db) / (1024 * 1024)  # MB
        reduction = ((source_size - target_size) / source_size) * 100

        print(f"📂 Base de datos original: {source_size:.1f} MB")
        print(f"📂 Base de datos normalizada: {target_size:.1f} MB")
        print(f"📉 Reducción: {reduction:.1f}% ({source_size - target_size:.1f} MB ahorrados)")

        return source_size, target_size, reduction

    def print_migration_stats(self):
        """Imprime estadísticas de migración según el modo usado"""
        mode_text = "ULTRA-OPTIMIZADA (SOLO MBID)" if self.mbid_only else "COMPLETA"
        print(f"\n📈 ESTADÍSTICAS DE MIGRACIÓN {mode_text}")
        print("=" * 60)
        print("👥 USUARIOS:")
        print(f"   • Migrados: {self.stats['users_migrated']}")

        print("\n🎤 ARTISTAS:")
        if self.mbid_only:
            print(f"   • Con MBID desde source: {self.stats['artists_with_mbid_from_source']}")
            print(f"   • Con MBID desde MusicBrainz: {self.stats['artists_with_mbid_from_musicbrainz']}")
            print(f"   • Total migrados: {self.stats['artists_migrated']}")
            print(f"   • Sin MBID (saltados): {self.stats['artists_without_mbid_skipped']}")
        else:
            print(f"   • Total migrados: {self.stats['artists_migrated']}")

        print("\n💿 ÁLBUMES:")
        if self.mbid_only:
            print(f"   • Con MBID desde source: {self.stats['albums_with_mbid_from_source']}")
            print(f"   • Con MBID desde MusicBrainz: {self.stats['albums_with_mbid_from_musicbrainz']}")
            print(f"   • Total migrados: {self.stats['albums_migrated']}")
            print(f"   • Sin MBID (saltados): {self.stats['albums_without_mbid_skipped']}")
        else:
            print(f"   • Total migrados: {self.stats['albums_migrated']}")

        print("\n🎵 TRACKS:")
        if self.mbid_only:
            print(f"   • Con MBID desde source: {self.stats['tracks_with_mbid_from_source']}")
            print(f"   • Con MBID desde MusicBrainz: {self.stats['tracks_with_mbid_from_musicbrainz']}")
            print(f"   • Total migrados: {self.stats['tracks_migrated']}")
            print(f"   • Sin MBID (saltados): {self.stats['tracks_without_mbid_skipped']}")
        else:
            print(f"   • Total migrados: {self.stats['tracks_migrated']}")

        print("\n🎧 SCROBBLES:")
        print(f"   • Migrados: {self.stats['scrobbles_migrated']}")

        if self.mbid_only:
            print("\n🎯 MODO MBID-ONLY:")
            print("   • Solo se migraron entidades con MBID válido")
            print("   • Máxima reducción de tamaño")
            print("   • Datos de alta calidad garantizados")
        else:
            print("\n🌐 MODO COMPLETO:")
            print("   • Se migraron todas las entidades")
            print("   • Metadatos integrados cuando disponibles")
            print("   • Estructura normalizada optimizada")

    def run_migration(self):
        """Ejecuta la migración completa"""
        start_time = time.time()

        mode_text = "ULTRA-OPTIMIZADA (SOLO MBID)" if self.mbid_only else "NORMALIZADA"
        target_reduction = "~150-250MB (80-85% menos)" if self.mbid_only else "~300-400MB (70-80% menos)"

        print(f"🚀 INICIANDO MIGRACIÓN {mode_text}")
        print("=" * 60)
        print(f"🎯 Objetivo: Reducir de 1.4GB a {target_reduction}")
        print("=" * 60)

        try:
            # Conectar bases de datos
            self.connect_databases()

            # Crear esquema ultra-optimizado
            self.create_ultra_optimized_schema()

            # Migrar datos según modo seleccionado
            self.migrate_entities()
            self.migrate_scrobbles()
            self.migrate_first_listen_tables()

            # Optimizar
            self.create_optimized_indexes()
            self.analyze_and_vacuum()

            # Comparar resultados
            source_size, target_size, reduction = self.compare_sizes()
            self.print_migration_stats()

            elapsed = time.time() - start_time
            print(f"\n⏱️ Tiempo total: {elapsed:.1f} segundos")

            if reduction >= 50:
                success_msg = "ULTRA-OPTIMIZADA" if self.mbid_only else "NORMALIZADA"
                print(f"\n🎉 ¡MIGRACIÓN {success_msg} EXITOSA!")
                print(f"✅ Reducción de {reduction:.1f}% lograda")
                print(f"💾 {source_size - target_size:.1f} MB ahorrados")

                if self.mbid_only:
                    print(f"🎯 Solo entidades con MBID válido migradas")
                else:
                    print(f"🌐 Todas las entidades migradas con metadatos integrados")

                print(f"\n📝 Siguientes pasos:")
                print(f"1. Verifica que todo funciona: sqlite3 {self.target_db}")
                print(f"2. Actualiza tus scripts para usar: {self.target_db}")
                print(f"3. Opcional: elimina el backup si todo está bien")
            else:
                print(f"\n⚠️ Reducción menor a la esperada ({reduction:.1f}%)")
                if self.mbid_only:
                    print("La reducción puede ser menor si:")
                    print("- Pocos artistas tenían MBID válido en tu base original")
                    print("- MusicBrainz no encontró muchos MBIDs nuevos")
                    print("- Aún así, la base está optimizada y normalizada")
                else:
                    print("La reducción es normal para migración completa")
                    print("- Se migraron todas las entidades (sin filtrar)")
                    print("- La normalización aún ofrece beneficios de rendimiento")
                    print("- Usa --mbid-only para mayor reducción de tamaño")

        except Exception as e:
            print(f"\n❌ ERROR EN MIGRACIÓN: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if self.source_conn:
                self.source_conn.close()
            if self.target_conn:
                self.target_conn.close()

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Migra base de datos Last.fm a estructura normalizada')
    parser.add_argument('--source', default='lastfm_cache.db',
                       help='Base de datos fuente (default: lastfm_cache.db)')
    parser.add_argument('--target', default='lastfm_normalized.db',
                       help='Base de datos destino (default: lastfm_normalized.db)')
    parser.add_argument('--force', action='store_true',
                       help='Sobrescribir base de datos destino si existe')
    parser.add_argument('--mbid-only', action='store_true',
                       help='Solo migrar entidades con MBID válido (máxima reducción de tamaño)')

    args = parser.parse_args()

    # Verificar archivos
    if not os.path.exists(args.source):
        print(f"❌ Base de datos fuente no encontrada: {args.source}")
        sys.exit(1)

    if os.path.exists(args.target) and not args.force:
        print(f"❌ Base de datos destino ya existe: {args.target}")
        print("Usa --force para sobrescribir o elige otro nombre con --target")
        sys.exit(1)

    if args.force and os.path.exists(args.target):
        os.remove(args.target)
        print(f"🗑️ Base de datos destino eliminada: {args.target}")

    # Mostrar información sobre el modo seleccionado
    if args.mbid_only:
        print("🎯 MODO MBID-ONLY ACTIVADO")
        print("   • Solo migrará entidades con MBID válido")
        print("   • Buscará MBIDs faltantes en MusicBrainz")
        print("   • Máxima reducción de tamaño (80-85%)")
        print("   • Datos de alta calidad garantizados")
    else:
        print("🌐 MODO COMPLETO ACTIVADO")
        print("   • Migrará todas las entidades")
        print("   • Metadatos integrados cuando estén disponibles")
        print("   • Reducción moderada (70-80%)")
        print("   • Tip: usa --mbid-only para mayor reducción")

    # Ejecutar migración
    normalizer = UltraOptimizedNormalizer(args.source, args.target, args.mbid_only)
    success = normalizer.run_migration()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

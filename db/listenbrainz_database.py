#!/usr/bin/env python3
"""
ListenBrainz to Last.fm Database Importer
Importa scrobbles desde ListenBrainz y los guarda en la base de datos con el usuario de Last.fm especificado
"""

import os
import sys
import requests
import json
import sqlite3
import time
import argparse
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import urllib.parse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class ListenBrainzListen:
    """Estructura de datos para un listen de ListenBrainz"""
    user: str
    artist: str
    track: str
    album: str
    timestamp: int
    artist_mbid: Optional[str] = None
    album_mbid: Optional[str] = None
    track_mbid: Optional[str] = None
    recording_mbid: Optional[str] = None


class ListenBrainzDatabase:
    """Clase simplificada para manejar la base de datos"""

    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._ensure_tables()

    def _ensure_tables(self):
        """Asegura que las tablas necesarias existan"""
        cursor = self.conn.cursor()

        # Tabla principal de scrobbles (debe existir del script original)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrobbles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                artist TEXT NOT NULL,
                track TEXT NOT NULL,
                album TEXT,
                timestamp INTEGER NOT NULL,
                artist_mbid TEXT,
                album_mbid TEXT,
                track_mbid TEXT,
                UNIQUE(user, timestamp, artist, track)
            )
        ''')

        # Tabla para tracking de imports de ListenBrainz
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listenbrainz_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listenbrainz_user TEXT NOT NULL,
                lastfm_user TEXT NOT NULL,
                last_import_timestamp INTEGER,
                total_imported INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(listenbrainz_user, lastfm_user)
            )
        ''')

        # Índices
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_user_timestamp
            ON scrobbles(user, timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_listenbrainz_imports_users
            ON listenbrainz_imports(listenbrainz_user, lastfm_user)
        ''')

        self.conn.commit()

    def get_last_import_timestamp(self, listenbrainz_user: str, lastfm_user: str) -> int:
        """Obtiene el timestamp del último import para este par de usuarios"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT last_import_timestamp FROM listenbrainz_imports
            WHERE listenbrainz_user = ? AND lastfm_user = ?
        ''', (listenbrainz_user, lastfm_user))
        result = cursor.fetchone()
        return result['last_import_timestamp'] if result and result['last_import_timestamp'] else 0

    def update_import_status(self, listenbrainz_user: str, lastfm_user: str,
                           last_timestamp: int, imported_count: int):
        """Actualiza el estado del import"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO listenbrainz_imports
                (listenbrainz_user, lastfm_user, last_import_timestamp, total_imported, created_at, updated_at)
                VALUES (?, ?, ?,
                    COALESCE((SELECT total_imported FROM listenbrainz_imports
                             WHERE listenbrainz_user = ? AND lastfm_user = ?), 0) + ?,
                    COALESCE((SELECT created_at FROM listenbrainz_imports
                             WHERE listenbrainz_user = ? AND lastfm_user = ?), ?),
                    ?)
            ''', (listenbrainz_user, lastfm_user, last_timestamp, imported_count,
                  listenbrainz_user, lastfm_user, imported_count,
                  listenbrainz_user, lastfm_user, int(time.time()),
                  int(time.time())))
            self.conn.commit()

    def save_listens(self, listens: List[ListenBrainzListen]):
        """Guarda los listens como scrobbles en la base de datos"""
        with self.lock:
            cursor = self.conn.cursor()
            imported_count = 0

            for listen in listens:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO scrobbles
                        (user, artist, track, album, timestamp, artist_mbid, album_mbid, track_mbid)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        listen.user,  # Usamos el usuario de Last.fm
                        listen.artist,
                        listen.track,
                        listen.album,
                        listen.timestamp,
                        listen.artist_mbid,
                        listen.album_mbid,
                        listen.recording_mbid  # En ListenBrainz el track MBID es recording MBID
                    ))
                    if cursor.rowcount > 0:
                        imported_count += 1
                except sqlite3.IntegrityError:
                    # Scrobble duplicado, ignorar
                    pass

            self.conn.commit()
            return imported_count

    def get_user_scrobble_count(self, user: str) -> int:
        """Obtiene el número de scrobbles de un usuario"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM scrobbles WHERE user = ?', (user,))
        result = cursor.fetchone()
        return result['count'] if result else 0

    def close(self):
        self.conn.close()


class ListenBrainzClient:
    """Cliente para la API de ListenBrainz"""

    def __init__(self):
        self.base_url = "https://api.listenbrainz.org/1/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ListenBrainz-Importer/1.0'
        })

    def get_listens(self, user: str, count: int = 1000, max_ts: Optional[int] = None,
                   min_ts: Optional[int] = None) -> Optional[Dict]:
        """
        Obtiene listens de un usuario

        Args:
            user: Usuario de ListenBrainz
            count: Número de listens a obtener (máximo 1000)
            max_ts: Timestamp máximo (para obtener listens anteriores a este momento)
            min_ts: Timestamp mínimo (para obtener listens posteriores a este momento)
        """
        url = f"{self.base_url}user/{user}/listens"

        params = {
            'count': min(count, 1000)  # ListenBrainz límite máximo es 1000
        }

        if max_ts:
            params['max_ts'] = max_ts
        if min_ts:
            params['min_ts'] = min_ts

        try:
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"   ❌ Usuario '{user}' no encontrado en ListenBrainz")
                return None
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"   ⏳ Rate limit en ListenBrainz. Esperando {retry_after}s...")
                time.sleep(retry_after)
                return self.get_listens(user, count, max_ts, min_ts)
            else:
                print(f"   ⚠️ Error HTTP {response.status_code} en ListenBrainz")
                return None

        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Error de conexión con ListenBrainz: {e}")
            return None

    def get_user_info(self, user: str) -> Optional[Dict]:
        """Obtiene información básica de un usuario"""
        url = f"{self.base_url}user/{user}"

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.RequestException:
            return None


class ListenBrainzImporter:
    """Importador principal de datos desde ListenBrainz"""

    def __init__(self):
        self.client = ListenBrainzClient()
        self.db = ListenBrainzDatabase()

    def parse_listens(self, listens_data: List[Dict], lastfm_user: str) -> List[ListenBrainzListen]:
        """Convierte datos de ListenBrainz a estructura interna"""
        parsed_listens = []

        for listen_data in listens_data:
            try:
                # Información básica del listen
                listened_at = listen_data.get('listened_at', 0)
                track_metadata = listen_data.get('track_metadata', {})

                # Extraer nombres
                artist_name = track_metadata.get('artist_name', '')
                track_name = track_metadata.get('track_name', '')
                release_name = track_metadata.get('release_name', '')

                # Extraer MBIDs
                additional_info = track_metadata.get('additional_info', {})
                artist_mbids = additional_info.get('artist_mbids', [])
                release_mbid = additional_info.get('release_mbid')
                recording_mbid = additional_info.get('recording_mbid')

                # Usar el primer artist MBID si existe
                artist_mbid = artist_mbids[0] if artist_mbids else None

                # Normalizar datos vacíos
                if not artist_name.strip():
                    continue  # Saltar si no hay artista

                if not track_name.strip():
                    continue  # Saltar si no hay track

                listen = ListenBrainzListen(
                    user=lastfm_user,  # ¡IMPORTANTE! Usamos el usuario de Last.fm
                    artist=artist_name.strip(),
                    track=track_name.strip(),
                    album=release_name.strip() if release_name else '',
                    timestamp=listened_at,
                    artist_mbid=artist_mbid if artist_mbid else None,
                    album_mbid=release_mbid if release_mbid else None,
                    recording_mbid=recording_mbid if recording_mbid else None
                )

                parsed_listens.append(listen)

            except Exception as e:
                print(f"   ⚠️ Error parseando listen: {e}")
                continue

        return parsed_listens

    def import_user_listens(self, listenbrainz_user: str, lastfm_user: str,
                          import_all: bool = False, max_listens: Optional[int] = None) -> int:
        """
        Importa listens de un usuario de ListenBrainz

        Args:
            listenbrainz_user: Usuario de ListenBrainz
            lastfm_user: Usuario de Last.fm (para guardar en la BD)
            import_all: Si es True, importa todo el historial
            max_listens: Máximo número de listens a importar (None = sin límite)

        Returns:
            Número total de listens importados
        """
        print(f"\n🎵 Importando listens de ListenBrainz...")
        print(f"   📡 Usuario ListenBrainz: {listenbrainz_user}")
        print(f"   👤 Usuario Last.fm (BD): {lastfm_user}")

        # Verificar que el usuario existe en ListenBrainz
        user_info = self.client.get_user_info(listenbrainz_user)
        if not user_info:
            print(f"   ❌ No se pudo obtener información del usuario {listenbrainz_user}")
            return 0

        # Determinar punto de inicio
        if import_all:
            print(f"   🔄 Modo: Importación completa")
            last_timestamp = None
            max_ts = None
        else:
            print(f"   🔄 Modo: Importación incremental")
            last_timestamp = self.db.get_last_import_timestamp(listenbrainz_user, lastfm_user)
            max_ts = None if last_timestamp == 0 else None

        total_imported = 0
        processed_batches = 0
        latest_timestamp = 0
        current_max_ts = max_ts

        # Obtener el primer batch para ver cuántos listens hay
        first_batch = self.client.get_listens(listenbrainz_user, count=1000, max_ts=current_max_ts)
        if not first_batch or 'listens' not in first_batch:
            print(f"   ❌ No se pudieron obtener listens para {listenbrainz_user}")
            return 0

        print(f"   📊 Iniciando importación...")

        while True:
            # Verificar límite máximo si está establecido
            if max_listens and total_imported >= max_listens:
                print(f"   🛑 Límite máximo de {max_listens} listens alcanzado")
                break

            # Obtener batch de listens
            data = self.client.get_listens(
                listenbrainz_user,
                count=min(1000, max_listens - total_imported) if max_listens else 1000,
                max_ts=current_max_ts,
                min_ts=last_timestamp if not import_all else None
            )

            if not data or 'listens' not in data or not data['listens']:
                break

            listens = data['listens']

            # En modo incremental, filtrar listens más antiguos que el último import
            if not import_all and last_timestamp > 0:
                listens = [l for l in listens if l.get('listened_at', 0) > last_timestamp]

            if not listens:
                break

            # Parsear listens
            parsed_listens = self.parse_listens(listens, lastfm_user)

            if not parsed_listens:
                # Si no hay listens válidos, actualizar max_ts y continuar
                oldest_ts = min(l.get('listened_at', 0) for l in listens)
                current_max_ts = oldest_ts - 1
                continue

            # Guardar en base de datos
            imported_count = self.db.save_listens(parsed_listens)
            total_imported += imported_count
            processed_batches += 1

            # Actualizar timestamps
            newest_timestamp = max(listen.timestamp for listen in parsed_listens)
            oldest_timestamp = min(listen.timestamp for listen in parsed_listens)

            if newest_timestamp > latest_timestamp:
                latest_timestamp = newest_timestamp

            # Log de progreso
            if processed_batches % 5 == 0:
                print(f"   📈 Procesados {processed_batches} batches, "
                      f"{total_imported} listens importados")

            # Preparar para el siguiente batch
            current_max_ts = oldest_timestamp - 1

            # Pequeño delay para no sobrecargar la API
            time.sleep(0.5)

        # Actualizar estado del import
        if total_imported > 0:
            self.db.update_import_status(
                listenbrainz_user,
                lastfm_user,
                latest_timestamp,
                total_imported
            )

        print(f"   ✅ Importación completada: {total_imported} listens nuevos")
        return total_imported

    def get_import_stats(self, listenbrainz_user: str, lastfm_user: str) -> Dict:
        """Obtiene estadísticas del import"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT last_import_timestamp, total_imported, created_at, updated_at
            FROM listenbrainz_imports
            WHERE listenbrainz_user = ? AND lastfm_user = ?
        ''', (listenbrainz_user, lastfm_user))

        result = cursor.fetchone()
        if not result:
            return {
                'last_import': None,
                'total_imported': 0,
                'first_import': None,
                'last_update': None
            }

        return {
            'last_import': datetime.fromtimestamp(result['last_import_timestamp']) if result['last_import_timestamp'] else None,
            'total_imported': result['total_imported'],
            'first_import': datetime.fromtimestamp(result['created_at']),
            'last_update': datetime.fromtimestamp(result['updated_at'])
        }


def main():
    parser = argparse.ArgumentParser(
        description='Importa scrobbles desde ListenBrainz a la base de datos de Last.fm'
    )

    parser.add_argument('--listenbrainz-user', required=True,
                       help='Usuario de ListenBrainz desde el cual importar')
    parser.add_argument('--lastfm-user', required=True,
                       help='Usuario de Last.fm bajo el cual guardar los datos en la BD')
    parser.add_argument('--all', action='store_true',
                       help='Importar todo el historial (por defecto: solo nuevos listens)')
    parser.add_argument('--max-listens', type=int,
                       help='Máximo número de listens a importar')
    parser.add_argument('--stats', action='store_true',
                       help='Mostrar estadísticas del import sin importar datos')
    parser.add_argument('--db-path', default='lastfm_cache.db',
                       help='Ruta a la base de datos (por defecto: lastfm_cache.db)')

    args = parser.parse_args()

    try:
        importer = ListenBrainzImporter()
        importer.db.db_path = args.db_path

        if args.stats:
            # Mostrar estadísticas
            stats = importer.get_import_stats(args.listenbrainz_user, args.lastfm_user)

            print("=" * 60)
            print("📊 ESTADÍSTICAS DE IMPORTACIÓN")
            print("=" * 60)
            print(f"ListenBrainz User: {args.listenbrainz_user}")
            print(f"Last.fm User (BD): {args.lastfm_user}")
            print(f"Total importado: {stats['total_imported']} listens")

            if stats['last_import']:
                print(f"Último import: {stats['last_import'].strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("Último import: Nunca")

            if stats['first_import']:
                print(f"Primer import: {stats['first_import'].strftime('%Y-%m-%d %H:%M:%S')}")

            # Mostrar total de scrobbles del usuario en la BD
            total_scrobbles = importer.db.get_user_scrobble_count(args.lastfm_user)
            print(f"Total scrobbles en BD: {total_scrobbles}")

        else:
            # Realizar import
            print("=" * 60)
            print("🎧 IMPORTADOR DE LISTENBRAINZ")
            print("=" * 60)

            imported = importer.import_user_listens(
                args.listenbrainz_user,
                args.lastfm_user,
                import_all=args.all,
                max_listens=args.max_listens
            )

            print("\n" + "=" * 60)
            print("✅ IMPORTACIÓN COMPLETADA")
            print("=" * 60)
            print(f"🎵 Listens importados: {imported}")
            print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # Mostrar estadísticas finales
            total_scrobbles = importer.db.get_user_scrobble_count(args.lastfm_user)
            print(f"📊 Total scrobbles del usuario: {total_scrobbles}")

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

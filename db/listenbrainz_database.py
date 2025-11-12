#!/usr/bin/env python3
"""
ListenBrainz Local File Importer
Importa scrobbles desde archivos JSONL locales de ListenBrainz y los guarda en la base de datos
"""

import os
import sys
import json
import sqlite3
import time
import argparse
import threading
import glob
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

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
    """Clase para manejar la base de datos"""

    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._ensure_tables()

    def _ensure_tables(self):
        """Asegura que las tablas necesarias existan"""
        cursor = self.conn.cursor()

        # Tabla principal de scrobbles
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

        # Tabla para tracking de imports de archivos locales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listenbrainz_file_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_directory TEXT NOT NULL,
                lastfm_user TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_mtime INTEGER NOT NULL,
                listens_imported INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(source_directory, lastfm_user, file_path)
            )
        ''')

        # Índices
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_user_timestamp
            ON scrobbles(user, timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_imports_path
            ON listenbrainz_file_imports(source_directory, file_path)
        ''')

        self.conn.commit()

    def is_file_processed(self, source_dir: str, lastfm_user: str, file_path: str, file_mtime: int) -> bool:
        """Verifica si un archivo ya fue procesado (basado en la fecha de modificación)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT file_mtime FROM listenbrainz_file_imports
            WHERE source_directory = ? AND lastfm_user = ? AND file_path = ?
        ''', (source_dir, lastfm_user, file_path))
        result = cursor.fetchone()

        if not result:
            return False

        return result['file_mtime'] >= file_mtime

    def mark_file_processed(self, source_dir: str, lastfm_user: str, file_path: str,
                          file_mtime: int, listens_count: int):
        """Marca un archivo como procesado"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO listenbrainz_file_imports
                (source_directory, lastfm_user, file_path, file_mtime, listens_imported, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (source_dir, lastfm_user, file_path, file_mtime, listens_count, int(time.time())))
            self.conn.commit()

    def save_listens(self, listens: List[ListenBrainzListen]) -> int:
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
                        listen.user,
                        listen.artist,
                        listen.track,
                        listen.album,
                        listen.timestamp,
                        listen.artist_mbid,
                        listen.album_mbid,
                        listen.recording_mbid
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

    def get_import_stats(self, source_dir: str, lastfm_user: str) -> Dict:
        """Obtiene estadísticas de import"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT
                COUNT(*) as files_processed,
                SUM(listens_imported) as total_imported,
                MIN(created_at) as first_import,
                MAX(created_at) as last_import
            FROM listenbrainz_file_imports
            WHERE source_directory = ? AND lastfm_user = ?
        ''', (source_dir, lastfm_user))

        result = cursor.fetchone()
        if not result or result['files_processed'] == 0:
            return {
                'files_processed': 0,
                'total_imported': 0,
                'first_import': None,
                'last_import': None
            }

        return {
            'files_processed': result['files_processed'],
            'total_imported': result['total_imported'] or 0,
            'first_import': datetime.fromtimestamp(result['first_import']) if result['first_import'] else None,
            'last_import': datetime.fromtimestamp(result['last_import']) if result['last_import'] else None
        }

    def close(self):
        self.conn.close()


class ListenBrainzFileReader:
    """Lector de archivos JSONL de ListenBrainz"""

    def __init__(self, base_directory: str):
        self.base_directory = Path(base_directory)
        if not self.base_directory.exists():
            raise FileNotFoundError(f"Directorio no encontrado: {base_directory}")

    def find_jsonl_files(self, year_filter: Optional[int] = None, month_filter: Optional[int] = None) -> List[Tuple[Path, int]]:
        """
        Encuentra todos los archivos JSONL en la estructura listens/year/month.jsonl

        Returns:
            Lista de tuplas (ruta_archivo, timestamp_modificacion)
        """
        files = []
        listens_dir = self.base_directory / "listens"

        if not listens_dir.exists():
            print(f"   ❌ Directorio 'listens' no encontrado en {self.base_directory}")
            return []

        # Buscar archivos según filtros
        if year_filter:
            year_dirs = [listens_dir / str(year_filter)]
        else:
            year_dirs = [d for d in listens_dir.iterdir() if d.is_dir() and d.name.isdigit()]

        for year_dir in year_dirs:
            if not year_dir.exists():
                continue

            if month_filter:
                month_files = [year_dir / f"{month_filter}.jsonl"]
            else:
                month_files = list(year_dir.glob("*.jsonl"))

            for month_file in month_files:
                if month_file.exists() and month_file.is_file():
                    mtime = int(month_file.stat().st_mtime)
                    files.append((month_file, mtime))

        # Ordenar por fecha (más antiguos primero)
        files.sort(key=lambda x: x[0].stem)  # Ordenar por nombre de archivo

        return files

    def parse_jsonl_file(self, file_path: Path, lastfm_user: str) -> List[ListenBrainzListen]:
        """Parsea un archivo JSONL y convierte a estructura interna"""
        listens = []
        line_count = 0
        error_count = 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    line_count += 1
                    try:
                        data = json.loads(line)
                        listen = self._parse_listen_data(data, lastfm_user)
                        if listen:
                            listens.append(listen)
                    except json.JSONDecodeError as e:
                        error_count += 1
                        if error_count <= 5:  # Solo mostrar primeros 5 errores
                            print(f"     ⚠️ Error JSON línea {line_num}: {e}")
                    except Exception as e:
                        error_count += 1
                        if error_count <= 5:
                            print(f"     ⚠️ Error parseando línea {line_num}: {e}")

        except Exception as e:
            print(f"   ❌ Error leyendo archivo {file_path}: {e}")
            return []

        if error_count > 5:
            print(f"     ... y {error_count - 5} errores más")

        print(f"     📊 Líneas: {line_count}, Válidas: {len(listens)}, Errores: {error_count}")
        return listens

    def _parse_listen_data(self, data: Dict, lastfm_user: str) -> Optional[ListenBrainzListen]:
        """Convierte un objeto JSON de listen a ListenBrainzListen"""
        try:
            # Información básica
            listened_at = data.get('listened_at', 0)
            track_metadata = data.get('track_metadata', {})

            # Extraer nombres básicos
            artist_name = track_metadata.get('artist_name', '').strip()
            track_name = track_metadata.get('track_name', '').strip()
            release_name = track_metadata.get('release_name', '').strip()

            # Validar datos mínimos
            if not artist_name or not track_name:
                return None

            # Extraer MBIDs desde mbid_mapping (formato nuevo)
            mbid_mapping = track_metadata.get('mbid_mapping', {})

            # Artist MBID
            artist_mbid = None
            artist_mbids = mbid_mapping.get('artist_mbids', [])
            if artist_mbids:
                artist_mbid = artist_mbids[0]

            # Release/Album MBID
            album_mbid = mbid_mapping.get('release_mbid')

            # Recording MBID
            recording_mbid = mbid_mapping.get('recording_mbid')

            # Si no hay mbid_mapping, intentar con additional_info (formato antiguo)
            if not any([artist_mbid, album_mbid, recording_mbid]):
                additional_info = track_metadata.get('additional_info', {})
                artist_mbid = additional_info.get('artist_mbid')
                album_mbid = additional_info.get('release_mbid')
                recording_mbid = additional_info.get('recording_mbid')

            return ListenBrainzListen(
                user=lastfm_user,
                artist=artist_name,
                track=track_name,
                album=release_name,
                timestamp=listened_at,
                artist_mbid=artist_mbid,
                album_mbid=album_mbid,
                recording_mbid=recording_mbid
            )

        except Exception as e:
            return None


class ListenBrainzLocalImporter:
    """Importador principal de archivos locales de ListenBrainz"""

    def __init__(self, source_directory: str, db_path: str = 'lastfm_cache.db'):
        self.reader = ListenBrainzFileReader(source_directory)
        self.db = ListenBrainzDatabase(db_path)
        self.source_directory = str(Path(source_directory).absolute())

    def import_files(self, lastfm_user: str, force_reimport: bool = False,
                    year_filter: Optional[int] = None, month_filter: Optional[int] = None,
                    max_files: Optional[int] = None) -> int:
        """
        Importa archivos JSONL a la base de datos

        Args:
            lastfm_user: Usuario de Last.fm para guardar en la BD
            force_reimport: Si es True, reprocessa archivos ya importados
            year_filter: Solo importar archivos de este año (YYYY)
            month_filter: Solo importar archivos de este mes (MM)
            max_files: Máximo número de archivos a procesar

        Returns:
            Número total de listens importados
        """
        print(f"\n🎵 Importando archivos JSONL de ListenBrainz...")
        print(f"   📁 Directorio: {self.source_directory}")
        print(f"   👤 Usuario Last.fm (BD): {lastfm_user}")

        # Encontrar archivos
        files = self.reader.find_jsonl_files(year_filter, month_filter)
        if not files:
            print(f"   ❌ No se encontraron archivos JSONL")
            return 0

        if max_files:
            files = files[:max_files]

        print(f"   📊 Archivos encontrados: {len(files)}")

        total_imported = 0
        processed_files = 0
        skipped_files = 0

        for file_path, file_mtime in files:
            relative_path = str(file_path.relative_to(self.reader.base_directory))

            # Verificar si el archivo ya fue procesado
            if not force_reimport and self.db.is_file_processed(
                self.source_directory, lastfm_user, relative_path, file_mtime
            ):
                skipped_files += 1
                if skipped_files % 10 == 1:  # Mostrar cada 10 archivos saltados
                    print(f"   ⏭️ Saltando archivos ya procesados... ({skipped_files})")
                continue

            print(f"\n   📄 Procesando: {relative_path}")

            # Parsear archivo
            listens = self.reader.parse_jsonl_file(file_path, lastfm_user)

            if not listens:
                print(f"     ⚠️ No se encontraron listens válidos")
                continue

            # Guardar en base de datos
            imported_count = self.db.save_listens(listens)
            total_imported += imported_count
            processed_files += 1

            # Marcar archivo como procesado
            self.db.mark_file_processed(
                self.source_directory, lastfm_user, relative_path, file_mtime, imported_count
            )

            print(f"     ✅ Importados: {imported_count} nuevos listens")

            # Progreso cada 5 archivos
            if processed_files % 5 == 0:
                print(f"\n   📈 Progreso: {processed_files} archivos procesados, "
                      f"{total_imported} listens importados")

        print(f"\n   ✅ Importación completada:")
        print(f"     📄 Archivos procesados: {processed_files}")
        print(f"     ⏭️ Archivos saltados: {skipped_files}")
        print(f"     🎵 Listens importados: {total_imported}")

        return total_imported


def main():
    parser = argparse.ArgumentParser(
        description='Importa scrobbles desde archivos JSONL locales de ListenBrainz'
    )

    parser.add_argument('--source-dir', required=True,
                       help='Directorio base con los archivos de ListenBrainz (contiene carpeta "listens")')
    parser.add_argument('--lastfm-user', required=True,
                       help='Usuario de Last.fm bajo el cual guardar los datos en la BD')
    parser.add_argument('--force', action='store_true',
                       help='Reprocesar archivos ya importados')
    parser.add_argument('--year', type=int,
                       help='Solo importar archivos de este año (YYYY)')
    parser.add_argument('--month', type=int,
                       help='Solo importar archivos de este mes (MM)')
    parser.add_argument('--max-files', type=int,
                       help='Máximo número de archivos a procesar')
    parser.add_argument('--stats', action='store_true',
                       help='Mostrar estadísticas de import sin importar datos')
    parser.add_argument('--db-path', default='lastfm_cache.db',
                       help='Ruta a la base de datos (por defecto: lastfm_cache.db)')

    args = parser.parse_args()

    try:
        importer = ListenBrainzLocalImporter(args.source_dir, args.db_path)

        if args.stats:
            # Mostrar estadísticas
            stats = importer.db.get_import_stats(importer.source_directory, args.lastfm_user)

            print("=" * 60)
            print("📊 ESTADÍSTICAS DE IMPORTACIÓN")
            print("=" * 60)
            print(f"Directorio fuente: {args.source_dir}")
            print(f"Usuario Last.fm (BD): {args.lastfm_user}")
            print(f"Archivos procesados: {stats['files_processed']}")
            print(f"Total importado: {stats['total_imported']} listens")

            if stats['first_import']:
                print(f"Primer import: {stats['first_import'].strftime('%Y-%m-%d %H:%M:%S')}")
            if stats['last_import']:
                print(f"Último import: {stats['last_import'].strftime('%Y-%m-%d %H:%M:%S')}")

            # Mostrar total de scrobbles del usuario en la BD
            total_scrobbles = importer.db.get_user_scrobble_count(args.lastfm_user)
            print(f"Total scrobbles en BD: {total_scrobbles}")

        else:
            # Realizar import
            print("=" * 60)
            print("🎧 IMPORTADOR LOCAL DE LISTENBRAINZ")
            print("=" * 60)

            imported = importer.import_files(
                args.lastfm_user,
                force_reimport=args.force,
                year_filter=args.year,
                month_filter=args.month,
                max_files=args.max_files
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

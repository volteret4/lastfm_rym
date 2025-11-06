#!/usr/bin/env python3
"""
Script de Migración - Retroalimentación de MBIDs
Actualiza scrobbles existentes con MBIDs cuando están disponibles en los datos enriquecidos
"""

import sqlite3
import sys
from typing import Dict, Tuple

class MigrationHelper:
    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def check_migration_status(self) -> Dict:
        """Verifica el estado actual de la migración"""
        cursor = self.conn.cursor()

        # Total de scrobbles
        cursor.execute('SELECT COUNT(*) as total FROM scrobbles')
        total_scrobbles = cursor.fetchone()['total']

        # Verificar si existen las columnas MBIDs
        cursor.execute("PRAGMA table_info(scrobbles)")
        columns = [row[1] for row in cursor.fetchall()]

        has_artist_mbid = 'artist_mbid' in columns
        has_album_mbid = 'album_mbid' in columns
        has_track_mbid = 'track_mbid' in columns

        # Scrobbles con MBIDs ya asignados (solo si las columnas existen)
        scrobbles_with_artist_mbid = 0
        scrobbles_with_album_mbid = 0
        scrobbles_with_track_mbid = 0

        if has_artist_mbid:
            cursor.execute('SELECT COUNT(*) as with_mbid FROM scrobbles WHERE artist_mbid IS NOT NULL')
            scrobbles_with_artist_mbid = cursor.fetchone()['with_mbid']

        if has_album_mbid:
            cursor.execute('SELECT COUNT(*) as with_mbid FROM scrobbles WHERE album_mbid IS NOT NULL')
            scrobbles_with_album_mbid = cursor.fetchone()['with_mbid']

        if has_track_mbid:
            cursor.execute('SELECT COUNT(*) as with_mbid FROM scrobbles WHERE track_mbid IS NOT NULL')
            scrobbles_with_track_mbid = cursor.fetchone()['with_mbid']

        # Datos disponibles para retroalimentar (verificar si las tablas existen)
        artist_mbids_available = 0
        album_mbids_available = 0
        track_mbids_available = 0

        # Verificar si existen las tablas de detalles
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artist_details'")
        has_artist_details = cursor.fetchone() is not None

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='album_details'")
        has_album_details = cursor.fetchone() is not None

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='track_details'")
        has_track_details = cursor.fetchone() is not None

        if has_artist_details:
            cursor.execute('SELECT COUNT(*) as available FROM artist_details WHERE mbid IS NOT NULL')
            artist_mbids_available = cursor.fetchone()['available']

        if has_album_details:
            cursor.execute('SELECT COUNT(*) as available FROM album_details WHERE mbid IS NOT NULL')
            album_mbids_available = cursor.fetchone()['available']

        if has_track_details:
            cursor.execute('SELECT COUNT(*) as available FROM track_details WHERE mbid IS NOT NULL')
            track_mbids_available = cursor.fetchone()['available']

        return {
            'total_scrobbles': total_scrobbles,
            'has_mbid_columns': {
                'artist': has_artist_mbid,
                'album': has_album_mbid,
                'track': has_track_mbid
            },
            'has_detail_tables': {
                'artist': has_artist_details,
                'album': has_album_details,
                'track': has_track_details
            },
            'current_mbids': {
                'artist': scrobbles_with_artist_mbid,
                'album': scrobbles_with_album_mbid,
                'track': scrobbles_with_track_mbid
            },
            'available_mbids': {
                'artist': artist_mbids_available,
                'album': album_mbids_available,
                'track': track_mbids_available
            }
        }

    def add_missing_columns(self):
        """Añade las columnas de MBIDs si no existen"""
        cursor = self.conn.cursor()

        columns_to_add = [
            ('artist_mbid', 'TEXT'),
            ('album_mbid', 'TEXT'),
            ('track_mbid', 'TEXT')
        ]

        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f'ALTER TABLE scrobbles ADD COLUMN {column_name} {column_type}')
                print(f"   ✅ Columna {column_name} añadida")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"   ℹ️ Columna {column_name} ya existe")
                else:
                    print(f"   ⚠️ Error añadiendo {column_name}: {e}")

        self.conn.commit()

    def backfill_artist_mbids(self) -> int:
        """Retroalimenta MBIDs de artistas desde artist_details"""
        cursor = self.conn.cursor()

        # Verificar si la columna artist_mbid existe
        cursor.execute("PRAGMA table_info(scrobbles)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'artist_mbid' not in columns:
            print(f"   ⚠️ Columna artist_mbid no existe aún. Se omite este paso.")
            return 0

        # Verificar si la tabla artist_details existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artist_details'")
        if not cursor.fetchone():
            print(f"   ⚠️ Tabla artist_details no existe aún. Se omite este paso.")
            return 0

        # Encontrar scrobbles sin artist_mbid que tienen datos disponibles
        cursor.execute('''
            UPDATE scrobbles
            SET artist_mbid = (
                SELECT ad.mbid
                FROM artist_details ad
                WHERE ad.artist = scrobbles.artist
                AND ad.mbid IS NOT NULL
            )
            WHERE artist_mbid IS NULL
            AND artist IN (
                SELECT artist FROM artist_details WHERE mbid IS NOT NULL
            )
        ''')

        updated_rows = cursor.rowcount
        self.conn.commit()
        return updated_rows

    def backfill_album_mbids(self) -> int:
        """Retroalimenta MBIDs de álbumes desde album_details"""
        cursor = self.conn.cursor()

        # Verificar si la columna album_mbid existe
        cursor.execute("PRAGMA table_info(scrobbles)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'album_mbid' not in columns:
            print(f"   ⚠️ Columna album_mbid no existe aún. Se omite este paso.")
            return 0

        # Verificar si la tabla album_details existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='album_details'")
        if not cursor.fetchone():
            print(f"   ⚠️ Tabla album_details no existe aún. Se omite este paso.")
            return 0

        cursor.execute('''
            UPDATE scrobbles
            SET album_mbid = (
                SELECT ald.mbid
                FROM album_details ald
                WHERE ald.artist = scrobbles.artist
                AND ald.album = scrobbles.album
                AND ald.mbid IS NOT NULL
            )
            WHERE album_mbid IS NULL
            AND album IS NOT NULL
            AND album != ''
            AND (artist, album) IN (
                SELECT artist, album FROM album_details WHERE mbid IS NOT NULL
            )
        ''')

        updated_rows = cursor.rowcount
        self.conn.commit()
        return updated_rows

    def backfill_track_mbids(self) -> int:
        """Retroalimenta MBIDs de tracks desde track_details"""
        cursor = self.conn.cursor()

        # Verificar si la columna track_mbid existe
        cursor.execute("PRAGMA table_info(scrobbles)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'track_mbid' not in columns:
            print(f"   ⚠️ Columna track_mbid no existe aún. Se omite este paso.")
            return 0

        # Verificar si la tabla track_details existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='track_details'")
        if not cursor.fetchone():
            print(f"   ⚠️ Tabla track_details no existe aún. Se omite este paso.")
            return 0

        cursor.execute('''
            UPDATE scrobbles
            SET track_mbid = (
                SELECT td.mbid
                FROM track_details td
                WHERE td.artist = scrobbles.artist
                AND td.track = scrobbles.track
                AND td.mbid IS NOT NULL
            )
            WHERE track_mbid IS NULL
            AND (artist, track) IN (
                SELECT artist, track FROM track_details WHERE mbid IS NOT NULL
            )
        ''')

        updated_rows = cursor.rowcount
        self.conn.commit()
        return updated_rows

    def create_missing_indexes(self):
        """Crea índices que pueden estar faltando"""
        cursor = self.conn.cursor()

        # Verificar qué columnas existen
        cursor.execute("PRAGMA table_info(scrobbles)")
        scrobbles_columns = [row[1] for row in cursor.fetchall()]

        # Verificar qué tablas existen
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        indexes_to_create = []

        # Índices para scrobbles solo si las columnas existen
        if 'artist_mbid' in scrobbles_columns:
            indexes_to_create.append(('idx_scrobbles_artist_mbid', 'scrobbles', 'artist_mbid'))
        if 'album_mbid' in scrobbles_columns:
            indexes_to_create.append(('idx_scrobbles_album_mbid', 'scrobbles', 'album_mbid'))
        if 'track_mbid' in scrobbles_columns:
            indexes_to_create.append(('idx_scrobbles_track_mbid', 'scrobbles', 'track_mbid'))

        # Índices para tablas de detalles solo si existen
        if 'artist_details' in existing_tables:
            indexes_to_create.append(('idx_artist_details_mbid', 'artist_details', 'mbid'))
        if 'album_details' in existing_tables:
            indexes_to_create.append(('idx_album_details_mbid', 'album_details', 'mbid'))
        if 'track_details' in existing_tables:
            indexes_to_create.append(('idx_track_details_mbid', 'track_details', 'mbid'))

        if not indexes_to_create:
            print(f"   ℹ️ No hay índices nuevos por crear en la estructura actual")
            return

        for index_name, table_name, column_name in indexes_to_create:
            try:
                cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})')
                print(f"   ✅ Índice {index_name} creado/verificado")
            except sqlite3.OperationalError as e:
                print(f"   ⚠️ Error con índice {index_name}: {e}")

        self.conn.commit()

    def run_migration(self):
        """Ejecuta el proceso completo de migración"""
        print("🔄 INICIANDO MIGRACIÓN DE DATOS EXISTENTES")
        print("=" * 60)

        # Verificar estado inicial
        status_before = self.check_migration_status()
        print(f"\n📊 ESTADO INICIAL:")
        print(f"   • Total de scrobbles: {status_before['total_scrobbles']:,}")

        print(f"\n🏗️ ESTRUCTURA ACTUAL:")
        print(f"   • Columna artist_mbid: {'✅ Existe' if status_before['has_mbid_columns']['artist'] else '❌ No existe'}")
        print(f"   • Columna album_mbid: {'✅ Existe' if status_before['has_mbid_columns']['album'] else '❌ No existe'}")
        print(f"   • Columna track_mbid: {'✅ Existe' if status_before['has_mbid_columns']['track'] else '❌ No existe'}")

        print(f"\n📚 TABLAS DE DETALLES:")
        print(f"   • Tabla artist_details: {'✅ Existe' if status_before['has_detail_tables']['artist'] else '❌ No existe'}")
        print(f"   • Tabla album_details: {'✅ Existe' if status_before['has_detail_tables']['album'] else '❌ No existe'}")
        print(f"   • Tabla track_details: {'✅ Existe' if status_before['has_detail_tables']['track'] else '❌ No existe'}")

        if any(status_before['has_mbid_columns'].values()):
            print(f"\n📋 MBIDs ACTUALES:")
            if status_before['has_mbid_columns']['artist']:
                print(f"   • Con artist_mbid: {status_before['current_mbids']['artist']:,}")
            if status_before['has_mbid_columns']['album']:
                print(f"   • Con album_mbid: {status_before['current_mbids']['album']:,}")
            if status_before['has_mbid_columns']['track']:
                print(f"   • Con track_mbid: {status_before['current_mbids']['track']:,}")

        if any(status_before['has_detail_tables'].values()):
            print(f"\n💾 MBIDs DISPONIBLES PARA RETROALIMENTAR:")
            if status_before['has_detail_tables']['artist']:
                print(f"   • Artistas: {status_before['available_mbids']['artist']:,}")
            if status_before['has_detail_tables']['album']:
                print(f"   • Álbumes: {status_before['available_mbids']['album']:,}")
            if status_before['has_detail_tables']['track']:
                print(f"   • Tracks: {status_before['available_mbids']['track']:,}")

        if status_before['total_scrobbles'] == 0:
            print(f"\n⚠️ No hay scrobbles en la base de datos")
            return

        # Paso 1: Añadir columnas faltantes
        print(f"\n🔧 PASO 1: Verificando estructura de tabla...")
        self.add_missing_columns()

        # Paso 2: Crear índices
        print(f"\n🗂️ PASO 2: Creando/verificando índices...")
        self.create_missing_indexes()

        # Paso 3: Retroalimentar MBIDs
        print(f"\n🔄 PASO 3: Retroalimentando MBIDs...")

        print(f"   Actualizando artist_mbid...")
        artist_updates = self.backfill_artist_mbids()
        print(f"   ✅ {artist_updates:,} scrobbles actualizados con artist_mbid")

        print(f"   Actualizando album_mbid...")
        album_updates = self.backfill_album_mbids()
        print(f"   ✅ {album_updates:,} scrobbles actualizados con album_mbid")

        print(f"   Actualizando track_mbid...")
        track_updates = self.backfill_track_mbids()
        print(f"   ✅ {track_updates:,} scrobbles actualizados con track_mbid")

        # Verificar estado final
        status_after = self.check_migration_status()

        print(f"\n📈 RESULTADOS DE LA MIGRACIÓN:")

        if any(status_before['has_mbid_columns'].values()):
            if status_before['has_mbid_columns']['artist']:
                print(f"   • Artist MBIDs: {status_before['current_mbids']['artist']:,} → {status_after['current_mbids']['artist']:,} (+{status_after['current_mbids']['artist'] - status_before['current_mbids']['artist']:,})")
            if status_before['has_mbid_columns']['album']:
                print(f"   • Album MBIDs: {status_before['current_mbids']['album']:,} → {status_after['current_mbids']['album']:,} (+{status_after['current_mbids']['album'] - status_before['current_mbids']['album']:,})")
            if status_before['has_mbid_columns']['track']:
                print(f"   • Track MBIDs: {status_before['current_mbids']['track']:,} → {status_after['current_mbids']['track']:,} (+{status_after['current_mbids']['track'] - status_before['current_mbids']['track']:,})")

        total_updates = artist_updates + album_updates + track_updates
        print(f"\n🎉 MIGRACIÓN COMPLETADA")
        print(f"   • Total de actualizaciones: {total_updates:,}")

        if status_after['has_mbid_columns']['artist'] and status_after['total_scrobbles'] > 0:
            print(f"   • Porcentaje de scrobbles con artist_mbid: {(status_after['current_mbids']['artist'] / status_after['total_scrobbles'] * 100):.1f}%")

        if total_updates > 0:
            print(f"\n💡 PRÓXIMO PASO RECOMENDADO:")
            print(f"   • Ejecutar: python update_database_optimized.py --enrich")
            print(f"   • Esto completará el enriquecimiento de entidades restantes")
        else:
            if not any(status_before['has_mbid_columns'].values()) and not any(status_before['has_detail_tables'].values()):
                print(f"\n💡 PRÓXIMO PASO RECOMENDADO:")
                print(f"   • Tu base de datos usa la estructura original")
                print(f"   • Ejecutar: python update_database_optimized.py --all")
                print(f"   • Esto creará la nueva estructura y descargará con MBIDs")
            else:
                print(f"\n⚠️ NOTA:")
                print(f"   • No se encontraron MBIDs para retroalimentar")
                print(f"   • Las columnas/tablas están creadas pero vacías")
                print(f"   • Ejecutar: python update_database_optimized.py --enrich")

    def close(self):
        self.conn.close()


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'lastfm_cache.db'

    try:
        migrator = MigrationHelper(db_path)
        migrator.run_migration()
    except sqlite3.Error as e:
        print(f"❌ Error de base de datos: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'migrator' in locals():
            migrator.close()


if __name__ == '__main__':
    main()

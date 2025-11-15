#!/usr/bin/env python3
"""
Script para añadir índices útiles a bases de datos Last.fm existentes
Mejora significativamente el rendimiento de consultas comunes
"""

import sqlite3
import sys
import time
from typing import List, Tuple

class IndexOptimizer:
    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_existing_indexes(self) -> List[str]:
        """Obtiene lista de índices existentes"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        return [row[0] for row in cursor.fetchall() if row[0] and not row[0].startswith('sqlite_')]

    def get_table_info(self) -> dict:
        """Obtiene información de la estructura de tablas"""
        cursor = self.conn.cursor()

        # Verificar qué tablas existen
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Verificar columnas de la tabla scrobbles
        cursor.execute("PRAGMA table_info(scrobbles)")
        scrobbles_columns = {row[1] for row in cursor.fetchall()}

        # Contar registros
        cursor.execute('SELECT COUNT(*) as total FROM scrobbles')
        total_scrobbles = cursor.fetchone()['total']

        return {
            'tables': existing_tables,
            'scrobbles_columns': scrobbles_columns,
            'total_scrobbles': total_scrobbles
        }

    def create_performance_indexes(self):
        """Crea índices optimizados para rendimiento"""
        print("🚀 CREANDO ÍNDICES DE RENDIMIENTO")
        print("=" * 60)

        table_info = self.get_table_info()
        existing_indexes = self.get_existing_indexes()

        print(f"📊 Base de datos: {table_info['total_scrobbles']:,} scrobbles")
        print(f"🗂️ Índices existentes: {len(existing_indexes)}")

        # Lista de índices a crear con descripción de su utilidad
        indexes_to_create = [
            # ÍNDICES BÁSICOS PARA CONSULTAS COMUNES
            (
                'idx_scrobbles_user_artist',
                'scrobbles',
                '(user, artist)',
                'Consultas de artistas escuchados por usuario (TOP artistas por usuario)'
            ),
            (
                'idx_scrobbles_artist_timestamp',
                'scrobbles',
                '(artist, timestamp)',
                'Análisis temporal de popularidad de artistas'
            ),
            (
                'idx_scrobbles_user_track',
                'scrobbles',
                '(user, track)',
                'Consultas de tracks favoritos por usuario'
            ),
            (
                'idx_scrobbles_user_artist_timestamp',
                'scrobbles',
                '(user, artist, timestamp)',
                'Análisis temporal detallado por usuario y artista'
            ),
            (
                'idx_scrobbles_album_artist',
                'scrobbles',
                '(album, artist)',
                'Búsquedas y agrupaciones por álbum'
            ),
            (
                'idx_scrobbles_track_artist',
                'scrobbles',
                '(track, artist)',
                'Búsquedas de tracks específicos'
            ),
            (
                'idx_scrobbles_timestamp_user',
                'scrobbles',
                '(timestamp, user)',
                'Consultas cronológicas con filtro de usuario'
            ),
            (
                'idx_scrobbles_artist_user',
                'scrobbles',
                '(artist, user)',
                'Análisis de usuarios por artista (quién escucha X artista)'
            )
        ]

        # Añadir índices para MBIDs si las columnas existen
        if 'artist_mbid' in table_info['scrobbles_columns']:
            indexes_to_create.extend([
                (
                    'idx_scrobbles_artist_mbid',
                    'scrobbles',
                    '(artist_mbid)',
                    'Consultas rápidas por MBID de artista'
                ),
                (
                    'idx_scrobbles_user_artist_mbid',
                    'scrobbles',
                    '(user, artist_mbid)',
                    'Análisis por usuario con MBIDs de artista'
                )
            ])

        if 'album_mbid' in table_info['scrobbles_columns']:
            indexes_to_create.append((
                'idx_scrobbles_album_mbid',
                'scrobbles',
                '(album_mbid)',
                'Consultas rápidas por MBID de álbum'
            ))

        if 'track_mbid' in table_info['scrobbles_columns']:
            indexes_to_create.append((
                'idx_scrobbles_track_mbid',
                'scrobbles',
                '(track_mbid)',
                'Consultas rápidas por MBID de track'
            ))

        # Índices para tablas de detalles si existen
        detail_table_indexes = [
            ('artist_details', 'mbid', 'Búsquedas por MBID en detalles de artista'),
            ('artist_details', 'country', 'Filtros por país de artista'),
            ('artist_details', 'artist_type', 'Filtros por tipo de artista'),
            ('album_details', 'mbid', 'Búsquedas por MBID en detalles de álbum'),
            ('album_details', 'album_type', 'Filtros por tipo de álbum'),
            ('album_details', 'release_group_mbid', 'Agrupaciones por release group'),
            ('track_details', 'mbid', 'Búsquedas por MBID en detalles de track'),
            ('artist_genres_detailed', '(artist, source)', 'Consultas de géneros por artista y fuente'),
            ('artist_genres_detailed', 'source', 'Filtros por fuente de género'),
            ('api_cache', 'expires_at', 'Limpieza de cache expirado')
        ]

        for table, column, description in detail_table_indexes:
            if table in table_info['tables']:
                index_name = f'idx_{table}_{column.replace("(", "").replace(")", "").replace(", ", "_")}'
                indexes_to_create.append((index_name, table, column, description))

        print(f"\n🔨 Creando {len(indexes_to_create)} índices...")

        created_count = 0
        skipped_count = 0
        error_count = 0

        for index_name, table_name, columns, description in indexes_to_create:
            if index_name in existing_indexes:
                skipped_count += 1
                continue

            try:
                start_time = time.time()

                sql = f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}{columns}'
                cursor = self.conn.cursor()
                cursor.execute(sql)

                elapsed = time.time() - start_time

                print(f"   ✅ {index_name}")
                print(f"      📝 {description}")
                print(f"      ⏱️ Creado en {elapsed:.2f}s")

                created_count += 1

            except sqlite3.OperationalError as e:
                print(f"   ❌ {index_name}: {e}")
                error_count += 1
            except Exception as e:
                print(f"   ⚠️ {index_name}: Error inesperado - {e}")
                error_count += 1

        self.conn.commit()

        print(f"\n📈 RESUMEN DE CREACIÓN DE ÍNDICES")
        print(f"   ✅ Creados: {created_count}")
        print(f"   ⏭️ Ya existían: {skipped_count}")
        print(f"   ❌ Errores: {error_count}")
        print(f"   🗂️ Total índices ahora: {len(self.get_existing_indexes())}")

    def analyze_query_performance(self):
        """Analiza el rendimiento de consultas comunes"""
        print(f"\n⚡ ANÁLISIS DE RENDIMIENTO")
        print("=" * 60)

        # Consultas de prueba para medir rendimiento
        test_queries = [
            (
                "Top 10 artistas por usuario",
                """
                SELECT artist, COUNT(*) as plays
                FROM scrobbles
                WHERE user = (SELECT user FROM scrobbles LIMIT 1)
                GROUP BY artist
                ORDER BY plays DESC
                LIMIT 10
                """
            ),
            (
                "Actividad por mes",
                """
                SELECT DATE(timestamp, 'unixepoch', 'start of month') as month, COUNT(*) as plays
                FROM scrobbles
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
                """
            ),
            (
                "Álbumes más escuchados",
                """
                SELECT artist, album, COUNT(*) as plays
                FROM scrobbles
                WHERE album IS NOT NULL
                GROUP BY artist, album
                ORDER BY plays DESC
                LIMIT 10
                """
            )
        ]

        for query_name, query_sql in test_queries:
            try:
                start_time = time.time()
                cursor = self.conn.cursor()
                cursor.execute(query_sql)
                results = cursor.fetchall()
                elapsed = time.time() - start_time

                print(f"   🔍 {query_name}")
                print(f"      ⏱️ {elapsed:.3f}s ({len(results)} resultados)")

            except Exception as e:
                print(f"   ❌ {query_name}: {e}")

    def show_index_recommendations(self):
        """Muestra recomendaciones de uso de índices"""
        print(f"\n💡 RECOMENDACIONES DE USO")
        print("=" * 60)

        print(f"""
🚀 CONSULTAS OPTIMIZADAS AHORA DISPONIBLES:

📊 Análisis por Usuario:
   • Top artistas: SELECT artist, COUNT(*) FROM scrobbles WHERE user='X' GROUP BY artist
   • Actividad temporal: WHERE user='X' AND timestamp BETWEEN X AND Y

🎵 Análisis por Artista:
   • Popularidad temporal: WHERE artist='X' ORDER BY timestamp
   • Usuarios que escuchan: WHERE artist='X' GROUP BY user

💿 Análisis de Álbumes:
   • Por artista: WHERE album='X' AND artist='Y'
   • Ranking global: GROUP BY album, artist ORDER BY COUNT(*)

🔍 Búsquedas Específicas:
   • Tracks: WHERE track='X' AND artist='Y'
   • MBIDs: WHERE artist_mbid='X' (si disponible)

⚡ RENDIMIENTO ESPERADO:
   • Consultas básicas: <100ms
   • Agrupaciones complejas: <1s
   • Análisis temporales: <500ms
        """)

    def vacuum_and_analyze(self):
        """Optimiza la base de datos después de crear índices"""
        print(f"\n🧹 OPTIMIZANDO BASE DE DATOS")
        print("=" * 60)

        print(f"   📊 Analizando estadísticas de tablas...")
        start_time = time.time()
        self.conn.execute('ANALYZE')
        elapsed = time.time() - start_time
        print(f"   ✅ ANALYZE completado en {elapsed:.2f}s")

        print(f"   🗜️ Compactando base de datos...")
        start_time = time.time()
        self.conn.execute('VACUUM')
        elapsed = time.time() - start_time
        print(f"   ✅ VACUUM completado en {elapsed:.2f}s")

    def run_optimization(self):
        """Ejecuta la optimización completa"""
        print("🚀 OPTIMIZADOR DE ÍNDICES LAST.FM")
        print("=" * 60)

        table_info = self.get_table_info()
        if table_info['total_scrobbles'] == 0:
            print("⚠️ La base de datos está vacía. Ejecuta primero update_database.py")
            return

        # Crear índices de rendimiento
        self.create_performance_indexes()

        # Analizar rendimiento
        self.analyze_query_performance()

        # Optimizar base de datos
        self.vacuum_and_analyze()

        # Mostrar recomendaciones
        self.show_index_recommendations()

        print(f"\n✨ OPTIMIZACIÓN COMPLETADA")
        print("=" * 60)

    def close(self):
        self.conn.close()


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'lastfm_cache.db'

    print(f"🗃️ Optimizando base de datos: {db_path}")

    try:
        optimizer = IndexOptimizer(db_path)
        optimizer.run_optimization()
    except sqlite3.Error as e:
        print(f"❌ Error de base de datos: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'optimizer' in locals():
            optimizer.close()


if __name__ == '__main__':
    main()

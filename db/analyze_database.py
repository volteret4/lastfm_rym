#!/usr/bin/env python3
"""
Analizador de mejoras en la base de datos optimizada
Muestra estadísticas y comparaciones de los datos enriquecidos
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List

class DatabaseAnalyzer:
    def __init__(self, db_path='lastfm_cache.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def analyze_enrichment_coverage(self) -> Dict:
        """Analiza la cobertura de enriquecimiento de datos"""
        cursor = self.conn.cursor()

        # Verificar qué tablas y columnas existen
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        cursor.execute("PRAGMA table_info(scrobbles)")
        scrobbles_columns = {row[1] for row in cursor.fetchall()}

        # Estadísticas básicas
        cursor.execute('SELECT COUNT(*) as total FROM scrobbles')
        total_scrobbles = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(DISTINCT artist) as total FROM scrobbles')
        total_artists = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(DISTINCT artist, album) as total FROM scrobbles WHERE album IS NOT NULL AND album != ""')
        total_albums = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(DISTINCT artist, track) as total FROM scrobbles')
        total_tracks = cursor.fetchone()['total']

        # Cobertura de MBIDs (solo si las columnas existen)
        scrobbles_with_artist_mbid = 0
        scrobbles_with_album_mbid = 0
        scrobbles_with_track_mbid = 0

        if 'artist_mbid' in scrobbles_columns:
            cursor.execute('SELECT COUNT(*) as with_mbid FROM scrobbles WHERE artist_mbid IS NOT NULL')
            scrobbles_with_artist_mbid = cursor.fetchone()['with_mbid']

        if 'album_mbid' in scrobbles_columns:
            cursor.execute('SELECT COUNT(*) as with_mbid FROM scrobbles WHERE album_mbid IS NOT NULL')
            scrobbles_with_album_mbid = cursor.fetchone()['with_mbid']

        if 'track_mbid' in scrobbles_columns:
            cursor.execute('SELECT COUNT(*) as with_mbid FROM scrobbles WHERE track_mbid IS NOT NULL')
            scrobbles_with_track_mbid = cursor.fetchone()['with_mbid']

        # Entidades enriquecidas (solo si las tablas existen)
        artists_with_details = 0
        albums_with_details = 0
        tracks_with_details = 0
        artists_with_detailed_genres = 0

        if 'artist_details' in existing_tables:
            cursor.execute('SELECT COUNT(*) as enriched FROM artist_details')
            artists_with_details = cursor.fetchone()['enriched']

        if 'album_details' in existing_tables:
            cursor.execute('SELECT COUNT(*) as enriched FROM album_details')
            albums_with_details = cursor.fetchone()['enriched']

        if 'track_details' in existing_tables:
            cursor.execute('SELECT COUNT(*) as enriched FROM track_details')
            tracks_with_details = cursor.fetchone()['enriched']

        if 'artist_genres_detailed' in existing_tables:
            cursor.execute('SELECT COUNT(DISTINCT artist) as with_genres FROM artist_genres_detailed')
            artists_with_detailed_genres = cursor.fetchone()['with_genres']

        return {
            'basic_stats': {
                'total_scrobbles': total_scrobbles,
                'total_artists': total_artists,
                'total_albums': total_albums,
                'total_tracks': total_tracks
            },
            'structure_info': {
                'has_mbid_columns': {
                    'artist_mbid': 'artist_mbid' in scrobbles_columns,
                    'album_mbid': 'album_mbid' in scrobbles_columns,
                    'track_mbid': 'track_mbid' in scrobbles_columns
                },
                'has_detail_tables': {
                    'artist_details': 'artist_details' in existing_tables,
                    'album_details': 'album_details' in existing_tables,
                    'track_details': 'track_details' in existing_tables,
                    'artist_genres_detailed': 'artist_genres_detailed' in existing_tables
                }
            },
            'mbid_coverage': {
                'artist_mbids': {
                    'count': scrobbles_with_artist_mbid,
                    'percentage': (scrobbles_with_artist_mbid / total_scrobbles * 100) if total_scrobbles > 0 else 0
                },
                'album_mbids': {
                    'count': scrobbles_with_album_mbid,
                    'percentage': (scrobbles_with_album_mbid / total_scrobbles * 100) if total_scrobbles > 0 else 0
                },
                'track_mbids': {
                    'count': scrobbles_with_track_mbid,
                    'percentage': (scrobbles_with_track_mbid / total_scrobbles * 100) if total_scrobbles > 0 else 0
                }
            },
            'enrichment_coverage': {
                'artists_detailed': {
                    'count': artists_with_details,
                    'percentage': (artists_with_details / total_artists * 100) if total_artists > 0 else 0
                },
                'albums_detailed': {
                    'count': albums_with_details,
                    'percentage': (albums_with_details / total_albums * 100) if total_albums > 0 else 0
                },
                'tracks_detailed': {
                    'count': tracks_with_details,
                    'percentage': (tracks_with_details / total_tracks * 100) if total_tracks > 0 else 0
                },
                'artists_with_detailed_genres': {
                    'count': artists_with_detailed_genres,
                    'percentage': (artists_with_detailed_genres / total_artists * 100) if total_artists > 0 else 0
                }
            }
        }

    def show_data_quality_improvements(self):
        """Muestra las mejoras en calidad de datos"""
        cursor = self.conn.cursor()

        # Verificar qué tablas existen
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        print("🔍 MEJORAS EN CALIDAD DE DATOS")
        print("=" * 50)

        # Artistas con múltiples fuentes de géneros
        if 'artist_genres_detailed' in existing_tables:
            cursor.execute('''
                SELECT artist, COUNT(DISTINCT source) as sources
                FROM artist_genres_detailed
                GROUP BY artist
                HAVING sources > 1
                LIMIT 10
            ''')

            multi_source_artists = cursor.fetchall()
            if multi_source_artists:
                print(f"\n👥 Artistas con géneros de múltiples fuentes:")
                for row in multi_source_artists:
                    print(f"   • {row['artist']} ({row['sources']} fuentes)")

        # Álbumes con fechas de lanzamiento detalladas
        if 'album_details' in existing_tables:
            cursor.execute('''
                SELECT artist, album, original_release_date, album_type, country
                FROM album_details
                WHERE original_release_date IS NOT NULL
                LIMIT 10
            ''')

            detailed_albums = cursor.fetchall()
            if detailed_albums:
                print(f"\n💿 Álbumes con información detallada:")
                for row in detailed_albums:
                    print(f"   • {row['artist']} - {row['album']}")
                    print(f"     Fecha: {row['original_release_date']}, Tipo: {row['album_type']}, País: {row['country']}")

        # Artistas con información biográfica
        if 'artist_details' in existing_tables:
            cursor.execute('''
                SELECT artist, begin_date, country, artist_type
                FROM artist_details
                WHERE begin_date IS NOT NULL OR country IS NOT NULL
                LIMIT 10
            ''')

            biographical_artists = cursor.fetchall()
            if biographical_artists:
                print(f"\n🎤 Artistas con información biográfica:")
                for row in biographical_artists:
                    info = []
                    if row['begin_date']:
                        info.append(f"Inicio: {row['begin_date']}")
                    if row['country']:
                        info.append(f"País: {row['country']}")
                    if row['artist_type']:
                        info.append(f"Tipo: {row['artist_type']}")

                    print(f"   • {row['artist']} ({', '.join(info)})")

        # Si no hay tablas avanzadas, mostrar datos básicos
        if not any(table in existing_tables for table in ['artist_details', 'album_details', 'artist_genres_detailed']):
            print(f"\n📊 Usando estructura de base de datos original:")

            # Artistas más escuchados
            cursor.execute('''
                SELECT artist, COUNT(*) as play_count
                FROM scrobbles
                GROUP BY artist
                ORDER BY play_count DESC
                LIMIT 10
            ''')

            top_artists = cursor.fetchall()
            if top_artists:
                print(f"\n🎵 Top 10 artistas por reproducciones:")
                for i, row in enumerate(top_artists, 1):
                    print(f"   {i:2d}. {row['artist']} ({row['play_count']:,} reproducciones)")

            # Información de géneros básica (si existe)
            if 'artist_genres' in existing_tables:
                cursor.execute('SELECT COUNT(*) as count FROM artist_genres')
                genre_count = cursor.fetchone()['count']
                print(f"\n🎨 Información de géneros: {genre_count} artistas con géneros")

    def show_api_usage_stats(self):
        """Muestra estadísticas de uso de APIs"""
        cursor = self.conn.cursor()

        # Verificar qué tablas existen
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        print("\n📊 ESTADÍSTICAS DE FUENTES DE DATOS")
        print("=" * 50)

        # Géneros por fuente
        if 'artist_genres_detailed' in existing_tables:
            cursor.execute('''
                SELECT source, COUNT(DISTINCT artist) as artists, COUNT(*) as total_genres
                FROM artist_genres_detailed
                GROUP BY source
            ''')

            genre_sources = cursor.fetchall()
            if genre_sources:
                print(f"\n🎨 Géneros por fuente API:")
                for row in genre_sources:
                    print(f"   • {row['source']}: {row['artists']} artistas, {row['total_genres']} géneros")

        # Cache hits
        if 'api_cache' in existing_tables:
            cursor.execute('SELECT COUNT(*) as cached_requests FROM api_cache')
            cached_requests = cursor.fetchone()['cached_requests']
            print(f"\n💾 Requests cacheadas: {cached_requests}")

        # Estadísticas básicas de la base original
        if 'artist_genres' in existing_tables:
            cursor.execute('SELECT COUNT(*) as artists_with_genres FROM artist_genres')
            artists_with_genres = cursor.fetchone()['artists_with_genres']
            print(f"\n🎭 Artistas con géneros (método original): {artists_with_genres}")

        if 'album_labels' in existing_tables:
            cursor.execute('SELECT COUNT(*) as albums_with_labels FROM album_labels WHERE label IS NOT NULL')
            albums_with_labels = cursor.fetchone()['albums_with_labels']
            print(f"\n🏷️ Álbumes con sellos: {albums_with_labels}")

        if 'album_release_dates' in existing_tables:
            cursor.execute('SELECT COUNT(*) as albums_with_dates FROM album_release_dates WHERE release_year IS NOT NULL')
            albums_with_dates = cursor.fetchone()['albums_with_dates']
            print(f"\n📅 Álbumes con fechas de lanzamiento: {albums_with_dates}")

    def show_missing_data_analysis(self):
        """Analiza qué datos faltan por enriquecer"""
        cursor = self.conn.cursor()

        print("\n❓ ANÁLISIS DE DATOS FALTANTES")
        print("=" * 50)

        # Artistas sin detalles
        cursor.execute('''
            SELECT COUNT(DISTINCT s.artist) as missing
            FROM scrobbles s
            LEFT JOIN artist_details ad ON s.artist = ad.artist
            WHERE ad.artist IS NULL
        ''')
        missing_artist_details = cursor.fetchone()['missing']

        # Álbumes sin detalles
        cursor.execute('''
            SELECT COUNT(DISTINCT s.artist || '|||' || s.album) as missing
            FROM scrobbles s
            LEFT JOIN album_details ald ON s.artist = ald.artist AND s.album = ald.album
            WHERE s.album IS NOT NULL AND s.album != '' AND ald.artist IS NULL
        ''')
        missing_album_details = cursor.fetchone()['missing']

        # Tracks sin detalles
        cursor.execute('''
            SELECT COUNT(DISTINCT s.artist || '|||' || s.track) as missing
            FROM scrobbles s
            LEFT JOIN track_details td ON s.artist = td.artist AND s.track = td.track
            WHERE td.artist IS NULL
        ''')
        missing_track_details = cursor.fetchone()['missing']

        print(f"👥 Artistas sin detalles: {missing_artist_details}")
        print(f"💿 Álbumes sin detalles: {missing_album_details}")
        print(f"🎵 Tracks sin detalles: {missing_track_details}")

    def generate_report(self):
        """Genera un reporte completo"""
        print("🚀 REPORTE DE BASE DE DATOS OPTIMIZADA")
        print("=" * 60)
        print(f"📅 Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Análisis de cobertura
        stats = self.analyze_enrichment_coverage()

        print(f"\n📈 ESTADÍSTICAS BÁSICAS")
        print(f"   • Total de scrobbles: {stats['basic_stats']['total_scrobbles']:,}")
        print(f"   • Artistas únicos: {stats['basic_stats']['total_artists']:,}")
        print(f"   • Álbumes únicos: {stats['basic_stats']['total_albums']:,}")
        print(f"   • Tracks únicos: {stats['basic_stats']['total_tracks']:,}")

        print(f"\n🏗️ ESTRUCTURA DE BASE DE DATOS")
        structure = stats['structure_info']
        print(f"   📋 Columnas MBID en scrobbles:")
        print(f"      • artist_mbid: {'✅' if structure['has_mbid_columns']['artist_mbid'] else '❌'}")
        print(f"      • album_mbid: {'✅' if structure['has_mbid_columns']['album_mbid'] else '❌'}")
        print(f"      • track_mbid: {'✅' if structure['has_mbid_columns']['track_mbid'] else '❌'}")

        print(f"   📚 Tablas de detalles:")
        print(f"      • artist_details: {'✅' if structure['has_detail_tables']['artist_details'] else '❌'}")
        print(f"      • album_details: {'✅' if structure['has_detail_tables']['album_details'] else '❌'}")
        print(f"      • track_details: {'✅' if structure['has_detail_tables']['track_details'] else '❌'}")
        print(f"      • artist_genres_detailed: {'✅' if structure['has_detail_tables']['artist_genres_detailed'] else '❌'}")

        # Solo mostrar estadísticas de MBIDs si las columnas existen
        if any(structure['has_mbid_columns'].values()):
            print(f"\n🆔 COBERTURA DE MBIDs")
            if structure['has_mbid_columns']['artist_mbid']:
                print(f"   • Scrobbles con MBID de artista: {stats['mbid_coverage']['artist_mbids']['count']:,} ({stats['mbid_coverage']['artist_mbids']['percentage']:.1f}%)")
            if structure['has_mbid_columns']['album_mbid']:
                print(f"   • Scrobbles con MBID de álbum: {stats['mbid_coverage']['album_mbids']['count']:,} ({stats['mbid_coverage']['album_mbids']['percentage']:.1f}%)")
            if structure['has_mbid_columns']['track_mbid']:
                print(f"   • Scrobbles con MBID de track: {stats['mbid_coverage']['track_mbids']['count']:,} ({stats['mbid_coverage']['track_mbids']['percentage']:.1f}%)")

        # Solo mostrar estadísticas de enriquecimiento si las tablas existen
        if any(structure['has_detail_tables'].values()):
            print(f"\n✨ ENRIQUECIMIENTO DE DATOS")
            if structure['has_detail_tables']['artist_details']:
                print(f"   • Artistas enriquecidos: {stats['enrichment_coverage']['artists_detailed']['count']:,} ({stats['enrichment_coverage']['artists_detailed']['percentage']:.1f}%)")
            if structure['has_detail_tables']['album_details']:
                print(f"   • Álbumes enriquecidos: {stats['enrichment_coverage']['albums_detailed']['count']:,} ({stats['enrichment_coverage']['albums_detailed']['percentage']:.1f}%)")
            if structure['has_detail_tables']['track_details']:
                print(f"   • Tracks enriquecidos: {stats['enrichment_coverage']['tracks_detailed']['count']:,} ({stats['enrichment_coverage']['tracks_detailed']['percentage']:.1f}%)")
            if structure['has_detail_tables']['artist_genres_detailed']:
                print(f"   • Artistas con géneros detallados: {stats['enrichment_coverage']['artists_with_detailed_genres']['count']:,} ({stats['enrichment_coverage']['artists_with_detailed_genres']['percentage']:.1f}%)")
        else:
            print(f"\n📊 USANDO ESTRUCTURA ORIGINAL")
            print(f"   • Base de datos con estructura clásica de Last.fm")
            print(f"   • Para acceder a funciones avanzadas, ejecutar script optimizado")

        # Mostrar ejemplos de mejoras
        self.show_data_quality_improvements()

        # Estadísticas de APIs
        self.show_api_usage_stats()

        # Análisis de datos faltantes
        self.show_missing_data_analysis()

        print(f"\n💡 PRÓXIMOS PASOS RECOMENDADOS")
        print(f"   • Ejecutar `python update_database_optimized.py --enrich` para completar el enriquecimiento")
        print(f"   • Configurar ejecución automática cada 24h para mantener datos actualizados")
        print(f"   • Considerar añadir más fuentes de datos (Spotify API, etc.)")

    def close(self):
        self.conn.close()


def main():
    try:
        analyzer = DatabaseAnalyzer()
        analyzer.generate_report()
    except sqlite3.Error as e:
        print(f"❌ Error de base de datos: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'analyzer' in locals():
            analyzer.close()


if __name__ == '__main__':
    main()

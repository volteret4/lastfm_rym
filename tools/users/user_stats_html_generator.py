#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Versión FINAL con conteos únicos correctos
Genera estadísticas individuales de usuarios usando clases extendidas
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import argparse

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass

# Importar las clases como propones
from tools.users.user_stats_analyzer import UserStatsAnalyzer
from tools.users.user_stats_database_extended import UserStatsDatabaseExtended
from tools.users.user_stats_html_generator_fixed import UserStatsHTMLGeneratorFixed


def main():
    """Función principal para generar estadísticas de usuarios con conteos únicos CORRECTOS"""
    parser = argparse.ArgumentParser(description='Generador de estadísticas individuales de usuarios de Last.fm')
    parser.add_argument('--years-back', type=int, default=5,
                       help='Número de años hacia atrás para analizar (por defecto: 5)')
    parser.add_argument('--output', type=str, default=None,
                       help='Archivo de salida HTML (por defecto: auto-generado con fecha)')
    args = parser.parse_args()

    # Auto-generar nombre de archivo si no se especifica
    if args.output is None:
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        args.output = f'docs/usuarios_{from_year}-{current_year}.html'

    try:
        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        if not users:
            raise ValueError("LASTFM_USERS no encontrada en las variables de entorno")

        print("🎵 Iniciando análisis de usuarios con conteos únicos CORRECTOS...")

        # ✅ Usar base de datos extendida con funciones adicionales
        database = UserStatsDatabaseExtended()
        analyzer = UserStatsAnalyzer(database, years_back=args.years_back)
        html_generator = UserStatsHTMLGeneratorFixed()

        # Analizar estadísticas para todos los usuarios
        print(f"👤 Analizando {len(users)} usuarios...")
        all_user_stats = {}

        for user in users:
            print(f"  • Procesando {user}...")
            user_stats = analyzer.analyze_user(user, users)
            all_user_stats[user] = user_stats

        # Generar HTML
        print("🎨 Generando HTML con conteos únicos...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Guardar archivo
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Archivo generado: {args.output}")
        print(f"📊 Características FINALES:")
        print(f"  • Géneros diferenciados por proveedor (Last.fm, MusicBrainz, Discogs)")
        print(f"  • Gráficos scatter con leyendas visibles y márgenes adecuados")
        print(f"  • Soporte para géneros de álbumes por separado")
        print(f"  • Sección de sellos completamente funcional")
        print(f"  • Manejo mejorado de datos vacíos")
        print(f"  • ✅ CORREGIDO: Gráficos de géneros se muestran correctamente")
        print(f"  • ✅ RESTAURADO: Funciones completas de scatter charts")
        print(f"  • ✅ RESTAURADO: Funciones completas de evolución")
        print(f"  • ✅ AÑADIDO: Popups interactivos con detalles")
        print(f"  • ✅ NUEVO: Conteos únicos reales del usuario (SOLUCIONADO)")

        # Mostrar resumen con conteos reales
        print("\n📈 Resumen con conteos únicos REALES:")
        for user, stats in all_user_stats.items():
            total_scrobbles = sum(stats['yearly_scrobbles'].values())

            # Mostrar conteos únicos reales
            if 'unique_counts' in stats:
                unique_counts = stats['unique_counts']
                print(f"  • {user}: {total_scrobbles:,} scrobbles")
                print(f"    - ✅ {unique_counts['total_artists']} artistas únicos")
                print(f"    - ✅ {unique_counts['total_albums']} álbumes únicos")
                print(f"    - ✅ {unique_counts['total_tracks']} canciones únicas")

                # ✅ NUEVO: Mostrar conteos de géneros por proveedor
                if 'total_genres' in unique_counts and unique_counts['total_genres']:
                    print(f"    - 🎭 Géneros únicos:")
                    for provider, count in unique_counts['total_genres'].items():
                        print(f"      • {provider}: {count} géneros")
                else:
                    print(f"    - 🎭 Sin géneros disponibles")

                # ✅ NUEVO: Mostrar conteos de sellos
                if 'total_labels' in unique_counts:
                    print(f"    - 🏷️ {unique_counts['total_labels']} sellos discográficos únicos")

                # Años únicos
                total_years = len(stats['yearly_scrobbles'])
                print(f"    - 📅 {total_years} años con actividad")
            else:
                print(f"  • {user}: {total_scrobbles:,} scrobbles (❌ sin conteos únicos)")

        database.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

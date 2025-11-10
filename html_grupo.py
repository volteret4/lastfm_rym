#!/usr/bin/env python3
"""
Last.fm Group Stats Generator
Genera estadísticas grupales con gráficos de coincidencias y evolución temporal
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

from tools.group_stats_analyzer import GroupStatsAnalyzer
from tools.group_stats_database import GroupStatsDatabase
from tools.group_stats_html_generator import GroupStatsHTMLGenerator


def main():
    """Función principal para generar estadísticas grupales"""
    parser = argparse.ArgumentParser(description='Generador de estadísticas grupales de Last.fm')
    parser.add_argument('--years-back', type=int, default=5,
                       help='Número de años hacia atrás para analizar (por defecto: 5)')
    parser.add_argument('--output', type=str, default=None,
                       help='Archivo de salida HTML (por defecto: auto-generado con fecha)')
    parser.add_argument('--mbid-only', action='store_true',
                       help='Solo incluir scrobbles con MBID válidos')
    args = parser.parse_args()

    # Auto-generar nombre de archivo si no se especifica
    if args.output is None:
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        args.output = f'docs/grupo_{from_year}-{current_year}.html'

    try:
        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        if not users:
            raise ValueError("LASTFM_USERS no encontrada en las variables de entorno")

        if len(users) < 2:
            raise ValueError("Se necesitan al menos 2 usuarios para generar estadísticas grupales")

        print("📊 Iniciando análisis grupal...")
        print(f"👥 Usuarios: {', '.join(users)}")
        print(f"📅 Período: {datetime.now().year - args.years_back}-{datetime.now().year}")
        print(f"🎯 MBID Only: {'Sí' if args.mbid_only else 'No'}")

        # Inicializar componentes
        database = GroupStatsDatabase()
        analyzer = GroupStatsAnalyzer(database, years_back=args.years_back, mbid_only=args.mbid_only)
        html_generator = GroupStatsHTMLGenerator()

        # Analizar estadísticas grupales
        print(f"🔍 Analizando estadísticas grupales...")
        group_stats = analyzer.analyze_group_stats(users)

        # Generar HTML
        print("🎨 Generando HTML...")
        html_content = html_generator.generate_html(group_stats, args.years_back)

        # Crear directorio si no existe
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Guardar archivo
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Archivo generado: {args.output}")

        # Mostrar resumen
        print(f"\n📈 Resumen de estadísticas grupales:")
        print(f"  • Usuarios analizados: {group_stats['user_count']}")
        print(f"  • Período: {group_stats['period']}")

        # Estadísticas de usuarios compartidos
        shared_stats = group_stats['shared_charts']
        print(f"  • Artistas compartidos: {len(shared_stats['artists']['data'])}")
        print(f"  • Álbumes compartidos: {len(shared_stats['albums']['data'])}")
        print(f"  • Canciones compartidas: {len(shared_stats['tracks']['data'])}")
        print(f"  • Géneros compartidos: {len(shared_stats['genres']['data'])}")
        print(f"  • Sellos compartidos: {len(shared_stats['labels']['data'])}")

        # Estadísticas de scrobbles
        scrobbles_stats = group_stats['scrobbles_charts']
        print(f"  • Total scrobbles (artistas): {scrobbles_stats['artists']['total']:,}")
        print(f"  • Total scrobbles (global): {scrobbles_stats['all_combined']['total']:,}")

        # Mostrar top 5 artistas más compartidos
        if shared_stats['artists']['data']:
            print(f"\n🎤 Top 5 artistas más compartidos:")
            top_artists = sorted(
                shared_stats['artists']['data'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            for i, (artist, user_count) in enumerate(top_artists, 1):
                users_list = shared_stats['artists']['details'][artist]['shared_users']
                scrobbles = shared_stats['artists']['details'][artist]['total_scrobbles']
                print(f"  {i}. {artist} ({user_count} usuarios, {scrobbles:,} scrobbles)")
                print(f"     Compartido por: {', '.join(users_list)}")

        # Mostrar top 5 por scrobbles totales
        if scrobbles_stats['all_combined']['data']:
            print(f"\n🌟 Top 5 global por scrobbles:")
            top_global = sorted(
                scrobbles_stats['all_combined']['data'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            for i, (item, scrobbles) in enumerate(top_global, 1):
                details = scrobbles_stats['all_combined']['details'][item]
                category = details['category']
                users_list = details['shared_users']
                print(f"  {i}. {item} ({scrobbles:,} scrobbles)")
                print(f"     Categoría: {category} | Usuarios: {', '.join(users_list)}")

        database.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

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

# Agregar el directorio actual al path para importar los módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importar los módulos necesarios
from tools.group.group_stats_analyzer import GroupStatsAnalyzer
from tools.group.group_stats_database import GroupStatsDatabase
from tools.group.group_stats_html_generator import GroupStatsHTMLGenerator
from tools.group.group_data_json_generator import GroupDataJSONGenerator


def main():
    """Función principal para generar estadísticas grupales"""
    parser = argparse.ArgumentParser(description='Generador de estadísticas grupales de Last.fm')
    parser.add_argument('--years-back', type=int, default=5,
                       help='Número de años hacia atrás para analizar (por defecto: 5)')
    parser.add_argument('--output', type=str, default=None,
                       help='Archivo de salida HTML (por defecto: auto-generado con fecha)')
    parser.add_argument('--mbid-only', action='store_true',
                       help='Solo incluir scrobbles con MBID válidos')
    parser.add_argument('--no-json', action='store_true',
                       help='No regenerar archivos JSON (usar existentes)')
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

        print("🎵 Iniciando análisis grupal...")
        print(f"👥 Usuarios: {', '.join(users)}")
        print(f"📅 Período: {datetime.now().year - args.years_back}-{datetime.now().year}")
        print(f"🎯 MBID Only: {'Sí' if args.mbid_only else 'No'}")
        print(f"📊 Regenerar JSON: {'No' if args.no_json else 'Sí'}")

        # Calcular período para la carpeta de datos
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        period_folder = f"{from_year}-{current_year}"

        # Inicializar componentes
        database = GroupStatsDatabase()
        analyzer = GroupStatsAnalyzer(database, years_back=args.years_back, mbid_only=args.mbid_only)
        html_generator = GroupStatsHTMLGenerator()

        # Analizar estadísticas grupales
        print(f"📈 Analizando estadísticas grupales...")
        group_stats = analyzer.analyze_group_stats(users)

        # Generar datos JSON para filtros dinámicos (solo si no está deshabilitado)
        if not args.no_json:
            print(f"📊 Generando datos JSON para filtros dinámicos...")
            json_generator = GroupDataJSONGenerator(database, years_back=args.years_back, mbid_only=args.mbid_only)
            # Crear carpeta específica del período dentro de data
            data_dir = os.path.join(os.path.dirname(args.output), 'data', period_folder)
            json_index = json_generator.generate_all_user_combinations_data(users, data_dir)
        else:
            print(f"⏭️ Saltando generación de JSON (--no-json activado)")

        # Generar HTML con información del período
        print("🎨 Generando HTML...")
        html_content = html_generator.generate_html(group_stats, args.years_back, period_folder)

        # Crear directorio si no existe
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Guardar archivo
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Archivo generado: {args.output}")

        # Mostrar resumen
        print(f"\n📊 Resumen de estadísticas grupales:")
        print(f"  • Usuarios analizados: {group_stats['user_count']}")
        print(f"  • Período: {group_stats['period']}")
        print(f"  • Carpeta de datos: data/{period_folder}")

        # Estadísticas de datos por niveles
        if 'data_by_levels' in group_stats:
            data_levels = group_stats['data_by_levels']
            print(f"  • Niveles de coincidencia disponibles: {len(data_levels)}")
            for level_key, level_data in data_levels.items():
                level_label = get_level_label(level_key, group_stats['user_count'])
                total_items = sum(level_data['counts'].values())
                print(f"    - {level_label}: {total_items} elementos totales")

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
            print(f"\n🎸 Top 5 global por scrobbles:")
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


def get_level_label(level_key: str, total_users: int) -> str:
    """Genera la etiqueta descriptiva para mostrar"""
    if level_key == "total_usuarios":
        return f"Total de usuarios ({total_users})"
    else:
        missing = int(level_key.replace("total_menos_", ""))
        remaining = total_users - missing
        return f"Total menos {missing} ({remaining} usuarios)"


if __name__ == '__main__':
    main()

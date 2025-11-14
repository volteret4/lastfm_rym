#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Versión Corregida con Soporte para Géneros por Proveedor MEJORADA
Genera estadísticas individuales de usuarios con gráficos de coincidencias, evolución y géneros
FIXES:
- Corrige el enlace del botón TEMPORALES para que apunte a index.html#temporal
- Arregla la inicialización de genresData para mostrar los gráficos de géneros
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

# Importar las versiones corregidas desde los outputs
from tools.users.user_stats_analyzer import UserStatsAnalyzer
from tools.users.user_stats_database import UserStatsDatabase
from tools.users.user_stats_html_generator_fixed import UserStatsHTMLGeneratorFixed


def main():
    """Función principal para generar estadísticas de usuarios con sección de géneros CORREGIDA"""
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

        print("🎵 Iniciando análisis de usuarios con sección de géneros CORREGIDA...")

        # Inicializar componentes
        database = UserStatsDatabase()
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
        print("🎨 Generando HTML con géneros corregidos...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Guardar archivo
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Archivo generado: {args.output}")
        print(f"📊 Características CORREGIDAS:")
        print(f"  • Géneros diferenciados por proveedor (Last.fm, MusicBrainz, Discogs)")
        print(f"  • Fallback automático a tabla antigua para Last.fm")
        print(f"  • Gráficos scatter con leyendas visibles y márgenes adecuados")
        print(f"  • Soporte para géneros de álbumes por separado")
        print(f"  • Sección de sellos completamente funcional")
        print(f"  • Manejo mejorado de datos vacíos")
        print(f"  • ✅ NUEVO: Botón TEMPORALES apunta correctamente a index.html#temporal")
        print(f"  • ✅ NUEVO: Gráficos de géneros se muestran correctamente")

        # Mostrar resumen
        print("\n📈 Resumen:")
        for user, stats in all_user_stats.items():
            total_scrobbles = sum(stats['yearly_scrobbles'].values())

            # Mostrar información sobre géneros por proveedor
            genres_info = []
            if 'genres' in stats:
                for provider in ['lastfm', 'musicbrainz', 'discogs']:
                    if provider in stats['genres']:
                        provider_data = stats['genres'][provider]
                        if 'pie_chart' in provider_data and provider_data['pie_chart']['total'] > 0:
                            genres_count = len(provider_data['pie_chart']['data'])
                            genres_info.append(f"{provider}: {genres_count} géneros")

            genres_str = ", ".join(genres_info) if genres_info else "sin géneros"

            # Mostrar información sobre sellos
            labels_info = ""
            if 'labels' in stats and 'pie_chart' in stats['labels']:
                labels_count = len(stats['labels']['pie_chart']['data'])
                labels_info = f", {labels_count} sellos"

            print(f"  • {user}: {total_scrobbles:,} scrobbles ({genres_str}{labels_info})")

        database.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

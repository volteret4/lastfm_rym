#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Versión Corregida con Soporte para Géneros por Proveedor
Genera estadísticas individuales de usuarios con gráficos de coincidencias, evolución y géneros
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

# Importar las versiones modificadas desde los outputs
from tools.users.user_stats_analyzer import UserStatsAnalyzer
from tools.users.user_stats_database import UserStatsDatabase
from tools.users.user_stats_html_generator import UserStatsHTMLGenerator


def main():
    """Función principal para generar estadísticas de usuarios con nueva sección de géneros"""
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

        print("🎵 Iniciando análisis de usuarios con nueva sección de géneros...")

        # Inicializar componentes
        database = UserStatsDatabase()
        analyzer = UserStatsAnalyzer(database, years_back=args.years_back)
        html_generator = UserStatsHTMLGenerator()

        # Analizar estadísticas para todos los usuarios
        print(f"👤 Analizando {len(users)} usuarios...")
        all_user_stats = {}

        for user in users:
            print(f"  • Procesando {user}...")
            user_stats = analyzer.analyze_user(user, users)
            all_user_stats[user] = user_stats

        # Generar HTML
        print("🎨 Generando HTML con nueva sección de géneros...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Guardar archivo
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Archivo generado: {args.output}")
        print(f"📊 Nuevas características incluidas:")
        print(f"  • Vista de Géneros con soporte para múltiples proveedores (Last.fm, MusicBrainz, Discogs)")
        print(f"  • Gráfico circular con top 15 géneros por proveedor")
        print(f"  • 5 gráficos de scatter mostrando evolución temporal de artistas por género")
        print(f"  • Puntos clickeables optimizados para móvil")
        print(f"  • Funcionalidad de usuario con botón y localStorage (como en temporales)")

        # Mostrar resumen
        print("\n📈 Resumen:")
        for user, stats in all_user_stats.items():
            total_scrobbles = sum(stats['yearly_scrobbles'].values())
            print(f"  • {user}: {total_scrobbles:,} scrobbles analizados")

        database.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

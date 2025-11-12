#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Version Corregida
Genera estadÃ­sticas individuales de usuarios con grÃ¡ficos de coincidencias y evoluciÃ³n
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

from tools.users.user_stats_analyzer import UserStatsAnalyzer
from tools.users.user_stats_database import UserStatsDatabase
from tools.users.user_stats_html_generator import UserStatsHTMLGenerator


def main():
    """FunciÃ³n principal para generar estadÃ­sticas de usuarios"""
    parser = argparse.ArgumentParser(description='Generador de estadÃ­sticas individuales de usuarios de Last.fm')
    parser.add_argument('--years-back', type=int, default=5,
                       help='NÃºmero de aÃ±os hacia atrÃ¡s para analizar (por defecto: 5)')
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

        print("ðŸ“Š Iniciando anÃ¡lisis de usuarios...")

        # Inicializar componentes
        database = UserStatsDatabase()
        analyzer = UserStatsAnalyzer(database, years_back=args.years_back)
        html_generator = UserStatsHTMLGenerator()

        # Analizar estadÃ­sticas para todos los usuarios
        print(f"ðŸ‘¤ Analizando {len(users)} usuarios...")
        all_user_stats = {}

        for user in users:
            print(f"  â€¢ Procesando {user}...")
            user_stats = analyzer.analyze_user(user, users)
            all_user_stats[user] = user_stats

        # Generar HTML
        print("ðŸŽ¨ Generando HTML...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Guardar archivo
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"âœ… Archivo generado: {args.output}")
        print(f"ðŸ“Š OptimizaciÃ³n aplicada:")
        print(f"  â€¢ AnÃ¡lisis: Datos completos procesados en Python")
        print(f"  â€¢ HTML: Solo datos necesarios para grÃ¡ficos")
        print(f"  â€¢ Resultado: Archivo HTML ligero con funcionalidad completa")

        # Mostrar resumen
        print("\nðŸ“ˆ Resumen:")
        for user, stats in all_user_stats.items():
            total_scrobbles = sum(stats['yearly_scrobbles'].values())
            print(f"  â€¢ {user}: {total_scrobbles:,} scrobbles analizados")

        database.close()

    except Exception as e:
        print(f"âŒ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

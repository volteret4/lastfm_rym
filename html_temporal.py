#!/usr/bin/env python3
"""
Last.fm Temporal Stats Generator
Generador de estadísticas temporales de Last.fm (semanales, mensuales, anuales)
"""

import os
import sys
import argparse
import shutil
from datetime import datetime, timedelta
from typing import List, Tuple, Dict

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass

from tools.temp.temp_database import Database
from tools.temp.temp_analyzer import StatsAnalyzer
from tools.temp.temp_html_generator import HTMLGenerator


class PeriodCalculator:
    @staticmethod
    def get_week_period(week_offset: int = 0) -> Tuple[int, int, str]:
        """
        Calcula el período de una semana específica

        Args:
            week_offset: 0 = esta semana, 1 = semana pasada, etc.

        Returns:
            Tuple con (from_timestamp, to_timestamp, period_label)
        """
        now = datetime.now()
        days_since_monday = now.weekday()
        monday_this_week = now - timedelta(days=days_since_monday)

        target_monday = monday_this_week - timedelta(weeks=week_offset)
        target_sunday = target_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

        week_names = [
            "Esta semana",
            "Semana pasada",
            "Hace dos semanas",
            "Hace tres semanas"
        ]

        period_label = week_names[week_offset] if week_offset < len(week_names) else f"Hace {week_offset} semanas"

        return int(target_monday.timestamp()), int(target_sunday.timestamp()), period_label

    @staticmethod
    def get_month_period(month: int, year: int) -> Tuple[int, int, str]:
        """
        Calcula el período de un mes específico

        Args:
            month: Mes (1-12)
            year: Año

        Returns:
            Tuple con (from_timestamp, to_timestamp, period_label)
        """
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)

        month_names = [
            '', 'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]

        period_label = f"{month_names[month]} {year}"

        return int(start_date.timestamp()), int(end_date.timestamp()), period_label

    @staticmethod
    def get_year_period(year: int) -> Tuple[int, int, str]:
        """
        Calcula el período de un año específico

        Args:
            year: Año

        Returns:
            Tuple con (from_timestamp, to_timestamp, period_label)
        """
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)

        period_label = f"Año {year}"

        return int(start_date.timestamp()), int(end_date.timestamp()), period_label


def rotate_weekly_files():
    """Rota los archivos semanales: actual → pasada → hace-dos → hace-tres → eliminar"""
    filenames = [
        'esta-semana.html',
        'semana-pasada.html',
        'hace-dos-semanas.html',
        'hace-tres-semanas.html'
    ]

    docs_dir = 'docs'
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)

    file_paths = [os.path.join(docs_dir, f) for f in filenames]

    print("🔄 Rotando archivos semanales...")

    # Eliminar el más antiguo (hace-tres-semanas)
    if os.path.exists(file_paths[3]):
        os.remove(file_paths[3])
        print(f"   ❌ Eliminado: {filenames[3]}")

    # Rotar los demás hacia atrás
    for i in range(2, -1, -1):  # [2, 1, 0]
        if os.path.exists(file_paths[i]):
            shutil.move(file_paths[i], file_paths[i + 1])
            print(f"   📝 {filenames[i]} → {filenames[i + 1]}")


def generate_stats(period_type: str, users: List[str], **kwargs) -> Tuple[Dict, str, str]:
    """
    Genera estadísticas para el período especificado

    Args:
        period_type: 'weekly', 'monthly', o 'yearly'
        users: Lista de usuarios
        **kwargs: Argumentos específicos del período

    Returns:
        Tuple con (stats, period_label, filename)
    """
    # Calcular período
    if period_type == 'weekly':
        week_offset = kwargs.get('week_offset', 0)
        from_timestamp, to_timestamp, period_label = PeriodCalculator.get_week_period(week_offset)
        filename = 'esta-semana.html'

    elif period_type == 'monthly':
        month = kwargs.get('month', datetime.now().month)
        year = kwargs.get('year', datetime.now().year)
        from_timestamp, to_timestamp, period_label = PeriodCalculator.get_month_period(month, year)

        month_names = ['', 'january', 'february', 'march', 'april', 'may', 'june',
                       'july', 'august', 'september', 'october', 'november', 'december']
        filename = f"monthly_{month_names[month]}_{year}.html"

    elif period_type == 'yearly':
        year = kwargs.get('year', datetime.now().year)
        from_timestamp, to_timestamp, period_label = PeriodCalculator.get_year_period(year)
        filename = f"yearly_{year}.html"

    else:
        raise ValueError(f"Tipo de período no válido: {period_type}")

    print(f"\n📅 {period_label}")
    print(f"   Desde: {datetime.fromtimestamp(from_timestamp).strftime('%Y-%m-%d %H:%M')}")
    print(f"   Hasta: {datetime.fromtimestamp(to_timestamp).strftime('%Y-%m-%d %H:%M')}")

    # Conectar a base de datos y analizar
    db = Database()
    analyzer = StatsAnalyzer(db)

    # Incluir novedades para todos los períodos (no solo semanales)
    include_novelties = True
    print(f"   🔍 Incluir novedades: {include_novelties} (período: {period_type})")

    stats = analyzer.analyze_period(users, from_timestamp, to_timestamp, include_novelties)

    if not stats:
        print("❌ No se pudieron generar estadísticas")
        db.close()
        return {}, period_label, filename

    # Añadir metadatos
    stats.update({
        'period_label': period_label,
        'from_date': datetime.fromtimestamp(from_timestamp).strftime('%Y-%m-%d'),
        'to_date': datetime.fromtimestamp(to_timestamp).strftime('%Y-%m-%d'),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    })

    db.close()
    return stats, period_label, filename


def main():
    parser = argparse.ArgumentParser(description='Genera estadísticas temporales de Last.fm')
    parser.add_argument('period', choices=['weekly', 'monthly', 'yearly'],
                        help='Tipo de período a generar')

    # Argumentos para semanales
    parser.add_argument('--week-offset', type=int, default=0,
                        help='Semanas hacia atrás (0=esta semana, 1=semana pasada, etc.)')

    # Argumentos para mensuales
    parser.add_argument('--month', type=int, default=datetime.now().month,
                        help='Mes (1-12, por defecto: mes actual)')
    parser.add_argument('--year', type=int, default=datetime.now().year,
                        help='Año (por defecto: año actual)')

    # Argumentos para anuales
    parser.add_argument('--years-ago', type=int, default=0,
                        help='Años hacia atrás (0=este año, 1=año pasado, etc.)')

    args = parser.parse_args()

    # Calcular año final si se usa years-ago
    if args.years_ago > 0:
        args.year = datetime.now().year - args.years_ago

    print("=" * 60)
    print(f"GENERADOR DE ESTADÍSTICAS {args.period.upper()}")
    print("=" * 60)

    # Cargar usuarios del .env
    users_env = os.getenv('LASTFM_USERS', '')
    if not users_env:
        print("❌ Error: Variable LASTFM_USERS no encontrada")
        print("💡 Añade LASTFM_USERS=usuario1,usuario2,usuario3 a tu .env")
        sys.exit(1)

    users = [u.strip() for u in users_env.split(',') if u.strip()]
    if not users:
        print("❌ Error: No se encontraron usuarios válidos en LASTFM_USERS")
        sys.exit(1)

    print(f"👥 Usuarios: {', '.join(users)}")

    # Verificar base de datos
    db_path = 'db/lastfm_cache.db'
    if not os.path.exists(db_path):
        print(f"❌ Error: Base de datos no encontrada en {db_path}")
        sys.exit(1)

    print(f"✅ Base de datos encontrada: {db_path}")

    # Rotar archivos semanales si es necesario
    if args.period == 'weekly' and args.week_offset == 0:
        rotate_weekly_files()

    # Generar estadísticas
    print(f"\n📊 Generando estadísticas...")

    period_kwargs = {}
    if args.period == 'weekly':
        period_kwargs['week_offset'] = args.week_offset
    elif args.period == 'monthly':
        period_kwargs['month'] = args.month
        period_kwargs['year'] = args.year
    elif args.period == 'yearly':
        period_kwargs['year'] = args.year

    stats, period_label, filename = generate_stats(args.period, users, **period_kwargs)

    if not stats:
        print("❌ No se pudieron generar estadísticas")
        sys.exit(1)

    # Crear HTML
    print("🎨 Generando HTML...")
    html_content = HTMLGenerator.create_html(stats, users, args.period.replace('ly', 'al'))

    # Crear directorio si no existe
    docs_dir = 'docs'
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)

    # Guardar archivo
    output_file = os.path.join(docs_dir, filename)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Archivo generado: {output_file}")
    print(f"📅 Período: {stats['period_label']}")
    print(f"📈 Total scrobbles: {stats['total_scrobbles']:,}")
    print(f"🎵 Artistas únicos: {len(stats.get('artists', []))}")
    print(f"🎶 Canciones únicas: {len(stats.get('tracks', []))}")
    print(f"💿 Álbumes únicos: {len(stats.get('albums', []))}")
    print(f"🎯 Géneros únicos: {len(stats.get('genres', []))}")
    print(f"🏷️ Sellos únicos: {len(stats.get('labels', []))}")
    print(f"📆 Años únicos: {len(stats.get('years', []))}")

    # Mostrar novedades si están disponibles
    if 'novelties' in stats:
        novelties = stats['novelties']
        print(f"\n🆕 NOVEDADES:")
        print(f"   Nuevos artistas: {len(novelties['nuevos']['artists'])}")
        print(f"   Nuevos álbumes: {len(novelties['nuevos']['albums'])}")
        print(f"   Nuevas canciones: {len(novelties['nuevos']['tracks'])}")
        print(f"   Artistas compartidos: {len(novelties['nuevos_compartidos']['artists'])}")
        print(f"   Álbumes compartidos: {len(novelties['nuevos_compartidos']['albums'])}")
        print(f"   Canciones compartidas: {len(novelties['nuevos_compartidos']['tracks'])}")

    print("\n" + "=" * 60)
    print("✅ PROCESO COMPLETADO")
    print("=" * 60)


if __name__ == '__main__':
    main()

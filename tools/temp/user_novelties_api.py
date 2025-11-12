#!/usr/bin/env python3
"""
User Novelties API
API para calcular novedades de usuario específico dinámicamente
"""

import sys
import json
from datetime import datetime
from typing import List
from tools.temp.temp_database import Database
from tools.temp.temp_analyzer import StatsAnalyzer

def calculate_user_novelties_for_period(user: str, users: List[str], period_type: str, **kwargs) -> dict:
    """
    Calcula novedades para un usuario en un período específico

    Args:
        user: Nombre del usuario
        users: Lista de todos los usuarios
        period_type: 'weekly', 'monthly', o 'yearly'
        **kwargs: Parámetros del período

    Returns:
        Dict con novedades del usuario
    """
    # Importar PeriodCalculator para calcular timestamps
    from html_temporal import PeriodCalculator

    # Calcular período
    if period_type == 'weekly':
        week_offset = kwargs.get('week_offset', 0)
        from_timestamp, to_timestamp, _ = PeriodCalculator.get_week_period(week_offset)

    elif period_type == 'monthly':
        month = kwargs.get('month', datetime.now().month)
        year = kwargs.get('year', datetime.now().year)
        from_timestamp, to_timestamp, _ = PeriodCalculator.get_month_period(month, year)

    elif period_type == 'yearly':
        year = kwargs.get('year', datetime.now().year)
        from_timestamp, to_timestamp, _ = PeriodCalculator.get_year_period(year)

    else:
        return {'artists': [], 'albums': [], 'tracks': []}

    # Conectar a base de datos y calcular
    db = Database()
    analyzer = StatsAnalyzer(db)

    novelties = analyzer.calculate_user_novelties(users, user, from_timestamp, to_timestamp)

    db.close()
    return novelties

def main():
    """
    Función principal para uso por línea de comandos o como API
    Acepta JSON en stdin y devuelve JSON en stdout
    """
    if len(sys.argv) > 1:
        # Modo línea de comandos
        user = sys.argv[1]
        users_str = sys.argv[2] if len(sys.argv) > 2 else ""
        period_type = sys.argv[3] if len(sys.argv) > 3 else 'weekly'

        # Parse users list
        users = [u.strip() for u in users_str.split(',') if u.strip()] if users_str else [user]

        kwargs = {}
        if len(sys.argv) > 4:
            # Parámetros adicionales como JSON
            try:
                kwargs = json.loads(sys.argv[4])
            except:
                pass

        result = calculate_user_novelties_for_period(user, users, period_type, **kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        # Modo API - lee JSON del stdin
        try:
            input_data = json.loads(sys.stdin.read())
            user = input_data.get('user')
            users = input_data.get('users', [user] if user else [])
            period_type = input_data.get('period_type', 'weekly')
            kwargs = input_data.get('params', {})

            if not user:
                print(json.dumps({'error': 'Usuario requerido'}, ensure_ascii=False))
                sys.exit(1)

            result = calculate_user_novelties_for_period(user, users, period_type, **kwargs)
            print(json.dumps(result, ensure_ascii=False))

        except Exception as e:
            print(json.dumps({'error': str(e)}, ensure_ascii=False))
            sys.exit(1)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
GroupStatsAnalyzer - Analizador para estadísticas grupales
"""

from datetime import datetime
from typing import List, Dict


class GroupStatsAnalyzer:
    """Clase para analizar estadísticas grupales del grupo de usuarios"""

    def __init__(self, database, years_back: int = 5, mbid_only: bool = False):
        self.database = database
        self.years_back = years_back
        self.mbid_only = mbid_only
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def analyze_group_stats(self, users: List[str]) -> Dict:
        """Analiza completamente las estadísticas grupales y devuelve todos los datos"""
        print(f"    • Obteniendo totales reales...")
        total_counts = self.database.get_total_shared_counts(users, self.from_year, self.to_year, self.mbid_only)

        print(f"    • Analizando datos por niveles de usuarios...")
        # Importar aquí para evitar dependencias circulares
        from tools.group_data_analyzer import GroupDataAnalyzer
        data_analyzer = GroupDataAnalyzer(self.database, self.years_back, self.mbid_only)
        data_stats = data_analyzer.analyze_data_by_user_levels(users)

        print(f"    • Analizando top por usuarios compartidos...")
        shared_stats = self._analyze_shared_stats(users)

        print(f"    • Analizando top por scrobbles totales...")
        scrobbles_stats = self._analyze_scrobbles_stats(users)

        print(f"    • Analizando evolución temporal...")
        evolution_stats = self._analyze_evolution_stats(users)

        return {
            'period': f"{self.from_year}-{self.to_year}",
            'users': users,
            'user_count': len(users),
            'total_counts': total_counts,
            'data_by_levels': data_stats['data_by_levels'],
            'shared_charts': shared_stats,
            'scrobbles_charts': scrobbles_stats,
            'evolution': evolution_stats,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _analyze_shared_stats(self, users: List[str]) -> Dict:
        """
        Analiza estadísticas basadas en usuarios compartidos
        Top 15 de cada categoría ordenado por:
        1. Número de usuarios que lo comparten (prioridad)
        2. Total de scrobbles (desempate)
        """
        # Top 15 artistas por usuarios compartidos
        top_artists = self.database.get_top_artists_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 álbumes por usuarios compartidos
        top_albums = self.database.get_top_albums_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 canciones por usuarios compartidos
        top_tracks = self.database.get_top_tracks_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 géneros por usuarios compartidos
        top_genres = self.database.get_top_genres_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 sellos por usuarios compartidos
        top_labels = self.database.get_top_labels_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 décadas de lanzamiento por usuarios compartidos
        top_release_decades = self.database.get_top_release_decades_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 años individuales de lanzamiento por usuarios compartidos
        top_release_years = self.database.get_top_individual_years_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        return {
            'artists': self._prepare_pie_chart_data('Artistas (Por Usuarios Compartidos)', top_artists, 'shared'),
            'albums': self._prepare_pie_chart_data('Álbumes (Por Usuarios Compartidos)', top_albums, 'shared'),
            'tracks': self._prepare_pie_chart_data('Canciones (Por Usuarios Compartidos)', top_tracks, 'shared'),
            'genres': self._prepare_pie_chart_data('Géneros (Por Usuarios Compartidos)', top_genres, 'shared'),
            'labels': self._prepare_pie_chart_data('Sellos (Por Usuarios Compartidos)', top_labels, 'shared'),
            'release_decades': self._prepare_pie_chart_data('Décadas de Lanzamiento (Por Usuarios Compartidos)', top_release_decades, 'shared'),
            'release_years': self._prepare_pie_chart_data('Años de Lanzamiento (Por Usuarios Compartidos)', top_release_years, 'shared')
        }

    def _analyze_scrobbles_stats(self, users: List[str]) -> Dict:
        """
        Analiza estadísticas basadas solo en scrobbles totales
        Top 15 de cada categoría ordenado solo por total de scrobbles
        """
        # Obtener todos los tops por scrobbles
        scrobbles_data = self.database.get_top_by_total_scrobbles(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # También obtener años individuales
        top_individual_years = self.database.get_top_release_years_by_scrobbles_only(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        return {
            'artists': self._prepare_pie_chart_data('Artistas (Por Scrobbles)', scrobbles_data['artists'], 'scrobbles'),
            'albums': self._prepare_pie_chart_data('Álbumes (Por Scrobbles)', scrobbles_data['albums'], 'scrobbles'),
            'tracks': self._prepare_pie_chart_data('Canciones (Por Scrobbles)', scrobbles_data['tracks'], 'scrobbles'),
            'genres': self._prepare_pie_chart_data('Géneros (Por Scrobbles)', scrobbles_data['genres'], 'scrobbles'),
            'labels': self._prepare_pie_chart_data('Sellos (Por Scrobbles)', scrobbles_data['labels'], 'scrobbles'),
            'release_decades': self._prepare_pie_chart_data('Décadas de Lanzamiento (Por Scrobbles)', scrobbles_data['release_years'], 'scrobbles'),
            'release_years': self._prepare_pie_chart_data('Años de Lanzamiento (Por Scrobbles)', top_individual_years, 'scrobbles'),
            'all_combined': self._prepare_combined_chart_data(scrobbles_data)
        }

    def _analyze_evolution_stats(self, users: List[str]) -> Dict:
        """Analiza evolución temporal para gráficos lineales"""
        evolution_data = self.database.get_evolution_data(
            users, self.from_year, self.to_year, self.mbid_only
        )

        return {
            'artists': self._prepare_line_chart_data('Top 15 Artistas por Año', evolution_data['artists'], evolution_data['years']),
            'albums': self._prepare_line_chart_data('Top 15 Álbumes por Año', evolution_data['albums'], evolution_data['years']),
            'tracks': self._prepare_line_chart_data('Top 15 Canciones por Año', evolution_data['tracks'], evolution_data['years']),
            'genres': self._prepare_line_chart_data('Top 15 Géneros por Año', evolution_data['genres'], evolution_data['years']),
            'labels': self._prepare_line_chart_data('Top 15 Sellos por Año', evolution_data['labels'], evolution_data['years']),
            'release_years': self._prepare_line_chart_data('Top 15 Años de Lanzamiento por Año', evolution_data['release_years'], evolution_data['years'])
        }

    def _prepare_pie_chart_data(self, title: str, raw_data: List[Dict], chart_type: str) -> Dict:
        """Prepara datos para gráficos circulares"""
        if not raw_data:
            return {
                'title': title,
                'data': {},
                'total': 0,
                'details': {},
                'type': chart_type
            }

        # Siempre usar scrobbles para el tamaño de las porciones
        chart_data = {item['name']: item['total_scrobbles'] for item in raw_data}
        total = sum(item['total_scrobbles'] for item in raw_data)

        # Detalles para popups con user_plays incluido
        details = {}
        for item in raw_data:
            details[item['name']] = {
                'user_count': item['user_count'],
                'total_scrobbles': item['total_scrobbles'],
                'shared_users': item.get('shared_users', []),
                'user_plays': item.get('user_plays', {}),
                'artist': item.get('artist', ''),
                'album': item.get('album', ''),
                'track': item.get('track', '')
            }

        return {
            'title': title,
            'data': chart_data,
            'total': total,
            'details': details,
            'type': chart_type
        }

    def _prepare_combined_chart_data(self, scrobbles_data: Dict) -> Dict:
        """Prepara datos combinados para el gráfico de "Todo por Scrobbles"""
        all_items = []

        # Combinar todos los tops con prefijo de categoría
        for category, items in scrobbles_data.items():
            for item in items[:5]:  # Solo top 5 de cada categoría para evitar saturación
                prefixed_name = f"{category.capitalize()}: {item['name']}"
                all_items.append({
                    'name': prefixed_name,
                    'original_name': item['name'],
                    'category': category,
                    'user_count': item['user_count'],
                    'total_scrobbles': item['total_scrobbles'],
                    'shared_users': item.get('shared_users', [])
                })

        # Ordenar por scrobbles y tomar top 15
        all_items.sort(key=lambda x: x['total_scrobbles'], reverse=True)
        top_combined = all_items[:15]

        chart_data = {item['name']: item['total_scrobbles'] for item in top_combined}
        total = sum(item['total_scrobbles'] for item in top_combined)

        details = {}
        for item in top_combined:
            details[item['name']] = {
                'original_name': item['original_name'],
                'category': item['category'],
                'user_count': item['user_count'],
                'total_scrobbles': item['total_scrobbles'],
                'shared_users': item['shared_users']
            }

        return {
            'title': 'Top 15 Global por Scrobbles',
            'data': chart_data,
            'total': total,
            'details': details,
            'type': 'combined'
        }

    def _prepare_line_chart_data(self, title: str, evolution_data: Dict, years: List[int]) -> Dict:
        """Prepara datos para gráficos lineales de evolución"""
        if not evolution_data:
            return {
                'title': title,
                'data': {},
                'years': years,
                'names': []
            }

        return {
            'title': title,
            'data': evolution_data,
            'years': years,
            'names': list(evolution_data.keys())
        }

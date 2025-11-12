#!/usr/bin/env python3
"""
GroupDataJSONGenerator - Generador de datos JSON para filtros dinámicos por usuarios
Crea archivos JSON con datos pre-calculados para diferentes combinaciones de usuarios
"""

import os
import json
from datetime import datetime
from typing import List, Dict
from itertools import combinations


class GroupDataJSONGenerator:
    """Generador de datos JSON para filtros dinámicos de usuarios"""

    def __init__(self, database, years_back: int = 5, mbid_only: bool = False):
        self.database = database
        self.years_back = years_back
        self.mbid_only = mbid_only
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def generate_all_user_combinations_data(self, users: List[str], output_dir: str = "docs/data") -> Dict:
        """Genera datos JSON para todas las combinaciones relevantes de usuarios"""
        print("    • Generando datos JSON para filtros de usuarios...")

        # Crear directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)

        # Mapeo de archivos generados
        generated_files = {
            'shared_charts': {},
            'scrobbles_charts': {},
            'evolution': {}
        }

        # Generar para todas las combinaciones de 2 o más usuarios
        for r in range(2, len(users) + 1):
            for user_combo in combinations(users, r):
                user_list = list(user_combo)
                user_key = "_".join(sorted(user_list))

                print(f"      • Procesando combinación: {', '.join(user_list)}")

                # Datos por usuarios compartidos
                shared_data = self._generate_shared_charts_data(user_list)
                shared_file = f"{output_dir}/shared_{user_key}.json"
                with open(shared_file, 'w', encoding='utf-8') as f:
                    json.dump(shared_data, f, indent=2, ensure_ascii=False)
                generated_files['shared_charts'][user_key] = shared_file

                # Datos por scrobbles totales
                scrobbles_data = self._generate_scrobbles_charts_data(user_list)
                scrobbles_file = f"{output_dir}/scrobbles_{user_key}.json"
                with open(scrobbles_file, 'w', encoding='utf-8') as f:
                    json.dump(scrobbles_data, f, indent=2, ensure_ascii=False)
                generated_files['scrobbles_charts'][user_key] = scrobbles_file

                # Datos de evolución temporal
                evolution_data = self._generate_evolution_data(user_list)
                evolution_file = f"{output_dir}/evolution_{user_key}.json"
                with open(evolution_file, 'w', encoding='utf-8') as f:
                    json.dump(evolution_data, f, indent=2, ensure_ascii=False)
                generated_files['evolution'][user_key] = evolution_file

        # Generar archivo de índice con metadatos
        index_data = {
            'users': users,
            'period': f"{self.from_year}-{self.to_year}",
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'files': generated_files,
            'user_combinations': [
                {
                    'users': list(combo),
                    'key': "_".join(sorted(combo))
                }
                for r in range(2, len(users) + 1)
                for combo in combinations(users, r)
            ]
        }

        index_file = f"{output_dir}/index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

        print(f"      • Archivos JSON generados en: {output_dir}")
        print(f"      • Combinaciones procesadas: {len(index_data['user_combinations'])}")

        return index_data

    def _generate_shared_charts_data(self, users: List[str]) -> Dict:
        """Genera datos para gráficos por usuarios compartidos"""
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
            'release_years': self._prepare_pie_chart_data('Años de Lanzamiento (Por Usuarios Compartidos)', top_release_years, 'shared')
        }

    def _generate_scrobbles_charts_data(self, users: List[str]) -> Dict:
        """Genera datos para gráficos por scrobbles totales"""
        # Obtener todos los tops por scrobbles
        scrobbles_data = self.database.get_top_by_total_scrobbles(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # También obtener años individuales
        top_individual_years = self.database.get_top_individual_release_years_by_scrobbles_only(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        return {
            'artists': self._prepare_pie_chart_data('Artistas (Por Scrobbles)', scrobbles_data['artists'], 'scrobbles'),
            'albums': self._prepare_pie_chart_data('Álbumes (Por Scrobbles)', scrobbles_data['albums'], 'scrobbles'),
            'tracks': self._prepare_pie_chart_data('Canciones (Por Scrobbles)', scrobbles_data['tracks'], 'scrobbles'),
            'genres': self._prepare_pie_chart_data('Géneros (Por Scrobbles)', scrobbles_data['genres'], 'scrobbles'),
            'labels': self._prepare_pie_chart_data('Sellos (Por Scrobbles)', scrobbles_data['labels'], 'scrobbles'),
            'release_years': self._prepare_pie_chart_data('Años de Lanzamiento (Por Scrobbles)', top_individual_years, 'scrobbles'),
            'all_combined': self._prepare_combined_chart_data(scrobbles_data)
        }

    def _generate_evolution_data(self, users: List[str]) -> Dict:
        """Genera datos para gráficos de evolución temporal"""
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

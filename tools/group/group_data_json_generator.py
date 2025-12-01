#!/usr/bin/env python3
"""
GroupDataJSONGenerator - Generador de datos JSON para filtros dinÃ¡micos por usuarios
Crea archivos JSON con datos pre-calculados para diferentes combinaciones de usuarios
"""

import os
import json
from datetime import datetime
from typing import List, Dict
from itertools import combinations


class GroupDataJSONGenerator:
    """Generador de datos JSON para filtros dinÃ¡micos de usuarios"""

    def __init__(self, database, years_back: int = 5, mbid_only: bool = False):
        self.database = database
        self.years_back = years_back
        self.mbid_only = mbid_only
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def generate_all_user_combinations_data(self, users: List[str], output_dir: str = "docs/data") -> Dict:
        """Genera un archivo JSON consolidado con todos los datos por usuario"""
        print("    • Generando archivo JSON consolidado para filtros dinámicos...")
        print(f"    • Directorio de salida: {output_dir}")

        # Crear directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)

        # Generar datos consolidados
        print("      • Recopilando datos por usuario...")
        consolidated_data = self._generate_consolidated_user_data(users)

        # Guardar archivo consolidado
        consolidated_file = f"{output_dir}/consolidated_data.json"
        print("      • Guardando archivo consolidado...")
        with open(consolidated_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated_data, f, indent=2, ensure_ascii=False)

        file_size_mb = os.path.getsize(consolidated_file) / (1024*1024)

        # Generar archivo de índice con metadatos
        index_data = {
            'users': users,
            'period': f"{self.from_year}-{self.to_year}",
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'consolidated_file': 'consolidated_data.json',
            'total_users': len(users),
            'file_size_mb': round(file_size_mb, 2),
            'data_structure': {
                'raw_data': 'Datos crudos por usuario para cada categoría',
                'evolution_data': 'Datos de evolución temporal por año',
                'categories': ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']
            }
        }

        index_file = f"{output_dir}/index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

        print(f"      • Archivo consolidado generado: {consolidated_file}")
        print(f"      • Tamaño del archivo: {file_size_mb:.2f} MB")
        print(f"      • Usuarios incluidos: {len(users)}")
        print(f"      • En lugar de {sum(1 for r in range(2, len(users) + 1) for _ in combinations(users, r))} archivos separados")

        return index_data

    def _generate_consolidated_user_data(self, users: List[str]) -> Dict:
        """Genera datos consolidados con información por usuario para filtrado dinámico"""

        print("        • Obteniendo datos crudos por usuario...")

        # Estructura consolidada
        consolidated = {
            'users': users,
            'period': f"{self.from_year}-{self.to_year}",
            'raw_data': {},
            'evolution': {},
            'evolution_scatter': {}
        }

        # Obtener datos crudos para cada usuario individual
        for user in users:
            print(f"          • Procesando datos de {user}...")
            user_data = self._get_user_raw_data([user])
            consolidated['raw_data'][user] = user_data

        # Obtener datos de evolución para todos los usuarios
        print("        • Procesando evolución temporal...")
        all_users_evolution = self.database.get_evolution_data(
            users, self.from_year, self.to_year, self.mbid_only
        )

        # Estructurar evolución por usuario
        for category in ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']:
            consolidated['evolution'][category] = {}
            for item_name, year_data in all_users_evolution[category].items():
                item_evolution = {}
                for year, data in year_data.items():
                    item_evolution[year] = {
                        'total': data['total'],
                        'users': data['users']  # Dict con scrobbles por usuario
                    }
                consolidated['evolution'][category][item_name] = item_evolution

        # Obtener datos scatter de evolución
        print("        • Procesando evolución scatter...")
        scatter_data = self.database.get_evolution_scatter_data(
            users, self.from_year, self.to_year, self.mbid_only
        )
        consolidated['evolution_scatter'] = scatter_data

        # Añadir metadatos
        consolidated['metadata'] = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'years': list(range(self.from_year, self.to_year + 1)),
            'mbid_only': self.mbid_only
        }

        return consolidated

    def _get_user_raw_data(self, user_list: List[str]) -> Dict:
        """Obtiene datos crudos para un usuario o lista de usuarios"""

        # Top artistas
        artists = self.database.get_top_artists_by_scrobbles_only(
            user_list, self.from_year, self.to_year, 100, self.mbid_only
        )

        # Top álbumes
        albums = self.database.get_top_albums_by_scrobbles_only(
            user_list, self.from_year, self.to_year, 100, self.mbid_only
        )

        # Top canciones
        tracks = self.database.get_top_tracks_by_scrobbles_only(
            user_list, self.from_year, self.to_year, 100, self.mbid_only
        )

        # Top géneros
        genres = self.database.get_top_genres_by_scrobbles_only(
            user_list, self.from_year, self.to_year, 50, self.mbid_only
        )

        # Top sellos
        labels = self.database.get_top_labels_by_scrobbles_only(
            user_list, self.from_year, self.to_year, 50, self.mbid_only
        )

        # Top años de lanzamiento
        release_years = self.database.get_top_individual_release_years_by_scrobbles_only(
            user_list, self.from_year, self.to_year, 50, self.mbid_only
        )

        return {
            'artists': artists,
            'albums': albums,
            'tracks': tracks,
            'genres': genres,
            'labels': labels,
            'release_years': release_years
        }

    def _generate_shared_charts_data(self, users: List[str]) -> Dict:
        # Top 15 artistas por usuarios compartidos
        top_artists = self.database.get_top_artists_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 Ã¡lbumes por usuarios compartidos
        top_albums = self.database.get_top_albums_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 canciones por usuarios compartidos
        top_tracks = self.database.get_top_tracks_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 gÃ©neros por usuarios compartidos
        top_genres = self.database.get_top_genres_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 sellos por usuarios compartidos
        top_labels = self.database.get_top_labels_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # Top 15 aÃ±os individuales de lanzamiento por usuarios compartidos
        top_release_years = self.database.get_top_individual_years_by_shared_users(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        return {
            'artists': self._prepare_pie_chart_data('Artistas (Por Usuarios Compartidos)', top_artists, 'shared'),
            'albums': self._prepare_pie_chart_data('Ãlbumes (Por Usuarios Compartidos)', top_albums, 'shared'),
            'tracks': self._prepare_pie_chart_data('Canciones (Por Usuarios Compartidos)', top_tracks, 'shared'),
            'genres': self._prepare_pie_chart_data('GÃ©neros (Por Usuarios Compartidos)', top_genres, 'shared'),
            'labels': self._prepare_pie_chart_data('Sellos (Por Usuarios Compartidos)', top_labels, 'shared'),
            'release_years': self._prepare_pie_chart_data('AÃ±os de Lanzamiento (Por Usuarios Compartidos)', top_release_years, 'shared')
        }

    def _generate_scrobbles_charts_data(self, users: List[str]) -> Dict:
        """Genera datos para grÃ¡ficos por scrobbles totales"""
        # Obtener todos los tops por scrobbles
        scrobbles_data = self.database.get_top_by_total_scrobbles(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        # TambiÃ©n obtener aÃ±os individuales
        top_individual_years = self.database.get_top_individual_release_years_by_scrobbles_only(
            users, self.from_year, self.to_year, 15, self.mbid_only
        )

        return {
            'artists': self._prepare_pie_chart_data('Artistas (Por Scrobbles)', scrobbles_data['artists'], 'scrobbles'),
            'albums': self._prepare_pie_chart_data('Ãlbumes (Por Scrobbles)', scrobbles_data['albums'], 'scrobbles'),
            'tracks': self._prepare_pie_chart_data('Canciones (Por Scrobbles)', scrobbles_data['tracks'], 'scrobbles'),
            'genres': self._prepare_pie_chart_data('GÃ©neros (Por Scrobbles)', scrobbles_data['genres'], 'scrobbles'),
            'labels': self._prepare_pie_chart_data('Sellos (Por Scrobbles)', scrobbles_data['labels'], 'scrobbles'),
            'release_years': self._prepare_pie_chart_data('AÃ±os de Lanzamiento (Por Scrobbles)', top_individual_years, 'scrobbles'),
            'all_combined': self._prepare_combined_chart_data(scrobbles_data)
        }

    def _generate_evolution_data(self, users: List[str]) -> Dict:
        """Genera datos para grÃ¡ficos de evoluciÃ³n temporal"""
        evolution_data = self.database.get_evolution_data(
            users, self.from_year, self.to_year, self.mbid_only
        )

        return {
            'artists': self._prepare_line_chart_data('Top 15 Artistas por AÃ±o', evolution_data['artists'], evolution_data['years']),
            'albums': self._prepare_line_chart_data('Top 15 Ãlbumes por AÃ±o', evolution_data['albums'], evolution_data['years']),
            'tracks': self._prepare_line_chart_data('Top 15 Canciones por AÃ±o', evolution_data['tracks'], evolution_data['years']),
            'genres': self._prepare_line_chart_data('Top 15 GÃ©neros por AÃ±o', evolution_data['genres'], evolution_data['years']),
            'labels': self._prepare_line_chart_data('Top 15 Sellos por AÃ±o', evolution_data['labels'], evolution_data['years']),
            'release_years': self._prepare_line_chart_data('Top 15 AÃ±os de Lanzamiento por AÃ±o', evolution_data['release_years'], evolution_data['years'])
        }

    def _prepare_pie_chart_data(self, title: str, raw_data: List[Dict], chart_type: str) -> Dict:
        """Prepara datos para grÃ¡ficos circulares"""
        if not raw_data:
            return {
                'title': title,
                'data': {},
                'total': 0,
                'details': {},
                'type': chart_type
            }

        # Siempre usar scrobbles para el tamaÃ±o de las porciones
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
        """Prepara datos combinados para el grÃ¡fico de "Todo por Scrobbles"""
        all_items = []

        # Combinar todos los tops con prefijo de categorÃ­a
        for category, items in scrobbles_data.items():
            for item in items[:5]:  # Solo top 5 de cada categorÃ­a para evitar saturaciÃ³n
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
        """Prepara datos para grÃ¡ficos lineales de evoluciÃ³n"""
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

    def _generate_evolution_scatter_data(self, users: List[str]) -> Dict:
        """Genera datos para gráficos scatter de evolución temporal"""
        evolution_scatter_data = self.database.get_evolution_scatter_data(
            users, self.from_year, self.to_year, self.mbid_only
        )

        return {
            'artists': self._prepare_scatter_chart_data('Top 5 Artistas Anuales', evolution_scatter_data['artists'], evolution_scatter_data['years']),
            'albums': self._prepare_scatter_chart_data('Top 5 Álbumes Anuales', evolution_scatter_data['albums'], evolution_scatter_data['years']),
            'tracks': self._prepare_scatter_chart_data('Top 5 Canciones Anuales', evolution_scatter_data['tracks'], evolution_scatter_data['years']),
            'genres': self._prepare_scatter_chart_data('Top 5 Géneros Anuales', evolution_scatter_data['genres'], evolution_scatter_data['years']),
            'labels': self._prepare_scatter_chart_data('Top 5 Sellos Anuales', evolution_scatter_data['labels'], evolution_scatter_data['years']),
            'release_years': self._prepare_scatter_chart_data('Top 5 Años de Lanzamiento Anuales', evolution_scatter_data['release_years'], evolution_scatter_data['years'])
        }

    def _prepare_scatter_chart_data(self, title: str, scatter_data: Dict, years: List[int]) -> Dict:
        """Prepara datos para gráficos scatter"""
        if not scatter_data:
            return {
                'title': title,
                'data': {},
                'years': years
            }

        return {
            'title': title,
            'data': scatter_data,
            'years': years
        }

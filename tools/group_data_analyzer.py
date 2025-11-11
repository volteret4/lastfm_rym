#!/usr/bin/env python3
"""
GroupDataAnalyzer - Analizador para datos de coincidencias por nivel de usuarios
Permite obtener TOPs de elementos compartidos por N usuarios o más
"""

from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict
import json


class GroupDataAnalyzer:
    """Clase para analizar datos de coincidencias por nivel de usuarios"""

    def __init__(self, database, years_back: int = 5, mbid_only: bool = False):
        self.database = database
        self.years_back = years_back
        self.mbid_only = mbid_only
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def analyze_data_by_user_levels(self, users: List[str]) -> Dict:
        """Analiza datos para diferentes niveles de coincidencia de usuarios"""
        print(f"    • Analizando datos por niveles de usuarios...")

        total_users = len(users)
        data_by_levels = {}

        # Generar datos para cada nivel de usuarios (todos, todos-1, todos-2, etc.)
        for min_users in range(total_users, 1, -1):  # Desde todos hasta 2 usuarios mínimo
            level_key = self._get_level_key(min_users, total_users)
            print(f"      • Nivel: {level_key}")

            level_data = self._get_data_for_level(users, min_users)
            data_by_levels[level_key] = level_data

        return {
            'period': f"{self.from_year}-{self.to_year}",
            'users': users,
            'user_count': len(users),
            'data_by_levels': data_by_levels,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _get_level_key(self, min_users: int, total_users: int) -> str:
        """Genera la clave descriptiva para el nivel de usuarios"""
        if min_users == total_users:
            return "total_usuarios"
        else:
            missing = total_users - min_users
            return f"total_menos_{missing}"

    def _get_level_label(self, level_key: str, total_users: int) -> str:
        """Genera la etiqueta descriptiva para mostrar en el HTML"""
        if level_key == "total_usuarios":
            return f"Total de usuarios ({total_users})"
        else:
            missing = int(level_key.replace("total_menos_", ""))
            remaining = total_users - missing
            return f"Total menos {missing} ({remaining} usuarios)"

    def _get_data_for_level(self, users: List[str], min_users: int) -> Dict:
        """Obtiene datos para un nivel específico de usuarios"""

        # Top 25 artistas
        top_artists = self.database.get_top_artists_by_shared_users(
            users, self.from_year, self.to_year, 50, self.mbid_only  # Obtenemos 50 para filtrar después
        )
        filtered_artists = [item for item in top_artists if item['user_count'] >= min_users][:25]

        # Top 25 álbumes
        top_albums = self.database.get_top_albums_by_shared_users(
            users, self.from_year, self.to_year, 50, self.mbid_only
        )
        filtered_albums = [item for item in top_albums if item['user_count'] >= min_users][:25]

        # Top 25 canciones
        top_tracks = self.database.get_top_tracks_by_shared_users(
            users, self.from_year, self.to_year, 50, self.mbid_only
        )
        filtered_tracks = [item for item in top_tracks if item['user_count'] >= min_users][:25]

        # Top 25 géneros
        top_genres = self.database.get_top_genres_by_shared_users(
            users, self.from_year, self.to_year, 50, self.mbid_only
        )
        filtered_genres = [item for item in top_genres if item['user_count'] >= min_users][:25]

        # Top 25 sellos
        top_labels = self.database.get_top_labels_by_shared_users(
            users, self.from_year, self.to_year, 50, self.mbid_only
        )
        filtered_labels = [item for item in top_labels if item['user_count'] >= min_users][:25]

        # Top 25 décadas
        top_decades = self.database.get_top_release_decades_by_shared_users(
            users, self.from_year, self.to_year, 50, self.mbid_only
        )
        filtered_decades = [item for item in top_decades if item['user_count'] >= min_users][:25]

        return {
            'min_users': min_users,
            'artists': self._prepare_data_items(filtered_artists),
            'albums': self._prepare_data_items(filtered_albums),
            'tracks': self._prepare_data_items(filtered_tracks),
            'genres': self._prepare_data_items(filtered_genres),
            'labels': self._prepare_data_items(filtered_labels),
            'decades': self._prepare_data_items(filtered_decades),
            'counts': {
                'artists': len(filtered_artists),
                'albums': len(filtered_albums),
                'tracks': len(filtered_tracks),
                'genres': len(filtered_genres),
                'labels': len(filtered_labels),
                'decades': len(filtered_decades)
            }
        }

    def _prepare_data_items(self, raw_data: List[Dict]) -> List[Dict]:
        """Prepara los elementos para mostrar en formato compatible con html_semanal.py"""
        if not raw_data:
            return []

        result = []
        for item in raw_data:
            prepared_item = {
                'name': item['name'],
                'count': item['total_scrobbles'],  # Usar total_scrobbles como "count"
                'users': item['shared_users'],
                'user_counts': item.get('user_plays', {}),  # Scrobbles por usuario
                'user_count': item['user_count']
            }

            # Agregar información adicional si está disponible
            if 'artist' in item:
                prepared_item['artist'] = item['artist']
            if 'album' in item:
                prepared_item['album'] = item['album']
            if 'track' in item:
                prepared_item['track'] = item['track']

            result.append(prepared_item)

        return result

    def get_level_labels(self, users: List[str]) -> Dict[str, str]:
        """Obtiene las etiquetas para todos los niveles disponibles"""
        total_users = len(users)
        labels = {}

        for min_users in range(total_users, 1, -1):
            level_key = self._get_level_key(min_users, total_users)
            labels[level_key] = self._get_level_label(level_key, total_users)

        return labels

    def get_summary_for_level(self, level_data: Dict) -> Dict:
        """Obtiene resumen de estadísticas para un nivel específico"""
        return {
            'total_items': sum(level_data['counts'].values()),
            'artists_count': level_data['counts']['artists'],
            'albums_count': level_data['counts']['albums'],
            'tracks_count': level_data['counts']['tracks'],
            'genres_count': level_data['counts']['genres'],
            'labels_count': level_data['counts']['labels'],
            'decades_count': level_data['counts']['decades'],
            'min_users': level_data['min_users']
        }

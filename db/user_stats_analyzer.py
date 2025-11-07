#!/usr/bin/env python3
"""
UserStatsAnalyzer - Clase para analizar y procesar estadísticas de usuarios
"""

from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional
import json


class UserStatsAnalyzer:
    def __init__(self, database, years_back: int = 5):
        self.database = database
        self.years_back = years_back
        self.current_year = datetime.now().year
        self.from_year = self.current_year - years_back
        self.to_year = self.current_year

    def analyze_user(self, user: str, all_users: List[str]) -> Dict:
        """Analiza completamente un usuario y devuelve todas sus estadísticas"""
        print(f"    • Analizando scrobbles...")
        yearly_scrobbles = self._analyze_yearly_scrobbles(user)

        print(f"    • Analizando coincidencias...")
        coincidences_stats = self._analyze_coincidences(user, all_users)

        print(f"    • Analizando evolución...")
        evolution_stats = self._analyze_evolution(user, all_users)

        return {
            'user': user,
            'period': f"{self.from_year}-{self.to_year}",
            'yearly_scrobbles': yearly_scrobbles,
            'coincidences': coincidences_stats,
            'evolution': evolution_stats,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _analyze_yearly_scrobbles(self, user: str) -> Dict[int, int]:
        """Analiza el número de scrobbles por año"""
        scrobbles_by_year = self.database.get_user_scrobbles_by_year(
            user, self.from_year, self.to_year
        )

        yearly_counts = {}
        for year in range(self.from_year, self.to_year + 1):
            yearly_counts[year] = len(scrobbles_by_year.get(year, []))

        return yearly_counts

    def _analyze_coincidences(self, user: str, all_users: List[str]) -> Dict:
        """Analiza coincidencias del usuario con otros usuarios"""
        other_users = [u for u in all_users if u != user]

        # Coincidencias de artistas
        artist_coincidences = self.database.get_common_artists_with_users(
            user, other_users, self.from_year, self.to_year
        )

        # Coincidencias de álbumes
        album_coincidences = self.database.get_common_albums_with_users(
            user, other_users, self.from_year, self.to_year
        )

        # Estadísticas de géneros del usuario
        user_genres = self.database.get_user_top_genres(
            user, self.from_year, self.to_year, limit=20
        )

        # Años de lanzamiento de álbumes
        release_years = self.database.get_artist_release_years_for_user(
            user, self.from_year, self.to_year
        )

        # Años de formación de artistas
        formation_years = self.database.get_artist_formation_years_for_user(
            user, self.from_year, self.to_year
        )

        # Procesar datos para gráficos circulares
        charts_data = self._prepare_coincidence_charts_data(
            user, other_users, artist_coincidences, album_coincidences,
            user_genres, release_years, formation_years
        )

        return {
            'artists': artist_coincidences,
            'albums': album_coincidences,
            'genres': dict(user_genres),
            'release_years': release_years,
            'formation_years': formation_years,
            'charts': charts_data
        }

    def _prepare_coincidence_charts_data(self, user: str, other_users: List[str],
                                       artist_coincidences: Dict, album_coincidences: Dict,
                                       user_genres: List[Tuple], release_years: Dict,
                                       formation_years: Dict) -> Dict:
        """Prepara datos para gráficos circulares de coincidencias"""

        # Gráfico de coincidencias de artistas
        artist_chart = self._prepare_coincidences_pie_data(
            "Artistas", artist_coincidences, other_users
        )

        # Gráfico de coincidencias de álbumes
        album_chart = self._prepare_coincidences_pie_data(
            "Álbumes", album_coincidences, other_users
        )

        # Gráfico de géneros (distribución personal)
        genres_chart = self._prepare_genres_pie_data(user_genres)

        # Gráfico de años de lanzamiento
        release_years_chart = self._prepare_years_pie_data(
            "Años de Lanzamiento", release_years, 'release_year'
        )

        # Gráfico de años de formación
        formation_years_chart = self._prepare_years_pie_data(
            "Años de Formación", formation_years, 'formation_year'
        )

        return {
            'artists': artist_chart,
            'albums': album_chart,
            'genres': genres_chart,
            'release_years': release_years_chart,
            'formation_years': formation_years_chart
        }

    def _prepare_coincidences_pie_data(self, chart_type: str, coincidences: Dict,
                                     other_users: List[str]) -> Dict:
        """Prepara datos para gráfico circular de coincidencias"""
        user_data = {}

        for other_user in other_users:
            if other_user in coincidences:
                user_data[other_user] = len(coincidences[other_user])
            else:
                user_data[other_user] = 0

        # Solo incluir usuarios con coincidencias
        filtered_data = {user: count for user, count in user_data.items() if count > 0}

        return {
            'title': f'Coincidencias en {chart_type}',
            'data': filtered_data,
            'total': sum(filtered_data.values()) if filtered_data else 0,
            'details': coincidences
        }

    def _prepare_genres_pie_data(self, user_genres: List[Tuple]) -> Dict:
        """Prepara datos para gráfico circular de géneros"""
        # Tomar solo los top 8 géneros para mejor visualización
        top_genres = dict(user_genres[:8])
        total_plays = sum(top_genres.values()) if top_genres else 0

        return {
            'title': 'Distribución de Géneros',
            'data': top_genres,
            'total': total_plays,
            'details': dict(user_genres)
        }

    def _prepare_years_pie_data(self, chart_type: str, years_data: Dict,
                              year_field: str) -> Dict:
        """Prepara datos para gráfico circular de años"""
        # Agrupar por décadas para mejor visualización
        decade_plays = defaultdict(int)

        for item, info in years_data.items():
            year = info[year_field]
            decade = self._get_decade(year)
            decade_plays[decade] += info['plays']

        return {
            'title': f'Distribución por {chart_type}',
            'data': dict(decade_plays),
            'total': sum(decade_plays.values()) if decade_plays else 0,
            'details': years_data
        }

    def _get_decade(self, year: int) -> str:
        """Convierte un año a etiqueta de década"""
        if year < 1950:
            return "Antes de 1950"
        elif year >= 2020:
            return "2020s+"
        else:
            decade_start = (year // 10) * 10
            return f"{decade_start}s"

    def _analyze_evolution(self, user: str, all_users: List[str]) -> Dict:
        """Analiza la evolución temporal del usuario"""
        other_users = [u for u in all_users if u != user]

        # Evolución de géneros por año
        genres_evolution = self._analyze_genres_evolution(user)

        # Evolución de coincidencias por año
        coincidences_evolution = self._analyze_coincidences_evolution(user, other_users)

        return {
            'genres': genres_evolution,
            'coincidences': coincidences_evolution
        }

    def _analyze_genres_evolution(self, user: str) -> Dict:
        """Analiza la evolución de géneros por año"""
        genres_by_year = self.database.get_user_genres_by_year(
            user, self.from_year, self.to_year
        )

        # Obtener los top 10 géneros de todo el período
        top_genres = self.database.get_user_top_genres(
            user, self.from_year, self.to_year, limit=10
        )

        top_genre_names = [genre for genre, _ in top_genres]

        # Crear datos para el gráfico lineal
        evolution_data = {}
        for genre in top_genre_names:
            evolution_data[genre] = {}
            for year in range(self.from_year, self.to_year + 1):
                year_genres = genres_by_year.get(year, {})
                evolution_data[genre][year] = year_genres.get(genre, 0)

        return {
            'data': evolution_data,
            'years': list(range(self.from_year, self.to_year + 1)),
            'top_genres': top_genre_names
        }

    def _analyze_coincidences_evolution(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias por año"""
        evolution_data = {
            'artists': {},
            'albums': {},
            'tracks': {}
        }

        # Para cada año, calcular coincidencias
        for year in range(self.from_year, self.to_year + 1):
            # Artistas
            artist_coincidences = self.database.get_common_artists_with_users(
                user, other_users, year, year
            )

            # Álbumes
            album_coincidences = self.database.get_common_albums_with_users(
                user, other_users, year, year
            )

            # Preparar datos por usuario
            for other_user in other_users:
                if other_user not in evolution_data['artists']:
                    evolution_data['artists'][other_user] = {}
                if other_user not in evolution_data['albums']:
                    evolution_data['albums'][other_user] = {}

                # Contar coincidencias
                evolution_data['artists'][other_user][year] = len(
                    artist_coincidences.get(other_user, {})
                )
                evolution_data['albums'][other_user][year] = len(
                    album_coincidences.get(other_user, {})
                )

        return {
            'data': evolution_data,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

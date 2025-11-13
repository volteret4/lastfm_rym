#!/usr/bin/env python3
"""
UserStatsAnalyzer - Versión optimizada con correcciones para géneros por proveedor
"""

from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional
import json


class UserStatsAnalyzer:
    """Clase para analizar y procesar estadísticas de usuarios - OPTIMIZADA y CORREGIDA"""

    def __init__(self, database, years_back: int = 5, mbid_only: bool = False):
        self.database = database
        self.years_back = years_back
        self.mbid_only = mbid_only
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

        print(f"    • Analizando datos individuales...")
        individual_stats = self._analyze_individual(user)

        print(f"    • Analizando géneros por proveedor...")
        genres_stats = self._analyze_genres_by_provider(user)

        print(f"    • Analizando sellos...")
        labels_stats = self._analyze_labels_by_user(user)

        return {
            'user': user,
            'period': f"{self.from_year}-{self.to_year}",
            'yearly_scrobbles': yearly_scrobbles,
            'coincidences': coincidences_stats,
            'evolution': evolution_stats,
            'individual': individual_stats,
            'genres': genres_stats,
            'labels': labels_stats,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _analyze_genres_by_provider(self, user: str) -> Dict:
        """Analiza géneros del usuario según diferentes proveedores - CORREGIDO"""
        providers = ['lastfm', 'musicbrainz', 'discogs']
        genres_data = {}

        for provider in providers:
            print(f"      - Analizando géneros de {provider}...")

            try:
                # Obtener top 15 géneros para el gráfico circular
                top_genres = self.database.get_user_top_genres_by_provider(
                    user, self.from_year, self.to_year, provider, limit=15, mbid_only=self.mbid_only
                )

                if not top_genres:
                    print(f"        No hay datos de géneros para {provider}")
                    continue

                # Tomar top 6 géneros para los gráficos de puntos
                top_6_genres = [genre for genre, _ in top_genres[:6]]

                # Para cada género del top 6, obtener top 15 artistas con datos temporales
                genres_scatter_data = {}
                for genre_name in top_6_genres:
                    genre_artists = self.database.get_top_artists_for_genre_by_provider(
                        user, genre_name, self.from_year, self.to_year, provider, limit=15, mbid_only=self.mbid_only
                    )
                    if genre_artists:
                        genres_scatter_data[genre_name] = genre_artists

                # Obtener géneros de álbumes
                top_album_genres = self.database.get_user_top_album_genres_by_provider(
                    user, self.from_year, self.to_year, provider, limit=15, mbid_only=self.mbid_only
                )

                # Solo crear scatter para álbumes si hay datos
                album_genres_scatter_data = {}
                if top_album_genres:
                    # Tomar top 6 géneros de álbumes para los gráficos de puntos
                    top_6_album_genres = [genre for genre, _ in top_album_genres[:6]]

                    # Para cada género del top 6, obtener top 15 álbumes con datos temporales
                    for genre_name in top_6_album_genres:
                        genre_albums = self.database.get_top_albums_for_genre_by_provider(
                            user, genre_name, self.from_year, self.to_year, provider, limit=15, mbid_only=self.mbid_only
                        )
                        if genre_albums:
                            album_genres_scatter_data[genre_name] = genre_albums

                genres_data[provider] = {
                    'pie_chart': {
                        'data': dict(top_genres),
                        'total': sum(plays for _, plays in top_genres)
                    },
                    'scatter_charts': genres_scatter_data,
                    'years': list(range(self.from_year, self.to_year + 1))
                }

                # Solo añadir datos de álbumes si existen
                if top_album_genres:
                    genres_data[provider]['album_pie_chart'] = {
                        'data': dict(top_album_genres),
                        'total': sum(plays for _, plays in top_album_genres)
                    }

                if album_genres_scatter_data:
                    genres_data[provider]['album_scatter_charts'] = album_genres_scatter_data

            except Exception as e:
                print(f"        Error analizando {provider}: {e}")
                continue

        return genres_data

    def _analyze_labels_by_user(self, user: str) -> Dict:
        """Analiza sellos del usuario"""
        print(f"      - Analizando sellos...")

        try:
            # Obtener top 15 sellos para el gráfico circular
            top_labels = self.database.get_user_top_labels(
                user, self.from_year, self.to_year, limit=15, mbid_only=self.mbid_only
            )

            if not top_labels:
                print(f"        No hay datos de sellos disponibles")
                return {}

            # Tomar top 6 sellos para los gráficos de puntos
            top_6_labels = [label for label, _ in top_labels[:6]]

            # Para cada sello del top 6, obtener top 15 artistas con datos temporales
            labels_scatter_data = {}
            for label_name in top_6_labels:
                label_artists = self.database.get_top_artists_for_label(
                    user, label_name, self.from_year, self.to_year, limit=15, mbid_only=self.mbid_only
                )
                if label_artists:
                    labels_scatter_data[label_name] = label_artists

            return {
                'pie_chart': {
                    'data': dict(top_labels),
                    'total': sum(plays for _, plays in top_labels)
                },
                'scatter_charts': labels_scatter_data,
                'years': list(range(self.from_year, self.to_year + 1))
            }

        except Exception as e:
            print(f"        Error analizando sellos: {e}")
            return {}

    def _analyze_individual(self, user: str) -> Dict:
        """Analiza datos individuales del usuario para la vista 'yomimeconmigo'"""
        # Datos por año (existente)
        individual_data = self.database.get_user_individual_evolution_data(
            user, self.from_year, self.to_year, self.mbid_only
        )

        # Datos acumulativos (nuevo)
        individual_cumulative_data = self.database.get_user_individual_evolution_data_cumulative(
            user, self.from_year, self.to_year, self.mbid_only
        )

        return {
            'annual': individual_data,
            'cumulative': individual_cumulative_data
        }

    def _analyze_yearly_scrobbles(self, user: str) -> Dict[int, int]:
        """Analiza el número de scrobbles por año - optimizado"""
        scrobbles_by_year = self.database.get_user_scrobbles_by_year(
            user, self.from_year, self.to_year, self.mbid_only
        )

        yearly_counts = {}
        for year in range(self.from_year, self.to_year + 1):
            yearly_counts[year] = scrobbles_by_year.get(year, 0)

        return yearly_counts

    def _analyze_coincidences(self, user: str, all_users: List[str]) -> Dict:
        """Analiza coincidencias del usuario con otros usuarios"""
        other_users = [u for u in all_users if u != user]

        # Coincidencias básicas con filtro MBID
        artist_coincidences = self.database.get_common_artists_with_users(
            user, other_users, self.from_year, self.to_year, self.mbid_only
        )

        album_coincidences = self.database.get_common_albums_with_users(
            user, other_users, self.from_year, self.to_year, self.mbid_only
        )

        track_coincidences = self.database.get_common_tracks_with_users(
            user, other_users, self.from_year, self.to_year, self.mbid_only
        )

        # Coincidencias de géneros, sellos y años (con filtro MBID)
        genre_coincidences = self.database.get_common_genres_with_users(
            user, other_users, self.from_year, self.to_year, self.mbid_only
        )

        label_coincidences = self.database.get_common_labels_with_users(
            user, other_users, self.from_year, self.to_year, self.mbid_only
        )

        release_year_coincidences = self.database.get_common_release_years_with_users(
            user, other_users, self.from_year, self.to_year, self.mbid_only
        )

        # Estadísticas de géneros del usuario (mantener para gráfico individual)
        user_genres = self.database.get_user_top_genres(
            user, self.from_year, self.to_year, limit=20, mbid_only=self.mbid_only
        )

        # Nuevos gráficos especiales
        special_charts = self._prepare_special_charts_data(user, all_users)

        # Procesar datos para gráficos circulares con popups optimizados
        charts_data = self._prepare_coincidence_charts_data(
            user, other_users, artist_coincidences, album_coincidences,
            track_coincidences, user_genres, genre_coincidences,
            label_coincidences, release_year_coincidences, special_charts
        )

        return {
            'charts': charts_data
        }

    def _prepare_special_charts_data(self, user: str, all_users: List[str]) -> Dict:
        """Prepara datos para los 4 nuevos gráficos especiales"""
        other_users = [u for u in all_users if u != user]

        # Top 10 artistas por escuchas
        top_scrobbles = self.database.get_top_artists_by_scrobbles(
            all_users, self.from_year, self.to_year, 10, self.mbid_only
        )

        # Top 10 artistas por días
        top_days = self.database.get_top_artists_by_days(
            all_users, self.from_year, self.to_year, 10, self.mbid_only
        )

        # Top 10 artistas por número de canciones
        top_tracks = self.database.get_top_artists_by_track_count(
            all_users, self.from_year, self.to_year, 10, self.mbid_only
        )

        # Top 5 artistas por streaks
        top_streaks = self.database.get_top_artists_by_streaks(
            all_users, self.from_year, self.to_year, 5, self.mbid_only
        )

        # Procesar coincidencias para cada métrica especial
        special_data = {}

        # Gráfico 1: Top artistas por escuchas
        user_top_artists = {artist['name']: artist['plays'] for artist in top_scrobbles.get(user, [])}
        scrobbles_coincidences = {}
        for other_user in other_users:
            other_top_artists = {artist['name']: artist['plays'] for artist in top_scrobbles.get(other_user, [])}
            common_artists = set(user_top_artists.keys()) & set(other_top_artists.keys())
            if common_artists:
                total_plays = sum(user_top_artists[artist] + other_top_artists[artist] for artist in common_artists)
                scrobbles_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_plays': total_plays,
                    'artists': {artist: {'user_plays': user_top_artists[artist], 'other_plays': other_top_artists[artist]}
                              for artist in common_artists}
                }

        special_data['top_scrobbles'] = {
            'title': 'Top 10 Artistas por Escuchas',
            'data': {user: data['count'] for user, data in scrobbles_coincidences.items()},
            'total': sum(data['count'] for data in scrobbles_coincidences.values()),
            'details': scrobbles_coincidences,
            'type': 'top_scrobbles'
        }

        # Gráfico 2: Vuelve a casa (días)
        user_top_days = {artist['name']: artist['days'] for artist in top_days.get(user, [])}
        days_coincidences = {}
        for other_user in other_users:
            other_top_days = {artist['name']: artist['days'] for artist in top_days.get(other_user, [])}
            common_artists = set(user_top_days.keys()) & set(other_top_days.keys())
            if common_artists:
                total_days = sum(user_top_days[artist] + other_top_days[artist] for artist in common_artists)
                days_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_days': total_days,
                    'artists': {artist: {'user_days': user_top_days[artist], 'other_days': other_top_days[artist]}
                              for artist in common_artists}
                }

        special_data['top_days'] = {
            'title': 'Vuelve a Casa (Días de Escucha)',
            'data': {user: data['total_days'] for user, data in days_coincidences.items()},
            'total': sum(data['total_days'] for data in days_coincidences.values()),
            'details': days_coincidences,
            'type': 'top_days'
        }

        # Gráfico 3: Discografía completada
        user_top_tracks = {artist['name']: artist for artist in top_tracks.get(user, [])}
        tracks_coincidences = {}
        for other_user in other_users:
            other_top_tracks = {artist['name']: artist for artist in top_tracks.get(other_user, [])}
            common_artists = set(user_top_tracks.keys()) & set(other_top_tracks.keys())
            if common_artists:
                total_track_count = sum(user_top_tracks[artist]['track_count'] + other_top_tracks[artist]['track_count'] for artist in common_artists)
                tracks_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_track_count': total_track_count,
                    'artists': {artist: {
                        'user_tracks': user_top_tracks[artist]['track_count'],
                        'other_tracks': other_top_tracks[artist]['track_count'],
                        'user_plays': user_top_tracks[artist]['plays'],
                        'other_plays': other_top_tracks[artist]['plays']
                    } for artist in common_artists}
                }

        special_data['top_discography'] = {
            'title': 'Discografía Completada (Canciones)',
            'data': {user: data['total_track_count'] for user, data in tracks_coincidences.items()},
            'total': sum(data['total_track_count'] for data in tracks_coincidences.values()),
            'details': tracks_coincidences,
            'type': 'top_discography'
        }

        # Gráfico 4: Streaks
        user_top_streaks = {artist['name']: artist for artist in top_streaks.get(user, [])}
        streaks_coincidences = {}
        for other_user in other_users:
            other_top_streaks = {artist['name']: artist for artist in top_streaks.get(other_user, [])}
            common_artists = set(user_top_streaks.keys()) & set(other_top_streaks.keys())
            if common_artists:
                total_streak_days = sum(user_top_streaks[artist]['total_days'] + other_top_streaks[artist]['total_days'] for artist in common_artists)
                streaks_coincidences[other_user] = {
                    'count': len(common_artists),
                    'total_streak_days': total_streak_days,
                    'artists': {artist: {
                        'user_streak': user_top_streaks[artist]['max_streak'],
                        'other_streak': other_top_streaks[artist]['max_streak'],
                        'user_days': user_top_streaks[artist]['total_days'],
                        'other_days': other_top_streaks[artist]['total_days'],
                        'user_plays': user_top_streaks[artist]['plays'],
                        'other_plays': other_top_streaks[artist]['plays']
                    } for artist in common_artists}
                }

        special_data['top_streaks'] = {
            'title': 'Streaks (Días Consecutivos)',
            'data': {user: data['total_streak_days'] for user, data in streaks_coincidences.items()},
            'total': sum(data['total_streak_days'] for data in streaks_coincidences.values()),
            'details': streaks_coincidences,
            'type': 'top_streaks'
        }

        return special_data

    def _prepare_coincidence_charts_data(self, user: str, other_users: List[str],
                                       artist_coincidences: Dict, album_coincidences: Dict,
                                       track_coincidences: Dict, user_genres: List[Tuple],
                                       genre_coincidences: Dict, label_coincidences: Dict,
                                       release_year_coincidences: Dict, special_charts: Dict) -> Dict:
        """Prepara datos para gráficos circulares de coincidencias"""

        # Gráficos básicos de coincidencias
        artist_chart = self._prepare_coincidences_pie_data(
            "Artistas", artist_coincidences, other_users, user, 'artists'
        )

        album_chart = self._prepare_coincidences_pie_data(
            "Álbumes", album_coincidences, other_users, user, 'albums'
        )

        track_chart = self._prepare_coincidences_pie_data(
            "Canciones", track_coincidences, other_users, user, 'tracks'
        )

        # Gráfico de géneros del usuario (individual)
        genres_chart = self._prepare_genres_pie_data(user_genres, user)

        # Nuevos gráficos de coincidencias (ahora géneros, sellos y años son coincidencias)
        genre_coincidences_chart = self._prepare_coincidences_pie_data(
            "Géneros", genre_coincidences, other_users, user, 'genres'
        )

        label_coincidences_chart = self._prepare_coincidences_pie_data(
            "Sellos Discográficos", label_coincidences, other_users, user, 'labels'
        )

        release_year_coincidences_chart = self._prepare_coincidences_pie_data(
            "Años de Lanzamiento", release_year_coincidences, other_users, user, 'release_years'
        )

        return {
            'artists': artist_chart,
            'albums': album_chart,
            'tracks': track_chart,
            'genres': genres_chart,  # Individual del usuario
            'genre_coincidences': genre_coincidences_chart,  # Coincidencias
            'labels': label_coincidences_chart,  # Coincidencias
            'release_years': release_year_coincidences_chart,  # Coincidencias
            **special_charts  # Gráficos especiales
        }

    def _prepare_coincidences_pie_data(self, chart_type: str, coincidences: Dict,
                                     other_users: List[str], user: str, data_type: str) -> Dict:
        """Prepara datos para gráfico circular de coincidencias con popups optimizados"""
        user_data = {}
        popup_details = {}

        for other_user in other_users:
            if other_user in coincidences:
                count = len(coincidences[other_user])
                user_data[other_user] = count

                # Para popups: obtener datos específicos según el tipo
                if count > 0:
                    if data_type == 'artists':
                        # Top 5 álbumes de estos artistas
                        artists = list(coincidences[other_user].keys())[:10]
                        popup_details[other_user] = self.database.get_top_albums_for_artists(
                            user, artists, self.from_year, self.to_year, 5
                        )
                    elif data_type == 'albums':
                        # Top 5 canciones de estos álbumes
                        albums = list(coincidences[other_user].keys())[:10]
                        popup_details[other_user] = self.database.get_top_tracks_for_albums(
                            user, albums, self.from_year, self.to_year, 5
                        )
                    else:  # tracks
                        # Solo mostrar las top 5 canciones más escuchadas
                        sorted_tracks = sorted(
                            coincidences[other_user].items(),
                            key=lambda x: x[1]['user_plays'],
                            reverse=True
                        )[:5]
                        popup_details[other_user] = dict(sorted_tracks)
                else:
                    popup_details[other_user] = {}
            else:
                user_data[other_user] = 0
                popup_details[other_user] = {}

        # Solo incluir usuarios con coincidencias
        filtered_data = {user: count for user, count in user_data.items() if count > 0}
        filtered_details = {user: details for user, details in popup_details.items() if user_data.get(user, 0) > 0}

        return {
            'title': f'Coincidencias en {chart_type}',
            'data': filtered_data,
            'total': sum(filtered_data.values()) if filtered_data else 0,
            'details': filtered_details,
            'type': data_type
        }

    def _prepare_genres_pie_data(self, user_genres: List[Tuple], user: str) -> Dict:
        """Prepara datos para gráfico circular de géneros con artistas top"""
        # Tomar solo los top 8 géneros para visualización
        top_genres = dict(user_genres[:8])
        total_plays = sum(top_genres.values()) if top_genres else 0

        # Para popup: obtener top 5 artistas por género
        popup_details = {}
        for genre, plays in user_genres[:8]:
            artists = self.database.get_top_artists_for_genre(
                user, genre, self.from_year, self.to_year, 5, self.mbid_only
            )
            popup_details[genre] = artists

        return {
            'title': 'Distribución de Géneros',
            'data': top_genres,
            'total': total_plays,
            'details': popup_details,
            'type': 'genres'
        }

    def _analyze_evolution(self, user: str, all_users: List[str]) -> Dict:
        """Analiza la evolución temporal de COINCIDENCIAS del usuario"""
        other_users = [u for u in all_users if u != user]

        # Evolución de coincidencias de géneros por año
        genres_evolution = self._analyze_genres_coincidences_evolution(user, other_users)

        # Evolución de coincidencias de sellos por año
        labels_evolution = self._analyze_labels_coincidences_evolution(user, other_users)

        # Evolución de coincidencias de años de lanzamiento por año
        release_years_evolution = self._analyze_release_years_coincidences_evolution(user, other_users)

        # Evolución de coincidencias básicas por año - OPTIMIZADA (datos simples)
        coincidences_evolution = self._analyze_coincidences_evolution_optimized(user, other_users)

        return {
            'genres': genres_evolution,
            'labels': labels_evolution,
            'release_years': release_years_evolution,
            'coincidences': coincidences_evolution
        }

    def _analyze_genres_coincidences_evolution(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias de géneros por año - OPTIMIZADA"""
        evolution_data = {}
        evolution_details = {}

        for other_user in other_users:
            evolution_data[other_user] = {}
            evolution_details[other_user] = {}

            for year in range(self.from_year, self.to_year + 1):
                genre_coincidences = self.database.get_common_genres_with_users(
                    user, [other_user], year, year, self.mbid_only
                )

                if other_user in genre_coincidences:
                    count = len(genre_coincidences[other_user])
                    evolution_data[other_user][year] = count

                    # Top 5 géneros simples (no detallados)
                    top_genres = sorted(
                        genre_coincidences[other_user].items(),
                        key=lambda x: x[1]['total_plays'],
                        reverse=True
                    )[:5]
                    evolution_details[other_user][year] = [
                        {'name': name, 'plays': data['total_plays']}
                        for name, data in top_genres
                    ]
                else:
                    evolution_data[other_user][year] = 0
                    evolution_details[other_user][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

    def _analyze_labels_coincidences_evolution(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias de sellos por año - OPTIMIZADA"""
        evolution_data = {}
        evolution_details = {}

        for other_user in other_users:
            evolution_data[other_user] = {}
            evolution_details[other_user] = {}

            for year in range(self.from_year, self.to_year + 1):
                label_coincidences = self.database.get_common_labels_with_users(
                    user, [other_user], year, year, self.mbid_only
                )

                if other_user in label_coincidences:
                    count = len(label_coincidences[other_user])
                    evolution_data[other_user][year] = count

                    # Top 5 sellos simples
                    top_labels = sorted(
                        label_coincidences[other_user].items(),
                        key=lambda x: x[1]['total_plays'],
                        reverse=True
                    )[:5]
                    evolution_details[other_user][year] = [
                        {'name': name, 'plays': data['total_plays']}
                        for name, data in top_labels
                    ]
                else:
                    evolution_data[other_user][year] = 0
                    evolution_details[other_user][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

    def _analyze_release_years_coincidences_evolution(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias de años de lanzamiento de álbumes por año - OPTIMIZADA"""
        evolution_data = {}
        evolution_details = {}

        for other_user in other_users:
            evolution_data[other_user] = {}
            evolution_details[other_user] = {}

            for year in range(self.from_year, self.to_year + 1):
                album_year_coincidences = self.database.get_common_album_release_years_with_users(
                    user, [other_user], year, year, self.mbid_only
                )

                if other_user in album_year_coincidences:
                    count = len(album_year_coincidences[other_user])
                    evolution_data[other_user][year] = count

                    # Top 5 años de lanzamiento simples
                    top_years = sorted(
                        album_year_coincidences[other_user].items(),
                        key=lambda x: x[1]['total_plays'],
                        reverse=True
                    )[:5]
                    evolution_details[other_user][year] = [
                        {'name': name, 'plays': data['total_plays']}
                        for name, data in top_years
                    ]
                else:
                    evolution_data[other_user][year] = 0
                    evolution_details[other_user][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

    def _analyze_coincidences_evolution_optimized(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias por año - VERSIÓN OPTIMIZADA"""
        evolution_data = {
            'artists': {},
            'albums': {},
            'tracks': {}
        }

        evolution_details = {
            'artists': {},
            'albums': {},
            'tracks': {}
        }

        # Para cada año, calcular coincidencias simples (sin detalles complejos)
        for year in range(self.from_year, self.to_year + 1):
            # Obtener coincidencias básicas
            artist_coincidences = self.database.get_common_artists_with_users(
                user, other_users, year, year, self.mbid_only
            )
            album_coincidences = self.database.get_common_albums_with_users(
                user, other_users, year, year, self.mbid_only
            )
            track_coincidences = self.database.get_common_tracks_with_users(
                user, other_users, year, year, self.mbid_only
            )

            # Preparar datos por usuario
            for other_user in other_users:
                if other_user not in evolution_data['artists']:
                    evolution_data['artists'][other_user] = {}
                    evolution_data['albums'][other_user] = {}
                    evolution_data['tracks'][other_user] = {}
                    evolution_details['artists'][other_user] = {}
                    evolution_details['albums'][other_user] = {}
                    evolution_details['tracks'][other_user] = {}

                # Artistas - datos simples
                artist_data = artist_coincidences.get(other_user, {})
                evolution_data['artists'][other_user][year] = len(artist_data)
                top_artists = sorted(
                    artist_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['artists'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_artists
                ]

                # Álbumes - datos simples
                album_data = album_coincidences.get(other_user, {})
                evolution_data['albums'][other_user][year] = len(album_data)
                top_albums = sorted(
                    album_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['albums'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_albums
                ]

                # Canciones - datos simples
                track_data = track_coincidences.get(other_user, {})
                evolution_data['tracks'][other_user][year] = len(track_data)
                top_tracks = sorted(
                    track_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['tracks'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_tracks
                ]

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
        }

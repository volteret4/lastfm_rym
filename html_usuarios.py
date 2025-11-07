#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Version Corregida
Genera estadísticas individuales de usuarios con gráficos de coincidencias y evolución
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


class UserStatsDatabase:
    """Versión optimizada con límites para evitar archivos HTML enormes"""

    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_user_scrobbles_by_year(self, user: str, from_year: int, to_year: int) -> Dict[int, int]:
        """Obtiene conteo de scrobbles del usuario agrupados por año - optimizado"""
        cursor = self.conn.cursor()

        # Convertir años a timestamps
        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Solo contar, no obtener todos los datos
        cursor.execute('''
            SELECT strftime('%Y', datetime(timestamp, 'unixepoch')) as year,
                   COUNT(*) as count
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY year
            ORDER BY year
        ''', (user, from_timestamp, to_timestamp))

        scrobbles_by_year = {}
        for row in cursor.fetchall():
            year = int(row['year'])
            scrobbles_by_year[year] = row['count']

        return scrobbles_by_year

    def get_user_genres_by_year(self, user: str, from_year: int, to_year: int, limit: int = 10) -> Dict[int, Dict[str, int]]:
        """Obtiene géneros del usuario por año - limitado"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Solo obtener los top artistas para reducir carga
        cursor.execute('''
            SELECT DISTINCT s.artist
            FROM scrobbles s
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
            GROUP BY s.artist
            ORDER BY COUNT(*) DESC
            LIMIT 100
        ''', (user, from_timestamp, to_timestamp))

        top_artists = [row['artist'] for row in cursor.fetchall()]

        if not top_artists:
            return {}

        # Obtener géneros solo para estos artistas
        cursor.execute('''
            SELECT ag.genres,
                   strftime('%Y', datetime(s.timestamp, 'unixepoch')) as year,
                   COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.artist IN ({})
            GROUP BY ag.genres, year
            ORDER BY year, plays DESC
        '''.format(','.join(['?'] * len(top_artists))),
        [user, from_timestamp, to_timestamp] + top_artists)

        genres_by_year = defaultdict(lambda: defaultdict(int))

        for row in cursor.fetchall():
            year = int(row['year'])
            genres_json = row['genres']
            plays = row['plays']

            try:
                genres_list = json.loads(genres_json) if genres_json else []
                for genre in genres_list[:3]:  # Solo primeros 3 géneros por artista
                    genres_by_year[year][genre] += plays
            except json.JSONDecodeError:
                continue

        # Limitar géneros por año
        limited_genres_by_year = {}
        for year, genres in genres_by_year.items():
            sorted_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)
            limited_genres_by_year[year] = dict(sorted_genres[:limit])

        return limited_genres_by_year

    def get_common_artists_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene artistas comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener artistas del usuario principal
        cursor.execute('''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY artist
        ''', (user, from_timestamp, to_timestamp))

        user_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

        if not user_artists:
            return {}

        common_artists = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT artist, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND artist IN ({})
                GROUP BY artist
            '''.format(','.join(['?'] * len(user_artists))),
            [other_user, from_timestamp, to_timestamp] + list(user_artists.keys()))

            other_user_artists = {row['artist']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias
            common = {}
            for artist in user_artists:
                if artist in other_user_artists:
                    common[artist] = {
                        'user_plays': user_artists[artist],
                        'other_plays': other_user_artists[artist],
                        'total_plays': user_artists[artist] + other_user_artists[artist]
                    }

            if common:
                common_artists[other_user] = common

        return common_artists

    def get_common_albums_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene álbumes comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener álbumes del usuario principal
        cursor.execute('''
            SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND album IS NOT NULL AND album != ''
            GROUP BY album_key
        ''', (user, from_timestamp, to_timestamp))

        user_albums = {row['album_key']: row['plays'] for row in cursor.fetchall()}

        if not user_albums:
            return {}

        common_albums = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT (artist || ' - ' || album) as album_key, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND album IS NOT NULL AND album != ''
                  AND (artist || ' - ' || album) IN ({})
                GROUP BY album_key
            '''.format(','.join(['?'] * len(user_albums))),
            [other_user, from_timestamp, to_timestamp] + list(user_albums.keys()))

            other_user_albums = {row['album_key']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias
            common = {}
            for album in user_albums:
                if album in other_user_albums:
                    common[album] = {
                        'user_plays': user_albums[album],
                        'other_plays': other_user_albums[album],
                        'total_plays': user_albums[album] + other_user_albums[album]
                    }

            if common:
                common_albums[other_user] = common

        return common_albums

    def get_common_tracks_with_users(self, user: str, other_users: List[str], from_year: int, to_year: int) -> Dict[str, Dict[str, int]]:
        """Obtiene canciones comunes entre el usuario y otros usuarios"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        # Obtener canciones del usuario principal
        cursor.execute('''
            SELECT (artist || ' - ' || track) as track_key, COUNT(*) as plays
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY track_key
        ''', (user, from_timestamp, to_timestamp))

        user_tracks = {row['track_key']: row['plays'] for row in cursor.fetchall()}

        if not user_tracks:
            return {}

        common_tracks = {}

        for other_user in other_users:
            if other_user == user:
                continue

            cursor.execute('''
                SELECT (artist || ' - ' || track) as track_key, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND timestamp >= ? AND timestamp <= ?
                  AND (artist || ' - ' || track) IN ({})
                GROUP BY track_key
            '''.format(','.join(['?'] * len(user_tracks))),
            [other_user, from_timestamp, to_timestamp] + list(user_tracks.keys()))

            other_user_tracks = {row['track_key']: row['plays'] for row in cursor.fetchall()}

            # Calcular coincidencias
            common = {}
            for track in user_tracks:
                if track in other_user_tracks:
                    common[track] = {
                        'user_plays': user_tracks[track],
                        'other_plays': other_user_tracks[track],
                        'total_plays': user_tracks[track] + other_user_tracks[track]
                    }

            if common:
                common_tracks[other_user] = common

        return common_tracks

    def get_user_top_genres(self, user: str, from_year: int, to_year: int, limit: int = 10) -> List[Tuple[str, int]]:
        """Obtiene los géneros más escuchados por el usuario - limitado"""
        genres_by_year = self.get_user_genres_by_year(user, from_year, to_year, limit=20)

        # Sumar todos los años
        total_genres = defaultdict(int)
        for year_genres in genres_by_year.values():
            for genre, plays in year_genres.items():
                total_genres[genre] += plays

        # Ordenar y limitar
        sorted_genres = sorted(total_genres.items(), key=lambda x: x[1], reverse=True)
        return sorted_genres[:limit]

    def get_user_release_years_distribution(self, user: str, from_year: int, to_year: int) -> Dict[str, Dict]:
        """Obtiene distribución de años de lanzamiento para el usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT ard.release_year, s.artist, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.album IS NOT NULL AND s.album != ''
              AND ard.release_year IS NOT NULL
            GROUP BY ard.release_year, s.artist
            ORDER BY ard.release_year, plays DESC
        ''', (user, from_timestamp, to_timestamp))

        years_data = defaultdict(lambda: {'total': 0, 'artists': []})

        for row in cursor.fetchall():
            year = row['release_year']
            decade = self._get_decade(year)
            years_data[decade]['total'] += row['plays']
            if len(years_data[decade]['artists']) < 5:  # Solo top 5 artistas por década
                years_data[decade]['artists'].append({
                    'name': row['artist'],
                    'plays': row['plays']
                })

        return dict(years_data)

    def get_user_labels_distribution(self, user: str, from_year: int, to_year: int) -> Dict[str, Dict]:
        """Obtiene distribución de sellos discográficos para el usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT al.label, s.artist, COUNT(*) as plays
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND s.album IS NOT NULL AND s.album != ''
              AND al.label IS NOT NULL AND al.label != ''
            GROUP BY al.label, s.artist
            ORDER BY al.label, plays DESC
        ''', (user, from_timestamp, to_timestamp))

        labels_data = defaultdict(lambda: {'total': 0, 'artists': []})

        for row in cursor.fetchall():
            label = row['label']
            labels_data[label]['total'] += row['plays']
            if len(labels_data[label]['artists']) < 5:  # Solo top 5 artistas por sello
                labels_data[label]['artists'].append({
                    'name': row['artist'],
                    'plays': row['plays']
                })

        return dict(labels_data)

    def get_top_albums_for_artists(self, user: str, artists: List[str], from_year: int, to_year: int, limit: int = 5) -> Dict[str, List]:
        """Obtiene top álbumes para artistas específicos"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        albums_data = {}
        for artist in artists[:10]:  # Limitar artistas
            cursor.execute('''
                SELECT album, COUNT(*) as plays
                FROM scrobbles
                WHERE user = ? AND artist = ? AND timestamp >= ? AND timestamp <= ?
                  AND album IS NOT NULL AND album != ''
                GROUP BY album
                ORDER BY plays DESC
                LIMIT ?
            ''', (user, artist, from_timestamp, to_timestamp, limit))

            albums_data[artist] = [{'name': row['album'], 'plays': row['plays']} for row in cursor.fetchall()]

        return albums_data

    def get_top_tracks_for_albums(self, user: str, albums: List[str], from_year: int, to_year: int, limit: int = 5) -> Dict[str, List]:
        """Obtiene top canciones para álbumes específicos"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        tracks_data = {}
        for album in albums[:10]:  # Limitar álbumes
            # Separar artista y álbum
            if ' - ' in album:
                artist, album_name = album.split(' - ', 1)
                cursor.execute('''
                    SELECT track, COUNT(*) as plays
                    FROM scrobbles
                    WHERE user = ? AND artist = ? AND album = ? AND timestamp >= ? AND timestamp <= ?
                    GROUP BY track
                    ORDER BY plays DESC
                    LIMIT ?
                ''', (user, artist, album_name, from_timestamp, to_timestamp, limit))

                tracks_data[album] = [{'name': row['track'], 'plays': row['plays']} for row in cursor.fetchall()]

        return tracks_data

    def get_top_artists_for_genre(self, user: str, genre: str, from_year: int, to_year: int, limit: int = 5) -> List[Dict]:
        """Obtiene top artistas para un género específico"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        cursor.execute('''
            SELECT s.artist, COUNT(*) as plays
            FROM scrobbles s
            JOIN artist_genres ag ON s.artist = ag.artist
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND ag.genres LIKE ?
            GROUP BY s.artist
            ORDER BY plays DESC
            LIMIT ?
        ''', (user, from_timestamp, to_timestamp, f'%"{genre}"%', limit))

        return [{'name': row['artist'], 'plays': row['plays']} for row in cursor.fetchall()]

    def _get_decade(self, year: int) -> str:
        """Convierte un año a etiqueta de década"""
        if year < 1950:
            return "Antes de 1950"
        elif year >= 2020:
            return "2020s+"
        else:
            decade_start = (year // 10) * 10
            return f"{decade_start}s"

    def close(self):
        """Cerrar conexión a la base de datos"""
        self.conn.close()


class UserStatsAnalyzer:
    """Clase para analizar y procesar estadísticas de usuarios"""

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
        """Analiza el número de scrobbles por año - optimizado"""
        scrobbles_by_year = self.database.get_user_scrobbles_by_year(
            user, self.from_year, self.to_year
        )

        yearly_counts = {}
        for year in range(self.from_year, self.to_year + 1):
            yearly_counts[year] = scrobbles_by_year.get(year, 0)

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

        # Coincidencias de canciones
        track_coincidences = self.database.get_common_tracks_with_users(
            user, other_users, self.from_year, self.to_year
        )

        # Estadísticas de géneros del usuario
        user_genres = self.database.get_user_top_genres(
            user, self.from_year, self.to_year, limit=20
        )

        # Años de lanzamiento y sellos
        release_years = self.database.get_user_release_years_distribution(
            user, self.from_year, self.to_year
        )

        labels_data = self.database.get_user_labels_distribution(
            user, self.from_year, self.to_year
        )

        # Procesar datos para gráficos circulares con popups optimizados
        charts_data = self._prepare_coincidence_charts_data(
            user, other_users, artist_coincidences, album_coincidences,
            track_coincidences, user_genres, release_years, labels_data
        )

        return {
            'charts': charts_data
        }

    def _prepare_coincidence_charts_data(self, user: str, other_users: List[str],
                                       artist_coincidences: Dict, album_coincidences: Dict,
                                       track_coincidences: Dict, user_genres: List[Tuple],
                                       release_years: Dict, labels_data: Dict) -> Dict:
        """Prepara datos para gráficos circulares de coincidencias"""

        # Gráfico de coincidencias de artistas
        artist_chart = self._prepare_coincidences_pie_data(
            "Artistas", artist_coincidences, other_users, user, 'artists'
        )

        # Gráfico de coincidencias de álbumes
        album_chart = self._prepare_coincidences_pie_data(
            "Álbumes", album_coincidences, other_users, user, 'albums'
        )

        # Gráfico de coincidencias de canciones
        track_chart = self._prepare_coincidences_pie_data(
            "Canciones", track_coincidences, other_users, user, 'tracks'
        )

        # Gráfico de géneros (distribución personal)
        genres_chart = self._prepare_genres_pie_data(user_genres, user)

        # Gráfico de años de lanzamiento
        release_years_chart = self._prepare_years_labels_pie_data(
            "Años de Lanzamiento", release_years
        )

        # Gráfico de sellos
        labels_chart = self._prepare_years_labels_pie_data(
            "Sellos Discográficos", labels_data
        )

        return {
            'artists': artist_chart,
            'albums': album_chart,
            'tracks': track_chart,
            'genres': genres_chart,
            'release_years': release_years_chart,
            'labels': labels_chart
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
                user, genre, self.from_year, self.to_year, 5
            )
            popup_details[genre] = artists

        return {
            'title': 'Distribución de Géneros',
            'data': top_genres,
            'total': total_plays,
            'details': popup_details,
            'type': 'genres'
        }

    def _prepare_years_labels_pie_data(self, chart_type: str, data: Dict) -> Dict:
        """Prepara datos para gráfico circular de años/sellos con artistas top"""
        chart_data = {}
        popup_details = {}

        for category, info in data.items():
            chart_data[category] = info['total']
            popup_details[category] = info['artists']  # Ya limitados a top 5

        return {
            'title': chart_type,
            'data': chart_data,
            'total': sum(chart_data.values()) if chart_data else 0,
            'details': popup_details,
            'type': 'years_labels'
        }

    def _analyze_evolution(self, user: str, all_users: List[str]) -> Dict:
        """Analiza la evolución temporal del usuario"""
        other_users = [u for u in all_users if u != user]

        # Evolución de géneros por año - limitada
        genres_evolution = self._analyze_genres_evolution_limited(user)

        # Evolución de sellos por año
        labels_evolution = self._analyze_labels_evolution_limited(user)

        # Evolución de años de lanzamiento por año
        release_years_evolution = self._analyze_release_years_evolution_limited(user)

        # Evolución de coincidencias por año - con datos detallados para popups
        coincidences_evolution = self._analyze_coincidences_evolution_with_details(user, other_users)

        return {
            'genres': genres_evolution,
            'labels': labels_evolution,
            'release_years': release_years_evolution,
            'coincidences': coincidences_evolution
        }

    def _analyze_labels_evolution_limited(self, user: str) -> Dict:
        """Analiza la evolución de sellos por año - solo top 10"""
        cursor = self.database.conn.cursor()

        labels_by_year = {}

        for year in range(self.from_year, self.to_year + 1):
            from_timestamp = int(datetime(year, 1, 1).timestamp())
            to_timestamp = int(datetime(year + 1, 1, 1).timestamp()) - 1

            cursor.execute('''
                SELECT al.label, s.artist, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND al.label IS NOT NULL AND al.label != ''
                GROUP BY al.label, s.artist
                ORDER BY al.label, plays DESC
            ''', (user, from_timestamp, to_timestamp))

            year_labels = defaultdict(lambda: {'plays': 0, 'artists': []})
            for row in cursor.fetchall():
                label = row['label']
                year_labels[label]['plays'] += row['plays']
                if len(year_labels[label]['artists']) < 5:
                    year_labels[label]['artists'].append({
                        'name': row['artist'],
                        'plays': row['plays']
                    })

            labels_by_year[year] = dict(year_labels)

        # Obtener los top 10 sellos de todo el período
        all_labels = defaultdict(int)
        for year_data in labels_by_year.values():
            for label, data in year_data.items():
                all_labels[label] += data['plays']

        top_labels = sorted(all_labels.items(), key=lambda x: x[1], reverse=True)[:10]
        top_label_names = [label for label, _ in top_labels]

        # Crear datos para el gráfico lineal
        evolution_data = {}
        evolution_details = {}

        for label in top_label_names:
            evolution_data[label] = {}
            evolution_details[label] = {}
            for year in range(self.from_year, self.to_year + 1):
                year_data = labels_by_year.get(year, {})
                if label in year_data:
                    evolution_data[label][year] = year_data[label]['plays']
                    evolution_details[label][year] = year_data[label]['artists']
                else:
                    evolution_data[label][year] = 0
                    evolution_details[label][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'top_labels': top_label_names
        }

    def _analyze_release_years_evolution_limited(self, user: str) -> Dict:
        """Analiza la evolución de décadas de lanzamiento por año - solo top 8"""
        cursor = self.database.conn.cursor()

        decades_by_year = {}

        for year in range(self.from_year, self.to_year + 1):
            from_timestamp = int(datetime(year, 1, 1).timestamp())
            to_timestamp = int(datetime(year + 1, 1, 1).timestamp()) - 1

            cursor.execute('''
                SELECT ard.release_year, s.artist, COUNT(*) as plays
                FROM scrobbles s
                LEFT JOIN album_release_dates ard ON s.artist = ard.artist AND s.album = ard.album
                WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                  AND ard.release_year IS NOT NULL
                GROUP BY ard.release_year, s.artist
                ORDER BY ard.release_year, plays DESC
            ''', (user, from_timestamp, to_timestamp))

            year_decades = defaultdict(lambda: {'plays': 0, 'artists': []})
            for row in cursor.fetchall():
                decade = self.database._get_decade(row['release_year'])
                year_decades[decade]['plays'] += row['plays']
                if len(year_decades[decade]['artists']) < 5:
                    year_decades[decade]['artists'].append({
                        'name': row['artist'],
                        'plays': row['plays']
                    })

            decades_by_year[year] = dict(year_decades)

        # Obtener las top 8 décadas de todo el período
        all_decades = defaultdict(int)
        for year_data in decades_by_year.values():
            for decade, data in year_data.items():
                all_decades[decade] += data['plays']

        top_decades = sorted(all_decades.items(), key=lambda x: x[1], reverse=True)[:8]
        top_decade_names = [decade for decade, _ in top_decades]

        # Crear datos para el gráfico lineal
        evolution_data = {}
        evolution_details = {}

        for decade in top_decade_names:
            evolution_data[decade] = {}
            evolution_details[decade] = {}
            for year in range(self.from_year, self.to_year + 1):
                year_data = decades_by_year.get(year, {})
                if decade in year_data:
                    evolution_data[decade][year] = year_data[decade]['plays']
                    evolution_details[decade][year] = year_data[decade]['artists']
                else:
                    evolution_data[decade][year] = 0
                    evolution_details[decade][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'top_decades': top_decade_names
        }

    def _analyze_coincidences_evolution_with_details(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias por año - con datos detallados para popups"""
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

        # Para cada año, calcular coincidencias con detalles
        for year in range(self.from_year, self.to_year + 1):
            # Obtener coincidencias detalladas
            artist_coincidences = self.database.get_common_artists_with_users(
                user, other_users, year, year
            )
            album_coincidences = self.database.get_common_albums_with_users(
                user, other_users, year, year
            )
            track_coincidences = self.database.get_common_tracks_with_users(
                user, other_users, year, year
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

                # Artistas
                artist_data = artist_coincidences.get(other_user, {})
                evolution_data['artists'][other_user][year] = len(artist_data)
                # Top 5 artistas con más coincidencias
                top_artists = sorted(
                    artist_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['artists'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_artists
                ]

                # Álbumes
                album_data = album_coincidences.get(other_user, {})
                evolution_data['albums'][other_user][year] = len(album_data)
                # Top 5 álbumes con más coincidencias
                top_albums = sorted(
                    album_data.items(),
                    key=lambda x: x[1]['total_plays'],
                    reverse=True
                )[:5]
                evolution_details['albums'][other_user][year] = [
                    {'name': name, 'plays': data['total_plays']}
                    for name, data in top_albums
                ]

                # Canciones
                track_data = track_coincidences.get(other_user, {})
                evolution_data['tracks'][other_user][year] = len(track_data)
                # Top 5 canciones con más coincidencias
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

    def _analyze_genres_evolution_limited(self, user: str) -> Dict:
        """Analiza la evolución de géneros por año - solo top 10 con detalles"""
        genres_by_year = self.database.get_user_genres_by_year(
            user, self.from_year, self.to_year, limit=10
        )

        # Obtener los top 10 géneros de todo el período
        top_genres = self.database.get_user_top_genres(
            user, self.from_year, self.to_year, limit=10
        )

        top_genre_names = [genre for genre, _ in top_genres]

        # Crear datos para el gráfico lineal
        evolution_data = {}
        evolution_details = {}

        for genre in top_genre_names:
            evolution_data[genre] = {}
            evolution_details[genre] = {}
            for year in range(self.from_year, self.to_year + 1):
                year_genres = genres_by_year.get(year, {})
                evolution_data[genre][year] = year_genres.get(genre, 0)

                # Para cada género/año, obtener top 5 artistas
                if year_genres.get(genre, 0) > 0:
                    artists = self.database.get_top_artists_for_genre(
                        user, genre, year, year, 5
                    )
                    evolution_details[genre][year] = artists
                else:
                    evolution_details[genre][year] = []

        return {
            'data': evolution_data,
            'details': evolution_details,
            'years': list(range(self.from_year, self.to_year + 1)),
            'top_genres': top_genre_names
        }


class UserStatsHTMLGenerator:
    """Clase para generar HTML con gráficos interactivos de estadísticas de usuarios"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, all_user_stats: Dict, users: List[str], years_back: int) -> str:
        """Genera el HTML completo para estadísticas de usuarios"""
        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(all_user_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Usuarios - Estadísticas Individuales</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: #181825;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: #1e1e2e;
            padding: 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        h1 {{
            font-size: 2em;
            color: #cba6f7;
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: #a6adc8;
            font-size: 1em;
        }}

        .controls {{
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .control-group {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}

        label {{
            color: #cba6f7;
            font-weight: 600;
        }}

        select {{
            padding: 8px 15px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
        }}

        select:hover {{
            border-color: #cba6f7;
        }}

        select:focus {{
            outline: none;
            border-color: #cba6f7;
            box-shadow: 0 0 0 3px rgba(203, 166, 247, 0.2);
        }}

        .view-buttons {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .view-btn {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }}

        .view-btn:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .view-btn.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .user-header {{
            background: #1e1e2e;
            padding: 25px 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        .user-header h2 {{
            color: #cba6f7;
            font-size: 1.5em;
            margin-bottom: 8px;
        }}

        .user-info {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .stats-container {{
            padding: 30px;
        }}

        .view {{
            display: none;
        }}

        .view.active {{
            display: block;
        }}

        .coincidences-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }}

        .chart-container {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }}

        .chart-container h3 {{
            color: #cba6f7;
            font-size: 1.2em;
            margin-bottom: 15px;
            text-align: center;
        }}

        .chart-wrapper {{
            position: relative;
            height: 300px;
            margin-bottom: 10px;
        }}

        .chart-info {{
            text-align: center;
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .evolution-section {{
            margin-bottom: 40px;
        }}

        .evolution-section h3 {{
            color: #cba6f7;
            font-size: 1.3em;
            margin-bottom: 20px;
            border-bottom: 2px solid #cba6f7;
            padding-bottom: 10px;
        }}

        .evolution-charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 25px;
        }}

        .evolution-chart {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }}

        .evolution-chart h4 {{
            color: #cba6f7;
            font-size: 1.1em;
            margin-bottom: 15px;
            text-align: center;
        }}

        .line-chart-wrapper {{
            position: relative;
            height: 400px;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
        }}

        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            background: #1e1e2e;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #313244;
            text-align: center;
        }}

        .summary-card .number {{
            font-size: 1.8em;
            font-weight: 600;
            color: #cba6f7;
            margin-bottom: 5px;
        }}

        .summary-card .label {{
            font-size: 0.9em;
            color: #a6adc8;
        }}

        .popup-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 999;
        }}

        .popup {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e1e2e;
            border: 2px solid #cba6f7;
            border-radius: 12px;
            padding: 20px;
            max-width: 500px;
            max-height: 400px;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }}

        .popup-header {{
            color: #cba6f7;
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 15px;
            border-bottom: 1px solid #313244;
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .popup-close {{
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.2em;
            cursor: pointer;
            padding: 0;
        }}

        .popup-close:hover {{
            color: #cba6f7;
        }}

        .popup-content {{
            max-height: 300px;
            overflow-y: auto;
        }}

        .popup-item {{
            padding: 8px 12px;
            background: #181825;
            margin-bottom: 5px;
            border-radius: 6px;
            border-left: 3px solid #45475a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .popup-item .name {{
            color: #cdd6f4;
            font-weight: 600;
        }}

        .popup-item .count {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .coincidences-grid {{
                grid-template-columns: 1fr;
            }}

            .evolution-charts {{
                grid-template-columns: 1fr;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .view-buttons {{
                justify-content: center;
            }}

            .summary-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>👤 Estadísticas Individuales</h1>
            <p class="subtitle">Análisis detallado por usuario</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Usuario:</label>
                <select id="userSelect">
                    <!-- Se llenará dinámicamente -->
                </select>
            </div>

            <div class="control-group">
                <label>Vista:</label>
                <div class="view-buttons">
                    <button class="view-btn active" data-view="coincidences">Coincidencias</button>
                    <button class="view-btn" data-view="evolution">Evolución</button>
                </div>
            </div>
        </div>

        <div id="userHeader" class="user-header">
            <h2 id="userName">Selecciona un usuario</h2>
            <p class="user-info" id="userInfo">Período de análisis: {years_back + 1} años</p>
        </div>

        <div class="stats-container">
            <!-- Resumen de estadísticas -->
            <div id="summaryStats" class="summary-stats">
                <!-- Se llenará dinámicamente -->
            </div>

            <!-- Vista de Coincidencias -->
            <div id="coincidencesView" class="view active">
                <div class="coincidences-grid">
                    <div class="chart-container">
                        <h3>Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="artistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="artistsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Álbumes</h3>
                        <div class="chart-wrapper">
                            <canvas id="albumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="albumsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Canciones</h3>
                        <div class="chart-wrapper">
                            <canvas id="tracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="tracksInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Géneros</h3>
                        <div class="chart-wrapper">
                            <canvas id="genresChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Años de Lanzamiento</h3>
                        <div class="chart-wrapper">
                            <canvas id="releaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="releaseYearsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Sellos Discográficos</h3>
                        <div class="chart-wrapper">
                            <canvas id="labelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista de Evolución -->
            <div id="evolutionView" class="view">
                <div class="evolution-section">
                    <h3>🎵 Evolución de Géneros</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="genresEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🏷️ Evolución de Sellos Discográficos</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Sellos por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="labelsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📅 Evolución de Décadas de Lanzamiento</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top Décadas por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="releaseYearsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🤝 Evolución de Coincidencias</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Artistas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="artistsEvolutionChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Coincidencias en Álbumes</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="albumsEvolutionChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Coincidencias en Canciones</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="tracksEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        <!-- Popup para mostrar detalles -->
        <div id="popupOverlay" class="popup-overlay" style="display: none;"></div>
        <div id="popup" class="popup" style="display: none;">
            <div class="popup-header">
                <span id="popupTitle">Detalles</span>
                <button id="popupClose" class="popup-close">×</button>
            </div>
            <div id="popupContent" class="popup-content"></div>
        </div>
        </div>
    </div>

    <script>
        const users = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};

        let currentUser = null;
        let currentView = 'coincidences';
        let charts = {{}};

        // Inicialización simple sin DOMContentLoaded - siguiendo el patrón de html_anual.py
        const userSelect = document.getElementById('userSelect');

        // Llenar selector de usuarios
        users.forEach(user => {{
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        }});

        // Manejar botones de vista
        const viewButtons = document.querySelectorAll('.view-btn');
        viewButtons.forEach(btn => {{
            btn.addEventListener('click', function() {{
                const view = this.dataset.view;
                switchView(view);
            }});
        }});

        function switchView(view) {{
            currentView = view;

            // Update buttons
            document.querySelectorAll('.view-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            document.querySelector(`[data-view="${{view}}"]`).classList.add('active');

            // Update views
            document.querySelectorAll('.view').forEach(v => {{
                v.classList.remove('active');
            }});
            document.getElementById(view + 'View').classList.add('active');

            // Render appropriate charts
            if (currentUser && allStats[currentUser]) {{
                const userStats = allStats[currentUser];
                if (view === 'coincidences') {{
                    renderCoincidenceCharts(userStats);
                }} else if (view === 'evolution') {{
                    renderEvolutionCharts(userStats);
                }}
            }}
        }}

        function selectUser(username) {{
            currentUser = username;
            const userStats = allStats[username];

            if (!userStats) {{
                console.error('No stats found for user:', username);
                return;
            }}

            updateUserHeader(username, userStats);
            updateSummaryStats(userStats);

            if (currentView === 'coincidences') {{
                renderCoincidenceCharts(userStats);
            }} else if (currentView === 'evolution') {{
                renderEvolutionCharts(userStats);
            }}
        }}

        function updateUserHeader(username, userStats) {{
            document.getElementById('userName').textContent = username;
            document.getElementById('userInfo').innerHTML =
                `Período: ${{userStats.period}} | Generado: ${{userStats.generated_at}}`;
        }}

        function updateSummaryStats(userStats) {{
            const totalScrobbles = Object.values(userStats.yearly_scrobbles).reduce((a, b) => a + b, 0);

            const artistsChart = userStats.coincidences.charts.artists;
            const albumsChart = userStats.coincidences.charts.albums;
            const tracksChart = userStats.coincidences.charts.tracks;
            const genresChart = userStats.coincidences.charts.genres;
            const releaseYearsChart = userStats.coincidences.charts.release_years;
            const labelsChart = userStats.coincidences.charts.labels;

            const totalArtistCoincidences = Object.keys(artistsChart.data || {{}}).length;
            const totalAlbumCoincidences = Object.keys(albumsChart.data || {{}}).length;
            const totalTrackCoincidences = Object.keys(tracksChart.data || {{}}).length;
            const totalGenres = Object.keys(genresChart.data || {{}}).length;
            const totalReleaseYears = Object.keys(releaseYearsChart.data || {{}}).length;
            const totalLabels = Object.keys(labelsChart.data || {{}}).length;

            const summaryHTML = `
                <div class="summary-card">
                    <div class="number">${{totalScrobbles.toLocaleString()}}</div>
                    <div class="label">Scrobbles</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalArtistCoincidences}}</div>
                    <div class="label">Usuarios (Artistas)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalAlbumCoincidences}}</div>
                    <div class="label">Usuarios (Álbumes)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalGenres}}</div>
                    <div class="label">Géneros</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalReleaseYears}}</div>
                    <div class="label">Décadas</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalLabels}}</div>
                    <div class="label">Sellos</div>
                </div>
            `;

            document.getElementById('summaryStats').innerHTML = summaryHTML;
        }}

        function renderCoincidenceCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            renderPieChart('artistsChart', userStats.coincidences.charts.artists, 'artistsInfo');
            renderPieChart('albumsChart', userStats.coincidences.charts.albums, 'albumsInfo');
            renderPieChart('tracksChart', userStats.coincidences.charts.tracks, 'tracksInfo');
            renderPieChart('genresChart', userStats.coincidences.charts.genres, 'genresInfo');
            renderPieChart('releaseYearsChart', userStats.coincidences.charts.release_years, 'releaseYearsInfo');
            renderPieChart('labelsChart', userStats.coincidences.charts.labels, 'labelsInfo');
        }}

        function renderEvolutionCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            renderGenresEvolution(userStats.evolution.genres);
            renderLabelsEvolution(userStats.evolution.labels);
            renderReleaseYearsEvolution(userStats.evolution.release_years);
            renderCoincidencesEvolution('artists', userStats.evolution.coincidences);
            renderCoincidencesEvolution('albums', userStats.evolution.coincidences);
            renderCoincidencesEvolution('tracks', userStats.evolution.coincidences);
        }}

        function renderPieChart(canvasId, chartData, infoId) {{
            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';
            info.innerHTML = `Total: ${{chartData.total.toLocaleString()}} | Click en una porción para ver detalles`;

            const data = {{
                labels: Object.keys(chartData.data),
                datasets: [{{
                    data: Object.values(chartData.data),
                    backgroundColor: colors.slice(0, Object.keys(chartData.data).length),
                    borderColor: '#181825',
                    borderWidth: 2
                }}]
            }};

            const config = {{
                type: 'pie',
                data: data,
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 15,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const index = elements[0].index;
                            const label = data.labels[index];
                            showSmartPopup(chartData, label);
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function showSmartPopup(chartData, selectedLabel) {{
            const details = chartData.details[selectedLabel];
            const chartType = chartData.type;

            if (!details) return;

            let title = '';
            let content = '';

            if (chartType === 'artists') {{
                // Mostrar álbumes top para estos artistas
                title = `Top Álbumes - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(artist => {{
                    if (details[artist] && details[artist].length > 0) {{
                        content += `<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">${{artist}}</h4>`;
                        details[artist].forEach(album => {{
                            content += `<div class="popup-item">
                                <span class="name">${{album.name}}</span>
                                <span class="count">${{album.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }});
            }} else if (chartType === 'albums') {{
                // Mostrar canciones top para estos álbumes
                title = `Top Canciones - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(album => {{
                    if (details[album] && details[album].length > 0) {{
                        content += `<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">${{album}}</h4>`;
                        details[album].forEach(track => {{
                            content += `<div class="popup-item">
                                <span class="name">${{track.name}}</span>
                                <span class="count">${{track.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }});
            }} else if (chartType === 'tracks') {{
                // Mostrar canciones más escuchadas
                title = `Top Canciones - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(track => {{
                    const trackData = details[track];
                    content += `<div class="popup-item">
                        <span class="name">${{track}}</span>
                        <span class="count">${{trackData.user_plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'genres') {{
                // Mostrar artistas top para este género
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'years_labels') {{
                // Mostrar artistas top para esta década/sello
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }}

            if (content) {{
                document.getElementById('popupTitle').textContent = title;
                document.getElementById('popupContent').innerHTML = content;
                document.getElementById('popupOverlay').style.display = 'block';
                document.getElementById('popup').style.display = 'block';
            }}
        }}

        // Configurar cierre de popup
        document.getElementById('popupClose').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});

        document.getElementById('popupOverlay').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});

        function renderGenresEvolution(genresData) {{
            const canvas = document.getElementById('genresEvolutionChart');

            if (!genresData || !genresData.data) {{
                return;
            }}

            const datasets = [];
            let colorIndex = 0;

            Object.keys(genresData.data).forEach(genre => {{
                datasets.push({{
                    label: genre,
                    data: genresData.years.map(year => genresData.data[genre][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: genresData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const genre = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const plays = this.data.datasets[datasetIndex].data[pointIndex];

                            if (plays > 0 && genresData.details && genresData.details[genre] && genresData.details[genre][year]) {{
                                showLinearPopup(`Top 5 Artistas - ${{genre}} (${{year}})`, genresData.details[genre][year]);
                            }}
                        }}
                    }}
                }}
            }};

            charts['genresEvolutionChart'] = new Chart(canvas, config);
        }}

        function renderLabelsEvolution(labelsData) {{
            const canvas = document.getElementById('labelsEvolutionChart');

            if (!labelsData || !labelsData.data) {{
                return;
            }}

            const datasets = [];
            let colorIndex = 0;

            Object.keys(labelsData.data).forEach(label => {{
                datasets.push({{
                    label: label,
                    data: labelsData.years.map(year => labelsData.data[label][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: labelsData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const label = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const plays = this.data.datasets[datasetIndex].data[pointIndex];

                            if (plays > 0 && labelsData.details && labelsData.details[label] && labelsData.details[label][year]) {{
                                showLinearPopup(`Top 5 Artistas - ${{label}} (${{year}})`, labelsData.details[label][year]);
                            }}
                        }}
                    }}
                }}
            }};

            charts['labelsEvolutionChart'] = new Chart(canvas, config);
        }}

        function renderReleaseYearsEvolution(releaseYearsData) {{
            const canvas = document.getElementById('releaseYearsEvolutionChart');

            if (!releaseYearsData || !releaseYearsData.data) {{
                return;
            }}

            const datasets = [];
            let colorIndex = 0;

            Object.keys(releaseYearsData.data).forEach(decade => {{
                datasets.push({{
                    label: decade,
                    data: releaseYearsData.years.map(year => releaseYearsData.data[decade][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: releaseYearsData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const decade = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const plays = this.data.datasets[datasetIndex].data[pointIndex];

                            if (plays > 0 && releaseYearsData.details && releaseYearsData.details[decade] && releaseYearsData.details[decade][year]) {{
                                showLinearPopup(`Top 5 Artistas - ${{decade}} (${{year}})`, releaseYearsData.details[decade][year]);
                            }}
                        }}
                    }}
                }}
            }};

            charts['releaseYearsEvolutionChart'] = new Chart(canvas, config);
        }}

        function renderCoincidencesEvolution(type, evolutionData) {{
            const canvas = document.getElementById(type + 'EvolutionChart');

            if (!evolutionData || !evolutionData.data || !evolutionData.data[type]) {{
                return;
            }}

            const typeData = evolutionData.data[type];
            const datasets = [];
            let colorIndex = 0;

            Object.keys(typeData).forEach(user => {{
                datasets.push({{
                    label: user,
                    data: evolutionData.years.map(year => typeData[user][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: evolutionData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const user = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const coincidences = this.data.datasets[datasetIndex].data[pointIndex];

                            if (coincidences > 0 && evolutionData.details && evolutionData.details[type] && evolutionData.details[type][user] && evolutionData.details[type][user][year]) {{
                                const typeLabel = type === 'artists' ? 'Artistas' : type === 'albums' ? 'Álbumes' : 'Canciones';
                                showLinearPopup(`Top 5 ${{typeLabel}} - ${{user}} (${{year}})`, evolutionData.details[type][user][year]);
                            }}
                        }}
                    }}
                }}
            }};

            charts[type + 'EvolutionChart'] = new Chart(canvas, config);
        }}

        function showLinearPopup(title, details) {{
            if (!details || details.length === 0) return;

            let content = '';
            details.slice(0, 5).forEach(item => {{
                content += `<div class="popup-item">
                    <span class="name">${{item.name}}</span>
                    <span class="count">${{item.plays}} plays</span>
                </div>`;
            }});

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function showEvolutionPopup(dataType, item, year, value) {{
            const title = `${{dataType.charAt(0).toUpperCase() + dataType.slice(1)}} - ${{item}} (${{year}})`;
            const content = `<div class="popup-item">
                <span class="name">${{item}} en ${{year}}</span>
                <span class="count">${{value}} ${{dataType.includes('coincidencias') ? 'coincidencias' : 'reproducciones'}}</span>
            </div>`;

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        // Siguiendo el patrón de html_anual.py: eventos directos al final
        userSelect.addEventListener('change', function() {{
            selectUser(this.value);
        }});

        // Seleccionar primer usuario automáticamente si hay usuarios
        if (users.length > 0) {{
            selectUser(users[0]);
        }}
    </script>
</body>
</html>"""


def main():
    """Función principal para generar estadísticas de usuarios"""
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

        print("📊 Iniciando análisis de usuarios...")

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
        print("🎨 Generando HTML...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Guardar archivo
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Archivo generado: {args.output}")
        print(f"📊 Optimización aplicada:")
        print(f"  • Análisis: Datos completos procesados en Python")
        print(f"  • HTML: Solo datos necesarios para gráficos")
        print(f"  • Resultado: Archivo HTML ligero con funcionalidad completa")

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

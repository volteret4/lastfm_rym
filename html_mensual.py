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

        # Procesar datos para gráficos circulares
        charts_data = self._prepare_coincidence_charts_data(
            user, other_users, artist_coincidences, album_coincidences,
            track_coincidences, user_genres
        )

        return {
            'charts': charts_data
        }

    def _prepare_coincidence_charts_data(self, user: str, other_users: List[str],
                                       artist_coincidences: Dict, album_coincidences: Dict,
                                       track_coincidences: Dict, user_genres: List[Tuple]) -> Dict:
        """Prepara datos para gráficos circulares de coincidencias"""

        # Gráfico de coincidencias de artistas
        artist_chart = self._prepare_coincidences_pie_data(
            "Artistas", artist_coincidences, other_users
        )

        # Gráfico de coincidencias de álbumes
        album_chart = self._prepare_coincidences_pie_data(
            "Álbumes", album_coincidences, other_users
        )

        # Gráfico de coincidencias de canciones
        track_chart = self._prepare_coincidences_pie_data(
            "Canciones", track_coincidences, other_users
        )

        # Gráfico de géneros (distribución personal)
        genres_chart = self._prepare_genres_pie_data(user_genres)

        return {
            'artists': artist_chart,
            'albums': album_chart,
            'tracks': track_chart,
            'genres': genres_chart,
            'release_years': {'title': 'Años de Lanzamiento', 'data': {}, 'total': 0, 'details': {}},
            'formation_years': {'title': 'Años de Formación', 'data': {}, 'total': 0, 'details': {}}
        }

    def _prepare_coincidences_pie_data(self, chart_type: str, coincidences: Dict,
                                     other_users: List[str]) -> Dict:
        """Prepara datos para gráfico circular de coincidencias"""
        user_data = {}
        popup_details = {}

        for other_user in other_users:
            if other_user in coincidences:
                user_data[other_user] = len(coincidences[other_user])

                # Solo incluir top 20 elementos para popups
                if coincidences[other_user]:
                    sorted_items = sorted(
                        coincidences[other_user].items(),
                        key=lambda x: x[1]['total_plays'] if isinstance(x[1], dict) and 'total_plays' in x[1] else 0,
                        reverse=True
                    )
                    popup_details[other_user] = dict(sorted_items[:20])  # Solo top 20
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
            'details': filtered_details
        }

    def _prepare_genres_pie_data(self, user_genres: List[Tuple]) -> Dict:
        """Prepara datos para gráfico circular de géneros"""
        # Tomar solo los top 8 géneros para visualización
        top_genres = dict(user_genres[:8])
        total_plays = sum(top_genres.values()) if top_genres else 0

        # Para popup, solo top 15 géneros
        popup_genres = dict(user_genres[:15])

        return {
            'title': 'Distribución de Géneros',
            'data': top_genres,
            'total': total_plays,
            'details': popup_genres
        }

    def _analyze_evolution(self, user: str, all_users: List[str]) -> Dict:
        """Analiza la evolución temporal del usuario"""
        other_users = [u for u in all_users if u != user]

        # Evolución de géneros por año - limitada
        genres_evolution = self._analyze_genres_evolution_limited(user)

        # Evolución de coincidencias por año - solo conteos
        coincidences_evolution = self._analyze_coincidences_evolution_counts(user, other_users)

        return {
            'genres': genres_evolution,
            'coincidences': coincidences_evolution
        }

    def _analyze_genres_evolution_limited(self, user: str) -> Dict:
        """Analiza la evolución de géneros por año - solo top 10"""
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

    def _analyze_coincidences_evolution_counts(self, user: str, other_users: List[str]) -> Dict:
        """Analiza la evolución de coincidencias por año - solo conteos"""
        evolution_data = {
            'artists': {},
            'albums': {},
            'tracks': {}
        }

        # Para cada año, calcular solo conteos de coincidencias
        for year in range(self.from_year, self.to_year + 1):
            # Obtener coincidencias pero solo contar
            artist_coincidences = self.database.get_common_artists_with_users(
                user, other_users, year, year
            )
            album_coincidences = self.database.get_common_albums_with_users(
                user, other_users, year, year
            )
            track_coincidences = self.database.get_common_tracks_with_users(
                user, other_users, year, year
            )

            # Preparar datos por usuario - solo conteos
            for other_user in other_users:
                if other_user not in evolution_data['artists']:
                    evolution_data['artists'][other_user] = {}
                if other_user not in evolution_data['albums']:
                    evolution_data['albums'][other_user] = {}
                if other_user not in evolution_data['tracks']:
                    evolution_data['tracks'][other_user] = {}

                # Solo guardar conteos, no datos completos
                evolution_data['artists'][other_user][year] = len(
                    artist_coincidences.get(other_user, {})
                )
                evolution_data['albums'][other_user][year] = len(
                    album_coincidences.get(other_user, {})
                )
                evolution_data['tracks'][other_user][year] = len(
                    track_coincidences.get(other_user, {})
                )

        return {
            'data': evolution_data,
            'years': list(range(self.from_year, self.to_year + 1)),
            'users': other_users
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
        </div>
    </div>

    <script>
        const users = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};

        let currentUser = null;
        let currentView = 'coincidences';
        let charts = {{}};

        // Inicializar
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('DOM loaded');
            console.log('Users:', users);
            console.log('Stats:', allStats);

            initializeUserSelector();
            initializeViewButtons();

            if (users.length > 0) {{
                selectUser(users[0]);
            }}
        }});

        function initializeUserSelector() {{
            const userSelect = document.getElementById('userSelect');
            userSelect.innerHTML = '';

            users.forEach(user => {{
                const option = document.createElement('option');
                option.value = user;
                option.textContent = user;
                userSelect.appendChild(option);
            }});

            userSelect.addEventListener('change', function() {{
                selectUser(this.value);
            }});
        }}

        function initializeViewButtons() {{
            const viewButtons = document.querySelectorAll('.view-btn');
            viewButtons.forEach(btn => {{
                btn.addEventListener('click', function() {{
                    const view = this.dataset.view;
                    switchView(view);
                }});
            }});
        }}

        function selectUser(username) {{
            currentUser = username;
            const userStats = allStats[username];

            if (!userStats) {{
                console.error('No stats found for user:', username);
                return;
            }}

            console.log('Selected user:', username, userStats);

            updateUserHeader(username, userStats);
            updateSummaryStats(userStats);

            if (currentView === 'coincidences') {{
                renderCoincidenceCharts(userStats);
            }} else if (currentView === 'evolution') {{
                renderEvolutionCharts(userStats);
            }}
        }}

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

            const totalArtistCoincidences = Object.keys(artistsChart.data || {{}}).length;
            const totalAlbumCoincidences = Object.keys(albumsChart.data || {{}}).length;
            const totalTrackCoincidences = Object.keys(tracksChart.data || {{}}).length;
            const totalGenres = Object.keys(genresChart.data || {{}}).length;

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
                    <div class="number">${{totalTrackCoincidences}}</div>
                    <div class="label">Usuarios (Canciones)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalGenres}}</div>
                    <div class="label">Géneros</div>
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
        }}

        function renderEvolutionCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            renderGenresEvolution(userStats.evolution.genres);
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
            info.innerHTML = `Total: ${{chartData.total.toLocaleString()}}`;

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
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

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
                    }}
                }}
            }};

            charts['genresEvolutionChart'] = new Chart(canvas, config);
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
                    }}
                }}
            }};

            charts[type + 'EvolutionChart'] = new Chart(canvas, config);
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
        args.output = f'usuarios_{from_year}-{current_year}.html'

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

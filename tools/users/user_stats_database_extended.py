#!/usr/bin/env python3
"""
UserStatsDatabase - Versión extendida CORREGIDA con funciones faltantes para conteos únicos
AÑADE: Funciones completas de novedades que comparan períodos correctamente
CORRIGE: Lógica de géneros (artistas: lastfm, álbumes: lastfm/musicbrainz/discogs)
Hereda de la clase original para mantener TODA la funcionalidad
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# Importar la clase original del proyecto
from .user_stats_database import UserStatsDatabase


class UserStatsDatabaseExtended(UserStatsDatabase):
    """Versión extendida CORREGIDA con funciones adicionales para conteos únicos y novedades"""

    def get_new_items_for_user_year(self, user: str, year: int, item_type: str, mbid_only: bool = False) -> List[Dict]:
        """
        NUEVA FUNCIÓN: Obtiene elementos NUEVOS para un usuario en un año específico

        Lógica correcta:
        1. Encuentra todos los elementos del año especificado para el usuario
        2. Los compara con TODOS los scrobbles anteriores a ese año del mismo usuario
        3. Devuelve solo los que NO existían antes (primera aparición)
        4. Incluye scrobbles del período para ordenar por popularidad

        Args:
            user: Usuario
            year: Año a analizar
            item_type: 'artist', 'album', 'track', 'label', 'genre'
            mbid_only: Solo scrobbles con MBID

        Returns:
            Lista de elementos nuevos con scrobbles del período
        """
        cursor = self.conn.cursor()

        # Timestamps del año
        year_start = int(datetime(year, 1, 1).timestamp())
        year_end = int(datetime(year + 1, 1, 1).timestamp()) - 1

        # Timestamp de inicio de todos los scrobbles (para comparar)
        all_time_start = 0
        before_year_end = year_start - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')
        mbid_filter_prev = self._get_mbid_filter(mbid_only, 'sp')

        new_items = []

        try:
            if item_type == 'artist':
                # 1. Obtener todos los artistas del año actual
                cursor.execute(f'''
                    SELECT s.artist, COUNT(*) as period_plays
                    FROM scrobbles s
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                    {mbid_filter}
                    GROUP BY s.artist
                    ORDER BY period_plays DESC
                ''', (user, year_start, year_end))

                year_artists = cursor.fetchall()

                for artist_row in year_artists:
                    artist_name = artist_row['artist']
                    period_plays = artist_row['period_plays']

                    # 2. Verificar si este artista existía antes del año
                    cursor.execute(f'''
                        SELECT COUNT(*) as prev_count
                        FROM scrobbles sp
                        WHERE sp.user = ? AND sp.artist = ?
                          AND sp.timestamp >= ? AND sp.timestamp <= ?
                        {mbid_filter_prev}
                    ''', (user, artist_name, all_time_start, before_year_end))

                    prev_result = cursor.fetchone()
                    prev_count = prev_result['prev_count'] if prev_result else 0

                    # 3. Si no existía antes, es una novedad
                    if prev_count == 0:
                        new_items.append({
                            'name': artist_name,
                            'period_plays': period_plays,
                            'first_year': year,
                            'type': 'artist'
                        })

            elif item_type == 'album':
                # Lógica similar para álbumes
                cursor.execute(f'''
                    SELECT s.artist, s.album, COUNT(*) as period_plays
                    FROM scrobbles s
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                    GROUP BY s.artist, s.album
                    ORDER BY period_plays DESC
                ''', (user, year_start, year_end))

                year_albums = cursor.fetchall()

                for album_row in year_albums:
                    artist_name = album_row['artist']
                    album_name = album_row['album']
                    period_plays = album_row['period_plays']

                    cursor.execute(f'''
                        SELECT COUNT(*) as prev_count
                        FROM scrobbles sp
                        WHERE sp.user = ? AND sp.artist = ? AND sp.album = ?
                          AND sp.timestamp >= ? AND sp.timestamp <= ?
                        {mbid_filter_prev}
                    ''', (user, artist_name, album_name, all_time_start, before_year_end))

                    prev_result = cursor.fetchone()
                    prev_count = prev_result['prev_count'] if prev_result else 0

                    if prev_count == 0:
                        new_items.append({
                            'name': f"{artist_name} - {album_name}",
                            'period_plays': period_plays,
                            'first_year': year,
                            'type': 'album'
                        })

            elif item_type == 'track':
                # Lógica similar para canciones
                cursor.execute(f'''
                    SELECT s.artist, s.track, COUNT(*) as period_plays
                    FROM scrobbles s
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND s.track IS NOT NULL AND s.track != ''
                    {mbid_filter}
                    GROUP BY s.artist, s.track
                    ORDER BY period_plays DESC
                ''', (user, year_start, year_end))

                year_tracks = cursor.fetchall()

                for track_row in year_tracks:
                    artist_name = track_row['artist']
                    track_name = track_row['track']
                    period_plays = track_row['period_plays']

                    cursor.execute(f'''
                        SELECT COUNT(*) as prev_count
                        FROM scrobbles sp
                        WHERE sp.user = ? AND sp.artist = ? AND sp.track = ?
                          AND sp.timestamp >= ? AND sp.timestamp <= ?
                        {mbid_filter_prev}
                    ''', (user, artist_name, track_name, all_time_start, before_year_end))

                    prev_result = cursor.fetchone()
                    prev_count = prev_result['prev_count'] if prev_result else 0

                    if prev_count == 0:
                        new_items.append({
                            'name': f"{artist_name} - {track_name}",
                            'period_plays': period_plays,
                            'first_year': year,
                            'type': 'track'
                        })

            elif item_type == 'label':
                # Lógica para sellos
                cursor.execute(f'''
                    SELECT al.label, COUNT(*) as period_plays
                    FROM scrobbles s
                    LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND al.label IS NOT NULL AND al.label != ''
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                    GROUP BY al.label
                    ORDER BY period_plays DESC
                ''', (user, year_start, year_end))

                year_labels = cursor.fetchall()

                for label_row in year_labels:
                    label_name = label_row['label']
                    period_plays = label_row['period_plays']

                    cursor.execute(f'''
                        SELECT COUNT(*) as prev_count
                        FROM scrobbles sp
                        LEFT JOIN album_labels al ON sp.artist = al.artist AND sp.album = al.album
                        WHERE sp.user = ? AND al.label = ?
                          AND sp.timestamp >= ? AND sp.timestamp <= ?
                          AND sp.album IS NOT NULL AND sp.album != ''
                        {mbid_filter_prev}
                    ''', (user, label_name, all_time_start, before_year_end))

                    prev_result = cursor.fetchone()
                    prev_count = prev_result['prev_count'] if prev_result else 0

                    if prev_count == 0:
                        new_items.append({
                            'name': label_name,
                            'period_plays': period_plays,
                            'first_year': year,
                            'type': 'label'
                        })

            elif item_type == 'genre':
                # Lógica para géneros (usando Last.fm)
                cursor.execute(f'''
                    SELECT ag.genres, COUNT(*) as period_plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                    {mbid_filter}
                    GROUP BY ag.genres
                    ORDER BY period_plays DESC
                ''', (user, year_start, year_end))

                year_genre_data = cursor.fetchall()
                genre_counts = defaultdict(int)

                # Procesar géneros del año actual
                for row in year_genre_data:
                    genres_json = row['genres']
                    period_plays = row['period_plays']
                    try:
                        genres_list = json.loads(genres_json) if genres_json else []
                        for genre in genres_list[:3]:  # Solo primeros 3 géneros
                            genre_counts[genre] += period_plays
                    except (json.JSONDecodeError, TypeError):
                        continue

                # Para cada género, verificar si existía antes
                for genre_name, period_plays in genre_counts.items():
                    cursor.execute(f'''
                        SELECT COUNT(*) as prev_count
                        FROM scrobbles sp
                        JOIN artist_genres ag ON sp.artist = ag.artist
                        WHERE sp.user = ? AND ag.genres LIKE ?
                          AND sp.timestamp >= ? AND sp.timestamp <= ?
                        {mbid_filter_prev}
                    ''', (user, f'%"{genre_name}"%', all_time_start, before_year_end))

                    prev_result = cursor.fetchone()
                    prev_count = prev_result['prev_count'] if prev_result else 0

                    if prev_count == 0:
                        new_items.append({
                            'name': genre_name,
                            'period_plays': period_plays,
                            'first_year': year,
                            'type': 'genre'
                        })

            # Ordenar por popularidad en el período y tomar top 10
            new_items.sort(key=lambda x: x['period_plays'], reverse=True)
            return new_items[:10]  # Top 10 novedades para este año

        except sqlite3.OperationalError as e:
            print(f"Error obteniendo novedades de {item_type} para {year}: {e}")
            return []

    def get_user_top_artists(self, user: str, from_year: int, to_year: int,
                           limit: Optional[int] = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene top artistas del usuario con conteo de reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        limit_clause = f"LIMIT {limit}" if limit else ""

        cursor.execute(f'''
            SELECT artist, COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist
            ORDER BY plays DESC
            {limit_clause}
        ''', (user, from_timestamp, to_timestamp))

        return [(row['artist'], row['plays']) for row in cursor.fetchall()]

    def get_user_top_albums(self, user: str, from_year: int, to_year: int,
                          limit: Optional[int] = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene top álbumes del usuario con conteo de reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        limit_clause = f"LIMIT {limit}" if limit else ""

        cursor.execute(f'''
            SELECT CASE
                WHEN album IS NULL OR album = '' THEN artist || ' - [Unknown Album]'
                ELSE artist || ' - ' || album
            END as album_display,
            COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
            GROUP BY artist, album
            ORDER BY plays DESC
            {limit_clause}
        ''', (user, from_timestamp, to_timestamp))

        return [(row['album_display'], row['plays']) for row in cursor.fetchall()]

    def get_user_top_tracks(self, user: str, from_year: int, to_year: int,
                          limit: Optional[int] = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """Obtiene top canciones del usuario con conteo de reproducciones"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        limit_clause = f"LIMIT {limit}" if limit else ""

        cursor.execute(f'''
            SELECT artist || ' - ' || track as track_display, COUNT(*) as plays
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND track IS NOT NULL AND track != ''
            {mbid_filter}
            GROUP BY artist, track
            ORDER BY plays DESC
            {limit_clause}
        ''', (user, from_timestamp, to_timestamp))

        return [(row['track_display'], row['plays']) for row in cursor.fetchall()]

    def get_user_unique_count_artists(self, user: str, from_year: int, to_year: int,
                                    mbid_only: bool = False) -> int:
        """Obtiene el número total de artistas únicos del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT artist) as unique_artists
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_artists'] if result else 0

    def get_user_unique_count_albums(self, user: str, from_year: int, to_year: int,
                                   mbid_only: bool = False) -> int:
        """Obtiene el número total de álbumes únicos del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT artist || '|' || COALESCE(album, '[Unknown Album]')) as unique_albums
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_albums'] if result else 0

    def get_user_unique_count_tracks(self, user: str, from_year: int, to_year: int,
                                   mbid_only: bool = False) -> int:
        """Obtiene el número total de canciones únicas del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT artist || '|' || track) as unique_tracks
            FROM scrobbles s
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
              AND track IS NOT NULL AND track != ''
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_tracks'] if result else 0

    def get_user_unique_count_genres_by_provider(self, user: str, from_year: int, to_year: int,
                                               provider: str = 'lastfm', mbid_only: bool = False) -> int:
        """
        FUNCIÓN CORREGIDA: Obtiene el número total de géneros únicos del usuario por proveedor
        - lastfm: géneros de artistas (artist_genres)
        - musicbrainz/discogs: géneros de álbumes (album_genres)
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        if provider == 'lastfm':
            # Para Last.fm: contar géneros únicos de artistas
            try:
                cursor.execute(f'''
                    SELECT ag.genres, COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                    {mbid_filter}
                    GROUP BY ag.genres
                ''', (user, from_timestamp, to_timestamp))

                unique_genres = set()
                for row in cursor.fetchall():
                    genres_json = row['genres']
                    try:
                        genres_list = json.loads(genres_json) if genres_json else []
                        for genre in genres_list[:3]:  # Solo primeros 3 géneros
                            unique_genres.add(genre)
                    except (json.JSONDecodeError, TypeError):
                        continue

                return len(unique_genres)

            except sqlite3.OperationalError as e:
                print(f"Error contando géneros Last.fm: {e}")
                return 0

        elif provider in ['musicbrainz', 'discogs']:
            # Para MusicBrainz y Discogs: contar géneros únicos de álbumes
            try:
                cursor.execute(f'''
                    SELECT COUNT(DISTINCT ag.genre) as unique_genres
                    FROM scrobbles s
                    JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND ag.source = ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                ''', (user, from_timestamp, to_timestamp, provider))

                result = cursor.fetchone()
                return result['unique_genres'] if result else 0

            except sqlite3.OperationalError as e:
                print(f"Error contando géneros {provider}: {e}")
                return 0

        else:
            print(f"Proveedor no válido: {provider}")
            return 0

    def get_user_unique_count_labels(self, user: str, from_year: int, to_year: int,
                                   mbid_only: bool = False) -> int:
        """Obtiene el número total de sellos únicos del usuario"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only)

        cursor.execute(f'''
            SELECT COUNT(DISTINCT al.label) as unique_labels
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
              AND al.label IS NOT NULL AND al.label != ''
            {mbid_filter}
        ''', (user, from_timestamp, to_timestamp))

        result = cursor.fetchone()
        return result['unique_labels'] if result else 0

    # ================================================================
    # FUNCIONES DE GÉNEROS CORREGIDAS - Sobrescriben las del padre
    # ================================================================

    def get_user_top_genres_by_provider(self, user: str, from_year: int, to_year: int, provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """
        FUNCIÓN CORREGIDA: Obtiene géneros según el proveedor
        - lastfm: géneros de artistas (artist_genres)
        - musicbrainz/discogs: géneros de álbumes (album_genres)
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        if provider == 'lastfm':
            # Para Last.fm: usar artist_genres (géneros de artistas)
            try:
                cursor.execute(f'''
                    SELECT ag.genres, COUNT(*) as plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                    {mbid_filter}
                    GROUP BY ag.genres
                    ORDER BY plays DESC
                ''', (user, from_timestamp, to_timestamp))

                genre_counts = defaultdict(int)
                for row in cursor.fetchall():
                    genres_json = row['genres']
                    try:
                        genres_list = json.loads(genres_json) if genres_json else []
                        for genre in genres_list[:3]:  # Solo primeros 3 géneros
                            genre_counts[genre] += row['plays']
                    except (json.JSONDecodeError, TypeError):
                        continue

                # Ordenar y limitar
                sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
                return sorted_genres[:limit]

            except sqlite3.OperationalError as e:
                print(f"Error en géneros Last.fm: {e}")
                return []

        elif provider in ['musicbrainz', 'discogs']:
            # Para MusicBrainz y Discogs: usar album_genres (géneros de álbumes)
            try:
                cursor.execute(f'''
                    SELECT ag.genre, COUNT(*) as plays
                    FROM scrobbles s
                    JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND ag.source = ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                    GROUP BY ag.genre
                    ORDER BY plays DESC
                    LIMIT ?
                ''', (user, from_timestamp, to_timestamp, provider, limit))

                return [(row['genre'], row['plays']) for row in cursor.fetchall()]

            except sqlite3.OperationalError as e:
                print(f"Error en géneros {provider}: {e}")
                return []

        else:
            print(f"Proveedor no válido: {provider}")
            return []

    def get_top_artists_for_genre_by_provider(self, user: str, genre: str, from_year: int, to_year: int, provider: str = 'lastfm', limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """
        FUNCIÓN CORREGIDA: Obtiene artistas por género
        Solo Last.fm soporta géneros de artistas
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        if provider == 'lastfm':
            # Solo Last.fm tiene géneros de artistas
            try:
                cursor.execute(f'''
                    SELECT s.artist, COUNT(*) as total_plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND ag.genres LIKE ?
                    {mbid_filter}
                    GROUP BY s.artist
                    ORDER BY total_plays DESC
                    LIMIT ?
                ''', (user, from_timestamp, to_timestamp, f'%"{genre}"%', limit))

                artists = cursor.fetchall()
                artists_data = []

                for artist_row in artists:
                    artist_name = artist_row['artist']
                    yearly_data = {}

                    for year in range(from_year, to_year + 1):
                        year_start = int(datetime(year, 1, 1).timestamp())
                        year_end = int(datetime(year + 1, 1, 1).timestamp()) - 1

                        cursor.execute(f'''
                            SELECT COUNT(*) as plays
                            FROM scrobbles s
                            JOIN artist_genres ag ON s.artist = ag.artist
                            WHERE s.user = ? AND s.artist = ?
                              AND s.timestamp >= ? AND s.timestamp <= ?
                              AND ag.genres LIKE ?
                            {mbid_filter}
                        ''', (user, artist_name, year_start, year_end, f'%"{genre}"%'))

                        year_result = cursor.fetchone()
                        yearly_data[year] = year_result['plays'] if year_result else 0

                    artists_data.append({
                        'artist': artist_name,
                        'yearly_data': yearly_data,
                        'total_plays': artist_row['total_plays']
                    })

                return artists_data

            except sqlite3.OperationalError as e:
                print(f"Error en artistas por género Last.fm: {e}")
                return []

        else:
            # MusicBrainz y Discogs no tienen géneros de artistas, solo de álbumes
            print(f"⚠ Géneros de artistas no disponibles para {provider}")
            print(f"💡 {provider} solo tiene géneros de álbumes")
            return []

    def get_user_top_album_genres_by_provider(self, user: str, from_year: int, to_year: int, provider: str, limit: int = 15, mbid_only: bool = False) -> List[Tuple[str, int]]:
        """
        FUNCIÓN CORREGIDA: Obtiene géneros de álbumes por proveedor
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        if provider in ['musicbrainz', 'discogs']:
            # Para MusicBrainz y Discogs: usar album_genres directamente
            try:
                cursor.execute(f'''
                    SELECT ag.genre, COUNT(*) as plays
                    FROM scrobbles s
                    JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND ag.source = ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                    GROUP BY ag.genre
                    ORDER BY plays DESC
                    LIMIT ?
                ''', (user, from_timestamp, to_timestamp, provider, limit))

                return [(row['genre'], row['plays']) for row in cursor.fetchall()]

            except sqlite3.OperationalError as e:
                print(f"Error en géneros de álbumes {provider}: {e}")
                return []

        elif provider == 'lastfm':
            # Para Last.fm: aproximar con géneros de artistas aplicados a álbumes
            try:
                cursor.execute(f'''
                    SELECT ag.genres, COUNT(*) as plays, s.album
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                    GROUP BY s.album, ag.genres
                    ORDER BY plays DESC
                ''', (user, from_timestamp, to_timestamp))

                # Procesar géneros por álbum
                album_genre_counts = defaultdict(int)
                for row in cursor.fetchall():
                    genres_json = row['genres']
                    album_plays = row['plays']
                    try:
                        genres_list = json.loads(genres_json) if genres_json else []
                        for genre in genres_list[:3]:  # Solo primeros 3 géneros
                            album_genre_counts[genre] += album_plays
                    except (json.JSONDecodeError, TypeError):
                        continue

                # Ordenar y limitar
                sorted_genres = sorted(album_genre_counts.items(), key=lambda x: x[1], reverse=True)
                return sorted_genres[:limit]

            except sqlite3.OperationalError as e:
                print(f"Error en géneros de álbumes Last.fm: {e}")
                return []

        else:
            print(f"Proveedor no válido: {provider}")
            return []

    def get_top_albums_for_genre_by_provider(self, user: str, genre: str, from_year: int, to_year: int, provider: str, limit: int = 15, mbid_only: bool = False) -> List[Dict]:
        """
        FUNCIÓN CORREGIDA: Obtiene álbumes por género según proveedor
        """
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        mbid_filter = self._get_mbid_filter(mbid_only, 's')

        if provider in ['musicbrainz', 'discogs']:
            # Para MusicBrainz y Discogs: usar album_genres directamente
            try:
                cursor.execute(f'''
                    SELECT s.artist, s.album, COUNT(*) as total_plays
                    FROM scrobbles s
                    JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND ag.genre = ? AND ag.source = ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                    GROUP BY s.artist, s.album
                    ORDER BY total_plays DESC
                    LIMIT ?
                ''', (user, from_timestamp, to_timestamp, genre, provider, limit))

                albums = cursor.fetchall()
                albums_data = []

                for album_row in albums:
                    artist_name = album_row['artist']
                    album_name = album_row['album']
                    album_key = f"{artist_name} - {album_name}"

                    yearly_data = {}
                    for year in range(from_year, to_year + 1):
                        year_start = int(datetime(year, 1, 1).timestamp())
                        year_end = int(datetime(year + 1, 1, 1).timestamp()) - 1

                        cursor.execute(f'''
                            SELECT COUNT(*) as plays
                            FROM scrobbles s
                            JOIN album_genres ag ON s.artist = ag.artist AND s.album = ag.album
                            WHERE s.user = ? AND s.artist = ? AND s.album = ?
                              AND s.timestamp >= ? AND s.timestamp <= ?
                              AND ag.genre = ? AND ag.source = ?
                            {mbid_filter}
                        ''', (user, artist_name, album_name, year_start, year_end, genre, provider))

                        year_result = cursor.fetchone()
                        yearly_data[year] = year_result['plays'] if year_result else 0

                    albums_data.append({
                        'album': album_key,
                        'yearly_data': yearly_data,
                        'total_plays': album_row['total_plays']
                    })

                return albums_data

            except sqlite3.OperationalError as e:
                print(f"Error en álbumes por género {provider}: {e}")
                return []

        elif provider == 'lastfm':
            # Para Last.fm: usar géneros de artistas aplicados a álbumes
            try:
                cursor.execute(f'''
                    SELECT s.artist, s.album, COUNT(*) as total_plays
                    FROM scrobbles s
                    JOIN artist_genres ag ON s.artist = ag.artist
                    WHERE s.user = ? AND s.timestamp >= ? AND s.timestamp <= ?
                      AND ag.genres LIKE ?
                      AND s.album IS NOT NULL AND s.album != ''
                    {mbid_filter}
                    GROUP BY s.artist, s.album
                    ORDER BY total_plays DESC
                    LIMIT ?
                ''', (user, from_timestamp, to_timestamp, f'%"{genre}"%', limit))

                albums = cursor.fetchall()
                albums_data = []

                for album_row in albums:
                    artist_name = album_row['artist']
                    album_name = album_row['album']
                    album_key = f"{artist_name} - {album_name}"

                    yearly_data = {}
                    for year in range(from_year, to_year + 1):
                        year_start = int(datetime(year, 1, 1).timestamp())
                        year_end = int(datetime(year + 1, 1, 1).timestamp()) - 1

                        cursor.execute(f'''
                            SELECT COUNT(*) as plays
                            FROM scrobbles s
                            JOIN artist_genres ag ON s.artist = ag.artist
                            WHERE s.user = ? AND s.artist = ? AND s.album = ?
                              AND s.timestamp >= ? AND s.timestamp <= ?
                              AND ag.genres LIKE ?
                            {mbid_filter}
                        ''', (user, artist_name, album_name, year_start, year_end, f'%"{genre}"%'))

                        year_result = cursor.fetchone()
                        yearly_data[year] = year_result['plays'] if year_result else 0

                    albums_data.append({
                        'album': album_key,
                        'yearly_data': yearly_data,
                        'total_plays': album_row['total_plays']
                    })

                return albums_data

            except sqlite3.OperationalError as e:
                print(f"Error en álbumes por género Last.fm: {e}")
                return []

        else:
            print(f"Proveedor no válido: {provider}")
            return []

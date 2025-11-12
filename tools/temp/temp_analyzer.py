#!/usr/bin/env python3
"""
Statistics analyzer module for Last.fm data
Módulo analizador de estadísticas para datos de Last.fm
"""

from collections import Counter, defaultdict
from typing import List, Dict, Optional
from tools.temp.temp_database import Database


class StatsAnalyzer:
    def __init__(self, db: Database):
        self.db = db

    def analyze_period(self, users: List[str], from_timestamp: int, to_timestamp: int, include_novelties: bool = False) -> Dict:
        """
        Analiza estadísticas para un período específico

        Args:
            users: Lista de usuarios
            from_timestamp: Timestamp de inicio
            to_timestamp: Timestamp de fin
            include_novelties: Si incluir análisis de novedades (solo para semanales)

        Returns:
            Dict con todas las estadísticas del período
        """
        print("📊 Analizando estadísticas...")

        # Obtener scrobbles para todos los usuarios
        all_scrobbles = []
        for user in users:
            user_scrobbles = self.db.get_scrobbles(user, from_timestamp, to_timestamp)
            print(f"   {user}: {len(user_scrobbles)} scrobbles")
            all_scrobbles.extend(user_scrobbles)

        if not all_scrobbles:
            print("   ⚠️ No hay scrobbles para el período")
            return {}

        # Inicializar contadores
        artist_counter = Counter()
        track_counter = Counter()
        album_counter = Counter()
        genre_counter = Counter()
        label_counter = Counter()
        year_counter = Counter()

        # Usuarios que han escuchado cada elemento
        artist_users = defaultdict(set)
        track_users = defaultdict(set)
        album_users = defaultdict(set)
        genre_users = defaultdict(set)
        label_users = defaultdict(set)
        year_users = defaultdict(set)

        # Conteo por usuario
        artist_user_counts = defaultdict(lambda: defaultdict(int))
        track_user_counts = defaultdict(lambda: defaultdict(int))
        album_user_counts = defaultdict(lambda: defaultdict(int))
        genre_user_counts = defaultdict(lambda: defaultdict(int))
        label_user_counts = defaultdict(lambda: defaultdict(int))
        year_user_counts = defaultdict(lambda: defaultdict(int))

        # Artistas por usuario para géneros/sellos/años
        genre_user_artists = defaultdict(lambda: defaultdict(set))
        label_user_artists = defaultdict(lambda: defaultdict(set))
        year_user_artists = defaultdict(lambda: defaultdict(set))

        # Top artistas/álbumes por género/sello/año
        genre_artists = defaultdict(Counter)
        genre_albums = defaultdict(Counter)
        label_artists = defaultdict(Counter)
        label_albums = defaultdict(Counter)
        year_artists = defaultdict(Counter)
        year_albums = defaultdict(Counter)

        print("   🔍 Procesando scrobbles...")

        for scrobble in all_scrobbles:
            user = scrobble['user']
            artist = scrobble['artist']
            track = scrobble['track']
            album = scrobble['album']

            # Contadores básicos
            artist_counter[artist] += 1
            track_counter[(artist, track)] += 1
            artist_users[artist].add(user)
            track_users[(artist, track)].add(user)
            artist_user_counts[artist][user] += 1
            track_user_counts[(artist, track)][user] += 1

            if album:
                album_counter[(artist, album)] += 1
                album_users[(artist, album)].add(user)
                album_user_counts[(artist, album)][user] += 1

            # Géneros
            genres = self.db.get_artist_genres(artist)
            for genre in genres:
                genre_counter[genre] += 1
                genre_users[genre].add(user)
                genre_user_counts[genre][user] += 1
                genre_user_artists[genre][user].add(artist)
                genre_artists[genre][artist] += 1
                if album:
                    genre_albums[genre][(artist, album)] += 1

            # Sellos discográficos
            if album:
                label = self.db.get_album_label(artist, album)
                if label:
                    label_counter[label] += 1
                    label_users[label].add(user)
                    label_user_counts[label][user] += 1
                    label_user_artists[label][user].add(artist)
                    label_artists[label][artist] += 1
                    label_albums[label][(artist, album)] += 1

            # Años de lanzamiento
            if album:
                year = self.db.get_album_release_year(artist, album)
                if year:
                    year_counter[year] += 1
                    year_users[year].add(user)
                    year_user_counts[year][user] += 1
                    year_user_artists[year][user].add(artist)
                    year_artists[year][artist] += 1
                    year_albums[year][(artist, album)] += 1

        print("   📈 Filtrando elementos compartidos...")

        # Crear estructura de datos final
        stats = {
            'total_scrobbles': len(all_scrobbles),
            'artists': self._filter_common(
                artist_counter, artist_users, artist_user_counts
            ),
            'tracks': self._filter_common(
                track_counter, track_users, track_user_counts
            ),
            'albums': self._filter_common(
                album_counter, album_users, album_user_counts
            ),
            'genres': self._filter_common(
                genre_counter, genre_users, genre_user_counts,
                genre_user_artists, genre_artists, genre_albums
            ),
            'labels': self._filter_common(
                label_counter, label_users, label_user_counts,
                label_user_artists, label_artists, label_albums
            ),
            'years': self._filter_common(
                year_counter, year_users, year_user_counts,
                year_user_artists, year_artists, year_albums
            )
        }

        # Añadir análisis de novedades si se solicita
        if include_novelties:
            print("   🆕 Analizando novedades...")
            novelties = self._analyze_novelties(users, from_timestamp, to_timestamp)
            stats['novelties'] = novelties

        print(f"   ✅ Análisis completado: {len(all_scrobbles):,} scrobbles procesados")
        return stats

    def _filter_common(self, counter: Counter, users_dict: Dict, user_counts: Dict,
                      user_artists_dict: Optional[Dict] = None,
                      artists_dict: Optional[Dict] = None,
                      albums_dict: Optional[Dict] = None) -> List[Dict]:
        """
        Filtra elementos que han sido escuchados por más de un usuario
        """
        common = []

        for item, count in counter.most_common(50):
            if len(users_dict[item]) > 1:  # Solo elementos compartidos
                # Formatear nombre del item
                if isinstance(item, str):
                    name = item
                elif isinstance(item, int):
                    name = str(item)
                else:
                    # Es una tupla (artist, track/album)
                    name = f"{item[0]} - {item[1]}"

                entry = {
                    'name': name,
                    'count': count,
                    'users': list(users_dict[item]),
                    'user_counts': dict(user_counts[item])
                }

                # Añadir artistas por usuario si existe
                if user_artists_dict and item in user_artists_dict:
                    entry['user_artists'] = {
                        user: list(artists) for user, artists in user_artists_dict[item].items()
                    }

                # Añadir top artistas/álbumes si existe
                if artists_dict and item in artists_dict:
                    entry['top_artists'] = [artist for artist, _ in artists_dict[item].most_common(10)]

                if albums_dict and item in albums_dict:
                    entry['top_albums'] = [f"{album[0]} - {album[1]}" for album, _ in albums_dict[item].most_common(10)]

                common.append(entry)

        return common

    def _analyze_novelties(self, users: List[str], from_timestamp: int, to_timestamp: int) -> Dict:
        """
        Analiza las novedades en el período especificado usando la lógica original mejorada
        """
        print("🔍 Analizando novedades...")

        # Obtener todos los scrobbles del período actual
        all_current_scrobbles = []
        for user in users:
            user_scrobbles = self.db.get_scrobbles(user, from_timestamp, to_timestamp)
            for scrobble in user_scrobbles:
                scrobble['user'] = user
            all_current_scrobbles.extend(user_scrobbles)

        if not all_current_scrobbles:
            return {
                'nuevos': {'artists': [], 'albums': [], 'tracks': []},
                'nuevos_compartidos': {'artists': [], 'albums': [], 'tracks': []},
                'nuevos_para_usuario': {'artists': [], 'albums': [], 'tracks': []}
            }

        # Contadores para elementos del período actual
        current_artists = Counter()
        current_albums = Counter()
        current_tracks_counter = Counter()

        # Usuarios que han escuchado cada elemento en el período actual
        current_artists_users = defaultdict(set)
        current_albums_users = defaultdict(set)
        current_tracks_users = defaultdict(set)

        # Procesar scrobbles actuales
        for scrobble in all_current_scrobbles:
            artist = scrobble['artist']
            album = scrobble['album']
            track_name = f"{artist} - {scrobble['track']}"
            user = scrobble['user']

            current_artists[artist] += 1
            current_artists_users[artist].add(user)

            current_tracks_counter[track_name] += 1
            current_tracks_users[track_name].add(user)

            if album and album.strip():
                album_display = f"{artist} - {album}"
                current_albums[album_display] += 1
                current_albums_users[album_display].add(user)

        # Analizar novedades
        total_users = len(users)
        majority_threshold = max(1, total_users // 2)  # Al menos 50% de usuarios

        nuevos_artists = []
        nuevos_albums = []
        nuevos_tracks = []

        nuevos_compartidos_artists = []
        nuevos_compartidos_albums = []
        nuevos_compartidos_tracks = []

        # NUEVOS ARTISTAS
        print("   🎵 Analizando artistas nuevos...")
        for artist, count in current_artists.most_common(20):
            first_global = self.db.get_global_first_scrobble_date(artist=artist)
            if first_global and first_global >= from_timestamp:
                nuevos_artists.append({
                    'name': artist,
                    'count': count,
                    'users': list(current_artists_users[artist]),
                    'first_date': first_global
                })

                # ¿Es compartido por la mayoría?
                if len(current_artists_users[artist]) >= majority_threshold:
                    nuevos_compartidos_artists.append({
                        'name': artist,
                        'count': count,
                        'users': list(current_artists_users[artist]),
                        'first_date': first_global
                    })

        # NUEVOS ÁLBUMES
        print("   💿 Analizando álbumes nuevos...")
        for album_display, count in current_albums.most_common(20):
            # Extraer artista y álbum
            parts = album_display.split(' - ', 1)
            if len(parts) == 2:
                artist, album = parts
                first_global = self.db.get_global_first_scrobble_date(artist=artist, album=album)
                if first_global and first_global >= from_timestamp:
                    nuevos_albums.append({
                        'name': album_display,
                        'artist': artist,
                        'album': album,
                        'count': count,
                        'users': list(current_albums_users[album_display]),
                        'first_date': first_global
                    })

                    # ¿Es compartido por la mayoría?
                    if len(current_albums_users[album_display]) >= majority_threshold:
                        nuevos_compartidos_albums.append({
                            'name': album_display,
                            'artist': artist,
                            'album': album,
                            'count': count,
                            'users': list(current_albums_users[album_display]),
                            'first_date': first_global
                        })

        # NUEVAS CANCIONES
        print("   🎶 Analizando canciones nuevas...")
        for track_name, count in current_tracks_counter.most_common(20):
            # Extraer artista y canción
            parts = track_name.split(' - ', 1)
            if len(parts) == 2:
                artist, track = parts
                first_global = self.db.get_global_first_scrobble_date(artist=artist, track=track)
                if first_global and first_global >= from_timestamp:
                    nuevos_tracks.append({
                        'name': track_name,
                        'artist': artist,
                        'track': track,
                        'count': count,
                        'users': list(current_tracks_users[track_name]),
                        'first_date': first_global
                    })

                    # ¿Es compartido por la mayoría?
                    if len(current_tracks_users[track_name]) >= majority_threshold:
                        nuevos_compartidos_tracks.append({
                            'name': track_name,
                            'artist': artist,
                            'track': track,
                            'count': count,
                            'users': list(current_tracks_users[track_name]),
                            'first_date': first_global
                        })

        # Ordenar por fecha de primer scrobble (más reciente primero)
        def sort_by_first_date(items):
            return sorted(items, key=lambda x: x['first_date'], reverse=True)

        result = {
            'nuevos': {
                'artists': sort_by_first_date(nuevos_artists),
                'albums': sort_by_first_date(nuevos_albums),
                'tracks': sort_by_first_date(nuevos_tracks)
            },
            'nuevos_compartidos': {
                'artists': sort_by_first_date(nuevos_compartidos_artists),
                'albums': sort_by_first_date(nuevos_compartidos_albums),
                'tracks': sort_by_first_date(nuevos_compartidos_tracks)
            },
            'nuevos_para_usuario': {
                'artists': [],  # Se calculará dinámicamente en el frontend
                'albums': [],
                'tracks': []
            }
        }

        print(f"   ✅ Novedades encontradas:")
        print(f"     - Artistas nuevos: {len(nuevos_artists)}")
        print(f"     - Álbumes nuevos: {len(nuevos_albums)}")
        print(f"     - Canciones nuevas: {len(nuevos_tracks)}")
        print(f"     - Artistas compartidos: {len(nuevos_compartidos_artists)}")
        print(f"     - Álbumes compartidos: {len(nuevos_compartidos_albums)}")
        print(f"     - Canciones compartidas: {len(nuevos_compartidos_tracks)}")

        return result

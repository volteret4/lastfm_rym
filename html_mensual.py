#!/usr/bin/env python3
"""
Last.fm Monthly Stats Generator
Genera estadísticas mensuales de coincidencias entre usuarios
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict
import argparse

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass


class Database:
    def __init__(self, db_path='db/lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_scrobbles(self, user: str, from_timestamp: int, to_timestamp: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user, artist, track, album, timestamp
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
        ''', (user, from_timestamp, to_timestamp))
        return [dict(row) for row in cursor.fetchall()]

    def get_artist_genres(self, artist: str) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT genres FROM artist_genres WHERE artist = ?', (artist,))
        result = cursor.fetchone()
        if result:
            return json.loads(result['genres'])
        return []

    def get_album_label(self, artist: str, album: str) -> str:
        cursor = self.conn.cursor()
        cursor.execute('SELECT label FROM album_labels WHERE artist = ? AND album = ?', (artist, album))
        result = cursor.fetchone()
        return result['label'] if result and result['label'] else None

    def get_album_release_year(self, artist: str, album: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute('SELECT release_year FROM album_release_dates WHERE artist = ? AND album = ?', (artist, album))
        result = cursor.fetchone()
        return result['release_year'] if result and result['release_year'] else None

    def get_first_scrobble_date(self, user: str, artist: str = None, album: str = None, track: str = None) -> int:
        """Obtiene la fecha del primer scrobble de un usuario para un elemento específico"""
        cursor = self.conn.cursor()

        if track and artist:
            # Primer scrobble de una canción específica
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE user = ? AND artist = ? AND track = ?
            ''', (user, artist, track))
        elif album and artist:
            # Primer scrobble de un álbum específico
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE user = ? AND artist = ? AND album = ?
            ''', (user, artist, album))
        elif artist:
            # Primer scrobble de un artista específico
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE user = ? AND artist = ?
            ''', (user, artist))
        else:
            return None

        result = cursor.fetchone()
        return result['first_scrobble'] if result and result['first_scrobble'] else None

    def get_global_first_scrobble_date(self, artist: str = None, album: str = None, track: str = None) -> int:
        """Obtiene la fecha del primer scrobble global (cualquier usuario) para un elemento específico"""
        cursor = self.conn.cursor()

        if track and artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE artist = ? AND track = ?
            ''', (artist, track))
        elif album and artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE artist = ? AND album = ?
            ''', (artist, album))
        elif artist:
            cursor.execute('''
                SELECT MIN(timestamp) as first_scrobble
                FROM scrobbles
                WHERE artist = ?
            ''', (artist,))
        else:
            return None

        result = cursor.fetchone()
        return result['first_scrobble'] if result and result['first_scrobble'] else None

    def close(self):
        self.conn.close()


def analyze_novelties(db, users, from_timestamp, to_timestamp):
    """
    Analiza elementos nuevos en el período especificado
    """
    print("🔍 Analizando novedades...")

    # Obtener todos los scrobbles del período actual
    all_current_tracks = []
    for user in users:
        tracks = db.get_scrobbles(user, from_timestamp, to_timestamp)
        all_current_tracks.extend(tracks)

    if not all_current_tracks:
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
    for track in all_current_tracks:
        artist = track['artist']
        album = track['album']
        track_name = f"{artist} - {track['track']}"
        user = track['user']

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
    for artist, count in current_artists.most_common(20):
        first_global = db.get_global_first_scrobble_date(artist=artist)
        if first_global and first_global >= from_timestamp:
            nuevos_artists.append({
                'name': artist,
                'count': count,
                'users': list(current_artists_users[artist])
            })

            # ¿Es compartido por la mayoría?
            if len(current_artists_users[artist]) >= majority_threshold:
                nuevos_compartidos_artists.append({
                    'name': artist,
                    'count': count,
                    'users': list(current_artists_users[artist])
                })

    # NUEVOS ÁLBUMES
    for album, count in current_albums.most_common(20):
        artist, album_name = album.split(' - ', 1)
        first_global = db.get_global_first_scrobble_date(artist=artist, album=album_name)
        if first_global and first_global >= from_timestamp:
            nuevos_albums.append({
                'name': album,
                'count': count,
                'users': list(current_albums_users[album])
            })

            if len(current_albums_users[album]) >= majority_threshold:
                nuevos_compartidos_albums.append({
                    'name': album,
                    'count': count,
                    'users': list(current_albums_users[album])
                })

    # NUEVAS CANCIONES
    for track, count in current_tracks_counter.most_common(20):
        artist, track_name = track.split(' - ', 1)
        first_global = db.get_global_first_scrobble_date(artist=artist, track=track_name)
        if first_global and first_global >= from_timestamp:
            nuevos_tracks.append({
                'name': track,
                'count': count,
                'users': list(current_tracks_users[track])
            })

            if len(current_tracks_users[track]) >= majority_threshold:
                nuevos_compartidos_tracks.append({
                    'name': track,
                    'count': count,
                    'users': list(current_tracks_users[track])
                })

    print(f"   - Artistas nuevos: {len(nuevos_artists)}")
    print(f"   - Álbumes nuevos: {len(nuevos_albums)}")
    print(f"   - Canciones nuevas: {len(nuevos_tracks)}")
    print(f"   - Artistas nuevos compartidos: {len(nuevos_compartidos_artists)}")
    print(f"   - Álbumes nuevos compartidos: {len(nuevos_compartidos_albums)}")
    print(f"   - Canciones nuevas compartidas: {len(nuevos_compartidos_tracks)}")

    return {
        'nuevos': {
            'artists': nuevos_artists,
            'albums': nuevos_albums,
            'tracks': nuevos_tracks
        },
        'nuevos_compartidos': {
            'artists': nuevos_compartidos_artists,
            'albums': nuevos_compartidos_albums,
            'tracks': nuevos_compartidos_tracks
        },
        'nuevos_para_usuario': {
            'artists': [],  # Se calculará dinámicamente en el frontend
            'albums': [],
            'tracks': []
        },
        'user_first_scrobbles': {}  # Para cálculos dinámicos en frontend
    }


def get_user_novelties(db, user, from_timestamp, to_timestamp, all_users):
    """
    Analiza elementos nuevos para un usuario específico
    (elementos que el usuario escucha por primera vez, pero que ya conocía el 50% del grupo)
    """
    if not user:
        return {'artists': [], 'albums': [], 'tracks': []}

    # Obtener scrobbles del usuario en el período actual
    user_tracks = db.get_scrobbles(user, from_timestamp, to_timestamp)

    if not user_tracks:
        return {'artists': [], 'albums': [], 'tracks': []}

    user_new_artists = []
    user_new_albums = []
    user_new_tracks = []

    # Analizar elementos únicos que el usuario escuchó en el período
    processed_artists = set()
    processed_albums = set()
    processed_tracks = set()

    for track in user_tracks:
        artist = track['artist']
        album = track['album']
        track_name = f"{artist} - {track['track']}"

        # ARTISTAS
        if artist not in processed_artists:
            processed_artists.add(artist)
            user_first = db.get_first_scrobble_date(user, artist=artist)
            global_first = db.get_global_first_scrobble_date(artist=artist)

            # ¿Es nuevo para el usuario pero ya conocido por el grupo?
            if (user_first and user_first >= from_timestamp and
                global_first and global_first < from_timestamp):

                user_new_artists.append({
                    'name': artist,
                    'count': sum(1 for t in user_tracks if t['artist'] == artist),
                    'users': [user]
                })

        # ÁLBUMES
        if album and album.strip():
            album_display = f"{artist} - {album}"
            if album_display not in processed_albums:
                processed_albums.add(album_display)
                user_first = db.get_first_scrobble_date(user, artist=artist, album=album)
                global_first = db.get_global_first_scrobble_date(artist=artist, album=album)

                if (user_first and user_first >= from_timestamp and
                    global_first and global_first < from_timestamp):

                    user_new_albums.append({
                        'name': album_display,
                        'count': sum(1 for t in user_tracks if t['artist'] == artist and t['album'] == album),
                        'users': [user]
                    })

        # CANCIONES
        if track_name not in processed_tracks:
            processed_tracks.add(track_name)
            user_first = db.get_first_scrobble_date(user, artist=artist, track=track['track'])
            global_first = db.get_global_first_scrobble_date(artist=artist, track=track['track'])

            if (user_first and user_first >= from_timestamp and
                global_first and global_first < from_timestamp):

                user_new_tracks.append({
                    'name': track_name,
                    'count': sum(1 for t in user_tracks if t['artist'] == artist and t['track'] == track['track']),
                    'users': [user]
                })

    # Ordenar por count y limitar a top 10
    user_new_artists.sort(key=lambda x: x['count'], reverse=True)
    user_new_albums.sort(key=lambda x: x['count'], reverse=True)
    user_new_tracks.sort(key=lambda x: x['count'], reverse=True)

    return {
        'artists': user_new_artists[:10],  # Top 10
        'albums': user_new_albums[:10],
        'tracks': user_new_tracks[:10]
    }


def generate_monthly_stats(months_ago: int = 0):
    """Genera estadísticas mensuales"""
    users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]

    if not users:
        raise ValueError("LASTFM_USERS no encontrada")

    db = Database()

    # Calcular rango mensual
    now = datetime.now()

    if months_ago > 0:
        # Calcular mes específico del pasado
        target_month = now.month - months_ago
        target_year = now.year

        while target_month <= 0:
            target_month += 12
            target_year -= 1

        from_date = datetime(target_year, target_month, 1, 0, 0, 0)

        # Último día del mes
        if target_month == 12:
            to_date = datetime(target_year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
        else:
            to_date = datetime(target_year, target_month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
    else:
        # Mes actual
        from_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        to_date = now

    from_timestamp = int(from_date.timestamp())
    to_timestamp = int(to_date.timestamp())

    period_label = from_date.strftime('%B %Y')

    print(f"📊 Generando estadísticas mensuales: {period_label}")
    print(f"   Desde: {from_date.strftime('%Y-%m-%d')}")
    print(f"   Hasta: {to_date.strftime('%Y-%m-%d')}")

    # Recopilar scrobbles por usuario
    user_scrobbles = {}
    all_tracks = []
    for user in users:
        tracks = db.get_scrobbles(user, from_timestamp, to_timestamp)
        user_scrobbles[user] = tracks
        all_tracks.extend(tracks)
        print(f"   {user}: {len(tracks)} scrobbles")

    if not all_tracks:
        print("⚠️  No hay scrobbles en este período")
        return None, period_label

    # Calcular estadísticas
    artists_counter = Counter()
    tracks_counter = Counter()
    albums_counter = Counter()
    genres_counter = Counter()
    labels_counter = Counter()
    years_counter = Counter()

    artists_users = defaultdict(set)
    tracks_users = defaultdict(set)
    albums_users = defaultdict(set)
    genres_users = defaultdict(set)
    labels_users = defaultdict(set)
    years_users = defaultdict(set)

    # Para contar scrobbles por usuario en cada categoría
    artists_user_counts = defaultdict(lambda: defaultdict(int))
    tracks_user_counts = defaultdict(lambda: defaultdict(int))
    albums_user_counts = defaultdict(lambda: defaultdict(int))
    genres_user_counts = defaultdict(lambda: defaultdict(int))
    labels_user_counts = defaultdict(lambda: defaultdict(int))
    years_user_counts = defaultdict(lambda: defaultdict(int))

    # Para almacenar artistas que contribuyen a cada categoría por usuario
    genres_user_artists = defaultdict(lambda: defaultdict(set))
    labels_user_artists = defaultdict(lambda: defaultdict(set))
    years_user_artists = defaultdict(lambda: defaultdict(set))

    # Para almacenar álbumes que contribuyen a cada categoría (para análisis detallado)
    genres_albums = defaultdict(lambda: defaultdict(int))  # género -> álbum -> count
    labels_albums = defaultdict(lambda: defaultdict(int))  # sello -> álbum -> count
    years_albums = defaultdict(lambda: defaultdict(int))   # año -> álbum -> count

    # Para almacenar artistas que contribuyen a cada categoría (para análisis detallado)
    genres_artists = defaultdict(lambda: defaultdict(int))  # género -> artista -> count
    labels_artists = defaultdict(lambda: defaultdict(int))  # sello -> artista -> count
    years_artists = defaultdict(lambda: defaultdict(int))   # año -> artista -> count

    processed_artists = set()
    processed_albums = set()

    def get_year_label(year):
        """Convierte un año a etiqueta de año específico"""
        if year is None:
            return None

        if year < 1950:
            return "Antes de 1950"
        else:
            return str(year)

    for track in all_tracks:
        artist = track['artist']
        track_name = f"{artist} - {track['track']}"
        album = track['album']
        user = track['user']

        artists_counter[artist] += 1
        artists_users[artist].add(user)
        artists_user_counts[artist][user] += 1

        tracks_counter[track_name] += 1
        tracks_users[track_name].add(user)
        tracks_user_counts[track_name][user] += 1

        if album and album.strip():  # Solo procesar álbumes que no estén vacíos
            # Mostrar álbum como "artista - álbum"
            album_display = f"{artist} - {album}"
            albums_counter[album_display] += 1
            albums_users[album_display].add(user)
            albums_user_counts[album_display][user] += 1

        # Géneros (procesar solo una vez por artista)
        if artist not in processed_artists:
            genres = db.get_artist_genres(artist)
            for genre in genres:
                genres_counter[genre] += 1
                genres_users[genre].add(user)
                # Para géneros, contamos scrobbles de todos los artistas de ese género del usuario
                for user_track in user_scrobbles[user]:
                    if user_track['artist'] == artist:
                        genres_user_counts[genre][user] += 1
                        genres_user_artists[genre][user].add(artist)
                        # Recopilar información detallada para el análisis
                        genres_artists[genre][artist] += 1
                        if user_track['album'] and user_track['album'].strip():
                            album_display = f"{artist} - {user_track['album']}"
                            genres_albums[genre][album_display] += 1
            processed_artists.add(artist)

        # Sellos y Años (procesar solo una vez por álbum único - artista+album)
        if album and album.strip():
            album_key = f"{artist}|{album}"
            if album_key not in processed_albums:
                album_display = f"{artist} - {album}"

                # Sellos
                label = db.get_album_label(artist, album)
                if label and label.strip():  # Solo procesar sellos que no estén vacíos
                    labels_counter[label] += 1
                    labels_users[label].add(user)
                    # Para sellos, contamos scrobbles de todos los álbumes de ese sello del usuario
                    for user_track in user_scrobbles[user]:
                        if user_track['album'] == album and user_track['artist'] == artist:
                            labels_user_counts[label][user] += 1
                            labels_user_artists[label][user].add(artist)
                            # Recopilar información detallada
                            labels_artists[label][artist] += 1
                            labels_albums[label][album_display] += 1

                # Años
                release_year = db.get_album_release_year(artist, album)
                year_label = get_year_label(release_year)
                if year_label is not None:  # Solo procesar años válidos
                    years_counter[year_label] += 1
                    years_users[year_label].add(user)
                    # Para años, contamos scrobbles de todos los álbumes de ese año del usuario
                    for user_track in user_scrobbles[user]:
                        if user_track['album'] == album and user_track['artist'] == artist:
                            years_user_counts[year_label][user] += 1
                            years_user_artists[year_label][user].add(artist)
                            # Recopilar información detallada
                            years_artists[year_label][artist] += 1
                            years_albums[year_label][album_display] += 1

                processed_albums.add(album_key)

    def filter_common(counter, users_dict, user_counts_dict, user_artists_dict=None, detailed_artists=None, detailed_albums=None):
        result = []
        for item, count in counter.most_common(50):
            if len(users_dict[item]) >= 2:
                entry = {
                    'name': item,
                    'count': count,
                    'users': list(users_dict[item]),
                    'user_counts': dict(user_counts_dict[item])
                }
                if user_artists_dict:
                    entry['user_artists'] = {user: list(artists) for user, artists in user_artists_dict[item].items()}
                if detailed_artists:
                    # Top 10 artistas que más contribuyen a esta categoría
                    top_artists = sorted(detailed_artists[item].items(), key=lambda x: x[1], reverse=True)[:10]
                    entry['top_artists'] = top_artists
                if detailed_albums:
                    # Top 10 álbumes que más contribuyen a esta categoría
                    top_albums = sorted(detailed_albums[item].items(), key=lambda x: x[1], reverse=True)[:10]
                    entry['top_albums'] = top_albums
                result.append(entry)
        return result

    stats = {
        'period_type': 'monthly',
        'period_label': period_label,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_scrobbles': len(all_tracks),
        'artists': filter_common(artists_counter, artists_users, artists_user_counts),
        'tracks': filter_common(tracks_counter, tracks_users, tracks_user_counts),
        'albums': filter_common(albums_counter, albums_users, albums_user_counts),
        'genres': filter_common(genres_counter, genres_users, genres_user_counts, genres_user_artists, genres_artists, genres_albums),
        'labels': filter_common(labels_counter, labels_users, labels_user_counts, labels_user_artists, labels_artists, labels_albums),
        'years': filter_common(years_counter, years_users, years_user_counts, years_user_artists, years_artists, years_albums),
        'users_list': users  # Para análisis dinámico de novedades
    }

    # Añadir análisis de novedades
    novelties = analyze_novelties(db, users, from_timestamp, to_timestamp)
    stats['novelties'] = novelties

    db.close()
    return stats, period_label


def create_html(stats: Dict, users: List[str]) -> str:
    """Crea el HTML para las estadísticas mensuales con categorías desplegables"""
    users_json = json.dumps(users)
    stats_json = json.dumps(stats, indent=2, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Stats - {stats['period_label']}</title>
    <link rel="icon" type="image/png" href="images/music.png">

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
            max-width: 1400px;
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

        .category-filters {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .category-filter {{
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

        .category-filter:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .category-filter.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .period-header {{
            background: #1e1e2e;
            padding: 25px 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        .period-header h2 {{
            color: #cba6f7;
            font-size: 1.5em;
            margin-bottom: 8px;
        }}

        .period-info {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .stats-container {{
            padding: 30px;
        }}

        .categories {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
        }}

        .category {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
            display: none;
        }}

        .category.visible {{
            display: block;
        }}

        .category h3 {{
            color: #cba6f7;
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #cba6f7;
        }}

        .item {{
            padding: 12px;
            margin-bottom: 10px;
            background: #181825;
            border-radius: 8px;
            border-left: 3px solid #45475a;
            transition: all 0.3s;
            cursor: pointer;
        }}

        .item:hover {{
            transform: translateX(5px);
            border-left-color: #cba6f7;
        }}

        .item.highlighted {{
            border-left-color: #cba6f7;
            background: #1e1e2e;
        }}

        .item.clickable {{
            cursor: pointer;
        }}

        .item.clickable:hover {{
            background: #1e1e2e;
        }}

        .item-name {{
            color: #cdd6f4;
            font-weight: 600;
            margin-bottom: 8px;
        }}

        .item-meta {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            font-size: 0.9em;
        }}

        .badge {{
            padding: 4px 10px;
            background: #313244;
            color: #a6adc8;
            border-radius: 6px;
            font-size: 0.85em;
        }}

        .user-badge {{
            padding: 4px 10px;
            background: #45475a;
            color: #cdd6f4;
            border-radius: 6px;
            font-size: 0.85em;
        }}

        .user-badge.highlighted-user {{
            background: #cba6f7;
            color: #1e1e2e;
            font-weight: 600;
        }}

        .item.expandable {{
            cursor: pointer;
            position: relative;
        }}

        .item.expandable:hover {{
            background: #1e1e2e;
        }}

        .item.expandable::after {{
            content: '▼';
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.8em;
            color: #6c7086;
            transition: transform 0.3s;
        }}

        .item.expandable.expanded::after {{
            transform: translateY(-50%) rotate(180deg);
        }}

        .item-details {{
            display: none;
            margin-top: 15px;
            padding: 15px;
            background: #11111b;
            border-radius: 8px;
            border-left: 3px solid #cba6f7;
        }}

        .item-details.visible {{
            display: block;
        }}

        .details-tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }}

        .detail-tab {{
            padding: 6px 12px;
            background: #313244;
            color: #a6adc8;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.3s;
        }}

        .detail-tab:hover {{
            background: #45475a;
        }}

        .detail-tab.active {{
            background: #cba6f7;
            color: #1e1e2e;
        }}

        .detail-content {{
            display: none;
        }}

        .detail-content.visible {{
            display: block;
        }}

        .detail-list {{
            list-style: none;
            padding: 0;
        }}

        .detail-item {{
            padding: 8px 12px;
            background: #181825;
            margin-bottom: 5px;
            border-radius: 6px;
            border-left: 2px solid #45475a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .detail-item-name {{
            color: #cdd6f4;
            font-size: 0.9em;
        }}

        .detail-item-count {{
            color: #a6adc8;
            font-size: 0.8em;
            background: #313244;
            padding: 2px 8px;
            border-radius: 4px;
        }}

        .novelty-section {{
            margin-bottom: 30px;
        }}

        .novelty-section h4 {{
            color: #cba6f7;
            font-size: 1.1em;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid #45475a;
        }}

        .novelty-subsection {{
            margin-bottom: 20px;
        }}

        .novelty-subsection h5 {{
            color: #f9e2af;
            font-size: 0.95em;
            margin-bottom: 10px;
        }}

        .novelty-empty {{
            color: #6c7086;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }}

        .artists-popup {{
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

        .popup-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 999;
        }}

        .popup-header {{
            color: #cba6f7;
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 15px;
            border-bottom: 1px solid #313244;
            padding-bottom: 10px;
        }}

        .popup-close {{
            float: right;
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.2em;
            cursor: pointer;
            padding: 0;
            margin-top: -5px;
        }}

        .popup-close:hover {{
            color: #cba6f7;
        }}

        .artist-list {{
            list-style: none;
            padding: 0;
        }}

        .artist-list li {{
            padding: 8px 12px;
            background: #181825;
            margin-bottom: 5px;
            border-radius: 6px;
            border-left: 3px solid #45475a;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
        }}

        .last-update {{
            text-align: center;
            padding: 20px;
            color: #6c7086;
            font-size: 0.85em;
            border-top: 1px solid #313244;
        }}

        @media (max-width: 768px) {{
            .categories {{
                grid-template-columns: 1fr;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .category-filters {{
                justify-content: center;
            }}

            .artists-popup {{
                max-width: 90%;
                max-height: 80%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📅 Estadísticas Mensuales</h1>
            <p class="subtitle">{stats['period_label']}</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Destacar usuario:</label>
                <select id="userSelect">
                    <option value="">Ninguno</option>
                </select>
            </div>

            <div class="control-group">
                <label>Mostrar categorías:</label>
                <div class="category-filters">
                    <button class="category-filter active" data-category="artists">Artistas</button>
                    <button class="category-filter" data-category="tracks">Canciones</button>
                    <button class="category-filter" data-category="albums">Álbumes</button>
                    <button class="category-filter" data-category="genres">Géneros</button>
                    <button class="category-filter" data-category="labels">Sellos</button>
                    <button class="category-filter" data-category="years">Años</button>
                    <button class="category-filter" data-category="novelties">Novedades</button>
                </div>
            </div>
        </div>

        <div class="period-header">
            <h2>{stats['period_label']}</h2>
            <p class="period-info">
                <span id="dateRange"></span> |
                <span id="totalScrobbles"></span> scrobbles totales
            </p>
        </div>

        <div class="stats-container">
            <div class="categories" id="categoriesContainer">
                <!-- Se llenará dinámicamente -->
            </div>
        </div>

        <div class="last-update">
            Generado: <span id="generatedAt"></span>
        </div>
    </div>

    <script>
        const users = {users_json};
        const stats = {stats_json};

        // Inicializar categorías activas
        let activeCategories = new Set(['artists']); // Por defecto mostrar artistas

        const userSelect = document.getElementById('userSelect');
        users.forEach(user => {{
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        }});

        document.getElementById('dateRange').textContent = `${{stats.from_date}} → ${{stats.to_date}}`;
        document.getElementById('totalScrobbles').textContent = stats.total_scrobbles;
        document.getElementById('generatedAt').textContent = stats.generated_at;

        // Manejar filtros de categorías
        const categoryFilters = document.querySelectorAll('.category-filter');
        categoryFilters.forEach(filter => {{
            filter.addEventListener('click', () => {{
                const category = filter.dataset.category;

                if (activeCategories.has(category)) {{
                    activeCategories.delete(category);
                    filter.classList.remove('active');
                }} else {{
                    activeCategories.add(category);
                    filter.classList.add('active');
                }}

                renderStats();
            }});
        }});

        function showArtistsPopup(itemName, category, user) {{
            const item = stats[category].find(item => item.name === itemName);
            if (!item || !item.user_artists || !item.user_artists[user]) return;

            const artists = item.user_artists[user];

            // Crear overlay
            const overlay = document.createElement('div');
            overlay.className = 'popup-overlay';

            // Crear popup
            const popup = document.createElement('div');
            popup.className = 'artists-popup';

            const header = document.createElement('div');
            header.className = 'popup-header';

            const closeBtn = document.createElement('button');
            closeBtn.className = 'popup-close';
            closeBtn.innerHTML = '×';
            closeBtn.onclick = () => {{
                document.body.removeChild(overlay);
                document.body.removeChild(popup);
            }};

            header.innerHTML = `Artistas de ${{user}} en "${{itemName}}"`;
            header.appendChild(closeBtn);

            const artistList = document.createElement('ul');
            artistList.className = 'artist-list';

            artists.forEach(artist => {{
                const li = document.createElement('li');
                li.textContent = artist;
                artistList.appendChild(li);
            }});

            popup.appendChild(header);
            popup.appendChild(artistList);

            // Cerrar al hacer click en overlay
            overlay.onclick = () => {{
                document.body.removeChild(overlay);
                document.body.removeChild(popup);
            }};

            document.body.appendChild(overlay);
            document.body.appendChild(popup);
        }}

        function createNoveltyItem(item, selectedUser) {{
            const itemDiv = document.createElement('div');
            itemDiv.className = 'item';

            if (selectedUser && item.users.includes(selectedUser)) {{
                itemDiv.classList.add('highlighted');
            }}

            const itemName = document.createElement('div');
            itemName.className = 'item-name';
            itemName.textContent = item.name;
            itemDiv.appendChild(itemName);

            const itemMeta = document.createElement('div');
            itemMeta.className = 'item-meta';

            const countBadge = document.createElement('span');
            countBadge.className = 'badge';
            countBadge.textContent = `${{item.count}} plays`;
            itemMeta.appendChild(countBadge);

            // Ordenar usuarios por scrobbles y mostrar
            const userCounts = item.users.map(user => ({{
                user,
                count: item.user_counts ? item.user_counts[user] || item.count : item.count
            }}));
            userCounts.sort((a, b) => b.count - a.count);

            userCounts.forEach(({{user, count}}) => {{
                const userBadge = document.createElement('span');
                userBadge.className = 'user-badge';
                if (user === selectedUser) {{
                    userBadge.classList.add('highlighted-user');
                }}

                userBadge.textContent = `${{user}} (${{count}})`;
                itemMeta.appendChild(userBadge);
            }});

            itemDiv.appendChild(itemMeta);
            return itemDiv;
        }}

        function toggleItemDetails(itemDiv, item, category) {{
            const detailsDiv = itemDiv.querySelector('.item-details');

            if (detailsDiv.classList.contains('visible')) {{
                // Colapsar
                detailsDiv.classList.remove('visible');
                itemDiv.classList.remove('expanded');
            }} else {{
                // Expandir
                detailsDiv.classList.add('visible');
                itemDiv.classList.add('expanded');

                // Generar contenido si no existe
                if (detailsDiv.children.length === 0) {{
                    generateDetailContent(detailsDiv, item, category);
                }}
            }}
        }}

        function generateDetailContent(detailsDiv, item, category) {{
            // Crear tabs
            const tabsDiv = document.createElement('div');
            tabsDiv.className = 'details-tabs';

            const artistsTab = document.createElement('button');
            artistsTab.className = 'detail-tab active';
            artistsTab.textContent = 'Artistas';
            artistsTab.onclick = () => switchDetailTab(detailsDiv, 'artists');

            const albumsTab = document.createElement('button');
            albumsTab.className = 'detail-tab';
            albumsTab.textContent = 'Álbumes';
            albumsTab.onclick = () => switchDetailTab(detailsDiv, 'albums');

            tabsDiv.appendChild(artistsTab);
            tabsDiv.appendChild(albumsTab);

            // Crear contenidos
            const artistsContent = document.createElement('div');
            artistsContent.className = 'detail-content visible';
            artistsContent.id = 'artists-content';

            const albumsContent = document.createElement('div');
            albumsContent.className = 'detail-content';
            albumsContent.id = 'albums-content';

            // Llenar contenido de artistas
            if (item.top_artists && item.top_artists.length > 0) {{
                const artistsList = document.createElement('ul');
                artistsList.className = 'detail-list';

                item.top_artists.forEach(([artist, count]) => {{
                    const li = document.createElement('li');
                    li.className = 'detail-item';

                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'detail-item-name';
                    nameSpan.textContent = artist;

                    const countSpan = document.createElement('span');
                    countSpan.className = 'detail-item-count';
                    countSpan.textContent = `${{count}} plays`;

                    li.appendChild(nameSpan);
                    li.appendChild(countSpan);
                    artistsList.appendChild(li);
                }});

                artistsContent.appendChild(artistsList);
            }} else {{
                artistsContent.innerHTML = '<p style="color: #6c7086; text-align: center;">No hay datos de artistas</p>';
            }}

            // Llenar contenido de álbumes
            if (item.top_albums && item.top_albums.length > 0) {{
                const albumsList = document.createElement('ul');
                albumsList.className = 'detail-list';

                item.top_albums.forEach(([album, count]) => {{
                    const li = document.createElement('li');
                    li.className = 'detail-item';

                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'detail-item-name';
                    nameSpan.textContent = album;

                    const countSpan = document.createElement('span');
                    countSpan.className = 'detail-item-count';
                    countSpan.textContent = `${{count}} plays`;

                    li.appendChild(nameSpan);
                    li.appendChild(countSpan);
                    albumsList.appendChild(li);
                }});

                albumsContent.appendChild(albumsList);
            }} else {{
                albumsContent.innerHTML = '<p style="color: #6c7086; text-align: center;">No hay datos de álbumes</p>';
            }}

            detailsDiv.appendChild(tabsDiv);
            detailsDiv.appendChild(artistsContent);
            detailsDiv.appendChild(albumsContent);
        }}

        function switchDetailTab(detailsDiv, tabType) {{
            // Actualizar tabs
            const tabs = detailsDiv.querySelectorAll('.detail-tab');
            tabs.forEach(tab => tab.classList.remove('active'));

            const activeTab = Array.from(tabs).find(tab =>
                tab.textContent.toLowerCase() === (tabType === 'artists' ? 'artistas' : 'álbumes')
            );
            if (activeTab) activeTab.classList.add('active');

            // Actualizar contenido
            const contents = detailsDiv.querySelectorAll('.detail-content');
            contents.forEach(content => content.classList.remove('visible'));

            const targetContent = detailsDiv.querySelector(`#${{tabType}}-content`);
            if (targetContent) targetContent.classList.add('visible');
        }}

        // Función para obtener novedades específicas del usuario
        function getUserSpecificNoveltiesWithDB(selectedUser) {{
            if (!selectedUser || !stats.novelties) {{
                return {{ artists: [], albums: [], tracks: [] }};
            }}

            const userNovelties = {{
                artists: [],
                albums: [],
                tracks: []
            }};

            // Timestamps del período
            const fromTimestamp = new Date(stats.from_date).getTime() / 1000;

            // Esta función requeriría una consulta al backend para:
            // SELECT artist FROM user_first_artist_listen
            // WHERE user = ? AND first_timestamp >= ?

            // Por ahora usamos la lógica anterior mejorada
            return getUserSpecificNovelties(selectedUser);
        }}

        // Función para renderizar novedades específicas del usuario
        function renderUserSpecificNovelties(selectedUser, usuarioSection) {{
            const userNovelties = getUserSpecificNovelties(selectedUser);

            // Limpiar contenido anterior
            usuarioSection.innerHTML = '';

            const usuarioTitle = document.createElement('h4');
            usuarioTitle.textContent = `👤 Nuevos para ${{selectedUser}} (ya conocidos por el grupo)`;
            usuarioSection.appendChild(usuarioTitle);

            let hasUserNovelties = false;

            ['artists', 'albums', 'tracks'].forEach(type => {{
                const subsection = document.createElement('div');
                subsection.className = 'novelty-subsection';

                const subsectionTitle = document.createElement('h5');
                subsectionTitle.textContent = type === 'artists' ? 'Artistas' :
                                             type === 'albums' ? 'Álbumes' : 'Canciones';
                subsection.appendChild(subsectionTitle);

                const items = userNovelties[type];
                if (items && items.length > 0) {{
                    hasUserNovelties = true;
                    items.forEach(item => {{
                        const itemDiv = createNoveltyItem(item, selectedUser);
                        subsection.appendChild(itemDiv);
                    }});
                }} else {{
                    const emptyDiv = document.createElement('div');
                    emptyDiv.className = 'novelty-empty';
                    emptyDiv.textContent = 'No hay elementos nuevos detectados para este usuario';
                    subsection.appendChild(emptyDiv);
                }}

                usuarioSection.appendChild(subsection);
            }});

            if (!hasUserNovelties) {{
                const infoDiv = document.createElement('div');
                infoDiv.className = 'novelty-empty';
                infoDiv.innerHTML = `
                    <p style="margin-bottom: 10px;">No se detectaron novedades específicas para ${{selectedUser}}.</p>
                    <p style="font-size: 0.9em; color: #a6adc8;">
                        Esto significa que la mayoría de elementos que escucha ${{selectedUser}}
                        son conocidos por todo el grupo o son novedades globales.
                    </p>
                `;
                usuarioSection.appendChild(infoDiv);
            }}
        }}

        function renderStats() {{
            const selectedUser = userSelect.value;
            const container = document.getElementById('categoriesContainer');
            container.innerHTML = '';

            const categoryOrder = ['artists', 'tracks', 'albums', 'genres', 'labels', 'years', 'novelties'];
            const categoryTitles = {{
                artists: 'Artistas',
                tracks: 'Canciones',
                albums: 'Álbumes',
                genres: 'Géneros',
                labels: 'Sellos',
                years: 'Años',
                novelties: 'Novedades'
            }};

            let hasData = false;

            categoryOrder.forEach(categoryKey => {{
                if (categoryKey === 'novelties') {{
                    // Manejar sección de novedades especialmente
                    if (!stats.novelties) return;

                    hasData = true;
                    const categoryDiv = document.createElement('div');
                    categoryDiv.className = 'category';
                    categoryDiv.dataset.category = categoryKey;

                    if (activeCategories.has(categoryKey)) {{
                        categoryDiv.classList.add('visible');
                    }}

                    const title = document.createElement('h3');
                    title.textContent = categoryTitles[categoryKey];
                    categoryDiv.appendChild(title);

                    // NUEVOS
                    const nuevosSection = document.createElement('div');
                    nuevosSection.className = 'novelty-section';

                    const nuevosTitle = document.createElement('h4');
                    nuevosTitle.textContent = '🆕 Nuevos para todos';
                    nuevosSection.appendChild(nuevosTitle);

                    ['artists', 'albums', 'tracks'].forEach(type => {{
                        const subsection = document.createElement('div');
                        subsection.className = 'novelty-subsection';

                        const subsectionTitle = document.createElement('h5');
                        subsectionTitle.textContent = type === 'artists' ? 'Artistas' :
                                                     type === 'albums' ? 'Álbumes' : 'Canciones';
                        subsection.appendChild(subsectionTitle);

                        const items = stats.novelties.nuevos[type];
                        if (items && items.length > 0) {{
                            items.forEach(item => {{
                                const itemDiv = createNoveltyItem(item, selectedUser);
                                subsection.appendChild(itemDiv);
                            }});
                        }} else {{
                            const emptyDiv = document.createElement('div');
                            emptyDiv.className = 'novelty-empty';
                            emptyDiv.textContent = 'No hay elementos nuevos';
                            subsection.appendChild(emptyDiv);
                        }}

                        nuevosSection.appendChild(subsection);
                    }});

                    categoryDiv.appendChild(nuevosSection);

                    // NUEVOS COMPARTIDOS
                    const compartidosSection = document.createElement('div');
                    compartidosSection.className = 'novelty-section';

                    const compartidosTitle = document.createElement('h4');
                    compartidosTitle.textContent = '👥 Nuevos compartidos (50%+ del grupo)';
                    compartidosSection.appendChild(compartidosTitle);

                    ['artists', 'albums', 'tracks'].forEach(type => {{
                        const subsection = document.createElement('div');
                        subsection.className = 'novelty-subsection';

                        const subsectionTitle = document.createElement('h5');
                        subsectionTitle.textContent = type === 'artists' ? 'Artistas' :
                                                     type === 'albums' ? 'Álbumes' : 'Canciones';
                        subsection.appendChild(subsectionTitle);

                        const items = stats.novelties.nuevos_compartidos[type];
                        if (items && items.length > 0) {{
                            items.forEach(item => {{
                                const itemDiv = createNoveltyItem(item, selectedUser);
                                subsection.appendChild(itemDiv);
                            }});
                        }} else {{
                            const emptyDiv = document.createElement('div');
                            emptyDiv.className = 'novelty-empty';
                            emptyDiv.textContent = 'No hay elementos nuevos compartidos';
                            subsection.appendChild(emptyDiv);
                        }}

                        compartidosSection.appendChild(subsection);
                    }});

                    categoryDiv.appendChild(compartidosSection);

                    // NUEVOS PARA USUARIO SELECCIONADO
                    if (selectedUser) {{
                        const usuarioSection = document.createElement('div');
                        usuarioSection.className = 'novelty-section';

                        // Usar la función real para renderizar novedades del usuario
                        renderUserSpecificNovelties(selectedUser, usuarioSection);

                        categoryDiv.appendChild(usuarioSection);
                    }} else {{
                        const usuarioSection = document.createElement('div');
                        usuarioSection.className = 'novelty-section';

                        const usuarioTitle = document.createElement('h4');
                        usuarioTitle.textContent = '👤 Nuevos para usuario específico';
                        usuarioSection.appendChild(usuarioTitle);

                        const infoDiv = document.createElement('div');
                        infoDiv.className = 'novelty-empty';
                        infoDiv.textContent = 'Selecciona un usuario para ver sus novedades personales';
                        usuarioSection.appendChild(infoDiv);

                        categoryDiv.appendChild(usuarioSection);
                    }}

                    container.appendChild(categoryDiv);
                    return;
                }}

                if (!stats[categoryKey] || stats[categoryKey].length === 0) return;

                hasData = true;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category';
                categoryDiv.dataset.category = categoryKey;

                // Mostrar u ocultar según filtros activos
                if (activeCategories.has(categoryKey)) {{
                    categoryDiv.classList.add('visible');
                }}

                const title = document.createElement('h3');
                title.textContent = categoryTitles[categoryKey];
                categoryDiv.appendChild(title);

                stats[categoryKey].forEach(item => {{
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'item';

                    if (selectedUser && item.users.includes(selectedUser)) {{
                        itemDiv.classList.add('highlighted');
                    }}

                    // Hacer clickeable si es género, año o sello y hay usuario seleccionado (para ver artistas por usuario)
                    const isClickableForUser = ['genres', 'labels', 'years'].includes(categoryKey) &&
                                       selectedUser &&
                                       item.users.includes(selectedUser) &&
                                       item.user_artists &&
                                       item.user_artists[selectedUser];

                    // Hacer expandible si tiene información detallada (para ver top artistas/álbumes)
                    const isExpandable = ['genres', 'labels', 'years'].includes(categoryKey) &&
                                         ((item.top_artists && item.top_artists.length > 0) ||
                                          (item.top_albums && item.top_albums.length > 0));

                    const itemName = document.createElement('div');
                    itemName.className = 'item-name';
                    itemName.textContent = item.name;

                    // Añadir indicadores de funcionalidad
                    if (isClickableForUser) {{
                        const userIndicator = document.createElement('span');
                        userIndicator.style.cssText = 'color: #cba6f7; font-size: 0.8em; margin-left: 8px;';
                        userIndicator.textContent = `[Ver artistas de ${{selectedUser}}]`;
                        itemName.appendChild(userIndicator);
                    }}

                    if (isExpandable) {{
                        itemDiv.classList.add('expandable');
                        const expandIndicator = document.createElement('span');
                        expandIndicator.style.cssText = 'color: #6c7086; font-size: 0.8em; margin-left: 8px;';
                        expandIndicator.textContent = '[Ver detalles]';
                        itemName.appendChild(expandIndicator);
                    }}

                    itemDiv.appendChild(itemName);

                    const itemMeta = document.createElement('div');
                    itemMeta.className = 'item-meta';

                    const countBadge = document.createElement('span');
                    countBadge.className = 'badge';
                    countBadge.textContent = `${{item.count}} plays`;
                    itemMeta.appendChild(countBadge);

                    // Ordenar usuarios por número de scrobbles
                    item.users.sort((a, b) => (item.user_counts[b] || 0) - (item.user_counts[a] || 0));

                    item.users.forEach(user => {{
                        const userBadge = document.createElement('span');
                        userBadge.className = 'user-badge';
                        if (user === selectedUser) {{
                            userBadge.classList.add('highlighted-user');
                        }}

                        // Mostrar usuario con número de scrobbles entre paréntesis
                        const userScrobbles = item.user_counts[user] || 0;
                        userBadge.textContent = `${{user}} (${{userScrobbles}})`;

                        // Click en usuario para ver sus artistas
                        if (isClickableForUser && user === selectedUser) {{
                            userBadge.style.cursor = 'pointer';
                            userBadge.title = `Click para ver artistas de ${{selectedUser}}`;
                            userBadge.onclick = (e) => {{
                                e.stopPropagation();
                                showArtistsPopup(item.name, categoryKey, selectedUser);
                            }};
                        }}

                        itemMeta.appendChild(userBadge);
                    }});

                    itemDiv.appendChild(itemMeta);

                    // Añadir contenedor de detalles si es expandible
                    if (isExpandable) {{
                        const detailsDiv = document.createElement('div');
                        detailsDiv.className = 'item-details';
                        itemDiv.appendChild(detailsDiv);

                        // Click en el item para expandir/colapsar
                        itemDiv.onclick = (e) => {{
                            // No expandir si se hizo click en un badge de usuario
                            if (e.target.classList.contains('user-badge')) {{
                                return;
                            }}
                            toggleItemDetails(itemDiv, item, categoryKey);
                        }};
                    }}

                    categoryDiv.appendChild(itemDiv);
                }});

                container.appendChild(categoryDiv);
            }});

            if (!hasData || activeCategories.size === 0) {{
                const noData = document.createElement('div');
                noData.className = 'no-data';
                noData.textContent = activeCategories.size === 0
                    ? 'Selecciona al menos una categoría para ver las estadísticas'
                    : 'No hay coincidencias para este período';
                container.appendChild(noData);
            }}
        }}

        userSelect.addEventListener('change', renderStats);
        renderStats();
    </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description='Generador de estadísticas mensuales de Last.fm')
    parser.add_argument('--months-ago', type=int, default=0,
                       help='Número de meses atrás (0 = mes actual)')
    args = parser.parse_args()

    try:
        stats, period_label = generate_monthly_stats(args.months_ago)

        if not stats:
            print("❌ No se pudieron generar estadísticas")
            sys.exit(1)

        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        html = create_html(stats, users)

        # Crear directorio docs si no existe
        os.makedirs('docs', exist_ok=True)

        # Nombre del archivo basado en el período
        safe_label = period_label.replace(' ', '_').lower()
        output_file = f'docs/monthly_{safe_label}.html'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"\n✅ Archivo generado: {output_file}")
        print(f"   Coincidencias encontradas:")
        print(f"   - Artistas: {len(stats['artists'])}")
        print(f"   - Canciones: {len(stats['tracks'])}")
        print(f"   - Álbumes: {len(stats['albums'])}")
        print(f"   - Géneros: {len(stats['genres'])}")
        print(f"   - Sellos: {len(stats['labels'])}")
        print(f"   - Años: {len(stats['years'])}")
        print(f"   - Novedades procesadas: {len(stats['novelties']['nuevos']['artists'] + stats['novelties']['nuevos']['albums'] + stats['novelties']['nuevos']['tracks'])}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

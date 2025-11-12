#!/usr/bin/env python3
"""
Last.fm Weekly Stats Generator - 4 Weeks Rotation
Genera estadísticas semanales de coincidencias entre usuarios para las últimas 4 semanas
con sistema de rotación automática de archivos
"""

import os
import sys
import json
import sqlite3
import shutil
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict

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


def analyze_novelties(db: Database, users: List[str], from_timestamp: int, to_timestamp: int) -> Dict:
    """Analiza las novedades en el período especificado"""
    print("🔍 Analizando novedades...")

    all_scrobbles = []
    for user in users:
        user_scrobbles = db.get_scrobbles(user, from_timestamp, to_timestamp)
        for scrobble in user_scrobbles:
            scrobble['user'] = user
        all_scrobbles.extend(user_scrobbles)

    # Elementos únicos por tipo en el período
    period_artists = set()
    period_albums = set()
    period_tracks = set()

    for scrobble in all_scrobbles:
        period_artists.add(scrobble['artist'])
        if scrobble['album']:
            period_albums.add((scrobble['artist'], scrobble['album']))
        period_tracks.add((scrobble['artist'], scrobble['track']))

    print(f"  📊 En período: {len(period_artists)} artistas, {len(period_albums)} álbumes, {len(period_tracks)} canciones")

    # Analizar qué es nuevo para todo el grupo
    nuevos_artists = []
    nuevos_albums = []
    nuevos_tracks = []

    # Nuevos compartidos (>= 50% del grupo los ha escuchado en este período)
    min_users_for_shared = max(1, len(users) // 2)

    nuevos_compartidos_artists = []
    nuevos_compartidos_albums = []
    nuevos_compartidos_tracks = []

    # Verificar artistas
    for artist in period_artists:
        global_first = db.get_global_first_scrobble_date(artist=artist)
        if global_first and global_first >= from_timestamp:
            # Es nuevo para todo el grupo
            users_listening = set()
            for scrobble in all_scrobbles:
                if scrobble['artist'] == artist:
                    users_listening.add(scrobble['user'])

            nuevos_artists.append({
                'name': artist,
                'users': list(users_listening),
                'first_date': global_first
            })

            if len(users_listening) >= min_users_for_shared:
                nuevos_compartidos_artists.append({
                    'name': artist,
                    'users': list(users_listening),
                    'first_date': global_first
                })

    # Verificar álbumes
    for artist, album in period_albums:
        global_first = db.get_global_first_scrobble_date(artist=artist, album=album)
        if global_first and global_first >= from_timestamp:
            users_listening = set()
            for scrobble in all_scrobbles:
                if scrobble['artist'] == artist and scrobble['album'] == album:
                    users_listening.add(scrobble['user'])

            nuevos_albums.append({
                'name': f"{artist} - {album}",
                'artist': artist,
                'album': album,
                'users': list(users_listening),
                'first_date': global_first
            })

            if len(users_listening) >= min_users_for_shared:
                nuevos_compartidos_albums.append({
                    'name': f"{artist} - {album}",
                    'artist': artist,
                    'album': album,
                    'users': list(users_listening),
                    'first_date': global_first
                })

    # Verificar canciones
    for artist, track in period_tracks:
        global_first = db.get_global_first_scrobble_date(artist=artist, track=track)
        if global_first and global_first >= from_timestamp:
            users_listening = set()
            for scrobble in all_scrobbles:
                if scrobble['artist'] == artist and scrobble['track'] == track:
                    users_listening.add(scrobble['user'])

            nuevos_tracks.append({
                'name': f"{artist} - {track}",
                'artist': artist,
                'track': track,
                'users': list(users_listening),
                'first_date': global_first
            })

            if len(users_listening) >= min_users_for_shared:
                nuevos_compartidos_tracks.append({
                    'name': f"{artist} - {track}",
                    'artist': artist,
                    'track': track,
                    'users': list(users_listening),
                    'first_date': global_first
                })

    # Ordenar por fecha de primer scrobble (más reciente primero)
    def sort_by_first_date(items):
        return sorted(items, key=lambda x: x['first_date'], reverse=True)

    return {
        'nuevos': {
            'artists': sort_by_first_date(nuevos_artists),
            'albums': sort_by_first_date(nuevos_albums),
            'tracks': sort_by_first_date(nuevos_tracks)
        },
        'nuevos_compartidos': {
            'artists': sort_by_first_date(nuevos_compartidos_artists),
            'albums': sort_by_first_date(nuevos_compartidos_albums),
            'tracks': sort_by_first_date(nuevos_compartidos_tracks)
        }
    }


def get_week_stats(week_offset: int, users: List[str]) -> tuple:
    """
    Obtiene estadísticas para una semana específica
    week_offset: 0 = esta semana, 1 = semana pasada, etc.
    """
    # Calcular fechas de la semana
    now = datetime.now()
    # Obtener el lunes de esta semana
    days_since_monday = now.weekday()
    monday_this_week = now - timedelta(days=days_since_monday)

    # Calcular el lunes de la semana objetivo
    target_monday = monday_this_week - timedelta(weeks=week_offset)
    target_sunday = target_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

    from_timestamp = int(target_monday.timestamp())
    to_timestamp = int(target_sunday.timestamp())

    # Nombres descriptivos para cada semana
    week_names = [
        "Esta semana",
        "Semana pasada",
        "Hace dos semanas",
        "Hace tres semanas"
    ]

    period_label = week_names[week_offset] if week_offset < len(week_names) else f"Hace {week_offset} semanas"

    print(f"\n📅 {period_label}")
    print(f"   Desde: {target_monday.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Hasta: {target_sunday.strftime('%Y-%m-%d %H:%M')}")

    db = Database()

    # Obtener scrobbles para todos los usuarios
    all_scrobbles = []
    for user in users:
        user_scrobbles = db.get_scrobbles(user, from_timestamp, to_timestamp)
        print(f"   {user}: {len(user_scrobbles)} scrobbles")
        all_scrobbles.extend(user_scrobbles)

    if not all_scrobbles:
        print(f"   ⚠️ No hay scrobbles para {period_label}")
        db.close()
        return {}, period_label

    # Contadores para coincidencias
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
        genres = db.get_artist_genres(artist)
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
            label = db.get_album_label(artist, album)
            if label:
                label_counter[label] += 1
                label_users[label].add(user)
                label_user_counts[label][user] += 1
                label_user_artists[label][user].add(artist)
                label_artists[label][artist] += 1
                label_albums[label][(artist, album)] += 1

        # Años de lanzamiento
        if album:
            year = db.get_album_release_year(artist, album)
            if year:
                year_counter[year] += 1
                year_users[year].add(user)
                year_user_counts[year][user] += 1
                year_user_artists[year][user].add(artist)
                year_artists[year][artist] += 1
                year_albums[year][(artist, album)] += 1

    # Filtrar elementos con más de un usuario
    def filter_common(counter, users_dict, user_counts, user_artists_dict=None, artists_dict=None, albums_dict=None):
        common = []
        for item, count in counter.most_common(50):
            if len(users_dict[item]) > 1:  # Solo elementos compartidos
                entry = {
                    'name': item if isinstance(item, str) else f"{item[0]} - {item[1]}",
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

    # Crear estructura de datos
    artists_counter = {artist: count for artist, count in artist_counter.items()}
    tracks_counter = {f"{track[0]} - {track[1]}": count for track, count in track_counter.items()}
    albums_counter = {f"{album[0]} - {album[1]}": count for album, count in album_counter.items()}
    genres_counter = {genre: count for genre, count in genre_counter.items()}
    labels_counter = {label: count for label, count in label_counter.items()}
    years_counter = {year: count for year, count in year_counter.items()}

    # Usuarios por elemento
    artists_users = {artist: list(users) for artist, users in artist_users.items()}
    tracks_users = {f"{track[0]} - {track[1]}": list(users) for track, users in track_users.items()}
    albums_users = {f"{album[0]} - {album[1]}": list(users) for album, users in album_users.items()}
    genres_users = {genre: list(users) for genre, users in genre_users.items()}
    labels_users = {label: list(users) for label, users in label_users.items()}
    years_users = {year: list(users) for year, users in year_users.items()}

    # User counts
    artists_user_counts = {artist: dict(counts) for artist, counts in artist_user_counts.items()}
    tracks_user_counts = {f"{track[0]} - {track[1]}": dict(counts) for track, counts in track_user_counts.items()}
    albums_user_counts = {f"{album[0]} - {album[1]}": dict(counts) for album, counts in album_user_counts.items()}
    genres_user_counts = {genre: dict(counts) for genre, counts in genre_user_counts.items()}
    labels_user_counts = {label: dict(counts) for label, counts in label_user_counts.items()}
    years_user_counts = {year: dict(counts) for year, counts in year_user_counts.items()}

    stats = {
        'period_label': period_label,
        'from_date': target_monday.strftime('%Y-%m-%d'),
        'to_date': target_sunday.strftime('%Y-%m-%d'),
        'total_scrobbles': len(all_scrobbles),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'artists': filter_common(artist_counter, artist_users, artist_user_counts),
        'tracks': filter_common(track_counter, track_users, track_user_counts),
        'albums': filter_common(album_counter, album_users, album_user_counts),
        'genres': filter_common(genre_counter, genre_users, genre_user_counts, genre_user_artists, genre_artists, genre_albums),
        'labels': filter_common(label_counter, label_users, label_user_counts, label_user_artists, label_artists, label_albums),
        'years': filter_common(year_counter, year_users, year_user_counts, year_user_artists, year_artists, year_albums),
        'users_list': users  # Para análisis dinámico de novedades
    }

    # Añadir análisis de novedades
    novelties = analyze_novelties(db, users, from_timestamp, to_timestamp)
    stats['novelties'] = novelties

    db.close()
    return stats, period_label


def create_html(stats: Dict, users: List[str]) -> str:
    """Crea el HTML para las estadísticas semanales con categorías desplegables"""
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
            padding: 20px 30px;
            border-bottom: 2px solid #cba6f7;
            display: flex;
            justify-content: space-between;
            align-items: center;
            min-height: 80px;
        }}

        .header-content {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex-grow: 1;
        }}

        h1 {{
            font-size: 1.8em;
            color: #cba6f7;
            margin: 0;
            text-align: center;
        }}

        .nav-buttons {{
            display: flex;
            gap: 15px;
            margin-top: 10px;
        }}

        .nav-button {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }}

        .nav-button:hover {{
            border-color: #cba6f7;
            background: #45475a;
            color: #cdd6f4;
        }}

        .nav-button.current {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .user-button {{
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #cba6f7;
            color: #1e1e2e;
            border: none;
            cursor: pointer;
            font-size: 1.2em;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s;
            flex-shrink: 0;
        }}

        .user-button:hover {{
            background: #b4a3e8;
            transform: scale(1.1);
        }}

        .user-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            backdrop-filter: blur(5px);
        }}

        .user-modal-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e1e2e;
            border-radius: 12px;
            padding: 30px;
            width: 90%;
            max-width: 400px;
            border: 2px solid #cba6f7;
        }}

        .user-modal-header {{
            color: #cba6f7;
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 20px;
            text-align: center;
        }}

        .user-modal-close {{
            position: absolute;
            top: 15px;
            right: 20px;
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.5em;
            cursor: pointer;
            padding: 0;
        }}

        .user-modal-close:hover {{
            color: #cba6f7;
        }}

        .user-options {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .user-option {{
            padding: 12px 20px;
            background: #313244;
            border: 2px solid #45475a;
            border-radius: 8px;
            color: #cdd6f4;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
        }}

        .user-option:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .user-option.selected {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .controls {{
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
        }}

        .control-group {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}

        .control-group label {{
            color: #cba6f7;
            font-weight: 600;
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
            background: #1a1826;
        }}

        .item-name {{
            font-weight: 600;
            color: #cdd6f4;
            font-size: 1em;
        }}

        .item-meta {{
            margin-top: 8px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .badge {{
            background: #45475a;
            color: #cdd6f4;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 600;
        }}

        .user-badge {{
            background: #313244;
            color: #a6adc8;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75em;
            border: 1px solid #45475a;
        }}

        .user-badge.highlighted-user {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .expandable {{
            position: relative;
        }}

        .expandable::after {{
            content: '▼';
            position: absolute;
            right: 12px;
            top: 12px;
            color: #6c7086;
            font-size: 0.8em;
        }}

        .expandable.expanded::after {{
            content: '▲';
        }}

        .details {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
            padding: 0 15px;
            margin-top: 10px;
        }}

        .details.expanded {{
            max-height: 400px;
            overflow-y: auto;
            border-top: 1px solid #313244;
            padding-top: 15px;
        }}

        .detail-section {{
            margin-bottom: 15px;
        }}

        .detail-title {{
            color: #f9e2af;
            font-size: 0.9em;
            font-weight: 600;
            margin-bottom: 8px;
        }}

        .detail-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }}

        .detail-item {{
            background: #181825;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            color: #a6adc8;
        }}

        .novelty-section {{
            margin-bottom: 25px;
        }}

        .novelty-section h4 {{
            color: #a6e3a1;
            font-size: 1.05em;
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
            background: rgba(0,0,0,0.8);
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

            header {{
                flex-direction: column;
                gap: 15px;
            }}

            .nav-buttons {{
                order: -1;
            }}

            .user-button {{
                order: 1;
                align-self: flex-end;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <h1>📊 RYM Hispano Estadísticas</h1>
                <div class="nav-buttons">
                    <a href="esta-semana.html" class="nav-button current">TEMPORALES</a>
                    <a href="grupo.html" class="nav-button">GRUPO</a>
                    <a href="index.html" class="nav-button">ACERCA DE</a>
                </div>
            </div>
            <button class="user-button" id="userButton">👤</button>
        </header>

        <!-- Modal de selección de usuario -->
        <div class="user-modal" id="userModal">
            <div class="user-modal-content">
                <button class="user-modal-close" id="userModalClose">×</button>
                <div class="user-modal-header">Seleccionar Usuario</div>
                <div class="user-options" id="userOptions">
                    <!-- Se llenarán dinámicamente -->
                </div>
            </div>
        </div>

        <div class="controls">
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
        // Usuarios reales del entorno LASTFM_USERS
        const availableUsers = {users_json};
        const stats = {stats_json};

        // Funcionalidad del botón de usuario
        function initializeUserSelector() {{
            const userButton = document.getElementById('userButton');
            const userModal = document.getElementById('userModal');
            const userModalClose = document.getElementById('userModalClose');
            const userOptions = document.getElementById('userOptions');

            // Cargar usuario guardado desde localStorage
            let selectedUser = localStorage.getItem('lastfm_selected_user') || '';

            // Llenar opciones de usuarios
            availableUsers.forEach(user => {{
                const option = document.createElement('div');
                option.className = 'user-option';
                option.dataset.user = user;
                option.textContent = user;
                userOptions.appendChild(option);
            }});

            // Marcar opción seleccionada
            updateSelectedUserOption(selectedUser);

            // Event listeners
            userButton.addEventListener('click', () => {{
                userModal.style.display = 'block';
            }});

            userModalClose.addEventListener('click', () => {{
                userModal.style.display = 'none';
            }});

            userModal.addEventListener('click', (e) => {{
                if (e.target === userModal) {{
                    userModal.style.display = 'none';
                }}
            }});

            userOptions.addEventListener('click', (e) => {{
                if (e.target.classList.contains('user-option')) {{
                    const user = e.target.dataset.user;
                    selectedUser = user;

                    // Guardar en localStorage
                    if (user) {{
                        localStorage.setItem('lastfm_selected_user', user);
                    }} else {{
                        localStorage.removeItem('lastfm_selected_user');
                    }}

                    updateSelectedUserOption(user);
                    userModal.style.display = 'none';
                    renderStats(); // Re-renderizar con nuevo usuario
                }}
            }});

            return selectedUser;
        }}

        function updateSelectedUserOption(selectedUser) {{
            const userOptions = document.getElementById('userOptions');
            userOptions.querySelectorAll('.user-option').forEach(option => {{
                option.classList.remove('selected');
                if (option.dataset.user === selectedUser) {{
                    option.classList.add('selected');
                }}
            }});
        }}

        // Inicializar categorías activas
        let activeCategories = new Set(['artists']); // Por defecto mostrar artistas
        let selectedUser = '';

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

            // Fecha de primer scrobble
            const date = new Date(item.first_date * 1000);
            const dateBadge = document.createElement('span');
            dateBadge.className = 'badge';
            dateBadge.textContent = `Primera vez: ${{date.toLocaleDateString('es-ES')}}`;
            itemMeta.appendChild(dateBadge);

            // Usuarios que lo han escuchado
            item.users.forEach(user => {{
                const userBadge = document.createElement('span');
                userBadge.className = 'user-badge';
                if (user === selectedUser) {{
                    userBadge.classList.add('highlighted-user');
                }}
                userBadge.textContent = user;
                itemMeta.appendChild(userBadge);
            }});

            itemDiv.appendChild(itemMeta);
            return itemDiv;
        }}

        function renderStats() {{
            const container = document.getElementById('categoriesContainer');
            container.innerHTML = '';

            const categoryTitles = {{
                artists: 'Artistas Más Escuchados',
                tracks: 'Canciones Más Escuchadas',
                albums: 'Álbumes Más Escuchados',
                genres: 'Géneros Más Escuchados',
                labels: 'Sellos Más Escuchados',
                years: 'Años Más Escuchados',
                novelties: 'Novedades'
            }};

            let hasData = false;

            ['artists', 'tracks', 'albums', 'genres', 'labels', 'years', 'novelties'].forEach(categoryKey => {{
                if (!activeCategories.has(categoryKey)) return;

                // Manejo especial para novedades
                if (categoryKey === 'novelties') {{
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

                        const usuarioTitle = document.createElement('h4');
                        usuarioTitle.textContent = `👤 Nuevos para ${{selectedUser}} (ya conocidos por el grupo)`;
                        usuarioSection.appendChild(usuarioTitle);

                        // Aquí se cargarían dinámicamente los elementos nuevos para el usuario
                        // Por simplicidad, mostrar mensaje indicativo
                        const infoDiv = document.createElement('div');
                        infoDiv.className = 'novelty-empty';
                        infoDiv.textContent = 'Función en desarrollo - se calculará dinámicamente';
                        usuarioSection.appendChild(infoDiv);

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
                            userBadge.addEventListener('click', (e) => {{
                                e.stopPropagation();
                                showArtistsPopup(item.name, categoryKey, user);
                            }});
                        }}

                        itemMeta.appendChild(userBadge);
                    }});

                    itemDiv.appendChild(itemMeta);

                    // Detalles expandibles
                    if (isExpandable) {{
                        const detailsDiv = document.createElement('div');
                        detailsDiv.className = 'details';

                        if (item.top_artists && item.top_artists.length > 0) {{
                            const artistSection = document.createElement('div');
                            artistSection.className = 'detail-section';

                            const artistTitle = document.createElement('div');
                            artistTitle.className = 'detail-title';
                            artistTitle.textContent = 'Top Artistas:';
                            artistSection.appendChild(artistTitle);

                            const artistList = document.createElement('div');
                            artistList.className = 'detail-list';

                            item.top_artists.slice(0, 10).forEach(artist => {{
                                const artistItem = document.createElement('span');
                                artistItem.className = 'detail-item';
                                artistItem.textContent = artist;
                                artistList.appendChild(artistItem);
                            }});

                            artistSection.appendChild(artistList);
                            detailsDiv.appendChild(artistSection);
                        }}

                        if (item.top_albums && item.top_albums.length > 0) {{
                            const albumSection = document.createElement('div');
                            albumSection.className = 'detail-section';

                            const albumTitle = document.createElement('div');
                            albumTitle.className = 'detail-title';
                            albumTitle.textContent = 'Top Álbumes:';
                            albumSection.appendChild(albumTitle);

                            const albumList = document.createElement('div');
                            albumList.className = 'detail-list';

                            item.top_albums.slice(0, 10).forEach(album => {{
                                const albumItem = document.createElement('span');
                                albumItem.className = 'detail-item';
                                albumItem.textContent = album;
                                albumList.appendChild(albumItem);
                            }});

                            albumSection.appendChild(albumList);
                            detailsDiv.appendChild(albumSection);
                        }}

                        itemDiv.appendChild(detailsDiv);

                        // Click para expandir/contraer
                        itemDiv.addEventListener('click', (e) => {{
                            // Solo expandir si no se clickeó en un userBadge clickeable
                            if (e.target.classList.contains('user-badge') && e.target.style.cursor === 'pointer') {{
                                return;
                            }}

                            itemDiv.classList.toggle('expanded');
                            detailsDiv.classList.toggle('expanded');
                        }});
                    }}

                    categoryDiv.appendChild(itemDiv);
                }});

                container.appendChild(categoryDiv);
            }});

            if (!hasData) {{
                const noDataDiv = document.createElement('div');
                noDataDiv.className = 'no-data';
                noDataDiv.textContent = 'No hay datos para mostrar con los filtros seleccionados.';
                container.appendChild(noDataDiv);
            }}
        }}

        // Inicialización
        document.addEventListener('DOMContentLoaded', function() {{
            selectedUser = initializeUserSelector();
            renderStats();
        }});
    </script>
</body>
</html>"""

    return html


def rotate_weekly_files():
    """Rota los archivos semanales: actual → pasada → hace-dos → hace-tres → eliminar"""
    filenames = [
        'esta-semana.html',
        'semana-pasada.html',
        'hace-dos-semanas.html',
        'hace-tres-semanas.html'
    ]

    docs_dir = 'docs'
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)

    # Crear rutas completas
    file_paths = [os.path.join(docs_dir, f) for f in filenames]

    # Rotar archivos existentes
    print("🔄 Rotando archivos semanales...")

    # Eliminar el más antiguo (hace-tres-semanas)
    if os.path.exists(file_paths[3]):
        os.remove(file_paths[3])
        print(f"   ❌ Eliminado: {filenames[3]}")

    # Rotar los demás hacia atrás
    for i in range(2, -1, -1):  # [2, 1, 0]
        if os.path.exists(file_paths[i]):
            shutil.move(file_paths[i], file_paths[i + 1])
            print(f"   📝 {filenames[i]} → {filenames[i + 1]}")


def main():
    print("=" * 60)
    print("GENERADOR DE ESTADÍSTICAS SEMANALES")
    print("=" * 60)

    # Cargar usuarios del .env
    users_env = os.getenv('LASTFM_USERS', '')
    if not users_env:
        print("❌ Error: Variable LASTFM_USERS no encontrada")
        print("💡 Añade LASTFM_USERS=usuario1,usuario2,usuario3 a tu .env")
        sys.exit(1)

    users = [u.strip() for u in users_env.split(',') if u.strip()]
    if not users:
        print("❌ Error: No se encontraron usuarios válidos en LASTFM_USERS")
        sys.exit(1)

    print(f"👥 Usuarios: {', '.join(users)}")

    # Verificar base de datos
    db_path = 'db/lastfm_cache.db'
    if not os.path.exists(db_path):
        print(f"❌ Error: Base de datos no encontrada en {db_path}")
        sys.exit(1)

    print(f"✅ Base de datos encontrada: {db_path}")

    # Rotar archivos existentes
    rotate_weekly_files()

    # Generar estadísticas para esta semana
    print(f"\n📊 Generando estadísticas...")
    stats, period_label = get_week_stats(0, users)  # 0 = esta semana

    if not stats:
        print("❌ No se pudieron generar estadísticas")
        sys.exit(1)

    # Crear HTML
    print("🎨 Generando HTML...")
    html_content = create_html(stats, users)

    # Guardar archivo
    output_file = os.path.join('docs', 'esta-semana.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Archivo generado: {output_file}")
    print(f"📅 Período: {stats['period_label']}")
    print(f"📈 Total scrobbles: {stats['total_scrobbles']:,}")
    print(f"🎵 Artistas únicos: {len(stats['artists'])}")
    print(f"🎶 Canciones únicas: {len(stats['tracks'])}")
    print(f"💿 Álbumes únicos: {len(stats['albums'])}")
    print(f"🎯 Géneros únicos: {len(stats['genres'])}")
    print(f"🏷️ Sellos únicos: {len(stats['labels'])}")
    print(f"📆 Años únicos: {len(stats['years'])}")

    # Mostrar novedades
    novelties = stats['novelties']
    print(f"\n🆕 NOVEDADES:")
    print(f"   Nuevos artistas: {len(novelties['nuevos']['artists'])}")
    print(f"   Nuevos álbumes: {len(novelties['nuevos']['albums'])}")
    print(f"   Nuevas canciones: {len(novelties['nuevos']['tracks'])}")
    print(f"   Artistas compartidos: {len(novelties['nuevos_compartidos']['artists'])}")
    print(f"   Álbumes compartidos: {len(novelties['nuevos_compartidos']['albums'])}")
    print(f"   Canciones compartidas: {len(novelties['nuevos_compartidos']['tracks'])}")

    print("\n" + "=" * 60)
    print("✅ PROCESO COMPLETADO")
    print("=" * 60)


if __name__ == '__main__':
    main()

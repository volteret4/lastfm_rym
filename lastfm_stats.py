#!/usr/bin/env python3
"""
Last.fm Statistics Generator
Generates HTML with weekly, monthly, and yearly statistics for multiple Last.fm users
"""

import os
import sys
import requests
import json
import sqlite3
import argparse
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Set, Optional, Tuple
import time

# Intentar cargar variables de entorno desde .env si no están disponibles
try:
    from dotenv import load_dotenv
    # Primero intentar cargar desde el entorno, si no existe, cargar desde .env
    if not os.getenv('LASTFM_API_KEY') or not os.getenv('DISCOGS_TOKEN') or not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    # Si python-dotenv no está instalado, solo usar variables de entorno del sistema
    pass


class Database:
    def __init__(self, db_path='lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()

        # Tabla de scrobbles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrobbles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                artist TEXT NOT NULL,
                track TEXT NOT NULL,
                album TEXT,
                timestamp INTEGER NOT NULL,
                UNIQUE(user, timestamp, artist, track)
            )
        ''')

        # Índice para búsquedas rápidas
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_user_timestamp
            ON scrobbles(user, timestamp)
        ''')

        # Tabla de géneros
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_genres (
                artist TEXT PRIMARY KEY,
                genres TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        ''')

        # Tabla de sellos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS album_labels (
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                label TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (artist, album)
            )
        ''')

        self.conn.commit()

    def get_last_scrobble_timestamp(self, user: str) -> int:
        """Obtiene el timestamp del último scrobble guardado para un usuario"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT MAX(timestamp) as max_ts FROM scrobbles WHERE user = ?',
            (user,)
        )
        result = cursor.fetchone()
        return result['max_ts'] if result['max_ts'] else 0

    def save_scrobbles(self, scrobbles: List[Dict]):
        """Guarda scrobbles en la base de datos"""
        cursor = self.conn.cursor()
        for scrobble in scrobbles:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO scrobbles (user, artist, track, album, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    scrobble['user'],
                    scrobble['artist'],
                    scrobble['track'],
                    scrobble['album'],
                    scrobble['timestamp']
                ))
            except sqlite3.IntegrityError:
                pass  # Ya existe
        self.conn.commit()

    def get_scrobbles(self, user: str, from_timestamp: int, to_timestamp: int) -> List[Dict]:
        """Obtiene scrobbles de la base de datos"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user, artist, track, album, timestamp
            FROM scrobbles
            WHERE user = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
        ''', (user, from_timestamp, to_timestamp))

        return [dict(row) for row in cursor.fetchall()]

    def get_artist_genres(self, artist: str) -> Optional[List[str]]:
        """Obtiene géneros de un artista desde la cache"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT genres FROM artist_genres WHERE artist = ?',
            (artist,)
        )
        result = cursor.fetchone()
        if result:
            return json.loads(result['genres'])
        return None

    def save_artist_genres(self, artist: str, genres: List[str]):
        """Guarda géneros de un artista en la cache"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO artist_genres (artist, genres, updated_at)
            VALUES (?, ?, ?)
        ''', (artist, json.dumps(genres), int(time.time())))
        self.conn.commit()

    def get_album_label(self, artist: str, album: str) -> Optional[str]:
        """Obtiene el sello de un álbum desde la cache"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT label FROM album_labels WHERE artist = ? AND album = ?',
            (artist, album)
        )
        result = cursor.fetchone()
        return result['label'] if result else None

    def save_album_label(self, artist: str, album: str, label: Optional[str]):
        """Guarda el sello de un álbum en la cache"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO album_labels (artist, album, label, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (artist, album, label, int(time.time())))
        self.conn.commit()

    def close(self):
        self.conn.close()


class LastFMStatsGenerator:
    def __init__(self):
        self.lastfm_api_key = os.getenv('LASTFM_API_KEY')
        self.discogs_token = os.getenv('DISCOGS_TOKEN', '')  # Opcional
        self.users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]

        if not self.lastfm_api_key:
            raise ValueError("LASTFM_API_KEY no encontrada en variables de entorno o .env")
        if not self.users:
            raise ValueError("LASTFM_USERS no encontrada en variables de entorno o .env")

        self.lastfm_base_url = "http://ws.audioscrobbler.com/2.0/"
        self.discogs_base_url = "https://api.discogs.com"

        # Base de datos para caching
        self.db = Database()

        # Caché en memoria para esta ejecución
        self.genre_cache = {}
        self.label_cache = {}

    def get_lastfm_data(self, method: str, params: Dict) -> Optional[Dict]:
        """Realiza una petición a la API de Last.fm"""
        params.update({
            'api_key': self.lastfm_api_key,
            'format': 'json',
            'method': method
        })

        try:
            response = requests.get(self.lastfm_base_url, params=params, timeout=10)

            # Verificar códigos de error HTTP
            if response.status_code == 403:
                print(f"\n❌ Error 403: API Key inválida o límite de rate excedido")
                return None
            elif response.status_code == 404:
                print(f"\n❌ Error 404: Endpoint no encontrado")
                return None
            elif response.status_code == 429:
                print(f"\n❌ Error 429: Demasiadas peticiones. Esperando 60 segundos...")
                time.sleep(60)
                return None
            elif response.status_code != 200:
                print(f"\n❌ Error HTTP {response.status_code}")
                return None

            return response.json()

        except requests.exceptions.Timeout:
            print(f"\n⚠️  Timeout en petición a Last.fm API")
            return None
        except requests.exceptions.ConnectionError:
            print(f"\n⚠️  Error de conexión con Last.fm API")
            return None
        except requests.exceptions.JSONDecodeError:
            print(f"\n⚠️  Respuesta inválida de Last.fm API")
            return None
        except Exception as e:
            print(f"\n❌ Error inesperado en petición Last.fm: {e}")
            return None

    def get_recent_tracks(self, user: str, from_timestamp: int, to_timestamp: int) -> List[Dict]:
        """Obtiene los scrobbles recientes de un usuario, usando cache cuando es posible"""

        # Primero intentar obtener de la base de datos
        cached_tracks = self.db.get_scrobbles(user, from_timestamp, to_timestamp)

        # Obtener el último timestamp en cache
        last_cached_timestamp = self.db.get_last_scrobble_timestamp(user)

        # Si tenemos todo en cache, retornar
        if cached_tracks and last_cached_timestamp >= to_timestamp:
            print(f"   ✓ {len(cached_tracks)} scrobbles obtenidos desde cache")
            return cached_tracks

        # Si no, obtener los nuevos desde la API
        fetch_from = max(last_cached_timestamp + 1, from_timestamp)

        if fetch_from > to_timestamp:
            print(f"   ✓ 0 scrobbles (fuera de rango)")
            return []

        print(f"   Obteniendo nuevos scrobbles de {user}...", end=' ')

        tracks = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            data = self.get_lastfm_data('user.getrecenttracks', {
                'user': user,
                'limit': 200,
                'page': page,
                'from': fetch_from,
                'to': to_timestamp
            })

            if not data:
                print(f"\n   ⚠️  No se pudo obtener datos (página {page})")
                break

            # Verificar si hay error en la respuesta
            if 'error' in data:
                error_code = data.get('error', 'unknown')
                error_msg = data.get('message', 'Error desconocido')
                print(f"\n   ❌ Error de API: {error_msg} (código {error_code})")

                if error_code == 6:
                    print(f"   → El usuario '{user}' no existe o no es público")
                elif error_code == 17:
                    print(f"   → El usuario '{user}' tiene el perfil privado")

                break

            if 'recenttracks' not in data:
                print(f"\n   ⚠️  Respuesta inesperada de la API")
                break

            # Si es la primera página, obtener total de páginas
            if page == 1:
                total_pages = int(data['recenttracks']['@attr'].get('totalPages', 1))
                total_tracks = int(data['recenttracks']['@attr'].get('total', 0))
                print(f"({total_tracks} nuevos scrobbles)")

            track_data = data['recenttracks'].get('track', [])

            # Si solo hay un track, la API lo devuelve como dict en lugar de lista
            if isinstance(track_data, dict):
                track_data = [track_data]

            for track in track_data:
                # Filtrar tracks que están "now playing"
                if '@attr' in track and 'nowplaying' in track['@attr']:
                    continue

                # Verificar que el track tiene fecha
                if 'date' not in track:
                    continue

                tracks.append({
                    'artist': track['artist'].get('#text', '') if isinstance(track['artist'], dict) else str(track.get('artist', '')),
                    'track': track.get('name', ''),
                    'album': track['album'].get('#text', '') if isinstance(track['album'], dict) else str(track.get('album', '')),
                    'timestamp': int(track['date']['uts']) if 'date' in track else 0,
                    'user': user
                })

            page += 1
            time.sleep(0.25)

        # Guardar nuevos scrobbles en la base de datos
        if tracks:
            self.db.save_scrobbles(tracks)
            print(f"   ✓ {len(tracks)} nuevos scrobbles guardados en cache")

        # Combinar con los que ya teníamos en cache
        all_tracks = cached_tracks + tracks
        return all_tracks

    def get_artist_tags(self, artist: str) -> List[str]:
        """Obtiene los géneros/tags de un artista, primero desde cache"""
        # Verificar cache en memoria
        if artist in self.genre_cache:
            return self.genre_cache[artist]

        # Verificar cache en base de datos
        cached_genres = self.db.get_artist_genres(artist)
        if cached_genres is not None:
            self.genre_cache[artist] = cached_genres
            return cached_genres

        # Si no está en cache, obtener de la API
        data = self.get_lastfm_data('artist.gettoptags', {'artist': artist})

        tags = []
        if data and 'toptags' in data and 'tag' in data['toptags']:
            tags = [tag['name'] for tag in data['toptags']['tag'][:5]]

        # Guardar en cache
        self.genre_cache[artist] = tags
        self.db.save_artist_genres(artist, tags)

        time.sleep(0.2)
        return tags

    def get_album_label(self, artist: str, album: str) -> Optional[str]:
        """Obtiene el sello discográfico, primero desde cache"""
        if not self.discogs_token or not album:
            return None

        cache_key = f"{artist}|{album}"

        # Verificar cache en memoria
        if cache_key in self.label_cache:
            return self.label_cache[cache_key]

        # Verificar cache en base de datos
        cached_label = self.db.get_album_label(artist, album)
        if cached_label is not None:
            self.label_cache[cache_key] = cached_label
            return cached_label if cached_label != '' else None

        # Si no está en cache, obtener de Discogs
        try:
            headers = {'Authorization': f'Discogs token={self.discogs_token}'}
            params = {'q': f'{artist} {album}', 'type': 'release', 'per_page': 1}

            response = requests.get(
                f"{self.discogs_base_url}/database/search",
                params=params,
                headers=headers,
                timeout=10
            )

            label = None
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    label = data['results'][0].get('label', [None])[0]

            # Guardar en cache (incluso si es None)
            self.label_cache[cache_key] = label
            self.db.save_album_label(artist, album, label if label else '')

            time.sleep(1)
            return label

        except Exception as e:
            print(f"Error obteniendo sello de Discogs: {e}")
            return None

    def calculate_statistics(self, period_type: str, specific_date: Optional[datetime] = None) -> Dict:
        """Calcula estadísticas para el período especificado"""
        now = specific_date if specific_date else datetime.now()

        # Determinar el rango de tiempo
        if period_type == 'weekly':
            from_date = now - timedelta(days=7)
        elif period_type == 'monthly':
            from_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period_type == 'yearly':
            from_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(f"Tipo de período no válido: {period_type}")

        from_timestamp = int(from_date.timestamp())
        to_timestamp = int(now.timestamp())

        # Recopilar todos los scrobbles
        all_tracks = []
        for user in self.users:
            print(f"Obteniendo scrobbles de {user} ({period_type})...")
            tracks = self.get_recent_tracks(user, from_timestamp, to_timestamp)
            all_tracks.extend(tracks)

        if not all_tracks:
            return {
                'period_type': period_type,
                'from_date': from_date.strftime('%Y-%m-%d'),
                'to_date': now.strftime('%Y-%m-%d'),
                'total_scrobbles': 0,
                'artists': [],
                'tracks': [],
                'albums': [],
                'genres': [],
                'labels': []
            }

        # Contar coincidencias
        artists_counter = Counter()
        tracks_counter = Counter()
        albums_counter = Counter()
        genres_counter = Counter()
        labels_counter = Counter()

        # Rastrear qué usuarios escucharon cada item
        artists_users = defaultdict(set)
        tracks_users = defaultdict(set)
        albums_users = defaultdict(set)
        genres_users = defaultdict(set)
        labels_users = defaultdict(set)

        processed_artists = set()

        for track in all_tracks:
            artist = track['artist']
            track_name = f"{artist} - {track['track']}"
            album = track['album']
            user = track['user']

            artists_counter[artist] += 1
            artists_users[artist].add(user)

            tracks_counter[track_name] += 1
            tracks_users[track_name].add(user)

            if album:
                albums_counter[album] += 1
                albums_users[album].add(user)

            # Obtener géneros (solo una vez por artista)
            if artist not in processed_artists:
                print(f"Obteniendo géneros para: {artist}")
                tags = self.get_artist_tags(artist)
                for tag in tags:
                    genres_counter[tag] += 1
                    genres_users[tag].add(user)
                processed_artists.add(artist)

        # Obtener sellos (solo si Discogs está configurado)
        if self.discogs_token:
            processed_albums = set()
            for track in all_tracks:
                album_key = f"{track['artist']}|{track['album']}"
                if track['album'] and album_key not in processed_albums:
                    print(f"Obteniendo sello para: {track['artist']} - {track['album']}")
                    label = self.get_album_label(track['artist'], track['album'])
                    if label:
                        labels_counter[label] += 1
                        labels_users[label].add(track['user'])
                    processed_albums.add(album_key)

        # Filtrar solo coincidencias (2+ usuarios)
        def filter_common(counter, users_dict):
            return [
                {
                    'name': item,
                    'count': count,
                    'users': list(users_dict[item])
                }
                for item, count in counter.most_common(50)
                if len(users_dict[item]) >= 2
            ]

        return {
            'period_type': period_type,
            'from_date': from_date.strftime('%Y-%m-%d'),
            'to_date': now.strftime('%Y-%m-%d'),
            'total_scrobbles': len(all_tracks),
            'artists': filter_common(artists_counter, artists_users),
            'tracks': filter_common(tracks_counter, tracks_users),
            'albums': filter_common(albums_counter, albums_users),
            'genres': filter_common(genres_counter, genres_users),
            'labels': filter_common(labels_counter, labels_users) if self.discogs_token else []
        }

    def generate_html(self, stats_data: Dict, args) -> str:
        """Genera el HTML con las estadísticas"""
        now = datetime.now()

        # Determinar qué estadísticas generar según los argumentos
        stats_to_include = {}

        # Estadísticas semanales (siempre)
        if not args.old_monthly and not args.old_yearly:
            print("\n=== Generando estadísticas semanales ===")
            stats_to_include['weekly'] = self.calculate_statistics('weekly')

        # Estadísticas mensuales
        if args.old_monthly:
            # Calcular meses pasados
            for months_ago in args.old_monthly:
                target_date = now - timedelta(days=30 * months_ago)
                target_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                period_key = f"monthly_{target_date.strftime('%Y%m')}"
                print(f"\n=== Generando estadísticas mensuales de {target_date.strftime('%B %Y')} ===")
                stats = self.calculate_statistics('monthly', target_date)
                stats['period_label'] = target_date.strftime('%B %Y')
                stats_to_include[period_key] = stats
        elif now.day == 1:
            # Solo generar mes actual el día 1
            print("\n=== Generando estadísticas mensuales ===")
            stats_to_include['monthly'] = self.calculate_statistics('monthly')

        # Estadísticas anuales
        if args.old_yearly:
            # Calcular años pasados
            for years_ago in args.old_yearly:
                target_date = now.replace(year=now.year - years_ago, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                period_key = f"yearly_{target_date.year}"
                print(f"\n=== Generando estadísticas anuales de {target_date.year} ===")
                stats = self.calculate_statistics('yearly', target_date)
                stats['period_label'] = str(target_date.year)
                stats_to_include[period_key] = stats
        elif now.month == 1 and now.day == 1:
            # Solo generar año actual el 1 de enero
            print("\n=== Generando estadísticas anuales ===")
            stats_to_include['yearly'] = self.calculate_statistics('yearly')

        # Mantener estadísticas previas si existen
        for period in stats_data:
            if period not in stats_to_include:
                stats_to_include[period] = stats_data[period]

        return self._create_html_template(stats_to_include)

    def _create_html_template(self, stats: Dict) -> str:
        """Crea el template HTML con las estadísticas"""
        users_json = json.dumps(self.users)
        stats_json = json.dumps(stats, indent=2, ensure_ascii=False)

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Stats - Coincidencias</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}

        .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .controls {{
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }}

        .control-group {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            justify-content: center;
            align-items: center;
        }}

        label {{
            font-weight: 600;
            color: #495057;
        }}

        select {{
            padding: 10px 20px;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            font-size: 1em;
            background: white;
            cursor: pointer;
            transition: all 0.3s;
        }}

        select:hover {{
            border-color: #667eea;
        }}

        select:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}

        .stats-container {{
            padding: 40px;
        }}

        .period-section {{
            margin-bottom: 50px;
        }}

        .period-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 30px;
        }}

        .period-header h2 {{
            font-size: 1.8em;
            margin-bottom: 5px;
        }}

        .period-info {{
            font-size: 0.95em;
            opacity: 0.9;
        }}

        .categories {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 30px;
        }}

        .category {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .category h3 {{
            font-size: 1.3em;
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}

        .item {{
            padding: 12px;
            margin-bottom: 10px;
            background: white;
            border-radius: 8px;
            border-left: 4px solid #dee2e6;
            transition: all 0.3s;
        }}

        .item:hover {{
            transform: translateX(5px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .item.highlighted {{
            border-left-color: #ffd700;
            background: #fffbea;
        }}

        .item-name {{
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 5px;
        }}

        .item-meta {{
            display: flex;
            gap: 15px;
            font-size: 0.9em;
            color: #718096;
        }}

        .badge {{
            display: inline-block;
            padding: 3px 10px;
            background: #e9ecef;
            border-radius: 12px;
            font-size: 0.85em;
        }}

        .users-list {{
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }}

        .user-badge {{
            padding: 3px 10px;
            background: #667eea;
            color: white;
            border-radius: 12px;
            font-size: 0.85em;
        }}

        .user-badge.highlighted-user {{
            background: #ffd700;
            color: #333;
            font-weight: 700;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #718096;
            font-style: italic;
        }}

        .last-update {{
            text-align: center;
            padding: 20px;
            color: #718096;
            font-size: 0.9em;
            border-top: 2px solid #e9ecef;
        }}

        @media (max-width: 768px) {{
            .categories {{
                grid-template-columns: 1fr;
            }}

            h1 {{
                font-size: 1.8em;
            }}

            .control-group {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 Last.fm Statistics</h1>
            <p class="subtitle">Coincidencias musicales entre usuarios</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Destacar usuario:</label>
                <select id="userSelect">
                    <option value="">Ninguno</option>
                </select>

                <label for="periodSelect">Período:</label>
                <select id="periodSelect">
                    <!-- Se llenará dinámicamente con JavaScript -->
                </select>
            </div>
        </div>

        <div class="stats-container" id="statsContainer">
            <!-- Se llenará dinámicamente con JavaScript -->
        </div>

        <div class="last-update">
            Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>

    <script>
        const users = {users_json};
        const statsData = {stats_json};

        // Inicializar selector de usuarios
        const userSelect = document.getElementById('userSelect');
        users.forEach(user => {{
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        }});

        // Inicializar selector de períodos con los disponibles
        const periodSelect = document.getElementById('periodSelect');
        const availablePeriods = Object.keys(statsData);

        // Limpiar opciones por defecto excepto "all"
        periodSelect.innerHTML = '<option value="all">Todos los períodos</option>';

        // Añadir períodos disponibles
        const periodLabels = {{
            'weekly': 'Semanal',
            'monthly': 'Mensual',
            'yearly': 'Anual'
        }};

        availablePeriods.forEach(period => {{
            const option = document.createElement('option');
            option.value = period;

            if (period.startsWith('monthly_')) {{
                option.textContent = `Mensual - ${{statsData[period].period_label || period.replace('monthly_', '')}}`;
            }} else if (period.startsWith('yearly_')) {{
                option.textContent = `Anual - ${{statsData[period].period_label || period.replace('yearly_', '')}}`;
            }} else {{
                option.textContent = periodLabels[period] || period;
            }}

            periodSelect.appendChild(option);
        }});

        // Función para renderizar las estadísticas
        function renderStats() {{
            const selectedUser = userSelect.value;
            const selectedPeriod = document.getElementById('periodSelect').value;
            const container = document.getElementById('statsContainer');

            container.innerHTML = '';

            const periodsToShow = selectedPeriod === 'all'
                ? Object.keys(statsData)
                : [selectedPeriod];

            periodsToShow.forEach(period => {{
                if (!statsData[period]) return;

                const stats = statsData[period];
                const section = document.createElement('div');
                section.className = 'period-section';

                const periodTitles = {{
                    weekly: 'Semanal',
                    monthly: 'Mensual',
                    yearly: 'Anual'
                }};

                // Detectar períodos personalizados
                let periodTitle = periodTitles[period] || period;
                if (period.startsWith('monthly_')) {{
                    periodTitle = `Mensual - ${{stats.period_label || period.replace('monthly_', '')}}`;
                }} else if (period.startsWith('yearly_')) {{
                    periodTitle = `Anual - ${{stats.period_label || period.replace('yearly_', '')}}`;
                }}

                section.innerHTML = `
                    <div class="period-header">
                        <h2>${{periodTitle}}</h2>
                        <p class="period-info">
                            ${{stats.from_date}} → ${{stats.to_date}} |
                            ${{stats.total_scrobbles}} scrobbles totales
                        </p>
                    </div>
                `;

                const categories = document.createElement('div');
                categories.className = 'categories';

                const categoryOrder = ['artists', 'tracks', 'albums', 'genres', 'labels'];
                const categoryTitles = {{
                    artists: 'Artistas',
                    tracks: 'Canciones',
                    albums: 'Álbumes',
                    genres: 'Géneros',
                    labels: 'Sellos'
                }};

                categoryOrder.forEach(categoryKey => {{
                    if (!stats[categoryKey] || stats[categoryKey].length === 0) return;

                    const categoryDiv = document.createElement('div');
                    categoryDiv.className = 'category';

                    const title = document.createElement('h3');
                    title.textContent = categoryTitles[categoryKey];
                    categoryDiv.appendChild(title);

                    stats[categoryKey].forEach(item => {{
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

                        const usersList = document.createElement('div');
                        usersList.className = 'users-list';

                        item.users.forEach(user => {{
                            const userBadge = document.createElement('span');
                            userBadge.className = 'user-badge';
                            if (user === selectedUser) {{
                                userBadge.classList.add('highlighted-user');
                            }}
                            userBadge.textContent = user;
                            usersList.appendChild(userBadge);
                        }});

                        itemMeta.appendChild(usersList);
                        itemDiv.appendChild(itemMeta);

                        categoryDiv.appendChild(itemDiv);
                    }});

                    categories.appendChild(categoryDiv);
                }});

                if (categories.children.length === 0) {{
                    const noData = document.createElement('div');
                    noData.className = 'no-data';
                    noData.textContent = 'No hay coincidencias para este período';
                    section.appendChild(noData);
                }} else {{
                    section.appendChild(categories);
                }}

                container.appendChild(section);
            }});
        }}

        // Event listeners
        userSelect.addEventListener('change', renderStats);
        document.getElementById('periodSelect').addEventListener('change', renderStats);

        // Renderizar inicialmente
        renderStats();
    </script>
</body>
</html>"""

        return html


def main():
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description='Generador de estadísticas de Last.fm con coincidencias entre usuarios'
    )
    parser.add_argument(
        '--old-monthly',
        type=int,
        nargs='+',
        metavar='N',
        help='Generar estadísticas mensuales de N meses atrás (ej: --old-monthly 1 2 3)'
    )
    parser.add_argument(
        '--old-yearly',
        type=int,
        nargs='+',
        metavar='N',
        help='Generar estadísticas anuales de N años atrás (ej: --old-yearly 1 2)'
    )

    args = parser.parse_args()

    # Cargar estadísticas previas si existen
    stats_file = 'stats_data.json'
    previous_stats = {}

    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                previous_stats = json.load(f)
        except:
            pass

    # Generar estadísticas
    generator = LastFMStatsGenerator()

    try:
        html_content = generator.generate_html(previous_stats, args)

        # Guardar HTML
        output_file = 'index.html'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"\n✅ HTML generado exitosamente: {output_file}")
        print(f"📊 Usuarios incluidos: {', '.join(generator.users)}")
        print(f"🔑 Discogs {'activado' if generator.discogs_token else 'desactivado'}")
        print(f"💾 Base de datos: lastfm_cache.db")

    finally:
        # Cerrar la base de datos
        generator.db.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

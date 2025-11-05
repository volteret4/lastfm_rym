#!/usr/bin/env python3
"""
Last.fm Monthly Stats Generator
Genera estadÃ­sticas mensuales de coincidencias entre usuarios
"""

import os
import sys
import json
import sqlite3
import argparse
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
    def __init__(self, db_path='lastfm_cache.db'):
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
        return result['label']

    def close(self):
        self.conn.close()


def generate_monthly_stats(months_ago: int = 0):
    """Genera estadÃ­sticas mensuales"""
    users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]

    if not users:
        raise ValueError("LASTFM_USERS no encontrada")

    db = Database()

    # Calcular rango mensual
    now = datetime.now()

    if months_ago > 0:
        # Calcular mes especÃ­fico del pasado
        target_month = now.month - months_ago
        target_year = now.year

        while target_month <= 0:
            target_month += 12
            target_year -= 1

        from_date = datetime(target_year, target_month, 1, 0, 0, 0)

        # Ãšltimo dÃ­a del mes
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

    print(f"ðŸ“Š Generando estadÃ­sticas mensuales: {period_label}")
    print(f"   Desde: {from_date.strftime('%Y-%m-%d')}")
    print(f"   Hasta: {to_date.strftime('%Y-%m-%d')}")

    # Recopilar scrobbles
    all_tracks = []
    for user in users:
        tracks = db.get_scrobbles(user, from_timestamp, to_timestamp)
        all_tracks.extend(tracks)
        print(f"   {user}: {len(tracks)} scrobbles")

    if not all_tracks:
        print("âš ï¸  No hay scrobbles en este perÃ­odo")
        return None, period_label

    # Calcular estadÃ­sticas
    artists_counter = Counter()
    tracks_counter = Counter()
    albums_counter = Counter()
    genres_counter = Counter()
    labels_counter = Counter()

    artists_users = defaultdict(set)
    tracks_users = defaultdict(set)
    albums_users = defaultdict(set)
    genres_users = defaultdict(set)
    labels_users = defaultdict(set)

    processed_artists = set()
    processed_albums = set()

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

        # GÃ©neros (procesar solo una vez por artista)
        if artist not in processed_artists:
            genres = db.get_artist_genres(artist)
            for genre in genres:
                genres_counter[genre] += 1
                genres_users[genre].add(user)
            processed_artists.add(artist)

        # Sellos (procesar solo una vez por Ã¡lbum Ãºnico - artista+album)
        if album:
            album_key = f"{artist}|{album}"
            if album_key not in processed_albums:
                label = db.get_album_label(artist, album)
                if label:
                    labels_counter[label] += 1
                    # Agregar todos los usuarios que escucharon este Ã¡lbum
                    labels_users[label].add(user)
                processed_albums.add(album_key)

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

    stats = {
        'period_type': 'monthly',
        'period_label': period_label,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_scrobbles': len(all_tracks),
        'artists': filter_common(artists_counter, artists_users),
        'tracks': filter_common(tracks_counter, tracks_users),
        'albums': filter_common(albums_counter, albums_users),
        'genres': filter_common(genres_counter, genres_users),
        'labels': filter_common(labels_counter, labels_users)
    }

    db.close()
    return stats, period_label


def create_html(stats: Dict, users: List[str]) -> str:
    """Crea el HTML para las estadÃ­sticas mensuales"""
    users_json = json.dumps(users)
    stats_json = json.dumps(stats, indent=2, ensure_ascii=False)
    period_label = stats['period_label']

    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Stats - """ + period_label + """</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: #181825;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        header {
            background: #1e1e2e;
            padding: 30px;
            border-bottom: 2px solid #cba6f7;
        }

        h1 {
            font-size: 2em;
            color: #cba6f7;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #a6adc8;
            font-size: 1em;
        }

        .controls {
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }

        .control-group {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .category-filters {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .category-filter {
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }

        .category-filter:hover {
            border-color: #cba6f7;
            background: #45475a;
        }

        .category-filter.active {
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }

        label {
            color: #cba6f7;
            font-weight: 600;
        }

        select {
            padding: 8px 15px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
        }

        select:hover {
            border-color: #cba6f7;
        }

        select:focus {
            outline: none;
            border-color: #cba6f7;
            box-shadow: 0 0 0 3px rgba(203, 166, 247, 0.2);
        }

        .period-header {
            background: #1e1e2e;
            padding: 25px 30px;
            border-bottom: 2px solid #cba6f7;
        }

        .period-header h2 {
            color: #cba6f7;
            font-size: 1.5em;
            margin-bottom: 8px;
        }

        .period-info {
            color: #a6adc8;
            font-size: 0.9em;
        }

        .stats-container {
            padding: 30px;
        }

        .categories {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
        }

        .category {
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
            display: none;
        }

        .category.visible {
            display: block;
        }

        .category h3 {
            color: #cba6f7;
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #cba6f7;
        }

        .item {
            padding: 12px;
            margin-bottom: 10px;
            background: #181825;
            border-radius: 8px;
            border-left: 3px solid #45475a;
            transition: all 0.3s;
        }

        .item:hover {
            transform: translateX(5px);
            border-left-color: #cba6f7;
        }

        .item.highlighted {
            border-left-color: #cba6f7;
            background: #1e1e2e;
        }

        .item-name {
            color: #cdd6f4;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .item-meta {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            font-size: 0.9em;
        }

        .badge {
            padding: 4px 10px;
            background: #313244;
            color: #a6adc8;
            border-radius: 6px;
            font-size: 0.85em;
        }

        .user-badge {
            padding: 4px 10px;
            background: #45475a;
            color: #cdd6f4;
            border-radius: 6px;
            font-size: 0.85em;
        }

        .user-badge.highlighted-user {
            background: #cba6f7;
            color: #1e1e2e;
            font-weight: 600;
        }

        .no-data {
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
        }

        .last-update {
            text-align: center;
            padding: 20px;
            color: #6c7086;
            font-size: 0.85em;
            border-top: 1px solid #313244;
        }

        @media (max-width: 768px) {
            .categories {
                grid-template-columns: 1fr;
            }

            .controls {
                flex-direction: column;
                align-items: stretch;
            }

            .category-filters {
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1> Estadísticas Mensuales</h1>
            <p class="subtitle">""" + period_label + """</p>
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
                </div>
            </div>
        </div>

        <div class="period-header">
            <h2>Mes """ + period_label + """</h2>
            <p class="period-info">
                <span id="dateRange"></span> |
                <span id="totalScrobbles"></span> scrobbles totales
            </p>
        </div>

        <div class="stats-container">
            <div class="categories" id="categoriesContainer">
                <!-- Se llenarÃ¡ dinÃ¡micamente -->
            </div>
        </div>

        <div class="last-update">
            Generado: <span id="generatedAt"></span>
        </div>
    </div>

    <script>
        const users = """ + users_json + """;
        const stats = """ + stats_json + """;


        const userSelect = document.getElementById('userSelect');
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        });

        document.getElementById('dateRange').textContent = `${stats.from_date} → ${stats.to_date}`;
        document.getElementById('totalScrobbles').textContent = stats.total_scrobbles;
        document.getElementById('generatedAt').textContent = stats.generated_at;
        let activeCategories = new Set(['artists']);

        function renderStats() {
            const selectedUser = userSelect.value;
            const container = document.getElementById('categoriesContainer');
            container.innerHTML = '';

            const categoryOrder = ['artists', 'tracks', 'albums', 'genres', 'labels'];
            const categoryTitles = {
                artists: 'Artistas',
                tracks: 'Canciones',
                albums: 'Ãlbumes',
                genres: 'GÃ©neros',
                labels: 'Sellos'
            };

            let hasData = false;

            categoryOrder.forEach(categoryKey => {
                if (!stats[categoryKey] || stats[categoryKey].length === 0) return;

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

                stats[categoryKey].forEach(item => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'item';

                    if (selectedUser && item.users.includes(selectedUser)) {
                        itemDiv.classList.add('highlighted');
                    }

                    const itemName = document.createElement('div');
                    itemName.className = 'item-name';
                    itemName.textContent = item.name;
                    itemDiv.appendChild(itemName);

                    const itemMeta = document.createElement('div');
                    itemMeta.className = 'item-meta';

                    const countBadge = document.createElement('span');
                    countBadge.className = 'badge';
                    countBadge.textContent = `${item.count} plays`;
                    itemMeta.appendChild(countBadge);

                    item.users.forEach(user => {
                        const userBadge = document.createElement('span');
                        userBadge.className = 'user-badge';
                        if (user === selectedUser) {
                            userBadge.classList.add('highlighted-user');
                        }
                        userBadge.textContent = user;
                        itemMeta.appendChild(userBadge);
                    });

                    itemDiv.appendChild(itemMeta);
                    categoryDiv.appendChild(itemDiv);
                });

                container.appendChild(categoryDiv);
            });

            if (!hasData) {
                const noData = document.createElement('div');
                noData.className = 'no-data';
                noData.textContent = 'No hay coincidencias para este perÃ­odo';
                container.appendChild(noData);
            }
        }

        userSelect.addEventListener('change', renderStats);
        renderStats();
    </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description='Generador de estadÃ­sticas mensuales de Last.fm')
    parser.add_argument('--months-ago', type=int, default=0,
                       help='NÃºmero de meses atrÃ¡s (0 = mes actual)')
    args = parser.parse_args()

    try:
        stats, period_label = generate_monthly_stats(args.months_ago)

        if not stats:
            print("âŒ No se pudieron generar estadÃ­sticas")
            sys.exit(1)

        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        html = create_html(stats, users)

        # Nombre del archivo basado en el perÃ­odo
        safe_label = period_label.replace(' ', '_').lower()
        output_file = f'monthly_{safe_label}.html'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"\nâœ… Archivo generado: {output_file}")
        print(f"   Coincidencias encontradas:")
        print(f"   - Artistas: {len(stats['artists'])}")
        print(f"   - Canciones: {len(stats['tracks'])}")
        print(f"   - Ãlbumes: {len(stats['albums'])}")
        print(f"   - GÃ©neros: {len(stats['genres'])}")
        print(f"   - Sellos: {len(stats['labels'])}")

    except Exception as e:
        print(f"âŒ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Last.fm Database Updater
Actualiza la base de datos con los últimos scrobbles de todos los usuarios
"""

import os
import sys
import requests
import json
import sqlite3
import time
import argparse
from datetime import datetime
from typing import List, Dict, Optional

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_API_KEY') or not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
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

        # Índice para búsquedas por artista y álbum
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scrobbles_artist_album
            ON scrobbles(artist, album)
        ''')

        # Tabla de géneros
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artist_genres (
                artist TEXT PRIMARY KEY,
                genres TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
        ''')

        # Tabla de sellos (optimizada - una entrada por álbum)
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

    def get_first_scrobble_timestamp(self, user: str) -> int:
        """Obtiene el timestamp del scrobble más antiguo guardado para un usuario"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT MIN(timestamp) as min_ts FROM scrobbles WHERE user = ?',
            (user,)
        )
        result = cursor.fetchone()
        return result['min_ts'] if result['min_ts'] else 0

    def get_user_scrobble_count(self, user: str) -> int:
        """Obtiene el número total de scrobbles en la base de datos para un usuario"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) as count FROM scrobbles WHERE user = ?',
            (user,)
        )
        result = cursor.fetchone()
        return result['count'] if result else 0

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
                pass
        self.conn.commit()

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

    def get_all_artists(self) -> List[str]:
        """Obtiene todos los artistas únicos de la base de datos"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist FROM scrobbles')
        return [row['artist'] for row in cursor.fetchall()]

    def get_all_albums(self) -> List[Dict]:
        """Obtiene todos los álbumes únicos de la base de datos"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT artist, album FROM scrobbles WHERE album IS NOT NULL AND album != ""')
        return [{'artist': row['artist'], 'album': row['album']} for row in cursor.fetchall()]

    def clear_user_scrobbles(self, user: str):
        """Elimina todos los scrobbles de un usuario"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM scrobbles WHERE user = ?', (user,))
        self.conn.commit()
        print(f"   🗑️  Scrobbles anteriores de {user} eliminados")

    def close(self):
        self.conn.close()


class LastFMUpdater:
    def __init__(self):
        self.lastfm_api_key = os.getenv('LASTFM_API_KEY')
        self.discogs_token = os.getenv('DISCOGS_TOKEN', '')
        self.users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]

        if not self.lastfm_api_key:
            raise ValueError("LASTFM_API_KEY no encontrada en variables de entorno o .env")
        if not self.users:
            raise ValueError("LASTFM_USERS no encontrada en variables de entorno o .env")

        self.lastfm_base_url = "http://ws.audioscrobbler.com/2.0/"
        self.discogs_base_url = "https://api.discogs.com"
        self.db = Database()

    def get_lastfm_data(self, method: str, params: Dict) -> Optional[Dict]:
        """Realiza una petición a la API de Last.fm"""
        params.update({
            'api_key': self.lastfm_api_key,
            'format': 'json',
            'method': method
        })

        try:
            response = requests.get(self.lastfm_base_url, params=params, timeout=10)

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

        except Exception as e:
            print(f"\n❌ Error en petición Last.fm: {e}")
            return None

    def update_user_scrobbles(self, user: str, download_all: bool = False, backfill: bool = False):
        """Actualiza los scrobbles de un usuario desde su último registro"""
        print(f"\n📥 Actualizando scrobbles de {user}...")

        current_timestamp = int(datetime.now().timestamp())

        if download_all:
            print(f"   ⚠️  Modo --all activado: Descargando TODOS los scrobbles")
            self.db.clear_user_scrobbles(user)
            from_timestamp = 0
            to_timestamp = current_timestamp
            mode_label = "completa"
        elif backfill:
            first_timestamp = self.db.get_first_scrobble_timestamp(user)
            if first_timestamp == 0:
                print(f"   ⚠️  No hay scrobbles previos. Usa --all para descargar todo")
                return

            print(f"   🔙 Modo --backfill activado: Descargando scrobbles anteriores")
            print(f"   📅 Scrobble más antiguo actual: {datetime.fromtimestamp(first_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")

            from_timestamp = 0
            to_timestamp = first_timestamp - 1
            mode_label = "backfill"
        else:
            last_timestamp = self.db.get_last_scrobble_timestamp(user)
            from_timestamp = last_timestamp + 1 if last_timestamp > 0 else 0
            to_timestamp = current_timestamp
            mode_label = "incremental"

            if last_timestamp == 0:
                print(f"   📝 Primera actualización para {user}")
            else:
                print(f"   📅 Última actualización: {datetime.fromtimestamp(last_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")

        tracks = []
        page = 1
        total_pages = 1
        consecutive_errors = 0
        max_consecutive_errors = 3

        while page <= total_pages:
            params = {
                'user': user,
                'limit': 200,
                'page': page,
                'to': to_timestamp
            }

            # Solo agregar 'from' si hay un límite inferior
            if from_timestamp > 0:
                params['from'] = from_timestamp

            try:
                data = self.get_lastfm_data('user.getrecenttracks', params)

                if not data:
                    consecutive_errors += 1
                    print(f"   ⚠️  No se pudo obtener datos (página {page}/{total_pages})")

                    if consecutive_errors >= max_consecutive_errors:
                        print(f"   ❌ Demasiados errores consecutivos. Abortando para este usuario.")
                        break

                    print(f"   🔄 Reintentando en 5 segundos...")
                    time.sleep(5)
                    continue

                if 'error' in data:
                    error_code = data.get('error', 'unknown')
                    error_msg = data.get('message', 'Error desconocido')
                    print(f"   ❌ Error de API: {error_msg} (código {error_code})")

                    if error_code == 6:
                        print(f"   → El usuario '{user}' no existe o no es público")
                    elif error_code == 17:
                        print(f"   → El usuario '{user}' tiene el perfil privado")

                    break

                if 'recenttracks' not in data:
                    consecutive_errors += 1
                    print(f"   ⚠️  Respuesta inesperada de la API (página {page}/{total_pages})")

                    if consecutive_errors >= max_consecutive_errors:
                        print(f"   ❌ Demasiados errores consecutivos. Abortando para este usuario.")
                        break

                    print(f"   🔄 Reintentando en 5 segundos...")
                    time.sleep(5)
                    continue

                # Reset contador de errores si la petición fue exitosa
                consecutive_errors = 0

                if page == 1:
                    total_pages = int(data['recenttracks']['@attr'].get('totalPages', 1))
                    total_tracks = int(data['recenttracks']['@attr'].get('total', 0))

                    if download_all:
                        print(f"   📊 Total de scrobbles del usuario: {total_tracks} ({total_pages} páginas)")
                    elif backfill:
                        print(f"   📊 {total_tracks} scrobbles históricos encontrados ({total_pages} páginas)")
                    else:
                        print(f"   📊 {total_tracks} nuevos scrobbles encontrados ({total_pages} páginas)")

                track_data = data['recenttracks'].get('track', [])
                if isinstance(track_data, dict):
                    track_data = [track_data]

                for track in track_data:
                    if '@attr' in track and 'nowplaying' in track['@attr']:
                        continue

                    if 'date' not in track:
                        continue

                    tracks.append({
                        'artist': track['artist'].get('#text', '') if isinstance(track['artist'], dict) else str(track.get('artist', '')),
                        'track': track.get('name', ''),
                        'album': track['album'].get('#text', '') if isinstance(track['album'], dict) else str(track.get('album', '')),
                        'timestamp': int(track['date']['uts']) if 'date' in track else 0,
                        'user': user
                    })

                # Mostrar progreso
                if total_pages > 10:
                    if page % 10 == 0 or page == total_pages:
                        print(f"   📄 Procesando página {page}/{total_pages} ({len(tracks)} scrobbles recopilados)")

                page += 1
                time.sleep(0.25)

            except Exception as e:
                consecutive_errors += 1
                print(f"   ⚠️  Error inesperado en página {page}/{total_pages}: {e}")

                if consecutive_errors >= max_consecutive_errors:
                    print(f"   ❌ Demasiados errores consecutivos. Abortando para este usuario.")
                    break

                print(f"   🔄 Reintentando en 5 segundos...")
                time.sleep(5)
                continue

        if tracks:
            self.db.save_scrobbles(tracks)
            db_count = self.db.get_user_scrobble_count(user)

            if download_all:
                print(f"   ✅ {len(tracks)} scrobbles totales descargados y guardados")
            elif backfill:
                print(f"   ✅ {len(tracks)} scrobbles históricos guardados")
            else:
                print(f"   ✅ {len(tracks)} nuevos scrobbles guardados")

            print(f"   💾 Total en base de datos para {user}: {db_count} scrobbles")
        else:
            if mode_label == "backfill":
                print(f"   ℹ️  No hay más scrobbles históricos disponibles")
            else:
                print(f"   ℹ️  No hay nuevos scrobbles")

    def update_genres(self):
        """Actualiza géneros de artistas que no los tienen"""
        print(f"\n🎨 Actualizando géneros de artistas...")

        all_artists = self.db.get_all_artists()
        artists_without_genres = [a for a in all_artists if self.db.get_artist_genres(a) is None]

        print(f"   📊 {len(artists_without_genres)} artistas sin géneros")

        for i, artist in enumerate(artists_without_genres, 1):
            if i % 10 == 0:
                print(f"   Procesando artista {i}/{len(artists_without_genres)}: {artist}")

            data = self.get_lastfm_data('artist.gettoptags', {'artist': artist})

            tags = []
            if data and 'toptags' in data and 'tag' in data['toptags']:
                tags = [tag['name'] for tag in data['toptags']['tag'][:5]]

            self.db.save_artist_genres(artist, tags)
            time.sleep(0.2)

        print(f"   ✅ Géneros actualizados")

    def update_labels(self):
        """Actualiza sellos de álbumes que no los tienen"""
        if not self.discogs_token:
            print(f"\n⏭️  Discogs no configurado, omitiendo sellos")
            return

        print(f"\n🏷️  Actualizando sellos de álbumes...")

        # Obtener álbumes únicos de los scrobbles que no tienen sello
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT s.artist, s.album
            FROM scrobbles s
            LEFT JOIN album_labels al ON s.artist = al.artist AND s.album = al.album
            WHERE s.album IS NOT NULL
            AND s.album != ''
            AND al.label IS NULL
        ''')

        albums_without_labels = [{'artist': row[0], 'album': row[1]} for row in cursor.fetchall()]

        print(f"   📊 {len(albums_without_labels)} álbumes únicos sin sello")

        if len(albums_without_labels) == 0:
            print(f"   ✅ Todos los álbumes ya tienen información de sello")
            return

        for i, album_info in enumerate(albums_without_labels, 1):
            if i % 5 == 0 or i == len(albums_without_labels):
                print(f"   📀 Procesando álbum {i}/{len(albums_without_labels)}: {album_info['artist']} - {album_info['album']}")

            try:
                headers = {'Authorization': f'Discogs token={self.discogs_token}'}
                params = {
                    'q': f'{album_info["artist"]} {album_info["album"]}',
                    'type': 'release',
                    'per_page': 1
                }

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
                        labels_list = data['results'][0].get('label', [])
                        if labels_list and len(labels_list) > 0:
                            label = labels_list[0]

                self.db.save_album_label(album_info['artist'], album_info['album'], label if label else '')
                time.sleep(1)  # Respetar rate limit de Discogs

            except Exception as e:
                print(f"   ⚠️  Error con álbum {album_info['album']}: {e}")

        print(f"   ✅ Sellos actualizados")

    def run(self, download_all: bool = False, backfill: bool = False):
        """Ejecuta la actualización completa"""
        print("="*60)
        print("🔄 ACTUALIZACIÓN DE BASE DE DATOS LAST.FM")
        print("="*60)

        if download_all:
            print("⚠️  MODO --all ACTIVADO: Se descargarán TODOS los scrobbles")
            print("⚠️  Esto eliminará los scrobbles existentes y los reemplazará")
            print("="*60)
        elif backfill:
            print("🔙 MODO --backfill ACTIVADO: Descargando scrobbles históricos")
            print("📥 Se descargarán los scrobbles anteriores al más antiguo")
            print("="*60)

        # Actualizar scrobbles de todos los usuarios
        for user in self.users:
            self.update_user_scrobbles(user, download_all, backfill)

        # Actualizar géneros
        self.update_genres()

        # Actualizar sellos
        self.update_labels()

        print("\n" + "="*60)
        print("✅ ACTUALIZACIÓN COMPLETADA")
        print("="*60)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💾 Base de datos: {self.db.db_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Actualiza la base de datos de Last.fm con scrobbles de usuarios'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Descargar TODOS los scrobbles desde el principio (elimina scrobbles existentes)'
    )
    parser.add_argument(
        '--backfill',
        action='store_true',
        help='Descargar scrobbles históricos (desde el más antiguo en la BD hasta el principio en Last.fm)'
    )

    args = parser.parse_args()

    # Validar que no se usen ambos argumentos al mismo tiempo
    if args.all and args.backfill:
        print("❌ Error: No puedes usar --all y --backfill al mismo tiempo")
        print("   --all: Descarga todo desde cero")
        print("   --backfill: Completa el historial desde lo más antiguo que tienes")
        sys.exit(1)

    try:
        updater = LastFMUpdater()
        updater.run(download_all=args.all, backfill=args.backfill)
    except KeyboardInterrupt:
        print("\n\n⚠️ Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'updater' in locals():
            updater.db.close()


if __name__ == '__main__':
    main()

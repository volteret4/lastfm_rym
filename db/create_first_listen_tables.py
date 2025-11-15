#!/usr/bin/env python3
"""
Script para precalcular las fechas de primera escucha de usuarios
Crea tablas con las fechas en que cada usuario escucha por primera vez cada elemento
"""

import os
import sys
import sqlite3
from datetime import datetime
from collections import defaultdict

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass


def create_first_listen_tables(db_path='db/lastfm_cache.db'):
    """Crea las tablas de primeras escuchas y las llena con datos"""

    print("🔄 Creando tablas de primeras escuchas...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Crear tabla para primeras escuchas de artistas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_first_artist_listen (
            user TEXT,
            artist TEXT,
            first_timestamp INTEGER,
            PRIMARY KEY (user, artist)
        )
    ''')

    # Crear tabla para primeras escuchas de álbumes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_first_album_listen (
            user TEXT,
            artist TEXT,
            album TEXT,
            first_timestamp INTEGER,
            PRIMARY KEY (user, artist, album)
        )
    ''')

    # Crear tabla para primeras escuchas de canciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_first_track_listen (
            user TEXT,
            artist TEXT,
            track TEXT,
            first_timestamp INTEGER,
            PRIMARY KEY (user, artist, track)
        )
    ''')

    # Crear tabla para primeras escuchas de sellos (a través de álbumes)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_first_label_listen (
            user TEXT,
            label TEXT,
            first_timestamp INTEGER,
            PRIMARY KEY (user, label)
        )
    ''')

    conn.commit()

    # Limpiar tablas existentes para recalcular
    print("🗑️ Limpiando tablas existentes...")
    cursor.execute('DELETE FROM user_first_artist_listen')
    cursor.execute('DELETE FROM user_first_album_listen')
    cursor.execute('DELETE FROM user_first_track_listen')
    cursor.execute('DELETE FROM user_first_label_listen')
    conn.commit()

    print("📊 Calculando primeras escuchas por usuario...")

    # Obtener todos los scrobbles ordenados por timestamp
    cursor.execute('''
        SELECT user, artist, track, album, timestamp
        FROM scrobbles
        ORDER BY user, timestamp ASC
    ''')

    # Diccionarios para trackear las primeras escuchas
    first_artists = defaultdict(dict)      # user -> artist -> first_timestamp
    first_albums = defaultdict(dict)       # user -> (artist,album) -> first_timestamp
    first_tracks = defaultdict(dict)       # user -> (artist,track) -> first_timestamp
    first_labels = defaultdict(dict)       # user -> label -> first_timestamp

    print("🔄 Procesando scrobbles...")

    processed_count = 0
    for row in cursor.fetchall():
        user, artist, track, album, timestamp = row
        processed_count += 1

        if processed_count % 100000 == 0:
            print(f"   Procesados {processed_count:,} scrobbles...")

        # Primera escucha de artista
        if artist not in first_artists[user]:
            first_artists[user][artist] = timestamp

        # Primera escucha de canción
        track_key = (artist, track)
        if track_key not in first_tracks[user]:
            first_tracks[user][track_key] = timestamp

        # Primera escucha de álbum (si existe)
        if album and album.strip():
            album_key = (artist, album)
            if album_key not in first_albums[user]:
                first_albums[user][album_key] = timestamp

    print(f"✅ Procesados {processed_count:,} scrobbles")

    # Insertar datos de artistas
    print("💾 Guardando primeras escuchas de artistas...")
    artist_data = []
    for user, artists in first_artists.items():
        for artist, timestamp in artists.items():
            artist_data.append((user, artist, timestamp))

    cursor.executemany('''
        INSERT INTO user_first_artist_listen (user, artist, first_timestamp)
        VALUES (?, ?, ?)
    ''', artist_data)

    # Insertar datos de canciones
    print("💾 Guardando primeras escuchas de canciones...")
    track_data = []
    for user, tracks in first_tracks.items():
        for (artist, track), timestamp in tracks.items():
            track_data.append((user, artist, track, timestamp))

    cursor.executemany('''
        INSERT INTO user_first_track_listen (user, artist, track, first_timestamp)
        VALUES (?, ?, ?, ?)
    ''', track_data)

    # Insertar datos de álbumes
    print("💾 Guardando primeras escuchas de álbumes...")
    album_data = []
    for user, albums in first_albums.items():
        for (artist, album), timestamp in albums.items():
            album_data.append((user, artist, album, timestamp))

    cursor.executemany('''
        INSERT INTO user_first_album_listen (user, artist, album, first_timestamp)
        VALUES (?, ?, ?, ?)
    ''', album_data)

    # Calcular primeras escuchas de sellos
    print("💾 Calculando primeras escuchas de sellos...")

    # Obtener datos de sellos de álbumes
    cursor.execute('''
        SELECT DISTINCT artist, album, label
        FROM album_labels
        WHERE label IS NOT NULL AND label != ""
    ''')

    album_labels = {}
    for artist, album, label in cursor.fetchall():
        album_labels[(artist, album)] = label

    # Calcular primera escucha de cada sello por usuario
    for user, albums in first_albums.items():
        user_label_first = {}
        for (artist, album), timestamp in albums.items():
            if (artist, album) in album_labels:
                label = album_labels[(artist, album)]
                if label not in user_label_first or timestamp < user_label_first[label]:
                    user_label_first[label] = timestamp

        # Insertar datos de sellos para este usuario
        for label, timestamp in user_label_first.items():
            first_labels[user][label] = timestamp

    label_data = []
    for user, labels in first_labels.items():
        for label, timestamp in labels.items():
            label_data.append((user, label, timestamp))

    cursor.executemany('''
        INSERT INTO user_first_label_listen (user, label, first_timestamp)
        VALUES (?, ?, ?)
    ''', label_data)

    conn.commit()

    # Crear índices para mejorar rendimiento
    print("📈 Creando índices...")

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_artist_user ON user_first_artist_listen(user)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_artist_timestamp ON user_first_artist_listen(first_timestamp)')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_album_user ON user_first_album_listen(user)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_album_timestamp ON user_first_album_listen(first_timestamp)')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_track_user ON user_first_track_listen(user)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_track_timestamp ON user_first_track_listen(first_timestamp)')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_label_user ON user_first_label_listen(user)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_label_timestamp ON user_first_label_listen(first_timestamp)')

    conn.commit()
    conn.close()

    print("✅ Tablas de primeras escuchas creadas exitosamente")

    # Mostrar estadísticas
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM user_first_artist_listen')
    artist_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM user_first_album_listen')
    album_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM user_first_track_listen')
    track_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM user_first_label_listen')
    label_count = cursor.fetchone()[0]

    conn.close()

    print(f"\n📊 Estadísticas finales:")
    print(f"   - Primeras escuchas de artistas: {artist_count:,}")
    print(f"   - Primeras escuchas de álbumes: {album_count:,}")
    print(f"   - Primeras escuchas de canciones: {track_count:,}")
    print(f"   - Primeras escuchas de sellos: {label_count:,}")


def main():
    try:
        create_first_listen_tables()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

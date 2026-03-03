#!/usr/bin/env python3
"""
cleanup_after_migration.py
===========================
Elimina las tablas legacy redundantes que ya están consolidadas en
artists / albums / tracks, y hace VACUUM para recuperar el espacio.

TABLAS QUE SE ELIMINAN (datos ya migrados a las canónicas):
  - artist_details          → artists
  - album_details           → albums
  - track_details           → tracks
  - album_labels            → albums.label
  - album_release_dates     → albums.release_year / original_release_date

TABLAS QUE SE CONSERVAN:
  - scrobbles               (con artist_id / album_id / track_id)
  - artists / albums / tracks
  - artist_genres           (legacy ligera, útil para compatibilidad rápida)
  - artist_genres_detailed
  - album_genres
  - user_first_*_listen
  - cache_responses / api_cache
  - group_stats
  - listenbrainz_*
  - import_errors

ÍNDICES DUPLICADOS:
  Se eliminan los índices redundantes que apuntan a las columnas de texto
  (artist, album, track) en scrobbles ahora que tenemos los IDs.
  Se conservan idx_scrobbles_user_timestamp y los de FK.

Hace backup automático antes de modificar nada.
"""

import sqlite3
import os
import sys
import shutil
import time
from datetime import datetime


DEFAULT_DB = 'db/lastfm_cache.db'

LEGACY_TABLES_TO_DROP = [
    'artist_details',
    'album_details',
    'track_details',
    'album_labels',
    'album_release_dates',
]

# Índices sobre columnas de texto que ya no son la vía principal de query
REDUNDANT_INDEXES_TO_DROP = [
    'idx_scrobbles_artist_album',
    'idx_scrobbles_user_artist',
    'idx_scrobbles_artist_timestamp',
    'idx_scrobbles_user_track',
    'idx_scrobbles_user_artist_timestamp',
    'idx_scrobbles_album_artist',
    'idx_scrobbles_track_artist',
    'idx_scrobbles_timestamp_user',
    'idx_scrobbles_artist_user',
    # MBIDs de texto en scrobbles (ahora en artists/albums/tracks)
    'idx_scrobbles_artist_mbid',
    'idx_scrobbles_user_artist_mbid',
    'idx_scrobbles_album_mbid',
    'idx_scrobbles_track_mbid',
]


def backup_db(db_path: str) -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.pre_cleanup_{ts}"
    print(f"💾 Backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    size_mb = os.path.getsize(backup_path) / 1024 / 1024
    print(f"   ✅ {size_mb:.1f} MB guardados")
    return backup_path


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=DELETE')   # WAL no es compatible con VACUUM
    conn.execute('PRAGMA foreign_keys=OFF')
    return conn


def verify_migration_complete(conn: sqlite3.Connection) -> bool:
    """Comprueba que la migración se ejecutó antes de limpiar."""
    cur = conn.cursor()
    for table in ('artists', 'albums', 'tracks'):
        row = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not row:
            print(f"❌ Tabla canónica '{table}' no encontrada.")
            print("   Ejecuta primero migrate_to_normalized_schema.py")
            return False

    # Verificar que las FKs están pobladas en scrobbles
    total   = cur.execute("SELECT COUNT(*) FROM scrobbles").fetchone()[0]
    with_id = cur.execute("SELECT COUNT(*) FROM scrobbles WHERE artist_id IS NOT NULL").fetchone()[0]
    if total > 0 and with_id / total < 0.8:
        print(f"⚠️  Solo el {with_id/total*100:.1f}% de scrobbles tiene artist_id.")
        print("   ¿Seguro que la migración terminó correctamente?")
        answer = input("   Continuar igualmente? (y/N): ").strip().lower()
        if answer != 'y':
            return False

    return True


def show_size_report(conn: sqlite3.Connection, label: str):
    """Muestra tamaño aproximado por tabla."""
    cur = conn.cursor()
    print(f"\n📊 {label}")
    rows = cur.execute("""
        SELECT name, SUM(payload) AS bytes
        FROM (
            SELECT name, payload FROM dbstat
        )
        GROUP BY name
        ORDER BY bytes DESC
        LIMIT 20
    """).fetchall()
    for name, size in rows:
        print(f"   {name:<40} {size/1024/1024:>7.2f} MB")


def drop_legacy_tables(conn: sqlite3.Connection):
    print("\n🗑️  Eliminando tablas legacy redundantes...")
    cur = conn.cursor()
    existing = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    for table in LEGACY_TABLES_TO_DROP:
        if table in existing:
            cur.execute(f"DROP TABLE {table}")
            print(f"   ✅ DROP TABLE {table}")
        else:
            print(f"   ⏭️  {table} no existe")

    conn.commit()


def drop_redundant_indexes(conn: sqlite3.Connection):
    print("\n🗑️  Eliminando índices redundantes...")
    cur = conn.cursor()
    existing = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()}

    for idx in REDUNDANT_INDEXES_TO_DROP:
        if idx in existing:
            cur.execute(f"DROP INDEX {idx}")
            print(f"   ✅ DROP INDEX {idx}")
        else:
            print(f"   ⏭️  {idx} no existe")

    conn.commit()


def drop_mbid_text_columns_scrobbles(conn: sqlite3.Connection):
    """
    Elimina las columnas artist_mbid/album_mbid/track_mbid de scrobbles
    (ya están en artists/albums/tracks).
    SQLite no soporta DROP COLUMN hasta la versión 3.35 — usamos recreación.
    """
    cur = conn.cursor()

    # Verificar versión de SQLite
    version = cur.execute("SELECT sqlite_version()").fetchone()[0]
    major, minor, *_ = (int(x) for x in version.split('.'))

    if major > 3 or (major == 3 and minor >= 35):
        print(f"\n🗑️  Eliminando columnas *_mbid de scrobbles (SQLite {version})...")
        for col in ('artist_mbid', 'album_mbid', 'track_mbid'):
            try:
                cur.execute(f"ALTER TABLE scrobbles DROP COLUMN {col}")
                print(f"   ✅ DROP COLUMN scrobbles.{col}")
            except Exception as e:
                print(f"   ⏭️  {col}: {e}")
        conn.commit()
    else:
        print(f"\n⚠️  SQLite {version} < 3.35 — no soporta DROP COLUMN.")
        print("   Las columnas *_mbid en scrobbles se conservan (impacto mínimo).")


def remove_text_columns_via_recreate(conn: sqlite3.Connection):
    """
    Elimina las columnas de texto 'artist', 'track', 'album' de scrobbles
    ahora que los IDs son la fuente de verdad.

    ⚠️  OPERACIÓN PESADA: recrea la tabla completa.
    Se omite por defecto; activar con --drop-text-cols.
    """
    print("\n⚙️  Recreando tabla scrobbles sin columnas de texto...")

    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM scrobbles").fetchone()[0]
    print(f"   {total:,} filas a mover...")

    cur.executescript("""
        CREATE TABLE scrobbles_new (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user       TEXT    NOT NULL,
            timestamp  INTEGER NOT NULL,
            artist_id  INTEGER NOT NULL REFERENCES artists(artist_id),
            album_id   INTEGER REFERENCES albums(album_id),
            track_id   INTEGER REFERENCES tracks(track_id),
            UNIQUE(user, timestamp, artist_id)
        );

        INSERT INTO scrobbles_new (id, user, timestamp, artist_id, album_id, track_id)
        SELECT id, user, timestamp, artist_id, album_id, track_id
        FROM scrobbles
        WHERE artist_id IS NOT NULL;

        DROP TABLE scrobbles;
        ALTER TABLE scrobbles_new RENAME TO scrobbles;

        CREATE INDEX IF NOT EXISTS idx_scrobbles_user_ts    ON scrobbles(user, timestamp);
        CREATE INDEX IF NOT EXISTS idx_scrobbles_artist_id  ON scrobbles(artist_id);
        CREATE INDEX IF NOT EXISTS idx_scrobbles_album_id   ON scrobbles(album_id);
        CREATE INDEX IF NOT EXISTS idx_scrobbles_track_id   ON scrobbles(track_id);
        CREATE INDEX IF NOT EXISTS idx_scrobbles_user_art   ON scrobbles(user, artist_id);
        CREATE INDEX IF NOT EXISTS idx_scrobbles_user_alb   ON scrobbles(user, album_id);
    """)
    conn.commit()
    print("   ✅ Tabla scrobbles recreada sin columnas de texto")


def vacuum_db(db_path: str):
    """VACUUM necesita conexión sin WAL activo."""
    print("\n🗜️  Ejecutando VACUUM (esto puede tardar varios minutos)...")
    size_before = os.path.getsize(db_path) / 1024 / 1024
    start = time.time()

    # VACUUM requiere conexión limpia
    conn = sqlite3.connect(db_path)
    conn.execute("VACUUM")
    conn.close()

    elapsed = time.time() - start
    size_after = os.path.getsize(db_path) / 1024 / 1024
    saved = size_before - size_after

    print(f"   ✅ VACUUM completado en {elapsed:.1f}s")
    print(f"   📦 {size_before:.1f} MB  →  {size_after:.1f} MB  (−{saved:.1f} MB)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Limpieza post-migración y reducción de tamaño')
    parser.add_argument('--db',             default=DEFAULT_DB, help=f'Ruta DB (default: {DEFAULT_DB})')
    parser.add_argument('--no-backup',      action='store_true', help='Saltar backup')
    parser.add_argument('--drop-text-cols', action='store_true',
                        help='⚠️  Eliminar columnas artist/track/album de scrobbles (máximo ahorro, operación pesada)')
    parser.add_argument('--dry-run',        action='store_true', help='Solo mostrar qué se haría')
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print(f"❌ No encontrada: {db_path}")
        sys.exit(1)

    size_initial = os.path.getsize(db_path) / 1024 / 1024
    print("=" * 60)
    print("🧹 CLEANUP POST-MIGRACIÓN")
    print("=" * 60)
    print(f"🗄️  {db_path}  ({size_initial:.1f} MB)")

    if args.dry_run:
        print("\n[DRY RUN — no se modifica nada]")
        print("Se eliminarían:")
        for t in LEGACY_TABLES_TO_DROP:
            print(f"  TABLE  {t}")
        for i in REDUNDANT_INDEXES_TO_DROP:
            print(f"  INDEX  {i}")
        if args.drop_text_cols:
            print("  COLUMNS scrobbles.(artist, track, album)  [recreación completa]")
        return

    conn = get_conn(db_path)

    if not verify_migration_complete(conn):
        conn.close()
        sys.exit(1)

    if not args.no_backup:
        conn.close()
        backup_db(db_path)
        conn = get_conn(db_path)

    show_size_report(conn, "Tamaño por tabla ANTES")

    drop_legacy_tables(conn)
    drop_redundant_indexes(conn)
    drop_mbid_text_columns_scrobbles(conn)

    if args.drop_text_cols:
        print("\n⚠️  --drop-text-cols activado: eliminando columnas de texto de scrobbles")
        print("   Esto elimina artist/track/album como strings — asegúrate de que")
        print("   todos tus scripts usan los IDs o hacen JOIN.")
        answer = input("   Confirmar? (y/N): ").strip().lower()
        if answer == 'y':
            remove_text_columns_via_recreate(conn)
        else:
            print("   Omitido.")

    show_size_report(conn, "Tamaño por tabla DESPUÉS (antes de VACUUM)")
    conn.close()

    vacuum_db(db_path)

    size_final = os.path.getsize(db_path) / 1024 / 1024
    print(f"\n✨ LIMPIEZA COMPLETADA")
    print(f"   {size_initial:.1f} MB  →  {size_final:.1f} MB  (−{size_initial - size_final:.1f} MB)")

    if not args.drop_text_cols:
        print("""
💡 Para máximo ahorro ejecuta también con --drop-text-cols:
   Elimina las columnas artist/track/album (texto) de la tabla scrobbles,
   que es la más grande. Solo hazlo cuando todos tus scripts usen los IDs.
   Ahorro estimado adicional: 150-250 MB según tu volumen de scrobbles.
""")


if __name__ == '__main__':
    main()

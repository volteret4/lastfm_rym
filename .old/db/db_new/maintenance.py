#!/usr/bin/env python3
"""
maintenance.py — Mantenimiento del schema normalizado
======================================================
Reemplaza en el nuevo schema lo que hacían:
  - create_first_listen_tables.py  → --first-listens
  - index_optimizer.py             → --vacuum
  - detailed_albums.py / detailed_db.py → cubiertos por update_database.py --enrich

Uso:
  python3 db_new/maintenance.py --all
  python3 db_new/maintenance.py --first-listens
  python3 db_new/maintenance.py --first-listens --reset
  python3 db_new/maintenance.py --vacuum
  python3 db_new/maintenance.py --stats
  python3 db_new/maintenance.py --db /ruta/a/lastfm_cache_rym_new_normalized.db --all
"""

import argparse
import os
import re
import sqlite3
import time
from typing import List, Tuple

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), '..', 'db',
                           'lastfm_cache_rym_new_normalized.db')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_table(username: str) -> str:
    safe = re.sub(r'[^a-z0-9]', '_', username.lower()).strip('_')
    return f"scrobbles_{safe}"


def _get_users(conn: sqlite3.Connection) -> List[Tuple[int, str]]:
    """Devuelve [(user_id, username), ...] de todos los usuarios con tabla de scrobbles."""
    rows = conn.execute("SELECT id, username FROM users ORDER BY username").fetchall()
    existing_tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'scrobbles_%'"
    ).fetchall()}
    return [(uid, uname) for uid, uname in rows
            if _user_table(uname) in existing_tables]


# ── First listens ─────────────────────────────────────────────────────────────

def compute_first_listens(conn: sqlite3.Connection, reset: bool = False) -> None:
    """
    Puebla user_first_artist/album/track/label_listen usando SQL puro.
    Cada tabla se calcula con un MIN(timestamp) GROUP BY sobre la tabla per-user.

    Si reset=True limpia y recalcula desde cero.
    Si reset=False usa INSERT OR IGNORE (solo añade registros nuevos).
    """
    users = _get_users(conn)
    if not users:
        print("⚠  No hay usuarios con tablas de scrobbles.")
        return

    if reset:
        print("🗑  Limpiando tablas user_first_* ...")
        for tbl in ("user_first_artist_listen", "user_first_album_listen",
                    "user_first_track_listen", "user_first_label_listen"):
            conn.execute(f"DELETE FROM {tbl}")
        conn.commit()

    total_artists = total_albums = total_tracks = total_labels = 0

    for user_id, username in users:
        tbl = _user_table(username)
        print(f"\n── {username} ({tbl}) ──")
        t0 = time.time()

        # Primeras escuchas de artistas
        n = conn.execute(f"""
            INSERT OR IGNORE INTO user_first_artist_listen (user_id, artist_id, first_timestamp)
            SELECT ?, artist_id, MIN(timestamp)
            FROM {tbl}
            GROUP BY artist_id
        """, (user_id,)).rowcount
        total_artists += n
        print(f"   artistas:  {n:,}")

        # Primeras escuchas de álbumes
        n = conn.execute(f"""
            INSERT OR IGNORE INTO user_first_album_listen (user_id, album_id, first_timestamp)
            SELECT ?, album_id, MIN(timestamp)
            FROM {tbl}
            WHERE album_id IS NOT NULL
            GROUP BY album_id
        """, (user_id,)).rowcount
        total_albums += n
        print(f"   álbumes:   {n:,}")

        # Primeras escuchas de tracks
        n = conn.execute(f"""
            INSERT OR IGNORE INTO user_first_track_listen (user_id, track_id, first_timestamp)
            SELECT ?, track_id, MIN(timestamp)
            FROM {tbl}
            GROUP BY track_id
        """, (user_id,)).rowcount
        total_tracks += n
        print(f"   tracks:    {n:,}")

        # Primeras escuchas de sellos (join con albums.label)
        n = conn.execute(f"""
            INSERT OR IGNORE INTO user_first_label_listen (user_id, label, first_timestamp)
            SELECT ?, al.label, MIN(sc.timestamp)
            FROM {tbl} sc
            JOIN albums al ON al.id = sc.album_id
            WHERE al.label IS NOT NULL AND al.label != ''
            GROUP BY al.label
        """, (user_id,)).rowcount
        total_labels += n
        print(f"   sellos:    {n:,}")

        conn.commit()
        print(f"   ({time.time() - t0:.1f}s)")

    print(f"""
✅ Primeras escuchas calculadas:
   artistas: {total_artists:,}
   álbumes:  {total_albums:,}
   tracks:   {total_tracks:,}
   sellos:   {total_labels:,}""")


# ── Vacuum / optimize ─────────────────────────────────────────────────────────

def vacuum_and_optimize(conn: sqlite3.Connection) -> None:
    """ANALYZE + PRAGMA optimize + VACUUM."""
    print("📊 ANALYZE ...")
    t0 = time.time()
    conn.execute("ANALYZE")
    print(f"   {time.time() - t0:.1f}s")

    print("⚡ PRAGMA optimize ...")
    t0 = time.time()
    conn.execute("PRAGMA optimize")
    print(f"   {time.time() - t0:.1f}s")

    print("🗜  VACUUM ...")
    t0 = time.time()
    conn.execute("VACUUM")
    elapsed = time.time() - t0
    size_mb = os.path.getsize(conn.execute("PRAGMA database_list").fetchone()[2]) / 1024 / 1024
    print(f"   {elapsed:.1f}s  →  {size_mb:.1f} MB")


# ── Stats ─────────────────────────────────────────────────────────────────────

def show_stats(conn: sqlite3.Connection) -> None:
    """Resumen del estado de la base de datos."""
    users = _get_users(conn)

    print(f"\n{'═'*55}")
    print(f"  DB: {conn.execute('PRAGMA database_list').fetchone()[2]}")
    print(f"{'═'*55}")

    print(f"\n{'─'*30}")
    print(f"  Usuarios: {len(users)}")

    total_sc = 0
    for user_id, username in users:
        tbl = _user_table(username)
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        total_sc += n
        print(f"    {username:<20} {n:>10,} scrobbles")

    print(f"  {'TOTAL':<20} {total_sc:>10,} scrobbles")

    print(f"\n{'─'*30}")
    for entity, tbl in [("Artistas", "artists"), ("Álbumes", "albums"), ("Tracks", "tracks")]:
        total  = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        enriched = conn.execute(
            f"SELECT COUNT(*) FROM {tbl} WHERE last_updated IS NOT NULL"
        ).fetchone()[0]
        pct = enriched / total * 100 if total else 0
        print(f"  {entity:<10} {total:>8,} total  {enriched:>8,} enriquecidos ({pct:.0f}%)")

    print(f"\n{'─'*30}")
    for label, tbl in [
        ("genres",       "genres"),
        ("album_genres", "album_genres"),
        ("artist_genres","artist_genres"),
    ]:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {label:<15} {n:>8,}")

    print(f"\n{'─'*30}")
    for label, tbl in [
        ("first_artist", "user_first_artist_listen"),
        ("first_album",  "user_first_album_listen"),
        ("first_track",  "user_first_track_listen"),
        ("first_label",  "user_first_label_listen"),
    ]:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {label:<15} {n:>8,}")

    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Mantenimiento del schema normalizado lastfm_cache_rym_new_normalized.db"
    )
    parser.add_argument("--db", default=_DEFAULT_DB,
                        help=f"Ruta a la BD (default: {_DEFAULT_DB})")
    parser.add_argument("--first-listens", action="store_true",
                        help="Calcular / actualizar tablas user_first_*")
    parser.add_argument("--reset", action="store_true",
                        help="Con --first-listens: limpiar y recalcular desde cero")
    parser.add_argument("--vacuum", action="store_true",
                        help="ANALYZE + PRAGMA optimize + VACUUM")
    parser.add_argument("--stats", action="store_true",
                        help="Mostrar estadísticas de la BD")
    parser.add_argument("--all", dest="do_all", action="store_true",
                        help="Ejecutar todo: --first-listens --vacuum --stats")
    args = parser.parse_args()

    if not any([args.first_listens, args.vacuum, args.stats, args.do_all]):
        parser.print_help()
        return

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print(f"❌ No existe: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    print(f"🗄  {db_path}")

    try:
        if args.do_all or args.first_listens:
            print("\n🕐 Calculando primeras escuchas...")
            compute_first_listens(conn, reset=args.reset or args.do_all)

        if args.do_all or args.vacuum:
            print("\n🔧 Optimizando BD...")
            vacuum_and_optimize(conn)

        if args.do_all or args.stats:
            show_stats(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()

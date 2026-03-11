#!/usr/bin/env python3
"""
dedup_must_hear.py — Elimina duplicados de must_hear.db y repara las FKs.

Tablas afectadas:
  albums          → puede tener filas (artist_id, name) duplicadas
  artists         → puede tener filas (name) duplicadas
  collection_albums → apunta a album_id que puede estar duplicado
  album_genres    → ídem
  album_metadata  → ídem
  user_heard      → ídem

Estrategia:
  1. Para cada grupo de álbumes duplicados en (artist_id, name):
       - Keeper  = el id MÁS PEQUEÑO (el más antiguo)
       - Reapuntar todas las FKs de los duplicados → keeper
       - Eliminar filas duplicadas de albums

  2. Para cada grupo de artistas duplicados en (name):
       - Keeper  = el id MÁS PEQUEÑO
       - Reapuntar albums.artist_id → keeper
       - Eliminar filas duplicadas de artists

  3. Ejecuta VACUUM al final.

Uso:
  python3 dedup_must_hear.py --db db/must_hear_rym_new.db
  python3 dedup_must_hear.py --db db/must_hear_rym_new.db --dry-run
"""

import sqlite3
import argparse
import sys
from pathlib import Path


def find_duplicate_albums(conn: sqlite3.Connection) -> list[dict]:
    """Devuelve grupos de álbumes con mismo (artist_id, name)."""
    rows = conn.execute("""
        SELECT artist_id, name, COUNT(*) as cnt,
               MIN(id) as keeper_id,
               GROUP_CONCAT(id ORDER BY id) as all_ids
        FROM albums
        GROUP BY artist_id, name
        HAVING cnt > 1
        ORDER BY cnt DESC, artist_id, name
    """).fetchall()
    result = []
    for artist_id, name, cnt, keeper_id, all_ids in rows:
        ids = [int(x) for x in all_ids.split(",")]
        dupes = [i for i in ids if i != keeper_id]
        result.append({
            "artist_id": artist_id,
            "name":      name,
            "keeper":    keeper_id,
            "dupes":     dupes,
            "count":     cnt,
        })
    return result


def find_duplicate_artists(conn: sqlite3.Connection) -> list[dict]:
    """Devuelve grupos de artistas con mismo name."""
    rows = conn.execute("""
        SELECT name, COUNT(*) as cnt,
               MIN(id) as keeper_id,
               GROUP_CONCAT(id ORDER BY id) as all_ids
        FROM artists
        GROUP BY name
        HAVING cnt > 1
        ORDER BY cnt DESC, name
    """).fetchall()
    result = []
    for name, cnt, keeper_id, all_ids in rows:
        ids = [int(x) for x in all_ids.split(",")]
        dupes = [i for i in ids if i != keeper_id]
        result.append({
            "name":    name,
            "keeper":  keeper_id,
            "dupes":   dupes,
            "count":   cnt,
        })
    return result


def repoint_album_fks(conn: sqlite3.Connection,
                       dupe_id: int, keeper_id: int) -> dict:
    """
    Reapunta todas las FKs de dupe_id → keeper_id en tablas hijas.
    Maneja conflictos (si keeper ya tiene la fila) eliminando la dupe.
    Devuelve conteo de cambios por tabla.
    """
    stats = {}

    # ── collection_albums ────────────────────────────────────────────────────
    # Puede haber (collection_id, dupe_id) donde ya existe (collection_id, keeper_id)
    # En ese caso simplemente borramos el dupe; si no existe, reapuntamos.
    ca_rows = conn.execute(
        "SELECT id, collection_id FROM collection_albums WHERE album_id=?",
        (dupe_id,)
    ).fetchall()
    moved = deleted = 0
    for ca_id, coll_id in ca_rows:
        exists = conn.execute(
            "SELECT id FROM collection_albums WHERE collection_id=? AND album_id=?",
            (coll_id, keeper_id)
        ).fetchone()
        if exists:
            conn.execute("DELETE FROM collection_albums WHERE id=?", (ca_id,))
            deleted += 1
        else:
            conn.execute(
                "UPDATE collection_albums SET album_id=? WHERE id=?",
                (keeper_id, ca_id)
            )
            moved += 1
    stats["collection_albums"] = {"moved": moved, "deleted": deleted}

    # ── album_genres ─────────────────────────────────────────────────────────
    ag_rows = conn.execute(
        "SELECT genre_id FROM album_genres WHERE album_id=?", (dupe_id,)
    ).fetchall()
    moved = deleted = 0
    for (genre_id,) in ag_rows:
        exists = conn.execute(
            "SELECT 1 FROM album_genres WHERE album_id=? AND genre_id=?",
            (keeper_id, genre_id)
        ).fetchone()
        if exists:
            conn.execute(
                "DELETE FROM album_genres WHERE album_id=? AND genre_id=?",
                (dupe_id, genre_id)
            )
            deleted += 1
        else:
            conn.execute(
                "UPDATE album_genres SET album_id=? WHERE album_id=? AND genre_id=?",
                (keeper_id, dupe_id, genre_id)
            )
            moved += 1
    stats["album_genres"] = {"moved": moved, "deleted": deleted}

    # ── album_metadata ───────────────────────────────────────────────────────
    # PK es album_id — si keeper ya tiene metadata, mergeamos campos vacíos
    dupe_meta = conn.execute(
        "SELECT * FROM album_metadata WHERE album_id=?", (dupe_id,)
    ).fetchone()
    if dupe_meta:
        cols = [d[0] for d in conn.execute(
            "PRAGMA table_info(album_metadata)"
        ).fetchall()]
        keeper_meta = conn.execute(
            "SELECT * FROM album_metadata WHERE album_id=?", (keeper_id,)
        ).fetchone()
        if keeper_meta:
            # Merge: para cada campo, usar el valor del keeper si no está vacío,
            # sino usar el del dupe
            keeper_dict = dict(zip(cols, keeper_meta))
            dupe_dict   = dict(zip(cols, dupe_meta))
            updates = []
            vals    = []
            for col in cols:
                if col == "album_id":
                    continue
                if not keeper_dict.get(col) and dupe_dict.get(col):
                    updates.append(f"{col}=?")
                    vals.append(dupe_dict[col])
            if updates:
                vals.append(keeper_id)
                conn.execute(
                    f"UPDATE album_metadata SET {', '.join(updates)} WHERE album_id=?",
                    vals
                )
            conn.execute(
                "DELETE FROM album_metadata WHERE album_id=?", (dupe_id,)
            )
            stats["album_metadata"] = {"merged": 1}
        else:
            conn.execute(
                "UPDATE album_metadata SET album_id=? WHERE album_id=?",
                (keeper_id, dupe_id)
            )
            stats["album_metadata"] = {"moved": 1}

    # ── user_heard ───────────────────────────────────────────────────────────
    uh_rows = conn.execute(
        "SELECT user_id FROM user_heard WHERE album_id=?", (dupe_id,)
    ).fetchall()
    moved = deleted = 0
    for (user_id,) in uh_rows:
        exists = conn.execute(
            "SELECT 1 FROM user_heard WHERE user_id=? AND album_id=?",
            (user_id, keeper_id)
        ).fetchone()
        if exists:
            conn.execute(
                "DELETE FROM user_heard WHERE user_id=? AND album_id=?",
                (user_id, dupe_id)
            )
            deleted += 1
        else:
            conn.execute(
                "UPDATE user_heard SET album_id=? WHERE user_id=? AND album_id=?",
                (keeper_id, user_id, dupe_id)
            )
            moved += 1
    stats["user_heard"] = {"moved": moved, "deleted": deleted}

    return stats


def repoint_artist_fks(conn: sqlite3.Connection,
                        dupe_id: int, keeper_id: int) -> int:
    """Reapunta albums.artist_id de dupe → keeper. Devuelve nº de álbumes movidos."""
    # albums sin conflicto (artist no tiene el mismo álbum bajo keeper_id)
    rows = conn.execute(
        "SELECT id, name FROM albums WHERE artist_id=?", (dupe_id,)
    ).fetchall()
    moved = 0
    for alb_id, alb_name in rows:
        exists = conn.execute(
            "SELECT id FROM albums WHERE artist_id=? AND name=?",
            (keeper_id, alb_name)
        ).fetchone()
        if not exists:
            conn.execute(
                "UPDATE albums SET artist_id=? WHERE id=?",
                (keeper_id, alb_id)
            )
            moved += 1
        # Si ya existe bajo keeper → ese álbum es en sí mismo un duplicado
        # que será resuelto en la fase de dedup_albums
    return moved


def dedup(db_path: str, dry_run: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # evitar errores de FK durante la limpieza

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Base de datos: {db_path}")
    print("=" * 60)

    # ── Fase 1: duplicados de álbumes ─────────────────────────────────────────
    album_dupes = find_duplicate_albums(conn)
    print(f"\n📀 Álbumes duplicados: {len(album_dupes)} grupos")

    total_albums_removed = 0
    for g in album_dupes:
        artist_name = conn.execute(
            "SELECT name FROM artists WHERE id=?", (g["artist_id"],)
        ).fetchone()
        artist_name = artist_name[0] if artist_name else f"artist_id={g['artist_id']}"
        print(f"  [{g['count']}x] {artist_name} — {g['name']}")
        print(f"       keeper={g['keeper']}  dupes={g['dupes']}")

        if not dry_run:
            for dupe_id in g["dupes"]:
                stats = repoint_album_fks(conn, dupe_id, g["keeper"])
                conn.execute("DELETE FROM albums WHERE id=?", (dupe_id,))
                total_albums_removed += 1
                # Mostrar cambios relevantes
                for tbl, s in stats.items():
                    if any(v > 0 for v in s.values()):
                        print(f"       {tbl}: {s}")

    if not dry_run:
        conn.commit()
        print(f"\n  ✅ {total_albums_removed} álbumes duplicados eliminados")

    # ── Fase 2: duplicados de artistas ────────────────────────────────────────
    artist_dupes = find_duplicate_artists(conn)
    print(f"\n🎤 Artistas duplicados: {len(artist_dupes)} grupos")

    total_artists_removed = 0
    for g in artist_dupes:
        print(f"  [{g['count']}x] '{g['name']}'")
        print(f"       keeper={g['keeper']}  dupes={g['dupes']}")

        if not dry_run:
            for dupe_id in g["dupes"]:
                moved = repoint_artist_fks(conn, dupe_id, g["keeper"])
                conn.execute("DELETE FROM artists WHERE id=?", (dupe_id,))
                total_artists_removed += 1
                print(f"       albums reapuntados: {moved}")

    if not dry_run:
        conn.commit()
        print(f"\n  ✅ {total_artists_removed} artistas duplicados eliminados")

    # ── Fase 3: segunda pasada de álbumes (pueden haber aparecido nuevos dupes
    #            tras consolidar artistas) ──────────────────────────────────────
    if not dry_run:
        album_dupes2 = find_duplicate_albums(conn)
        if album_dupes2:
            print(f"\n📀 Segunda pasada álbumes (tras consolidar artistas): "
                  f"{len(album_dupes2)} grupos")
            removed2 = 0
            for g in album_dupes2:
                for dupe_id in g["dupes"]:
                    repoint_album_fks(conn, dupe_id, g["keeper"])
                    conn.execute("DELETE FROM albums WHERE id=?", (dupe_id,))
                    removed2 += 1
            conn.commit()
            print(f"  ✅ {removed2} álbumes adicionales eliminados")

    # ── Resumen final ─────────────────────────────────────────────────────────
    if not dry_run:
        n_albums  = conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
        n_artists = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
        n_ca      = conn.execute("SELECT COUNT(*) FROM collection_albums").fetchone()[0]
        n_ag      = conn.execute("SELECT COUNT(*) FROM album_genres").fetchone()[0]
        n_uh      = conn.execute("SELECT COUNT(*) FROM user_heard").fetchone()[0]
        print(f"\n📊 Estado final:")
        print(f"   albums:            {n_albums}")
        print(f"   artists:           {n_artists}")
        print(f"   collection_albums: {n_ca}")
        print(f"   album_genres:      {n_ag}")
        print(f"   user_heard:        {n_uh}")

        # Verificación: no deben quedar duplicados
        remaining_alb = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT artist_id, name FROM albums
                GROUP BY artist_id, name HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        remaining_art = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT name FROM artists
                GROUP BY name HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        if remaining_alb == 0 and remaining_art == 0:
            print("\n  ✅ Sin duplicados restantes")
        else:
            print(f"\n  ⚠  Duplicados restantes: {remaining_alb} grupos álbumes, "
                  f"{remaining_art} grupos artistas")

        print("\n🧹 Ejecutando VACUUM...")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()
        # VACUUM necesita conexión nueva fuera de transacción
        conn2 = sqlite3.connect(db_path)
        conn2.execute("VACUUM")
        conn2.close()
        print("  ✅ VACUUM completado")
    else:
        conn.close()
        print(f"\n[DRY-RUN] No se ha modificado nada. "
              f"Ejecuta sin --dry-run para aplicar los cambios.")


def main():
    parser = argparse.ArgumentParser(
        description="Elimina duplicados de albums/artists en must_hear.db y repara FKs"
    )
    parser.add_argument("--db", required=True,
                        help="Ruta a must_hear.db")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra qué se haría, sin modificar la DB")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"❌ No existe: {args.db}", file=sys.stderr)
        sys.exit(1)

    dedup(args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

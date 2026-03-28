#!/usr/bin/env python3
"""
merge_youtube_from_a_to_b.py — One-off migration script.

Copies YouTube data from version A (must_hear_rym_new.db) into version B
(must_hear_youtube.db), which is kept as the authoritative database.

Data transferred:
  - albums.yt_id        (video ID used in embeds)
  - albums.youtube_url  (full URL, if present)

Matching strategy (in order of preference):
  1. release_group_mbid  — most reliable, survives renames
  2. artist name + album name (case-insensitive, normalised)

Albums already having a yt_id in B are left untouched.

Usage:
    python3 db/merge_youtube_from_a_to_b.py
    python3 db/merge_youtube_from_a_to_b.py --dry-run
    python3 db/merge_youtube_from_a_to_b.py \
        --db-a db/must_hear_rym_new.db \
        --db-b db/must_hear_youtube.db
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


# ── normalisation ────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for fuzzy matching."""
    s = (s or "").lower()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


# ── main ─────────────────────────────────────────────────────────────────────

def run(db_a: Path, db_b: Path, dry_run: bool) -> None:
    print(f"  A (fuente YouTube) : {db_a}")
    print(f"  B (destino, master): {db_b}")
    if dry_run:
        print("  [dry-run: no se escribirá nada]\n")

    conn_a = sqlite3.connect(str(db_a))
    conn_b = sqlite3.connect(str(db_b))
    conn_b.execute("PRAGMA journal_mode=WAL")

    # ── Load YouTube data from A ──────────────────────────────────────────────
    rows_a = conn_a.execute("""
        SELECT al.release_group_mbid, ar.name, al.name, al.yt_id, al.youtube_url
        FROM albums al
        JOIN artists ar ON ar.id = al.artist_id
        WHERE al.yt_id IS NOT NULL AND al.yt_id != ''
    """).fetchall()

    print(f"  Albums con yt_id en A: {len(rows_a)}")

    # ── Build lookup structures for B ─────────────────────────────────────────
    # mbid → (b_album_id, b_yt_id)
    mbid_map: dict[str, tuple[int, str | None]] = {}
    # (norm_artist, norm_title) → (b_album_id, b_yt_id)
    name_map: dict[tuple[str, str], tuple[int, str | None]] = {}

    for row in conn_b.execute("""
        SELECT al.id, al.release_group_mbid, ar.name, al.name, al.yt_id
        FROM albums al
        JOIN artists ar ON ar.id = al.artist_id
    """).fetchall():
        bid, mbid, artist, title, byt = row
        if mbid:
            mbid_map[mbid] = (bid, byt)
        name_map[(_norm(artist), _norm(title))] = (bid, byt)

    # ── Match and collect updates ─────────────────────────────────────────────
    updates: list[tuple[str, str | None, int]] = []  # (yt_id, youtube_url, b_album_id)
    skipped_already = 0
    skipped_no_match = 0

    for mbid, artist, title, yt_id, yt_url in rows_a:
        # Try mbid first
        match = mbid_map.get(mbid) if mbid else None
        if match is None:
            match = name_map.get((_norm(artist), _norm(title)))

        if match is None:
            skipped_no_match += 1
            continue

        b_album_id, b_yt_id = match
        if b_yt_id:
            skipped_already += 1
            continue

        updates.append((yt_id, yt_url, b_album_id))

    print(f"  Ya tienen yt_id en B (sin cambios): {skipped_already}")
    print(f"  Sin match en B (no encontrados):    {skipped_no_match}")
    print(f"  A actualizar en B:                  {len(updates)}")

    if not updates:
        print("\n  Nada que hacer.")
        conn_a.close()
        conn_b.close()
        return

    # ── Preview ──────────────────────────────────────────────────────────────
    print("\n  Primeras 10 actualizaciones:")
    preview_ids = {u[2] for u in updates[:10]}
    preview_rows = conn_b.execute("""
        SELECT al.id, ar.name, al.name
        FROM albums al JOIN artists ar ON ar.id = al.artist_id
        WHERE al.id IN ({})
    """.format(",".join("?" * len(preview_ids))), list(preview_ids)).fetchall()
    id_to_name = {r[0]: f"{r[1]} — {r[2]}" for r in preview_rows}

    for yt_id, yt_url, bid in updates[:10]:
        print(f"    [{bid}] {id_to_name.get(bid, '?')}  →  {yt_id}")
    if len(updates) > 10:
        print(f"    … y {len(updates) - 10} más")

    # ── Apply ─────────────────────────────────────────────────────────────────
    if not dry_run:
        for yt_id, yt_url, bid in updates:
            conn_b.execute(
                "UPDATE albums SET yt_id=?, youtube_url=COALESCE(youtube_url,?) WHERE id=?",
                (yt_id, yt_url, bid),
            )
        conn_b.commit()
        print(f"\n  ✅ {len(updates)} álbumes actualizados en B.")
    else:
        print("\n  [dry-run: se habrían actualizado los álbumes anteriores]")

    conn_a.close()
    conn_b.close()


def main() -> None:
    here = Path(__file__).parent
    p = argparse.ArgumentParser(description="Merge yt_id from DB-A into DB-B")
    p.add_argument("--db-a",    default=str(here / "must_hear_rym_new.db"),
                   help="Fuente: DB con yt_ids (default: must_hear_rym_new.db)")
    p.add_argument("--db-b",    default=str(here / "must_hear_youtube.db"),
                   help="Destino: DB master a actualizar (default: must_hear_youtube.db)")
    p.add_argument("--dry-run", action="store_true",
                   help="Mostrar qué se haría sin escribir nada")
    args = p.parse_args()
    run(Path(args.db_a), Path(args.db_b), args.dry_run)


if __name__ == "__main__":
    main()

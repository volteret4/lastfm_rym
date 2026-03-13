#!/usr/bin/env python3
"""
4chan /mu/ Chart Image → Must Hear Collection

Downloads a chart image (essential albums grid), runs OCR to extract
artist/album candidates, then verifies each against MusicBrainz.
When MB search fails, prompts the user interactively to correct the query.

Called from html_must_hear.py when --series URL points to an image file
(.jpg/.jpeg/.png/.gif/.webp/.bmp).

Usage:
    python3 html_must_hear.py \\
        --must-hear-db db/must_hear.db \\
        --scrobbles-db db/scrobbles.db \\
        --collection "4chan /mu/" \\
        --series "https://static.wikitide.net/.../Essential50srockandroll.jpg" \\
        --name "Essential 50s Rock and Roll"

Requires:
    pip install Pillow pytesseract
    apt install tesseract-ocr

Workflow:
  1. First run: downloads image, OCRs it, searches MB for each candidate.
     Unrecognised albums trigger an interactive prompt (correct or skip).
  2. Results saved to <out_dir>/4chan_cache.json (human-editable JSON).
  3. Re-run with --from-cache to regenerate HTML from the saved cache
     without re-scanning or re-asking.
"""

import json, re, sys, time, sqlite3, urllib.request, urllib.parse
import os, tempfile
from pathlib import Path
from datetime import datetime

UA  = "MustHearAlbums/1.0 (https://github.com/musthear)"
CAA = "https://coverartarchive.org/release-group"

# ── DEP CHECK ────────────────────────────────────────────────────────────────

def _check_deps():
    missing = []
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow       →  pip install Pillow")
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        missing.append("pytesseract  →  pip install pytesseract  +  apt install tesseract-ocr")
    if missing:
        raise RuntimeError("Dependencias OCR no encontradas:\n  " + "\n  ".join(missing))


# ── IMAGE DOWNLOAD ────────────────────────────────────────────────────────────

def _download_image(url: str) -> Path:
    ext = Path(url.split("?")[0]).suffix or ".jpg"
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        tmp.write(r.read())
    tmp.close()
    return Path(tmp.name)


# ── OCR ───────────────────────────────────────────────────────────────────────

def _ocr_image(img_path: Path, conf_threshold: int = 60) -> list[dict]:
    """
    Run Tesseract on the image and return high-confidence word boxes.
    conf_threshold: discard words below this confidence (0-100).
    Raising this threshold reduces OCR noise from cover art.
    """
    from PIL import Image, ImageEnhance
    import pytesseract

    img = Image.open(img_path).convert("RGB")
    w, h = img.size

    if w < 1200:
        scale = 1200 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    img = ImageEnhance.Contrast(img).enhance(1.4)

    data = pytesseract.image_to_data(
        img,
        config="--psm 11 --oem 3",
        output_type=pytesseract.Output.DICT,
    )

    boxes = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        conf = int(data["conf"][i])
        if conf < conf_threshold:
            continue
        boxes.append({
            "text":   text,
            "left":   data["left"][i],
            "top":    data["top"][i],
            "width":  data["width"][i],
            "height": data["height"][i],
            "conf":   conf,
        })
    return boxes


# ── LINE CLUSTERING ───────────────────────────────────────────────────────────

def _cluster_lines(boxes: list[dict], line_gap: int = 14) -> list[str]:
    """Merge word boxes into text lines by vertical proximity."""
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: b["top"])
    lines: list[list] = []   # [[avg_mid_y, [box, ...]], ...]

    for box in boxes:
        mid = box["top"] + box["height"] / 2
        placed = False
        for line in lines:
            if abs(mid - line[0]) <= line_gap:
                line[1].append(box)
                tops = [b["top"] + b["height"] / 2 for b in line[1]]
                line[0] = sum(tops) / len(tops)
                placed = True
                break
        if not placed:
            lines.append([mid, [box]])

    result = []
    for _, bs in sorted(lines, key=lambda l: l[0]):
        words = [b["text"] for b in sorted(bs, key=lambda b: b["left"])]
        result.append(" ".join(words))
    return result


# ── TEXT FILTERING ────────────────────────────────────────────────────────────

def _alpha_ratio(s: str) -> float:
    """Fraction of characters that are letters or spaces."""
    if not s:
        return 0.0
    return sum(1 for c in s if c.isalpha() or c == " ") / len(s)


def _is_noise(s: str) -> bool:
    """True for lines that are clearly OCR garbage, not album text."""
    s = s.strip()
    if len(s) < 3:
        return True
    # Must have at least 55% letters/spaces
    if _alpha_ratio(s) < 0.55:
        return True
    # Short all-caps blobs (cover art labels: "COLEMAN", "GO", "R")
    if re.fullmatch(r"[A-Z0-9 ]{1,6}", s):
        return True
    # Pure numbers or punctuation
    if re.fullmatch(r"[^a-zA-Z]+", s):
        return True
    # Looks like a section header ("Jazz By Year: The 1960s")
    if ":" in s and re.search(r"\d{4}", s):
        return True
    return False


def _clean(s: str) -> str:
    """Strip OCR punctuation noise from extracted groups."""
    s = re.sub(r"[|(){}\[\]\\@#$%^*+=~`<>]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ── PARSER ────────────────────────────────────────────────────────────────────

def parse_ocr_to_candidates(lines: list[str]) -> list[dict]:
    """
    Convert OCR lines into (artist, title) candidate pairs.

    Three patterns tried in order:
      A)  "N. Artist - Album"  /  "N) Artist — Album"
      B)  "Artist - Album"  (no number)
      C)  Two consecutive clean short lines  (artist \\n album)

    Returns list of {number, artist, title}.
    """
    candidates = []
    rank = 1
    i    = 0

    # Pre-filter obvious noise
    clean_lines = [l for l in lines if not _is_noise(l)]

    while i < len(clean_lines):
        raw  = clean_lines[i]
        line = _clean(raw)

        if _is_noise(line):
            i += 1
            continue

        # ── Pattern A: "N. Artist - Album" (raw line keeps digit+punct) ──
        m = re.match(r'^(\d+)\s*[.)]\s*(.+?)\s+[-–—]\s+(.+)$', raw)
        if m:
            artist = _clean(m.group(2))
            title  = _clean(m.group(3))
            if not _is_noise(artist) and not _is_noise(title):
                candidates.append({"number": int(m.group(1)),
                                   "artist": artist, "title": title})
            i += 1
            continue

        # ── Pattern B: "Artist - Album" (no leading number) ───────────────
        m = re.match(r'^(.+?)\s+[-–—]\s+(.+)$', line)
        if m:
            artist = _clean(m.group(1))
            title  = _clean(m.group(2))
            if (not _is_noise(artist) and not _is_noise(title)
                    and len(artist) < 60 and len(title) < 80
                    and _alpha_ratio(artist) >= 0.60
                    and _alpha_ratio(title)  >= 0.60):
                candidates.append({"number": rank, "artist": artist, "title": title})
                rank += 1
                i += 1
                continue

        # ── Pattern C: two consecutive short clean lines ───────────────────
        # Stricter than A/B: both lines must look like real name text,
        # not cover-art fragments.  Requires title-case or mixed-case,
        # no all-caps (which usually means cover label noise).
        if i + 1 < len(clean_lines):
            next_line = _clean(clean_lines[i + 1])
            artist_ok = (
                not _is_noise(next_line)
                and len(line) <= 45 and len(next_line) <= 65
                and _alpha_ratio(line)      >= 0.70
                and _alpha_ratio(next_line) >= 0.70
                and not re.match(r'^\d+[.)]', next_line)
                # Reject lines that are ALL UPPERCASE (cover art fragments)
                and not (line.isupper() or next_line.isupper())
                # Reject lines with colons (headers) or leading numbers
                and ":" not in line and ":" not in next_line
                # Require at least one lowercase letter in each line
                and re.search(r'[a-z]', line)
                and re.search(r'[a-z]', next_line)
            )
            if artist_ok:
                candidates.append({"number": rank, "artist": line, "title": next_line})
                rank += 1
                i += 2
                continue

        i += 1

    return candidates


# ── MUSICBRAINZ ───────────────────────────────────────────────────────────────

def _mb_search(query: str) -> dict:
    """
    Search MB for a release-group using a free-form query string.
    query: "Artist - Album"  or just "Artist Album"
    Returns {mbid, artist, title, year} or {}.
    """
    try:
        # Try to split artist/album from query
        m = re.match(r'^(.+?)\s+[-–—]\s+(.+)$', query)
        if m:
            artist, album = m.group(1).strip(), m.group(2).strip()
            q = f'releasegroup:"{album}" AND artist:"{artist}"'
        else:
            q = query   # fallback: full-text search

        url = (f"https://musicbrainz.org/ws/2/release-group"
               f"?query={urllib.parse.quote(q)}&limit=3&fmt=json")
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())

        rgs = data.get("release-groups", [])
        if not rgs:
            return {}

        best = rgs[0]
        year_str = best.get("first-release-date", "") or ""
        year     = int(year_str[:4]) if re.match(r'\d{4}', year_str) else None

        # Extract canonical artist name from MB result
        credits  = best.get("artist-credit", [])
        mb_artist = "".join(
            (c.get("name") or c.get("artist", {}).get("name", "")) + c.get("joinphrase", "")
            for c in credits if isinstance(c, dict)
        ).strip() or best.get("artist-credit-phrase", "")

        return {
            "mbid":   best.get("id", ""),
            "artist": mb_artist or (m.group(1) if m else query),
            "title":  best.get("title", m.group(2) if m else query),
            "year":   year,
        }
    except Exception:
        return {}


# ── INTERACTIVE VERIFICATION ──────────────────────────────────────────────────

def _interactive_enrich(candidates: list[dict]) -> list[dict]:
    """
    For each candidate:
      - Search MB. If found, use MB canonical names.
      - If not found and running in a TTY, prompt the user to correct
        the search query (or skip the entry).
    Returns only accepted albums (with mbid/year/cover_url populated).
    """
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    albums  = []
    total   = len(candidates)

    print(f"\n  🔍 Verificando {total} candidatos en MusicBrainz...\n")

    for idx, cand in enumerate(candidates, 1):
        query = f"{cand['artist']} - {cand['title']}"
        prefix = f"  [{idx:2d}/{total}]"

        mb = _mb_search(query)
        time.sleep(1)   # MB rate limit

        if mb.get("mbid"):
            cand["mbid"]      = mb["mbid"]
            cand["artist"]    = mb.get("artist") or cand["artist"]
            cand["title"]     = mb.get("title")  or cand["title"]
            cand["year"]      = cand.get("year") or mb.get("year")
            cand["cover_url"] = f"{CAA}/{mb['mbid']}/front-500"
            albums.append(cand)
            print(f"{prefix} ✅  {cand['artist']} — {cand['title']}")
            continue

        # ── Not found ──────────────────────────────────────────────────────
        print(f"{prefix} ❌  {query!r}")

        if not is_tty:
            print(f"           (omitido — modo no interactivo)")
            continue

        # Interactive: ask user to correct or skip
        print(f"           [Enter]=omitir  [q]=terminar  o escribe 'Artista - Álbum':")
        try:
            correction = input("           > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not correction:
            continue
        if correction.lower() == "q":
            break

        # Retry with user correction
        mb2 = _mb_search(correction)
        time.sleep(1)

        if mb2.get("mbid"):
            cand["mbid"]      = mb2["mbid"]
            cand["artist"]    = mb2.get("artist") or correction.split(" - ")[0]
            cand["title"]     = mb2.get("title")  or correction.split(" - ", 1)[-1]
            cand["year"]      = cand.get("year") or mb2.get("year")
            cand["cover_url"] = f"{CAA}/{mb2['mbid']}/front-500"
            albums.append(cand)
            print(f"           ✅  {cand['artist']} — {cand['title']}")
        else:
            # Ask whether to add anyway (manual, no MBID)
            print(f"           ⚠  Todavía no encontrado en MB.")
            try:
                keep = input("           ¿Añadir igualmente sin MBID? (s/Enter=omitir) > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if keep == "s":
                m = re.match(r'^(.+?)\s+[-–—]\s+(.+)$', correction)
                if m:
                    cand["artist"] = _clean(m.group(1))
                    cand["title"]  = _clean(m.group(2))
                else:
                    cand["artist"] = correction
                    cand["title"]  = ""
                cand["mbid"]      = ""
                cand["cover_url"] = ""
                albums.append(cand)

    print(f"\n  ✅ {len(albums)}/{total} candidatos OCR aceptados")

    # ── Offer manual additions ─────────────────────────────────────────────
    if is_tty:
        print(f"  ➕ ¿Añadir álbumes manualmente? (s/Enter=no)")
        try:
            ans = input("     > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans == "s":
            next_rank = (max((a["number"] for a in albums), default=0) + 1)
            print("     Escribe 'Artista - Álbum' por línea. Enter vacío para terminar.")
            while True:
                try:
                    entry = input(f"     [{next_rank}] > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not entry:
                    break
                mb3 = _mb_search(entry)
                time.sleep(1)
                m  = re.match(r'^(.+?)\s+[-–—]\s+(.+)$', entry)
                ar = _clean(m.group(1)) if m else entry
                ti = _clean(m.group(2)) if m else ""
                if mb3.get("mbid"):
                    ar = mb3.get("artist") or ar
                    ti = mb3.get("title")  or ti
                    albums.append({
                        "number": next_rank, "artist": ar, "title": ti,
                        "mbid": mb3["mbid"], "year": mb3.get("year"),
                        "cover_url": f"{CAA}/{mb3['mbid']}/front-500",
                        "rym": "", "yt_id": "", "genres": [],
                        "desc_lfm_album": "", "desc_lfm_artist": "",
                        "desc_mb_album":  "", "desc_mb_artist":  "",
                    })
                    print(f"     ✅ {ar} — {ti}")
                else:
                    albums.append({
                        "number": next_rank, "artist": ar, "title": ti,
                        "mbid": "", "year": None, "cover_url": "",
                        "rym": "", "yt_id": "", "genres": [],
                        "desc_lfm_album": "", "desc_lfm_artist": "",
                        "desc_mb_album":  "", "desc_mb_artist":  "",
                    })
                    print(f"     ⚠  No encontrado en MB — añadido sin MBID")
                next_rank += 1

    print()
    return albums


# ── SCAN ─────────────────────────────────────────────────────────────────────

def scan_image(img_url: str, cache_path: Path, from_cache: bool = False) -> list[dict]:
    """
    Full pipeline: download → OCR → parse → interactive MB verification → cache.
    If from_cache=True and cache exists with data, skip scan entirely.
    """
    if from_cache and cache_path.exists():
        data = json.loads(cache_path.read_text())
        if data:
            print(f"  📦 Caché: {len(data)} álbumes desde {cache_path}")
            return data
        print("  ⚠  Caché vacío, re-escaneando...")

    if not from_cache and cache_path.exists():
        data = json.loads(cache_path.read_text())
        if data:
            print(f"  📦 Caché: {len(data)} álbumes desde {cache_path}")
            return data

    _check_deps()

    print(f"  🖼  Descargando: {img_url}")
    img_path = _download_image(img_url)
    try:
        print("  🔍 OCR...")
        boxes = _ocr_image(img_path, conf_threshold=60)
        print(f"     {len(boxes)} palabras (conf ≥60)")
        lines      = _cluster_lines(boxes)
        candidates = parse_ocr_to_candidates(lines)
        print(f"  📝 {len(candidates)} candidatos tras filtrar ruido OCR")
    finally:
        os.unlink(img_path)

    if not candidates:
        print("  ⚠  Sin candidatos. La imagen puede tener texto demasiado pequeño o ruidoso.")
        cache_path.write_text("[]")
        return []

    # Seed empty fields
    for c in candidates:
        c.setdefault("mbid",           "")
        c.setdefault("year",           None)
        c.setdefault("cover_url",      "")
        c.setdefault("rym",            "")
        c.setdefault("yt_id",          "")
        c.setdefault("genres",         [])
        c.setdefault("desc_lfm_album",  "")
        c.setdefault("desc_lfm_artist", "")
        c.setdefault("desc_mb_album",   "")
        c.setdefault("desc_mb_artist",  "")

    albums = _interactive_enrich(candidates)

    cache_path.write_text(json.dumps(albums, ensure_ascii=False, indent=2))
    print(f"  💾 Caché guardado: {cache_path}")
    if albums:
        print(f"  💡 Edita {cache_path} para corregir cualquier error antes de re-ejecutar.")
    return albums


# ── DB SYNC ───────────────────────────────────────────────────────────────────

def sync_to_db(mh_conn: sqlite3.Connection, slug: str, name: str,
               source_url: str, albums: list[dict]) -> list[dict]:
    """
    Upsert a chart collection into must_hear.db.
    Existing collection_albums for this slug are replaced entirely.
    """
    ts = int(time.time())

    # Collection: create or update
    row = mh_conn.execute("SELECT id FROM collections WHERE slug=?", (slug,)).fetchone()
    if row:
        coll_id = row[0]
        mh_conn.execute(
            "UPDATE collections SET name=?, source_url=?, source_type=?, last_updated=? WHERE id=?",
            (name, source_url, "image_ocr", ts, coll_id)
        )
        # Remove old entries so we start fresh
        mh_conn.execute("DELETE FROM collection_albums WHERE collection_id=?", (coll_id,))
        print(f"  📋 Colección existente '{slug}' (id={coll_id}) — reemplazando contenido")
    else:
        mh_conn.execute(
            "INSERT INTO collections (name, slug, source_url, source_type, last_updated, added_timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (name, slug, source_url, "image_ocr", ts, ts)
        )
        coll_id = mh_conn.execute(
            "SELECT id FROM collections WHERE slug=?", (slug,)
        ).fetchone()[0]
        print(f"  📋 Colección nueva '{slug}' (id={coll_id})")
    mh_conn.commit()

    result = []
    for album in albums:
        artist_name = album.get("artist", "").strip()
        title       = album.get("title",  "").strip()
        if not artist_name or not title:
            continue

        mbid      = album.get("mbid")    or None
        year      = album.get("year")
        rank      = album.get("number",  0)
        cover_url = album.get("cover_url", "")

        # Artist upsert
        ar = mh_conn.execute("SELECT id FROM artists WHERE name=?", (artist_name,)).fetchone()
        if ar:
            artist_id = ar[0]
        else:
            mh_conn.execute(
                "INSERT INTO artists (name, added_timestamp) VALUES (?,?)", (artist_name, ts)
            )
            artist_id = mh_conn.execute(
                "SELECT id FROM artists WHERE name=?", (artist_name,)
            ).fetchone()[0]

        # Album upsert
        al = None
        if mbid:
            al = mh_conn.execute(
                "SELECT id FROM albums WHERE release_group_mbid=?", (mbid,)
            ).fetchone()
        if not al:
            al = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?", (artist_id, title)
            ).fetchone()

        if al:
            album_id = al[0]
            mh_conn.execute(
                "UPDATE albums SET "
                "release_group_mbid = CASE WHEN release_group_mbid IS NULL THEN ? ELSE release_group_mbid END, "
                "year      = COALESCE(year, ?), "
                "cover_url = CASE WHEN (cover_url IS NULL OR cover_url='') AND ?!='' THEN ? ELSE cover_url END, "
                "last_updated = ? WHERE id=?",
                (mbid, year, cover_url, cover_url, ts, album_id)
            )
        else:
            mh_conn.execute(
                "INSERT INTO albums (artist_id, name, year, release_group_mbid, cover_url, added_timestamp) "
                "VALUES (?,?,?,?,?,?)",
                (artist_id, title, year, mbid, cover_url or None, ts)
            )
            album_id = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?", (artist_id, title)
            ).fetchone()[0]

        mh_conn.execute(
            "INSERT INTO collection_albums (collection_id, album_id, rank) VALUES (?,?,?)",
            (coll_id, album_id, rank)
        )
        merged       = dict(album)
        merged["id"] = album_id
        result.append(merged)

    mh_conn.execute(
        "UPDATE collections SET total_albums=?, last_updated=? WHERE id=?",
        (len(result), ts, coll_id)
    )
    mh_conn.commit()
    print(f"  💾 DB: {len(result)} álbumes guardados en '{slug}'")
    return result


# ── MAIN RUNNER ───────────────────────────────────────────────────────────────

def run_4chan(args, root_dir: Path) -> None:
    """
    Entry point called from html_must_hear.py when --series is an image URL.
    """
    from html_must_hear import (
        mh_get_users, mh_get_user_albums, mh_load_collection, check_heard,
        mh_album_to_json, render_collection_index_html, render_user_html,
        update_root_index, update_collection_group_index,
    )

    img_url    = args.series
    name       = (getattr(args, "name", "") or "").strip()
    if not name:
        name = Path(img_url.split("?")[0]).stem.replace("_", " ").title()

    slug       = getattr(args, "slug", None)
    collection = getattr(args, "collection", None)
    index_only = getattr(args, "index_only", False)
    from_cache = getattr(args, "from_cache", False)

    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:48]

    if collection:
        coll_slug = re.sub(r"[^a-z0-9]+", "_", collection.lower()).strip("_")
        out_dir   = root_dir / coll_slug / slug
    else:
        coll_slug = None
        out_dir   = root_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = out_dir / "4chan_cache.json"
    generated  = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── DB ──────────────────────────────────────────────────────────────────
    mh_conn: sqlite3.Connection | None = getattr(args, "_4chan_mh_conn", None)
    if mh_conn is None and getattr(args, "must_hear_db", None):
        p = Path(args.must_hear_db)
        if p.exists():
            mh_conn = sqlite3.connect(str(p))
            mh_conn.execute("PRAGMA journal_mode=WAL")

    scr_path = getattr(args, "scrobbles_db", None) or getattr(args, "db", None)

    # ── Albums ──────────────────────────────────────────────────────────────
    albums_from_db = False

    if mh_conn and (index_only or from_cache):
        albums = mh_load_collection(mh_conn, slug)
        if albums:
            albums_from_db = True
            print(f"  📦 {len(albums)} álbumes desde must_hear.db ('{slug}')")

    if not albums_from_db:
        if index_only:
            if cache_path.exists():
                albums = json.loads(cache_path.read_text())
                print(f"  📦 {len(albums)} álbumes desde caché")
            else:
                print(f"  ❌ --index-only pero no hay caché: {cache_path}")
                return
        else:
            albums = scan_image(img_url, cache_path, from_cache=from_cache)
            if not albums:
                print("  ❌ Sin álbumes aceptados. Edita el caché y usa --from-cache.")
                return
            if mh_conn:
                albums = sync_to_db(mh_conn, slug, name, img_url, albums)
                albums_from_db = True

    # ── Users & scrobbles ────────────────────────────────────────────────────
    if mh_conn:
        users = mh_get_users(mh_conn)
    else:
        users = getattr(args, "users", None) or []
    print(f"👥 Usuarios: {', '.join(users) or '(ninguno)'}")

    if scr_path:
        import sqlite3 as _sq
        _scr = _sq.connect(scr_path)
        users_heard = {u: mh_get_user_albums(_scr, u) for u in users}
        _scr.close()
    else:
        users_heard = {u: set() for u in users}

    COVER_PH = (
        "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20"
        "width=%22250%22%20height=%22250%22%20viewBox=%220%200%20250%20250%22%3E"
        "%3Crect%20width=%22250%22%20height=%22250%22%20fill=%22%23111%22/%3E%3C/svg%3E"
    )

    # ── Per-user HTML ────────────────────────────────────────────────────────
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)
    users_index = []

    for user in users:
        scrobbles  = users_heard.get(user, set())
        albums_data = []

        for album in albums:
            heard = check_heard(scrobbles, album)
            if albums_from_db:
                jdata = mh_album_to_json(album, heard)
            else:
                jdata = {
                    "artist":          album.get("artist", ""),
                    "title":           album.get("title", ""),
                    "year":            album.get("year"),
                    "mbid":            album.get("mbid", ""),
                    "cover_url":       album.get("cover_url", "") or COVER_PH,
                    "rym":             album.get("rym", ""),
                    "yt_id":           album.get("yt_id", ""),
                    "genres":          album.get("genres", []),
                    "desc_lfm_album":  album.get("desc_lfm_album", ""),
                    "desc_lfm_artist": album.get("desc_lfm_artist", ""),
                    "desc_mb_album":   album.get("desc_mb_album", ""),
                    "desc_mb_artist":  album.get("desc_mb_artist", ""),
                    "heard":           heard,
                    "number":          album.get("number", 0),
                }
            albums_data.append(jdata)

        heard_count = sum(1 for a in albums_data if a["heard"])
        pct         = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0
        safe_user   = re.sub(r"[^a-z0-9]", "_", user.lower())

        (data_dir / f"{safe_user}.json").write_text(
            json.dumps(albums_data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        (out_dir / f"user_{safe_user}.html").write_text(
            render_user_html(user, albums_data, name, data_file=f"data/{safe_user}.json"),
            encoding="utf-8",
        )
        users_index.append({
            "user": user, "file": f"user_{safe_user}.html",
            "heard": heard_count, "total": len(albums_data), "pct": pct,
        })
        print(f"   {user}: {heard_count}/{len(albums_data)} ({pct}%)")

    users_index.sort(key=lambda u: u["pct"], reverse=True)

    (out_dir / "index.html").write_text(
        render_collection_index_html(users_index, name, generated),
        encoding="utf-8",
    )
    print(f"  📋 {out_dir / 'index.html'}")

    if coll_slug:
        update_collection_group_index(
            root_dir, collection, coll_slug, name, slug, users_index, generated
        )
    else:
        update_root_index(root_dir, name, slug, users_index, generated)

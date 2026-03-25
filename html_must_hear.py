#!/usr/bin/env python3
"""
1001 Albums Must Hear — HTML Generator
Scrapes MusicBrainz series, crosses with last.fm scrobbles DB,
generates per-user HTML grids + index.html
"""

import subprocess, os, json, re, time, argparse, sqlite3, urllib.parse, urllib.request, urllib.error
from html import unescape
from pathlib import Path
from datetime import datetime

# Optional clients — imported lazily so the script works without them
def _try_import(mod):
    try:
        import importlib
        return importlib.import_module(mod)
    except ImportError:
        return None

# ── CONFIG ────────────────────────────────────────────────────────────────────
DEFAULT_SERIES = "https://musicbrainz.org/series/4bc2a338-e1d8-4546-8a61-640da8aaf888"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
CAA = "https://coverartarchive.org/release-group"

# ── SCRAPER ───────────────────────────────────────────────────────────────────

GEN_INDEX = "https://1001albumsgenerator.com/albums"

def _resolve_lastfm_credentials(args) -> tuple[str, str]:
    """Devuelve (api_key, api_secret) resolviendo en este orden:
      1. --lastfm-api-key / --lastfm-api-secret (CLI)
      2. Variables de entorno LASTFM_API_KEY / LASTFM_API_SECRET
      3. SOPS: sops -d --extract '["LASTFM_API_KEY"]' .encrypted.env
    Devuelve ("", "") sin lanzar excepción si no hay credenciales."""
    key    = getattr(args, "lastfm_api_key",    None) or ""
    secret = getattr(args, "lastfm_api_secret", None) or ""

    if not key:
        key    = os.environ.get("LASTFM_API_KEY",    "")
        secret = os.environ.get("LASTFM_API_SECRET", "") or secret

    if not key:
        encrypted = Path(".encrypted.env")
        if encrypted.exists():
            try:
                key = subprocess.check_output(
                    ["sops", "-d", "--extract", '["LASTFM_API_KEY"]', str(encrypted)],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
                secret = subprocess.check_output(
                    ["sops", "-d", "--extract", '["LASTFM_API_SECRET"]', str(encrypted)],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
            except Exception:
                pass

    return key, secret

def curl_get(url: str) -> str:
    r = subprocess.run(
        ["curl", "-s", "-L", "-A", UA, "--max-time", "30", url],
        capture_output=True, text=True
    )
    return r.stdout if r.returncode == 0 else ""

def extract_series_id(url: str) -> str:
    m = re.search(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", url)
    if not m: raise ValueError(f"No MBID in: {url}")
    return m.group(1)

def get_total_pages(html: str) -> int:
    pages = re.findall(r'[?&]page=(\d+)', html)
    return max((int(p) for p in pages), default=1)

def parse_page(html: str) -> list[dict]:
    """Parsea una página de serie MusicBrainz.
    La columna 'number-column' es opcional: algunas series MB no tienen
    numeración explícita (p.ej. listas por año). En ese caso se asigna
    el orden de aparición en la página como número provisional.
    Soporta series de release-groups Y series de releases (entity_type='release').
    """
    items = []
    _counter = [0]  # contador de fila para series sin número
    for row in re.findall(r'<tr class="(?:odd|even)">(.*?)</tr>', html, re.DOTALL):
        # Try release-group first, then release
        title_m = re.search(r'href="/release-group/([a-f0-9-]{36})"[^>]*><bdi>(.*?)</bdi>', row)
        entity_type = "release-group"
        if not title_m:
            title_m = re.search(r'href="/release/([a-f0-9-]{36})"[^>]*><bdi>(.*?)</bdi>', row)
            entity_type = "release"
        if not title_m:
            continue  # fila sin álbum (cabecera de letra, etc.)
        num_m   = re.search(r'<td class="number-column">(\d+)</td>', row)
        # Buscar todos los años en la fila; en series sin número la primera
        # columna <td class="c"> suele ser el año de la lista (ej. "2024") y
        # la segunda el año de lanzamiento. Tomamos el último año encontrado
        # como año del álbum, que suele ser el más preciso.
        year_matches = re.findall(r'<td class="c">(\d{4})</td>', row)
        year = int(year_matches[-1]) if year_matches else None
        artist_m = re.search(r'<td><bdi>(.*?)</bdi></td>', row, re.DOTALL)
        artist = ""
        if artist_m:
            artist = unescape(re.sub(r'<[^>]+>', '', artist_m.group(1))).strip()
            artist = re.sub(r'\s+', ' ', artist)
        _counter[0] += 1
        items.append({
            "number":      int(num_m.group(1)) if num_m else _counter[0],
            "year":        year,
            "title":       unescape(re.sub(r'<[^>]+>', '', title_m.group(2))).strip(),
            "artist":      artist,
            "mbid":        title_m.group(1),
            "entity_type": entity_type,
        })
    return items


def _resolve_release_to_rg(release_mbid: str) -> str:
    """Fetch a release's release-group MBID from the MB API. Returns '' on failure."""
    try:
        url = (f"https://musicbrainz.org/ws/2/release/{release_mbid}"
               f"?inc=release-groups&fmt=json")
        req = urllib.request.Request(url, headers={
            "User-Agent": "MustHearAlbums/1.0 (https://github.com/musthear)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return data.get("release-group", {}).get("id", "")
    except Exception:
        return ""

def fetch_page_with_retry(url: str, retries: int = 3, delay: float = 3.0) -> str:
    for attempt in range(retries):
        html = curl_get(url)
        rows = re.findall(r'<tr class="(?:odd|even)">', html)
        if rows:
            return html
        if attempt < retries - 1:
            wait = delay * (attempt + 1)
            print(f"    ⚠ Vacío, reintentando en {wait:.0f}s...")
            time.sleep(wait)
    return html  # devolver aunque esté vacío

def fetch_series(series_url: str, cache_file: Path, force: bool = False) -> list[dict]:
    if not force and cache_file.exists():
        data = json.loads(cache_file.read_text())
        if data:
            print(f"📦 Caché: {len(data)} álbumes en {cache_file}")
            return data
        print("📦 Caché vacío — re-scrapeando...")

    sid  = extract_series_id(series_url)
    base = f"https://musicbrainz.org/series/{sid}"

    # Primera página para obtener total
    print("📡 Página 1...")
    html = fetch_page_with_retry(f"{base}?page=1")
    if not html: raise RuntimeError("No se pudo obtener la primera página")
    total = get_total_pages(html)
    print(f"📚 {total} páginas detectadas")

    all_items = parse_page(html)
    print(f"  → {len(all_items)} álbumes")

    for page in range(2, total + 1):
        print(f"📡 Página {page}/{total}...")
        time.sleep(2)  # delay conservador para evitar rate limit
        html = fetch_page_with_retry(f"{base}?page={page}")
        items = parse_page(html)
        print(f"  → {len(items)} álbumes")
        all_items.extend(items)

    # ── Resolver releases → release-groups ────────────────────────────────────
    releases = [a for a in all_items if a.get("entity_type") == "release"]
    if releases:
        print(f"🔗 {len(releases)} releases → buscando release-groups en MB API...")
        for i, item in enumerate(releases, 1):
            rg_mbid = _resolve_release_to_rg(item["mbid"])
            if rg_mbid:
                item["mbid"] = rg_mbid
                item["entity_type"] = "release-group"
            else:
                print(f"  ⚠  No se encontró release-group para {item['title']!r} ({item['mbid']})")
            if i < len(releases):
                time.sleep(1)  # MB rate limit

    # Detectar si la serie tiene numeración explícita (number-column en MB)
    # Si todos los números son consecutivos desde 1 con la cuenta total,
    # asumimos numeración real; si no, renumeramos por orden de aparición.
    nums = sorted(a["number"] for a in all_items)
    has_explicit_numbering = (
        nums == list(range(1, len(nums) + 1))
    ) if nums else False

    if not has_explicit_numbering:
        # Renumerar por orden de aparición (ya vienen ordenados por página)
        for i, item in enumerate(all_items, 1):
            item["number"] = i
        print(f"ℹ️  Serie sin numeración explícita — asignados números 1-{len(all_items)}")
    else:
        all_items.sort(key=lambda x: x["number"])
        # Verificar huecos solo en series con numeración real
        nums_set = {a["number"] for a in all_items}
        expected = set(range(1, max(nums_set) + 1)) if nums_set else set()
        missing  = sorted(expected - nums_set)
        if missing:
            print(f"⚠ Huecos en numeración: {missing[:10]}{'...' if len(missing)>10 else ''}")
        else:
            print(f"✅ Lista completa ({len(all_items)} álbumes)")

    cache_file.write_text(json.dumps(all_items, ensure_ascii=False, indent=2))
    print(f"✅ {len(all_items)} álbumes scrapeados → {cache_file}")
    return all_items

def fetch_descriptions_1001(cache_file: Path) -> dict:
    """Scrape 1001albumsgenerator.com for Spotify IDs + descriptions.
    Returns dict keyed by _norm(artist)+'|||'+_norm(title)."""
    desc_cache = cache_file.parent / "descriptions_1001_cache.json"
    if desc_cache.exists():
        print(f"  📦 1001gen caché: {desc_cache}")
        return json.loads(desc_cache.read_text())

    print("  🌐 Scrapeando 1001albumsgenerator.com/albums...")
    html = curl_get("https://1001albumsgenerator.com/albums")
    if not html:
        print("  ⚠ No se pudo obtener la página")
        return {}

    rows = re.findall(
        r'href="/albums/([A-Za-z0-9]{22})"[^>]*>\s*([^<]+)</a>.*?'
        r'href="/artists/[^"]*"[^>]*>\s*([^<]+)</a>',
        html, re.DOTALL
    )
    data = {}
    for spotify_id, title, artist in rows:
        key = _norm(artist.strip()) + "|||" + _norm(title.strip())
        data[key] = {"spotify_id": spotify_id, "title": title.strip(),
                     "artist": artist.strip(), "desc": ""}

    print(f"  ✅ {len(data)} álbumes con Spotify ID")

    items = list(data.items())
    for i, (key, info) in enumerate(items):
        if i % 50 == 0:
            print(f"  📄 Desc {i}/{len(items)}...")
        dhtml = curl_get(f"https://1001albumsgenerator.com/albums/{info['spotify_id']}")
        m = re.search(r'<(?:p|div)[^>]*class="[^"]*(?:description|about)[^"]*"[^>]*>(.*?)</(?:p|div)>',
                      dhtml, re.DOTALL | re.IGNORECASE)
        if m:
            info["desc"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()[:800]
        else:
            for p in re.findall(r'<p[^>]*>((?:[^<]|<(?!/?p))*)</p>', dhtml, re.DOTALL):
                clean = re.sub(r'<[^>]+>', '', p).strip()
                if len(clean) > 120:
                    info["desc"] = clean[:800]
                    break
        time.sleep(0.3)

    desc_cache.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"  💾 {desc_cache}")
    return data



def _migrate_desc_entry(entry: dict) -> dict:
    """Migrate old single 'desc' field → 'desc_lfm_album'. Non-destructive."""
    if "desc" in entry and "desc_lfm_album" not in entry:
        entry["desc_lfm_album"] = entry.pop("desc")
    for k in ("desc_lfm_album", "desc_lfm_artist", "desc_mb_album", "desc_mb_artist"):
        entry.setdefault(k, "")
    return entry


def _clean_lfm_text(text: str) -> str:
    text = re.sub(r'<a href="[^"]*last\.fm[^"]*"[^>]*>[^<]*</a>', '', text)
    return re.sub(r'<[^>]+>', '', text).strip()


def _fetch_mb_annotation(mbid: str, entity: str = "release-group") -> str:
    """Fetch MusicBrainz annotation for a release-group or artist MBID."""
    if not mbid:
        return ""
    try:
        url = f"https://musicbrainz.org/ws/2/{entity}/{mbid}?inc=annotation&fmt=json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "MustHearAlbums/1.0 (https://github.com/musthear)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        ann = data.get("annotation") or {}
        text = ann.get("text", "") if isinstance(ann, dict) else str(ann)
        return text.strip()[:800] if text and len(text.strip()) > 20 else ""
    except Exception:
        pass
    return ""


def _fetch_mb_artist_mbid(artist_name: str) -> str:
    """Search MusicBrainz for an artist MBID by name."""
    try:
        q = urllib.parse.quote(f'artist:"{artist_name}"')
        url = f"https://musicbrainz.org/ws/2/artist?query={q}&limit=1&fmt=json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "MustHearAlbums/1.0 (https://github.com/musthear)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        artists = data.get("artists", [])
        return artists[0].get("id", "") if artists else ""
    except Exception:
        pass
    return ""


def fetch_album_info_lastfm(albums: list, cache_file: Path,
                             api_key: str, api_secret: str,
                             fetch_mb: bool = True) -> dict:
    """Fetch album/artist info from Last.fm and MusicBrainz annotations.
    Cache fields: desc_lfm_album, desc_lfm_artist, desc_mb_album, desc_mb_artist.
    Migrates legacy 'desc' → 'desc_lfm_album' automatically."""
    lfm_cache = cache_file.parent / "descriptions_lastfm_cache.json"
    if lfm_cache.exists():
        raw = json.loads(lfm_cache.read_text())
        cached = {k: _migrate_desc_entry(v) for k, v in raw.items()}
        missing = [a for a in albums
                   if (_norm(a["artist"]) + "|||" + _norm(a["title"])) not in cached]
        # Also re-enrich entries missing MB fields if fetch_mb enabled
        if fetch_mb:
            missing += [a for a in albums
                        if (_norm(a["artist"]) + "|||" + _norm(a["title"])) in cached
                        and not cached[_norm(a["artist"]) + "|||" + _norm(a["title"])].get("desc_mb_album")
                        and not cached[_norm(a["artist"]) + "|||" + _norm(a["title"])].get("desc_mb_artist")]
            missing = list({id(a): a for a in missing}.values())  # deduplicate
        if not missing:
            print(f"  📦 Last.fm caché completo: {lfm_cache}")
            return cached
        print(f"  📦 Last.fm caché parcial/incompleto: {len(cached)} entradas, {len(missing)} a enriquecer")
    else:
        cached = {}
        missing = albums

    pylast = _try_import("pylast")
    if not pylast:
        print("  ⚠ pylast no disponible. Instala con: pip install pylast --break-system-packages")
        return cached

    network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
    print(f"  🎙 Obteniendo info Last.fm + MusicBrainz de {len(missing)} álbumes...")

    for i, album in enumerate(missing):
        if i % 25 == 0:
            print(f"    {i}/{len(missing)}...")
        key = _norm(album["artist"]) + "|||" + _norm(album["title"])
        entry = _migrate_desc_entry(cached.get(key, {
            "spotify_id": "", "title": album["title"], "artist": album["artist"],
        }))

        # ── Last.fm album wiki ──
        if not entry["desc_lfm_album"]:
            try:
                lfm_album = network.get_album(album["artist"], album["title"])
                wiki = _clean_lfm_text(lfm_album.get_wiki_summary() or "")
                entry["desc_lfm_album"] = wiki[:800] if len(wiki) > 40 else ""
            except Exception:
                pass
            time.sleep(0.25)

        # ── Last.fm artist bio ──
        if not entry["desc_lfm_artist"]:
            try:
                lfm_artist = network.get_artist(album["artist"])
                bio = _clean_lfm_text(lfm_artist.get_bio_summary() or "")
                entry["desc_lfm_artist"] = bio[:800] if len(bio) > 40 else ""
            except Exception:
                pass
            time.sleep(0.25)

        # ── MusicBrainz annotations ──
        if fetch_mb:
            album_mbid = album.get("mbid", "")

            if album_mbid and not entry["desc_mb_album"]:
                entry["desc_mb_album"] = _fetch_mb_annotation(album_mbid, "release-group")
                time.sleep(1.1)

            if not entry["desc_mb_artist"]:
                artist_mbid = _fetch_mb_artist_mbid(album["artist"])
                if artist_mbid:
                    entry["desc_mb_artist"] = _fetch_mb_annotation(artist_mbid, "artist")
                time.sleep(1.1)

        cached[key] = entry

    lfm_cache.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    print(f"  💾 {lfm_cache}")
    return cached

def fetch_album_info(albums: list, cache_file: Path, args) -> dict:
    """Dispatcher: choose info source based on CLI args.
    Priority: --1001-albums > --lastfm-*
    Multiple sources are merged (1001gen wins for desc_lfm_album if available)."""
    desc_db = {}

    lfm_key, lfm_secret = _resolve_lastfm_credentials(args)
    use_1001 = getattr(args, "gen_1001", False)
    fetch_mb = True  # always fetch MB annotations if available

    if not any([use_1001, lfm_key]):
        print("ℹ️  Sin fuente de descripciones (usa --1001-albums o --lastfm-api-key/secret)")
        return {}

    # Layer sources from lowest to highest priority
    if lfm_key and lfm_secret:
        print("\n📡 Fuente: Last.fm + MusicBrainz")
        lfm_data = fetch_album_info_lastfm(albums, cache_file, lfm_key, lfm_secret, fetch_mb=fetch_mb)
        desc_db.update(lfm_data)

    if use_1001:
        print("\n📡 Fuente: 1001albumsgenerator.com")
        data_1001 = fetch_descriptions_1001(cache_file)
        # 1001gen wins: overwrite desc_lfm_album + spotify_id
        for k, v in data_1001.items():
            entry = _migrate_desc_entry(desc_db.get(k, {}))
            entry["spotify_id"] = v.get("spotify_id", entry.get("spotify_id", ""))
            # 1001gen legacy field "desc" maps to desc_lfm_album
            gen_desc = v.get("desc", "") or v.get("desc_lfm_album", "")
            if gen_desc:
                entry["desc_lfm_album"] = gen_desc
            desc_db[k] = entry

    total_with_any = sum(
        1 for v in desc_db.values()
        if any(v.get(f) for f in ("desc_lfm_album","desc_lfm_artist","desc_mb_album","desc_mb_artist"))
    )
    print(f"\n  📖 {total_with_any}/{len(desc_db)} álbumes con alguna descripción")
    return desc_db


# ── DATABASE ──────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())


# ── Schema detection helpers ───────────────────────────────────────────────────

def _user_table_name(username: str) -> str:
    """Nombre de la tabla scrobbles per-user (schema normalizado nuevo)."""
    safe = re.sub(r'[^a-z0-9]', '_', username.lower()).strip('_')
    return f"scrobbles_{safe}"


def _scrobbles_schema(conn: sqlite3.Connection) -> str:
    """Detecta el esquema del DB de scrobbles.
    'new': tablas scrobbles_<user> + artists/albums (lastfm_cache_rym_new_normalized.db)
    'old': tabla scrobbles con columnas user/artist/album TEXT (rym_lastfm.db)
    """
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    return "new" if "scrobbles" not in tables and "artists" in tables else "old"


def _scrobbles_get_users(conn: sqlite3.Connection) -> list[str]:
    """Lee lista de usuarios, compatible con schema old y new."""
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "users" in tables:
        return [r[0] for r in conn.execute(
            "SELECT username FROM users ORDER BY username"
        ).fetchall()]
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT user FROM scrobbles ORDER BY user"
    ).fetchall()]


def get_users(db_path: str) -> list[str]:
    """
    Lee usuarios desde must_hear.db (tabla users) o desde rym_lastfm.db (tabla scrobbles).
    Detecta automáticamente el esquema disponible.
    """
    with sqlite3.connect(db_path) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "users" in tables:
            rows = c.execute("SELECT username FROM users ORDER BY username").fetchall()
        else:
            rows = c.execute("SELECT DISTINCT user FROM scrobbles ORDER BY user").fetchall()
    return [r[0] for r in rows]


def get_user_albums_from_scrobbles(scrobbles_db: str, user: str) -> set[tuple]:
    """Lee scrobbles de la DB. Devuelve set de (norm_artist, norm_album).
    Compatible con schema old (rym_lastfm.db) y new (lastfm_cache_rym_new_normalized.db)."""
    with sqlite3.connect(scrobbles_db) as c:
        if _scrobbles_schema(c) == "new":
            tbl = _user_table_name(user)
            exists = c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone()
            if not exists:
                return set()
            rows = c.execute(f"""
                SELECT ar.name, al.name
                FROM {tbl} sc
                JOIN artists ar ON ar.id = sc.artist_id
                JOIN albums  al ON al.id = sc.album_id
                WHERE sc.album_id IS NOT NULL
            """).fetchall()
        else:
            rows = c.execute(
                "SELECT artist, album FROM scrobbles WHERE user=? AND album IS NOT NULL AND album != ''",
                (user,)
            ).fetchall()
    return {(_norm(r[0]), _norm(r[1])) for r in rows}


def get_user_albums_from_must_hear(mh_conn: sqlite3.Connection,
                                    user: str) -> set[tuple]:
    """
    Lee user_heard de must_hear.db.
    Devuelve set de (norm_artist, norm_album) para los álbumes marcados como escuchados.
    """
    rows = mh_conn.execute("""
        SELECT ar.name, al.name
        FROM user_heard uh
        JOIN users u  ON u.id  = uh.user_id
        JOIN albums al ON al.id = uh.album_id
        JOIN artists ar ON ar.id = al.artist_id
        WHERE u.username = ?
    """, (user,)).fetchall()
    return {(_norm(r[0]), _norm(r[1])) for r in rows}


def populate_user_heard(mh_conn: sqlite3.Connection,
                         user: str,
                         collection_slug: str,
                         scrobbles_db: str):
    """
    Cruza los scrobbles del usuario contra los álbumes de la colección
    y puebla user_heard en must_hear.db.
    Solo inserta filas nuevas (INSERT OR IGNORE).
    """
    user_row = mh_conn.execute(
        "SELECT id FROM users WHERE username=?", (user,)
    ).fetchone()
    if not user_row:
        return 0
    user_id = user_row[0]

    # Álbumes de la colección
    coll_albums = mh_conn.execute("""
        SELECT al.id, ar.name, al.name
        FROM collection_albums ca
        JOIN collections c  ON c.id  = ca.collection_id
        JOIN albums al      ON al.id = ca.album_id
        JOIN artists ar     ON ar.id = al.artist_id
        WHERE c.slug = ?
    """, (collection_slug,)).fetchall()

    if not coll_albums:
        return 0

    # Scrobbles del usuario
    user_nk_set = get_user_albums_from_scrobbles(scrobbles_db, user)

    inserted = 0
    for album_id, artist_name, album_name in coll_albums:
        # check_heard logic inline (substring match)
        a_n = _norm(artist_name)
        t_n = _norm(album_name)
        heard = False
        for ua, ut in user_nk_set:
            if not ut:
                continue
            title_match = (t_n == ut or t_n in ut or
                           (ut in t_n and len(ut) >= len(t_n) * 0.8))
            if not title_match:
                continue
            if not a_n or a_n in ua or ua in a_n:
                heard = True
                break
        if heard:
            mh_conn.execute(
                "INSERT OR IGNORE INTO user_heard (user_id, album_id) VALUES (?,?)",
                (user_id, album_id)
            )
            inserted += 1
    mh_conn.commit()
    return inserted


def get_user_albums(db_path: str, user: str) -> set[tuple]:
    """Backwards-compat wrapper: lee de rym_lastfm.db (scrobbles)."""
    return get_user_albums_from_scrobbles(db_path, user)

def check_heard(user_albums: set, album: dict) -> bool:
    """Match by normalized (title, artist).
    Title: canonical title must be contained in the scrobble title OR vice-versa
           (handles remasters, editions, bonus discs, e.g.
            'boston' matches 'boston2000remaster', 'bostondeluxeedition', etc.)
    Artist: fuzzy substring match in either direction.
    """
    a_n = _norm(album["artist"])
    t_n = _norm(album["title"])
    if not t_n:
        return False
    for ua, ut in user_albums:
        if not ut:
            continue
        # Title match: exact, canonical-in-scrobble, or scrobble-in-canonical (min 80% length)
        title_match = (
            t_n == ut or
            t_n in ut or
            (ut in t_n and len(ut) >= len(t_n) * 0.8)
        )
        if not title_match:
            continue
        # Artist match: substring in either direction
        if not a_n or a_n in ua or ua in a_n:
            return True
    return False

# ── YOUTUBE PRE-FETCH ────────────────────────────────────────────────────────

def _yt_search(query: str) -> str:
    """Return first YouTube video ID for query using yt-dlp (no API key needed)."""
    try:
        r = subprocess.run(
            ["yt-dlp", "--no-playlist", "--get-id", "--quiet",
             f"ytsearch1:{query}"],
            capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        return ""
    vid = r.stdout.strip()
    return vid if len(vid) == 11 else ""


def fetch_youtube_ids(albums: list, cache_file: Path, force: bool = False) -> dict:
    """Pre-fetch YouTube video IDs for all albums.
    Returns dict keyed by mbid → video_id (str, may be "").
    Uses YouTube search page HTML scrape — no API key needed."""
    yt_cache = cache_file.parent / "youtube_cache.json"
    if yt_cache.exists() and not force:
        cached = json.loads(yt_cache.read_text())
        # Re-try entries that are missing OR were cached as empty (possible bot-wall hit)
        missing = [a for a in albums if a["mbid"] not in cached or cached[a["mbid"]] == ""]
        if not missing:
            print(f"  📦 YouTube caché completo: {yt_cache}")
            return cached
        print(f"  📦 YouTube caché: {len(cached)-sum(1 for v in cached.values() if not v)} con vídeo, "
              f"{sum(1 for v in cached.values() if not v)} vacíos, {len(missing)} a buscar")
    else:
        cached = {}
        missing = albums

    print(f"  🎬 Buscando {len(missing)} vídeos en YouTube (yt-dlp)...")
    for i, album in enumerate(missing):
        if i % 25 == 0:
            print(f"    {i}/{len(missing)}...")
        q   = f"{album['artist']} {album['title']} full album"
        vid = _yt_search(q)
        cached[album["mbid"]] = vid
        if i % 25 != 0 and not vid:
            pass  # silent miss
        time.sleep(0.5)

    yt_cache.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    found = sum(1 for v in cached.values() if v)
    print(f"  💾 {yt_cache} ({found}/{len(cached)} encontrados)")
    return cached



# ── RATEYOURMUSIC FETCH ──────────────────────────────────────────────────────

RYM_URL_RE = re.compile(r'https://rateyourmusic\.com/release/[a-z]+/[^/]+/[^/]+/?')

def fetch_rym_urls(albums: list, cache_file: Path,
                   searxng: str = "http://localhost:8485",
                   key_field: str = "mbid") -> dict:
    """Search RateYourMusic URLs via local SearXNG instance.
    key_field: 'mbid' for 1001/RS collections, 'normkey' for Scaruffi.
    Returns dict keyed by key_field value → rym URL string ('' if not found)."""
    rym_cache_path = cache_file.parent / "rym_cache.json"
    if rym_cache_path.exists():
        cached = json.loads(rym_cache_path.read_text())
        missing = []
        for a in albums:
            k = a[key_field] if key_field == "mbid" else (_norm(a["artist"]) + "|||" + _norm(a["title"]))
            if k and k not in cached:
                missing.append(a)
        if not missing:
            found = sum(1 for v in cached.values() if v)
            print(f"  📦 RYM caché completo: {found}/{len(cached)} con URL")
            return cached
        print(f"  📦 RYM caché parcial: {len(cached)} OK, {len(missing)} pendientes")
    else:
        cached = {}
        missing = albums

    print(f"  🔍 Buscando {len(missing)} álbumes en RateYourMusic via SearXNG ({searxng})...")
    errors = 0
    for i, album in enumerate(missing):
        if i % 25 == 0:
            print(f"    {i}/{len(missing)}...")
        k = album[key_field] if key_field == "mbid" else (_norm(album["artist"]) + "|||" + _norm(album["title"]))
        if not k:
            continue

        q   = urllib.parse.quote_plus(f"{album['artist']} - {album['title']} site:rateyourmusic.com")
        url = f"{searxng}/search?q={q}&format=json&categories=general"
        try:
            req  = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            results = data.get("results", [])
            rym_url = ""
            for result in results:
                href = result.get("url", "")
                if RYM_URL_RE.match(href):
                    rym_url = href.rstrip("/")
                    break
            cached[k] = rym_url
        except Exception as e:
            errors += 1
            cached[k] = ""
            if errors <= 3:
                print(f"    ⚠ Error SearXNG ({album['artist']} — {album['title']}): {e}")

        time.sleep(0.4)

    rym_cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    found = sum(1 for v in cached.values() if v)
    print(f"  💾 {rym_cache_path} ({found}/{len(cached)} encontrados, {errors} errores)")
    if errors > 3:
        print(f"  ⚠ {errors} errores totales — ¿está SearXNG corriendo en {searxng}?")
    return cached


# ── MUSICBRAINZ GENRE FETCH ──────────────────────────────────────────────────

# Genres too generic / meta to be useful for filtering
GENRE_BLACKLIST = {
    "seen live", "electronic", "pop", "rock", "music", "indie",
    "alternative", "experimental", "ambient", "noise", "progressive",
    "contemporary", "modern", "classic", "traditional", "americana",
    "lo-fi", "lo fi", "chillout", "chill", "downtempo", "adult contemporary",
    "easy listening", "background music", "world", "world music",
    "singer-songwriter", "singer songwriter", "acoustic", "instrumental",
    "australian", "british", "american", "canadian", "french", "german",
    "spanish", "japanese", "swedish", "norwegian", "irish",
}

def fetch_genres_musicbrainz(albums: list, cache_file: Path) -> dict:
    """Fetch genres for each release-group from MusicBrainz API.
    Returns dict keyed by mbid → list[str] of genres (filtered by blacklist)."""
    genre_cache_path = cache_file.parent / "genres_mb_cache.json"
    if genre_cache_path.exists():
        cached = json.loads(genre_cache_path.read_text())
        missing = [a for a in albums if a["mbid"] not in cached]
        if not missing:
            print(f"  📦 Géneros MB caché completo: {genre_cache_path}")
            return cached
        print(f"  📦 Géneros MB caché parcial: {len(cached)} OK, {len(missing)} pendientes")
    else:
        cached = {}
        missing = albums

    print(f"  🎸 Obteniendo géneros de MusicBrainz para {len(missing)} álbumes...")
    for i, album in enumerate(missing):
        if i % 50 == 0:
            print(f"    {i}/{len(missing)}...")
        url = f"https://musicbrainz.org/ws/2/release-group/{album['mbid']}?inc=genres&fmt=json"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "MustHearAlbums/1.0 (https://github.com/musthear)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            genres = [
                g["name"].lower() for g in data.get("genres", [])
                if g.get("count", 1) >= 1
                and g["name"].lower() not in GENRE_BLACKLIST
                and len(g["name"]) > 2
            ]
            # Sort by vote count descending, keep top 6
            genres_with_count = [
                (g["name"].lower(), g.get("count", 1))
                for g in data.get("genres", [])
                if g["name"].lower() not in GENRE_BLACKLIST and len(g["name"]) > 2
            ]
            genres_with_count.sort(key=lambda x: x[1], reverse=True)
            cached[album["mbid"]] = [g for g, _ in genres_with_count[:6]]
        except Exception as e:
            cached[album["mbid"]] = []
        time.sleep(1.1)  # MB rate limit: 1 req/sec

    genre_cache_path.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
    total_with = sum(1 for v in cached.values() if v)
    print(f"  💾 {genre_cache_path} ({total_with}/{len(cached)} álbumes con géneros)")
    return cached

# ── HTML GENERATION ───────────────────────────────────────────────────────────

COVER_PLACEHOLDER = "data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20width=%22250%22%20height=%22250%22%20viewBox=%220%200%20250%20250%22%3E%3Crect%20width=%22250%22%20height=%22250%22%20fill=%22%23111%22/%3E%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%2260%22%20fill=%22none%22%20stroke=%22%23333%22%20stroke-width=%222%22/%3E%3Ccircle%20cx=%22125%22%20cy=%22125%22%20r=%228%22%20fill=%22%23333%22/%3E%3C/svg%3E"

def album_to_json(album: dict, heard: bool, desc_db: dict = None,
                   yt_cache: dict = None, genre_cache: dict = None,
                   rym_cache: dict = None) -> dict:
    key  = _norm(album.get("artist","")) + "|||" + _norm(album.get("title",""))
    raw  = (desc_db or {}).get(key, {})
    info = _migrate_desc_entry(dict(raw))  # ensure new fields present
    return {
        "n":              album["number"],
        "title":          album["title"],
        "artist":         album["artist"],
        "year":           album["year"],
        "mbid":           album["mbid"],
        "heard":          heard,
        "cover":          f"{CAA}/{album['mbid']}/front-250",
        "spotify_id":     info.get("spotify_id", ""),
        "spotify_url":    info.get("spotify_url", ""),
        "desc_lfm_album": info.get("desc_lfm_album", ""),
        "desc_lfm_artist":info.get("desc_lfm_artist", ""),
        "desc_mb_album":  info.get("desc_mb_album", ""),
        "desc_mb_artist": info.get("desc_mb_artist", ""),
        "yt_id":          (yt_cache or {}).get(album["mbid"], ""),
        "genres":         (genre_cache or {}).get(album["mbid"], []),
        "rym":            (rym_cache or {}).get(album["mbid"], ""),
    }

def render_user_html(user: str, albums_data: list[dict], series_name: str,
                     data_file: str = "data/albums.json") -> str:
    heard_count   = sum(1 for a in albums_data if a["heard"])
    pending_count = len(albums_data) - heard_count
    pct           = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{user} — {series_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<!-- Umami Analytics -->
<script
    defer
    src="https://cloud.umami.is/script.js"
    data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"
></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:       #0a0a0a;
    --surface:  #111111;
    --border:   #1e1e1e;
    --accent:   #e8ff47;
    --heard:    #e8ff47;
    --pending:  #ff4747;
    --text:     #e0e0e0;
    --muted:    #555;
    --gap:      6px;
    --panel:    390px;
    --header-h: 58px;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
  }}

  /* ── LAYOUT: header top strip, grid left, panel fixed right ── */
  header {{
    position: fixed; top: 0; left: 0; right: var(--panel);
    height: var(--header-h);
    z-index: 100;
    background: rgba(10,10,10,.97);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    border-right: 1px solid var(--border);
    padding: 0 20px;
    display: flex; align-items: center; gap: 16px;
    overflow: hidden;
  }}
  .header-title {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.6rem; letter-spacing: .08em;
    color: var(--accent); text-decoration: none; white-space: nowrap;
  }}
  .header-sub {{
    font-family: 'DM Mono', monospace; font-size: .65rem;
    color: var(--muted); line-height: 1.5; flex-shrink: 0;
  }}
  .header-sub strong {{ color: var(--text); }}

  /* ── PROGRESS BAR ── */
  .progress-wrap {{ width: 110px; flex-shrink: 0; }}
  .progress-bar {{
    height: 3px; background: var(--border); border-radius: 2px; overflow: hidden;
  }}
  .progress-fill {{
    height: 100%; background: var(--accent); border-radius: 2px;
    width: {pct}%;
  }}
  .progress-label {{
    font-family: 'DM Mono', monospace; font-size: .6rem; color: var(--muted); margin-top: 3px;
  }}
  .progress-label span {{ color: var(--accent); }}

  /* ── CONTROLS ── */
  .controls {{ display: flex; align-items: center; gap: 8px; margin-left: auto; flex-shrink: 0; }}
  .filter-btn {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 5px 11px; border-radius: 3px;
    border: 1px solid var(--border); background: transparent;
    color: var(--muted); cursor: pointer; transition: all .15s;
  }}
  .filter-btn:hover {{ border-color: var(--muted); color: var(--text); }}
  .filter-btn.active {{ border-color: var(--accent); color: var(--accent); background: rgba(232,255,71,.06); }}
  .search-box {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    padding: 5px 10px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 3px;
    color: var(--text); width: 160px; outline: none; transition: border-color .15s;
  }}
  .search-box:focus {{ border-color: var(--accent); }}
  .search-box::placeholder {{ color: var(--muted); }}

  /* ── GENRE DROPDOWN ── */
  .genre-wrap {{ position: relative; }}
  .genre-btn {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 5px 11px; border-radius: 3px;
    border: 1px solid var(--border); background: transparent;
    color: var(--muted); cursor: pointer; transition: all .15s;
    display: flex; align-items: center; gap: 5px; white-space: nowrap;
  }}
  .genre-btn:hover {{ border-color: var(--muted); color: var(--text); }}
  .genre-btn.active {{ border-color: var(--accent); color: var(--accent); background: rgba(232,255,71,.06); }}
  .genre-btn .badge {{
    background: var(--accent); color: #000; border-radius: 10px;
    padding: 1px 6px; font-size: .58rem; font-weight: 700;
  }}
  .genre-dropdown {{
    display: none; position: fixed;
    background: #161616; border: 1px solid var(--border); border-radius: 4px;
    z-index: 9999; min-width: 220px; max-height: 360px;
    overflow-y: auto; padding: 6px 0;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
    box-shadow: 0 8px 32px rgba(0,0,0,.6);
  }}
  .genre-dropdown.open {{ display: block; }}
  .genre-dropdown-header {{
    padding: 6px 12px 4px;
    font-family: 'DM Mono', monospace; font-size: .6rem;
    letter-spacing: .15em; text-transform: uppercase; color: var(--muted);
    border-bottom: 1px solid var(--border); margin-bottom: 4px;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .genre-clear {{ color: var(--pending); cursor: pointer; font-size: .58rem; }}
  .genre-clear:hover {{ color: #ff7070; }}
  .genre-item {{
    display: flex; align-items: center; gap: 8px;
    padding: 5px 12px; cursor: pointer; transition: background .1s;
  }}
  .genre-item:hover {{ background: var(--surface); }}
  .genre-item input {{ accent-color: var(--accent); cursor: pointer; flex-shrink: 0; }}
  .genre-item label {{
    font-family: 'DM Mono', monospace; font-size: .7rem; color: var(--text);
    cursor: pointer; flex: 1;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .genre-item label .genre-count {{
    color: var(--muted); font-size: .6rem;
  }}

  /* ── GRID SLIDER ── */
  .grid-sizer {{ display: flex; align-items: center; gap: 6px; }}
  .grid-sizer span {{
    font-family: 'DM Mono', monospace; font-size: .6rem;
    color: var(--muted); min-width: 26px; text-align: right;
  }}
  #grid-slider {{
    -webkit-appearance: none; appearance: none;
    width: 80px; height: 3px; background: var(--border); border-radius: 2px; outline: none; cursor: pointer;
  }}
  #grid-slider::-webkit-slider-thumb {{
    -webkit-appearance: none; width: 11px; height: 11px; border-radius: 50%;
    background: var(--accent); cursor: pointer;
  }}
  #grid-slider::-moz-range-thumb {{
    width: 11px; height: 11px; border-radius: 50%;
    background: var(--accent); border: none; cursor: pointer;
  }}

  /* ── GRID AREA ── */
  #main {{
    margin-top: var(--header-h);
    margin-right: var(--panel);
    padding: 16px 20px 60px;
    position: relative;
    z-index: 0;
  }}
  .count-bar {{
    font-family: 'DM Mono', monospace; font-size: .68rem;
    color: var(--muted); margin-bottom: 12px; display: flex; gap: 16px; flex-wrap: wrap;
  }}
  .count-bar b {{ color: var(--text); }}
  #grid {{
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: var(--gap);
  }}

  /* ── CARD ── */
  .card {{
    position: relative; aspect-ratio: 1; border-radius: 3px;
    overflow: hidden; cursor: pointer;
    transition: transform .15s;
  }}
  .card:hover {{ transform: scale(1.05); z-index: 10; }}
  .card.hidden {{ display: none; }}
  .card.active-card {{ outline: 2px solid var(--accent); outline-offset: 2px; z-index: 11; }}
  .card img {{
    width: 100%; height: 100%; object-fit: cover; display: block; background: var(--surface);
  }}
  .card::before {{
    content: ''; position: absolute; top: 5px; right: 5px;
    width: 7px; height: 7px; border-radius: 50%; z-index: 3;
  }}
  .card.heard::before  {{ background: var(--heard); box-shadow: 0 0 5px var(--heard); }}
  .card.pending::before {{ background: var(--pending); box-shadow: 0 0 5px var(--pending); }}
  .card-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(0deg, rgba(0,0,0,.9) 0%, rgba(0,0,0,0) 55%);
    opacity: 0; transition: opacity .18s;
    display: flex; flex-direction: column; justify-content: flex-end;
    padding: 7px; z-index: 2;
  }}
  .card:hover .card-overlay {{ opacity: 1; }}
  .card-num   {{ font-family: 'Bebas Neue', sans-serif; font-size: .85rem; color: var(--accent); line-height: 1; }}
  .card-title {{ font-size: .6rem; font-weight: 500; color: #fff; line-height: 1.3;
                 overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
  .card-artist {{ font-size: .55rem; color: var(--muted); margin-top: 2px;
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

  /* ── PANEL (sidebar on desktop, hidden overlay on mobile) ── */
  #panel {{
    position: fixed; top: 0; right: 0; bottom: 0; width: var(--panel);
    background: #0c0c0c;
    border-left: 1px solid var(--border);
    z-index: 200;
    display: flex; flex-direction: column;
    overflow: hidden;
  }}
  /* Panel top strip (mirrors header height) */
  .panel-topbar {{
    height: var(--header-h);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center;
    padding: 0 16px;
    flex-shrink: 0;
  }}
  .panel-topbar-label {{
    font-family: 'DM Mono', monospace; font-size: .6rem;
    letter-spacing: .18em; text-transform: uppercase; color: var(--muted);
  }}

  .panel-cover {{
    width: 100%; aspect-ratio: 1; flex-shrink: 0;
    position: relative; background: var(--surface);
    max-height: 190px; overflow: hidden;
  }}
  .panel-cover img {{
    width: 100%; height: 100%; object-fit: cover; display: block;
  }}
  .panel-cover-status {{
    position: absolute; bottom: 8px; left: 8px;
    font-family: 'DM Mono', monospace; font-size: .6rem;
    letter-spacing: .12em; text-transform: uppercase;
    padding: 2px 7px; border-radius: 2px;
  }}
  .panel-cover-status.heard   {{ background: var(--heard); color: #000; }}
  .panel-cover-status.pending {{ background: var(--pending); color: #fff; }}

  .panel-body {{
    flex: 1; overflow-y: auto; padding: 16px;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .panel-body::-webkit-scrollbar {{ width: 3px; }}
  .panel-body::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}

  .panel-empty {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 100%; gap: 8px;
    font-family: 'DM Mono', monospace; font-size: .75rem; color: var(--muted); text-align: center;
  }}
  .panel-empty-icon {{ font-size: 2rem; opacity: .3; }}

  .panel-num    {{ font-family: 'DM Mono', monospace; font-size: .62rem; color: var(--accent); letter-spacing: .15em; margin-bottom: 4px; }}
  .panel-title  {{ font-family: 'Bebas Neue', sans-serif; font-size: 1.5rem; letter-spacing: .04em; color: var(--text); line-height: 1.05; margin-bottom: 3px; }}
  .panel-artist {{ font-size: .82rem; color: var(--muted); margin-bottom: 2px; }}
  .panel-year   {{ font-family: 'DM Mono', monospace; font-size: .68rem; color: var(--muted); margin-bottom: 12px; }}
  .panel-genres {{
    display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 14px;
  }}
  .panel-genre-tag {{
    font-family: 'DM Mono', monospace; font-size: .6rem;
    padding: 2px 8px; border-radius: 2px;
    background: rgba(232,255,71,.08); border: 1px solid rgba(232,255,71,.2);
    color: rgba(232,255,71,.7); letter-spacing: .05em;
  }}
  .panel-divider {{ height: 1px; background: var(--border); margin: 12px 0; }}
  .panel-section-label {{
    font-family: 'DM Mono', monospace; font-size: .58rem;
    letter-spacing: .18em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px;
  }}
  .panel-bio {{
    font-size: .76rem; color: #aaa; line-height: 1.65;
    max-height: 140px; overflow-y: auto;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .panel-bio::-webkit-scrollbar {{ width: 3px; }}
  .panel-bio::-webkit-scrollbar-thumb {{ background: var(--border); }}
  .panel-bio-loading {{ font-family: 'DM Mono', monospace; font-size: .7rem; color: var(--muted); font-style: italic; }}
  .desc-block {{ margin-bottom: 10px; }}
  .desc-source-label {{
    font-family: 'DM Mono', monospace; font-size: .52rem;
    letter-spacing: .14em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 3px;
    display: flex; align-items: center; gap: 5px;
  }}
  .desc-source-label::before {{
    content: ''; display: inline-block; width: 6px; height: 6px;
    border-radius: 50%; background: currentColor; flex-shrink: 0;
  }}
  .desc-source-label.lfm {{ color: #d51007; }}
  .desc-source-label.mb  {{ color: #ba478f; }}
  .desc-source-label.artist {{ color: #6a9fb5; }}
  .desc-source-text {{ font-size: .75rem; color: #aaa; line-height: 1.6; }}

  .panel-links {{ display: flex; gap: 7px; flex-wrap: wrap; margin-top: 12px; }}
  .panel-link {{
    font-family: 'DM Mono', monospace; font-size: .62rem;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 4px 10px; border-radius: 3px;
    border: 1px solid var(--border); color: var(--muted);
    text-decoration: none; transition: all .15s;
  }}
  .panel-link.rym{{border-color:#5baadb;color:#5baadb}}
  .panel-link.rym:hover{{background:rgba(48,81,159,.08)}}

  .panel-yt-wrap {{
    margin-top: 14px; border-radius: 4px; overflow: hidden;
    background: var(--surface); border: 1px solid var(--border);
  }}
  .panel-yt-wrap iframe {{ display: block; width: 100%; height: 150px; border: none; }}
  .panel-yt-placeholder {{
    height: 70px; display: flex; align-items: center; justify-content: center;
    font-family: 'DM Mono', monospace; font-size: .68rem; color: var(--muted);
  }}

  /* ── MISC ── */
  .back-link {{ font-family: 'DM Mono', monospace; font-size: .68rem; color: var(--muted); text-decoration: none; }}
  .back-link:hover {{ color: var(--text); }}
  #empty {{ display: none; text-align: center; padding: 60px 0; font-family: 'DM Mono', monospace; color: var(--muted); font-size: .75rem; }}

  /* ── CLOSE BUTTON (visible only on mobile) ── */
  .panel-close-btn {{
    display: none;
    position: absolute; top: 13px; right: 13px;
    width: 34px; height: 34px; border-radius: 50%;
    background: rgba(255,255,255,.07); border: 1px solid var(--border);
    color: var(--text); font-size: 1rem; line-height: 1; cursor: pointer;
    align-items: center; justify-content: center; z-index: 10;
    transition: background .15s; flex-shrink: 0;
  }}
  .panel-close-btn:hover {{ background: rgba(255,255,255,.18); }}

  @media (max-width: 600px) {{
    /* ── Header: full width, wraps to two rows ── */
    header {{
      right: 0;
      height: auto; min-height: var(--header-h);
      flex-wrap: wrap; align-items: center;
      padding: 8px 12px; gap: 6px 10px;
      overflow: visible;
    }}
    .header-title {{ font-size: 1.3rem; }}
    .header-sub   {{ font-size: .6rem; }}

    /* Controls: own row, scroll horizontally so nothing wraps */
    .controls {{
      flex: 0 0 100%; margin-left: 0;
      overflow-x: auto; flex-wrap: nowrap;
      gap: 6px; padding: 6px 0 2px;
      border-top: 1px solid var(--border);
      scrollbar-width: none;
    }}
    .controls::-webkit-scrollbar {{ display: none; }}
    .search-box  {{ width: 120px; flex-shrink: 0; }}
    .genre-wrap, .grid-sizer, .filter-btn {{ flex-shrink: 0; }}

    /* Grid area */
    #main {{ padding: 12px 10px 60px; margin-right: 0; }}

    /* Panel: full-screen overlay, hidden by default */
    #panel {{
      inset: 0; width: 100%; border-left: none;
      transform: translateY(105%);
      transition: transform .28s cubic-bezier(.4,0,.2,1);
    }}
    #panel.panel-open {{ transform: translateY(0); }}
    .panel-close-btn {{ display: flex; }}
    .panel-cover {{ max-height: 50vw; }}
    .panel-yt-wrap iframe {{ height: 200px; }}
  }}
</style>
</head>
<body>

<header>
  <a href="index.html" class="back-link">←</a>
  <a href="#" class="header-title">{user}</a>
  <div class="header-sub">
    <strong>{series_name}</strong><br>
    {heard_count} heard &middot; {pending_count} pending
  </div>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill"></div></div>
    <div class="progress-label"><span id="prog-pct">{pct}%</span></div>
  </div>
  <div class="controls">
    <button class="filter-btn active" id="btn-all"     onclick="setFilter('all')">All</button>
    <button class="filter-btn"        id="btn-heard"   onclick="setFilter('heard')">Heard</button>
    <button class="filter-btn"        id="btn-pending" onclick="setFilter('pending')">Pending</button>
    <input class="search-box" id="search" placeholder="Search…" oninput="applyFilters()">

    <!-- Genre multi-select -->
    <div class="genre-wrap">
      <button class="genre-btn" id="genre-btn" onclick="toggleGenreDropdown()">
        Genre <span class="badge" id="genre-badge" style="display:none">0</span> ▾
      </button>
    </div>

    <div class="grid-sizer">
      <span id="grid-label">10×</span>
      <input type="range" id="grid-slider" min="3" max="20" value="5" step="1" oninput="setGridSize(this.value)">
    </div>
  </div>
</header>
<!-- Genre dropdown at body level so backdrop-filter on header doesn't trap it -->
<div class="genre-dropdown" id="genre-dropdown">
  <div class="genre-dropdown-header">
    Filter by genre
    <span class="genre-clear" onclick="clearGenres()">clear</span>
  </div>
  <div id="genre-list"></div>
</div>

<main id="main">
  <div class="count-bar">
    <span>Showing <b id="vis-count">{len(albums_data)}</b> of {len(albums_data)}</span>
    <span><b id="vis-heard">0</b> heard · <b id="vis-pending">0</b> pending</span>
  </div>
  <div id="grid"></div>
  <div id="empty">No albums match your filters.</div>
</main>

<!-- Side panel: always visible on desktop, full-screen overlay on mobile -->
<aside id="panel">
  <button class="panel-close-btn" onclick="closePanel()" aria-label="Close">✕</button>
  <div class="panel-topbar">
    <span class="panel-topbar-label">Album detail</span>
  </div>
  <div id="panel-cover-wrap" class="panel-cover" style="display:none">
    <img id="p-cover" src="" alt="">
    <span class="panel-cover-status" id="p-status"></span>
  </div>
  <div class="panel-body" id="panel-body">
    <div class="panel-empty">
      <div class="panel-empty-icon">◉</div>
      Click an album to see details
    </div>
  </div>
</aside>

<script>
let ALBUMS = [];
let filter = 'all';
let gridCols = 10;
let currentAlbum = null;
let selectedGenres = new Set();

// ── COVER HELPERS ──
function thumbUrl(url) {{
  if (!url) return url;
  return url
    .replace(/\/front-500\b/, '/front-250')
    .replace(/e\.snmc\.io\/i\/\d+\//, 'e.snmc.io/i/150/');
}}

// ── PARALLEL PRELOADER ──
const PRELOAD_CONCURRENCY = 8;
let _preloadQueue = [];
let _preloadActive = 0;

function _preloadTick() {{
  while (_preloadActive < PRELOAD_CONCURRENCY && _preloadQueue.length) {{
    _preloadActive++;
    const img = _preloadQueue.shift();
    const url = img.dataset.src;
    if (!url) {{ _preloadActive--; _preloadTick(); return; }}
    const tmp = new Image();
    tmp.onload = () => {{ img.src = url; img.removeAttribute('data-src'); _preloadActive--; _preloadTick(); }};
    tmp.onerror = () => {{ _preloadActive--; _preloadTick(); }};
    tmp.src = url;
  }}
}}

function startPreload() {{
  _preloadQueue = Array.from(document.querySelectorAll('img[data-src]'));
  _preloadActive = 0;
  _preloadTick();
}}

// ── GRID SIZE ──
function setGridSize(val) {{
  gridCols = parseInt(val);
  document.getElementById('grid-label').textContent = val + '\xd7';
  document.getElementById('grid').style.gridTemplateColumns = `repeat(${{gridCols}}, 1fr)`;
  try {{ localStorage.setItem('grid-cols', val); }} catch(e) {{}}
}}

// ── GENRE DROPDOWN ──
function buildGenreList() {{
  const counts = {{}};
  ALBUMS.forEach(a => (a.genres || []).forEach(g => counts[g] = (counts[g] || 0) + 1));
  const sorted = Object.entries(counts).sort((a,b) => b[1]-a[1]);
  const list = document.getElementById('genre-list');
  list.innerHTML = '';
  sorted.forEach(([genre, count]) => {{
    const div = document.createElement('div');
    div.className = 'genre-item';
    const id = 'g-' + genre.replace(/[^a-z0-9]/g,'_');
    div.innerHTML = `
      <input type="checkbox" id="${{id}}" value="${{genre}}" onchange="toggleGenre('${{genre}}', this.checked)">
      <label for="${{id}}">${{genre}} <span class="genre-count">${{count}}</span></label>`;
    list.appendChild(div);
  }});
}}

function toggleGenreDropdown() {{
  const dd  = document.getElementById('genre-dropdown');
  const btn = document.getElementById('genre-btn');
  const open = !dd.classList.contains('open');
  dd.classList.toggle('open', open);
  btn.classList.toggle('active', open || selectedGenres.size > 0);
  if (open) {{
    const r = btn.getBoundingClientRect();
    dd.style.top  = (r.bottom + 4) + 'px';
    dd.style.left = Math.max(4, r.right - 220) + 'px';
  }}
}}

function toggleGenre(genre, checked) {{
  if (checked) selectedGenres.add(genre); else selectedGenres.delete(genre);
  updateGenreBadge();
  applyFilters();
}}

function clearGenres() {{
  selectedGenres.clear();
  document.querySelectorAll('#genre-list input').forEach(i => i.checked = false);
  updateGenreBadge();
  applyFilters();
}}

function updateGenreBadge() {{
  const badge = document.getElementById('genre-badge');
  const btn   = document.getElementById('genre-btn');
  if (selectedGenres.size > 0) {{
    badge.textContent = selectedGenres.size;
    badge.style.display = '';
    btn.classList.add('active');
  }} else {{
    badge.style.display = 'none';
    btn.classList.remove('active');
  }}
}}

// Close dropdown when clicking outside
document.addEventListener('click', e => {{
  if (!e.target.closest('.genre-wrap')) {{
    document.getElementById('genre-dropdown').classList.remove('open');
  }}
}});

// ── GRID BUILD ──
function buildGrid() {{
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  ALBUMS.forEach(a => {{
    const card = document.createElement('div');
    card.className = `card ${{a.heard ? 'heard' : 'pending'}}`;
    card.dataset.title  = a.title.toLowerCase();
    card.dataset.artist = a.artist.toLowerCase();
    card.dataset.heard  = a.heard ? '1' : '0';
    card.dataset.num    = a.n;
    card.dataset.genres = (a.genres || []).join(',');
    card.innerHTML = `
      <img data-src="${{thumbUrl(a.cover)}}" src="{COVER_PLACEHOLDER}" alt="${{a.n}}"
           onerror="this.src='{COVER_PLACEHOLDER}'">
      <div class="card-overlay">
        <div class="card-num">#${{a.n}}</div>
        <div class="card-title">${{a.title}}</div>
        <div class="card-artist">${{a.artist}} · ${{a.year ?? ''}}</div>
      </div>`;
    card.addEventListener('click', () => openPanel(a, card));
    grid.appendChild(card);
  }});
  startPreload();
  applyFilters();
}}

// ── PANEL ──
function closePanel() {{
  document.getElementById('panel').classList.remove('panel-open');
  document.querySelectorAll('.card.active-card').forEach(c => c.classList.remove('active-card'));
  currentAlbum = null;
}}

function openPanel(a, cardEl) {{
  document.querySelectorAll('.card.active-card').forEach(c => c.classList.remove('active-card'));
  cardEl.classList.add('active-card');
  currentAlbum = a;
  if (_isMobile()) document.getElementById('panel').classList.add('panel-open');

  // Cover
  const coverWrap = document.getElementById('panel-cover-wrap');
  coverWrap.style.display = '';
  const img = document.getElementById('p-cover');
  img.src = `https://coverartarchive.org/release-group/${{a.mbid}}/front-500`;
  img.onerror = function() {{ this.src = '{COVER_PLACEHOLDER}'; }};
  const statusEl = document.getElementById('p-status');
  statusEl.textContent = a.heard ? 'Heard' : 'Pending';
  statusEl.className   = 'panel-cover-status ' + (a.heard ? 'heard' : 'pending');

  // Body
  const body = document.getElementById('panel-body');

  const genreTags = (a.genres || []).map(g =>
    `<span class="panel-genre-tag">${{g}}</span>`).join('');

  const mbUrl      = `https://musicbrainz.org/release-group/${{a.mbid}}`;
  const gen1001Url = a.spotify_id
    ? `https://1001albumsgenerator.com/albums/${{a.spotify_id}}` : '';

  const ytSearchUrl = `https://www.youtube.com/results?search_query=${{encodeURIComponent(a.artist + ' ' + a.title + ' full album')}}`;
  const ytBlock = a.yt_id
    ? `<iframe src="https://www.youtube.com/embed/${{a.yt_id}}"
         allow="autoplay; encrypted-media" allowfullscreen></iframe>
       <div style="padding:5px 10px;font-family:'DM Mono',monospace;font-size:.58rem;color:var(--muted)">
         <a href="${{ytSearchUrl}}" target="_blank" style="color:var(--muted);text-decoration:none">↗ open in YouTube</a>
       </div>`
    : `<div class="panel-yt-placeholder">
         No video cached — <a href="${{ytSearchUrl}}" target="_blank" style="color:var(--accent);text-decoration:none">Search YouTube ↗</a>
       </div>`;

  // ── Build "About" section with all available desc sources ──
  const descSources = [
    {{ key: 'desc_lfm_album',  cls: 'lfm',    label: '💿 Album · Last.fm'    }},
    {{ key: 'desc_lfm_artist', cls: 'artist',  label: '🎙 Artist · Last.fm'   }},
    {{ key: 'desc_mb_album',   cls: 'mb',      label: '💿 Album · MusicBrainz'}},
    {{ key: 'desc_mb_artist',  cls: 'mb artist',label: '🎙 Artist · MusicBrainz'}},
  ];
  const descBlocks = descSources
    .filter(s => a[s.key] && a[s.key].length > 40)
    .map(s => `<div class="desc-block">
      <div class="desc-source-label ${{s.cls}}">${{s.label}}</div>
      <div class="desc-source-text">${{a[s.key]}}</div>
    </div>`).join('');
  const aboutHtml = descBlocks || '<span style="color:var(--muted);font-size:.8rem">No info available.</span>';

  body.innerHTML = `
    <div class="panel-num">#${{a.n}}</div>
    <div class="panel-title">${{a.title}}</div>
    <div class="panel-artist">${{a.artist}}</div>
    <div class="panel-year">${{a.year ?? ''}}</div>
    ${{genreTags ? `<div class="panel-genres">${{genreTags}}</div>` : ''}}
    <div class="panel-links">
      <a class="panel-link" href="${{mbUrl}}" target="_blank">MusicBrainz</a>
      ${{gen1001Url ? `<a class="panel-link" href="${{gen1001Url}}" target="_blank" style="border-color:#7b61ff;color:#7b61ff">1001gen</a>` : ''}}
      ${{a.rym ? `<a class="panel-link rym" href="${{a.rym}}" target="_blank">RYM</a>` : ''}}
    </div>
    <div class="panel-divider"></div>
    <div class="panel-section-label">About</div>
    <div class="panel-bio" id="p-bio">${{aboutHtml}}</div>
    <div class="panel-divider"></div>
    <div class="panel-section-label">Listen on YouTube</div>
    <div class="panel-yt-wrap">${{ytBlock}}</div>
  `;
}}

// ── FILTERS ──
function setFilter(f) {{
  filter = f;
  ['all','heard','pending'].forEach(x => {{
    const btn = document.getElementById('btn-' + x);
    btn.classList.toggle('active', x === f);
    if (x === 'pending') {{
      btn.style.borderColor = f === 'pending' ? 'var(--pending)' : '';
      btn.style.color       = f === 'pending' ? 'var(--pending)' : '';
      btn.style.background  = f === 'pending' ? 'rgba(255,71,71,.06)' : '';
    }}
  }});
  applyFilters();
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase().trim();
  let vis = 0, visH = 0, visP = 0;
  document.querySelectorAll('.card').forEach(c => {{
    const matchFilter = filter === 'all'
      || (filter === 'heard'   && c.dataset.heard === '1')
      || (filter === 'pending' && c.dataset.heard === '0');
    const matchSearch = !q || c.dataset.title.includes(q) || c.dataset.artist.includes(q);
    const cardGenres = c.dataset.genres ? c.dataset.genres.split(',') : [];
    const matchGenre = selectedGenres.size === 0
      || [...selectedGenres].some(g => cardGenres.includes(g));
    const show = matchFilter && matchSearch && matchGenre;
    c.classList.toggle('hidden', !show);
    if (show) {{ vis++; if (c.dataset.heard === '1') visH++; else visP++; }}
  }});
  document.getElementById('vis-count').textContent   = vis;
  document.getElementById('vis-heard').textContent   = visH;
  document.getElementById('vis-pending').textContent = visP;
  document.getElementById('empty').style.display     = vis === 0 ? 'block' : 'none';
  const pct = vis > 0 ? Math.round(visH / vis * 100) : 0;
  document.getElementById('prog-pct').textContent = (filter !== 'all' || q || selectedGenres.size > 0)
    ? pct + '%' : '{pct}%';
}}

// ── INIT ──
const _isMobile = () => window.matchMedia('(max-width: 600px)').matches;

// Adjust #main top margin to match actual header height (handles wrapping on mobile)
function adjustMainTop() {{
  document.getElementById('main').style.marginTop = document.querySelector('header').offsetHeight + 'px';
}}
window.addEventListener('resize', adjustMainTop);

try {{
  const saved = localStorage.getItem('grid-cols');
  const defaultCols = _isMobile() ? 3 : 10;
  const v = saved ? Math.min(20, Math.max(3, parseInt(saved))) : defaultCols;
  document.getElementById('grid-slider').value = v;
  setGridSize(v);
}} catch(e) {{ setGridSize(_isMobile() ? 3 : 10); }}

fetch('{data_file}')
  .then(r => {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
  .then(data => {{
    ALBUMS = data;
    buildGrid();
    buildGenreList();
    adjustMainTop();
    // Open first card by default (desktop only — on mobile the panel would cover the grid)
    if (!_isMobile()) {{
      setTimeout(() => {{
        const firstCard = document.querySelector('.card:not(.hidden)');
        if (firstCard) {{
          const album = ALBUMS.find(a => a.n === parseInt(firstCard.dataset.num));
          if (album) openPanel(album, firstCard);
        }}
      }}, 100);
    }}
  }})
  .catch(err => {{
    document.getElementById('grid').innerHTML =
      '<div style="color:var(--muted);font-family:monospace;padding:40px">⚠ Could not load data: ' + err.message + '</div>';
  }});
</script>
</body>
</html>
"""



# ── SCARUFFI DECADES ──────────────────────────────────────────────────────────

SCARUFFI_DECADES = ["60", "70", "80", "90", "00", "10", "20"]
SCARUFFI_BASE    = "https://scaruffiplaylists.netlify.app"
SCARUFFI_DECADE_LABELS = {
    "60": "1960s", "70": "1970s", "80": "1980s",
    "90": "1990s", "00": "2000s", "10": "2010s", "20": "2020s",
}


def scaruffi_fetch_decade(decade: str, cache_dir: Path, debug: bool = False) -> list:
    """Scrape one decade page from scaruffiplaylists.netlify.app.
    Handles both HTML and Markdown responses automatically."""
    cache_file = cache_dir / f"scaruffi_{decade}s_cache.json"
    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        if data:
            print(f"  📦 Scaruffi {decade}s cache: {cache_file} ({len(data)} albums)")
            return data
        print(f"  ⚠ Cache empty for {decade}s, re-fetching...")

    url = f"{SCARUFFI_BASE}/{decade}/"
    print(f"  🌐 Scaruffi {decade}s: {url}")

    # Try urllib with text/plain Accept first — Netlify SSG sometimes serves
    # the pre-rendered content directly when JS is not requested
    raw = ""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "curl/7.88.1",
            "Accept": "text/plain, text/html;q=0.5",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception:
        pass

    # Fallback to subprocess curl
    if not raw:
        raw = curl_get(url)

    if not raw:
        print(f"  ❌ Could not fetch {url}")
        return []

    if debug:
        debug_file = cache_dir / f"scaruffi_{decade}s_raw.txt"
        debug_file.write_text(raw[:8000], encoding="utf-8")
        print(f"  🔍 Raw saved to {debug_file} ({len(raw)} chars)")

    is_html = raw.strip().startswith("<!") or "<html" in raw[:200] or "<body" in raw[:500]

    if is_html:
        albums = _parse_scaruffi_html(raw)
    else:
        albums = _parse_scaruffi_markdown(raw)
        if not albums:
            albums = _parse_scaruffi_html(raw)

    if not albums:
        print(f"  ⚠ Parsed 0 albums from {len(raw)} chars ({'HTML' if is_html else 'Markdown'})")
        print(f"     First 300 chars: {repr(raw[:300])}")

    cache_file.write_text(json.dumps(albums, ensure_ascii=False, indent=2))
    print(f"  ✅ {len(albums)} albums -> {cache_file}")
    return albums


def _get_link_from_html(html_frag: str, domains: list) -> str:
    """Extract first href matching any of the given domain substrings."""
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_frag)
    for href in hrefs:
        for domain in domains:
            if domain in href:
                return href
    return ""


def _get_cover_from_html(html_frag: str) -> str:
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_frag, re.IGNORECASE)
    if m:
        src = m.group(1)
        return src if src.startswith("http") else SCARUFFI_BASE + src
    return ""


def _parse_scaruffi_html(html: str) -> list:
    """Parse rendered HTML from scaruffiplaylists.netlify.app using stdlib HTMLParser.
    Structure: <h2 id="hN">rating/10</h2><ol class="playlist"><li id="N">...</li></ol>
    Each <li> has: <span class="title">Artist<br><cite>Title</cite><br>(year)</span>
                   <span class="stream"><a class="youtube-link" href="...">
    """
    from html.parser import HTMLParser as _HTMLParser

    class _Parser(_HTMLParser):
        def __init__(self):
            super().__init__()
            self.albums       = []
            self.rank         = 0
            self.cur_rating   = None
            self._h2_buf      = None   # None = not in h2
            self._in_li       = False
            self._in_title    = False
            self._in_cite     = False
            self._li          = {}
            self._title_parts = []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "h2":
                self._h2_buf = ""
            if tag == "li" and a.get("id", "").isdigit():
                self._in_li       = True
                self._in_title    = False
                self._in_cite     = False
                self._li          = {"cover": "", "yt": "", "sp": "", "bc": "", "sc": ""}
                self._title_parts = []
            if not self._in_li:
                return
            cls  = a.get("class", "")
            href = a.get("href",  "")
            if tag == "span" and "title" in cls:
                self._in_title = True
            if tag == "cite" and self._in_title:
                self._in_cite = True
            if tag == "br" and self._in_title:
                self._title_parts.append("\n")
            if tag == "img":
                src = a.get("src", "")
                if src and "icons" not in src and not self._li["cover"]:
                    self._li["cover"] = src if src.startswith("http") else SCARUFFI_BASE + src
            if tag == "a" and href:
                if   "youtube"     in cls: self._li["yt"] = href
                elif "spotify"     in cls: self._li["sp"] = href
                elif "bandcamp"    in cls: self._li["bc"] = href
                elif "soundcloud"  in cls: self._li["sc"] = href

        def handle_endtag(self, tag):
            if tag == "h2" and self._h2_buf is not None:
                m = re.search(r"([\d.]+)/10", self._h2_buf)
                if m:
                    self.cur_rating = float(m.group(1))
                self._h2_buf = None
            if tag == "cite":
                self._in_cite = False
            if tag == "span" and self._in_title:
                self._in_title = False
            if tag == "li" and self._in_li:
                self._in_li = False
                parts = [p.strip() for p in "".join(self._title_parts).split("\n") if p.strip()]
                artist = parts[0] if len(parts) >= 1 else ""
                title  = parts[1] if len(parts) >= 2 else ""
                year   = None
                if len(parts) >= 3:
                    my = re.search(r"\((\d{4})\)", parts[2])
                    if my:
                        year = int(my.group(1))
                if artist and title:
                    self.rank += 1
                    self.albums.append({
                        "rank": self.rank, "artist": artist, "title": title,
                        "year": year, "cover": self._li["cover"],
                        "rating": self.cur_rating,
                        "youtube": self._li["yt"], "spotify": self._li["sp"],
                        "bandcamp": self._li["bc"], "soundcloud": self._li["sc"],
                        "note": "", "mbid": "", "genres": [], "desc": "", "yt_id": "",
                    })

        def handle_data(self, data):
            if self._h2_buf is not None:
                self._h2_buf += data
            if self._in_title:
                self._title_parts.append(data)

    p = _Parser()
    p.feed(html)

    if p.albums:
        return p.albums

    # Fallback: strip tags, parse visible text as Markdown
    clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<style[^>]*>.*?</style>",   "", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<br\s*/?>",                "\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"</(p|li|div|tr|cite)>",     "\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<[^>]+>",                   " ",   clean)
    clean = unescape(clean)
    clean = re.sub(r"[ \t]+",  " ",   clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return _parse_scaruffi_markdown(clean)


def _parse_scaruffi_markdown(md: str) -> list:
    """Parse raw Markdown: ## rating, numbered list items."""
    albums = []
    current_rating = None

    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Rating header — Markdown "## 9.5/10" OR plain stripped text "9.5/10"
        m_rating = re.match(r"^#{1,3}\s*([\d.]+)/10", line) or re.match(r"^([\d.]+)/10\s*$", line)
        if m_rating:
            current_rating = float(m_rating.group(1))
            i += 1
            continue

        m_num = re.match(r"^(\d+)\.\s*(.*)", line)
        if m_num and current_rating is not None:
            rank      = int(m_num.group(1))
            remainder = m_num.group(2).strip()

            cover = ""
            m_img = re.search(r"!\[art\]\((/img/[^)]+)\)", remainder)
            if m_img:
                cover     = SCARUFFI_BASE + m_img.group(1)
                remainder = re.sub(r"!\[art\]\([^)]+\)", "", remainder).strip()

            block_lines = [remainder] if remainder else []
            j = i + 1
            while j < len(lines):
                nl = lines[j].strip()
                if re.match(r"^\d+\.\s", nl) or re.match(r"^##\s+[\d.]+/10", nl) or nl.startswith("[Home]"):
                    break
                block_lines.append(nl)
                j += 1

            raw_block = "\n".join(block_lines)

            def extract_md_link(s, platform):
                m = re.search(r"\[!\[" + platform + r"\]\([^)]*\)\]\(([^)]+)\)", s, re.IGNORECASE)
                return m.group(1) if m else ""

            yt = extract_md_link(raw_block, "youtube")
            sp = extract_md_link(raw_block, "spotify")
            bc = extract_md_link(raw_block, "bandcamp")
            sc = extract_md_link(raw_block, "soundcloud")

            def strip_md_icons(s):
                s = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", "", s)
                s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
                return s.strip()

            text_lines = [strip_md_icons(bl) for bl in block_lines if strip_md_icons(bl)]

            artist = text_lines[0].strip() if len(text_lines) >= 1 else ""
            title  = text_lines[1].strip() if len(text_lines) >= 2 else ""
            year   = None
            note   = ""

            if len(text_lines) >= 3:
                m_year = re.search(r"\((\d{4})\)", text_lines[2])
                if m_year:
                    year = int(m_year.group(1))
            if len(text_lines) >= 4:
                note = re.sub(r"\s+", " ", " ".join(text_lines[3:])).strip()

            if artist and title:
                albums.append({
                    "rank":       rank,
                    "artist":     artist,
                    "title":      title,
                    "year":       year,
                    "cover":      cover,
                    "rating":     current_rating,
                    "youtube":    yt,
                    "spotify":    sp,
                    "bandcamp":   bc,
                    "soundcloud": sc,
                    "note":       note,
                    "mbid":       "",
                    "genres":     [],
                    "desc":       "",
                    "yt_id":      "",
                })
            i = j
            continue

        i += 1

    return albums

def scaruffi_enrich_albums(albums: list, cache_dir: Path,
                            lfm_key: str = "", lfm_secret: str = "",
                            fetch_genres: bool = False) -> list:
    """Enrich Scaruffi albums with Last.fm desc + MusicBrainz genres and annotations.
    Cache fields: desc_lfm_album, desc_lfm_artist, desc_mb_album, desc_mb_artist, mbid, genres.
    Migrates legacy 'desc' → 'desc_lfm_album' automatically."""
    enrich_cache = cache_dir / "scaruffi_enrich_cache.json"
    raw_cached   = json.loads(enrich_cache.read_text()) if enrich_cache.exists() else {}
    # Migrate legacy entries
    cached = {k: _migrate_desc_entry(v) for k, v in raw_cached.items()}

    pylast  = None
    network = None
    if lfm_key and lfm_secret:
        pylast = _try_import("pylast")
        if pylast:
            network = pylast.LastFMNetwork(api_key=lfm_key, api_secret=lfm_secret)

    changed = False
    for album in albums:
        key   = _norm(album["artist"]) + "|||" + _norm(album["title"])
        entry = _migrate_desc_entry(cached.get(key, {}))

        # ── Last.fm album wiki ──
        if network and not entry["desc_lfm_album"]:
            try:
                lfm_al = network.get_album(album["artist"], album["title"])
                wiki   = _clean_lfm_text(lfm_al.get_wiki_summary() or "")
                if wiki and len(wiki) > 40:
                    entry["desc_lfm_album"] = wiki[:800]
                    changed = True
            except Exception:
                pass
            time.sleep(0.25)

        # ── Last.fm artist bio ──
        if network and not entry["desc_lfm_artist"]:
            try:
                lfm_ar = network.get_artist(album["artist"])
                bio    = _clean_lfm_text(lfm_ar.get_bio_summary() or "")
                if bio and len(bio) > 40:
                    entry["desc_lfm_artist"] = bio[:800]
                    changed = True
            except Exception:
                pass
            time.sleep(0.25)

        # ── MusicBrainz: find MBID for release-group ──
        if fetch_genres and not entry.get("mbid") and not entry.get("mbid_tried"):
            q = urllib.parse.quote(f'releasegroup:"{album["title"]}" AND artist:"{album["artist"]}"'  )
            try:
                req = urllib.request.Request(
                    f"https://musicbrainz.org/ws/2/release-group?query={q}&limit=1&fmt=json",
                    headers={"User-Agent": "ScaruffiTracker/1.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                rgs = data.get("release-groups", [])
                if rgs:
                    entry["mbid"] = rgs[0]["id"]
                    changed = True
            except Exception:
                pass
            entry["mbid_tried"] = True
            time.sleep(1.1)

        # ── MusicBrainz genres ──
        if fetch_genres and entry.get("mbid") and not entry.get("genres"):
            try:
                req = urllib.request.Request(
                    f"https://musicbrainz.org/ws/2/release-group/{entry['mbid']}?inc=genres&fmt=json",
                    headers={"User-Agent": "ScaruffiTracker/1.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                glist = [
                    (g["name"].lower(), g.get("count", 1))
                    for g in data.get("genres", [])
                    if g["name"].lower() not in GENRE_BLACKLIST and len(g["name"]) > 2
                ]
                glist.sort(key=lambda x: x[1], reverse=True)
                entry["genres"] = [g for g, _ in glist[:6]]
                changed = True
            except Exception:
                pass
            time.sleep(1.1)

        # ── MusicBrainz album annotation ──
        if entry.get("mbid") and not entry["desc_mb_album"]:
            ann = _fetch_mb_annotation(entry["mbid"], "release-group")
            if ann:
                entry["desc_mb_album"] = ann
                changed = True
            time.sleep(1.1)

        # ── MusicBrainz artist annotation ──
        if not entry["desc_mb_artist"]:
            artist_mbid = _fetch_mb_artist_mbid(album["artist"])
            if artist_mbid:
                ann = _fetch_mb_annotation(artist_mbid, "artist")
                if ann:
                    entry["desc_mb_artist"] = ann
                    changed = True
            time.sleep(1.1)

        if entry:
            cached[key]             = entry
            album["desc_lfm_album"] = entry.get("desc_lfm_album", "")
            album["desc_lfm_artist"]= entry.get("desc_lfm_artist", "")
            album["desc_mb_album"]  = entry.get("desc_mb_album", "")
            album["desc_mb_artist"] = entry.get("desc_mb_artist", "")
            album["mbid"]           = entry.get("mbid", "")
            album["genres"]         = entry.get("genres", [])

    if changed:
        enrich_cache.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
        print(f"  💾 enrich cache -> {enrich_cache}")

    return albums

def scaruffi_check_heard(user_albums: set, album: dict) -> bool:
    a_n = _norm(album["artist"])
    t_n = _norm(album["title"])
    if not t_n:
        return False
    for ua, ut in user_albums:
        if not ut:
            continue
        title_match = (t_n == ut or t_n in ut or (ut in t_n and len(ut) >= len(t_n) * 0.8))
        if not title_match:
            continue
        if not a_n or a_n in ua or ua in a_n:
            return True
    return False


def render_scaruffi_decade_html(decade: str, albums: list, users_heard: dict,
                                 series_name: str, all_decades: list) -> str:
    label     = SCARUFFI_DECADE_LABELS.get(decade, decade + "s")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    total     = len(albums)
    users     = list(users_heard.keys())

    decade_nav = ""
    for d in SCARUFFI_DECADES:
        lbl    = SCARUFFI_DECADE_LABELS.get(d, d + "s")
        active = "active" if d == decade else ""
        decade_nav += f'<a class="dec-item {active}" href="decade_{d}s.html">{lbl}</a>'

    all_genres: dict = {}
    for a in albums:
        for g in (a.get("genres") or []):
            all_genres[g] = all_genres.get(g, 0) + 1
    genre_opts_js = json.dumps(sorted(all_genres.items(), key=lambda x: -x[1]))

    albums_js = []
    for a in albums:
        heard_by = [u for u in users if scaruffi_check_heard(users_heard[u], a)]
        albums_js.append({
            "rank":           a["rank"],
            "artist":         a["artist"],
            "title":          a["title"],
            "year":           a.get("year"),
            "cover":          a.get("cover", ""),
            "rating":         a.get("rating", 0),
            "youtube":        a.get("youtube", ""),
            "spotify":        a.get("spotify", ""),
            "bandcamp":       a.get("bandcamp", ""),
            "soundcloud":     a.get("soundcloud", ""),
            "note":           a.get("note", ""),
            "mbid":           a.get("mbid", ""),
            "genres":         a.get("genres", []),
            "desc_lfm_album": a.get("desc_lfm_album", "") or a.get("desc", ""),  # migrate
            "desc_lfm_artist":a.get("desc_lfm_artist", ""),
            "desc_mb_album":  a.get("desc_mb_album", ""),
            "desc_mb_artist": a.get("desc_mb_artist", ""),
            "yt_id":          a.get("yt_id", ""),
            "heard_by":       heard_by,
            "rym":            a.get("rym", ""),
        })

    albums_json   = json.dumps(albums_js, ensure_ascii=False)
    users_json    = json.dumps(users, ensure_ascii=False)
    genre_json    = genre_opts_js
    cover_ph      = COVER_PLACEHOLDER

    # ── HTML ─────────────────────────────────────────────────────────────────
    css = """
:root{
  --bg:#0a0a0a;--surface:#111;--border:#1e1e1e;
  --accent:#e8ff47;--heard:#e8ff47;--pending:#ff4747;
  --text:#e0e0e0;--muted:#555;--gap:6px;
  --panel:390px;--header-h:58px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh}
header{
  position:fixed;top:0;left:0;right:var(--panel);height:var(--header-h);z-index:100;
  background:rgba(10,10,10,.97);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--border);border-right:1px solid var(--border);
  padding:0 18px;display:flex;align-items:center;gap:12px;
}
.back-link{font-family:'DM Mono',monospace;font-size:.68rem;color:var(--muted);text-decoration:none}
.back-link:hover{color:var(--text)}
.header-title{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;letter-spacing:.08em;color:var(--accent);white-space:nowrap}
.dec-wrap{position:relative}
.dec-btn{
  font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 9px;border-radius:3px;border:1px solid var(--accent);background:rgba(232,255,71,.06);
  color:var(--accent);cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:4px;white-space:nowrap;
}
.dec-btn:hover{background:rgba(232,255,71,.12)}
.dec-dropdown{
  display:none;position:fixed;background:#161616;border:1px solid var(--border);border-radius:4px;
  z-index:9999;min-width:160px;padding:4px 0;box-shadow:0 8px 32px rgba(0,0,0,.6);
}
.dec-dropdown.open{display:block}
.dec-dh{padding:5px 10px 4px;font-family:'DM Mono',monospace;font-size:.56rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);margin-bottom:3px}
.dec-item{display:block;padding:6px 14px;font-family:'DM Mono',monospace;font-size:.68rem;color:var(--text);text-decoration:none;transition:background .1s}
.dec-item:hover{background:var(--surface)}
.dec-item.active{color:var(--accent)}
.controls{display:flex;align-items:center;gap:7px;margin-left:auto;flex-shrink:0}
.filter-btn{
  font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 9px;border-radius:3px;border:1px solid var(--border);
  background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;
}
.filter-btn:hover{border-color:var(--muted);color:var(--text)}
.filter-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(232,255,71,.06)}
.search-box{
  font-family:'DM Mono',monospace;font-size:.62rem;padding:4px 9px;
  background:var(--surface);border:1px solid var(--border);border-radius:3px;
  color:var(--text);width:130px;outline:none;transition:border-color .15s;
}
.search-box:focus{border-color:var(--accent)}
.search-box::placeholder{color:var(--muted)}
.genre-wrap{position:relative}
.genre-btn{
  font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 9px;border-radius:3px;border:1px solid var(--border);background:transparent;
  color:var(--muted);cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:4px;
}
.genre-btn:hover,.genre-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(232,255,71,.06)}
.genre-btn .badge{background:var(--accent);color:#000;border-radius:10px;padding:1px 5px;font-size:.52rem;font-weight:700}
.genre-dropdown{
  display:none;position:fixed;top:calc(100% + 6px);right:0;
  background:#161616;border:1px solid var(--border);border-radius:4px;
  z-index:9999;min-width:200px;max-height:320px;overflow-y:auto;padding:4px 0;
  box-shadow:0 8px 32px rgba(0,0,0,.6);
}
.genre-dropdown.open{display:block}
.genre-dh{
  padding:5px 10px 4px;font-family:'DM Mono',monospace;font-size:.56rem;
  letter-spacing:.15em;text-transform:uppercase;color:var(--muted);
  border-bottom:1px solid var(--border);margin-bottom:3px;
  display:flex;justify-content:space-between;
}
.genre-clear{color:var(--pending);cursor:pointer}
.genre-item{display:flex;align-items:center;gap:7px;padding:4px 10px;cursor:pointer;transition:background .1s}
.genre-item:hover{background:var(--surface)}
.genre-item input{accent-color:var(--accent);cursor:pointer;flex-shrink:0}
.genre-item label{font-family:'DM Mono',monospace;font-size:.65rem;color:var(--text);cursor:pointer;flex:1;display:flex;justify-content:space-between}
.genre-item label span{color:var(--muted);font-size:.56rem}
.rating-wrap{display:flex;gap:3px}
.rating-btn{
  font-family:'DM Mono',monospace;font-size:.58rem;padding:3px 6px;border-radius:3px;
  border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;transition:all .15s;
}
.rating-btn:hover{border-color:var(--muted);color:var(--text)}
.rating-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(232,255,71,.06)}
#main{margin-top:var(--header-h);margin-right:var(--panel);padding:14px 18px 60px;position:relative;z-index:0}
.count-bar{font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted);margin-bottom:10px;display:flex;gap:14px}
.count-bar b{color:var(--text)}
#grid{display:grid;grid-template-columns:repeat(10,1fr);gap:var(--gap)}
.card{position:relative;aspect-ratio:1;border-radius:3px;overflow:hidden;cursor:pointer;transition:transform .15s}
.card:hover{transform:scale(1.05);z-index:10}
.card.hidden{display:none}
.card.active-card{outline:2px solid var(--accent);outline-offset:2px;z-index:11}
.card img{width:100%;height:100%;object-fit:cover;display:block;background:var(--surface)}
.heard-dot{position:absolute;top:4px;right:4px;width:7px;height:7px;border-radius:50%;z-index:3;background:var(--heard);box-shadow:0 0 5px var(--heard)}
.card-overlay{
  position:absolute;inset:0;
  background:linear-gradient(0deg,rgba(0,0,0,.9) 0%,rgba(0,0,0,0) 55%);
  opacity:0;transition:opacity .18s;display:flex;flex-direction:column;justify-content:flex-end;
  padding:6px;z-index:2;
}
.card:hover .card-overlay{opacity:1}
.card-rating{font-family:'Bebas Neue',sans-serif;font-size:.78rem;color:var(--accent);line-height:1}
.card-title{font-size:.56rem;font-weight:500;color:#fff;line-height:1.25;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.card-artist{font-size:.52rem;color:var(--muted);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#panel{
  position:fixed;top:0;right:0;bottom:0;width:var(--panel);
  background:#0c0c0c;border-left:1px solid var(--border);
  z-index:50;display:flex;flex-direction:column;overflow:hidden;
}
.panel-topbar{height:var(--header-h);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 15px;flex-shrink:0}
.panel-topbar-label{font-family:'DM Mono',monospace;font-size:.56rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
.panel-cover{width:100%;aspect-ratio:1;flex-shrink:0;position:relative;background:var(--surface);max-height:180px;overflow:hidden}
.panel-cover img{width:100%;height:100%;object-fit:cover;display:block}
.panel-cover-rating{position:absolute;bottom:8px;left:8px;font-family:'Bebas Neue',sans-serif;font-size:1rem;color:var(--accent);background:rgba(0,0,0,.7);padding:2px 7px;border-radius:2px}
.panel-body{flex:1;overflow-y:auto;padding:14px;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.panel-body::-webkit-scrollbar{width:3px}
.panel-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:8px;font-family:'DM Mono',monospace;font-size:.7rem;color:var(--muted);text-align:center}
.panel-empty-icon{font-size:2rem;opacity:.3}
.panel-title{font-family:'Bebas Neue',sans-serif;font-size:1.4rem;letter-spacing:.04em;color:var(--text);line-height:1.05;margin-bottom:2px}
.panel-artist{font-size:.78rem;color:var(--muted);margin-bottom:1px}
.panel-year{font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted);margin-bottom:10px}
.panel-genres{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.panel-genre-tag{font-family:'DM Mono',monospace;font-size:.56rem;padding:2px 6px;border-radius:2px;background:rgba(232,255,71,.07);border:1px solid rgba(232,255,71,.18);color:rgba(232,255,71,.65)}
.panel-heard-by{font-family:'DM Mono',monospace;font-size:.6rem;color:var(--muted);margin-bottom:9px}
.panel-heard-by b{color:var(--heard)}
.panel-divider{height:1px;background:var(--border);margin:9px 0}
.panel-section-label{font-family:'DM Mono',monospace;font-size:.54rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:5px}
.panel-bio{font-size:.72rem;color:#aaa;line-height:1.6;max-height:120px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.panel-bio::-webkit-scrollbar{width:3px}
.panel-bio::-webkit-scrollbar-thumb{background:var(--border)}
.desc-block{margin-bottom:9px}
.desc-source-label{font-family:'DM Mono',monospace;font-size:.5rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:2px;display:flex;align-items:center;gap:4px}
.desc-source-label::before{content:'';display:inline-block;width:5px;height:5px;border-radius:50%;background:currentColor;flex-shrink:0}
.desc-source-label.lfm{color:#d51007}.desc-source-label.mb{color:#ba478f}.desc-source-label.artist{color:#6a9fb5}
.desc-source-text{font-size:.7rem;color:#aaa;line-height:1.55}
.panel-note{font-family:'DM Mono',monospace;font-size:.62rem;color:#666;font-style:italic;line-height:1.5;margin-top:6px}
.panel-links{display:flex;gap:5px;flex-wrap:wrap;margin-top:9px}
.panel-link{font-family:'DM Mono',monospace;font-size:.58rem;letter-spacing:.07em;text-transform:uppercase;padding:3px 8px;border-radius:3px;border:1px solid var(--border);color:var(--muted);text-decoration:none;transition:all .15s}
.panel-link:hover{border-color:var(--accent);color:var(--accent)}
.panel-link.yt{border-color:#f00;color:#f00}
.panel-link.yt:hover{background:rgba(255,0,0,.08)}
.panel-link.sp{border-color:#1db954;color:#1db954}
.panel-link.sp:hover{background:rgba(29,185,84,.08)}
.panel-link.bc{border-color:#1da0c3;color:#1da0c3}
.panel-link.sc{border-color:#f50;color:#f50}
.panel-link.rym{border-color:#5baadb;color:#5baadb}
.panel-link.rym:hover{background:rgba(48,81,159,.08)}
.panel-yt-wrap{margin-top:11px;border-radius:4px;overflow:hidden;background:var(--surface);border:1px solid var(--border)}
.panel-yt-wrap iframe{display:block;width:100%;height:145px;border:none}
.panel-yt-placeholder{height:60px;display:flex;align-items:center;justify-content:center;font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted)}
.panel-close-btn{display:none;position:absolute;top:13px;right:13px;width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.07);border:1px solid var(--border);color:var(--text);font-size:1rem;cursor:pointer;align-items:center;justify-content:center;z-index:10;transition:background .15s}
.panel-close-btn:hover{background:rgba(255,255,255,.18)}
.grid-sizer{display:flex;align-items:center;gap:5px}
.grid-sizer span{font-family:'DM Mono',monospace;font-size:.6rem;color:var(--muted);min-width:24px;text-align:right}
#grid-slider{-webkit-appearance:none;appearance:none;width:70px;height:3px;background:var(--border);border-radius:2px;outline:none;cursor:pointer}
#grid-slider::-webkit-slider-thumb{-webkit-appearance:none;width:11px;height:11px;border-radius:50%;background:var(--accent);cursor:pointer}
#grid-slider::-moz-range-thumb{width:11px;height:11px;border-radius:50%;background:var(--accent);border:none;cursor:pointer}
#empty{display:none;text-align:center;padding:50px 0;font-family:'DM Mono',monospace;color:var(--muted);font-size:.7rem}
@media(max-width:600px){
  :root{--header-h:50px}
  header{right:0;height:auto;min-height:var(--header-h);flex-wrap:wrap;padding:8px 12px;gap:6px 10px;overflow:visible}
  #main{margin-right:0;padding:10px 10px 60px}
  #panel{inset:0;width:100%;border-left:none;transform:translateY(105%);transition:transform .28s cubic-bezier(.4,0,.2,1)}
  #panel.panel-open{transform:translateY(0)}
  .panel-close-btn{display:flex}
  .controls{flex:0 0 100%;margin-left:0;overflow-x:auto;flex-wrap:nowrap;gap:5px;padding:5px 0 2px;border-top:1px solid var(--border);scrollbar-width:none}
  .controls::-webkit-scrollbar{display:none}
  .dec-wrap{display:none}
}
.user-wrap{position:relative}
.user-btn{font-family:'DM Mono',monospace;font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;padding:4px 9px;border-radius:3px;border:1px solid var(--accent);background:rgba(232,255,71,.06);color:var(--accent);cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:5px;white-space:nowrap}
.user-btn:hover{background:rgba(232,255,71,.12)}
.user-btn .u-name{max-width:90px;overflow:hidden;text-overflow:ellipsis}
.user-dropdown{display:none;position:fixed;background:#161616;border:1px solid var(--border);border-radius:4px;z-index:9999;min-width:164px;padding:4px 0;box-shadow:0 8px 32px rgba(0,0,0,.6)}
.user-dropdown.open{display:block}
.user-dh{padding:5px 10px 4px;font-family:'DM Mono',monospace;font-size:.56rem;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);margin-bottom:3px}
.user-item{display:flex;align-items:center;gap:7px;padding:5px 10px;cursor:pointer;transition:background .1s;font-family:'DM Mono',monospace;font-size:.68rem;color:var(--text)}
.user-item:hover{background:var(--surface)}
.user-item.active{color:var(--accent)}
.user-item .u-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;background:var(--border)}
.user-item.active .u-dot{background:var(--accent)}
.card::before{content:'';position:absolute;top:4px;right:4px;width:7px;height:7px;border-radius:50%;z-index:3}
.card.heard-user::before{background:var(--heard);box-shadow:0 0 5px var(--heard)}
.card.unheard-user::before{background:var(--pending);box-shadow:0 0 5px var(--pending)}"""

    js = f"""
const ALBUMS = {albums_json};
const USERS  = {users_json};
const GENRE_OPTS = {genre_json};
let filter = 'all';
let selectedGenres = new Set();
let selectedRating = null;
let selectedUser   = null;
const COVER_PH = '{cover_ph}';

function isHeard(a) {{
  if (selectedUser) return a.heard_by.includes(selectedUser);
  return a.heard_by.length > 0;
}}

function thumbUrl(url) {{
  if (!url) return url;
  return url
    .replace(/\/front-500\b/, '/front-250')
    .replace(/e\.snmc\.io\/i\/\d+\//, 'e.snmc.io/i/150/');
}}

const PRELOAD_CONCURRENCY = 8;
let _preloadQueue = [];
let _preloadActive = 0;

function _preloadTick() {{
  while (_preloadActive < PRELOAD_CONCURRENCY && _preloadQueue.length) {{
    _preloadActive++;
    const img = _preloadQueue.shift();
    const url = img.dataset.src;
    if (!url) {{ _preloadActive--; _preloadTick(); return; }}
    const tmp = new Image();
    tmp.onload = () => {{ img.src = url; img.removeAttribute('data-src'); _preloadActive--; _preloadTick(); }};
    tmp.onerror = () => {{ _preloadActive--; _preloadTick(); }};
    tmp.src = url;
  }}
}}

function startPreload() {{
  _preloadQueue = Array.from(document.querySelectorAll('img[data-src]'));
  _preloadActive = 0;
  _preloadTick();
}}

function buildGenreList() {{
  const list = document.getElementById('genre-list');
  list.innerHTML = '';
  GENRE_OPTS.forEach(([genre, count]) => {{
    const div = document.createElement('div');
    div.className = 'genre-item';
    const id = 'g-'+genre.replace(/[^a-z0-9]/g,'_');
    div.innerHTML = '<input type="checkbox" id="'+id+'" value="'+genre+'" onchange="toggleGenre(\\''+genre+'\\',this.checked)"><label for="'+id+'">'+genre+'<span>'+count+'</span></label>';
    list.appendChild(div);
  }});
}}

function toggleGenreDD() {{
  const dd  = document.getElementById('genre-dd');
  const btn = document.getElementById('genre-btn');
  const open = !dd.classList.contains('open');
  dd.classList.toggle('open', open);
  btn.classList.toggle('active', open || selectedGenres.size > 0);
  if (open) {{
    const r = btn.getBoundingClientRect();
    dd.style.top  = (r.bottom + 4) + 'px';
    dd.style.left = Math.max(4, r.right - 200) + 'px';
  }}
}}

function toggleGenre(g, checked) {{
  if (checked) selectedGenres.add(g); else selectedGenres.delete(g);
  const badge = document.getElementById('genre-badge');
  const btn   = document.getElementById('genre-btn');
  if (selectedGenres.size>0) {{ badge.textContent=selectedGenres.size; badge.style.display=''; btn.classList.add('active'); }}
  else {{ badge.style.display='none'; btn.classList.remove('active'); }}
  applyFilters();
}}

function clearGenres() {{
  selectedGenres.clear();
  document.querySelectorAll('#genre-list input').forEach(i=>i.checked=false);
  document.getElementById('genre-badge').style.display='none';
  document.getElementById('genre-btn').classList.remove('active');
  applyFilters();
}}

document.addEventListener('click', e => {{
  if (!e.target.closest('.genre-wrap')) document.getElementById('genre-dd').classList.remove('open');
  if (!e.target.closest('.user-wrap'))  document.getElementById('user-dd').classList.remove('open');
  if (!e.target.closest('.dec-wrap'))   document.getElementById('dec-dd').classList.remove('open');
}});

function toggleDecDD() {{
  const dd  = document.getElementById('dec-dd');
  const btn = document.getElementById('dec-btn');
  const open = !dd.classList.contains('open');
  dd.classList.toggle('open', open);
  if (open) {{
    const r = btn.getBoundingClientRect();
    dd.style.top  = (r.bottom + 4) + 'px';
    dd.style.left = r.left + 'px';
  }}
}}

function buildRatingBtns() {{
  const ratings = [...new Set(ALBUMS.map(a=>a.rating))].sort((a,b)=>b-a);
  const wrap = document.getElementById('rating-btns');
  ratings.forEach(r => {{
    const btn = document.createElement('button');
    btn.className='rating-btn'; btn.textContent=r; btn.dataset.rating=r;
    btn.onclick = () => {{
      if (selectedRating===r) {{ selectedRating=null; btn.classList.remove('active'); }}
      else {{ selectedRating=r; document.querySelectorAll('.rating-btn').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); }}
      applyFilters();
    }};
    wrap.appendChild(btn);
  }});
}}

function buildUserList() {{
  const list = document.getElementById('user-list');
  list.innerHTML = '';
  const allDiv = document.createElement('div');
  allDiv.className = 'user-item' + (!selectedUser ? ' active' : '');
  allDiv.innerHTML = '<span class="u-dot"></span>All users';
  allDiv.onclick = () => setUser(null);
  list.appendChild(allDiv);
  USERS.forEach(u => {{
    const div = document.createElement('div');
    div.className = 'user-item' + (selectedUser===u ? ' active' : '');
    const n = ALBUMS.filter(a=>a.heard_by.includes(u)).length;
    div.innerHTML = '<span class="u-dot"></span>'+u+'<span style="color:var(--muted);font-size:.58rem;margin-left:auto">'+n+'</span>';
    div.onclick = () => setUser(u);
    list.appendChild(div);
  }});
}}

function toggleUserDD() {{
  const dd  = document.getElementById('user-dd');
  const btn = document.getElementById('user-btn');
  const open = !dd.classList.contains('open');
  dd.classList.toggle('open', open);
  if (open) {{
    const r = btn.getBoundingClientRect();
    dd.style.top  = (r.bottom + 4) + 'px';
    dd.style.left = Math.max(4, r.right - 164) + 'px';
  }}
}}

function setUser(u) {{
  selectedUser = u;
  document.getElementById('user-btn-label').textContent = u || 'All users';
  document.getElementById('user-dd').classList.remove('open');
  buildUserList();
  document.querySelectorAll('.card').forEach(card => {{
    const rank = parseInt(card.dataset.num);
    const a    = ALBUMS.find(x=>x.rank===rank);
    if (!a) return;
    const heard = isHeard(a);
    card.dataset.heard = heard ? '1' : '0';
    card.classList.remove('heard-user','unheard-user');
    card.classList.add(heard ? 'heard-user' : 'unheard-user');
    let dot = card.querySelector('.heard-dot');
    if (heard && !dot) {{ dot = document.createElement('div'); dot.className='heard-dot'; card.appendChild(dot); }}
    else if (!heard && dot) {{ dot.remove(); }}
  }});
  applyFilters();
}}

function buildGrid() {{
  const grid = document.getElementById('grid');
  grid.innerHTML='';
  ALBUMS.forEach(a => {{
    const card = document.createElement('div');
    const heard = isHeard(a);
    card.className = 'card ' + (heard ? 'heard-user' : 'unheard-user');
    card.dataset.artist = a.artist.toLowerCase();
    card.dataset.title  = a.title.toLowerCase();
    card.dataset.rating = a.rating;
    card.dataset.genres = (a.genres||[]).join(',');
    card.dataset.heard  = heard ? '1' : '0';
    card.dataset.num    = a.rank;
    const coverSrc = a.cover || COVER_PH;
    const img = document.createElement('img');
    img.dataset.src = thumbUrl(coverSrc); img.src = COVER_PH; img.alt = a.rank;
    img.onerror = function(){{ this.onerror=null; this.src=COVER_PH; }};
    card.appendChild(img);
    if (heard) {{ const dot=document.createElement('div'); dot.className='heard-dot'; card.appendChild(dot); }}
    card.insertAdjacentHTML('beforeend',
      '<div class="card-overlay">'+
      '<div class="card-rating">'+a.rating+'</div>'+
      '<div class="card-title">'+a.title+'</div>'+
      '<div class=\"card-artist\">'+a.artist+(a.year?' \xb7 '+a.year:'')+'</div>'+
      '</div>');
    card.addEventListener('click', () => openPanel(a, card));
    grid.appendChild(card);
  }});
  startPreload();
  applyFilters();
}}

const _isMobile = () => window.matchMedia('(max-width:600px)').matches;

function closePanel() {{
  document.getElementById('panel').classList.remove('panel-open');
  document.querySelectorAll('.card.active-card').forEach(c=>c.classList.remove('active-card'));
}}

function setGridSize(val) {{
  document.getElementById('grid-label').textContent = val + '\xd7';
  document.getElementById('grid').style.gridTemplateColumns = 'repeat('+val+',1fr)';
  try {{ localStorage.setItem('grid-cols-scaruffi', val); }} catch(e) {{}}
}}

function openPanel(a, cardEl) {{
  document.querySelectorAll('.card.active-card').forEach(c=>c.classList.remove('active-card'));
  cardEl.classList.add('active-card');
  if (_isMobile()) document.getElementById('panel').classList.add('panel-open');

  const coverWrap = document.getElementById('panel-cover-wrap');
  coverWrap.style.display='';
  const img = document.getElementById('p-cover');
  img.src = a.cover || COVER_PH;
  img.onerror = function(){{ this.src=COVER_PH; }};
  document.getElementById('p-rating').textContent = a.rating+'/10';

  const links = [];
  if (a.youtube)    links.push('<a class="panel-link yt" href="'+a.youtube+'" target="_blank">YouTube</a>');
  if (a.spotify)    links.push('<a class="panel-link sp" href="'+a.spotify+'" target="_blank">Spotify</a>');
  if (a.bandcamp)   links.push('<a class="panel-link bc" href="'+a.bandcamp+'" target="_blank">Bandcamp</a>');
  if (a.soundcloud) links.push('<a class="panel-link sc" href="'+a.soundcloud+'" target="_blank">SoundCloud</a>');
  if (a.rym)        links.push('<a class="panel-link rym" href="'+a.rym+'" target="_blank">RYM</a>');
  if (a.mbid)       links.push('<a class="panel-link" href="https://musicbrainz.org/release-group/'+a.mbid+'" target="_blank">MusicBrainz</a>');

  let ytBlock = '';
  if (a.yt_id) {{
    ytBlock = '<iframe src="https://www.youtube.com/embed/'+a.yt_id+'" allow="autoplay;encrypted-media" allowfullscreen></iframe>';
  }} else if (a.youtube && a.youtube.includes('youtube')) {{
    const ytUrl = a.youtube.replace('music.youtube.com','www.youtube.com').replace('/playlist?','/embed/videoseries?');
    ytBlock = '<iframe src="'+ytUrl+'" allow="autoplay;encrypted-media" allowfullscreen></iframe>';
  }} else {{
    const q = encodeURIComponent(a.artist+' '+a.title+' full album');
    ytBlock = '<div class="panel-yt-placeholder"><a href="https://www.youtube.com/results?search_query='+q+'" target="_blank" style="color:var(--accent);text-decoration:none">Search YouTube \u2197</a></div>';
  }}

  const genreTags = (a.genres||[]).map(g=>'<span class="panel-genre-tag">'+g+'</span>').join('');
  const heardLine = a.heard_by.length>0 ? '<div class="panel-heard-by">Heard by <b>'+a.heard_by.join(', ')+'</b></div>' : '';
  const noteHtml  = a.note ? '<div class="panel-note">'+a.note+'</div>' : '';
  const descSrcs  = [
    {{key:'desc_lfm_album',  cls:'lfm',    lbl:'💿 Album \u00b7 Last.fm'}},
    {{key:'desc_lfm_artist', cls:'artist',  lbl:'🎙 Artist \u00b7 Last.fm'}},
    {{key:'desc_mb_album',   cls:'mb',      lbl:'💿 Album \u00b7 MusicBrainz'}},
    {{key:'desc_mb_artist',  cls:'mb artist',lbl:'🎙 Artist \u00b7 MusicBrainz'}},
  ];
  const descBlocks = descSrcs.filter(s=>a[s.key]&&a[s.key].length>40)
    .map(s=>'<div class="desc-block"><div class="desc-source-label '+s.cls+'">'+s.lbl+'</div><div class="desc-source-text">'+a[s.key]+'</div></div>').join('');
  const bioHtml = descBlocks || '<span style="color:var(--muted);font-style:italic">Loading\u2026</span>';
  const needsFetch = !descBlocks;

  document.getElementById('panel-body').innerHTML =
    '<div class="panel-title">'+a.title+'</div>'
    +'<div class="panel-artist">'+a.artist+'</div>'
    +'<div class="panel-year">'+(a.year||'')+'</div>'
    +(genreTags?'<div class="panel-genres">'+genreTags+'</div>':'')
    +heardLine
    +'<div class="panel-links">'+links.join('')+'</div>'
    +'<div class="panel-divider"></div>'
    +'<div class="panel-section-label">Listen on YouTube</div>'
    +'<div class="panel-yt-wrap">'+ytBlock+'</div>'
    +'<div class="panel-divider"></div>'
    +'<div class="panel-section-label">About</div>'
    +'<div class="panel-bio" id="p-bio">'+bioHtml+'</div>'
    +noteHtml;

  if (needsFetch) fetchBio(a.artist, a.title, a.mbid);
}}

async function fetchBio(artist, title, mbid) {{
  const bioEl = document.getElementById('p-bio');
  if (!bioEl) return;
  const KEY = 'c9b21e5a749e4f279b6cdce9d5b3a7b3';
  const clean = t => t.replace(/<a href="[^"]*last\\.fm[^"]*"[^>]*>[^<]*<\\/a>/g,'').replace(/<[^>]+>/g,'').replace(/ {{2,}}/g,' ').trim().slice(0,800);
  const blocks = [];
  try {{
    const d  = await fetch('https://ws.audioscrobbler.com/2.0/?method=album.getinfo&artist='+encodeURIComponent(artist)+'&album='+encodeURIComponent(title)+'&format=json&api_key='+KEY).then(r=>r.json());
    const wiki = clean(d?.album?.wiki?.summary||d?.album?.wiki?.content||'');
    if (wiki.length>40) blocks.push('<div class="desc-block"><div class="desc-source-label lfm">💿 Album \u00b7 Last.fm</div><div class="desc-source-text">'+wiki+'</div></div>');
    const d2 = await fetch('https://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist='+encodeURIComponent(artist)+'&format=json&api_key='+KEY).then(r=>r.json());
    const bio = clean(d2?.artist?.bio?.summary||'');
    if (bio.length>40) blocks.push('<div class="desc-block"><div class="desc-source-label artist">🎙 Artist \u00b7 Last.fm</div><div class="desc-source-text">'+bio+'</div></div>');
  }} catch(e) {{}}
  try {{
    if (mbid) {{
      const mb  = await fetch('https://musicbrainz.org/ws/2/release-group/'+mbid+'?inc=annotation&fmt=json').then(r=>r.json());
      const ann = (mb?.annotation?.text||'').trim();
      if (ann.length>20) blocks.push('<div class="desc-block"><div class="desc-source-label mb">💿 Album \u00b7 MusicBrainz</div><div class="desc-source-text">'+ann.slice(0,800)+'</div></div>');
    }}
  }} catch(e) {{}}
  if (bioEl) bioEl.innerHTML = blocks.length ? blocks.join('') : 'No info available.';
}}

function setFilter(f) {{
  filter=f;
  ['all','heard','unheard'].forEach(x => {{
    const btn=document.getElementById('btn-'+x); if(!btn) return;
    btn.classList.toggle('active',x===f);
    if(x==='unheard') {{
      btn.style.borderColor=f==='unheard'?'var(--pending)':'';
      btn.style.color=f==='unheard'?'var(--pending)':'';
      btn.style.background=f==='unheard'?'rgba(255,71,71,.06)':'';
    }}
  }});
  applyFilters();
}}

function applyFilters() {{
  const q=document.getElementById('search').value.toLowerCase().trim();
  let vis=0,visH=0;
  document.querySelectorAll('.card').forEach(c => {{
    const mf=filter==='all'||(filter==='heard'&&c.dataset.heard==='1')||(filter==='unheard'&&c.dataset.heard==='0');
    const ms=!q||c.dataset.title.includes(q)||c.dataset.artist.includes(q);
    const cg=c.dataset.genres?c.dataset.genres.split(','):[];
    const mg=selectedGenres.size===0||[...selectedGenres].some(g=>cg.includes(g));
    const mr=!selectedRating||parseFloat(c.dataset.rating)===selectedRating;
    const show=mf&&ms&&mg&&mr;
    c.classList.toggle('hidden',!show);
    if(show){{vis++;if(c.dataset.heard==='1')visH++;}}
  }});
  document.getElementById('vis-count').textContent=vis;
  const uLabel = selectedUser ? ' ('+selectedUser+')' : '';
  document.getElementById('vis-heard').textContent=visH+' heard'+uLabel;
  document.getElementById('empty').style.display=vis===0?'block':'none';
}}

buildGenreList(); buildRatingBtns(); buildUserList(); buildGrid();
try{{const sv=localStorage.getItem('grid-cols-scaruffi');const dv=_isMobile()?3:10;const v=sv?Math.min(20,Math.max(3,parseInt(sv))):dv;document.getElementById('grid-slider').value=v;setGridSize(v);}}catch(e){{setGridSize(_isMobile()?3:10);}}
setTimeout(()=>{{
  if(!_isMobile()){{const first=document.querySelector('.card:not(.hidden)');if(first){{const a=ALBUMS.find(x=>x.rank===parseInt(first.dataset.num));if(a)openPanel(a,first);}}}}
}},100);"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Scaruffi {label}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<!-- Umami Analytics -->
<script
    defer
    src="https://cloud.umami.is/script.js"
    data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"
></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<header>
  <a href="index.html" class="back-link">←</a>
  <span class="header-title">Scaruffi {label}</span>
  <div class="dec-wrap">
    <button class="dec-btn" id="dec-btn" onclick="toggleDecDD()">
      Decade: {label} &#x25BE;
    </button>
  </div>
  <div class="controls">
    <button class="filter-btn active" id="btn-all"     onclick="setFilter('all')">All</button>
    <button class="filter-btn"        id="btn-heard"   onclick="setFilter('heard')">Heard</button>
    <button class="filter-btn"        id="btn-unheard" onclick="setFilter('unheard')">Unheard</button>
    <input class="search-box" id="search" placeholder="Search..." oninput="applyFilters()">
    <div class="genre-wrap">
      <button class="genre-btn" id="genre-btn" onclick="toggleGenreDD()">
        Genre <span class="badge" id="genre-badge" style="display:none">0</span> v
      </button>
    </div>
    <div class="user-wrap">
      <button class="user-btn" id="user-btn" onclick="toggleUserDD()">
        <span class="u-name" id="user-btn-label">All users</span> &#x25BE;
      </button>
    </div>
    <div class="rating-wrap" id="rating-btns"></div>
    <div class="grid-sizer">
      <span id="grid-label">10×</span>
      <input type="range" id="grid-slider" min="3" max="20" value="10" step="1" oninput="setGridSize(this.value)">
    </div>
  </div>
</header>
<main id="main">
  <div class="count-bar">
    <span>Showing <b id="vis-count">{total}</b> of {total}</span>
    <span><b id="vis-heard">0</b> heard</span>
  </div>
  <div id="grid"></div>
  <div id="empty">No albums match your filters.</div>
</main>
<aside id="panel">
  <button class="panel-close-btn" onclick="closePanel()" aria-label="Close">&#x2715;</button>
  <div class="panel-topbar">
    <span class="panel-topbar-label">Album detail</span>
  </div>
  <div id="panel-cover-wrap" class="panel-cover" style="display:none">
    <img id="p-cover" src="" alt="">
    <span class="panel-cover-rating" id="p-rating"></span>
  </div>
  <div class="panel-body" id="panel-body">
    <div class="panel-empty"><div class="panel-empty-icon">◉</div>Click an album</div>
  </div>
</aside>
<!-- Dropdowns rendered at body level so position:fixed is never clipped by header overflow -->
<div class="dec-dropdown" id="dec-dd">
  <div class="dec-dh">Jump to decade</div>
  {decade_nav}
</div>
<div class="genre-dropdown" id="genre-dd">
  <div class="genre-dh">Filter by genre <span class="genre-clear" onclick="clearGenres()">clear</span></div>
  <div id="genre-list"></div>
</div>
<div class="user-dropdown" id="user-dd">
  <div class="user-dh">View as user</div>
  <div id="user-list"></div>
</div>
<script>{js}</script>
</body>
</html>"""


def render_scaruffi_index_html(decades_data: dict, users: list, generated: str) -> str:
    rows = ""
    for decade in SCARUFFI_DECADES:
        if decade not in decades_data:
            continue
        albums = decades_data[decade]
        label  = SCARUFFI_DECADE_LABELS.get(decade, decade + "s")
        total  = len(albums)
        user_cells = ""
        for u in users:
            heard = sum(1 for a in albums if u in (a.get("heard_by") or []))
            pct   = round(heard / total * 100) if total else 0
            user_cells += f'<td class="uc"><span class="uc-heard">{heard}</span><span class="uc-pct">{pct}%</span></td>'
        rows += f'<tr><td class="dc"><a href="decade_{decade}s.html" class="dec-a">{label}</a></td><td class="tc">{total}</td>{user_cells}</tr>'

    user_headers = "".join(f'<th>{u}</th>' for u in users)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Scaruffi Decades</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<!-- Umami Analytics -->
<script
    defer
    src="https://cloud.umami.is/script.js"
    data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"
></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0a0a;--surface:#111;--border:#1e1e1e;--accent:#e8ff47;--text:#e0e0e0;--muted:#555}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh}}
header{{padding:48px 60px 32px;border-bottom:1px solid var(--border)}}
.site-label{{font-family:'DM Mono',monospace;font-size:.65rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}}
h1{{font-family:'Bebas Neue',sans-serif;font-size:3.5rem;letter-spacing:.06em;color:var(--accent);line-height:1}}
.header-meta{{font-family:'DM Mono',monospace;font-size:.65rem;color:var(--muted);margin-top:8px}}
main{{padding:40px 60px 80px}}
.back-link{{font-family:'DM Mono',monospace;font-size:.7rem;color:var(--muted);text-decoration:none;display:inline-block;margin-bottom:24px}}
.back-link:hover{{color:var(--text)}}
table{{width:100%;border-collapse:collapse;font-family:'DM Mono',monospace;font-size:.72rem}}
thead th{{color:var(--muted);font-size:.62rem;letter-spacing:.15em;text-transform:uppercase;padding:8px 12px;border-bottom:1px solid var(--border);text-align:left}}
tbody tr{{border-bottom:1px solid #161616;transition:background .1s}}
tbody tr:hover{{background:var(--surface)}}
td{{padding:10px 12px;vertical-align:middle}}
.dc{{width:110px}}
.dec-a{{font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.04em;color:var(--text);text-decoration:none;transition:color .15s}}
.dec-a:hover{{color:var(--accent)}}
.tc{{color:var(--muted);text-align:center}}
.uc{{text-align:center}}
.uc-heard{{color:var(--accent);font-weight:500;display:block}}
.uc-pct{{color:var(--muted);font-size:.6rem}}
footer{{padding:24px 60px;border-top:1px solid var(--border);font-family:'DM Mono',monospace;font-size:.62rem;color:var(--muted)}}
@media(max-width:700px){{header,main,footer{{padding-left:20px;padding-right:20px}}}}
</style>
</head>
<body>
<header>
  <div class="site-label">Scaruffi's Best Rock Albums</div>
  <h1>By Decade</h1>
  <div class="header-meta">Generated {generated}</div>
</header>
<main>
  <a href="../index.html" class="back-link">All collections</a>
  <table>
    <thead><tr><th>Decade</th><th>Albums</th>{user_headers}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
</main>
<footer>Generated {generated}</footer>
</body>
</html>"""


def scaruffi_fetch_covers(albums_all: list, cache_dir: Path,
                          lfm_key: str = "", discogs_token: str = "") -> int:
    """Fetch HD covers for Scaruffi albums.
    Priority: MusicBrainz CAA (needs mbid) → Last.fm → Discogs.
    Updates the cover field in-place and persists cache.
    Returns number of covers updated."""
    cover_cache_file = cache_dir / "scaruffi_covers_cache.json"
    cache = json.loads(cover_cache_file.read_text()) if cover_cache_file.exists() else {}

    updated = 0
    for album in albums_all:
        key = _norm(album["artist"]) + "|||" + _norm(album["title"])
        if cache.get(key):
            album["cover"] = cache[key]
            continue  # already have HD cover

        artist = album["artist"]
        title  = album["title"]
        mbid   = album.get("mbid", "")
        new_cover = ""

        # ── Strategy 1: Cover Art Archive (free, high-res) ──
        if mbid and not new_cover:
            try:
                url = f"https://coverartarchive.org/release-group/{mbid}/front"
                req = urllib.request.Request(url, headers={"User-Agent": "ScaruffiTracker/1.0"})
                # CAA redirects to actual image — follow redirect
                with urllib.request.urlopen(req, timeout=10) as r:
                    new_cover = r.url  # final URL after redirect
            except Exception:
                pass
            time.sleep(0.3)

        # ── Strategy 2: Last.fm album.getInfo image (extralarge ~300px) ──
        if not new_cover:
            try:
                api_key = lfm_key or "c9b21e5a749e4f279b6cdce9d5b3a7b3"
                params  = urllib.parse.urlencode({
                    "method": "album.getinfo",
                    "artist": artist, "album": title,
                    "api_key": api_key, "format": "json"
                })
                req = urllib.request.Request(
                    f"https://ws.audioscrobbler.com/2.0/?{params}",
                    headers={"User-Agent": "ScaruffiTracker/1.0"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                images = data.get("album", {}).get("image", [])
                # Pick largest available: extralarge (index 3), then mega (4)
                for img in reversed(images):
                    src = img.get("#text", "")
                    if src and "2a96cbd8b46e442fc41c2b86b821562f" not in src:
                        new_cover = src
                        break
            except Exception:
                pass
            time.sleep(0.25)

        # ── Strategy 3: Discogs search ──
        if not new_cover and discogs_token:
            try:
                q = urllib.parse.urlencode({"q": f"{artist} {title}", "type": "release", "per_page": "1"})
                req = urllib.request.Request(
                    f"https://api.discogs.com/database/search?{q}",
                    headers={
                        "User-Agent":    "ScaruffiTracker/1.0",
                        "Authorization": f"Discogs token={discogs_token}",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                results = data.get("results", [])
                if results:
                    thumb = results[0].get("cover_image") or results[0].get("thumb", "")
                    if thumb:
                        new_cover = thumb
            except Exception:
                pass
            time.sleep(0.5)

        if new_cover:
            album["cover"] = new_cover
            cache[key] = new_cover
            updated += 1
            print(f"    🖼  {artist} — {title}")

    cover_cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    return updated


def run_scaruffi(args, root_dir: Path) -> None:
    out_dir = root_dir / "scaruffi"
    out_dir.mkdir(parents=True, exist_ok=True)

    lfm_key    = getattr(args, "lastfm_api_key",    None) or ""
    lfm_secret = getattr(args, "lastfm_api_secret", None) or ""
    do_genres  = getattr(args, "genres",             False)
    index_only = getattr(args, "index_only",         False)

    # Usuarios: desde must_hear.db si disponible, sino desde scrobbles
    _mh_c  = getattr(args, "_sca_mh_conn", None)
    _scr_path = args.scrobbles_db or args.db
    if _mh_c:
        users = args.users or mh_get_users(_mh_c)
    elif _scr_path:
        import sqlite3 as _sq
        with _sq.connect(_scr_path) as _c:
            users = args.users or _scrobbles_get_users(_c)
    else:
        users = args.users or []
    print(f"Scaruffi: {len(users)} users: {', '.join(users)}")

    if _scr_path:
        import sqlite3 as _sq
        _scr_conn = _sq.connect(_scr_path)
        users_heard = {u: mh_get_user_albums(_scr_conn, u) for u in users}
        _scr_conn.close()
    else:
        users_heard = {u: set() for u in users}
    generated   = datetime.now().strftime("%Y-%m-%d %H:%M")
    decades_data: dict = {}

    # Decide which decades to process
    decade_arg = getattr(args, "scaruffi_decade", None)
    if decade_arg:
        def _norm_decade(d):
            d = d.strip()
            if len(d) == 4: d = d[2:]    # "1960" → "60"
            if d == "0":    d = "00"      # edge case
            return d.zfill(2)
        decades_to_run = [_norm_decade(d) for d in decade_arg]
    else:
        decades_to_run = list(SCARUFFI_DECADES) if not index_only else []

    # Always load all existing caches for the index, but only scrape selected decades
    for decade in SCARUFFI_DECADES:
        cache_file = out_dir / f"scaruffi_{decade}s_cache.json"

        # Decades NOT selected: just load from cache for the combined index
        if decade not in decades_to_run and not index_only:
            if cache_file.exists():
                cached = json.loads(cache_file.read_text())
                if cached:
                    enrich_path = out_dir / "scaruffi_enrich_cache.json"
                    if enrich_path.exists() and not index_only:
                        ec = json.loads(enrich_path.read_text())
                        for a in cached:
                            key = _norm(a["artist"]) + "|||" + _norm(a["title"])
                            e   = ec.get(key, {})
                            a.setdefault("desc_lfm_album",  e.get("desc_lfm_album","") or e.get("desc",""))
                            a.setdefault("desc_lfm_artist", e.get("desc_lfm_artist",""))
                            a.setdefault("desc_mb_album",   e.get("desc_mb_album",  ""))
                            a.setdefault("desc_mb_artist",  e.get("desc_mb_artist", ""))
                            a.setdefault("mbid",   e.get("mbid",   ""))
                            a.setdefault("genres", e.get("genres", []))
                    for a in cached:
                        a["heard_by"] = [u for u in users if scaruffi_check_heard(users_heard[u], a)]
                    decades_data[decade] = cached
            continue

        print(f"\n-- Scaruffi {SCARUFFI_DECADE_LABELS.get(decade, decade+'s')} --")
        cache_file = out_dir / f"scaruffi_{decade}s_cache.json"

        if index_only:
            if not cache_file.exists():
                print(f"  No cache for {decade}s, skipping")
                continue
            albums = json.loads(cache_file.read_text())
        else:
            # Force re-fetch if --decade was explicitly specified
            if decade_arg and cache_file.exists():
                cache_file.unlink()
                print(f"  🗑 Deleted cache for {decade}s (--decade flag, re-fetching)")
            albums = scaruffi_fetch_decade(decade, out_dir, debug=getattr(args,'scaruffi_debug',False))

        if not albums:
            continue

        if (lfm_key or do_genres) and not index_only:
            print(f"  Enriching {len(albums)} albums...")
            albums = scaruffi_enrich_albums(albums, out_dir, lfm_key, lfm_secret, do_genres)
        elif index_only:
            # Cargar enrich desde must_hear.db (si disponible) o JSON
            _mh_c = getattr(args, "_sca_mh_conn", None)
            if _mh_c:
                # Cargar desde must_hear.db usando la colección scaruffi
                sca_desc = mh_load_collection(_mh_c, f"scaruffi_{decade}s")
                sca_by_nk = {_norm(a["artist"]) + "|||" + _norm(a["title"]): a
                             for a in sca_desc}
                for a in albums:
                    key = _norm(a["artist"]) + "|||" + _norm(a["title"])
                    e   = sca_by_nk.get(key, {})
                    a["desc_lfm_album"]  = e.get("desc_lfm_album",  "")
                    a["desc_lfm_artist"] = e.get("desc_lfm_artist", "")
                    a["desc_mb_album"]   = e.get("desc_mb_album",   "")
                    a["desc_mb_artist"]  = e.get("desc_mb_artist",  "")
                    a["mbid"]   = e.get("mbid",   a.get("mbid",""))
                    a["genres"] = e.get("genres", [])
            else:
                enrich_path = out_dir / "scaruffi_enrich_cache.json"
                if enrich_path.exists():
                    ec = json.loads(enrich_path.read_text())
                    for a in albums:
                        key = _norm(a["artist"]) + "|||" + _norm(a["title"])
                        e   = ec.get(key, {})
                        a["desc_lfm_album"]  = e.get("desc_lfm_album","") or e.get("desc","")
                        a["desc_lfm_artist"] = e.get("desc_lfm_artist","")
                        a["desc_mb_album"]   = e.get("desc_mb_album",  "")
                        a["desc_mb_artist"]  = e.get("desc_mb_artist", "")
                        a["mbid"]   = e.get("mbid",   "")
                        a["genres"] = e.get("genres", [])

        for a in albums:
            a["heard_by"] = [u for u in users if scaruffi_check_heard(users_heard[u], a)]

        decades_data[decade] = albums

        html = render_scaruffi_decade_html(
            decade, albums, users_heard, "Scaruffi",
            list(SCARUFFI_DECADES)
        )
        out_path = out_dir / f"decade_{decade}s.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"  -> {out_path}")

    # ── Carátulas HD (--caratulas) ──
    do_caratulas = getattr(args, "caratulas", False)
    if do_caratulas and not index_only and decades_data:
        discogs_token = getattr(args, "discogs_token", "") or ""
        all_albums = [a for v in decades_data.values() for a in v]
        print(f"\n🖼  Buscando carátulas HD para {len(all_albums)} álbumes...")
        n = scaruffi_fetch_covers(all_albums, out_dir, lfm_key, discogs_token)
        print(f"  ✅ {n} carátulas actualizadas")
        # Re-render HTMLs with updated covers
        if n > 0:
            print("  Re-rendering HTMLs con carátulas HD...")
            # Persist updated covers back to decade caches
            for decade, albums in decades_data.items():
                cf = out_dir / f"scaruffi_{decade}s_cache.json"
                if cf.exists():
                    cached = json.loads(cf.read_text())
                    cover_map = {(a["artist"], a["title"]): a["cover"] for a in albums}
                    for ca in cached:
                        new_c = cover_map.get((ca["artist"], ca["title"]))
                        if new_c:
                            ca["cover"] = new_c
                    cf.write_text(json.dumps(cached, ensure_ascii=False, indent=2))
            # Re-render
            for decade, albums in decades_data.items():
                html = render_scaruffi_decade_html(
                    decade, albums, users_heard, "Scaruffi", list(SCARUFFI_DECADES)
                )
                (out_dir / f"decade_{decade}s.html").write_text(html, encoding="utf-8")
            print("  ✅ HTMLs re-renderizados")

    if not decades_data:
        print("No decade data to index")
        return

    # ── RateYourMusic URLs (--rateyourmusic) ──
    do_rym    = getattr(args, "rateyourmusic", False)
    searxng   = getattr(args, "searxng", "http://localhost:8485")
    _mh_c_sca = getattr(args, "_sca_mh_conn", None)
    rym_cache_path = out_dir / "rym_cache.json"
    if _mh_c_sca:
        # Cargar rym_urls de must_hear.db keyed por normkey para Scaruffi
        _rym_rows = _mh_c_sca.execute("""
            SELECT ar.name, al.name, al.rateyourmusic_url
            FROM albums al JOIN artists ar ON ar.id=al.artist_id
            JOIN collection_albums ca ON ca.album_id=al.id
            JOIN collections c ON c.id=ca.collection_id
            WHERE c.slug LIKE 'scaruffi_%' AND al.rateyourmusic_url IS NOT NULL AND al.rateyourmusic_url != ''
        """).fetchall()
        rym_cache = {_norm(r[0])+"|||"+_norm(r[1]): r[2] for r in _rym_rows}
        print(f"  📦 RYM desde must_hear.db: {len(rym_cache)} entradas")
    elif rym_cache_path.exists():
        rym_cache = json.loads(rym_cache_path.read_text())
        print(f"  📦 RYM caché cargado: {sum(1 for v in rym_cache.values() if v)}/{len(rym_cache)} con URL")
    else:
        rym_cache = {}
    if do_rym and not index_only:
        all_for_rym = [a for v in decades_data.values() for a in v]
        # Use a dummy cache_file path so fetch_rym_urls writes to out_dir/rym_cache.json
        class _FakePath:
            parent = out_dir
        rym_cache = fetch_rym_urls(all_for_rym, _FakePath(), searxng=searxng, key_field="normkey")
    # Inject rym URLs into album dicts
    if rym_cache:
        for decade, albums in decades_data.items():
            for a in albums:
                k = _norm(a["artist"]) + "|||" + _norm(a["title"])
                a["rym"] = rym_cache.get(k, "")
    # Re-render all decade HTMLs with rym data
    if do_rym or rym_cache:
        for decade, albums in decades_data.items():
            html = render_scaruffi_decade_html(
                decade, albums, users_heard, "Scaruffi", list(SCARUFFI_DECADES)
            )
            (out_dir / f"decade_{decade}s.html").write_text(html, encoding="utf-8")
        print("  ✅ HTMLs re-renderizados con RYM")

    (out_dir / "index.html").write_text(
        render_scaruffi_index_html(decades_data, users, generated), encoding="utf-8"
    )
    print(f"\nScaruffi index -> {out_dir / 'index.html'}")

    # Update root index
    meta_file = root_dir / ".collections_meta.json"
    collections = json.loads(meta_file.read_text()) if meta_file.exists() else []
    all_albums   = [a for v in decades_data.values() for a in v]
    total_albums = len(all_albums)
    if users and total_albums:
        user_pcts = []
        for u in users:
            heard = sum(1 for a in all_albums if u in (a.get("heard_by") or []))
            user_pcts.append(heard / total_albums * 100)
        avg_pct_scaruffi = round(sum(user_pcts) / len(user_pcts), 1)
    else:
        avg_pct_scaruffi = 0
    entry = {
        "slug":    "scaruffi",
        "name":    "Scaruffi's Best Rock (by Decade)",
        "users":   len(users),
        "total":   total_albums,
        "avg_pct": avg_pct_scaruffi,
        "updated": generated,
        "url":     "scaruffi/index.html",
    }
    # Remove combined entry AND any stale per-decade entries (scaruffi_60s etc.)
    existing = [c for c in collections
                if c["slug"] != "scaruffi" and not c["slug"].startswith("scaruffi_")]
    existing.append(entry)
    existing.sort(key=lambda c: c["name"])
    meta_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    (root_dir / "index.html").write_text(render_root_index_html(existing, generated), encoding="utf-8")
    print(f"Root index updated -> {root_dir / 'index.html'}")
    print(f"\nDone! Open: {out_dir / 'index.html'}")

def render_collection_index_html(users_data: list[dict], series_name: str, generated: str) -> str:
    cards_html = ""
    for u in users_data:
        pct  = u["pct"]
        bar_w = pct
        cards_html += f"""
        <a class="user-card" href="{u['file']}">
          <div class="uc-name">{u['user']}</div>
          <div class="uc-stats">
            <span class="uc-heard">{u['heard']}</span>
            <span class="uc-sep">/</span>
            <span class="uc-total">{u['total']}</span>
            <span class="uc-label">albums heard</span>
          </div>
          <div class="uc-bar-wrap">
            <div class="uc-bar" style="width:{bar_w}%"></div>
          </div>
          <div class="uc-pct">{pct}%</div>
        </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{series_name} — Must Hear</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<!-- Umami Analytics -->
<script
    defer
    src="https://cloud.umami.is/script.js"
    data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"
></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:     #0a0a0a;
    --surface:#111;
    --border: #1e1e1e;
    --accent: #e8ff47;
    --muted:  #555;
    --text:   #e0e0e0;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
  }}

  /* noise grain overlay */
  body::before {{
    content: '';
    position: fixed; inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
    pointer-events: none; z-index: 0; opacity: .4;
  }}

  header {{
    position: relative; z-index: 1;
    padding: 60px 60px 40px;
    border-bottom: 1px solid var(--border);
  }}
  .site-label {{
    font-family: 'DM Mono', monospace;
    font-size: .7rem;
    letter-spacing: .2em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
  }}
  h1 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(2.4rem, 6vw, 5rem);
    letter-spacing: .04em;
    line-height: .95;
    color: var(--accent);
  }}
  .header-meta {{
    font-family: 'DM Mono', monospace;
    font-size: .72rem;
    color: var(--muted);
    margin-top: 16px;
  }}
  .header-meta span {{ color: var(--text); }}

  main {{
    position: relative; z-index: 1;
    padding: 48px 60px 80px;
  }}
  .section-label {{
    font-family: 'DM Mono', monospace;
    font-size: .65rem;
    letter-spacing: .18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 24px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }}

  .users-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
  }}

  .user-card {{
    display: block;
    text-decoration: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 22px 20px 18px;
    transition: border-color .15s, transform .15s;
    position: relative;
    overflow: hidden;
  }}
  .user-card::after {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
    transform: scaleX(0);
    transform-origin: left;
    transition: transform .25s ease;
  }}
  .user-card:hover {{ border-color: #333; transform: translateY(-2px); }}
  .user-card:hover::after {{ transform: scaleX(1); }}

  .uc-name {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.5rem;
    letter-spacing: .06em;
    color: var(--text);
    margin-bottom: 10px;
  }}
  .uc-stats {{
    display: flex; align-items: baseline; gap: 4px;
    margin-bottom: 12px;
  }}
  .uc-heard  {{ font-family: 'DM Mono', monospace; font-size: 1.4rem; color: var(--accent); font-weight: 500; }}
  .uc-sep    {{ font-family: 'DM Mono', monospace; font-size: .8rem; color: var(--muted); }}
  .uc-total  {{ font-family: 'DM Mono', monospace; font-size: .8rem; color: var(--muted); }}
  .uc-label  {{ font-size: .7rem; color: var(--muted); margin-left: 4px; }}

  .uc-bar-wrap {{
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 6px;
  }}
  .uc-bar {{
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width .8s ease;
  }}
  .uc-pct {{
    font-family: 'DM Mono', monospace;
    font-size: .65rem;
    color: var(--muted);
    text-align: right;
  }}

  footer {{
    position: relative; z-index: 1;
    padding: 24px 60px;
    border-top: 1px solid var(--border);
    font-family: 'DM Mono', monospace;
    font-size: .65rem;
    color: var(--muted);
  }}

  @media (max-width: 700px) {{
    header, main, footer {{ padding-left: 20px; padding-right: 20px; }}
    header {{ padding-top: 36px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="site-label"><a href="../index.html" style="color:var(--muted);text-decoration:none;letter-spacing:.2em">← All Collections</a></div>
  <h1>{series_name}</h1>
  <div class="header-meta">
    <span>{len(users_data)}</span> users &nbsp;·&nbsp;
    <span>1,001</span> albums &nbsp;·&nbsp;
    Generated {generated}
  </div>
</header>
<main>
  <div class="section-label">Users — click to explore</div>
  <div class="users-grid">
    {cards_html}
  </div>
</main>
<footer>Data from MusicBrainz &amp; Last.fm · Cover art from Cover Art Archive</footer>
</body>
</html>
"""


def render_root_index_html(collections: list[dict], generated: str,
                            title: str = "Collections",
                            back_link: str = "") -> str:
    """Top-level index listing all music collections (reused for collection-group index too)."""
    cards_html = ""
    for c in collections:
        avg_pct  = c["avg_pct"]
        users_n  = c["users"]
        total    = c["total"]
        cards_html += f"""
      <a class="col-card" href="{c.get('url', c['slug']+'/index.html')}">
        <div class="col-name">{c['name']}</div>
        <div class="col-meta">{users_n} users &middot; {total} albums</div>
        <div class="col-bar-wrap">
          <div class="col-bar" style="width:{avg_pct:.1f}%"></div>
        </div>
        <div class="col-pct">{avg_pct:.1f}% avg completion</div>
      </a>"""

    site_label = (
        f'<div class="site-label"><a href="{back_link}" '
        f'style="color:var(--muted);text-decoration:none;letter-spacing:.2em">'
        f'&larr; All Collections</a></div>'
        if back_link else
        '<div class="site-label">Must Hear Tracker</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Must Hear — {title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<!-- Umami Analytics -->
<script
    defer
    src="https://cloud.umami.is/script.js"
    data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"
></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0a0a0a; --surface:#111; --border:#1e1e1e;
    --accent:#e8ff47; --muted:#555; --text:#e0e0e0;
  }}
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:var(--bg); color:var(--text);
    font-family:'DM Sans',sans-serif; min-height:100vh;
  }}
  body::before {{
    content:''; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.4;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
  }}
  header {{
    position:relative; z-index:1;
    padding:60px 60px 40px;
    border-bottom:1px solid var(--border);
  }}
  .site-label {{
    font-family:'DM Mono',monospace; font-size:.7rem;
    letter-spacing:.2em; text-transform:uppercase;
    color:var(--muted); margin-bottom:12px;
  }}
  h1 {{
    font-family:'Bebas Neue',sans-serif;
    font-size:clamp(2.4rem,6vw,5rem);
    letter-spacing:.04em; line-height:.95; color:var(--accent);
  }}
  .header-meta {{
    font-family:'DM Mono',monospace; font-size:.72rem;
    color:var(--muted); margin-top:16px;
  }}
  main {{ position:relative; z-index:1; padding:40px 60px 80px; }}
  .section-label {{
    font-family:'DM Mono',monospace; font-size:.65rem;
    letter-spacing:.2em; text-transform:uppercase;
    color:var(--muted); margin-bottom:20px;
  }}
  .collections-grid {{
    display:grid;
    grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
    gap:16px;
  }}
  .col-card {{
    display:block; text-decoration:none;
    background:var(--surface); border:1px solid var(--border);
    border-radius:6px; padding:26px 22px 20px;
    transition:border-color .15s, transform .15s;
    position:relative; overflow:hidden;
  }}
  .col-card::after {{
    content:''; position:absolute; top:0; left:0; right:0;
    height:3px; background:var(--accent);
    transform:scaleX(0); transform-origin:left;
    transition:transform .25s ease;
  }}
  .col-card:hover {{ border-color:#333; transform:translateY(-2px); }}
  .col-card:hover::after {{ transform:scaleX(1); }}
  .col-name {{
    font-family:'Bebas Neue',sans-serif;
    font-size:1.6rem; letter-spacing:.05em;
    color:var(--text); margin-bottom:8px; line-height:1.1;
  }}
  .col-meta {{
    font-family:'DM Mono',monospace; font-size:.65rem;
    color:var(--muted); margin-bottom:14px;
  }}
  .col-bar-wrap {{
    height:3px; background:var(--border);
    border-radius:2px; overflow:hidden; margin-bottom:6px;
  }}
  .col-bar {{
    height:100%; background:var(--accent);
    border-radius:2px; transition:width .8s ease;
  }}
  .col-pct {{
    font-family:'DM Mono',monospace; font-size:.62rem; color:var(--muted);
  }}
  footer {{
    position:relative; z-index:1;
    padding:24px 60px; border-top:1px solid var(--border);
    font-family:'DM Mono',monospace; font-size:.65rem; color:var(--muted);
  }}
  @media (max-width:700px) {{
    header,main,footer {{ padding-left:20px; padding-right:20px; }}
    header {{ padding-top:36px; }}
  }}
</style>
</head>
<body>
<header>
  {site_label}
  <h1>{title}</h1>
  <div class="header-meta">
    {len(collections)} collection{'s' if len(collections) != 1 else ''} &nbsp;&middot;&nbsp;
    Generated {generated}
  </div>
</header>
<main>
  <div class="section-label">All Lists</div>
  <div class="collections-grid">{cards_html}
  </div>
</main>
<footer>Generated {generated}</footer>
</body>
</html>
"""


def update_root_index(root_dir: Path, collection_name: str, slug: str,
                      users_index: list[dict], generated: str,
                      url: str = "") -> None:
    """Read existing root index data (if any), upsert this collection, rewrite."""
    meta_file = root_dir / ".collections_meta.json"

    # Load existing metadata
    if meta_file.exists():
        collections = json.loads(meta_file.read_text())
    else:
        collections = []

    # Compute avg completion for this collection
    avg_pct = (sum(u["pct"] for u in users_index) / len(users_index)) if users_index else 0
    total   = users_index[0]["total"] if users_index else 0

    entry = {
        "slug":    slug,
        "name":    collection_name,
        "users":   len(users_index),
        "total":   total,
        "avg_pct": round(avg_pct, 1),
        "updated": generated,
    }
    if url:
        entry["url"] = url

    # Upsert by slug
    existing = [c for c in collections if c["slug"] != slug]
    existing.append(entry)
    existing.sort(key=lambda c: c["name"])

    meta_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    # Render and write root index
    html = render_root_index_html(existing, generated)
    (root_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"📋 root index → {root_dir / 'index.html'} ({len(existing)} collections)")


def update_collection_group_index(root_dir: Path, collection_name: str,
                                   collection_slug: str, series_name: str,
                                   series_slug: str, users_index: list[dict],
                                   generated: str) -> None:
    """Upsert a series into a collection-group index (e.g. pitchfork/index.html),
    then update the root index with the group as a single entry."""
    coll_dir  = root_dir / collection_slug
    coll_dir.mkdir(parents=True, exist_ok=True)
    meta_file = coll_dir / ".series_meta.json"

    series = json.loads(meta_file.read_text()) if meta_file.exists() else []

    avg_pct = (sum(u["pct"] for u in users_index) / len(users_index)) if users_index else 0
    total   = users_index[0]["total"] if users_index else 0

    entry = {
        "slug":    series_slug,
        "name":    series_name,
        "users":   len(users_index),
        "total":   total,
        "avg_pct": round(avg_pct, 1),
        "updated": generated,
    }
    existing_series = [s for s in series if s["slug"] != series_slug]
    existing_series.append(entry)
    existing_series.sort(key=lambda s: s["name"])
    meta_file.write_text(json.dumps(existing_series, ensure_ascii=False, indent=2))

    # Render collection-group index (reuse root index template with back-link)
    html = render_root_index_html(
        existing_series, generated,
        title=collection_name,
        back_link="../index.html",
    )
    (coll_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"📋 group index → {coll_dir / 'index.html'} ({len(existing_series)} series)")

    # Update root index: represent the whole group as one entry
    group_avg   = round(sum(s["avg_pct"] for s in existing_series) / len(existing_series), 1)
    group_total = sum(s["total"] for s in existing_series)
    group_users = len(users_index)
    root_proxy  = [{"user": "_group", "pct": group_avg, "total": group_total, "heard": 0}
                   for _ in range(group_users)]
    update_root_index(
        root_dir,
        collection_name=collection_name,
        slug=collection_slug,
        users_index=root_proxy,
        generated=generated,
        url=f"{collection_slug}/index.html",
    )


# ── MAIN ──────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# MUST HEAR DB LAYER  (--must-hear-db)
# Lee álbumes/descripciones/géneros/urls de must_hear.db (esquema normalizado).
# Los scrobbles siguen en rym_lastfm.db (--scrobbles-db).
# ══════════════════════════════════════════════════════════════════════════════

def mh_get_users(mh_conn: sqlite3.Connection) -> list[str]:
    """Lista de usuarios desde must_hear.db.users."""
    rows = mh_conn.execute("SELECT username FROM users ORDER BY username").fetchall()
    return [r[0] for r in rows]


def mh_get_user_albums(scrobbles_conn: sqlite3.Connection, user: str) -> set[tuple]:
    """
    Devuelve set de (norm_artist, norm_album) escuchados por user.
    Compatible con schema old (tabla scrobbles con user TEXT) y
    new (tablas scrobbles_<user> con FKs a artists/albums).
    """
    if _scrobbles_schema(scrobbles_conn) == "new":
        tbl = _user_table_name(user)
        exists = scrobbles_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not exists:
            return set()
        rows = scrobbles_conn.execute(f"""
            SELECT ar.name, al.name
            FROM {tbl} sc
            JOIN artists ar ON ar.id = sc.artist_id
            JOIN albums  al ON al.id = sc.album_id
            WHERE sc.album_id IS NOT NULL
        """).fetchall()
    else:
        rows = scrobbles_conn.execute(
            "SELECT artist, album FROM scrobbles "
            "WHERE user=? AND album IS NOT NULL AND album != ''",
            (user,)
        ).fetchall()
    return {(_norm(r[0]), _norm(r[1])) for r in rows}


def mh_populate_user_heard(mh_conn: sqlite3.Connection,
                            scrobbles_conn: sqlite3.Connection,
                            user: str, album_ids_heard: list[tuple]):
    """
    Puebla user_heard en must_hear.db para un usuario dado.
    album_ids_heard: lista de (album_id, first_heard_ts)
    """
    row = mh_conn.execute(
        "SELECT id FROM users WHERE username=?", (user,)
    ).fetchone()
    if not row:
        mh_conn.execute(
            "INSERT OR IGNORE INTO users (username, lastfm_username, added_timestamp) VALUES (?,?,?)",
            (user, user, int(time.time()))
        )
        row = mh_conn.execute("SELECT id FROM users WHERE username=?", (user,)).fetchone()
    user_id = row[0]
    for album_id, first_ts in album_ids_heard:
        mh_conn.execute(
            "INSERT OR IGNORE INTO user_heard (user_id, album_id, first_heard_at) VALUES (?,?,?)",
            (user_id, album_id, first_ts)
        )
    mh_conn.commit()


def mh_load_collection(mh_conn: sqlite3.Connection,
                        collection_slug: str) -> list[dict]:
    """
    Carga todos los álbumes de una colección desde must_hear.db.
    Devuelve lista de dicts con los mismos campos que series_cache.json
    más todos los campos enriquecidos (desc, genres, urls...).
    """
    rows = mh_conn.execute("""
        SELECT
            al.id,
            ar.name                AS artist,
            al.name                AS title,
            al.year,
            al.release_group_mbid  AS mbid,
            ca.rank,
            am.desc_lfm_album,
            am.desc_lfm_artist,
            am.desc_mb_album,
            am.desc_mb_artist,
            al.yt_id,
            al.rateyourmusic_url   AS rym,
            al.spotify_id,
            al.spotify_url,
            al.cover_url,
            al.scaruffi_rating,
            al.scaruffi_note,
            al.wikipedia_url,
            am.wikipedia_content,
            al.aoty_user_score,
            al.aoty_critic_score,
            al.metacritic_score,
            al.label
        FROM collection_albums ca
        JOIN collections c        ON c.id  = ca.collection_id
        JOIN albums al            ON al.id = ca.album_id
        JOIN artists ar           ON ar.id = al.artist_id
        LEFT JOIN album_metadata am ON am.album_id = al.id
        WHERE c.slug = ?
        ORDER BY ca.rank ASC NULLS LAST, al.year ASC
    """, (collection_slug,)).fetchall()

    col_names = [
        "id","artist","title","year","mbid","rank",
        "desc_lfm_album","desc_lfm_artist","desc_mb_album","desc_mb_artist",
        "yt_id","rym","spotify_id","spotify_url","cover_url",
        "scaruffi_rating","scaruffi_note","wikipedia_url","wikipedia_content",
        "aoty_user_score","aoty_critic_score","metacritic_score","label",
    ]

    albums = []
    for i, row in enumerate(rows):
        rd = dict(zip(col_names, row))
        rd["number"] = rd["rank"] or (i + 1)
        # Géneros desde album_genres (JOIN genres)
        genre_rows = mh_conn.execute("""
            SELECT g.name FROM genres g
            JOIN album_genres ag ON ag.genre_id = g.id
            WHERE ag.album_id = ?
            ORDER BY ag.weight DESC
            LIMIT 6
        """, (rd["id"],)).fetchall()
        rd["genres"] = [r[0] for r in genre_rows]
        albums.append(rd)

    return albums


def mh_album_to_json(album: dict, heard: bool) -> dict:
    """
    Construye el dict JSON por álbum directamente desde must_hear.db,
    sin necesidad de los caches intermedios (desc_db, yt_cache, etc.).
    Mantiene la misma estructura de salida que album_to_json() para
    compatibilidad con los templates HTML existentes.
    """
    mbid = album.get("mbid", "")
    cover = album.get("cover_url") or (f"{CAA}/{mbid}/front-500" if mbid else "")
    return {
        "n":               album.get("number", 0),
        "title":           album.get("title", ""),
        "artist":          album.get("artist", ""),
        "year":            album.get("year"),
        "mbid":            mbid,
        "heard":           heard,
        "cover":           cover,
        "spotify_id":      album.get("spotify_id", ""),
        "spotify_url":     album.get("spotify_url", ""),
        "desc_lfm_album":  album.get("desc_lfm_album", ""),
        "desc_lfm_artist": album.get("desc_lfm_artist", ""),
        "desc_mb_album":   album.get("desc_mb_album", ""),
        "desc_mb_artist":  album.get("desc_mb_artist", ""),
        "yt_id":           album.get("yt_id", ""),
        "genres":          album.get("genres", []),
        "rym":             album.get("rym", ""),
        "scaruffi_rating":   album.get("scaruffi_rating"),
        "scaruffi_note":     album.get("scaruffi_note", ""),
        "wikipedia_url":     album.get("wikipedia_url", ""),
        "aoty_user_score":   album.get("aoty_user_score"),
        "aoty_critic_score": album.get("aoty_critic_score"),
        "metacritic_score":  album.get("metacritic_score"),
        "label":             album.get("label", ""),
    }


_ALBUM_METADATA_FIELDS = frozenset({
    "desc_lfm_album", "desc_lfm_artist",
    "desc_mb_album",  "desc_mb_artist",
    "wikipedia_content",
    "producers", "engineers", "credits",
})


def mh_fetch_covers(mh_conn: sqlite3.Connection, albums: list,
                     lfm_key: str = "", discogs_token: str = "") -> None:
    """
    Busca portadas de mayor calidad para los álbumes de una colección.

    Estrategia por prioridad:
      1. front-250 en cover_url existente → reemplaza por front-500 (sin red)
      2. CAA: sigue redirect para obtener URL real de alta resolución (necesita mbid)
      3. Last.fm album.getInfo: extralarge/mega (~300-500 px)
      4. Discogs search: cover_image (suele ser 600 px+, requiere token)

    Guarda el resultado en albums.cover_url y actualiza album en memoria.
    """
    CAA_PREFIX = "https://coverartarchive.org/release-group"
    PLACEHOLDER = "2a96cbd8b46e442fc41c2b86b821562f"  # imagen vacía Last.fm
    ts = int(time.time())

    upgraded = fetched = already_ok = 0
    total = len(albums)

    for i, album in enumerate(albums, 1):
        album_id  = album["id"]
        mbid      = album.get("mbid", "")
        title     = album.get("title", "")
        artist    = album.get("artist", "")
        current   = album.get("cover_url") or ""

        print(f"  [{i}/{total}] {artist} — {title}", end="  ")

        # ── Upgrade rápido front-250 → front-500 ──────────────────────────────
        if "front-250" in current:
            new_url = current.replace("front-250", "front-500")
            mh_conn.execute(
                "UPDATE albums SET cover_url=?, last_updated=? WHERE id=?",
                (new_url, ts, album_id)
            )
            album["cover_url"] = new_url
            upgraded += 1
            print("⬆ 250→500")
            continue

        # Si ya tiene portada externa (no archive.org), saltamos
        if current and CAA_PREFIX not in current and "archive.org" not in current:
            already_ok += 1
            print("✓")
            continue

        new_cover = ""

        # ── Estrategia 1: CAA redirect (res completa, verifica existencia) ────
        if mbid:
            try:
                req = urllib.request.Request(
                    f"{CAA_PREFIX}/{mbid}/front",
                    headers={"User-Agent": UA}
                )
                with urllib.request.urlopen(req, timeout=12) as r:
                    new_cover = r.url   # URL real tras el redirect
            except Exception:
                pass
            time.sleep(0.3)

        # ── Estrategia 2: Last.fm album.getInfo ──────────────────────────────
        if not new_cover and lfm_key:
            try:
                params = urllib.parse.urlencode({
                    "method": "album.getinfo",
                    "artist": artist, "album": title,
                    "api_key": lfm_key, "format": "json",
                    "autocorrect": 1,
                })
                req = urllib.request.Request(
                    f"https://ws.audioscrobbler.com/2.0/?{params}",
                    headers={"User-Agent": UA}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                images = data.get("album", {}).get("image", [])
                # reversed: empieza por mega/extralarge (los mayores)
                for img in reversed(images):
                    src = img.get("#text", "")
                    if src and PLACEHOLDER not in src:
                        new_cover = src
                        break
            except Exception:
                pass
            time.sleep(0.25)

        # ── Estrategia 3: Discogs search ──────────────────────────────────────
        if not new_cover and discogs_token:
            try:
                q = urllib.parse.urlencode({
                    "q": f"{artist} {title}",
                    "type": "release", "per_page": "1",
                })
                req = urllib.request.Request(
                    f"https://api.discogs.com/database/search?{q}",
                    headers={
                        "User-Agent":    UA,
                        "Authorization": f"Discogs token={discogs_token}",
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                results = data.get("results", [])
                if results:
                    img = results[0].get("cover_image") or results[0].get("thumb", "")
                    if img:
                        new_cover = img
            except Exception:
                pass
            time.sleep(0.5)

        if new_cover:
            mh_conn.execute(
                "UPDATE albums SET cover_url=?, last_updated=? WHERE id=?",
                (new_cover, ts, album_id)
            )
            album["cover_url"] = new_cover
            fetched += 1
            print("🖼")
        else:
            print("✗ sin portada")

    mh_conn.commit()
    print(f"\n  portadas: {upgraded} actualizadas 250→500 · "
          f"{fetched} nuevas · {already_ok} ya correctas")


def mh_save_fetched_data(mh_conn: sqlite3.Connection, album_id: int, fields: dict):
    """
    Persiste datos recién obtenidos en must_hear.db.
    - Campos de texto largo → album_metadata
    - Resto (urls, ids, scores…) → albums
    Solo rellena campos vacíos (COALESCE). No sobreescribe.
    """
    valid = {k: v for k, v in fields.items() if v not in (None, "", [], {})}
    if not valid:
        return
    ts = int(time.time())

    meta_fields  = {k: v for k, v in valid.items() if k in _ALBUM_METADATA_FIELDS}
    album_fields = {k: v for k, v in valid.items() if k not in _ALBUM_METADATA_FIELDS}

    if album_fields:
        set_parts, params = [], []
        for col, val in album_fields.items():
            if isinstance(val, list):
                val = json.dumps(val, ensure_ascii=False)
            set_parts.append(f"{col} = COALESCE({col}, ?)")
            params.append(val)
        set_parts.append("last_updated = ?")
        params.extend([ts, album_id])
        mh_conn.execute(
            f"UPDATE albums SET {', '.join(set_parts)} WHERE id=?",
            params
        )

    if meta_fields:
        # Garantizar que existe la fila en album_metadata
        mh_conn.execute(
            "INSERT OR IGNORE INTO album_metadata (album_id) VALUES (?)",
            (album_id,)
        )
        set_parts, params = [], []
        for col, val in meta_fields.items():
            if isinstance(val, list):
                val = json.dumps(val, ensure_ascii=False)
            set_parts.append(f"{col} = COALESCE({col}, ?)")
            params.append(val)
        params.append(album_id)
        mh_conn.execute(
            f"UPDATE album_metadata SET {', '.join(set_parts)} WHERE album_id=?",
            params
        )


def mh_save_genres(mh_conn: sqlite3.Connection, album_id: int,
                   genres: list[str], source: str = "musicbrainz"):
    """Inserta géneros nuevos en genres + album_genres para un álbum."""
    ts = int(time.time())
    for g in genres:
        g = g.lower().strip()
        if not g:
            continue
        mh_conn.execute(
            "INSERT OR IGNORE INTO genres (name, source, last_updated) VALUES (?,?,?)",
            (g, source, ts)
        )
        gid = mh_conn.execute("SELECT id FROM genres WHERE name=?", (g,)).fetchone()[0]
        mh_conn.execute(
            "INSERT OR IGNORE INTO album_genres (album_id, genre_id, weight) VALUES (?,?,?)",
            (album_id, gid, 1.0)
        )


def mh_sync_mb_collection(mh_conn: sqlite3.Connection,
                           slug: str,
                           name: str,
                           source_url: str,
                           albums: list[dict]) -> list[dict]:
    """Upsert a MusicBrainz series into must_hear.db.
    The DB has NO unique constraints on slug/name/artist, so every table
    uses SELECT-first to avoid duplicates on repeated runs.
    Returns album list with 'id' field populated from DB."""
    ts = int(time.time())

    # ── 1. Collection row ─────────────────────────────────────────────────────
    row = mh_conn.execute(
        "SELECT id FROM collections WHERE slug=?", (slug,)
    ).fetchone()
    if row:
        coll_id = row[0]
        mh_conn.execute(
            "UPDATE collections SET name=?, source_url=?, source_type=?, "
            "last_updated=? WHERE id=?",
            (name, source_url, "musicbrainz", ts, coll_id)
        )
        print(f"  📋 Colección existente '{slug}' (id={coll_id}) — actualizando")
    else:
        mh_conn.execute(
            "INSERT INTO collections "
            "(name, slug, source_url, source_type, last_updated, added_timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (name, slug, source_url, "musicbrainz", ts, ts)
        )
        coll_id = mh_conn.execute(
            "SELECT id FROM collections WHERE slug=?", (slug,)
        ).fetchone()[0]
        print(f"  📋 Colección nueva '{slug}' creada (id={coll_id})")
    mh_conn.commit()

    # ── 2. Albums ─────────────────────────────────────────────────────────────
    result = []
    for album in albums:
        artist_name = album.get("artist", "")
        title       = album.get("title", "")
        mbid        = album.get("mbid", "") or None
        year        = album.get("year")
        rank        = album.get("number", 0)

        # Artist: SELECT by name (idx_mh_artists_name), insert only if missing
        artist_row = mh_conn.execute(
            "SELECT id FROM artists WHERE name=?", (artist_name,)
        ).fetchone()
        if artist_row:
            artist_id = artist_row[0]
        else:
            mh_conn.execute(
                "INSERT INTO artists (name, added_timestamp) VALUES (?,?)",
                (artist_name, ts)
            )
            artist_id = mh_conn.execute(
                "SELECT id FROM artists WHERE name=?", (artist_name,)
            ).fetchone()[0]

        # Album: buscar por release_group_mbid primero (tiene UNIQUE constraint),
        # luego por (artist_id, name) como fallback.
        album_row = None
        if mbid:
            album_row = mh_conn.execute(
                "SELECT id FROM albums WHERE release_group_mbid=?", (mbid,)
            ).fetchone()
        if not album_row:
            album_row = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?",
                (artist_id, title)
            ).fetchone()

        if album_row:
            album_id = album_row[0]
            # Solo escribir release_group_mbid si el campo está NULL en esta fila
            # (nunca sobreescribir — evita violar el UNIQUE constraint)
            mh_conn.execute(
                "UPDATE albums SET "
                "release_group_mbid = CASE WHEN release_group_mbid IS NULL THEN ? ELSE release_group_mbid END, "
                "year               = COALESCE(year, ?), "
                "last_updated       = ? "
                "WHERE id=?",
                (mbid, year, ts, album_id)
            )
        else:
            mh_conn.execute(
                "INSERT INTO albums "
                "(artist_id, name, year, release_group_mbid, added_timestamp) "
                "VALUES (?,?,?,?,?)",
                (artist_id, title, year, mbid, ts)
            )
            album_id = mh_conn.execute(
                "SELECT id FROM albums WHERE artist_id=? AND name=?",
                (artist_id, title)
            ).fetchone()[0]

        # collection_albums: SELECT by (collection_id, album_id) — no UNIQUE constraint
        ca_row = mh_conn.execute(
            "SELECT id FROM collection_albums "
            "WHERE collection_id=? AND album_id=?",
            (coll_id, album_id)
        ).fetchone()
        if not ca_row:
            mh_conn.execute(
                "INSERT INTO collection_albums (collection_id, album_id, rank) "
                "VALUES (?,?,?)",
                (coll_id, album_id, rank)
            )

        merged = dict(album)
        merged["id"] = album_id
        result.append(merged)

    # ── 3. Update total ───────────────────────────────────────────────────────
    mh_conn.execute(
        "UPDATE collections SET total_albums=?, last_updated=? WHERE id=?",
        (len(result), ts, coll_id)
    )
    mh_conn.commit()
    print(f"  💾 DB: '{slug}' → {len(result)} álbumes guardados en must_hear.db")
    return result


# ── GLOBAL DB OPERATIONS (no specific collection target) ─────────────────────

def mh_global_fetch_lastfm(mh_conn: sqlite3.Connection,
                             api_key: str, api_secret: str,
                             album_ids: list[int] | None = None) -> None:
    """Fetch Last.fm + MusicBrainz descriptions for albums in must_hear.db
    that are missing at least one description field.
    If album_ids is given, only those albums are processed (targeted mode).
    Persiste directamente en album_metadata usando mh_save_fetched_data."""
    pylast = _try_import("pylast")
    if not pylast:
        print("  ⚠ pylast no disponible. Instala con: pip install pylast --break-system-packages")
        return

    # Álbumes con algún campo de descripción vacío
    if album_ids:
        placeholders = ",".join("?" * len(album_ids))
        rows = mh_conn.execute(f"""
            SELECT al.id, ar.name, al.name, al.release_group_mbid,
                   COALESCE(am.desc_lfm_album,  '') as dla,
                   COALESCE(am.desc_lfm_artist, '') as dlar,
                   COALESCE(am.desc_mb_album,   '') as dma,
                   COALESCE(am.desc_mb_artist,  '') as dmar
            FROM albums al
            JOIN artists ar ON ar.id = al.artist_id
            LEFT JOIN album_metadata am ON am.album_id = al.id
            WHERE al.id IN ({placeholders})
              AND (COALESCE(am.desc_lfm_album,  '') = ''
               OR  COALESCE(am.desc_lfm_artist, '') = ''
               OR  COALESCE(am.desc_mb_album,   '') = ''
               OR  COALESCE(am.desc_mb_artist,  '') = '')
            ORDER BY ar.name, al.name
        """, album_ids).fetchall()
    else:
        rows = mh_conn.execute("""
            SELECT al.id, ar.name, al.name, al.release_group_mbid,
                   COALESCE(am.desc_lfm_album,  '') as dla,
                   COALESCE(am.desc_lfm_artist, '') as dlar,
                   COALESCE(am.desc_mb_album,   '') as dma,
                   COALESCE(am.desc_mb_artist,  '') as dmar
            FROM albums al
            JOIN artists ar ON ar.id = al.artist_id
            LEFT JOIN album_metadata am ON am.album_id = al.id
            WHERE am.album_id IS NULL
               OR (COALESCE(am.desc_lfm_album,  '') = ''
              AND  COALESCE(am.desc_lfm_artist, '') = ''
              AND  COALESCE(am.desc_mb_album,   '') = ''
              AND  COALESCE(am.desc_mb_artist,  '') = '')
            ORDER BY ar.name, al.name
        """).fetchall()

    if not rows:
        print("✅ Todos los álbumes ya tienen descripciones en DB")
        return

    scope = f"{len(rows)} de {len(album_ids)} álbumes objetivo" if album_ids else f"{len(rows)} álbumes en toda la DB"
    print(f"📖 {scope} con alguna descripción vacía")

    DESC_FIELDS = ("desc_lfm_album", "desc_lfm_artist", "desc_mb_album", "desc_mb_artist")

    try:
        network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
    except Exception as e:
        print(f"  ❌ Error conectando con Last.fm: {e}")
        return

    ts      = int(time.time())
    updated = 0
    for i, (alb_id, artist, title, mbid, dla, dlar, dma, dmar) in enumerate(rows):
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}...")

        entry = {
            "desc_lfm_album":  dla,
            "desc_lfm_artist": dlar,
            "desc_mb_album":   dma,
            "desc_mb_artist":  dmar,
        }
        changed = {}

        # ── Last.fm album wiki ───────────────────────────────────────────────
        if not entry["desc_lfm_album"]:
            try:
                wiki = _clean_lfm_text(
                    network.get_album(artist, title).get_wiki_summary() or ""
                )
                if len(wiki) > 40:
                    changed["desc_lfm_album"] = wiki[:800]
            except Exception:
                pass
            time.sleep(0.25)

        # ── Last.fm artist bio ───────────────────────────────────────────────
        if not entry["desc_lfm_artist"]:
            try:
                bio = _clean_lfm_text(
                    network.get_artist(artist).get_bio_summary() or ""
                )
                if len(bio) > 40:
                    changed["desc_lfm_artist"] = bio[:800]
            except Exception:
                pass
            time.sleep(0.25)

        # ── MusicBrainz annotation — álbum ──────────────────────────────────
        if not entry["desc_mb_album"] and mbid:
            try:
                url = f"https://musicbrainz.org/ws/2/release-group/{mbid}?inc=annotation&fmt=json"
                req = urllib.request.Request(url, headers={"User-Agent": "MustHearScraper/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())
                ann = (data.get("annotation") or "").strip()
                if ann and len(ann) > 40:
                    changed["desc_mb_album"] = ann[:800]
            except Exception:
                pass
            time.sleep(0.5)

        # ── MusicBrainz annotation — artista ────────────────────────────────
        if not entry["desc_mb_artist"]:
            try:
                # Buscar MBID del artista desde MB
                q   = urllib.parse.quote(f'artist:"{artist}"')
                url = f"https://musicbrainz.org/ws/2/artist?query={q}&limit=1&fmt=json"
                req = urllib.request.Request(url, headers={"User-Agent": "MustHearScraper/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())
                artists_mb = data.get("artists", [])
                if artists_mb:
                    ambid = artists_mb[0].get("id", "")
                    if ambid:
                        url2 = f"https://musicbrainz.org/ws/2/artist/{ambid}?inc=annotation&fmt=json"
                        req2 = urllib.request.Request(url2, headers={"User-Agent": "MustHearScraper/1.0"})
                        with urllib.request.urlopen(req2, timeout=8) as r2:
                            data2 = json.loads(r2.read())
                        ann = (data2.get("annotation") or "").strip()
                        if ann and len(ann) > 40:
                            changed["desc_mb_artist"] = ann[:800]
            except Exception:
                pass
            time.sleep(0.5)

        if changed:
            mh_save_fetched_data(mh_conn, alb_id, changed)
            updated += 1
            if updated % 50 == 0:
                mh_conn.commit()

    mh_conn.commit()
    print(f"✅ {updated}/{len(rows)} álbumes con nuevas descripciones guardadas en DB")


def _is_global_mode(args) -> bool:
    """True when no specific collection target was given → operate on whole DB.
    Los flags de enriquecimiento global (--lastfm-info, --youtube, --caratulas)
    sin --series/--name/--slug explícito implican siempre modo global."""
    has_enrichment_flag = (
        getattr(args, "lastfm_info", False) or
        getattr(args, "youtube",     False) or
        getattr(args, "caratulas",   False) or
        getattr(args, "genres",      False)
    )
    has_explicit_collection = (
        getattr(args, "slug",            None) or
        getattr(args, "scaruffi_decades", False) or
        getattr(args, "scaruffi_decade",  None) or
        getattr(args, "aoty_decades",     False) or
        getattr(args, "aoty_decade_list", None) or
        getattr(args, "rym_url",          None) or
        getattr(args, "collection",       None) or
        args.series != DEFAULT_SERIES or
        args.name   != "1001 Albums You Must Hear Before You Die"
    )
    if has_enrichment_flag and not has_explicit_collection:
        return True
    return not has_explicit_collection


def mh_global_fetch_covers(mh_conn: sqlite3.Connection,
                            lfm_key: str = "", discogs_token: str = "") -> None:
    """Fetch HD covers for ALL albums in must_hear.db that are missing one."""
    PLACEHOLDER = "2a96cbd8b46e442fc41c2b86b821562f"
    rows = mh_conn.execute("""
        SELECT al.id, ar.name, al.name, al.release_group_mbid, al.cover_url
        FROM albums al JOIN artists ar ON ar.id = al.artist_id
        WHERE al.cover_url IS NULL OR al.cover_url = ''
           OR al.cover_url LIKE '%front-250%'
           OR instr(al.cover_url, ?) > 0
        ORDER BY ar.name, al.name
    """, (PLACEHOLDER,)).fetchall()
    if not rows:
        print("✅ Todos los álbumes ya tienen portada en DB")
        return
    albums = [
        {"id": r[0], "artist": r[1], "title": r[2], "mbid": r[3] or "", "cover_url": r[4] or ""}
        for r in rows
    ]
    print(f"🖼  {len(albums)} álbumes sin portada completa en toda la DB")
    mh_fetch_covers(mh_conn, albums, lfm_key=lfm_key, discogs_token=discogs_token)


def mh_global_fetch_youtube(mh_conn: sqlite3.Connection) -> None:
    """Fetch YouTube IDs for ALL albums in must_hear.db that are missing one."""
    rows = mh_conn.execute("""
        SELECT al.id, ar.name, al.name
        FROM albums al JOIN artists ar ON ar.id = al.artist_id
        WHERE al.yt_id IS NULL OR al.yt_id = ''
        ORDER BY ar.name, al.name
    """).fetchall()
    if not rows:
        print("✅ Todos los álbumes ya tienen YouTube ID en DB")
        return
    print(f"🎬 {len(rows)} álbumes sin YouTube en toda la DB (yt-dlp)...")
    ts    = int(time.time())
    found = 0
    for i, (alb_id, artist, title) in enumerate(rows):
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}...")
        yt_id = _yt_search(f"{artist} {title} full album")
        if yt_id:
            mh_conn.execute(
                "UPDATE albums SET yt_id=?, last_updated=? WHERE id=?", (yt_id, ts, alb_id)
            )
            found += 1
        time.sleep(0.5)
    mh_conn.commit()
    print(f"✅ {found}/{len(rows)} YouTube IDs nuevos guardados en DB")


def mh_global_fetch_genres(mh_conn: sqlite3.Connection) -> None:
    """Fetch MusicBrainz genres for albums that have NO entry in album_genres."""
    rows = mh_conn.execute("""
        SELECT al.id, ar.name, al.name, al.release_group_mbid
        FROM albums al
        JOIN artists ar ON ar.id = al.artist_id
        LEFT JOIN album_genres ag ON ag.album_id = al.id
        WHERE ag.album_id IS NULL
          AND al.release_group_mbid IS NOT NULL AND al.release_group_mbid != ''
        ORDER BY ar.name, al.name
    """).fetchall()

    if not rows:
        print("✅ Todos los álbumes con MBID ya tienen géneros en DB")
        return

    print(f"🎸 {len(rows)} álbumes sin géneros en toda la DB — consultando MusicBrainz...")
    found  = 0
    skipped = 0
    for i, (alb_id, artist, title, mbid) in enumerate(rows):
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}...")
        try:
            url = f"https://musicbrainz.org/ws/2/release-group/{mbid}?inc=genres&fmt=json"
            req = urllib.request.Request(url, headers={
                "User-Agent": "MustHearAlbums/1.0 (https://github.com/musthear)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            genres_raw = [
                (g["name"].lower(), g.get("count", 1))
                for g in data.get("genres", [])
                if g["name"].lower() not in GENRE_BLACKLIST and len(g["name"]) > 2
            ]
            genres_raw.sort(key=lambda x: x[1], reverse=True)
            genres = [g for g, _ in genres_raw[:6]]
            if genres:
                mh_save_genres(mh_conn, alb_id, genres, source="musicbrainz")
                found += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
        time.sleep(1.1)  # MB rate limit

    mh_conn.commit()
    print(f"✅ {found}/{len(rows)} álbumes con géneros nuevos guardados ({skipped} sin géneros en MB)")


def _discover_group_slugs(root_dir: Path) -> dict:
    """Scan root_dir for .series_meta.json files to map series_slug → group_slug."""
    groups = {}
    for meta_file in root_dir.glob("*/.series_meta.json"):
        group_slug = meta_file.parent.name
        for s in json.loads(meta_file.read_text()):
            groups[s["slug"]] = group_slug
    return groups


def _regen_one_collection(mh_conn, scrobbles_conn, root_dir: Path,
                           slug: str, name: str, out_dir: Path,
                           users: list, generated: str,
                           collection_slug: str = None,
                           collection_name: str = None,
                           update_db: bool = True) -> None:
    """Regenerate HTML pages for one MusicBrainz-series collection using DB data."""
    albums = mh_load_collection(mh_conn, slug)
    if not albums:
        print(f"  ⚠ '{slug}' vacía, saltando")
        return
    print(f"  📦 {len(albums)} álbumes")
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)

    users_index = []
    for user in users:
        user_scrobbles = mh_get_user_albums(scrobbles_conn, user) if scrobbles_conn else set()
        albums_data    = []
        heard_ids      = []
        for album in albums:
            heard = check_heard(user_scrobbles, album)
            jdata = mh_album_to_json(album, heard)
            if heard:
                heard_ids.append((album["id"], 0))
            albums_data.append(jdata)

        heard_count = sum(1 for a in albums_data if a["heard"])
        pct         = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0
        safe_user   = re.sub(r"[^a-z0-9]", "_", user.lower())
        json_fname  = f"{safe_user}.json"
        fname       = f"user_{safe_user}.html"

        (data_dir / json_fname).write_text(
            json.dumps(albums_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        (out_dir / fname).write_text(
            render_user_html(user, albums_data, name, data_file=f"data/{json_fname}"),
            encoding="utf-8"
        )
        if heard_ids and update_db:
            mh_populate_user_heard(mh_conn, scrobbles_conn, user, heard_ids)
        users_index.append({
            "user": user, "file": fname,
            "heard": heard_count, "total": len(albums_data), "pct": pct,
        })
        print(f"   {user}: {heard_count}/{len(albums_data)} ({pct}%)")

    users_index.sort(key=lambda u: u["pct"], reverse=True)
    (out_dir / "index.html").write_text(
        render_collection_index_html(users_index, name, generated), encoding="utf-8"
    )
    print(f"  📋 {out_dir / 'index.html'}")

    if collection_slug:
        update_collection_group_index(
            root_dir, collection_name, collection_slug,
            name, slug, users_index, generated,
        )
    else:
        update_root_index(root_dir, name, slug, users_index, generated)


def global_index_only(args, root_dir: Path, mh_conn, scrobbles_conn) -> None:
    """Regenerate HTML pages for ALL known collections (scaruffi, aoty, MB series)."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    users = getattr(args, "users", None) or (mh_get_users(mh_conn) if mh_conn else [])
    if not users:
        print("❌ No hay usuarios en la DB")
        return
    print(f"👥 {len(users)} usuarios: {', '.join(users)}")

    # ── Scaruffi ──────────────────────────────────────────────────────────────
    if (root_dir / "scaruffi").exists():
        print("\n── Scaruffi ──────────────────────────────────────────────────")
        orig_sca = getattr(args, "scaruffi_decades", False)
        orig_idx = args.index_only
        args.scaruffi_decades = True
        args.index_only       = True
        if mh_conn:
            args._sca_mh_conn = mh_conn
        run_scaruffi(args, root_dir)
        args.scaruffi_decades = orig_sca
        args.index_only       = orig_idx

    # ── AOTY ──────────────────────────────────────────────────────────────────
    if (root_dir / "aoty").exists():
        print("\n── AOTY ──────────────────────────────────────────────────────")
        try:
            from tools.must_hear.aoty_must_hear import run_aoty
            args.aoty_decades  = None   # None = all available from cache/DB
            args.force_scrape  = False
            args.scrobbles_db  = getattr(args, "scrobbles_db", None) or getattr(args, "db", None)
            if mh_conn:
                args._aoty_mh_conn = mh_conn
            run_aoty(args, root_dir)
            args.aoty_decades = False
        except Exception as e:
            print(f"  ⚠ AOTY error: {e}")

    # ── MusicBrainz series (from must_hear.db) ────────────────────────────────
    if not mh_conn:
        print("⚠ Sin --must-hear-db: no se pueden regenerar colecciones MB")
        return

    group_map   = _discover_group_slugs(root_dir)
    group_names = {}
    root_meta   = root_dir / ".collections_meta.json"
    if root_meta.exists():
        for c in json.loads(root_meta.read_text()):
            group_names[c["slug"]] = c["name"]

    skip = {"scaruffi"}
    rows = mh_conn.execute("SELECT slug, name FROM collections ORDER BY name").fetchall()
    mb_rows = [(s, n) for s, n in rows
               if s not in skip and not s.startswith("aoty")
               and not s.startswith("scaruffi_")]

    for slug, name in mb_rows:
        print(f"\n── {name} ({slug}) ──────────────────────────────────────────")
        g_slug = group_map.get(slug)
        if g_slug:
            out_dir = root_dir / g_slug / slug
            g_name  = group_names.get(g_slug, g_slug.replace("_", " ").title())
        else:
            out_dir = root_dir / slug
            g_slug  = None
            g_name  = None
        _regen_one_collection(
            mh_conn, scrobbles_conn, root_dir,
            slug, name, out_dir, users, generated,
            collection_slug=g_slug, collection_name=g_name,
            update_db=False,
        )

    print(f"\n✅ Global index-only done → {root_dir / 'index.html'}")


def main():
    parser = argparse.ArgumentParser(description="1001 Albums Must Hear — HTML Generator")
    parser.add_argument("--must-hear-db", dest="must_hear_db", default=None,
                        help="Ruta a must_hear.db (esquema normalizado: albums, artists, genres...)")
    parser.add_argument("--scrobbles-db", dest="scrobbles_db", default=None,
                        help="Ruta a rym_lastfm.db (scrobbles para calcular heard). "
                             "Si no se indica, se usa --must-hear-db para usuarios y scrobbles.")
    # Compatibilidad: --db sigue funcionando como alias de --scrobbles-db
    parser.add_argument("--db", dest="db", default=None,
                        help="[legacy] Alias de --scrobbles-db para compatibilidad")
    parser.add_argument("--out",    default="docs/must_hear",
                        help="Directorio raíz de salida (contiene el index superior)")
    parser.add_argument("--series", default=DEFAULT_SERIES, help="URL de la serie en MusicBrainz")
    parser.add_argument("--name",   default="1001 Albums You Must Hear Before You Die",
                        help="Nombre de la serie (usado en títulos y en el index superior)")
    parser.add_argument("--collection", default=None,
                        help="Nombre del grupo/colección que agrupa varias series "
                             "(ej: 'pitchfork'). Crea docs/must_hear/<collection>/<serie>/")
    parser.add_argument("--slug",   default=None,
                        help="Nombre del subdirectorio para esta colección (auto si no se indica)")
    parser.add_argument("--cache",  default=None,
                        help="Caché local del scraping (por defecto <out>/<slug>/series_cache.json)")
    parser.add_argument("--users",       nargs="*", help="Usuarios específicos (por defecto todos)")
    parser.add_argument("--force-scrape", action="store_true",
                        help="Re-scrapear la fuente aunque haya caché (para cuando la colección fue actualizada)")
    # ── Fuentes de descripción (opcionales, combinables) ──
    parser.add_argument("--1001-albums", dest="gen_1001", action="store_true",
                        help="Scrape 1001albumsgenerator.com para descripciones y Spotify IDs")

    parser.add_argument("--lastfm-api-key",        dest="lastfm_api_key",        default=None,
                        help="Last.fm API key (para wiki de álbumes/artistas)")
    parser.add_argument("--lastfm-api-secret",     dest="lastfm_api_secret",     default=None,
                        help="Last.fm API secret")
    parser.add_argument("--lastfm-info",  dest="lastfm_info", action="store_true",
                        help="Fetch descripciones Last.fm + MusicBrainz para álbumes sin ella. "
                             "Credenciales en orden: --lastfm-api-key/secret → env "
                             "LASTFM_API_KEY/SECRET → SOPS (.encrypted.env). "
                             "Requiere --must-hear-db.")
    parser.add_argument("--youtube",      action="store_true",
                        help="Pre-fetch YouTube video IDs for all albums (saved in youtube_cache.json)")
    parser.add_argument("--rateyourmusic", dest="rateyourmusic", action="store_true",
                        help="Pre-fetch RateYourMusic URLs via SearXNG (saved in rym_cache.json)")
    parser.add_argument("--searxng",      dest="searxng", default="http://localhost:8485",
                        help="URL base de la instancia SearXNG con JSON habilitado (default: http://localhost:8485)")
    parser.add_argument("--genres",       action="store_true",
                        help="Pre-fetch géneros desde MusicBrainz (guardado en genres_mb_cache.json)")
    parser.add_argument("--audit",        action="store_true",
                        help="Mostrar álbumes sin descripción / sin YouTube y salir")
    parser.add_argument("--index-only",   action="store_true",
                        help="Solo regenerar HTMLs y ambos índices desde caché existente, sin scrapear ni APIs")
    parser.add_argument("--scaruffi-decades", dest="scaruffi_decades", action="store_true",
                        help="Scrapear decadas de Scaruffi (scaruffiplaylists.netlify.app)")
    parser.add_argument("--decade", dest="scaruffi_decade", nargs="+", metavar="DECADE",
                        help="Décadas a (re)scrapear: 60 70 80 90 00 10  (borra caché y re-fetcha)")
    parser.add_argument("--caratulas", dest="caratulas", action="store_true",
                        help="Buscar carátulas HD para álbumes Scaruffi (CAA → Last.fm → Discogs)")
    parser.add_argument("--discogs-token", dest="discogs_token", default="",
                        help="Token Discogs para carátulas HD (opcional, mejora resultados)")
    parser.add_argument("--scaruffi-debug",   dest="scaruffi_debug",   action="store_true",
                        help="Guardar HTML/Markdown crudo de Scaruffi para depurar el parser")
    parser.add_argument("--aoty-decades", dest="aoty_decades", action="store_true",
                        help="Scrapear décadas de AOTY (albumoftheyear.org/must-hear/YYYYs/)")
    parser.add_argument("--aoty-decade", dest="aoty_decade_list", nargs="+", metavar="DECADE",
                        help="Décadas AOTY específicas a (re)scrapear: 1950s 1960s ... 2020s")
    parser.add_argument("--aoty-force", dest="aoty_force_scrape", action="store_true",
                        help="Re-scrapear AOTY aunque haya caché")
    parser.add_argument("--rym-list", dest="rym_url", default=None, metavar="URL",
                        help="URL de lista RateYourMusic a scrapear (abre navegador visible "
                             "para pasar Cloudflare; estado guardado en ~/.rym_playwright_state/)")
    args = parser.parse_args()

    root_dir = Path(args.out)
    root_dir.mkdir(parents=True, exist_ok=True)

    # ── Conexiones a bases de datos ──────────────────────────────────────────
    # --db es alias legacy de --scrobbles-db
    scrobbles_db_path = args.scrobbles_db or args.db
    mh_db_path        = args.must_hear_db

    mh_conn         = None
    scrobbles_conn  = None

    if mh_db_path:
        p = Path(mh_db_path)
        if not p.exists():
            print(f"❌ --must-hear-db no existe: {p}", file=__import__("sys").stderr)
            return
        mh_conn = sqlite3.connect(str(p))
        mh_conn.execute("PRAGMA journal_mode=WAL")
        mh_conn.execute("PRAGMA synchronous=NORMAL")
        print(f"🗄  must_hear.db: {p}")

    if scrobbles_db_path:
        p = Path(scrobbles_db_path)
        if not p.exists():
            print(f"❌ --scrobbles-db no existe: {p}", file=__import__("sys").stderr)
            return
        scrobbles_conn = sqlite3.connect(str(p))
        scrobbles_conn.execute("PRAGMA query_only=ON")
        print(f"🗄  scrobbles.db: {p}")

    # ── Global mode: no specific collection target ────────────────────────────
    if mh_conn and _is_global_mode(args):
        if args.index_only:
            global_index_only(args, root_dir, mh_conn, scrobbles_conn)
            if mh_conn: mh_conn.close()
            if scrobbles_conn: scrobbles_conn.close()
            return
        do_covers  = getattr(args, "caratulas",   False)
        do_youtube = getattr(args, "youtube",     False)
        do_lastfm  = getattr(args, "lastfm_info", False)
        do_genres  = getattr(args, "genres",      False)
        if do_covers or do_youtube or do_lastfm or do_genres:
            if do_covers:
                mh_global_fetch_covers(
                    mh_conn,
                    lfm_key=getattr(args, "lastfm_api_key", "") or "",
                    discogs_token=getattr(args, "discogs_token", "") or "",
                )
            if do_youtube:
                mh_global_fetch_youtube(mh_conn)
            if do_genres:
                mh_global_fetch_genres(mh_conn)
            if do_lastfm:
                lfm_key, lfm_secret = _resolve_lastfm_credentials(args)
                if not lfm_key:
                    print("❌ --lastfm-info: no se encontraron credenciales.\n"
                          "   Usa --lastfm-api-key/secret, env LASTFM_API_KEY/SECRET, "
                          "o .encrypted.env con SOPS.",
                          file=__import__("sys").stderr)
                else:
                    print(f"\n📖 Last.fm + MusicBrainz descripciones (global DB)")
                    mh_global_fetch_lastfm(mh_conn, lfm_key, lfm_secret)
            if mh_conn: mh_conn.close()
            if scrobbles_conn: scrobbles_conn.close()
            return

    # Scaruffi mode: fully separate flow
    if getattr(args, "scaruffi_decades", False):
        if mh_conn:
            args._sca_mh_conn = mh_conn
        run_scaruffi(args, root_dir)
        if mh_conn: mh_conn.close()
        if scrobbles_conn: scrobbles_conn.close()
        return

    # AOTY mode: fully separate flow
    if getattr(args, "aoty_decades", False) or getattr(args, "aoty_decade_list", None):
        from tools.must_hear.aoty_must_hear import run_aoty
        args.scrobbles_db   = scrobbles_db_path
        args.aoty_decades   = getattr(args, "aoty_decade_list", None)
        args.force_scrape   = getattr(args, "aoty_force_scrape", False)
        if mh_conn:
            args._aoty_mh_conn = mh_conn
        # Resolve Last.fm credentials (for description fetch + covers)
        if not getattr(args, "lastfm_api_key", None):
            _k, _s = _resolve_lastfm_credentials(args)
            if _k:
                args.lastfm_api_key    = _k
                args.lastfm_api_secret = _s
        run_aoty(args, root_dir)
        if mh_conn: mh_conn.close()
        if scrobbles_conn: scrobbles_conn.close()
        return

    # RateYourMusic list mode: fully separate flow
    if getattr(args, "rym_url", None):
        from tools.must_hear.rym_must_hear import run_rym
        args.scrobbles_db = scrobbles_db_path
        if mh_conn:
            args._rym_mh_conn = mh_conn
        run_rym(args, root_dir)
        if mh_conn: mh_conn.close()
        if scrobbles_conn: scrobbles_conn.close()
        return

    # Image OCR mode: --series points to an image file (jpg/png/etc.)
    _img_exts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
    if any(args.series.lower().split("?")[0].endswith(ext) for ext in _img_exts):
        from tools.must_hear.fourchan import run_4chan
        args.scrobbles_db = scrobbles_db_path
        if mh_conn:
            args._4chan_mh_conn = mh_conn
        run_4chan(args, root_dir)
        if mh_conn: mh_conn.close()
        if scrobbles_conn: scrobbles_conn.close()
        return

    # ── Slug y directorio de salida ──────────────────────────────────────────
    if args.slug:
        slug = args.slug
    else:
        slug = re.sub(r"[^a-z0-9]+", "_", args.name.lower()).strip("_")
        slug = re.sub(r"_+", "_", slug)

    # --collection groups multiple series under a common subdirectory
    collection_name = getattr(args, "collection", None)
    if collection_name:
        collection_slug = re.sub(r"[^a-z0-9]+", "_", collection_name.lower()).strip("_")
        collection_slug = re.sub(r"_+", "_", collection_slug)
        out_dir = root_dir / collection_slug / slug
    else:
        collection_slug = None
        out_dir = root_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = Path(args.cache) if args.cache else out_dir / "series_cache.json"

    # ── 1. Lista de álbumes ──────────────────────────────────────────────────
    albums_from_db = False
    if mh_conn:
        # Modo must_hear.db: cargar directamente de la BD
        albums = mh_load_collection(mh_conn, slug)
        if albums and not args.force_scrape:
            albums_from_db = True
            print(f"\n📦 {len(albums)} álbumes desde must_hear.db (colección '{slug}')")
        else:
            if args.force_scrape:
                print(f"🔄 --force-scrape: re-scrapeando '{slug}' desde MusicBrainz...")
            else:
                print(f"ℹ  Colección '{slug}' no encontrada en must_hear.db, scrapeando desde MusicBrainz...")
            albums = fetch_series(args.series, cache_path, force=args.force_scrape)
            print(f"\n🎵 {len(albums)} álbumes en la serie")
    else:
        albums = fetch_series(args.series, cache_path, force=args.force_scrape)
        print(f"\n🎵 {len(albums)} álbumes en la serie")

    # ── 1b. Si tenemos must_hear.db pero la colección es nueva, persistirla ahora ─
    if mh_conn and not albums_from_db and albums:
        print(f"\n💾 Persistiendo colección '{slug}' en must_hear.db...")
        albums = mh_sync_mb_collection(
            mh_conn, slug, args.name, args.series, albums
        )
        albums_from_db = True

    # ── 1c. Descripciones e info enriquecida (solo si NO usamos must_hear.db) ─
    # Con must_hear.db ya vienen incluidas en mh_load_collection()
    if not albums_from_db:
        if args.index_only:
            desc_db = {}
            for fname in ("descriptions_lastfm_cache.json", "descriptions_1001_cache.json"):
                p = cache_path.parent / fname
                if p.exists():
                    data = json.loads(p.read_text())
                    for k, v in data.items():
                        v = _migrate_desc_entry(v)
                        if k not in desc_db:
                            desc_db[k] = v
                        else:
                            for field in ("desc_lfm_album","desc_lfm_artist","desc_mb_album","desc_mb_artist","spotify_id"):
                                if v.get(field) and not desc_db[k].get(field):
                                    desc_db[k][field] = v[field]
                    print(f"  📦 Desc cargado desde {fname}: {len(data)} entradas")
        else:
            desc_db = fetch_album_info(albums, cache_path, args)

        yt_cache_path = cache_path.parent / "youtube_cache.json"
        yt_cache = json.loads(yt_cache_path.read_text()) if yt_cache_path.exists() else {}
        if yt_cache:
            print(f"  📦 YouTube caché: {sum(1 for v in yt_cache.values() if v)}/{len(yt_cache)} con vídeo")
        if args.youtube and not args.index_only:
            print("\n🎬 YouTube pre-fetch")
            yt_cache = fetch_youtube_ids(albums, cache_path)

        genre_cache_path = cache_path.parent / "genres_mb_cache.json"
        genre_cache = json.loads(genre_cache_path.read_text()) if genre_cache_path.exists() else {}
        if genre_cache:
            print(f"  📦 Géneros: {sum(1 for v in genre_cache.values() if v)}/{len(genre_cache)} con géneros")
        if args.genres and not args.index_only:
            print("\n🎸 MusicBrainz géneros pre-fetch")
            genre_cache = fetch_genres_musicbrainz(albums, cache_path)

        rym_cache_path = cache_path.parent / "rym_cache.json"
        rym_cache = json.loads(rym_cache_path.read_text()) if rym_cache_path.exists() else {}
        if rym_cache:
            print(f"  📦 RYM: {sum(1 for v in rym_cache.values() if v)}/{len(rym_cache)} con URL")
        if args.rateyourmusic and not args.index_only:
            print("\n🎵 RateYourMusic pre-fetch")
            rym_cache = fetch_rym_urls(albums, cache_path, searxng=args.searxng, key_field="mbid")
    else:
        # Con must_hear.db: si se pasan flags de fetch, enriquecer y persistir
        if args.youtube and not args.index_only:
            print("\n🎬 YouTube pre-fetch")
            # Construir lista compatible con fetch_youtube_ids
            yt_input = [{"artist": a["artist"], "title": a["title"],
                         "mbid": a["mbid"]} for a in albums]
            yt_result = fetch_youtube_ids(yt_input, cache_path)
            for album in albums:
                yt_id = yt_result.get(album["mbid"], "")
                if yt_id:
                    album["yt_id"] = yt_id
                    mh_save_fetched_data(mh_conn, album["id"], {"yt_id": yt_id})
            mh_conn.commit()

        if args.genres and not args.index_only:
            print("\n🎸 MusicBrainz géneros pre-fetch")
            genre_input = [{"artist": a["artist"], "title": a["title"],
                            "mbid": a["mbid"]} for a in albums]
            genre_result = fetch_genres_musicbrainz(genre_input, cache_path)
            for album in albums:
                genres = genre_result.get(album["mbid"], [])
                if genres:
                    album["genres"] = genres
                    mh_save_genres(mh_conn, album["id"], genres, "musicbrainz")
            mh_conn.commit()

        if args.rateyourmusic and not args.index_only:
            print("\n🎵 RateYourMusic pre-fetch")
            rym_input = [{"artist": a["artist"], "title": a["title"],
                          "mbid": a["mbid"]} for a in albums]
            rym_result = fetch_rym_urls(rym_input, cache_path,
                                        searxng=args.searxng, key_field="mbid")
            for album in albums:
                rym_url = rym_result.get(album["mbid"], "")
                if rym_url:
                    album["rym"] = rym_url
                    mh_save_fetched_data(mh_conn, album["id"],
                                         {"rateyourmusic_url": rym_url})
            mh_conn.commit()

        if getattr(args, "caratulas", False) and not args.index_only:
            print("\n🖼  Portadas HD (CAA → Last.fm → Discogs)")
            mh_fetch_covers(
                mh_conn, albums,
                lfm_key=getattr(args, "lastfm_api_key", "") or "",
                discogs_token=getattr(args, "discogs_token", "") or "",
            )

        if args.lastfm_api_key and not args.index_only:
            print("\n📖 Last.fm / MusicBrainz descripciones pre-fetch")
            desc_input = [{"artist": a["artist"], "title": a["title"],
                           "mbid": a["mbid"]} for a in albums]
            fresh = fetch_album_info_lastfm(desc_input, cache_path,
                                             args.lastfm_api_key,
                                             args.lastfm_api_secret or "",
                                             fetch_mb=True)
            for album in albums:
                nk = _norm(album["artist"]) + "|||" + _norm(album["title"])
                v  = fresh.get(nk, {})
                for field in ("desc_lfm_album","desc_lfm_artist",
                              "desc_mb_album","desc_mb_artist"):
                    if v.get(field) and not album.get(field):
                        album[field] = v[field]
                        mh_save_fetched_data(mh_conn, album["id"],
                                             {field: v[field]})
            mh_conn.commit()

    # ── Audit mode ───────────────────────────────────────────────────────────
    if args.audit:
        print("\n🔍 AUDIT — álbumes con datos incompletos:")
        no_desc = [a for a in albums if not a.get("desc_lfm_album")]
        no_yt   = [a for a in albums if not a.get("yt_id")]
        for section, items in [
            (f"Sin descripción ({len(no_desc)})", no_desc),
            (f"Sin YouTube ({len(no_yt)})", no_yt),
        ]:
            print(f"\n{'─'*50}\n{section}:")
            for a in items[:20]:
                print(f"  #{a.get('number',0):4d}  {a['artist']} — {a['title']}")
            if len(items) > 20:
                print(f"  ... y {len(items)-20} más")
        if mh_conn: mh_conn.close()
        if scrobbles_conn: scrobbles_conn.close()
        return

    # ── 2. Usuarios ───────────────────────────────────────────────────────────
    if mh_conn:
        users = args.users or mh_get_users(mh_conn)
    elif scrobbles_conn:
        users = args.users or _scrobbles_get_users(scrobbles_conn)
    else:
        users = args.users or []
    print(f"👥 {len(users)} usuarios: {', '.join(users)}")

    users_index = []
    heard_album_ids_by_user: dict[str, list] = {}  # para poblar user_heard

    # ── 3. Por cada usuario ───────────────────────────────────────────────────
    for user in users:
        print(f"\n── {user} ──")

        # Obtener scrobbles del usuario
        if scrobbles_conn:
            user_scrobbles = mh_get_user_albums(scrobbles_conn, user)
        else:
            user_scrobbles = set()
        print(f"   {len(user_scrobbles)} scrobbles únicos")

        albums_data = []
        heard_ids   = []

        for album in albums:
            if albums_from_db:
                heard = check_heard(user_scrobbles, album)
                jdata = mh_album_to_json(album, heard)
                if heard:
                    heard_ids.append((album["id"], 0))
            else:
                heard = check_heard(user_scrobbles, album)
                jdata = album_to_json(album, heard, desc_db, yt_cache,
                                      genre_cache, rym_cache)
            albums_data.append(jdata)

        heard_count = sum(1 for a in albums_data if a["heard"])
        pct = round(heard_count / len(albums_data) * 100, 1) if albums_data else 0
        print(f"   ✅ {heard_count}/{len(albums_data)} escuchados ({pct}%)")

        # Poblar user_heard en must_hear.db
        if mh_conn and heard_ids and not args.index_only:
            mh_populate_user_heard(mh_conn, scrobbles_conn, user, heard_ids)

        # Guardar JSON por usuario
        safe_user = re.sub(r"[^a-z0-9]", "_", user.lower())
        data_dir  = out_dir / "data"
        data_dir.mkdir(exist_ok=True)
        json_fname = f"{safe_user}.json"
        (data_dir / json_fname).write_text(
            json.dumps(albums_data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8"
        )

        fname    = f"user_{safe_user}.html"
        data_rel = f"data/{json_fname}"
        html     = render_user_html(user, albums_data, args.name, data_file=data_rel)
        (out_dir / fname).write_text(html, encoding="utf-8")
        print(f"   💾 {out_dir / fname}  +  {data_dir / json_fname}")

        users_index.append({
            "user":  user,
            "file":  fname,
            "heard": heard_count,
            "total": len(albums_data),
            "pct":   pct,
        })

    # ── 4. Collection index ───────────────────────────────────────────────────
    users_index.sort(key=lambda u: u["pct"], reverse=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    index_html = render_collection_index_html(users_index, args.name, generated)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"\n📋 collection index → {out_dir / 'index.html'}")

    # ── 5. Root index ─────────────────────────────────────────────────────────
    if collection_slug:
        update_collection_group_index(
            root_dir, collection_name, collection_slug,
            args.name, slug, users_index, generated,
        )
        print(f"\n🎉 Listo! Abre: {root_dir / collection_slug / 'index.html'}")
    else:
        update_root_index(root_dir, args.name, slug, users_index, generated)
        print(f"\n🎉 Listo! Abre: {root_dir / 'index.html'}")

    if mh_conn: mh_conn.close()
    if scrobbles_conn: scrobbles_conn.close()

if __name__ == "__main__":
    main()

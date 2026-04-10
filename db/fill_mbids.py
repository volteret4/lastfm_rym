import sqlite3
import ssl
import requests
import time
import os
import argparse
import itertools
from concurrent.futures import ThreadPoolExecutor # [NUEVO] Para multihilo
from threading import Lock                     # [NUEVO] Para evitar conflictos en DB
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

MAIN_DB  = "db/must_hear_rym_new.db"
CACHE_DB = "db/lasfm_cache_rym_new_normalized.db"
RATE_LIMIT = 1.1
db_lock = Lock() # Bloqueo global para escrituras en SQLite

HEADERS = {
    "User-Agent": "mbid-filler/1.1 (frodobolson@disroot.org)"
}

class _TLS12Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)

_retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
_session = requests.Session()
_session.mount("https://", _TLS12Adapter(max_retries=_retry))

def normalize(s):
    if not s: return ""
    s = s.lower().strip()
    if s.startswith("the "): s = s[4:]
    return s

def get_from_cache(cache_conn, artist, album):
    try:
        row = cache_conn.execute("""
            SELECT a.mbid, a.release_group_mbid
            FROM albums a
            JOIN artists ar ON a.artist_id = ar.id
            WHERE LOWER(ar.name) = ? AND LOWER(a.name) = ?
              AND (a.mbid IS NOT NULL OR a.release_group_mbid IS NOT NULL)
            LIMIT 1
        """, (normalize(artist), normalize(album))).fetchone()
        return row
    except: return None

def search_musicbrainz(artist, album, proxy=None):
    query = f'artist:"{artist}" AND release:"{album}"'
    url = "https://musicbrainz.org/ws/2/release/"
    params = {"query": query, "fmt": "json", "limit": 1}
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        r = _session.get(url, headers=HEADERS, params=params, timeout=20, proxies=proxies)
        if r.status_code == 200:
            data = r.json()
            if data.get("releases"):
                rel = data["releases"][0]
                return rel.get("id"), rel.get("release-group", {}).get("id")
        return None
    except: return None

def get_rg_from_mbid(mbid, proxy=None):
    url = f"https://musicbrainz.org/ws/2/release/{mbid}"
    params = {"inc": "release-groups", "fmt": "json"}
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        r = _session.get(url, headers=HEADERS, params=params, timeout=20, proxies=proxies)
        return r.json().get("release-group", {}).get("id") if r.status_code == 200 else None
    except: return None

def process_album(album_data, proxy, cache_path):
    """Función que ejecuta cada hilo"""
    album_id, album_name, artist_name = album_data

    # Necesitamos una conexión por hilo para evitar errores de SQLite
    main_conn = sqlite3.connect(MAIN_DB, timeout=30)
    cache_conn = sqlite3.connect(cache_path) if cache_path else None

    release_mbid = rg_mbid = None

    try:
        # 0. Check si el álbum aún existe (por si fue borrado en un merge previo)
        with db_lock:
            exists = main_conn.execute("SELECT mbid FROM albums WHERE id=?", (album_id,)).fetchone()
        if not exists: return "skipped"
        existing_mbid = exists[0]

        # 1. MBID directo
        if existing_mbid:
            rg_mbid = get_rg_from_mbid(existing_mbid, proxy)

        # 2. Cache
        if not rg_mbid and cache_conn:
            cached = get_from_cache(cache_conn, artist_name, album_name)
            if cached: release_mbid, rg_mbid = cached

        # 3. API (aquí es donde los hilos brillan)
        if not rg_mbid:
            time.sleep(RATE_LIMIT) # Respetar un poco el rate limit por IP/Proxy
            result = search_musicbrainz(artist_name, album_name, proxy)
            if result: release_mbid, rg_mbid = result

        if rg_mbid:
            with db_lock: # BLOQUEO PARA ESCRITURA
                # ¿Ya existe este release group en la DB?
                dup = main_conn.execute("SELECT id FROM albums WHERE release_group_mbid=? AND id!=?", (rg_mbid, album_id)).fetchone()
                if dup:
                    # Aquí llamarías a tu lógica de merge_into simplificada para el hilo
                    # Para brevedad, actualizamos este y ya
                    main_conn.execute("UPDATE albums SET release_group_mbid=? WHERE id=?", (rg_mbid, album_id))
                    status = "merged"
                else:
                    main_conn.execute("UPDATE albums SET mbid=COALESCE(mbid,?), release_group_mbid=? WHERE id=?", (release_mbid, rg_mbid, album_id))
                    status = "updated"
                main_conn.commit()
            return status
    except Exception as e:
        return f"error: {e}"
    finally:
        main_conn.close()
        if cache_conn: cache_conn.close()
    return "not_found"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxies", type=str, help="Lista de proxies separada por comas")
    args = parser.parse_args()

    if not args.proxies:
        print("❌ Error: Debes proporcionar al menos un proxy con --proxies")
        return

    p_list = [p.strip() for p in args.proxies.split(",")]
    num_threads = len(p_list)
    proxy_cycle = itertools.cycle(p_list)

    main_conn = sqlite3.connect(MAIN_DB)
    rows = main_conn.execute("""
        SELECT albums.id, albums.name, artists.name FROM albums
        JOIN artists ON albums.artist_id = artists.id
        WHERE albums.release_group_mbid IS NULL
    """).fetchall()
    main_conn.close()

    print(f"🚀 Iniciando {num_threads} hilos para {len(rows)} álbumes...")

    # Usamos ThreadPoolExecutor para gestionar los hilos
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Asignamos cada álbum a un proxy de la lista rotativa
        futures = [executor.submit(process_album, row, next(proxy_cycle), CACHE_DB if os.path.exists(CACHE_DB) else None) for row in rows]

        # Opcional: ver progreso
        for i, future in enumerate(futures):
            res = future.result()
            if (i+1) % 10 == 0:
                print(f"✅ Procesados {i+1}/{len(rows)}...")

    print("\n✨ Tarea completada.")

if __name__ == "__main__":
    main()

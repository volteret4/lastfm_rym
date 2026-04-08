import sqlite3
import ssl
import requests
import time
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

MAIN_DB  = "db/must_hear_rym_new.db"
CACHE_DB = "db/lasfm_cache_rym_new_normalized.db"

RATE_LIMIT = 1.1

HEADERS = {
    "User-Agent": "mbid-filler/1.0 (frodobolson@disroot.org)"
}


class _TLS12Adapter(HTTPAdapter):
    """Fuerza TLS 1.2 para evitar UNEXPECTED_EOF_WHILE_READING con TLS 1.3."""
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
    return s.lower().strip()


def get_from_cache(cache_conn, artist, album):
    try:
        row = cache_conn.execute("""
            SELECT a.mbid, a.release_group_mbid
            FROM albums a
            JOIN artists ar ON a.artist_id = ar.id
            WHERE LOWER(ar.name) = ?
              AND LOWER(a.name) = ?
              AND (a.mbid IS NOT NULL OR a.release_group_mbid IS NOT NULL)
            LIMIT 1
        """, (normalize(artist), normalize(album))).fetchone()
        return row
    except sqlite3.OperationalError:
        return None


def search_musicbrainz(artist, album):
    query = f'artist:"{artist}" AND release:"{album}"'
    url = "https://musicbrainz.org/ws/2/release/"
    params = {"query": query, "fmt": "json", "limit": 1}

    try:
        r = _session.get(url, headers=HEADERS, params=params, timeout=20)
    except requests.RequestException as e:
        print(f"   ⚠ error de red: {e}")
        return None

    if r.status_code == 503:
        print("   ⏳ MusicBrainz 503 — esperando 10s")
        time.sleep(10)
        return None
    if r.status_code != 200:
        print(f"   ⚠ HTTP {r.status_code}")
        return None

    data = r.json()
    if not data.get("releases"):
        return None

    release = data["releases"][0]
    return (
        release.get("id"),
        release.get("release-group", {}).get("id"),
    )


def main():
    if not os.path.isfile(MAIN_DB):
        raise FileNotFoundError(f"Main DB not found: {MAIN_DB}")

    main_conn  = sqlite3.connect(MAIN_DB)
    cache_conn = sqlite3.connect(CACHE_DB) if os.path.isfile(CACHE_DB) else None

    if cache_conn:
        print(f"📦 Cache DB: {CACHE_DB}")
    else:
        print(f"⚠  Cache DB no encontrada ({CACHE_DB}) — sólo MusicBrainz API")

    rows = main_conn.execute("""
        SELECT albums.id, albums.name, artists.name
        FROM albums
        JOIN artists ON albums.artist_id = artists.id
        WHERE albums.release_group_mbid IS NULL
    """).fetchall()

    print(f"🔎 {len(rows)} álbumes sin release_group_mbid")

    found = skipped = api_calls = 0

    for album_id, album_name, artist_name in rows:
        print(f"\n🎵 {artist_name} — {album_name}")

        release_mbid = rg_mbid = None

        # 1. Try cache
        if cache_conn:
            cached = get_from_cache(cache_conn, artist_name, album_name)
            if cached and any(cached):
                release_mbid, rg_mbid = cached
                print(f"   ⚡ cache: release={release_mbid}  rg={rg_mbid}")

        # 2. MusicBrainz API if still missing
        if not rg_mbid:
            result = search_musicbrainz(artist_name, album_name)
            api_calls += 1
            time.sleep(RATE_LIMIT)
            if result:
                release_mbid, rg_mbid = result
                print(f"   🌐 MB:    release={release_mbid}  rg={rg_mbid}")
            else:
                print("   ❌ no encontrado")
                skipped += 1
                continue

        main_conn.execute("""
            UPDATE albums
            SET mbid = COALESCE(mbid, ?),
                release_group_mbid = COALESCE(release_group_mbid, ?)
            WHERE id = ?
        """, (release_mbid, rg_mbid, album_id))
        main_conn.commit()
        found += 1

    main_conn.close()
    if cache_conn:
        cache_conn.close()

    print(f"\n✅ terminado — rellenados: {found}  sin resultado: {skipped}  llamadas API: {api_calls}")


if __name__ == "__main__":
    main()

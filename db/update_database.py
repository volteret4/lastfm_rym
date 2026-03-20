#!/usr/bin/env python3
"""
Last.fm Database Updater — Normalized Schema v1
================================================
Escribe en lastfm_cache_rym_new_normalized.db (esquema v2 normalizado).

Diferencias clave respecto a db/update_database.py (schema legacy):
  - Una tabla por usuario: scrobbles_<username> (sin columna user_id)
  - artists / albums / tracks son filas normalizadas con FKs enteras
  - géneros van a M2M: genres + album_genres / artist_genres
  - album_metadata almacena textos largos (bio, wiki, productores…)
  - Sin tabla cache_responses: last_updated indica si ya fue enriquecido

Uso idéntico al legacy:
  python3 db_new/update_database.py
  python3 db_new/update_database.py --all
  python3 db_new/update_database.py --enrich --limit 500
  python3 db_new/update_database.py --db /ruta/a/lastfm_cache_rym_new_normalized.db
"""

import os, sys, json, sqlite3, time, threading, re, unicodedata, argparse
import requests
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_API_KEY') or not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass


# ── Default DB path ───────────────────────────────────────────────────────────
_DEFAULT_DB = os.path.join(os.path.dirname(__file__), '..', 'db',
                           'lastfm_cache_rym_new_normalized.db')

# ── Campos que van a album_metadata (no a albums) ────────────────────────────
_ALBUM_METADATA_FIELDS = frozenset({
    "desc_lfm_album", "desc_lfm_artist",
    "desc_mb_album",  "desc_mb_artist",
    "wikipedia_content",
    "producers", "engineers", "credits",
})


def _user_table(username: str) -> str:
    """Nombre de la tabla de scrobbles para un usuario."""
    safe = re.sub(r'[^a-z0-9]', '_', username.lower()).strip('_')
    return f"scrobbles_{safe}"


# ══════════════════════════════════════════════════════════════════════════════
# TEXT NORMALIZER  (sin cambios respecto al script legacy)
# ══════════════════════════════════════════════════════════════════════════════

class TextNormalizer:
    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        text = text.lower()
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[^\w\s]', ' ', text)
        return ' '.join(text.split()).strip()

    @staticmethod
    def clean_for_search(text: str) -> Tuple[str, str]:
        if not text:
            return "", ""
        original = text
        cleaned = text
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
        cleaned = re.sub(r'\{[^}]*\}', '', cleaned)
        special_versions = [
            r'\b(remaster(?:ed)?|deluxe|expanded|special|anniversary|edition|version)\b',
            r'\b(feat(?:uring)?|ft\.?|with)\s+[^-]*',
            r'\b(remix|mix|radio\s+edit|extended|acoustic)\b',
            r'\b\d+th\s+anniversary\b',
            r'\b(mono|stereo)\b',
        ]
        for pattern in special_versions:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'[^\w\s\-]', ' ', cleaned)
        return ' '.join(cleaned.split()).strip(), original

    @staticmethod
    def generate_search_variants(text: str) -> List[str]:
        if not text:
            return []
        variants = []
        cleaned, original = TextNormalizer.clean_for_search(text)
        variants.append(original.strip())
        if cleaned != original and cleaned:
            variants.append(cleaned)
        super_clean = re.sub(r'[^\w\s]', ' ', cleaned)
        super_clean = ' '.join(super_clean.split())
        if super_clean and super_clean not in variants:
            variants.append(super_clean)
        return [v for v in variants if v]


# ══════════════════════════════════════════════════════════════════════════════
# PROXY MANAGER  (sin cambios)
# ══════════════════════════════════════════════════════════════════════════════

class ProxyManager:
    def __init__(self, use_proxies: bool = False):
        self.use_proxies = use_proxies
        self.proxies: List[Dict] = []
        self.current_proxy_index = 0
        self.failed_proxies: Set[str] = set()
        self.lock = threading.Lock()
        if use_proxies:
            self._load_proxies()

    def _load_proxies(self):
        proxy_list = os.getenv('PROXIES', '').strip().strip('"').strip("'")
        if not proxy_list:
            i = 1
            while True:
                proxy = os.getenv(f'PROXY_{i}', '').strip().strip('"').strip("'")
                if not proxy:
                    break
                parsed = self._parse_proxy(proxy)
                if parsed:
                    self.proxies.append(parsed)
                i += 1
        else:
            for p in proxy_list.split(','):
                parsed = self._parse_proxy(p.strip().strip('"').strip("'"))
                if parsed:
                    self.proxies.append(parsed)
        if not self.proxies:
            print("⚠️  --proxied: no se encontraron proxies válidos en .env")
            self.use_proxies = False
        else:
            print(f"📄 {len(self.proxies)} proxies cargados")

    def _parse_proxy(self, s: str) -> Optional[Dict]:
        if not s:
            return None
        auth = None
        host_port = s
        if '@' in s:
            auth_part, host_port = s.rsplit('@', 1)
            if ':' in auth_part:
                auth = auth_part
        g_user = os.getenv('PROXY_USER', '').strip().strip('"').strip("'")
        g_pass = os.getenv('PROXY_PASS', '').strip().strip('"').strip("'")
        if not auth and g_user and g_pass:
            auth = f"{g_user}:{g_pass}"
        if ':' not in host_port:
            return None
        try:
            host, port = host_port.rsplit(':', 1)
            int(port)
        except ValueError:
            return None
        url = f"http://{auth}@{host}:{port}" if auth else f"http://{host}:{port}"
        return {'http': url, 'https': url,
                '_display': f"{host}:{port}" + (" (auth)" if auth else "")}

    def get_proxy_config(self) -> Optional[Dict]:
        if not self.use_proxies or not self.proxies:
            return None
        with self.lock:
            available = [p for p in self.proxies if p['_display'] not in self.failed_proxies]
            if not available:
                self.failed_proxies.clear()
                available = self.proxies
            proxy = available[self.current_proxy_index % len(available)]
            self.current_proxy_index += 1
            return dict(proxy)

    def mark_proxy_failed(self, proxy_config: Dict):
        if proxy_config and '_display' in proxy_config:
            with self.lock:
                self.failed_proxies.add(proxy_config['_display'])


# ══════════════════════════════════════════════════════════════════════════════
# API CLIENTS  (sin cambios)
# ══════════════════════════════════════════════════════════════════════════════

class ApiClient:
    def __init__(self, base_url: str, rate_limit_delay: float = 0.2,
                 proxy_manager: Optional[ProxyManager] = None, debug_mode: bool = False):
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
        self.proxy_manager = proxy_manager
        self.debug_mode = debug_mode
        self.session = requests.Session()
        self.last_request_time = 0.0
        self.lock = threading.Lock()
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5

    def _rate_limit(self):
        with self.lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
            self.last_request_time = time.time()

    def get(self, url: str, params: Dict = None,
            headers: Dict = None, timeout: int = 15) -> Optional[Dict]:
        if self.consecutive_errors >= self.max_consecutive_errors:
            return None
        self._rate_limit()
        proxy_config = None
        if self.proxy_manager and self.proxy_manager.use_proxies:
            proxy_config = self.proxy_manager.get_proxy_config()
        proxies = (
            {'http': proxy_config['http'], 'https': proxy_config['https']}
            if proxy_config else None
        )
        try:
            r = self.session.get(url, params=params, headers=headers,
                                 timeout=timeout, proxies=proxies)
            if r.status_code == 200:
                self.consecutive_errors = 0
                return r.json()
            elif r.status_code == 429:
                wait = int(r.headers.get('Retry-After', 60))
                time.sleep(wait)
                return self.get(url, params, headers, timeout)
            elif r.status_code in (502, 503, 504):
                time.sleep(5)
                r2 = self.session.get(url, params=params, headers=headers,
                                      timeout=timeout, proxies=proxies)
                if r2.status_code == 200:
                    self.consecutive_errors = 0
                    return r2.json()
            self.consecutive_errors += 1
        except requests.exceptions.ProxyError:
            if proxy_config and self.proxy_manager:
                self.proxy_manager.mark_proxy_failed(proxy_config)
            self.consecutive_errors += 1
        except requests.exceptions.Timeout:
            self.consecutive_errors += 1
        except requests.exceptions.ConnectionError:
            self.consecutive_errors += 1
            time.sleep(2)
        except Exception:
            self.consecutive_errors += 1
        return None


class LastFMClient(ApiClient):
    def __init__(self, api_key: str, proxy_manager=None, debug_mode=False):
        super().__init__("https://ws.audioscrobbler.com/2.0/", 0.2, proxy_manager, debug_mode)
        self.api_key = api_key

    def get_user_scrobbles(self, username, limit=200, from_timestamp=None,
                           to_timestamp=None, page=1):
        params = {
            'method': 'user.getRecentTracks', 'user': username,
            'api_key': self.api_key, 'format': 'json',
            'limit': limit, 'page': page,
        }
        if from_timestamp:
            params['from'] = from_timestamp
        if to_timestamp:
            params['to'] = to_timestamp
        return self.get(self.base_url, params)

    def get_artist_info(self, artist_name):
        return self.get(self.base_url, {
            'method': 'artist.getInfo', 'artist': artist_name,
            'api_key': self.api_key, 'format': 'json', 'autocorrect': 1,
        })

    def get_album_info(self, artist, album):
        return self.get(self.base_url, {
            'method': 'album.getInfo', 'artist': artist, 'album': album,
            'api_key': self.api_key, 'format': 'json', 'autocorrect': 1,
        })

    def get_track_info(self, artist, track):
        return self.get(self.base_url, {
            'method': 'track.getInfo', 'artist': artist, 'track': track,
            'api_key': self.api_key, 'format': 'json', 'autocorrect': 1,
        })


class MusicBrainzClient(ApiClient):
    def __init__(self, proxy_manager=None, debug_mode=False):
        super().__init__("https://musicbrainz.org/ws/2/", 1.1, proxy_manager, debug_mode)
        self.session.headers.update({
            'User-Agent': 'LastFM-Database-Updater/2.0 (contact@example.com)'
        })

    def search_artist(self, name):
        for variant in TextNormalizer.generate_search_variants(name)[:2]:
            r = self.get(f"{self.base_url}artist/",
                         {'query': f'artist:"{variant}"', 'fmt': 'json', 'limit': 5})
            if r and r.get('artists'):
                return r
        return None

    def get_artist_by_mbid(self, mbid):
        return self.get(f"{self.base_url}artist/{mbid}",
                        {'fmt': 'json', 'inc': 'genres+tags'})

    def search_release(self, artist, album, track_hint=None):
        for alb in TextNormalizer.generate_search_variants(album)[:2]:
            for art in TextNormalizer.generate_search_variants(artist)[:2]:
                r = self.get(f"{self.base_url}release/", {
                    'query': f'release:"{alb}" AND artist:"{art}"',
                    'fmt': 'json', 'limit': 5,
                })
                if r and r.get('releases'):
                    return r
        return None

    def get_release_by_mbid(self, mbid):
        return self.get(f"{self.base_url}release/{mbid}", {
            'fmt': 'json',
            'inc': 'release-groups+labels+recordings+genres+tags',
        })

    def search_recording(self, artist, track, album_hint=None):
        for art in TextNormalizer.generate_search_variants(artist)[:2]:
            for trk in TextNormalizer.generate_search_variants(track)[:2]:
                q = f'recording:"{trk}" AND artist:"{art}"'
                if album_hint:
                    alb_clean, _ = TextNormalizer.clean_for_search(album_hint)
                    if alb_clean:
                        q += f' AND release:"{alb_clean}"'
                r = self.get(f"{self.base_url}recording/",
                             {'query': q, 'fmt': 'json', 'limit': 5})
                if r and r.get('recordings'):
                    return r
        return None


class DiscogsClient(ApiClient):
    def __init__(self, token: str, proxy_manager=None, debug_mode=False):
        super().__init__("https://api.discogs.com/", 1.2, proxy_manager, debug_mode)
        self.token = token
        if token:
            self.session.headers.update({
                'Authorization': f'Discogs token={token}',
                'User-Agent': 'LastFM-Database-Updater/2.0',
            })

    def search_artist(self, name):
        if not self.token:
            return None
        for v in TextNormalizer.generate_search_variants(name)[:2]:
            r = self.get(f"{self.base_url}database/search",
                         {'q': v, 'type': 'artist', 'per_page': 5})
            if r and r.get('results'):
                return r
        return None

    def search_release(self, artist, album):
        if not self.token:
            return None
        for art in TextNormalizer.generate_search_variants(artist)[:2]:
            for alb in TextNormalizer.generate_search_variants(album)[:2]:
                r = self.get(f"{self.base_url}database/search",
                             {'q': f'{art} {alb}', 'type': 'release', 'per_page': 5})
                if r and r.get('results'):
                    return r
        return None

    def get_artist_details(self, artist_id):
        if not self.token:
            return None
        return self.get(f"{self.base_url}artists/{artist_id}")

    def get_release_details(self, release_id):
        if not self.token:
            return None
        return self.get(f"{self.base_url}releases/{release_id}")


# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZED DATABASE
# ══════════════════════════════════════════════════════════════════════════════

class NormalizedDatabase:
    """
    Capa de acceso a datos para el esquema v2 normalizado.

    Una tabla por usuario:
      scrobbles_<username>(artist_id, track_id, album_id, timestamp)

    Sin columna user_id en scrobbles → consultas por usuario ~10x más rápidas.
    La tabla 'users' sigue existiendo como registro de usuarios conocidos.

    Cachés en memoria para get_or_create_* evitan round-trips innecesarios.
    """

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.lock = threading.RLock()
        self.pending_commits = 0

        # Cachés en memoria
        self._artist_cache: Dict[str, int] = {}          # name → id
        self._album_cache:  Dict[Tuple[str, int], int] = {}  # (name, artist_id) → id
        self._track_cache:  Dict[Tuple[str, int], int] = {}  # (name, artist_id) → id
        self._genre_cache:  Dict[str, int] = {}              # name.lower() → id
        self._user_tables:  Set[str] = set()                  # nombres de tablas ya creadas

        self._preload_caches()

    # ── Cache pre-loading ─────────────────────────────────────────────────────

    def _preload_caches(self):
        for row in self.conn.execute("SELECT id, name FROM artists"):
            self._artist_cache[row[1]] = row[0]
        for row in self.conn.execute("SELECT id, name, artist_id FROM albums"):
            self._album_cache[(row[1], row[2])] = row[0]
        for row in self.conn.execute("SELECT id, name, artist_id FROM tracks"):
            self._track_cache[(row[1], row[2])] = row[0]
        for row in self.conn.execute("SELECT id, name FROM genres"):
            self._genre_cache[row[1].lower()] = row[0]
        # Detectar tablas de scrobbles existentes
        for row in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'scrobbles_%'"
        ):
            self._user_tables.add(row[0])

    # ── Per-user scrobble table management ───────────────────────────────────

    def _ensure_user_table(self, username: str) -> str:
        """Crea la tabla de scrobbles del usuario si no existe. Devuelve el nombre."""
        tbl = _user_table(username)
        if tbl in self._user_tables:
            return tbl
        with self.lock:
            if tbl in self._user_tables:
                return tbl
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    artist_id INTEGER NOT NULL REFERENCES artists(id),
                    track_id  INTEGER NOT NULL REFERENCES tracks(id),
                    album_id  INTEGER          REFERENCES albums(id),
                    timestamp INTEGER NOT NULL,
                    UNIQUE (timestamp, artist_id, track_id)
                )
            """)
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{tbl}_ts      ON {tbl}(timestamp)"
            )
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{tbl}_artist  ON {tbl}(artist_id)"
            )
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{tbl}_album   ON {tbl}(album_id)"
            )
            # Registrar en users si no existe
            self.conn.execute(
                "INSERT OR IGNORE INTO users (username) VALUES (?)", (username,)
            )
            self.conn.commit()
            self._user_tables.add(tbl)
            return tbl

    def _known_user_tables(self) -> List[str]:
        return list(self._user_tables)

    # ── Entity resolution ─────────────────────────────────────────────────────

    def get_or_create_artist(self, name: str, mbid: str = None) -> int:
        with self.lock:
            if name in self._artist_cache:
                return self._artist_cache[name]
            self.conn.execute(
                "INSERT OR IGNORE INTO artists (name, mbid) VALUES (?,?)",
                (name, mbid or None)
            )
            row = self.conn.execute(
                "SELECT id FROM artists WHERE name=?", (name,)
            ).fetchone()
            self._artist_cache[name] = row[0]
            self.pending_commits += 1
            return row[0]

    def get_or_create_album(self, name: str, artist_id: int,
                             mbid: str = None, year: int = None) -> int:
        key = (name, artist_id)
        with self.lock:
            if key in self._album_cache:
                return self._album_cache[key]
            self.conn.execute(
                "INSERT OR IGNORE INTO albums (name, artist_id, mbid, year) VALUES (?,?,?,?)",
                (name, artist_id, mbid or None, year)
            )
            row = self.conn.execute(
                "SELECT id FROM albums WHERE name=? AND artist_id=?",
                (name, artist_id)
            ).fetchone()
            self._album_cache[key] = row[0]
            self.pending_commits += 1
            return row[0]

    def get_or_create_track(self, name: str, artist_id: int,
                             album_id: int = None, mbid: str = None) -> int:
        key = (name, artist_id)
        with self.lock:
            if key in self._track_cache:
                return self._track_cache[key]
            self.conn.execute(
                "INSERT OR IGNORE INTO tracks (name, artist_id, album_id, mbid) VALUES (?,?,?,?)",
                (name, artist_id, album_id, mbid or None)
            )
            row = self.conn.execute(
                "SELECT id FROM tracks WHERE name=? AND artist_id=?",
                (name, artist_id)
            ).fetchone()
            self._track_cache[key] = row[0]
            self.pending_commits += 1
            return row[0]

    def _get_or_create_genre_nolock(self, name: str, source: str = None) -> Optional[int]:
        """Sin lock — para usar dentro de métodos que ya lo tienen."""
        key = name.lower().strip()
        if not key:
            return None
        if key in self._genre_cache:
            return self._genre_cache[key]
        ts = int(time.time())
        self.conn.execute(
            "INSERT OR IGNORE INTO genres (name, source, last_updated) VALUES (?,?,?)",
            (key, source, ts)
        )
        row = self.conn.execute("SELECT id FROM genres WHERE name=?", (key,)).fetchone()
        self._genre_cache[key] = row[0]
        return row[0]

    # ── Scrobbles ─────────────────────────────────────────────────────────────

    def save_scrobbles_batch(self, username: str,
                              rows: List[Tuple]) -> int:
        """
        rows: lista de (artist_id, track_id, album_id, timestamp)
        Devuelve número de filas nuevas insertadas.
        """
        tbl = self._ensure_user_table(username)
        with self.lock:
            count = 0
            for row in rows:
                try:
                    self.conn.execute(
                        f"INSERT OR IGNORE INTO {tbl} "
                        f"(artist_id, track_id, album_id, timestamp) VALUES (?,?,?,?)",
                        row
                    )
                    count += 1
                except Exception:
                    pass
            self.pending_commits += count
            if self.pending_commits >= 200:
                self.conn.commit()
                self.pending_commits = 0
            return count

    def get_last_scrobble_timestamp(self, username: str) -> Optional[int]:
        tbl = _user_table(username)
        if tbl not in self._user_tables:
            return None
        row = self.conn.execute(
            f"SELECT MAX(timestamp) FROM {tbl}"
        ).fetchone()
        return row[0] if row else None

    def get_first_scrobble_timestamp(self, username: str) -> Optional[int]:
        tbl = _user_table(username)
        if tbl not in self._user_tables:
            return None
        row = self.conn.execute(
            f"SELECT MIN(timestamp) FROM {tbl}"
        ).fetchone()
        return row[0] if row else None

    def count_overlap_scrobbles(self, username: str,
                                 ts_from: int, ts_to: int) -> int:
        tbl = _user_table(username)
        if tbl not in self._user_tables:
            return 0
        row = self.conn.execute(
            f"SELECT COUNT(*) FROM {tbl} WHERE timestamp>=? AND timestamp<=?",
            (ts_from, ts_to)
        ).fetchone()
        return row[0] if row else 0

    # ── Artist enrichment ─────────────────────────────────────────────────────

    def update_artist(self, artist_id: int, fields: Dict):
        """COALESCE: solo rellena campos vacíos.
        Si hay conflicto UNIQUE (mbid duplicado), reintenta sin los campos únicos."""
        if not fields:
            return
        ts = int(time.time())
        # Campos con índice UNIQUE que pueden colisionar con otros artistas
        unique_fields = {'mbid'}
        with self.lock:
            def _build_and_run(flds):
                set_parts, params = [], []
                for col, val in flds.items():
                    if isinstance(val, (list, dict)):
                        val = json.dumps(val, ensure_ascii=False)
                    set_parts.append(f"{col} = COALESCE({col}, ?)")
                    params.append(val)
                set_parts.append("last_updated = ?")
                params.extend([ts, artist_id])
                self.conn.execute(
                    f"UPDATE artists SET {', '.join(set_parts)} WHERE id=?", params
                )
            try:
                _build_and_run(fields)
            except sqlite3.IntegrityError:
                # Reintenta sin los campos únicos conflictivos
                safe_fields = {k: v for k, v in fields.items() if k not in unique_fields}
                if safe_fields:
                    _build_and_run(safe_fields)
            self.pending_commits += 1

    def save_artist_genres(self, artist_id: int, genres: List, source: str = None):
        with self.lock:
            for g in genres:
                name = g.get('name', g) if isinstance(g, dict) else str(g)
                weight = g.get('weight', 1.0) if isinstance(g, dict) else 1.0
                gid = self._get_or_create_genre_nolock(name, source)
                if gid:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO artist_genres "
                        "(artist_id, genre_id, weight) VALUES (?,?,?)",
                        (artist_id, gid, weight)
                    )
            self.pending_commits += len(genres)

    def get_artist_id_by_name(self, name: str) -> Optional[int]:
        return self._artist_cache.get(name)

    # ── Album enrichment ──────────────────────────────────────────────────────

    def update_album(self, album_id: int, fields: Dict):
        """COALESCE. Textos largos (_ALBUM_METADATA_FIELDS) → album_metadata."""
        if not fields:
            return
        ts = int(time.time())
        meta  = {k: v for k, v in fields.items() if k in _ALBUM_METADATA_FIELDS}
        album = {k: v for k, v in fields.items() if k not in _ALBUM_METADATA_FIELDS}
        unique_fields = {'mbid'}
        with self.lock:
            if album:
                def _run_album(flds):
                    set_parts, params = [], []
                    for col, val in flds.items():
                        if isinstance(val, (list, dict)):
                            val = json.dumps(val, ensure_ascii=False)
                        set_parts.append(f"{col} = COALESCE({col}, ?)")
                        params.append(val)
                    set_parts.append("last_updated = ?")
                    params.extend([ts, album_id])
                    self.conn.execute(
                        f"UPDATE albums SET {', '.join(set_parts)} WHERE id=?", params
                    )
                try:
                    _run_album(album)
                except sqlite3.IntegrityError:
                    safe = {k: v for k, v in album.items() if k not in unique_fields}
                    if safe:
                        _run_album(safe)
            if meta:
                self.conn.execute(
                    "INSERT OR IGNORE INTO album_metadata (album_id) VALUES (?)",
                    (album_id,)
                )
                set_parts, params = [], []
                for col, val in meta.items():
                    set_parts.append(f"{col} = COALESCE({col}, ?)")
                    params.append(val)
                params.append(album_id)
                self.conn.execute(
                    f"UPDATE album_metadata SET {', '.join(set_parts)} WHERE album_id=?",
                    params
                )
            self.pending_commits += 1

    def save_artist_similarities(self, artist_id: int,
                                   similar_names: List[str], source: str = 'lastfm'):
        """Inserta en artist_similarities para los artistas similares que ya existen en la BD."""
        with self.lock:
            # Crear tabla si no existe (puede que el migrador aún no haya corrido)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS artist_similarities (
                    artist_id        INTEGER NOT NULL REFERENCES artists(id),
                    similar_artist_id INTEGER NOT NULL REFERENCES artists(id),
                    score            REAL    NOT NULL DEFAULT 1.0,
                    source           TEXT,
                    PRIMARY KEY (artist_id, similar_artist_id)
                )
            """)
            for name in similar_names:
                sim_id = self._artist_cache.get(name)
                if sim_id and sim_id != artist_id:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO artist_similarities "
                        "(artist_id, similar_artist_id, score, source) VALUES (?,?,?,?)",
                        (artist_id, sim_id, 1.0, source)
                    )
            self.pending_commits += len(similar_names)

    def save_album_genres(self, album_id: int, genres: List, source: str = None):
        with self.lock:
            for g in genres:
                name = g.get('name', g) if isinstance(g, dict) else str(g)
                weight = g.get('weight', 1.0) if isinstance(g, dict) else 1.0
                gid = self._get_or_create_genre_nolock(name, source)
                if gid:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO album_genres "
                        "(album_id, genre_id, weight) VALUES (?,?,?)",
                        (album_id, gid, weight)
                    )
            self.pending_commits += len(genres)

    def get_album_id(self, album_name: str, artist_id: int) -> Optional[int]:
        return self._album_cache.get((album_name, artist_id))

    # ── Track enrichment ──────────────────────────────────────────────────────

    def update_track(self, track_id: int, fields: Dict):
        if not fields:
            return
        ts = int(time.time())
        unique_fields = {'mbid', 'isrc'}
        with self.lock:
            def _run_track(flds):
                set_parts, params = [], []
                for col, val in flds.items():
                    set_parts.append(f"{col} = COALESCE({col}, ?)")
                    params.append(val)
                set_parts.append("last_updated = ?")
                params.extend([ts, track_id])
                self.conn.execute(
                    f"UPDATE tracks SET {', '.join(set_parts)} WHERE id=?", params
                )
            try:
                _run_track(fields)
            except sqlite3.IntegrityError:
                safe = {k: v for k, v in fields.items() if k not in unique_fields}
                if safe:
                    _run_track(safe)
            self.pending_commits += 1

    # ── Queries for enrichment queue ──────────────────────────────────────────

    def _scrobble_counts_subquery(self, entity_col: str) -> str:
        """
        Subconsulta que agrega scrobbles de todos los usuarios en un solo pase
        (UNION ALL + GROUP BY), mucho más rápida que subqueries correlacionadas.
        """
        tables = self._known_user_tables()
        if not tables:
            return "(SELECT 0 AS entity_id, 0 AS cnt)"
        union = " UNION ALL ".join(
            f"SELECT {entity_col} AS entity_id FROM {t}"
            for t in tables
        )
        return f"(SELECT entity_id, COUNT(*) AS cnt FROM ({union}) GROUP BY entity_id)"

    def get_entities_to_enrich(self, entity_type: str, limit: int = 1000) -> List[Tuple]:
        """
        Entidades sin enriquecer, ordenadas por popularidad.

        Criterio "no enriquecido":
          artist → mbid IS NULL  (el enricher siempre lo rellena)
          album  → year IS NULL  (viene de MB/Discogs, nunca del ingesto)
          track  → mbid IS NULL

        Returns:
          artist → [(artist_id, artist_name), ...]
          album  → [(album_id, artist_name, album_name), ...]
          track  → [(track_id, artist_name, track_name), ...]
        """
        if entity_type == 'artist':
            sq = self._scrobble_counts_subquery("artist_id")
            rows = self.conn.execute(f"""
                SELECT e.id, e.name
                FROM artists e
                LEFT JOIN {sq} sc ON sc.entity_id = e.id
                WHERE e.mbid IS NULL
                ORDER BY COALESCE(sc.cnt, 0) DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [(r[0], r[1]) for r in rows]

        elif entity_type == 'album':
            sq = self._scrobble_counts_subquery("album_id")
            rows = self.conn.execute(f"""
                SELECT e.id, ar.name, e.name
                FROM albums e
                JOIN artists ar ON ar.id = e.artist_id
                LEFT JOIN {sq} sc ON sc.entity_id = e.id
                WHERE e.year IS NULL
                ORDER BY COALESCE(sc.cnt, 0) DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [(r[0], r[1], r[2]) for r in rows]

        elif entity_type == 'track':
            sq = self._scrobble_counts_subquery("track_id")
            rows = self.conn.execute(f"""
                SELECT e.id, ar.name, e.name
                FROM tracks e
                JOIN artists ar ON ar.id = e.artist_id
                LEFT JOIN {sq} sc ON sc.entity_id = e.id
                WHERE e.mbid IS NULL
                ORDER BY COALESCE(sc.cnt, 0) DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [(r[0], r[1], r[2]) for r in rows]

        return []

    def get_scrobble_context_for_album(self, artist_id: int,
                                        album_id: int) -> Optional[str]:
        """Track más escuchado para un álbum (hint para búsquedas MB)."""
        tables = self._known_user_tables()
        if not tables:
            return None
        # Buscar en la primera tabla disponible (suficiente como hint)
        tbl = tables[0]
        row = self.conn.execute(f"""
            SELECT t.name FROM {tbl} s
            JOIN tracks t ON t.id = s.track_id
            WHERE s.artist_id=? AND s.album_id=?
            GROUP BY s.track_id ORDER BY COUNT(*) DESC LIMIT 1
        """, (artist_id, album_id)).fetchone()
        return row[0] if row else None

    def get_scrobble_context_for_track(self, artist_id: int,
                                        track_id: int) -> Optional[str]:
        """Álbum más común para un track (hint para búsquedas MB)."""
        tables = self._known_user_tables()
        if not tables:
            return None
        tbl = tables[0]
        row = self.conn.execute(f"""
            SELECT a.name FROM {tbl} s
            JOIN albums a ON a.id = s.album_id
            WHERE s.artist_id=? AND s.track_id=? AND s.album_id IS NOT NULL
            GROUP BY s.album_id ORDER BY COUNT(*) DESC LIMIT 1
        """, (artist_id, track_id)).fetchone()
        return row[0] if row else None

    # ── Commit / close ────────────────────────────────────────────────────────

    def force_commit(self):
        with self.lock:
            self.conn.commit()
            self.pending_commits = 0

    def close(self):
        self.force_commit()
        self.conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# MULTITHREADED UPDATER
# ══════════════════════════════════════════════════════════════════════════════

class MultithreadedLastFMUpdater:
    def __init__(self, db_path: str = _DEFAULT_DB,
                 debug_mode: bool = False, use_proxies: bool = False,
                 max_workers: int = 8):
        self.debug_mode  = debug_mode
        self.use_proxies = use_proxies
        self.max_workers = max_workers

        self.proxy_manager = ProxyManager(use_proxies) if use_proxies else None

        self.lastfm_api_key    = os.getenv('LASTFM_API_KEY')
        self.discogs_tokens    = self._load_discogs_tokens()
        self.current_token_idx = 0

        if not self.lastfm_api_key:
            raise ValueError("LASTFM_API_KEY no encontrado en variables de entorno")

        users_env = os.getenv('LASTFM_USERS', '')
        self.users = [u.strip() for u in users_env.split(',') if u.strip()]
        if not self.users:
            raise ValueError("LASTFM_USERS no encontrado en variables de entorno")

        self.db = NormalizedDatabase(db_path)

        self.stats_lock = threading.Lock()
        self.stats = {
            'scrobbles_added': 0,
            'artists_enriched': 0,
            'albums_enriched': 0,
            'tracks_enriched': 0,
            'api_errors': 0,
        }

        if debug_mode:
            print(f"🔧 DEBUG MODE")
            print(f"🗄  DB: {db_path}")
            print(f"🧵 Workers: {max_workers}")
            print(f"👥 Usuarios: {len(self.users)}")

    def _load_discogs_tokens(self) -> List[str]:
        tokens = []
        t = os.getenv('DISCOGS_TOKEN', '')
        if t:
            tokens.append(t)
        i = 2
        while True:
            t = os.getenv(f'DISCOGS_TOKEN_{i}', '')
            if not t:
                break
            tokens.append(t)
            i += 1
        return tokens

    def _create_worker_clients(self):
        with self.stats_lock:
            idx = self.current_token_idx % len(self.discogs_tokens) \
                  if self.discogs_tokens else 0
            self.current_token_idx = (self.current_token_idx + 1) \
                                     % max(len(self.discogs_tokens), 1)
        token = self.discogs_tokens[idx] if self.discogs_tokens else ''
        return (
            LastFMClient(self.lastfm_api_key, self.proxy_manager, self.debug_mode),
            MusicBrainzClient(self.proxy_manager, self.debug_mode),
            DiscogsClient(token, self.proxy_manager, self.debug_mode),
        )

    def _update_stats(self, key: str, n: int = 1):
        with self.stats_lock:
            self.stats[key] = self.stats.get(key, 0) + n

    def _save_similar_artists(self, artist_id: int, similar: List[Dict], source: str):
        names = [s.get('name', '') for s in similar if s.get('name')]
        if names:
            self.db.save_artist_similarities(artist_id, names, source)

    # ── Artist enrichment worker ──────────────────────────────────────────────

    def enrich_artist_worker(self, artist_id: int, artist_name: str) -> bool:
        try:
            lastfm, mb, discogs = self._create_worker_clients()
            details: Dict = {}

            # ── LastFM ────────────────────────────────────────────────────────
            lfm = lastfm.get_artist_info(artist_name)
            if lfm and 'artist' in lfm:
                a = lfm['artist']
                details.update({
                    'mbid':       a.get('mbid') or None,
                    'bio':        a.get('bio', {}).get('summary', '').strip() or None,
                    'listeners':  int(a.get('stats', {}).get('listeners', 0)) or None,
                    'playcount':  int(a.get('stats', {}).get('playcount', 0)) or None,
                    'lastfm_url': a.get('url') or None,
                })
                # La API de LastFM deprecó imágenes de artistas (~2019);
                # el campo viene vacío o con placeholder genérico — lo ignoramos.
                tags = a.get('tags', {}).get('tag', [])
                if isinstance(tags, list) and tags:
                    details['tags'] = json.dumps([t.get('name', '') for t in tags[:10]])
                    lfm_genres = [{'name': t.get('name', ''), 'weight': 1.0}
                                  for t in tags[:5] if t.get('name')]
                    self.db.save_artist_genres(artist_id, lfm_genres, 'lastfm')
                similar = a.get('similar', {}).get('artist', [])
                if isinstance(similar, list) and similar:
                    self._save_similar_artists(artist_id, similar[:10], 'lastfm')

            # ── MusicBrainz ───────────────────────────────────────────────────
            mb_data = None
            if details.get('mbid'):
                mb_data = mb.get_artist_by_mbid(details['mbid'])
            else:
                sr = mb.search_artist(artist_name)
                if sr and sr.get('artists'):
                    details['mbid'] = sr['artists'][0]['id']
                    mb_data = mb.get_artist_by_mbid(details['mbid'])

            if mb_data:
                mb_genres = []
                if mb_data.get('genres'):
                    mb_genres = [{'name': g['name'], 'weight': 1.0}
                                 for g in mb_data['genres']]
                elif mb_data.get('tags'):
                    mb_genres = [{'name': t['name'],
                                  'weight': float(t.get('count', 1))}
                                 for t in mb_data['tags'][:10]]
                if mb_genres:
                    self.db.save_artist_genres(artist_id, mb_genres, 'musicbrainz')
                begin_date = (mb_data.get('life-span') or {}).get('begin') or None
                formed_year = None
                if begin_date:
                    try:
                        formed_year = int(begin_date[:4])
                    except (ValueError, TypeError):
                        pass
                details.update({
                    'country':        mb_data.get('country') or None,
                    'begin_date':     begin_date,
                    'end_date':       (mb_data.get('life-span') or {}).get('end') or None,
                    'formed_year':    formed_year,
                    'artist_type':    mb_data.get('type') or None,
                    'disambiguation': mb_data.get('disambiguation') or None,
                })

            # ── Discogs — imagen del artista ──────────────────────────────────
            if discogs.token:
                dr = discogs.search_artist(artist_name)
                if dr and dr.get('results'):
                    res = dr['results'][0]
                    cover = res.get('cover_image') or res.get('thumb')
                    # Filtramos el placeholder genérico de Discogs
                    if cover and 'spacer.gif' not in cover:
                        details['img_discogs'] = cover

            details = {k: v for k, v in details.items() if v is not None}
            self.db.update_artist(artist_id, details)
            self._update_stats('artists_enriched')
            return True

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️  Artista {artist_name}: {e}")
            self._update_stats('api_errors')
            return False

    # ── Album enrichment worker ───────────────────────────────────────────────

    def enrich_album_worker(self, album_id: int,
                             artist_name: str, album_name: str) -> bool:
        try:
            lastfm, mb, discogs = self._create_worker_clients()
            details: Dict = {}

            artist_id = self.db.get_artist_id_by_name(artist_name)
            track_hint = (
                self.db.get_scrobble_context_for_album(artist_id, album_id)
                if artist_id else None
            )

            lfm = lastfm.get_album_info(artist_name, album_name)
            if lfm and 'album' in lfm:
                mbid = lfm['album'].get('mbid') or None
                if mbid:
                    details['mbid'] = mbid

            mb_data = None
            if details.get('mbid'):
                mb_data = mb.get_release_by_mbid(details['mbid'])
            else:
                sr = mb.search_release(artist_name, album_name, track_hint)
                if sr and sr.get('releases'):
                    details['mbid'] = sr['releases'][0]['id']
                    mb_data = mb.get_release_by_mbid(details['mbid'])

            if mb_data:
                rg = mb_data.get('release-group', {})
                details.update({
                    'release_group_mbid': rg.get('id') or None,
                    'release_date':       mb_data.get('date') or None,
                    'album_type':         rg.get('primary-type') or None,
                    'status':             mb_data.get('status') or None,
                    'country':            mb_data.get('country') or None,
                    'barcode':            mb_data.get('barcode') or None,
                    'total_tracks': len(
                        (mb_data.get('media') or [{}])[0].get('tracks', [])
                    ) or None,
                })
                if mb_data.get('date'):
                    try:
                        details['year'] = int(mb_data['date'][:4])
                    except Exception:
                        pass
                li = mb_data.get('label-info', [])
                if li and isinstance(li, list):
                    lbl = (li[0].get('label') or {}).get('name')
                    if lbl:
                        details['label'] = lbl
                mb_genres = []
                if mb_data.get('genres'):
                    mb_genres = [{'name': g['name'], 'weight': 1.0}
                                 for g in mb_data['genres']]
                elif mb_data.get('tags'):
                    mb_genres = [{'name': t['name'],
                                  'weight': float(t.get('count', 1))}
                                 for t in mb_data['tags'][:10]]
                if mb_genres:
                    self.db.save_album_genres(album_id, mb_genres, 'musicbrainz')

            if discogs.token and (not details.get('year') or not details.get('producers')):
                dr = discogs.search_release(artist_name, album_name)
                if dr and dr.get('results'):
                    res = dr['results'][0]
                    if not details.get('year') and res.get('year'):
                        try:
                            details['year'] = int(res['year'])
                        except Exception:
                            pass
                    if not details.get('label') and res.get('label'):
                        details['label'] = res['label'][0]
                    if res.get('genre'):
                        dg = [{'name': g, 'weight': 1.0}
                              for g in res['genre'][:10] if g]
                        if dg:
                            self.db.save_album_genres(album_id, dg, 'discogs')
                    discogs_id = res.get('id')
                    if discogs_id:
                        full = discogs.get_release_details(discogs_id)
                        if full:
                            extra = full.get('extraartists', [])
                            producers = [
                                e['name'] for e in extra
                                if 'producer' in e.get('role', '').lower()
                            ]
                            if producers:
                                details['producers'] = json.dumps(producers, ensure_ascii=False)

            details = {k: v for k, v in details.items() if v is not None}
            self.db.update_album(album_id, details)
            self._update_stats('albums_enriched')
            return True

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️  Álbum {artist_name} — {album_name}: {e}")
            self._update_stats('api_errors')
            return False

    # ── Track enrichment worker ───────────────────────────────────────────────

    def enrich_track_worker(self, track_id: int,
                             artist_name: str, track_name: str) -> bool:
        try:
            lastfm, mb, _ = self._create_worker_clients()
            details: Dict = {}

            artist_id = self.db.get_artist_id_by_name(artist_name)
            album_hint = (
                self.db.get_scrobble_context_for_track(artist_id, track_id)
                if artist_id else None
            )

            lfm = lastfm.get_track_info(artist_name, track_name)
            if lfm and 'track' in lfm:
                t = lfm['track']
                details.update({
                    'mbid':        t.get('mbid') or None,
                    'duration_ms': int(t.get('duration', 0)) or None,
                })

            if not details.get('mbid'):
                sr = mb.search_recording(artist_name, track_name, album_hint)
                if sr and sr.get('recordings'):
                    rec = sr['recordings'][0]
                    details.update({
                        'mbid':        rec['id'],
                        'duration_ms': rec.get('length') or None,
                        'isrc':        (rec.get('isrcs') or [None])[0],
                    })

            details = {k: v for k, v in details.items() if v is not None}
            self.db.update_track(track_id, details)
            self._update_stats('tracks_enriched')
            return True

        except Exception as e:
            if self.debug_mode:
                print(f"⚠️  Track {artist_name} — {track_name}: {e}")
            self._update_stats('api_errors')
            return False

    # ── Parallel enrichment ───────────────────────────────────────────────────

    def enrich_entities_parallel(self, limit: int = 1000):
        print(f"\n🧵 Enriquecimiento paralelo ({self.max_workers} workers)")

        artists = self.db.get_entities_to_enrich('artist', limit)
        albums  = self.db.get_entities_to_enrich('album',  limit)
        tracks  = self.db.get_entities_to_enrich('track',  limit)

        print(f"  Artistas pendientes: {len(artists)}")
        print(f"  Álbumes pendientes:  {len(albums)}")
        print(f"  Tracks pendientes:   {len(tracks)}")

        def _run_pool(task_list, worker_fn, label, step):
            if not task_list:
                return
            emoji = '🎤' if label == 'artistas' else '💿' if label == 'álbumes' else '🎵'
            print(f"\n{emoji} Enriqueciendo {len(task_list)} {label}...")
            with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
                futures = [ex.submit(worker_fn, *args) for args in task_list]
                done = 0
                for _ in as_completed(futures):
                    done += 1
                    if done % step == 0:
                        print(f"   {done}/{len(task_list)}")
                        self.db.force_commit()
            self.db.force_commit()
            print(f"   ✅ {label} completados")

        _run_pool(artists, self.enrich_artist_worker, 'artistas', 50)
        _run_pool(albums,  self.enrich_album_worker,  'álbumes',  25)
        _run_pool(tracks,  self.enrich_track_worker,  'tracks',  100)

    # ── Scrobble download ─────────────────────────────────────────────────────

    def update_user_scrobbles_complete(self, username: str,
                                        download_all: bool = False,
                                        backfill: bool = False):
        print(f"\n👤 {username}")

        lastfm, _, _ = self._create_worker_clients()
        # Crea la tabla del usuario si no existe
        self.db._ensure_user_table(username)
        self.db.force_commit()

        from_timestamp = None
        if not download_all:
            last_ts = self.db.get_last_scrobble_timestamp(username)
            if last_ts:
                if backfill:
                    first_ts = self.db.get_first_scrobble_timestamp(username)
                    from_timestamp = (first_ts - 86400) if first_ts else None
                    print(f"   Backfill desde: "
                          f"{datetime.fromtimestamp(from_timestamp) if from_timestamp else 'origen'}")
                else:
                    from_timestamp = last_ts + 1
                    print(f"   Último scrobble: {datetime.fromtimestamp(last_ts)}")
            else:
                print(f"   Primera sincronización completa")

        init = lastfm.get_user_scrobbles(username, limit=1,
                                          from_timestamp=from_timestamp, page=1)
        if not init or 'recenttracks' not in init:
            print(f"   ❌ No se pudo contactar con Last.fm para {username}")
            return

        total_tracks = int(init['recenttracks'].get('@attr', {}).get('total', 0))
        if total_tracks == 0:
            print(f"   ✅ Sin nuevos scrobbles")
            return

        per_page    = 200
        total_pages = (total_tracks + per_page - 1) // per_page
        print(f"   {total_tracks} scrobbles nuevos — {total_pages} páginas")

        page = 1
        new_scrobbles = 0
        empty_streak  = 0
        processed     = 0

        while page <= total_pages:
            data = lastfm.get_user_scrobbles(
                username, limit=per_page,
                from_timestamp=from_timestamp, page=page
            )
            if not data or 'recenttracks' not in data:
                empty_streak += 1
                if empty_streak >= 5:
                    print(f"   ⚠ Demasiadas páginas vacías, abortando")
                    break
                page += 1
                continue
            else:
                empty_streak = 0

            tracks_data = data['recenttracks']
            if 'track' not in tracks_data:
                empty_streak += 1
                page += 1
                continue

            raw = tracks_data['track']
            if not isinstance(raw, list):
                raw = [raw]

            batch_rows = []
            for t in raw:
                if '@attr' in t and 'nowplaying' in t['@attr']:
                    continue
                if 'date' not in t:
                    continue
                ts = int(t['date']['uts'])
                if not download_all and not backfill and from_timestamp:
                    if ts <= from_timestamp - 1:
                        continue

                artist_name = (
                    t.get('artist', {}).get('#text', '')
                    if isinstance(t.get('artist'), dict)
                    else t.get('artist', '')
                )
                track_name = t.get('name', '')
                album_name = (
                    t.get('album', {}).get('#text', '')
                    if isinstance(t.get('album'), dict)
                    else t.get('album', '')
                )

                if not artist_name or not track_name:
                    continue

                artist_id = self.db.get_or_create_artist(artist_name)
                album_id  = (
                    self.db.get_or_create_album(album_name, artist_id)
                    if album_name else None
                )
                track_id  = self.db.get_or_create_track(
                    track_name, artist_id, album_id
                )
                # (artist_id, track_id, album_id, timestamp)
                batch_rows.append((artist_id, track_id, album_id, ts))

            if batch_rows:
                added = self.db.save_scrobbles_batch(username, batch_rows)
                new_scrobbles += added
                self._update_stats('scrobbles_added', added)

            processed += 1
            if processed % 10 == 0:
                self.db.force_commit()
                print(f"   💾 {new_scrobbles} scrobbles hasta ahora (pág {page})")

            if backfill and batch_rows and page > 10:
                latest = max(r[3] for r in batch_rows)
                overlap = self.db.count_overlap_scrobbles(username, latest, latest + 3600)
                if overlap > len(batch_rows) * 0.8:
                    print(f"   Backfill completado — solapamiento en pág {page}")
                    break

            page += 1

        self.db.force_commit()
        print(f"   ✅ {new_scrobbles} nuevos scrobbles — {processed} páginas")

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self, download_all=False, backfill=False,
            enrich_only=False, limit=1000):
        print("=" * 60)
        print("🚀 ACTUALIZADOR LAST.FM — SCHEMA NORMALIZADO v1")
        print("   (Una tabla por usuario: scrobbles_<username>)")
        print("=" * 60)
        print(f"🗄  DB:      {self.db.db_path}")
        print(f"🧵 Workers: {self.max_workers}")
        print(f"👥 Usuarios: {', '.join(self.users)}")

        start = time.time()
        try:
            if enrich_only:
                self.enrich_entities_parallel(limit=limit)
            else:
                for user in self.users:
                    self.update_user_scrobbles_complete(user, download_all, backfill)
                self.enrich_entities_parallel(limit=limit)

            elapsed = time.time() - start
            print("\n" + "=" * 60)
            print("✅ COMPLETADO")
            print("=" * 60)
            print(f"⏱  {elapsed:.1f}s")
            print(f"   Scrobbles añadidos:  {self.stats['scrobbles_added']}")
            print(f"   Artistas enriquec.:  {self.stats['artists_enriched']}")
            print(f"   Álbumes enriquec.:   {self.stats['albums_enriched']}")
            print(f"   Tracks enriquec.:    {self.stats['tracks_enriched']}")
            print(f"   Errores API:         {self.stats['api_errors']}")
        finally:
            self.db.close()


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Actualizador Last.fm — schema normalizado v1'
    )
    parser.add_argument('--db', default=_DEFAULT_DB,
                        help=f'Ruta a la BD normalizada (default: {_DEFAULT_DB})')
    parser.add_argument('--all',      action='store_true',
                        help='Descargar TODOS los scrobbles desde el inicio')
    parser.add_argument('--backfill', action='store_true',
                        help='Rellenar huecos históricos hacia atrás')
    parser.add_argument('--enrich',   action='store_true',
                        help='Solo enriquecer entidades (sin descargar scrobbles)')
    parser.add_argument('--limit',    type=int, default=1000,
                        help='Máx entidades a enriquecer por tipo (default: 1000)')
    parser.add_argument('--workers',  type=int, default=8,
                        help='Hilos concurrentes (default: 8)')
    parser.add_argument('--proxied',  action='store_true',
                        help='Usar proxies (configura en .env)')
    parser.add_argument('--debug',    action='store_true',
                        help='Logging detallado')
    args = parser.parse_args()

    if args.all and args.backfill:
        print("❌ --all y --backfill son mutuamente excluyentes")
        sys.exit(1)
    if args.workers < 1:
        print("❌ --workers debe ser al menos 1")
        sys.exit(1)
    if args.workers > 20:
        if input("⚠️  Más de 20 workers. ¿Continuar? (y/N): ").lower() != 'y':
            sys.exit(1)

    try:
        updater = MultithreadedLastFMUpdater(
            db_path=args.db,
            debug_mode=args.debug,
            use_proxies=args.proxied,
            max_workers=args.workers,
        )
        updater.run(
            download_all=args.all,
            backfill=args.backfill,
            enrich_only=args.enrich,
            limit=args.limit,
        )
    except KeyboardInterrupt:
        print("\n⚠️  Interrumpido")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

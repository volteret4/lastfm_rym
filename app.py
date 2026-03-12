#!/usr/bin/env python3
"""
mustlisten — Flask backend
Cruza scrobbles de Last.fm con must_hear.db para mostrar qué te falta escuchar.

Uso:
    python app.py --db path/to/must_hear.db --lastfm-api-key KEY [--port 5000]
    python app.py --db path/to/must_hear.db  # usa SOPS / env vars para las credenciales
"""
import os
import re
import json
import time
import sqlite3
import argparse
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from functools import lru_cache
from flask import Flask, jsonify, request, render_template_string, abort

app = Flask(__name__)

# ── Config (se rellena en main()) ─────────────────────────────────────────────
DB_PATH      = None
LFM_API_KEY  = None
CAA          = "https://coverartarchive.org/release-group"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())


def check_heard(user_set: set, artist: str, title: str) -> bool:
    """Fuzzy match idéntico al de html_must_hear.py."""
    a_n = _norm(artist)
    t_n = _norm(title)
    if not t_n:
        return False
    for ua, ut in user_set:
        if not ut:
            continue
        title_match = (
            t_n == ut or
            t_n in ut or
            (ut in t_n and len(ut) >= len(t_n) * 0.8)
        )
        if not title_match:
            continue
        if not a_n or a_n in ua or ua in a_n:
            return True
    return False


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Last.fm API ────────────────────────────────────────────────────────────────

def lfm_get(method: str, params: dict) -> dict:
    base = "https://ws.audioscrobbler.com/2.0/"
    params = {**params, "method": method, "api_key": LFM_API_KEY, "format": "json"}
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "mustlisten/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}



# ── DB queries ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_all_collections() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, slug, name, total_albums, source_type FROM collections ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_collection_albums(slug: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT
            al.id, ar.name AS artist, al.name AS title,
            al.year, al.release_group_mbid AS mbid,
            ca.rank, al.cover_url, al.yt_id,
            al.aoty_critic_score, al.scaruffi_rating
        FROM collection_albums ca
        JOIN collections c  ON c.id  = ca.collection_id
        JOIN albums al       ON al.id = ca.album_id
        JOIN artists ar      ON ar.id = al.artist_id
        WHERE c.slug = ?
        ORDER BY ca.rank ASC NULLS LAST, al.year ASC
    """, (slug,)).fetchall()
    conn.close()
    result = []
    for i, r in enumerate(rows):
        d = dict(r)
        d["number"] = d["rank"] or (i + 1)
        mbid = d.get("mbid", "")
        d["cover"] = d.get("cover_url") or (f"/api/cover?mbid={d['mbid']}" if d.get("mbid") else "")
        result.append(d)
    return result


# ── API endpoints ──────────────────────────────────────────────────────────────

@app.route("/api/collections")
def api_collections():
    return jsonify(get_all_collections())


@app.route("/api/scrobbles")
def api_scrobbles():
    """
    Descarga TODOS los scrobbles del usuario de Last.fm de una vez.
    Devuelve lista de pares [norm_artist, norm_title] para que el cliente
    haga el cruce localmente sin volver a llamar al servidor al cambiar de lista.
    """
    username = request.args.get("user", "").strip()
    if not username:
        return jsonify({"error": "Parámetro 'user' requerido"}), 400
    if not LFM_API_KEY:
        return jsonify({"error": "Last.fm API key no configurada"}), 500

    t0 = time.time()

    # Top albums — paginar SIN límite artificial hasta agotar todas las páginas
    heard_set = set()
    page = 1
    per_page = 200
    total_pages = 1
    while page <= total_pages:
        data = lfm_get("user.getTopAlbums", {
            "user": username, "period": "overall",
            "limit": per_page, "page": page,
        })
        if "error" in data and "topalbums" not in data:
            if page == 1:
                return jsonify({"error": data.get("message", "Usuario no encontrado en Last.fm")}), 404
            break
        albums = data.get("topalbums", {}).get("album", [])
        if not albums:
            break
        for a in albums:
            artist = a.get("artist", {})
            artist = artist.get("name", "") if isinstance(artist, dict) else str(artist)
            title  = a.get("name", "")
            if artist and title:
                heard_set.add((_norm(artist), _norm(title)))
        attrs = data.get("topalbums", {}).get("@attr", {})
        total_pages = int(attrs.get("totalPages", 1))
        page += 1

    # Recent tracks (últimas ~600 para capturar álbumes escuchados muy recientemente
    # que aún no aparecen en el top)
    for rpage in range(1, 4):
        data = lfm_get("user.getRecentTracks", {
            "user": username, "limit": 200, "page": rpage,
        })
        tracks = data.get("recenttracks", {}).get("track", [])
        if not tracks:
            break
        for t in tracks:
            artist = t.get("artist", {})
            artist = artist.get("#text", "") if isinstance(artist, dict) else str(artist)
            album  = t.get("album", {})
            album  = album.get("#text", "") if isinstance(album, dict) else str(album)
            if artist and album:
                heard_set.add((_norm(artist), _norm(album)))

    fetch_ms = round((time.time() - t0) * 1000)
    return jsonify({
        "user":       username,
        "count":      len(heard_set),
        "fetch_ms":   fetch_ms,
        "fetched_at": int(time.time()),
        # Lista de pares [norm_artist, norm_title]
        "heard":      [list(p) for p in heard_set],
    })


@app.route("/api/scrobbles/update")
def api_scrobbles_update():
    """
    Sync incremental: descarga el top completo de nuevo y devuelve solo
    los pares que no estaban en el set existente (enviado por el cliente).
    Usar getRecentTracks con `from` es inviable para usuarios con 300k+ scrobbles
    porque puede suponer miles de páginas. getTopAlbums es la única fuente fiable
    y completa; la diferencia entre dos descargas son los álbumes nuevos.
    """
    username   = request.args.get("user", "").strip()
    if not username:
        return jsonify({"error": "Parámetro 'user' requerido"}), 400
    if not LFM_API_KEY:
        return jsonify({"error": "Last.fm API key no configurada"}), 500

    # El cliente envía los pares que ya tiene como JSON en el body (POST)
    # o como query param `known_count` para saber si algo cambió antes de descargar
    known_count = request.args.get("known_count", "0")
    try:
        known_count = int(known_count)
    except ValueError:
        known_count = 0

    # Primero comprobar si el total de álbumes en LFM cambió
    check = lfm_get("user.getTopAlbums", {"user": username, "period": "overall", "limit": 1, "page": 1})
    if "error" in check and "topalbums" not in check:
        return jsonify({"error": check.get("message", "Error Last.fm")}), 404
    lfm_total = int(check.get("topalbums", {}).get("@attr", {}).get("total", 0))

    if lfm_total <= known_count:
        return jsonify({
            "user":       username,
            "new_count":  0,
            "fetched_at": int(time.time()),
            "heard":      [],
            "lfm_total":  lfm_total,
        })

    # Descargar todo de nuevo para obtener el diff
    new_set = set()
    page = 1
    per_page = 200
    total_pages = 1
    while page <= total_pages:
        data = lfm_get("user.getTopAlbums", {
            "user": username, "period": "overall",
            "limit": per_page, "page": page,
        })
        if "error" in data and "topalbums" not in data:
            break
        albums = data.get("topalbums", {}).get("album", [])
        if not albums:
            break
        for a in albums:
            artist = a.get("artist", {})
            artist = artist.get("name", "") if isinstance(artist, dict) else str(artist)
            title  = a.get("name", "")
            if artist and title:
                new_set.add((_norm(artist), _norm(title)))
        attrs = data.get("topalbums", {}).get("@attr", {})
        total_pages = int(attrs.get("totalPages", 1))
        page += 1

    # Recientes también
    for rpage in range(1, 4):
        data = lfm_get("user.getRecentTracks", {"user": username, "limit": 200, "page": rpage})
        tracks = data.get("recenttracks", {}).get("track", [])
        if not tracks:
            break
        for t in tracks:
            artist = t.get("artist", {})
            artist = artist.get("#text", "") if isinstance(artist, dict) else str(artist)
            album  = t.get("album", {})
            album  = album.get("#text", "") if isinstance(album, dict) else str(album)
            if artist and album:
                new_set.add((_norm(artist), _norm(album)))

    return jsonify({
        "user":       username,
        "new_count":  len(new_set),
        "fetched_at": int(time.time()),
        "lfm_total":  lfm_total,
        # Devolvemos el set completo; el cliente reemplaza su caché
        "heard":      [list(p) for p in new_set],
        "full_replace": True,
    })


@app.route("/api/collection")
def api_collection():
    slug = request.args.get("slug", "").strip()
    if not slug:
        return jsonify({"error": "Parámetro 'slug' requerido"}), 400
    albums = get_collection_albums(slug)
    if not albums:
        return jsonify({"error": f"Colección '{slug}' no encontrada o vacía"}), 404
    result = [{
        "n":      a["number"],
        "artist": a["artist"],
        "title":  a["title"],
        "year":   a.get("year"),
        "mbid":   a.get("mbid", ""),
        "cover":  a.get("cover_url") or (f"/api/cover?mbid={a['mbid']}" if a.get("mbid") else ""),
        "yt_id":  a.get("yt_id", ""),
        "aoty":   a.get("aoty_critic_score"),
        "scaruffi": a.get("scaruffi_rating"),
    } for a in albums]
    return jsonify({"slug": slug, "albums": result})


@app.route("/api/check_user")
def api_check_user():
    """Verifica que el usuario de Last.fm existe."""
    username = request.args.get("user", "").strip()
    if not username:
        return jsonify({"ok": False, "error": "Usuario vacío"}), 400
    data = lfm_get("user.getInfo", {"user": username})
    if "error" in data:
        return jsonify({"ok": False, "error": data.get("message", "Usuario no encontrado")})
    u = data.get("user", {})
    return jsonify({
        "ok":         True,
        "username":   u.get("name", username),
        "realname":   u.get("realname", ""),
        "playcount":  u.get("playcount", 0),
        "image":      next((i["#text"] for i in u.get("image", []) if i.get("size") == "medium"), ""),
    })


@app.route("/api/cover")
def api_cover():
    """
    Proxy para portadas de CoverArtArchive (CAA devuelve redirects que los
    navegadores no siguen en cross-origin). Sigue el redirect y devuelve la imagen.
    """
    mbid = request.args.get("mbid", "").strip()
    if not mbid or not re.match(r'^[a-f0-9-]{36}$', mbid):
        abort(400)
    url = f"{CAA}/{mbid}/front-500"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mustlisten/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data     = r.read()
            ctype    = r.headers.get("Content-Type", "image/jpeg")
        from flask import Response
        resp = Response(data, content_type=ctype)
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception:
        abort(404)


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


# ── HTML Template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>mustlisten</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
/* ── Reset & Variables ─────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:       #0d0d0d;
  --bg2:      #141414;
  --bg3:      #1c1c1c;
  --border:   #2a2a2a;
  --border2:  #333;
  --ink:      #e8e2d8;
  --ink2:     #9a9080;
  --ink3:     #5a5248;
  --accent:   #e8c14a;
  --accent2:  #c8993a;
  --heard-tint: rgba(232,193,74,0.06);
  --missing-tint: rgba(255,255,255,0.02);
  --red:      #c0392b;
  --radius:   2px;
  --mono:     'DM Mono', monospace;
  --serif:    'Playfair Display', Georgia, serif;
  --sans:     'DM Sans', sans-serif;
}

html { font-size: 15px; }
body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--sans);
  font-weight: 300;
  min-height: 100vh;
  line-height: 1.5;
}

/* ── Noise overlay ─────────────────────────────────────────────────── */
body::before {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  opacity: 0.025;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 200px;
}

/* ── Layout ────────────────────────────────────────────────────────── */
.page { position: relative; z-index: 1; max-width: 1400px; margin: 0 auto; padding: 0 2rem 4rem; }

/* ── Header ────────────────────────────────────────────────────────── */
header {
  padding: 3rem 0 2rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 2.5rem;
  display: flex;
  align-items: flex-end;
  gap: 2rem;
}
.logo {
  font-family: var(--serif);
  font-size: 2.6rem;
  font-weight: 900;
  letter-spacing: -0.02em;
  color: var(--ink);
  line-height: 1;
}
.logo em {
  color: var(--accent);
  font-style: italic;
}
.tagline {
  font-family: var(--mono);
  font-size: 0.72rem;
  color: var(--ink3);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 0.2rem;
}

/* ── Search panel ──────────────────────────────────────────────────── */
.search-panel {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 1rem;
  align-items: end;
  margin-bottom: 2rem;
}
label {
  display: block;
  font-family: var(--mono);
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink3);
  margin-bottom: 0.4rem;
}
input, select {
  width: 100%;
  background: var(--bg2);
  border: 1px solid var(--border2);
  color: var(--ink);
  font-family: var(--mono);
  font-size: 0.88rem;
  padding: 0.65rem 0.9rem;
  border-radius: var(--radius);
  outline: none;
  transition: border-color 0.15s;
  -webkit-appearance: none;
}
select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%235a5248' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.8rem center;
  padding-right: 2.2rem;
  cursor: pointer;
}
input:focus, select:focus { border-color: var(--accent2); }
input::placeholder { color: var(--ink3); }
.btn {
  background: var(--accent);
  color: #0d0d0d;
  border: none;
  font-family: var(--mono);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.65rem 1.5rem;
  border-radius: var(--radius);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, transform 0.1s;
}
.btn:hover  { background: var(--accent2); }
.btn:active { transform: translateY(1px); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

/* ── User badge ────────────────────────────────────────────────────── */
#user-badge {
  display: none;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1rem;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 1rem;
}
#user-badge.visible { display: flex; }
#badge-avatar { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; background: var(--bg3); }
#badge-name   { font-family: var(--mono); font-size: 0.82rem; color: var(--ink); }
#badge-plays  { font-family: var(--mono); font-size: 0.72rem; color: var(--ink3); }
#badge-date   { font-family: var(--mono); font-size: 0.68rem; color: var(--ink3); }
.badge-actions { margin-left: auto; display: flex; gap: 0.5rem; align-items: center; }

/* ── Session controls ──────────────────────────────────────────────── */
#session-bar {
  display: none;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 1rem;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius);
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}
#session-bar.visible { display: flex; }
.session-label {
  font-family: var(--mono);
  font-size: 0.68rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink3);
  margin-right: 0.25rem;
}
.btn-sm {
  font-family: var(--mono);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.3rem 0.75rem;
  border-radius: var(--radius);
  cursor: pointer;
  transition: all 0.12s;
  border: 1px solid var(--border2);
  background: var(--bg3);
  color: var(--ink2);
}
.btn-sm:hover { border-color: var(--accent); color: var(--accent); }
.btn-sm.primary { background: var(--accent); border-color: var(--accent); color: #0d0d0d; }
.btn-sm.primary:hover { background: var(--accent2); border-color: var(--accent2); }
#inp-session { display: none; }

/* ── Stats bar ─────────────────────────────────────────────────────── */
#stats-bar {
  display: none;
  align-items: center;
  gap: 2rem;
  padding: 0.9rem 1.2rem;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}
#stats-bar.visible { display: flex; }
.stat { text-align: center; }
.stat-val {
  font-family: var(--serif);
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1;
  color: var(--ink);
}
.stat-val.accent { color: var(--accent); }
.stat-lbl {
  font-family: var(--mono);
  font-size: 0.62rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink3);
  margin-top: 0.2rem;
}
.stat-sep { width: 1px; height: 36px; background: var(--border); align-self: center; }

/* ── Progress bar ──────────────────────────────────────────────────── */
.prog-wrap { flex: 1; min-width: 160px; }
.prog-track {
  height: 4px;
  background: var(--bg3);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 0.5rem;
}
.prog-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(.16,1,.3,1);
  width: 0%;
}

/* ── Filters ───────────────────────────────────────────────────────── */
#filters {
  display: none;
  gap: 0.5rem;
  margin-bottom: 1.2rem;
  flex-wrap: wrap;
  align-items: center;
}
#filters.visible { display: flex; }
.filter-btn {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.35rem 0.8rem;
  background: var(--bg2);
  border: 1px solid var(--border2);
  color: var(--ink2);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all 0.12s;
}
.filter-btn:hover  { border-color: var(--ink3); color: var(--ink); }
.filter-btn.active { background: var(--accent); border-color: var(--accent); color: #0d0d0d; }
.filter-sep { margin-left: auto; }
#sort-select { width: auto; padding: 0.35rem 2rem 0.35rem 0.7rem; font-size: 0.7rem; }

/* ── Grid ──────────────────────────────────────────────────────────── */
#grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

/* ── Album card ────────────────────────────────────────────────────── */
.card {
  position: relative;
  background: var(--bg);
  cursor: pointer;
  overflow: hidden;
  transition: z-index 0s;
  aspect-ratio: 1;
}
.card.heard   { background: var(--heard-tint); }
.card.missing { background: var(--missing-tint); }

.card-cover {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.3s ease, filter 0.3s ease;
  filter: grayscale(20%) brightness(0.85);
}
.card:hover .card-cover {
  transform: scale(1.04);
  filter: grayscale(0%) brightness(1);
}
.card.heard .card-cover   { filter: grayscale(0%)  brightness(0.9); }
.card.missing .card-cover { filter: grayscale(60%) brightness(0.7); }
.card:hover.missing .card-cover { filter: grayscale(20%) brightness(0.85); }

.card-overlay {
  position: absolute; inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0) 55%);
  pointer-events: none;
}
.card-info {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 0.5rem 0.55rem 0.5rem;
}
.card-title {
  font-family: var(--sans);
  font-size: 0.72rem;
  font-weight: 500;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.2;
}
.card-artist {
  font-family: var(--mono);
  font-size: 0.6rem;
  color: rgba(255,255,255,0.55);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 0.1rem;
}
.card-year {
  font-family: var(--mono);
  font-size: 0.58rem;
  color: rgba(255,255,255,0.35);
}
.card-n {
  position: absolute; top: 0.4rem; left: 0.4rem;
  font-family: var(--mono);
  font-size: 0.58rem;
  color: rgba(255,255,255,0.3);
  background: rgba(0,0,0,0.5);
  padding: 0.1rem 0.3rem;
  border-radius: 1px;
}
.badge-heard {
  position: absolute; top: 0.4rem; right: 0.4rem;
  width: 18px; height: 18px;
  background: var(--accent);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}
.badge-heard svg { width: 10px; height: 10px; }

/* ── Cover placeholder ─────────────────────────────────────────────── */
.card-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg3);
}
.card-placeholder svg { width: 28px; height: 28px; opacity: 0.2; }

/* ── Modal ─────────────────────────────────────────────────────────── */
#modal-bg {
  display: none; position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.75);
  backdrop-filter: blur(4px);
  align-items: center; justify-content: center;
  padding: 2rem;
}
#modal-bg.open { display: flex; }
#modal {
  background: var(--bg2);
  border: 1px solid var(--border2);
  border-radius: 4px;
  max-width: 540px; width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  position: relative;
  animation: modalIn 0.2s ease;
}
@keyframes modalIn { from { opacity:0; transform: scale(0.96) translateY(8px); } }
.modal-header {
  display: flex; gap: 1.2rem;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
}
.modal-cover {
  width: 90px; height: 90px; object-fit: cover;
  border-radius: 2px; flex-shrink: 0;
  background: var(--bg3);
}
.modal-meta { flex: 1; min-width: 0; }
.modal-title {
  font-family: var(--serif);
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 1.2;
  color: var(--ink);
}
.modal-artist {
  font-family: var(--mono);
  font-size: 0.78rem;
  color: var(--accent);
  margin-top: 0.25rem;
}
.modal-year {
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--ink3);
  margin-top: 0.15rem;
}
.modal-status {
  display: inline-flex; align-items: center; gap: 0.35rem;
  margin-top: 0.5rem;
  font-family: var(--mono);
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.modal-status.heard   { color: var(--accent); }
.modal-status.missing { color: var(--ink3); }
.modal-body { padding: 1.2rem 1.5rem 1.5rem; }
.modal-desc {
  font-size: 0.85rem;
  color: var(--ink2);
  line-height: 1.65;
  margin-bottom: 1rem;
}
.modal-yt {
  position: relative;
  width: 100%;
  padding-bottom: 56.25%;
  background: #000;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 1rem;
}
.modal-yt iframe {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  border: none;
}
.modal-links { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.modal-link {
  font-family: var(--mono);
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.3rem 0.7rem;
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  color: var(--ink2);
  text-decoration: none;
  transition: all 0.12s;
}
.modal-link:hover { border-color: var(--accent); color: var(--accent); }
.modal-close {
  position: absolute; top: 0.8rem; right: 0.8rem;
  background: none; border: none; color: var(--ink3);
  cursor: pointer; font-size: 1.2rem; line-height: 1;
  padding: 0.2rem 0.4rem;
}
.modal-close:hover { color: var(--ink); }

/* ── Loading / Error ───────────────────────────────────────────────── */
#loading {
  display: none; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 6rem 2rem; gap: 1rem;
  color: var(--ink3);
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
#loading.visible { display: flex; }
.spinner {
  width: 28px; height: 28px;
  border: 2px solid var(--border2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
#error-msg {
  display: none;
  padding: 1rem 1.2rem;
  background: rgba(192,57,43,0.1);
  border: 1px solid rgba(192,57,43,0.3);
  border-radius: var(--radius);
  font-family: var(--mono);
  font-size: 0.8rem;
  color: #e07060;
  margin-bottom: 1rem;
}
#error-msg.visible { display: block; }

/* ── Empty state ───────────────────────────────────────────────────── */
#empty {
  display: none;
  text-align: center;
  padding: 5rem 2rem;
  color: var(--ink3);
}
#empty.visible { display: block; }
#empty p { font-family: var(--mono); font-size: 0.78rem; letter-spacing: 0.1em; text-transform: uppercase; }

/* ── Responsive ────────────────────────────────────────────────────── */
@media (max-width: 700px) {
  .search-panel { grid-template-columns: 1fr; }
  #grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
  header { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <header>
    <div>
      <div class="logo">must<em>listen</em></div>
    </div>
    <div>
      <div class="tagline">Tu historial · Las listas · Lo que te falta</div>
    </div>
  </header>

  <!-- Search -->
  <div class="search-panel">
    <div>
      <label for="inp-user">Usuario Last.fm</label>
      <input id="inp-user" type="text" placeholder="tu_usuario" autocomplete="off" spellcheck="false">
    </div>
    <div>
      <label for="inp-coll">Lista / Colección</label>
      <select id="inp-coll"><option value="">Cargando...</option></select>
    </div>
    <div>
      <button class="btn" id="btn-go" disabled>Buscar</button>
    </div>
  </div>

  <!-- User badge -->
  <div id="user-badge">
    <img id="badge-avatar" src="" alt="">
    <span id="badge-name"></span>
    <span id="badge-plays"></span>
    <span id="badge-date"></span>
    <div class="badge-actions">
      <button class="btn-sm" id="btn-save-session" style="display:none">↓ Guardar sesión</button>
      <button class="btn-sm" id="btn-sync-session" style="display:none">↻ Sincronizar</button>
    </div>
  </div>

  <!-- Session bar (cargar sesión guardada) -->
  <div id="session-bar">
    <span class="session-label">Sesión guardada</span>
    <span id="session-info"></span>
    <button class="btn-sm primary" id="btn-load-session">Cargar</button>
    <button class="btn-sm" id="btn-discard-session">✕</button>
  </div>
  <input type="file" id="inp-session" accept=".json">

  <!-- Error -->
  <div id="error-msg"></div>

  <!-- Loading -->
  <div id="loading">
    <div class="spinner"></div>
    <span id="loading-text">Cargando scrobbles...</span>
  </div>

  <!-- Stats -->
  <div id="stats-bar">
    <div class="stat">
      <div class="stat-val" id="s-total">—</div>
      <div class="stat-lbl">Total</div>
    </div>
    <div class="stat-sep"></div>
    <div class="stat">
      <div class="stat-val accent" id="s-heard">—</div>
      <div class="stat-lbl">Escuchados</div>
    </div>
    <div class="stat-sep"></div>
    <div class="stat">
      <div class="stat-val" id="s-missing">—</div>
      <div class="stat-lbl">Pendientes</div>
    </div>
    <div class="stat-sep"></div>
    <div class="stat">
      <div class="stat-val" id="s-pct">—</div>
      <div class="stat-lbl">Completado</div>
    </div>
    <div class="stat-sep"></div>
    <div class="prog-wrap">
      <div class="stat-lbl">Progreso</div>
      <div class="prog-track"><div class="prog-fill" id="prog-fill"></div></div>
    </div>
  </div>

  <!-- Filters -->
  <div id="filters">
    <button class="filter-btn active" data-filter="all">Todos</button>
    <button class="filter-btn" data-filter="missing">Pendientes</button>
    <button class="filter-btn" data-filter="heard">Escuchados</button>
    <div class="filter-sep"></div>
    <label for="sort-select" style="margin:0">
      <select id="sort-select">
        <option value="rank">Orden lista</option>
        <option value="year_asc">Año ↑</option>
        <option value="year_desc">Año ↓</option>
        <option value="artist">Artista A–Z</option>
      </select>
    </label>
  </div>

  <!-- Grid -->
  <div id="grid"></div>
  <div id="empty"><p>No hay álbumes para mostrar</p></div>

</div><!-- .page -->

<!-- Modal -->
<div id="modal-bg">
  <div id="modal">
    <button class="modal-close" id="modal-close">✕</button>
    <div class="modal-header">
      <img class="modal-cover" id="m-cover" src="" alt="">
      <div class="modal-meta">
        <div class="modal-title"  id="m-title"></div>
        <div class="modal-artist" id="m-artist"></div>
        <div class="modal-year"   id="m-year"></div>
        <div class="modal-status" id="m-status"></div>
      </div>
    </div>
    <div class="modal-body">
      <div class="modal-yt" id="m-yt" style="display:none"></div>
      <div class="modal-desc" id="m-desc"></div>
      <div class="modal-links" id="m-links"></div>
    </div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let allAlbums    = [];
let heardCache   = null; // { user, pairs:[[a,t],...], count, fetched_at }
let collCache    = {};   // slug → albums[]
let activeFilter = 'all';
let activeSort   = 'rank';
let loadedUser   = null;
let pendingSession = null; // sesión cargada de fichero, esperando confirmación

// ── DOM refs ───────────────────────────────────────────────────────────────
const inpUser    = document.getElementById('inp-user');
const inpColl    = document.getElementById('inp-coll');
const btnGo      = document.getElementById('btn-go');
const grid       = document.getElementById('grid');
const loading    = document.getElementById('loading');
const loadTxt    = document.getElementById('loading-text');
const errMsg     = document.getElementById('error-msg');
const statsBar   = document.getElementById('stats-bar');
const filtersEl  = document.getElementById('filters');
const emptyEl    = document.getElementById('empty');
const userBadge  = document.getElementById('user-badge');
const sessionBar = document.getElementById('session-bar');
const inpSession = document.getElementById('inp-session');

// ── Init: load collections ─────────────────────────────────────────────────
(async () => {
  try {
    const cols = await fetch('/api/collections').then(r => r.json());
    inpColl.innerHTML = cols.map(c =>
      `<option value="${c.slug}">${c.name}${c.total_albums ? ' ('+c.total_albums+')' : ''}</option>`
    ).join('');
    btnGo.disabled = false;
  } catch(e) {
    inpColl.innerHTML = '<option value="">Error cargando colecciones</option>';
  }
})();

// ── User validation (debounced) ────────────────────────────────────────────
let userTimer = null;
inpUser.addEventListener('input', () => {
  clearTimeout(userTimer);
  if (heardCache && inpUser.value.trim().toLowerCase() !== loadedUser) {
    heardCache = null; loadedUser = null;
    hideUserBadge();
  }
  userTimer = setTimeout(() => validateUser(inpUser.value.trim()), 700);
});

async function validateUser(u) {
  if (!u || u.length < 2) return;
  const data = await fetch(`/api/check_user?user=${encodeURIComponent(u)}`).then(r=>r.json()).catch(()=>null);
  if (!data || !data.ok) return;
  showUserBadge(data.username, data.image,
    Number(data.playcount).toLocaleString() + ' scrobbles totales', null);
}

function showUserBadge(username, img, plays, fetchedAt) {
  document.getElementById('badge-avatar').src         = img || '';
  document.getElementById('badge-name').textContent   = username;
  document.getElementById('badge-plays').textContent  = plays || '';
  document.getElementById('badge-date').textContent   =
    fetchedAt ? '· descargado ' + new Date(fetchedAt * 1000).toLocaleDateString() : '';
  userBadge.classList.add('visible');
}
function hideUserBadge() { userBadge.classList.remove('visible'); }

// ── Session: guardar ───────────────────────────────────────────────────────
document.getElementById('btn-save-session').addEventListener('click', () => {
  if (!heardCache) return;
  const blob = new Blob([JSON.stringify({
    version:    1,
    user:       heardCache.user,
    count:      heardCache.count,
    fetched_at: heardCache.fetched_at,
    heard:      heardCache.pairs,
  }, null, 0)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = `mustlisten_${heardCache.user}_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
});

// ── Session: cargar fichero ────────────────────────────────────────────────
// Botón en la search panel para abrir el selector
const btnImport = document.createElement('button');
btnImport.className = 'btn-sm';
btnImport.textContent = '↑ Cargar sesión';
btnImport.style.cssText = 'margin-left:0.5rem';
btnImport.addEventListener('click', () => inpSession.click());
document.querySelector('.search-panel').appendChild(btnImport);

inpSession.addEventListener('change', async e => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    if (!data.heard || !data.user) throw new Error('Formato inválido');
    pendingSession = data;
    document.getElementById('session-info').textContent =
      `${data.user} · ${data.heard.length.toLocaleString()} álbumes · ${new Date(data.fetched_at * 1000).toLocaleDateString()}`;
    sessionBar.classList.add('visible');
    inpUser.value = data.user;
  } catch(err) {
    showError('Fichero de sesión no válido: ' + err.message);
  }
  e.target.value = '';
});

document.getElementById('btn-load-session').addEventListener('click', async () => {
  if (!pendingSession) return;
  loadHeardCache(pendingSession);
  sessionBar.classList.remove('visible');
  pendingSession = null;
  // Si hay colección seleccionada, aplicar directamente
  if (inpColl.value) {
    await ensureCollection(inpColl.value);
    applyCollection();
  }
});

document.getElementById('btn-discard-session').addEventListener('click', () => {
  pendingSession = null;
  sessionBar.classList.remove('visible');
});

// ── Session: sync incremental ──────────────────────────────────────────────
document.getElementById('btn-sync-session').addEventListener('click', async () => {
  if (!heardCache) return;
  const btn = document.getElementById('btn-sync-session');
  btn.disabled = true;
  btn.textContent = '↻ Sincronizando...';
  try {
    const knownCount = heardCache.count || 0;
    const url = `/api/scrobbles/update?user=${encodeURIComponent(heardCache.user)}&known_count=${knownCount}`;
    const data = await fetch(url).then(r => r.json());
    if (data.error) { showError(data.error); return; }

    if (data.new_count === 0) {
      btn.textContent = '✓ Al día';
      btn.disabled = false;
      return;
    }

    // El servidor devuelve el set completo actualizado
    if (data.full_replace) {
      const prev = heardCache.count;
      heardCache.pairs      = data.heard;
      heardCache.count      = data.heard.length;
      heardCache.fetched_at = data.fetched_at;
      const added = heardCache.count - prev;
      document.getElementById('badge-plays').textContent =
        heardCache.count.toLocaleString() + ' álbumes' + (added > 0 ? ` (+${added} nuevos)` : '');
      document.getElementById('badge-date').textContent =
        '· actualizado ' + new Date(data.fetched_at * 1000).toLocaleDateString();
      if (inpColl.value && collCache[inpColl.value]) applyCollection();
      btn.textContent = added > 0 ? `✓ +${added} nuevos` : '✓ Al día';
    }
  } catch(e) {
    showError('Error sincronizando: ' + e.message);
    btn.textContent = '↻ Sincronizar';
  } finally {
    btn.disabled = false;
  }
});

function loadHeardCache(data) {
  heardCache = {
    user:       data.user,
    pairs:      data.heard,
    count:      data.heard.length,
    fetched_at: data.fetched_at || 0,
  };
  loadedUser = data.user.toLowerCase();
  inpUser.value = data.user;
  showUserBadge(data.user, '', data.heard.length.toLocaleString() + ' álbumes en sesión',
    data.fetched_at);
  document.getElementById('btn-save-session').style.display = '';
  document.getElementById('btn-sync-session').style.display = '';
  document.getElementById('btn-sync-session').textContent   = '↻ Sincronizar';
}

// ── Fuzzy match (= check_heard Python) ────────────────────────────────────
function norm(s) { return (s || '').toLowerCase().replace(/[^\w]/g, ''); }

function checkHeard(pairs, artist, title) {
  const aN = norm(artist), tN = norm(title);
  if (!tN) return false;
  for (const [uA, uT] of pairs) {
    if (!uT) continue;
    const tm = (tN === uT) || tN.includes(uT) || (uT.includes(tN) && uT.length >= tN.length * 0.8);
    if (!tm) continue;
    if (!aN || aN.includes(uA) || uA.includes(aN)) return true;
  }
  return false;
}

// ── Main search ────────────────────────────────────────────────────────────
btnGo.addEventListener('click', doSearch);
inpUser.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
inpColl.addEventListener('change', () => { if (heardCache) applyCollection(); });

async function doSearch() {
  const user = inpUser.value.trim();
  const slug = inpColl.value;
  if (!user || !slug) return;

  hideError();
  btnGo.disabled = true;

  try {
    // ── Scrobbles (solo si no hay caché o cambió el usuario) ───────────────
    if (!heardCache || loadedUser !== user.toLowerCase()) {
      showLoading('Descargando scrobbles de Last.fm...');
      hideResults();
      const sData = await fetch(`/api/scrobbles?user=${encodeURIComponent(user)}`).then(r => r.json());
      if (sData.error) { showError(sData.error); return; }
      loadHeardCache(sData);
    }

    // ── Colección (con caché local) ────────────────────────────────────────
    showLoading('Cargando colección...');
    await ensureCollection(slug);
    applyCollection();

  } catch(e) {
    showError('Error de red: ' + e.message);
  } finally {
    hideLoading();
    btnGo.disabled = false;
  }
}

async function ensureCollection(slug) {
  if (!collCache[slug]) {
    const cData = await fetch(`/api/collection?slug=${encodeURIComponent(slug)}`).then(r => r.json());
    if (cData.error) throw new Error(cData.error);
    collCache[slug] = cData.albums;
  }
}

function applyCollection() {
  const slug = inpColl.value;
  const raw  = collCache[slug];
  if (!raw || !heardCache) return;

  allAlbums = raw.map(a => ({ ...a, heard: checkHeard(heardCache.pairs, a.artist, a.title) }));

  const heardN   = allAlbums.filter(a => a.heard).length;
  const missingN = allAlbums.length - heardN;
  const pct      = allAlbums.length ? Math.round(heardN / allAlbums.length * 100) : 0;

  document.getElementById('s-total').textContent   = allAlbums.length;
  document.getElementById('s-heard').textContent   = heardN;
  document.getElementById('s-missing').textContent = missingN;
  document.getElementById('s-pct').textContent     = pct + '%';
  setTimeout(() => { document.getElementById('prog-fill').style.width = pct + '%'; }, 50);

  statsBar.classList.add('visible');
  filtersEl.classList.add('visible');
  renderGrid();
}

// ── Grid ───────────────────────────────────────────────────────────────────
function renderGrid() {
  let f = [...allAlbums];
  if (activeFilter === 'missing') f = f.filter(a => !a.heard);
  if (activeFilter === 'heard')   f = f.filter(a =>  a.heard);
  if (activeSort === 'year_asc')  f.sort((a,b) => (a.year||0)-(b.year||0));
  if (activeSort === 'year_desc') f.sort((a,b) => (b.year||0)-(a.year||0));
  if (activeSort === 'artist')    f.sort((a,b) => a.artist.localeCompare(b.artist));
  if (activeSort === 'rank')      f.sort((a,b) => (a.n||0)-(b.n||0));

  if (!f.length) { grid.innerHTML = ''; emptyEl.classList.add('visible'); return; }
  emptyEl.classList.remove('visible');
  grid.innerHTML = f.map(a => cardHTML(a)).join('');

  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const img = e.target.querySelector('img[data-src]');
      if (img) { img.src = img.dataset.src; img.removeAttribute('data-src'); }
      obs.unobserve(e.target);
    });
  }, { rootMargin: '300px' });

  grid.querySelectorAll('.card').forEach(c => {
    obs.observe(c);
    c.addEventListener('click', () => openModal(parseInt(c.dataset.idx)));
  });
}

function cardHTML(a) {
  const cls  = a.heard ? 'heard' : 'missing';
  const idx  = allAlbums.indexOf(a);
  const imgEl = a.cover
    ? `<img class="card-cover" data-src="${escH(a.cover)}" src="" alt="${escH(a.title)}"
          onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    : '';
  const ph = `<div class="card-placeholder" ${a.cover ? 'style="display:none"' : ''}>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>
    </svg></div>`;
  const tick = a.heard
    ? `<div class="badge-heard"><svg viewBox="0 0 12 9" fill="none" stroke="#0d0d0d" stroke-width="2"><path d="M1 4l3.5 3.5L11 1"/></svg></div>`
    : '';
  return `<div class="card ${cls}" data-idx="${idx}">
    ${imgEl}${ph}
    <div class="card-overlay"></div>
    <div class="card-n">${a.n}</div>${tick}
    <div class="card-info">
      <div class="card-title">${escH(a.title)}</div>
      <div class="card-artist">${escH(a.artist)}</div>
      ${a.year ? `<div class="card-year">${a.year}</div>` : ''}
    </div>
  </div>`;
}

document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    renderGrid();
  });
});
document.getElementById('sort-select').addEventListener('change', e => {
  activeSort = e.target.value; renderGrid();
});

// ── Modal ──────────────────────────────────────────────────────────────────
function openModal(idx) {
  const a = allAlbums[idx];
  if (!a) return;

  document.getElementById('m-cover').src             = a.cover || '';
  document.getElementById('m-title').textContent      = a.title;
  document.getElementById('m-artist').textContent     = a.artist;
  document.getElementById('m-year').textContent       = a.year || '';
  document.getElementById('m-desc').textContent       = a.desc_lfm_album || a.desc_mb_album || a.desc_lfm_artist || '';

  const st = document.getElementById('m-status');
  if (a.heard) {
    st.className = 'modal-status heard';
    st.innerHTML = `<svg width="10" height="10" viewBox="0 0 12 9" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4l3.5 3.5L11 1"/></svg> Escuchado`;
  } else {
    st.className = 'modal-status missing';
    st.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg> Pendiente`;
  }

  // YouTube embed
  const ytDiv = document.getElementById('m-yt');
  if (a.yt_id) {
    ytDiv.style.display = '';
    ytDiv.innerHTML = `<iframe src="https://www.youtube.com/embed/${escH(a.yt_id)}?rel=0"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowfullscreen></iframe>`;
  } else {
    ytDiv.style.display = 'none';
    ytDiv.innerHTML = '';
  }

  // Links
  const links = [];
  if (a.mbid)  links.push(`<a class="modal-link" href="https://musicbrainz.org/release-group/${a.mbid}" target="_blank">MusicBrainz</a>`);
  if (a.yt_id) links.push(`<a class="modal-link" href="https://youtube.com/watch?v=${escH(a.yt_id)}" target="_blank">YouTube ↗</a>`);
  document.getElementById('m-links').innerHTML = links.join('');

  document.getElementById('modal-bg').classList.add('open');
  document.body.style.overflow = 'hidden';
}

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-bg').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-bg')) closeModal();
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

function closeModal() {
  // Parar YouTube al cerrar
  const ytDiv = document.getElementById('m-yt');
  ytDiv.innerHTML = '';
  ytDiv.style.display = 'none';
  document.getElementById('modal-bg').classList.remove('open');
  document.body.style.overflow = '';
}

// ── UI helpers ─────────────────────────────────────────────────────────────
function showLoading(msg) { loadTxt.textContent = msg || 'Cargando...'; loading.classList.add('visible'); }
function hideLoading()    { loading.classList.remove('visible'); }
function showError(msg)   { errMsg.textContent = msg; errMsg.classList.add('visible'); }
function hideError()      { errMsg.classList.remove('visible'); }
function hideResults()    {
  allAlbums = []; grid.innerHTML = '';
  statsBar.classList.remove('visible');
  filtersEl.classList.remove('visible');
  emptyEl.classList.remove('visible');
}
function escH(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>"""

# ── CLI / entrypoint ──────────────────────────────────────────────────────────

def resolve_lastfm_key(cli_key: str | None) -> str:
    if cli_key:
        return cli_key
    k = os.environ.get("LASTFM_API_KEY", "")
    if k:
        return k
    # SOPS
    enc = Path(".encrypted.env")
    if enc.exists():
        try:
            return subprocess.check_output(
                ["sops", "-d", "--extract", '["LASTFM_API_KEY"]', str(enc)],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            pass
    return ""


def main():
    global DB_PATH, LFM_API_KEY

    parser = argparse.ArgumentParser(description="mustlisten — web app")
    parser.add_argument("--db",             required=True, help="Ruta a must_hear.db")
    parser.add_argument("--lastfm-api-key", default=None,  help="Last.fm API key")
    parser.add_argument("--port",           type=int, default=5000)
    parser.add_argument("--host",           default="127.0.0.1")
    parser.add_argument("--debug",          action="store_true")
    args = parser.parse_args()

    DB_PATH     = args.db
    LFM_API_KEY = resolve_lastfm_key(args.lastfm_api_key)

    if not Path(DB_PATH).exists():
        print(f"❌ DB no encontrada: {DB_PATH}")
        raise SystemExit(1)
    if not LFM_API_KEY:
        print("⚠  Sin Last.fm API key — las búsquedas fallarán.")
        print("   Usa --lastfm-api-key KEY, env LASTFM_API_KEY, o .encrypted.env")

    print(f"🎵 mustlisten → http://{args.host}:{args.port}")
    print(f"🗄  DB: {DB_PATH}")
    print(f"🔑 Last.fm API key: {'✓' if LFM_API_KEY else '✗ no encontrada'}")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

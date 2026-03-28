"""
html_rym_genre_mermaid.py — Standalone RYM Genre Tree visualizer.

Generates docs/must_hear/rym_genre_tree.html (or --output path).

Usage:
    python3 html_rym_genre_mermaid.py --mh-db db/must_hear_rym_new.db
    python3 html_rym_genre_mermaid.py --mh-db db/must_hear_rym_new.db \\
        --genres-json docs/must_hear/rym_charts/rym_genres.json \\
        --output docs/must_hear/rym_genre_tree.html

Can also be called from html_must_hear.py via --rym-genre-mermaid.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────

def _chart_slug_from_genre(genre_slug: str) -> str:
    return "rym_chart_all_time_" + genre_slug.replace("-", "_")


def _genre_slug_from_chart(chart_slug: str) -> str:
    return chart_slug.replace("rym_chart_all_time_", "").replace("_", "-")


# ── data gathering ─────────────────────────────────────────────────────────

def load_genre_tree(genres_json: Path) -> list[dict]:
    return json.loads(genres_json.read_text(encoding="utf-8"))


def get_scraped_collections(mh_conn: sqlite3.Connection) -> dict[str, dict]:
    """Returns {collection_slug: {total, avg_pct}} for all scraped RYM chart collections."""
    rows = mh_conn.execute("""
        SELECT c.slug, COUNT(ca.album_id) AS total
        FROM collections c
        JOIN collection_albums ca ON ca.collection_id = c.id
        WHERE c.slug LIKE 'rym_chart_all_time_%'
        GROUP BY c.id
    """).fetchall()
    return {r[0]: {"total": r[1]} for r in rows}


def get_top_albums_per_collection(
    mh_conn: sqlite3.Connection,
    collection_slugs: list[str],
    n: int = 5,
) -> dict[str, list[dict]]:
    """Returns {collection_slug: [{artist, title, year, mbid, yt_id}]}."""
    result: dict[str, list[dict]] = {}
    for slug in collection_slugs:
        rows = mh_conn.execute("""
            SELECT ar.name, al.name, al.year, al.release_group_mbid, al.yt_id
            FROM collection_albums ca
            JOIN collections c  ON c.id  = ca.collection_id
            JOIN albums al      ON al.id = ca.album_id
            JOIN artists ar     ON ar.id = al.artist_id
            WHERE c.slug = ?
            ORDER BY ca.rank ASC NULLS LAST
            LIMIT ?
        """, (slug, n)).fetchall()
        if rows:
            result[slug] = [
                {"artist": r[0], "title": r[1], "year": r[2] or "",
                 "mbid": r[3] or "", "yt_id": r[4] or ""}
                for r in rows
            ]
    return result


def build_panel_data(
    genre_tree: list[dict],
    scraped: dict[str, dict],
    top_albums: dict[str, list[dict]],
) -> dict[str, dict]:
    """Build {genre_slug: {name, desc, chart_slug, albums: [...]}} for all genres."""
    data: dict[str, dict] = {}

    def walk(nodes: list[dict]) -> None:
        for n in nodes:
            slug = n["slug"]
            cslug = _chart_slug_from_genre(slug)
            entry: dict = {
                "name":       n["name"],
                "desc":       n.get("desc", ""),
                "chart_slug": cslug if cslug in scraped else "",
                "total":      scraped.get(cslug, {}).get("total", 0),
                "albums":     top_albums.get(cslug, []),
            }
            data[slug] = entry
            walk(n.get("subgenres", []))

    walk(genre_tree)
    return data


# ── HTML rendering ─────────────────────────────────────────────────────────

def render_html(
    genre_tree: list[dict],
    panel_data: dict[str, dict],
    scraped_slugs: set[str],
    scraped_map: dict[str, dict],
    generated: str,
) -> str:
    # ── compact tree for JS (slug, name, children) ──────────────────────
    def _compact(nodes: list[dict]) -> list[dict]:
        return [{"s": n["slug"], "n": n["name"],
                 "c": _compact(n.get("subgenres", []))} for n in nodes]

    compact_json = json.dumps(_compact(genre_tree), ensure_ascii=False, separators=(",", ":"))

    # chart lookup for JS: {collection_slug: {total}}
    charts_json = json.dumps(
        {cs: {"total": scraped_map[cs]["total"]}
         for cs in scraped_map},
        ensure_ascii=False, separators=(",", ":"),
    )

    # panel data JSON (descriptions + albums)
    panel_json = json.dumps(panel_data, ensure_ascii=False, separators=(",", ":"))

    n_scraped = len(scraped_slugs)
    n_total   = sum(1 + _count_all(g) for g in genre_tree)
    main_genres = [{"slug": g["slug"], "name": g["name"],
                    "scraped": _chart_slug_from_genre(g["slug"]) in scraped_slugs}
                   for g in genre_tree]

    sidebar_html = ""
    for g in main_genres:
        cls  = "mg-link scraped" if g["scraped"] else "mg-link"
        dot  = '<span class="dot scraped-dot"></span>' if g["scraped"] else '<span class="dot"></span>'
        sidebar_html += (
            f'<div class="{cls}" data-slug="{g["slug"]}" '
            f'onclick="selectGenre(\'{g["slug"]}\',\'{g["name"].replace(chr(39), "")}\')"> '
            f'{dot}{g["name"]}</div>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RYM Genre Tree</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="icon" type="image/png" href="/images/discount.png" />
<script defer src="https://cloud.umami.is/script.js" data-website-id="5d84fd6c-0760-4a0c-a2d0-ffabb82179f5"></script>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
  :root {{
    --bg:#0a0a0a; --surface:#111; --border:#1e1e1e;
    --accent:#c9a227; --muted:#555; --text:#e0e0e0; --header-h:52px;
    --sidebar-w:220px; --panel-w:360px;
  }}
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif;
          min-height:100vh; overflow-x:hidden; }}
  /* ── header ── */
  header {{
    position:fixed; top:0; left:0; right:0; z-index:200; height:var(--header-h);
    background:rgba(10,10,10,.97); backdrop-filter:blur(12px);
    border-bottom:1px solid var(--border);
    display:flex; align-items:center; gap:14px; padding:0 24px;
  }}
  .site-label {{ font-family:'DM Mono',monospace; font-size:.6rem; letter-spacing:.18em;
                 text-transform:uppercase; color:var(--muted); }}
  h1 {{ font-family:'Bebas Neue',sans-serif; font-size:1.6rem; letter-spacing:.06em;
        line-height:1; color:var(--accent); white-space:nowrap; }}
  .header-meta {{ font-family:'DM Mono',monospace; font-size:.6rem; color:var(--muted); margin-left:auto; }}
  .header-nav-link {{
    font-family:'DM Mono',monospace; font-size:.58rem; letter-spacing:.1em;
    text-transform:uppercase; padding:4px 10px; border-radius:3px;
    border:1px solid var(--border); color:var(--muted); text-decoration:none; transition:all .12s;
  }}
  .header-nav-link:hover {{ border-color:var(--accent); color:var(--accent); }}
  /* ── layout ── */
  #layout {{
    display:flex; margin-top:var(--header-h); height:calc(100vh - var(--header-h));
  }}
  /* ── sidebar ── */
  #sidebar {{
    width:var(--sidebar-w); flex-shrink:0; overflow-y:auto;
    border-right:1px solid var(--border); padding:12px 0;
  }}
  .sidebar-label {{
    font-family:'DM Mono',monospace; font-size:.55rem; letter-spacing:.2em;
    text-transform:uppercase; color:var(--muted); padding:6px 14px 10px;
  }}
  .mg-link {{
    display:flex; align-items:center; gap:8px;
    padding:7px 14px; font-size:.83rem; cursor:pointer;
    transition:background .1s, color .1s; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis;
  }}
  .mg-link:hover {{ background:var(--surface); color:var(--accent); }}
  .mg-link.active {{ background:var(--surface); color:var(--accent); }}
  .mg-link.scraped {{ color:var(--text); }}
  .mg-link:not(.scraped) {{ color:var(--muted); }}
  .dot {{
    flex-shrink:0; width:6px; height:6px; border-radius:50%;
    background:var(--border);
  }}
  .dot.scraped-dot {{ background:var(--accent); }}
  /* ── diagram area ── */
  #diagram-wrap {{
    flex:1; overflow:auto; padding:20px; position:relative;
    transition:margin-right .2s;
  }}
  #diagram-wrap.panel-open {{ margin-right:var(--panel-w); }}
  #diag-placeholder {{
    display:flex; align-items:center; justify-content:center;
    height:60%; font-family:'DM Mono',monospace; font-size:.75rem;
    color:#333; text-align:center; line-height:2;
  }}
  #diag-container {{ min-width:100%; }}
  #diag-container svg {{ max-width:100%; height:auto; }}
  #diag-status {{
    font-family:'DM Mono',monospace; font-size:.65rem; color:var(--muted);
    padding:4px 0 16px;
  }}
  /* ── side panel ── */
  #panel {{
    position:fixed; top:var(--header-h); right:0; bottom:0;
    width:var(--panel-w); background:var(--surface);
    border-left:1px solid var(--border);
    transform:translateX(100%); transition:transform .2s;
    overflow-y:auto; z-index:150; padding:18px;
  }}
  #panel.open {{ transform:translateX(0); }}
  .panel-close {{
    background:none; border:none; color:var(--muted); cursor:pointer;
    font-size:.8rem; float:right; padding:2px 6px;
    transition:color .12s;
  }}
  .panel-close:hover {{ color:var(--accent); }}
  .panel-slug {{
    font-family:'DM Mono',monospace; font-size:.55rem; color:var(--muted);
    letter-spacing:.1em; margin-bottom:4px;
  }}
  .panel-title {{
    font-family:'Bebas Neue',sans-serif; font-size:1.5rem; color:var(--accent);
    letter-spacing:.04em; margin-bottom:8px; line-height:1.1;
  }}
  .panel-desc {{
    font-size:.82rem; color:var(--muted); line-height:1.5;
    margin-bottom:14px; border-bottom:1px solid var(--border); padding-bottom:14px;
  }}
  .panel-chart-link {{
    display:inline-block; margin-bottom:14px;
    font-family:'DM Mono',monospace; font-size:.6rem; letter-spacing:.08em;
    padding:4px 10px; border:1px solid var(--accent); border-radius:3px;
    color:var(--accent); text-decoration:none; transition:all .12s;
  }}
  .panel-chart-link:hover {{ background:var(--accent); color:#000; }}
  .panel-section-label {{
    font-family:'DM Mono',monospace; font-size:.58rem; letter-spacing:.15em;
    text-transform:uppercase; color:var(--muted); margin-bottom:8px;
  }}
  .panel-album {{
    margin-bottom:14px; border-bottom:1px solid var(--border); padding-bottom:14px;
  }}
  .panel-album:last-child {{ border-bottom:none; }}
  .album-meta {{
    font-size:.8rem; margin-bottom:6px;
    display:flex; justify-content:space-between; align-items:baseline;
  }}
  .album-name {{ font-weight:500; }}
  .album-year {{ font-family:'DM Mono',monospace; font-size:.65rem; color:var(--muted); }}
  .album-artist {{ font-size:.75rem; color:var(--muted); margin-bottom:6px; }}
  .yt-embed {{
    position:relative; padding-bottom:56.25%; height:0; overflow:hidden;
    border-radius:3px; background:#000;
  }}
  .yt-embed iframe {{
    position:absolute; top:0; left:0; width:100%; height:100%;
    border:0;
  }}
  .yt-placeholder {{
    position:relative; padding-bottom:56.25%; height:0; overflow:hidden;
    border-radius:3px; background:#0a0a0a; border:1px solid var(--border);
    cursor:pointer;
  }}
  .yt-placeholder-inner {{
    position:absolute; inset:0; display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:6px;
    font-family:'DM Mono',monospace; font-size:.6rem; color:var(--muted);
  }}
  .yt-play-btn {{
    width:36px; height:36px; background:var(--accent); border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:.9rem; color:#000;
  }}
  #panel-no-chart {{
    font-family:'DM Mono',monospace; font-size:.65rem; color:#333;
    padding:20px 0; text-align:center;
  }}
  /* ── legend ── */
  .legend {{
    display:flex; gap:14px; padding:8px 14px 4px;
    border-bottom:1px solid var(--border); flex-wrap:wrap;
  }}
  .legend-item {{
    display:flex; align-items:center; gap:5px;
    font-family:'DM Mono',monospace; font-size:.55rem; color:var(--muted);
  }}
  .legend-swatch {{
    width:10px; height:10px; border-radius:2px; flex-shrink:0;
  }}
  @media (max-width:768px) {{
    :root {{ --sidebar-w:0px; --panel-w:100vw; }}
    #sidebar {{ display:none; }}
    #diag-container svg {{ min-width:600px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="site-label">
    <a href="index.html" style="color:var(--muted);text-decoration:none;letter-spacing:.2em">&larr; RYM Charts</a>
  </div>
  <h1>RYM Genre Tree</h1>
  <div class="header-meta">{n_scraped}&thinsp;/&thinsp;{n_total} géneros scrapeados</div>
  <a class="header-nav-link" href="../index_alternativo.html">Explorador ↗</a>
</header>

<div id="layout">
  <aside id="sidebar">
    <div class="sidebar-label">Géneros principales</div>
    <div class="legend">
      <div class="legend-item">
        <div class="legend-swatch" style="background:#c9a227"></div>principal
      </div>
      <div class="legend-item">
        <div class="legend-swatch" style="background:#2a1e00;border:1px solid #5c4400"></div>con chart
      </div>
      <div class="legend-item">
        <div class="legend-swatch" style="background:#111;border:1px solid #333"></div>sin chart
      </div>
    </div>
{sidebar_html}  </aside>

  <div id="diagram-wrap">
    <div id="diag-status"></div>
    <div id="diag-container">
      <div id="diag-placeholder">
        ← Selecciona un género de la lista<br>para ver su árbol de subgéneros
      </div>
    </div>
  </div>

  <aside id="panel">
    <button class="panel-close" onclick="closePanel()">✕</button>
    <div id="panel-content"></div>
  </aside>
</div>

<script>
mermaid.initialize({{
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'dark',
  themeVariables: {{
    darkMode: true,
    primaryColor: '#111', primaryTextColor: '#e0e0e0',
    primaryBorderColor: '#333', lineColor: '#444',
    secondaryColor: '#1a1a1a', tertiaryColor: '#0a0a0a',
    edgeLabelBackground: '#0a0a0a',
  }},
  flowchart: {{ curve: 'basis', htmlLabels: true, useMaxWidth: false }},
}});

const TREE_IDX = {{}};
const CHARTS   = {charts_json};
const PANEL_DATA = {panel_json};

(function buildIdx(nodes) {{
  for (const n of nodes) {{ TREE_IDX[n.s] = n; buildIdx(n.c || []); }}
}})({compact_json});

function chartSlug(s) {{ return 'rym_chart_all_time_' + s.replace(/-/g,'_'); }}

let _diag_counter = 0;
let _current_slug = null;

// ── Mermaid code builder ───────────────────────────────────────────────
function buildMermaidCode(rootSlug) {{
  const root = TREE_IDX[rootSlug];
  if (!root) return null;
  const lines = ['graph LR'];
  const seen = new Set();  // avoid duplicate nodes if slug appears multiple times

  function add(node, parentId, depth) {{
    const s = node.s;
    const nid = s.replace(/[^a-zA-Z0-9]/g, '_');
    const name = node.n.replace(/"/g, "'");
    const scraped = !!CHARTS[chartSlug(s)];
    const cls = depth === 0 ? 'mg' : (scraped ? 'sc' : 'un');
    const shape = depth === 0 ? `([\"${{name}}\"])` : `[\"${{name}}\"]`;

    if (!seen.has(nid)) {{
      seen.add(nid);
      lines.push(`  ${{nid}}${{shape}}:::${{cls}}`);
      lines.push(`  click ${{nid}} call showPanel('${{s}}')`);
    }}
    if (parentId) lines.push(`  ${{parentId}} --> ${{nid}}`);

    for (const c of (node.c || [])) {{
      add(c, nid, depth + 1);
    }}
  }}

  add(root, null, 0);
  lines.push('  classDef mg fill:#c9a227,color:#000,stroke:#c9a227,font-weight:bold');
  lines.push('  classDef sc fill:#2a1e00,color:#c9a227,stroke:#5c4400');
  lines.push('  classDef un fill:#111,color:#555,stroke:#2a2a2a');
  return lines.join('\\n');
}}

// ── Genre selection ────────────────────────────────────────────────────
async function selectGenre(slug, name) {{
  // Highlight sidebar item
  document.querySelectorAll('.mg-link').forEach(el => el.classList.remove('active'));
  const link = document.querySelector(`.mg-link[data-slug="${{slug}}"]`);
  if (link) link.classList.add('active');

  const wrap = document.getElementById('diagram-wrap');
  const container = document.getElementById('diag-container');
  const status = document.getElementById('diag-status');

  container.innerHTML = '';
  status.textContent = 'Generando diagrama…';

  const code = buildMermaidCode(slug);
  if (!code) {{
    container.innerHTML = '<div id="diag-placeholder">Sin datos para este género.</div>';
    status.textContent = '';
    return;
  }}

  // Count nodes for info
  const nodeCount = (code.split('\\n').filter(l => /^  [A-Za-z]/.test(l) && !l.includes('-->') && !l.includes('classDef') && !l.includes('click')).length);
  status.textContent = `${{nodeCount}} nodos · ${{name}}`;

  try {{
    const id = 'mg_' + (++_diag_counter);
    const {{ svg }} = await mermaid.render(id, code);
    container.innerHTML = svg;
  }} catch(e) {{
    container.innerHTML = `<div id="diag-placeholder">Error al renderizar: ${{e.message}}</div>`;
    status.textContent = '';
  }}
}}

// ── Panel ──────────────────────────────────────────────────────────────
function showPanel(slug) {{
  const data = PANEL_DATA[slug];
  if (!data) return;
  _current_slug = slug;

  const cslug = chartSlug(slug);
  const hasChart = !!CHARTS[cslug];

  let html = `<div class="panel-slug">${{slug}}</div>`;
  html += `<div class="panel-title">${{data.name}}</div>`;

  if (data.desc) {{
    html += `<div class="panel-desc">${{data.desc}}</div>`;
  }}

  if (hasChart) {{
    html += `<a class="panel-chart-link" href="${{cslug}}/index.html" target="_blank">
      Ver chart → ${{CHARTS[cslug].total}} álbumes
    </a>`;
  }}

  if (data.albums && data.albums.length > 0) {{
    html += `<div class="panel-section-label">Top álbumes</div>`;
    for (const a of data.albums) {{
      html += renderAlbum(a);
    }}
  }} else {{
    html += `<div id="panel-no-chart">${{hasChart ? 'Sin álbumes en DB' : 'Sin chart scrapeado'}}</div>`;
  }}

  document.getElementById('panel-content').innerHTML = html;
  document.getElementById('panel').classList.add('open');
  document.getElementById('diagram-wrap').classList.add('panel-open');
}}

function renderAlbum(a) {{
  const ytBlock = a.yt_id
    ? `<div class="yt-embed"><iframe
        src="https://www.youtube.com/embed/${{a.yt_id}}"
        allow="autoplay;encrypted-media" allowfullscreen loading="lazy"></iframe></div>`
    : `<div class="yt-placeholder" onclick="loadYtSearch(this,'${{encodeURIComponent(a.artist + ' ' + a.title)}}')">
        <div class="yt-placeholder-inner">
          <div class="yt-play-btn">▶</div>
          <span>Buscar en YouTube</span>
          <span style="color:#222;font-size:.5rem">${{a.artist}} — ${{a.title}}</span>
        </div>
      </div>`;
  return `<div class="panel-album">
    <div class="album-meta">
      <span class="album-name">${{a.title}}</span>
      <span class="album-year">${{a.year}}</span>
    </div>
    <div class="album-artist">${{a.artist}}</div>
    ${{ytBlock}}
  </div>`;
}}

function loadYtSearch(el, query) {{
  el.outerHTML = `<div class="yt-embed"><iframe
    src="https://www.youtube.com/embed?listType=search&list=${{query}}"
    allow="autoplay;encrypted-media" allowfullscreen loading="lazy"></iframe></div>`;
}}

function closePanel() {{
  document.getElementById('panel').classList.remove('open');
  document.getElementById('diagram-wrap').classList.remove('panel-open');
  _current_slug = null;
}}
</script>
</body>
</html>
"""


def _count_all(node: dict) -> int:
    return sum(1 + _count_all(s) for s in node.get("subgenres", []))


# ── entry point ────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    mh_db = Path(args.mh_db)
    if not mh_db.exists():
        raise FileNotFoundError(f"must_hear DB not found: {mh_db}")

    # Auto-detect genres JSON
    if args.genres_json:
        genres_json = Path(args.genres_json)
    else:
        # Try common locations relative to mh_db
        candidates = [
            mh_db.parent.parent / "docs/must_hear/rym_charts/rym_genres.json",
            mh_db.parent / "rym_genres.json",
        ]
        genres_json = next((p for p in candidates if p.exists()), None)
        if genres_json is None:
            raise FileNotFoundError(
                "rym_genres.json not found; pass --genres-json explicitly"
            )

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = mh_db.parent.parent / "docs/must_hear/rym_genre_tree.html"

    print(f"📂 genres JSON: {genres_json}")
    print(f"🗄  must_hear DB: {mh_db}")

    genre_tree = load_genre_tree(genres_json)
    print(f"🌳 {len(genre_tree)} main genres loaded")

    conn = sqlite3.connect(str(mh_db))
    scraped_slugs_map = get_scraped_collections(conn)
    scraped_slugs = set(scraped_slugs_map.keys())
    print(f"✅ {len(scraped_slugs)} scraped collections found")

    top_albums = get_top_albums_per_collection(conn, list(scraped_slugs), n=5)
    conn.close()

    panel_data = build_panel_data(genre_tree, scraped_slugs_map, top_albums)
    generated  = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = render_html(genre_tree, panel_data, scraped_slugs, scraped_slugs_map, generated)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"✨ {out_path}  ({len(html)//1024}KB)")


def main() -> None:
    p = argparse.ArgumentParser(description="Generate RYM Genre Tree interactive page")
    p.add_argument("--mh-db",      required=True, help="Path to must_hear DB")
    p.add_argument("--genres-json", default="", help="Path to rym_genres.json (auto-detected if omitted)")
    p.add_argument("--output",      default="", help="Output HTML path (default: docs/must_hear/rym_genre_tree.html)")
    run(p.parse_args())


if __name__ == "__main__":
    main()

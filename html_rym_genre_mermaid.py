"""
html_rym_genre_mermaid.py — Standalone RYM Genre Tree visualizer.

Generates docs/must_hear/rym_genre_tree.html (or --output path).

Usage:
    python3 html_rym_genre_mermaid.py --mh-db db/must_hear_rym_new.db
    python3 html_rym_genre_mermaid.py --mh-db db/must_hear_rym_new.db \\
        --genres-json docs/must_hear/rym_charts/rym_genres.json \\
        --output docs/must_hear/rym_genre_tree.html

Can also be called from html_must_hear.py via --rym-genre-mermaid.

Tree behaviour:
  - Left sidebar: main genres. Selecting one shows root + direct children.
  - Click a node body → expand its children one level at a time.
  - Click the "+" button on any node → open info panel (desc + YouTube).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────

def _chart_slug(genre_slug: str) -> str:
    return "rym_chart_all_time_" + genre_slug.replace("-", "_")


def _count_all(node: dict) -> int:
    return sum(1 + _count_all(s) for s in node.get("subgenres", []))


# ── data gathering ─────────────────────────────────────────────────────────

def load_genre_tree(genres_json: Path) -> list[dict]:
    return json.loads(genres_json.read_text(encoding="utf-8"))


def get_scraped_collections(mh_conn: sqlite3.Connection) -> dict[str, dict]:
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
    scraped_map: dict[str, dict],
    top_albums: dict[str, list[dict]],
) -> dict[str, dict]:
    data: dict[str, dict] = {}

    def walk(nodes: list[dict]) -> None:
        for n in nodes:
            slug  = n["slug"]
            cslug = _chart_slug(slug)
            data[slug] = {
                "name":   n["name"],
                "desc":   n.get("desc", ""),
                "total":  scraped_map.get(cslug, {}).get("total", 0),
                "cslug":  cslug if cslug in scraped_map else "",
                "albums": top_albums.get(cslug, []),
            }
            walk(n.get("subgenres", []))

    walk(genre_tree)
    return data


# ── HTML rendering ─────────────────────────────────────────────────────────

def render_html(
    genre_tree: list[dict],
    panel_data: dict[str, dict],
    scraped_map: dict[str, dict],
    generated: str,
) -> str:
    # Compact tree for JS: {s, n, c[]}
    def _compact(nodes: list[dict]) -> list[dict]:
        return [{"s": n["slug"], "n": n["name"],
                 "c": _compact(n.get("subgenres", []))} for n in nodes]

    compact_json = json.dumps(_compact(genre_tree), ensure_ascii=False, separators=(",", ":"))
    charts_json  = json.dumps(
        {cs: d["total"] for cs, d in scraped_map.items()},
        ensure_ascii=False, separators=(",", ":"),
    )
    panel_json = json.dumps(panel_data, ensure_ascii=False, separators=(",", ":"))

    n_scraped = len(scraped_map)
    n_total   = sum(1 + _count_all(g) for g in genre_tree)

    # Sidebar HTML: one entry per main genre
    sidebar_html = ""
    for g in genre_tree:
        cslug   = _chart_slug(g["slug"])
        scraped = cslug in scraped_map
        cls = "mg-link" + (" scraped" if scraped else "")
        sidebar_html += (
            f'<div class="{cls}" data-slug="{g["slug"]}" '
            f'onclick="selectGenre(\'{g["slug"]}\')">'
            f'<span class="dot{"" if not scraped else " dot-scraped"}"></span>'
            f'{g["name"]}'
            f'</div>\n'
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
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<style>
  :root {{
    --bg:#0a0a0a; --surface:#111; --border:#1e1e1e;
    --accent:#c9a227; --muted:#555; --text:#e0e0e0; --header-h:52px;
    --panel-w:340px;
  }}
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif;
          min-height:100vh; overflow:hidden; }}

  /* ── header ── */
  header {{
    position:fixed; top:0; left:0; right:0; z-index:200; height:var(--header-h);
    background:rgba(10,10,10,.97); backdrop-filter:blur(12px);
    border-bottom:1px solid var(--border);
    display:flex; align-items:center; gap:12px; padding:0 18px;
  }}
  /* MH unified nav */
  .mh-title {{ font-family:'Bebas Neue',sans-serif; font-size:1.1rem; letter-spacing:.1em; color:var(--text); white-space:nowrap; flex-shrink:0; }}
  .mh-nav {{ display:flex; gap:2px; flex-shrink:0; }}
  .mh-na {{ font-family:'DM Mono',monospace; font-size:.6rem; letter-spacing:.07em; text-transform:uppercase; color:var(--muted); text-decoration:none; padding:3px 8px; border-radius:3px; transition:all .12s; }}
  .mh-na:hover {{ color:var(--text); background:rgba(255,255,255,.06); }}
  .mh-na.on {{ color:var(--accent); background:rgba(255,255,255,.04); }}
  /* Genre picker dropdown */
  .genre-picker {{ position:relative; flex-shrink:0; }}
  .genre-picker-btn {{
    display:flex; align-items:center; gap:8px; padding:5px 12px;
    background:none; border:1px solid var(--border); border-radius:5px;
    color:var(--text); font-family:'DM Sans',sans-serif; font-size:.82rem;
    cursor:pointer; white-space:nowrap; min-width:170px; justify-content:space-between;
    transition:border-color .12s;
  }}
  .genre-picker-btn:hover {{ border-color:var(--accent); }}
  .genre-picker-btn.open {{ border-color:var(--accent); color:var(--accent); }}
  .gp-caret {{ font-size:.65rem; color:var(--muted); transition:transform .15s; flex-shrink:0; }}
  .genre-picker-btn.open .gp-caret {{ transform:rotate(180deg); color:var(--accent); }}
  .genre-picker-dd {{
    display:none; position:absolute; top:calc(100% + 6px); left:0;
    background:#0d0d0d; border:1px solid var(--border); border-radius:6px;
    padding:4px 0; min-width:220px; max-height:65vh;
    overflow-y:auto; z-index:300;
    box-shadow:0 6px 24px rgba(0,0,0,.6);
    scrollbar-width:thin; scrollbar-color:var(--border) transparent;
  }}
  .genre-picker-dd.open {{ display:block; }}
  .mg-link {{
    display:flex; align-items:center; gap:8px; padding:6px 14px;
    font-size:.82rem; cursor:pointer; transition:background .1s, color .1s;
    color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  }}
  .mg-link.scraped {{ color:var(--text); }}
  .mg-link:hover, .mg-link.active {{ background:rgba(255,255,255,.04); color:var(--accent); }}
  .dot {{ flex-shrink:0; width:6px; height:6px; border-radius:50%; background:#333; }}
  .dot-scraped {{ background:var(--accent); }}
  /* MH user switcher */
  .mh-usr {{ position:relative; margin-left:auto; flex-shrink:0; }}
  .mh-usr-b {{ display:flex; align-items:center; gap:4px; background:none; border:1px solid var(--border); border-radius:4px; color:var(--muted); font-family:'DM Mono',monospace; font-size:.62rem; padding:4px 9px; cursor:pointer; white-space:nowrap; }}
  .mh-usr-b:hover {{ color:var(--text); border-color:var(--accent); }}
  .mh-usr-d {{ display:none; position:absolute; right:0; top:calc(100% + 5px); background:#0f0f0f; border:1px solid var(--border); border-radius:6px; padding:4px; min-width:130px; z-index:300; box-shadow:0 4px 16px rgba(0,0,0,.5); }}
  .mh-usr-d.open {{ display:block; }}
  .mh-usr-o {{ display:block; padding:4px 10px; border-radius:3px; font-family:'DM Mono',monospace; font-size:.62rem; color:var(--muted); text-decoration:none; cursor:pointer; white-space:nowrap; }}
  .mh-usr-o:hover {{ background:var(--border); color:var(--text); }}
  .mh-usr-o.cur {{ color:var(--accent); }}

  /* ── layout ── */
  #layout {{ display:flex; position:fixed; top:var(--header-h); left:0; right:0; bottom:0; }}

  /* ── tree canvas ── */
  #tree-wrap {{
    flex:1; overflow:hidden; position:relative; background:var(--bg);
    transition:right .2s;
  }}
  #tree-wrap.panel-open {{ right:var(--panel-w); }}
  #tree-svg {{ width:100%; height:100%; cursor:grab; }}
  #tree-svg:active {{ cursor:grabbing; }}
  #tree-placeholder {{
    position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
    font-family:'DM Mono',monospace; font-size:.75rem; color:#2a2a2a; text-align:center;
    line-height:2; pointer-events:none;
  }}

  /* ── D3 node styles (SVG) ── */
  .node-group {{ cursor:pointer; }}
  .node-rect {{
    rx:6; fill:var(--surface,#111); stroke:var(--border,#1e1e1e);
    transition:fill .15s, stroke .15s;
  }}
  .node-rect.scraped {{ fill:#1a1300; stroke:#4a3800; }}
  .node-rect.root    {{ fill:#2a1e00; stroke:var(--accent,#c9a227); stroke-width:2; }}
  .node-rect:hover, .node-group:hover .node-rect {{ stroke:var(--accent,#c9a227); }}
  .node-name {{ fill:var(--text,#e0e0e0); font-family:'DM Sans',sans-serif;
                font-size:12px; pointer-events:none; }}
  .node-name.root-text {{ fill:var(--accent,#c9a227); font-weight:600; font-size:13px; }}
  .node-name.muted {{ fill:var(--muted,#555); }}
  .node-sub {{
    fill:var(--muted,#555); font-family:'DM Mono',monospace;
    font-size:9px; pointer-events:none;
  }}
  .expand-caret {{
    fill:none; stroke:var(--muted,#555); stroke-width:1.5;
    transition:stroke .15s;
  }}
  .node-group:hover .expand-caret {{ stroke:var(--accent,#c9a227); }}
  .expand-caret.open {{ stroke:var(--accent,#c9a227); }}

  /* "+" info button */
  .info-btn-circle {{ fill:#1e1e1e; stroke:#333; transition:fill .15s, stroke .15s; cursor:pointer; }}
  .info-btn-circle:hover {{ fill:var(--accent,#c9a227); stroke:var(--accent,#c9a227); }}
  .info-btn-text {{ fill:var(--accent,#c9a227); font-family:'DM Mono',monospace;
                    font-size:14px; font-weight:700; pointer-events:none; text-anchor:middle;
                    dominant-baseline:central; }}
  .info-btn-circle:hover + .info-btn-text {{ fill:#000; }}

  /* links */
  .tree-link {{ fill:none; stroke:#2a2a2a; stroke-width:1.5; }}

  /* ── side panel ── */
  #panel {{
    position:absolute; top:0; right:0; bottom:0;
    width:var(--panel-w); background:var(--surface);
    border-left:1px solid var(--border);
    transform:translateX(100%); transition:transform .2s;
    overflow-y:auto; z-index:100; padding:18px 18px 40px;
  }}
  #panel.open {{ transform:translateX(0); }}
  .panel-close {{
    background:none; border:none; color:var(--muted); cursor:pointer;
    font-size:.8rem; float:right; padding:2px 6px; transition:color .12s;
  }}
  .panel-close:hover {{ color:var(--accent); }}
  .panel-slug {{ font-family:'DM Mono',monospace; font-size:.52rem; color:var(--muted); margin-bottom:4px; }}
  .panel-title {{
    font-family:'Bebas Neue',sans-serif; font-size:1.5rem; color:var(--accent);
    letter-spacing:.04em; margin-bottom:8px; line-height:1.1; clear:both;
  }}
  .panel-desc {{
    font-size:.82rem; color:var(--muted); line-height:1.5;
    margin-bottom:14px; border-bottom:1px solid var(--border); padding-bottom:14px;
  }}
  .panel-chart-link {{
    display:inline-block; margin-bottom:14px;
    font-family:'DM Mono',monospace; font-size:.58rem; letter-spacing:.08em;
    padding:4px 10px; border:1px solid var(--accent); border-radius:3px;
    color:var(--accent); text-decoration:none; transition:all .12s;
  }}
  .panel-chart-link:hover {{ background:var(--accent); color:#000; }}
  .panel-section {{ font-family:'DM Mono',monospace; font-size:.56rem; letter-spacing:.15em;
                    text-transform:uppercase; color:var(--muted); margin:14px 0 8px; }}
  .panel-album {{ margin-bottom:16px; }}
  .album-meta {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:3px; }}
  .album-title {{ font-size:.82rem; font-weight:500; }}
  .album-year {{ font-family:'DM Mono',monospace; font-size:.65rem; color:var(--muted); }}
  .album-artist {{ font-size:.75rem; color:var(--muted); margin-bottom:6px; }}
  .yt-wrap {{ position:relative; padding-bottom:56.25%; height:0; overflow:hidden;
               border-radius:4px; background:#000; }}
  .yt-wrap iframe {{ position:absolute; top:0; left:0; width:100%; height:100%; border:0; }}
  .yt-placeholder {{
    position:relative; padding-bottom:56.25%; height:0; overflow:hidden;
    border-radius:4px; background:#0a0a0a; border:1px solid var(--border); cursor:pointer;
  }}
  .yt-ph-inner {{
    position:absolute; inset:0; display:flex; flex-direction:column;
    align-items:center; justify-content:center; gap:6px;
  }}
  .yt-play {{ width:38px; height:38px; background:var(--accent); border-radius:50%;
               display:flex; align-items:center; justify-content:center; color:#000; font-size:.9rem; }}
  .yt-ph-label {{ font-family:'DM Mono',monospace; font-size:.55rem; color:var(--muted); text-align:center; padding:0 10px; }}
  .no-data {{ font-family:'DM Mono',monospace; font-size:.65rem; color:#2a2a2a;
               text-align:center; padding:20px 0; }}

  @media (max-width:700px) {{
    :root {{ --panel-w:100vw; }}
  }}
</style>
</head>
<body>
<header>
  <div class="mh-title">Géneros RYM</div>
  <nav class="mh-nav">
    <a class="mh-na" href="../index.html">Colección</a>
    <a class="mh-na" href="../index_alternativo.html">Explorador</a>
    <a class="mh-na on" href="rym_genre_tree.html">Géneros RYM</a>
    <a class="mh-na" href="../estadisticas.html">Estadísticas</a>
  </nav>
  <div class="genre-picker" id="genrePicker">
    <button class="genre-picker-btn" id="gpBtn" onclick="togglePicker()">
      <span id="gpLabel">Selecciona un género…</span>
      <span class="gp-caret">▾</span>
    </button>
    <div class="genre-picker-dd" id="gpDd">
{sidebar_html}    </div>
  </div>
  <div class="mh-usr">
    <button class="mh-usr-b" id="mhUBtn">👤 <span id="mhULbl">—</span></button>
    <div class="mh-usr-d" id="mhUDd"></div>
  </div>
</header>

<div id="layout">
  <div id="tree-wrap">
    <svg id="tree-svg"></svg>
    <div id="tree-placeholder">Selecciona un género para ver su árbol</div>
  </div>

  <aside id="panel">
    <button class="panel-close" onclick="closePanel()">✕</button>
    <div id="panel-body"></div>
  </aside>
</div>

<script>
// ── Data ──────────────────────────────────────────────────────────────────
const TREE_IDX  = {{}};  // slug → compact {{s,n,c[]}}
const CHARTS    = {charts_json};    // chart_slug → total albums
const PANEL_DATA = {panel_json};  // genre_slug → {{name,desc,cslug,total,albums[]}}

(function idx(nodes) {{
  for (const n of nodes) {{ TREE_IDX[n.s] = n; idx(n.c || []); }}
}})({compact_json});

function cslug(s) {{ return 'rym_chart_all_time_' + s.replace(/-/g,'_'); }}
function isScraped(s) {{ return !!CHARTS[cslug(s)]; }}

// ── Tree state ────────────────────────────────────────────────────────────
// Each node in our working tree: {{slug, name, children:null|[], _raw, expanded}}
let treeRoot = null;
let activeSlug = null;

function makeNode(compactNode, expanded=false) {{
  return {{
    slug:     compactNode.s,
    name:     compactNode.n,
    _raw:     compactNode,
    children: null,   // null = collapsed, [] or [...] = expanded
    expanded: false,
  }};
}}

function expandNode(node) {{
  if (node.children !== null) return;  // already expanded
  const rawKids = node._raw.c || [];
  node.children = rawKids.map(c => makeNode(TREE_IDX[c.s] || c));
  node.expanded = true;
}}

function collapseNode(node) {{
  node.children = null;
  node.expanded = false;
}}

function toggleExpand(node) {{
  if (node.children !== null) collapseNode(node);
  else expandNode(node);
  render();
}}

// ── D3 layout ─────────────────────────────────────────────────────────────
const NODE_W  = 188;
const NODE_H  = 46;
const BTN_R   = 14;
const H_GAP   = 60;   // horizontal gap between levels
const V_GAP   = 8;    // vertical gap between siblings

const svg    = d3.select('#tree-svg');
const gRoot  = svg.append('g');  // all content (transformed by zoom)

const zoomBehavior = d3.zoom()
  .scaleExtent([0.15, 3])
  .on('zoom', e => gRoot.attr('transform', e.transform));
svg.call(zoomBehavior);

const treeLayout = d3.tree()
  .nodeSize([NODE_H + V_GAP, NODE_W + H_GAP])
  .separation((a, b) => a.parent === b.parent ? 1 : 1.4);

function buildHierarchy(node) {{
  const obj = {{ id: node.slug, node }};
  if (node.children !== null) {{
    obj.children = node.children.map(c => buildHierarchy(c));
  }}
  return obj;
}}

let _idCounter = 0;
function render() {{
  if (!treeRoot) return;

  const hierRoot = d3.hierarchy(buildHierarchy(treeRoot));
  treeLayout(hierRoot);

  // d3.tree uses x=vertical, y=horizontal — swap for LR layout
  const nodes = hierRoot.descendants();
  const links = hierRoot.links();

  // ── links ──────────────────────────────────────────────────────────────
  const linkSel = gRoot.selectAll('.tree-link').data(links, d => d.target.data.id);

  // Bezier from right-edge of source to left-edge of target
  function linkPath(d) {{
    const sx = d.source.y + NODE_W, sy = d.source.x + NODE_H / 2;
    const tx = d.target.y,          ty = d.target.x + NODE_H / 2;
    const mx = (sx + tx) / 2;
    return `M${{sx}},${{sy}} C${{mx}},${{sy}} ${{mx}},${{ty}} ${{tx}},${{ty}}`;
  }}

  linkSel.enter().append('path')
    .attr('class', 'tree-link')
    .attr('d', linkPath)
    .merge(linkSel)
    .transition().duration(250)
    .attr('d', linkPath);

  linkSel.exit().transition().duration(200).style('opacity',0).remove();

  // ── nodes ──────────────────────────────────────────────────────────────
  // Colours as constants (inline attrs — more reliable than CSS vars in SVG)
  const C_ACCENT = '#c9a227';
  const C_MUTED  = '#555555';
  const NODE_BG   = (depth, scraped) => depth === 0 ? '#2a1e00' : scraped ? '#1a1300' : '#161616';
  const NODE_STR  = (depth, scraped) => depth === 0 ? C_ACCENT  : scraped ? '#4a3800' : '#2a2a2a';
  const NODE_STW  = (depth) => depth === 0 ? 2 : 1;
  const TEXT_CLR  = (depth, scraped) => depth === 0 ? C_ACCENT  : scraped ? '#e0e0e0' : '#666';
  const BX = NODE_W + BTN_R + 6;
  const BY = NODE_H / 2;

  const nodeSel = gRoot.selectAll('.node-group').data(nodes, d => d.data.id);

  const enter = nodeSel.enter().append('g')
    .attr('class', 'node-group')
    .attr('transform', d => `translate(${{d.y}},${{d.x}})`)
    .style('opacity', 0);

  // Background rect — click = expand/collapse
  enter.append('rect')
    .attr('rx', 6)
    .attr('width', NODE_W)
    .attr('height', NODE_H)
    .attr('fill',         d => NODE_BG(d.depth, isScraped(d.data.node.slug)))
    .attr('stroke',       d => NODE_STR(d.depth, isScraped(d.data.node.slug)))
    .attr('stroke-width', d => NODE_STW(d.depth))
    .style('cursor', d => (d.data.node._raw.c || []).length > 0 ? 'pointer' : 'default')
    .on('mouseover', function(e, d) {{
      d3.select(this).attr('stroke', C_ACCENT);
    }})
    .on('mouseout', function(e, d) {{
      d3.select(this).attr('stroke', NODE_STR(d.depth, isScraped(d.data.node.slug)));
    }})
    .on('click', (e, d) => {{
      e.stopPropagation();
      const n = d.data.node;
      if ((n._raw.c || []).length > 0) toggleExpand(n);
    }});

  // Genre name
  enter.append('text')
    .attr('x', 10)
    .attr('y', 18)
    .attr('fill',        d => TEXT_CLR(d.depth, isScraped(d.data.node.slug)))
    .attr('font-family', "'DM Sans', sans-serif")
    .attr('font-size',   d => d.depth === 0 ? '13px' : '12px')
    .attr('font-weight', d => d.depth === 0 ? '600' : '400')
    .style('pointer-events', 'none')
    .text(d => {{
      const name = d.data.node.name;
      return name.length > 20 ? name.slice(0, 19) + '…' : name;
    }});

  // Subtext: chart total or subgenre count
  enter.append('text')
    .attr('x', 10)
    .attr('y', 34)
    .attr('fill', C_MUTED)
    .attr('font-family', "'DM Mono', monospace")
    .attr('font-size', '9px')
    .style('pointer-events', 'none')
    .text(d => {{
      const n = d.data.node;
      const cs = cslug(n.slug);
      if (CHARTS[cs]) return CHARTS[cs] + ' álb';
      const kids = (n._raw.c || []).length;
      return kids > 0 ? kids + ' sub' : '';
    }});

  // ── "ℹ" info button inside rect (always) → opens panel ───────────────────
  const infoG = enter.append('g')
    .attr('class', '_info_g')
    .style('cursor', 'pointer')
    .on('click', (e, d) => {{ e.stopPropagation(); showPanel(d.data.node.slug); }})
    .on('mouseover', function() {{
      d3.select(this).select('circle').attr('fill', C_ACCENT).attr('stroke', C_ACCENT);
      d3.select(this).select('text').attr('fill', '#000');
    }})
    .on('mouseout', function() {{
      d3.select(this).select('circle').attr('fill', '#1e1e1e').attr('stroke', '#3a3a3a');
      d3.select(this).select('text').attr('fill', C_ACCENT);
    }});

  infoG.append('circle')
    .attr('cx', NODE_W - 14).attr('cy', NODE_H / 2).attr('r', 9)
    .attr('fill', '#1e1e1e').attr('stroke', '#3a3a3a');

  infoG.append('text')
    .attr('x', NODE_W - 14).attr('y', NODE_H / 2)
    .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
    .attr('fill', C_ACCENT)
    .attr('font-family', "'DM Mono', monospace")
    .attr('font-size', '11px').attr('font-weight', '700')
    .style('pointer-events', 'none')
    .text('i');

  // ── "+" expand button outside rect (only for nodes with children) ─────────
  const expandG = enter.append('g')
    .attr('class', '_expand_g')
    .style('display', d => (d.data.node._raw.c || []).length > 0 ? null : 'none')
    .style('cursor', 'pointer')
    .on('click', (e, d) => {{
      e.stopPropagation();
      const n = d.data.node;
      if ((n._raw.c || []).length > 0) toggleExpand(n);
    }})
    .on('mouseover', function() {{
      d3.select(this).select('circle').attr('fill', C_ACCENT).attr('stroke', C_ACCENT);
      d3.select(this).select('._expand_txt').attr('fill', '#000');
    }})
    .on('mouseout', function() {{
      d3.select(this).select('circle').attr('fill', '#1e1e1e').attr('stroke', '#3a3a3a');
      d3.select(this).select('._expand_txt').attr('fill', C_ACCENT);
    }});

  expandG.append('circle')
    .attr('cx', BX).attr('cy', BY).attr('r', BTN_R)
    .attr('fill', '#1e1e1e').attr('stroke', '#3a3a3a');

  expandG.append('text')
    .attr('class', '_expand_txt')
    .attr('x', BX).attr('y', BY)
    .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
    .attr('fill', C_ACCENT)
    .attr('font-family', "'DM Mono', monospace")
    .attr('font-size', '16px').attr('font-weight', '700')
    .style('pointer-events', 'none')
    .text(d => d.data.node.children !== null ? '−' : '+');

  // ── update + enter: position, opacity, expand button state ───────────────
  const update = nodeSel.merge(enter);
  update.transition().duration(250)
    .style('opacity', 1)
    .attr('transform', d => `translate(${{d.y}},${{d.x}})`);

  update.each(function(d) {{
    const isOpen  = d.data.node.children !== null;
    const hasKids = (d.data.node._raw.c || []).length > 0;
    d3.select(this).select('._expand_txt').text(!hasKids ? '' : isOpen ? '−' : '+');
  }});

  // ── exit ───────────────────────────────────────────────────────────────
  nodeSel.exit().transition().duration(200).style('opacity',0).remove();
}}

// ── Genre selection ────────────────────────────────────────────────────────
function togglePicker() {{
  const btn = document.getElementById('gpBtn');
  const dd  = document.getElementById('gpDd');
  btn.classList.toggle('open');
  dd.classList.toggle('open');
}}

function selectGenre(slug) {{
  // Update picker label and close dropdown
  const link = document.querySelector(`.mg-link[data-slug="${{slug}}"]`);
  if (link) {{
    document.getElementById('gpLabel').textContent = link.textContent.trim();
  }}
  document.querySelectorAll('.mg-link').forEach(el => el.classList.remove('active'));
  if (link) link.classList.add('active');
  document.getElementById('gpBtn').classList.remove('open');
  document.getElementById('gpDd').classList.remove('open');

  document.getElementById('tree-placeholder').style.display = 'none';

  const raw = TREE_IDX[slug];
  if (!raw) return;

  // Build root with children pre-expanded one level
  treeRoot = makeNode(raw);
  expandNode(treeRoot);
  activeSlug = slug;

  render();

  // Center view
  const wrap = document.getElementById('tree-wrap');
  const W = wrap.clientWidth;
  const H = wrap.clientHeight;
  svg.transition().duration(300).call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(60, H / 2).scale(1)
  );
}}

// ── Panel ──────────────────────────────────────────────────────────────────
function showPanel(slug) {{
  const data = PANEL_DATA[slug] || {{}};
  const cs   = cslug(slug);
  const hasChart = !!CHARTS[cs];

  let html = `<div class="panel-slug">${{slug}}</div>`;
  html += `<div class="panel-title">${{data.name || slug}}</div>`;

  if (data.desc) {{
    html += `<div class="panel-desc">${{data.desc}}</div>`;
  }}

  if (hasChart) {{
    html += `<a class="panel-chart-link" href="rym_charts/${{cs}}/index.html" target="_blank">
      Ver chart · ${{data.total}} álbumes ↗
    </a>`;
  }}

  if (data.albums && data.albums.length) {{
    html += `<div class="panel-section">Top álbumes</div>`;
    for (const a of data.albums) html += albumHtml(a);
  }} else {{
    html += `<div class="no-data">${{hasChart ? 'Sin álbumes en DB' : 'Sin chart scrapeado'}}</div>`;
  }}

  document.getElementById('panel-body').innerHTML = html;
  document.getElementById('panel').classList.add('open');
  document.getElementById('tree-wrap').classList.add('panel-open');
}}

function albumHtml(a) {{
  const ytBlock = a.yt_id
    ? `<div class="yt-wrap"><iframe
         src="https://www.youtube.com/embed/${{a.yt_id}}"
         allow="autoplay;encrypted-media" allowfullscreen loading="lazy"></iframe></div>`
    : `<div class="yt-placeholder" onclick="loadYtSearch(this,'${{encodeURIComponent(a.artist+' '+a.title)}}')">
         <div class="yt-ph-inner">
           <div class="yt-play">▶</div>
           <div class="yt-ph-label">${{a.artist}}<br>${{a.title}}</div>
         </div>
       </div>`;
  return `<div class="panel-album">
    <div class="album-meta">
      <span class="album-title">${{a.title}}</span>
      <span class="album-year">${{a.year}}</span>
    </div>
    <div class="album-artist">${{a.artist}}</div>
    ${{ytBlock}}
  </div>`;
}}

function loadYtSearch(el, q) {{
  el.outerHTML = `<div class="yt-wrap"><iframe
    src="https://www.youtube.com/embed?listType=search&list=${{q}}"
    allow="autoplay;encrypted-media" allowfullscreen loading="lazy"></iframe></div>`;
}}

function closePanel() {{
  document.getElementById('panel').classList.remove('open');
  document.getElementById('tree-wrap').classList.remove('panel-open');
}}

// Close genre picker on outside click
document.addEventListener('click', e => {{
  const picker = document.getElementById('genrePicker');
  if (picker && !picker.contains(e.target)) {{
    document.getElementById('gpBtn').classList.remove('open');
    document.getElementById('gpDd').classList.remove('open');
  }}
}});

// MH user switcher
(function() {{
  const KEY = 'mh_user';
  const btn = document.getElementById('mhUBtn');
  const dd  = document.getElementById('mhUDd');
  if (!btn || !dd) return;
  const stored = localStorage.getItem(KEY);
  if (stored) document.getElementById('mhULbl').textContent = stored;
  btn.addEventListener('click', e => {{ e.stopPropagation(); dd.classList.toggle('open'); }});
  document.addEventListener('click', () => dd.classList.remove('open'));
}})();
</script>
</body>
</html>
"""


# ── entry point ────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    mh_db = Path(args.mh_db)
    if not mh_db.exists():
        raise FileNotFoundError(f"must_hear DB not found: {mh_db}")

    if getattr(args, "genres_json", ""):
        genres_json = Path(args.genres_json)
    else:
        candidates = [
            mh_db.parent.parent / "docs/must_hear/rym_charts/rym_genres.json",
            mh_db.parent / "rym_genres.json",
        ]
        genres_json = next((p for p in candidates if p.exists()), None)
        if genres_json is None:
            raise FileNotFoundError(
                "rym_genres.json not found; pass --genres-json explicitly"
            )

    out_path = Path(getattr(args, "output", "") or
                    str(mh_db.parent.parent / "docs/must_hear/rym_genre_tree.html"))

    print(f"📂 genres JSON : {genres_json}")
    print(f"🗄  must_hear DB: {mh_db}")

    genre_tree = load_genre_tree(genres_json)
    print(f"🌳 {len(genre_tree)} main genres")

    conn = sqlite3.connect(str(mh_db))
    scraped_map  = get_scraped_collections(conn)
    top_albums   = get_top_albums_per_collection(conn, list(scraped_map.keys()), n=5)
    conn.close()
    print(f"✅ {len(scraped_map)} scraped collections")

    panel_data = build_panel_data(genre_tree, scraped_map, top_albums)
    generated  = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = render_html(genre_tree, panel_data, scraped_map, generated)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"✨ {out_path}  ({len(html)//1024}KB)")


def main() -> None:
    p = argparse.ArgumentParser(description="Generate RYM Genre Tree interactive page")
    p.add_argument("--mh-db",       required=True, help="Path to must_hear DB")
    p.add_argument("--genres-json", default="",    help="Path to rym_genres.json")
    p.add_argument("--output",      default="",    help="Output HTML path")
    run(p.parse_args())


if __name__ == "__main__":
    main()

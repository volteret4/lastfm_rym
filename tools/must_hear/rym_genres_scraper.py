#!/usr/bin/env python3
"""
RYM Genres Tree Scraper

Scrapes https://rateyourmusic.com/genres/ to build a hierarchy of
main genres → subgenres, each with their all-time chart URL.

Usage via html_must_hear.py:
    # Fetch and save the full genre tree (runs browser once)
    python3 html_must_hear.py --rym-genres-fetch [--force-scrape]

    # List fetched genres (no browser needed)
    python3 html_must_hear.py --rym-genres-print [--rym-genre PARENT]

    # Scrape chart for one genre/subgenre (derives URL from slug)
    python3 html_must_hear.py --rym-genre SLUG [--rym-chart-limit N]

    # Scrape chart for every subgenre of a parent genre
    python3 html_must_hear.py --rym-genre-all PARENT [--rym-chart-limit N]

The genre tree JSON is saved at:
    docs/must_hear/rym_charts/rym_genres.json
"""

import json, re, time
from pathlib import Path
from bs4 import BeautifulSoup, Tag

RYM_GENRES_URL = "https://rateyourmusic.com/genres/"
GENRES_FILENAME = "rym_genres.json"


# ── URL helpers ───────────────────────────────────────────────────────────────

def chart_url_from_slug(slug: str) -> str:
    """Derive the all-time chart URL for a genre slug.
    e.g. 'dark-ambient' → 'https://rateyourmusic.com/charts/top/album/all-time/g:dark-ambient/'
    """
    return f"https://rateyourmusic.com/charts/top/album/all-time/g:{slug}/"


def slug_from_genre_url(url: str) -> str:
    """Extract slug from '/genre/dark-ambient/' → 'dark-ambient'."""
    m = re.search(r"/genre/([^/?#]+)/?$", url)
    return m.group(1) if m else ""


# ── HTML parser ───────────────────────────────────────────────────────────────

def _parse_hierarchy_item(li: Tag) -> dict | None:
    """
    Parse a <li class="hierarchy_list_item"> element into a subgenre dict.
    Recursively processes nested <ul class="hierarchy_list"> children.

    Each <li> may look like:
      <li class="hierarchy_list_item">
        <div class="hierarchy_list_item_details">
          <a href="/genre/dark-ambient/">Dark Ambient</a>
          <p>Emphasizes an ominous, gloomy...</p>
        </div>
        <ul class="hierarchy_list">         ← optional nested children
          <li class="hierarchy_list_item">...</li>
        </ul>
      </li>
    """
    details = li.find("div", class_="hierarchy_list_item_details")
    if not details:
        return None
    link = details.find("a", href=re.compile(r"^/genre/"))
    if not link:
        return None

    slug = slug_from_genre_url(link["href"])
    name = link.get_text(strip=True)
    if not slug or not name:
        return None

    desc_p = details.find("p")
    desc = desc_p.get_text(strip=True) if desc_p else ""

    # Each child may live in its own <ul class="hierarchy_list"> directly under
    # this <li> (not inside details), so search direct children only.
    children: list[dict] = []
    seen: set[str] = set()
    for sub_ul in li.find_all("ul", class_="hierarchy_list", recursive=False):
        for sub_li in sub_ul.find_all("li", class_="hierarchy_list_item", recursive=False):
            child = _parse_hierarchy_item(sub_li)
            if child and child["slug"] not in seen:
                seen.add(child["slug"])
                children.append(child)

    return {
        "slug":      slug,
        "name":      name,
        "desc":      desc,
        "chart_url": chart_url_from_slug(slug),
        "subgenres": children,
    }


def _parse_genres_page(html: str) -> list[dict]:
    """
    Parse the /genres/ page and return a list of main genres, each with
    description and a recursive subgenre tree.

    Actual RYM structure (as of 2025):
      <li id="page_genre_index_hierarchy_item_N"
          class="page_genre_index_hierarchy_item anchor [parentless_non_top_level]">
        <div class="page_genre_index_hierarchy_item_main_inner">
          <h2><a href="/genre/ambient/">Ambient</a></h2>
          <p class="page_genre_index_hierarchy_item_description">...</p>
        </div>
        <div class="page_genre_index_hierarchy_item_expanded">
          <ul class="hierarchy_list">          ← one <ul> per direct subgenre
            <li class="hierarchy_list_item">
              <div class="hierarchy_list_item_details">
                <a href="/genre/dark-ambient/">Dark Ambient</a>
                <p>description...</p>
              </div>
              <ul class="hierarchy_list">      ← optional nested children
                ...
              </ul>
            </li>
          </ul>
          ...

    Items with class "parentless_non_top_level" are subgenres already listed
    under a different parent — they are skipped as top-level entries.
    """
    soup = BeautifulSoup(html, "html.parser")
    result: list[dict] = []

    for li in soup.find_all("li", class_="page_genre_index_hierarchy_item"):
        if "parentless_non_top_level" in (li.get("class") or []):
            continue

        main_inner = li.find("div", class_="page_genre_index_hierarchy_item_main_inner")
        if not main_inner:
            continue

        h2 = main_inner.find("h2")
        if not h2:
            continue
        link = h2.find("a", href=re.compile(r"^/genre/"))
        if not link:
            continue

        slug = slug_from_genre_url(link["href"])
        name = link.get_text(strip=True)
        if not slug or not name:
            continue

        desc_p = main_inner.find("p", class_="page_genre_index_hierarchy_item_description")
        desc = desc_p.get_text(strip=True) if desc_p else ""

        subgenres: list[dict] = []
        seen: set[str] = set()
        expanded = li.find("div", class_="page_genre_index_hierarchy_item_expanded")
        if expanded:
            for sub_ul in expanded.find_all("ul", class_="hierarchy_list", recursive=False):
                for sub_li in sub_ul.find_all("li", class_="hierarchy_list_item", recursive=False):
                    entry = _parse_hierarchy_item(sub_li)
                    if entry and entry["slug"] not in seen:
                        seen.add(entry["slug"])
                        subgenres.append(entry)

        result.append({
            "slug":      slug,
            "name":      name,
            "desc":      desc,
            "chart_url": chart_url_from_slug(slug),
            "subgenres": subgenres,
        })

    return result


# ── Playwright scraper ────────────────────────────────────────────────────────

def fetch_genre_tree(state_dir: Path, cache_path: Path,
                     force: bool = False) -> list[dict]:
    """
    Fetch and parse the RYM genres hierarchy using Playwright.
    Result cached at cache_path as JSON.
    """
    if cache_path.exists() and not force:
        data = json.loads(cache_path.read_text())
        if data:
            print(f"  📦 Géneros desde caché: {cache_path} ({len(data)} géneros principales)")
            return data
        print("  ⚠  Caché vacío, re-scrapeando...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("playwright not installed. Run: pip install playwright && playwright install chromium")

    from tools.must_hear.rym_must_hear import _find_chromium, _wait_for_page

    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    chromium = _find_chromium()
    extra_kwargs = {"executable_path": chromium} if chromium else {}

    html = ""
    print(f"  🌐 Abriendo {RYM_GENRES_URL}")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(state_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            **extra_kwargs,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        html = _wait_for_page(page, RYM_GENRES_URL)

        if html:
            # Expand any collapsed "Show N subgenres" sections
            try:
                btns = page.query_selector_all("button, [class*='show'], [class*='expand']")
                for btn in btns:
                    txt = (btn.inner_text() or "").lower()
                    if "subgenre" in txt or "more" in txt:
                        try:
                            btn.click()
                            time.sleep(0.15)
                        except Exception:
                            pass
                # Re-grab expanded HTML
                time.sleep(0.5)
                html = page.content()
            except Exception:
                pass

        # Save debug dump
        try:
            dbg = Path("/tmp/rym_genres_debug.html")
            dbg.write_text(html or "", encoding="utf-8")
            print(f"  💡 HTML guardado en {dbg} (para depuración)")
        except Exception:
            pass

        ctx.close()

    if not html:
        print("  ❌ No se pudo obtener el HTML de géneros")
        return []

    genres = _parse_genres_page(html)

    if not genres:
        print("  ⚠  Parser no encontró géneros. Revisa /tmp/rym_genres_debug.html")
        return []

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(genres, ensure_ascii=False, indent=2))
    print(f"  💾 {cache_path}")
    return genres


# ── Tree lookup helpers ───────────────────────────────────────────────────────

def _find_in_subtree(node: dict, slug: str) -> tuple[dict | None, dict | None]:
    """Recursively search for slug within a genre node. Returns (entry, parent)."""
    for s in node.get("subgenres", []):
        if s["slug"] == slug:
            return s, node
        found, parent = _find_in_subtree(s, slug)
        if found:
            return found, parent
    return None, None


def find_genre(tree: list[dict], slug: str) -> tuple[dict | None, dict | None]:
    """Return (genre_entry, immediate_parent_or_None) for a given slug at any depth."""
    for g in tree:
        if g["slug"] == slug:
            return g, None
        found, parent = _find_in_subtree(g, slug)
        if found:
            return found, parent
    return None, None


def find_by_parent(tree: list[dict], parent_slug: str) -> dict | None:
    """Return the top-level genre entry with the given slug."""
    for g in tree:
        if g["slug"] == parent_slug:
            return g
    return None


def _count_all(node: dict) -> int:
    """Count total subgenres at all depths under a node."""
    total = 0
    for s in node.get("subgenres", []):
        total += 1 + _count_all(s)
    return total


def _flatten_all(node: dict) -> list[dict]:
    """Return a flat list of all descendants of a node (breadth-first)."""
    result: list[dict] = []
    queue = list(node.get("subgenres", []))
    while queue:
        entry = queue.pop(0)
        result.append(entry)
        queue.extend(entry.get("subgenres", []))
    return result


# ── Pretty printer ────────────────────────────────────────────────────────────

def _print_subgenres(entries: list[dict], indent: int = 6) -> None:
    """Recursively print subgenre hierarchy with indentation."""
    pad = " " * indent
    for s in entries:
        children = s.get("subgenres", [])
        marker = "┬" if children else "·"
        desc = f"  — {s['desc'][:80]}" if s.get("desc") else ""
        print(f"{pad}{marker} {s['name']}  [{s['slug']}]{desc}")
        if children:
            _print_subgenres(children, indent + 4)


def print_genre_tree(tree: list[dict], filter_parent: str = "") -> None:
    """Print the genre hierarchy with descriptions. Optionally filter to one parent."""
    if filter_parent:
        parent = find_by_parent(tree, filter_parent)
        if not parent:
            print(f"  ❌ Género '{filter_parent}' no encontrado")
            return
        items = [parent]
    else:
        items = tree

    for g in items:
        total = _count_all(g)
        desc = f"\n      {g['desc']}" if g.get("desc") else ""
        print(f"  ▶ {g['name']}  [{g['slug']}]  ({total} subgéneros totales){desc}")
        _print_subgenres(g.get("subgenres", []))


# ── Entry points ──────────────────────────────────────────────────────────────

def run_rym_genres_fetch(args, root_dir: Path) -> None:
    """--rym-genres-fetch: scrape and save genre tree."""
    from tools.must_hear.rym_must_hear import STATE_DIR

    cache_path = root_dir / "rym_charts" / GENRES_FILENAME
    force      = getattr(args, "force_scrape", False)

    print("🎼 Obteniendo árbol de géneros de RateYourMusic…")
    tree = fetch_genre_tree(Path(STATE_DIR), cache_path, force=force)
    if tree:
        total_subs = sum(_count_all(g) for g in tree)
        print(f"  ✅ {len(tree)} géneros principales · {total_subs} subgéneros (todos los niveles)")
        print()
        print_genre_tree(tree)


def run_rym_genres_print(args, root_dir: Path) -> None:
    """--rym-genres-print: print the cached genre tree."""
    cache_path   = root_dir / "rym_charts" / GENRES_FILENAME
    filter_slug  = getattr(args, "rym_genre", None) or ""

    if not cache_path.exists():
        print(f"  ❌ Árbol de géneros no encontrado. Ejecuta --rym-genres-fetch primero.")
        return

    tree = json.loads(cache_path.read_text())
    print(f"🎼 Géneros RYM ({cache_path.name})")
    print()
    print_genre_tree(tree, filter_parent=filter_slug)


def run_rym_genre(args, root_dir: Path) -> None:
    """
    --rym-genre SLUG: scrape the chart for one genre/subgenre.
    Derives the chart URL from the slug; optionally validates against genres.json.
    """
    from tools.must_hear.rym_charts_must_hear import run_rym_chart

    genre_slug = (getattr(args, "rym_genre", None) or "").strip()
    if not genre_slug:
        print("  ❌ Indica el slug del género: --rym-genre dark-ambient")
        return

    # Optionally look up name from genre tree
    cache_path = root_dir / "rym_charts" / GENRES_FILENAME
    display_name = ""
    parent_name  = ""
    if cache_path.exists():
        tree = json.loads(cache_path.read_text())
        entry, parent = find_genre(tree, genre_slug)
        if entry:
            display_name = entry["name"]
            parent_name  = parent["name"] if parent else ""
        else:
            print(f"  ⚠  '{genre_slug}' no encontrado en géneros guardados. Continuando de todas formas…")

    chart_url = chart_url_from_slug(genre_slug)
    # Build a nice name: "RYM Top — Ambient — Dark Ambient" or "RYM Top — Dark Ambient"
    if display_name:
        if parent_name:
            derived_name = f"RYM Top — {parent_name} — {display_name}"
        else:
            derived_name = f"RYM Top — {display_name}"
    else:
        derived_name = f"RYM Top — {genre_slug.replace('-', ' ').title()}"

    args.rym_chart_url   = chart_url
    args.name            = getattr(args, "name", "") or derived_name
    args.collection      = getattr(args, "collection", None) or "RYM Charts"

    print(f"🎼 Scrapeando chart: {derived_name}")
    print(f"   URL: {chart_url}")
    run_rym_chart(args, root_dir)


def _collection_album_count(mh_conn, db_slug: str) -> int:
    """Return the number of albums already stored for a chart slug (0 if not found)."""
    row = mh_conn.execute(
        """SELECT COUNT(*) FROM collection_albums ca
           JOIN collections c ON c.id = ca.collection_id
           WHERE c.slug = ?""",
        (db_slug,),
    ).fetchone()
    return row[0] if row else 0


def run_rym_genre_all(args, root_dir: Path) -> None:
    """
    --rym-genre-all PARENT: scrape charts for every subgenre under a parent genre.
    """
    from tools.must_hear.rym_charts_must_hear import run_rym_chart, _slug_from_chart_url

    parent_slug = (getattr(args, "rym_genre_all", None) or "").strip()
    if not parent_slug:
        print("  ❌ Indica el género padre: --rym-genre-all ambient")
        return

    cache_path = root_dir / "rym_charts" / GENRES_FILENAME
    if not cache_path.exists():
        print("  ❌ Ejecuta --rym-genres-fetch primero")
        return

    tree   = json.loads(cache_path.read_text())
    parent = find_by_parent(tree, parent_slug)
    if not parent:
        print(f"  ❌ Género padre '{parent_slug}' no encontrado")
        return

    all_descendants = _flatten_all(parent)
    targets = [parent] + all_descendants
    force   = getattr(args, "force_scrape", False)
    mh_conn = getattr(args, "_rym_chart_mh_conn", None)
    print(f"🎼 {len(targets)} chart(s) bajo '{parent['name']}'…")

    for entry in targets:
        slug = entry["slug"]
        name = entry["name"]
        chart_url = chart_url_from_slug(slug)
        db_slug   = _slug_from_chart_url(chart_url)

        if entry is parent:
            derived_name = f"RYM Top — {name}"
        else:
            derived_name = f"RYM Top — {parent['name']} — {name}"

        print(f"\n── {derived_name} ──")

        # Skip if already scraped and --force-scrape not requested
        if not force and mh_conn:
            count = _collection_album_count(mh_conn, db_slug)
            if count:
                print(f"  ⏭  Ya en DB ({count} álbumes), omitiendo")
                continue

        args.rym_chart_url = chart_url
        args.name          = derived_name
        args.slug          = None   # let run_rym_chart derive it
        args.collection    = getattr(args, "collection", None) or "RYM Charts"
        run_rym_chart(args, root_dir)

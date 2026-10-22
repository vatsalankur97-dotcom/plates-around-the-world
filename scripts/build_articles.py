#!/usr/bin/env python3
"""Build sitemap, JSON-LD, search index, disclosure page, and gear HTML.

Ported from Content Studio's local build_articles.py. That script was never
in the repo. It string-replaced templates/article-template.html (ARTICLE TITLE,
SLUG, and the Lisbon description sentence), wrote articles/*.html, and spliced
cards into the homepage, guides, and recipes. lib.py was not imported by it
(it is a Playwright social-image renderer with machine-local paths) and is
not part of this build.

The default command does not rewrite article pages, meta tags, canonicals,
alt text, or robots.txt. It fills <!-- JSON-LD:START -->…<!-- JSON-LD:END -->
and <!-- GEAR:START -->…<!-- GEAR:END --> only when a published page already
contains both markers.

    python3 scripts/build_articles.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

import gear

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://platesaroundtheworld.netlify.app"

JSONLD_START = "<!-- JSON-LD:START -->"
JSONLD_END = "<!-- JSON-LD:END -->"
GEAR_START = "<!-- GEAR:START -->"
GEAR_END = "<!-- GEAR:END -->"

# Sentence the original page() replaced inside the article template.
_LEGACY_DESCRIPTION = (
    "Custard tarts in Belém, garlic prawns at Ramiro and a market hall "
    "built for grazing: Lisbon's most-praised tables."
)

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def main() -> int:
    gear.self_check()
    _self_check_legacy_renderer()
    config = gear.load_config(ROOT / "data" / "affiliate-config.json")
    site = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))
    articles = _load_collection(ROOT / "content" / "articles", "article")
    recipes = _load_collection(ROOT / "content" / "recipes", "recipe")
    restaurants = _load_restaurants(ROOT / "content" / "restaurants")
    pages = articles + recipes
    _validate_pages(pages, restaurants)
    gear_files = _load_gear(pages)
    warnings = []
    for slug, payload in gear_files.items():
        warnings.extend(gear.validate_gear(payload, f"data/gear/{slug}.json"))
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    _write_sitemap(site, pages)
    _write_jsonld(pages, restaurants)
    _inject_jsonld(pages)
    _inject_gear(pages, gear_files, config)
    _write_search_index(pages, restaurants, gear_files)
    _write_disclosure(config)
    _assert_site_urls()
    if not config["AFFILIATE_LINKS_ENABLED"]:
        _assert_flag_off()
    print(f"built {len(pages)} pages, {len(restaurants)} restaurants")
    return 0


def render_article_html(
    template: str,
    slug: str,
    title: str,
    description: str,
    tag: str,
    note: str,
    body_html: str,
    sources_html: str,
    alt: str,
    image: str | None = None,
    sources_checked: str = "16 Oct 2026",
    sources_suffix: str = "Hours change, so check before you go.",
) -> str:
    """Same shell the local generator wrote: tag, h1, lead, cover, note, body, sources.

    `template` is the caller's string. This does not read templates/ on the
    default build, so a frontend template edit cannot be overwritten.
    """
    if "<main>" not in template or "</main>" not in template:
        raise SystemExit("article template is missing <main>")
    head, rest = template.split("<main>", 1)
    _main, foot = rest.split("</main>", 1)
    head = head.replace("ARTICLE TITLE", title).replace("SLUG", slug)
    head = head.replace(_LEGACY_DESCRIPTION, description)
    image_src = image or f"../assets/img/{slug}.jpg"
    if image_src.startswith("assets/"):
        image_src = "../" + image_src
    note_html = ""
    if note:
        note_html = (
            f'<div class="note">{escape(note)} '
            '<a href="../about.html#method">How we research</a>.</div>'
        )
    suffix = f" {sources_suffix}" if sources_suffix else ""
    article = (
        f'<main><article><span class="tag">{escape(tag)}</span>'
        f"<h1>{escape(title)}</h1><p class=\"lead\">{escape(description)}</p>"
        f'<img class="cover" src="{escape(image_src, quote=True)}" alt="{escape(alt)}">'
        f"{note_html}{body_html}"
        f'<p class="sources"><strong>Sources (checked {escape(sources_checked)}):</strong> '
        f"{sources_html}{suffix}</p></article></main>"
    )
    return head + article + foot


def render_card(slug: str, title: str, blurb: str, tag: str = "Researched guide", image: str | None = None) -> str:
    """Listing card. Not written into index, guides, or recipes by this build."""
    src = image or f"assets/img/{slug}.jpg"
    return (
        f'<a class="card" href="articles/{slug}.html">'
        f'<img src="{escape(src, quote=True)}" alt="{escape(title)}" loading="lazy">'
        f'<div><span class="tag ghost">{escape(tag)}</span>'
        f"<h3>{escape(title)}</h3><p>{escape(blurb)}</p></div></a>"
    )


def inject_between(html: str, start: str, end: str, inner: str) -> str | None:
    """Replace the interior of the first marker pair. None if either marker is missing."""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if start not in html or end not in html:
        return None
    block = f"{start}\n{inner}\n{end}" if inner else f"{start}\n{end}"
    updated, count = pattern.subn(block, html, count=1)
    if count != 1:
        raise SystemExit(f"could not replace {start}")
    return updated


def _load_collection(folder: Path, expected_type: str) -> list[dict]:
    pages = []
    if not folder.is_dir():
        return pages
    for path in sorted(folder.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = _FRONT_MATTER.match(raw)
        if not match:
            raise SystemExit(f"{path}: missing YAML front matter")
        meta = _parse_yaml(match.group(1), str(path))
        body = raw[match.end():]
        if meta.get("type") != expected_type:
            raise SystemExit(f"{path}: type must be {expected_type}")
        if meta.get("slug") != path.stem:
            raise SystemExit(f"{path}: slug must match the filename")
        meta["body"] = body.strip("\n")
        meta["source_path"] = str(path.relative_to(ROOT))
        pages.append(meta)
    return pages


def _load_restaurants(folder: Path) -> dict[str, dict]:
    found = {}
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("slug") != path.stem:
            raise SystemExit(f"{path}: slug must match the filename")
        for key in ("name", "description", "featured_in"):
            if not data.get(key):
                raise SystemExit(f"{path}: {key} is required")
        found[path.stem] = data
    return found


def _load_gear(pages: list[dict]) -> dict[str, dict]:
    folder = ROOT / "data" / "gear"
    found = {}
    known = {page["slug"] for page in pages}
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.stem not in known:
            raise SystemExit(f"{path}: no article or recipe with this slug")
        if data.get("slug") != path.stem:
            raise SystemExit(f"{path}: slug must match the filename")
        found[path.stem] = data
    return found


def _validate_pages(pages: list[dict], restaurants: dict[str, dict]) -> None:
    paths = set()
    for page in pages:
        for key in ("title", "description", "date", "path", "image", "alt", "tag"):
            if not page.get(key):
                raise SystemExit(f"{page['slug']}: {key} is required")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", page["date"]):
            raise SystemExit(f"{page['slug']}: date must be YYYY-MM-DD")
        if not str(page["path"]).startswith("/"):
            raise SystemExit(f"{page['slug']}: path must start with /")
        if page["path"] in paths:
            raise SystemExit(f"duplicate path {page['path']}")
        paths.add(page["path"])
        image = ROOT / page["image"]
        if not image.is_file():
            raise SystemExit(f"{page['slug']}: missing image {page['image']}")
        for match in re.finditer(r"\((assets/[^)\s]+)\)", page["body"]):
            if not (ROOT / match.group(1)).is_file():
                raise SystemExit(f"{page['slug']}: missing {match.group(1)}")
        for match in re.finditer(r"\((/[^)\s]+)\)", page["body"]):
            url = match.group(1)
            file_path, _fragment = (url.split("#", 1) + [""])[:2]
            rel = "index.html" if file_path == "/" else file_path.lstrip("/")
            if not (ROOT / rel).is_file() and rel != "disclosure.html":
                # disclosure.html is written by this same build.
                raise SystemExit(f"{page['slug']}: missing link target {url}")
        for slug in page.get("restaurants") or []:
            if slug not in restaurants:
                raise SystemExit(f"{page['slug']}: unknown restaurant {slug}")
        if page.get("draft"):
            continue
        target = ROOT / page["path"].lstrip("/")
        if page["path"] != "/disclosure.html" and not target.is_file():
            raise SystemExit(
                f"{page['slug']}: {page['path']} has no HTML file. "
                "Existing URLs stay put; add the page before publishing the path."
            )


def _write_sitemap(site: dict, pages: list[dict]) -> None:
    urls = []
    for entry in site["static_pages"]:
        urls.append((entry["path"], entry["lastmod"]))
    published = [page for page in pages if not page.get("draft")]
    for page in sorted(published, key=lambda item: item["path"]):
        urls.append((page["path"], page["date"]))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, lastmod in urls:
        loc = SITE_URL + "/" if path == "/" else SITE_URL + path
        if loc.endswith("//"):
            raise SystemExit(f"bad sitemap loc {loc}")
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    text = "\n".join(lines) + "\n"
    if "/index.html" in text or "platesaroundtheworld.com" in text:
        raise SystemExit("sitemap must use the netlify.app host and homepage /")
    (ROOT / "sitemap.xml").write_text(text, encoding="utf-8")


def _write_jsonld(pages: list[dict], restaurants: dict[str, dict]) -> None:
    out_dir = ROOT / "data" / "jsonld"
    out_dir.mkdir(parents=True, exist_ok=True)
    keep = set()
    for page in pages:
        if page.get("draft"):
            continue
        graph = _jsonld_graph(page, restaurants)
        payload = {"@context": "https://schema.org", "@graph": graph}
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        text = text.replace("<", "\\u003c")
        name = page["slug"] + ".json"
        (out_dir / name).write_text(text, encoding="utf-8")
        keep.add(name)
    for stale in out_dir.glob("*.json"):
        if stale.name not in keep:
            stale.unlink()


def _jsonld_graph(page: dict, restaurants: dict[str, dict]) -> list[dict]:
    url = _absolute(page["path"])
    org = {
        "@type": "Organization",
        "name": "Plates Around the World",
        "url": SITE_URL + "/",
    }
    image = _absolute("/" + page["image"].lstrip("/"))
    if page["type"] == "recipe":
        node = {
            "@type": "Recipe",
            "@id": url + "#recipe",
            "name": page["title"],
            "description": page["description"],
            "image": image,
            "datePublished": page["date"],
            "author": org,
            "mainEntityOfPage": url,
            "recipeIngredient": _flat_ingredients(page),
            "recipeInstructions": [
                {"@type": "HowToStep", "text": step}
                for step in page.get("instructions") or []
            ],
        }
        for key, schema_key in (
            ("recipe_yield", "recipeYield"),
            ("recipe_cuisine", "recipeCuisine"),
            ("recipe_category", "recipeCategory"),
            ("prep_time", "prepTime"),
            ("cook_time", "cookTime"),
            ("total_time", "totalTime"),
        ):
            if page.get(key):
                node[schema_key] = page[key]
    else:
        node = {
            "@type": "Article",
            "@id": url + "#article",
            "headline": page["title"],
            "description": page["description"],
            "image": image,
            "datePublished": page["date"],
            "dateModified": page["date"],
            "author": org,
            "publisher": org,
            "mainEntityOfPage": url,
        }
    graph = [node]
    mentions = []
    for slug in page.get("restaurants") or []:
        place = restaurants[slug]
        place_id = url + "#" + slug
        mentions.append({"@id": place_id})
        graph.append(_restaurant_node(place, place_id))
        review = _review_node(place, place_id, page["date"])
        if review:
            graph.append(review)
    if mentions:
        node["mentions"] = mentions
    return graph


def _restaurant_node(place: dict, place_id: str) -> dict:
    node = {
        "@type": place.get("schema_type") or "Restaurant",
        "@id": place_id,
        "name": place["name"],
        "description": place["description"],
    }
    address = place.get("address") or {}
    postal = {}
    mapping = {
        "street": "streetAddress",
        "locality": "addressLocality",
        "region": "addressRegion",
        "country": "addressCountry",
    }
    for src, dest in mapping.items():
        if address.get(src):
            postal[dest] = address[src]
    if postal:
        postal["@type"] = "PostalAddress"
        node["address"] = postal
    if place.get("url"):
        node["url"] = place["url"]
    if place.get("serves_cuisine"):
        node["servesCuisine"] = place["serves_cuisine"]
    return node


def _review_node(place: dict, place_id: str, published: str) -> dict | None:
    if place.get("role") == "context" or not place.get("review_body"):
        return None
    review = {
        "@type": "Review",
        "itemReviewed": {"@id": place_id},
        "reviewBody": place["review_body"],
        "datePublished": published,
        "author": {
            "@type": "Organization",
            "name": "Plates Around the World",
            "url": SITE_URL + "/",
        },
    }
    if place.get("rating_value") is not None and place.get("best_rating") is not None:
        review["reviewRating"] = {
            "@type": "Rating",
            "ratingValue": place["rating_value"],
            "bestRating": place["best_rating"],
        }
    return review


def _flat_ingredients(page: dict) -> list[str]:
    flat = []
    for group in page.get("ingredients") or []:
        name = group.get("group")
        for item in group.get("items") or []:
            flat.append(f"{name}: {item}" if name else item)
    return flat


def _inject_jsonld(pages: list[dict]) -> None:
    for page in pages:
        if page.get("draft"):
            continue
        path = ROOT / page["path"].lstrip("/")
        if not path.is_file():
            continue
        html = path.read_text(encoding="utf-8")
        payload = (ROOT / "data" / "jsonld" / f"{page['slug']}.json").read_text(encoding="utf-8").strip()
        script = '<script type="application/ld+json">\n' + payload + "\n</script>"
        updated = inject_between(html, JSONLD_START, JSONLD_END, script)
        if updated is not None and updated != html:
            path.write_text(updated, encoding="utf-8")


def _inject_gear(pages: list[dict], gear_files: dict, config: dict) -> None:
    for page in pages:
        path = ROOT / page["path"].lstrip("/")
        if not path.is_file():
            continue
        html = path.read_text(encoding="utf-8")
        if GEAR_START not in html and GEAR_END not in html:
            continue
        href = "../disclosure.html" if page["path"].startswith("/articles/") else "disclosure.html"
        data = gear_files.get(page["slug"], {"slug": page["slug"], "items": []})
        section = gear.render_gear_section(data, config, href)
        updated = inject_between(html, GEAR_START, GEAR_END, section)
        if updated is not None and updated != html:
            path.write_text(updated, encoding="utf-8")


def _write_search_index(pages: list[dict], restaurants: dict, gear_files: dict) -> None:
    records = []
    for page in pages:
        if page.get("draft"):
            continue
        records.append({
            "title": page["title"],
            "url": page["path"],
            "type": page["type"],
            "description": page["description"],
            "text": _plain(page["body"]),
        })
    by_slug = {page["slug"]: page for page in pages}
    for place in restaurants.values():
        parent = by_slug.get(place["featured_in"])
        if not parent or parent.get("draft"):
            continue
        records.append({
            "title": place["name"],
            "url": parent["path"],
            "type": "restaurant",
            "description": place["description"],
            "text": place.get("review_body") or "",
        })
    disclosure = ROOT / "content" / "disclosure.md"
    if disclosure.is_file():
        raw = disclosure.read_text(encoding="utf-8")
        match = _FRONT_MATTER.match(raw)
        meta = _parse_yaml(match.group(1), "content/disclosure.md") if match else {}
        body = raw[match.end():] if match else raw
        records.append({
            "title": meta.get("title", "Disclosure"),
            "url": "/disclosure.html",
            "type": "page",
            "description": meta.get("description", ""),
            "text": _plain(body),
        })
    records.sort(key=lambda item: (item["type"], item["title"]))
    text = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "data" / "search-index.json").write_text(text, encoding="utf-8")
    # gear_files is accepted so a future index can mention gear names.
    # With the flag off and empty lists there is nothing to add.
    del gear_files


def _write_disclosure(config: dict) -> None:
    path = ROOT / "content" / "disclosure.md"
    raw = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(raw)
    if not match:
        raise SystemExit("content/disclosure.md is missing front matter")
    meta = _parse_yaml(match.group(1), "content/disclosure.md")
    body = _markdown_html(raw[match.end():].strip("\n"))
    amazon = config.get("networks", {}).get("amazon", {})
    if config.get("AFFILIATE_LINKS_ENABLED") and amazon.get("enabled") and str(amazon.get("tag", "")).strip():
        body += (
            "<p>As an Amazon Associate I earn from qualifying purchases.</p>"
        )
    title = meta["title"]
    description = meta["description"]
    canonical = SITE_URL + "/disclosure.html"
    # New page, so it needs its own head. Existing pages are not rewritten.
    # Shell matches about.html so the current stylesheet and nav still apply.
    # The frontend can replace this shell when redesign templates land.
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} | Plates Around the World</title><meta name="description" content="{escape(description)}"><link rel="canonical" href="{canonical}">
<meta property="og:type" content="website"><meta property="og:title" content="{escape(title)} | Plates Around the World"><meta property="og:description" content="{escape(description)}"><meta property="og:image" content="{SITE_URL}/assets/img/banner.jpg"><meta property="og:url" content="{canonical}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="assets/img/icon.jpg"><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..700;1,9..144,400..600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"><link rel="stylesheet" href="assets/style.css?v=4"></head><body>
<header><div class="nav"><a class="brand" href="index.html"><img src="assets/img/icon.jpg" alt="">Plates Around the World</a><button class="menu" aria-label="Menu">☰</button>
<nav><ul><li><a href="guides.html">Restaurant Guides</a></li><li><a href="recipes.html">Recipes</a></li><li><a href="about.html">About</a></li><li><a href="contact.html">Contact</a></li></ul></nav></div></header>
<main><div class="page">{body}</div></main>
<footer><div class="wrap"><p><strong>Plates Around the World</strong> · Restaurants. Recipes. Every corner of the map.</p><p><a href="https://www.instagram.com/platesaroundtheworld_/" target="_blank" rel="noopener">Instagram</a> · <a href="https://www.pinterest.com/platesarounddtheworld/" target="_blank" rel="noopener">Pinterest</a> · <a href="https://www.youtube.com/@platesaroundtheworld" target="_blank" rel="noopener">YouTube</a></p><p><a href="mailto:plates.arounddtheworld@gmail.com">plates.arounddtheworld@gmail.com</a></p><p>Guides are researched from public ratings and press coverage unless marked as a first-hand visit. <a href="disclosure.html">Disclosure</a>. © 2026</p></div></footer>
<script src="assets/main.js"></script></body></html>
"""
    (ROOT / "disclosure.html").write_text(html, encoding="utf-8")


def _assert_site_urls() -> None:
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    home = f"<loc>{SITE_URL}/</loc>"
    if home not in sitemap:
        raise SystemExit("sitemap homepage must be " + SITE_URL + "/")
    if "platesaroundtheworld.com" in sitemap:
        raise SystemExit("sitemap still points at platesaroundtheworld.com")


def _assert_flag_off() -> None:
    skip = {"docs", "scripts"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if path.suffix not in {".html", ".xml", ".js", ".css", ".json"}:
            continue
        if path.name == "affiliate-config.json":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "tag=" in text:
            raise SystemExit(f"{path}: tag= present while affiliate links are off")
        for host in ("earnkaro.com", "cuelinks.com", "clk.om"):
            if host in text.lower():
                raise SystemExit(f"{path}: {host} present while affiliate links are off")


def _absolute(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path == "/":
        return SITE_URL + "/"
    return SITE_URL + (path if path.startswith("/") else "/" + path)


def _plain(markdown: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", markdown)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[#*_>`]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _markdown_html(markdown: str) -> str:
    """Small subset: headings, paragraphs, bold, italic, links."""
    blocks = re.split(r"\n\s*\n", markdown.strip())
    html = []
    for block in blocks:
        lines = block.splitlines()
        if lines and lines[0].startswith("## "):
            html.append(f"<h1>{_inline(lines[0][3:].strip())}</h1>")
            rest = "\n".join(lines[1:]).strip()
            if rest:
                html.append(f"<p>{_inline(rest)}</p>")
            continue
        if lines and lines[0].startswith("### "):
            html.append(f"<h2>{_inline(lines[0][4:].strip())}</h2>")
            continue
        html.append(f"<p>{_inline(' '.join(line.strip() for line in lines))}</p>")
    return "".join(html)


def _inline(text: str) -> str:
    parts = []
    pattern = re.compile(
        r"\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)]+)\)"
    )
    cursor = 0
    for match in pattern.finditer(text):
        parts.append(escape(text[cursor:match.start()]))
        if match.group(1) is not None:
            parts.append(f"<strong>{escape(match.group(1))}</strong>")
        elif match.group(2) is not None:
            parts.append(f"<em>{escape(match.group(2))}</em>")
        else:
            label, href = match.group(3), match.group(4)
            parts.append(
                f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'
            )
        cursor = match.end()
    parts.append(escape(text[cursor:]))
    return "".join(parts)


def _parse_yaml(text: str, where: str) -> dict:
    lines = text.splitlines()
    for line in lines:
        if "\t" in line:
            raise SystemExit(f"{where}: tabs are not allowed in front matter")
    value, index = _parse_map(lines, 0, 0, where)
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index != len(lines):
        raise SystemExit(f"{where}: could not parse front matter near {lines[index]!r}")
    return value


def _parse_map(lines: list[str], index: int, indent: int, where: str):
    mapping: dict = {}
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        current = len(line) - len(line.lstrip(" "))
        if current < indent:
            break
        if current != indent:
            raise SystemExit(f"{where}: bad indent {line!r}")
        stripped = line.strip()
        if stripped.startswith("#"):
            index += 1
            continue
        if stripped.startswith("- "):
            raise SystemExit(f"{where}: expected a key, found a list: {line!r}")
        if ":" not in stripped:
            raise SystemExit(f"{where}: expected key: value, found {line!r}")
        key, raw = stripped.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        if raw == "":
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            if index >= len(lines):
                mapping[key] = ""
                break
            child = len(lines[index]) - len(lines[index].lstrip(" "))
            if child <= indent:
                mapping[key] = ""
                continue
            if lines[index].lstrip().startswith("- "):
                mapping[key], index = _parse_list(lines, index, child, where)
            else:
                mapping[key], index = _parse_map(lines, index, child, where)
        else:
            mapping[key] = _coerce(raw)
            index += 1
    return mapping, index


def _parse_list(lines: list[str], index: int, indent: int, where: str):
    items = []
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        current = len(line) - len(line.lstrip(" "))
        if current < indent:
            break
        if current != indent:
            raise SystemExit(f"{where}: bad list indent {line!r}")
        stripped = line.lstrip()
        if not stripped.startswith("- "):
            break
        raw = stripped[2:].strip()
        if ":" in raw and not raw.startswith(("http://", "https://")):
            item_key, item_raw = raw.split(":", 1)
            item = {item_key.strip(): _coerce(item_raw.strip()) if item_raw.strip() else ""}
            index += 1
            extras = []
            while index < len(lines):
                if not lines[index].strip():
                    blank = index
                    index += 1
                    if index < len(lines) and lines[index].strip():
                        nxt = len(lines[index]) - len(lines[index].lstrip(" "))
                        if nxt <= indent:
                            index = blank
                            break
                    continue
                nxt = len(lines[index]) - len(lines[index].lstrip(" "))
                if nxt <= indent:
                    break
                extras.append(lines[index])
                index += 1
            if extras:
                child = len(extras[0]) - len(extras[0].lstrip(" "))
                nested, _end = _parse_map(extras, 0, child, where)
                item.update(nested)
            items.append(item)
        else:
            items.append(_coerce(raw))
            index += 1
    return items, index


def _coerce(raw: str):
    if raw in ("true", "false"):
        return raw == "true"
    if raw in ("null", "~", ""):
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    return raw


def _self_check_legacy_renderer() -> None:
    template = (
        "<head><title>ARTICLE TITLE | Plates Around the World</title>"
        f'<meta name="description" content="{_LEGACY_DESCRIPTION}">'
        f'<link rel="canonical" href="{SITE_URL}/articles/SLUG.html"></head>'
        "<main>OLD</main><footer>FOOT</footer>"
    )
    html = render_article_html(
        template,
        slug="demo",
        title="Demo title",
        description="A short lead.",
        tag="Recipe",
        note="",
        body_html="<p>Body</p>",
        sources_html="Source.",
        alt="Demo alt",
        image="assets/img/demo.jpg",
    )
    if "ARTICLE TITLE" in html or "OLD" in html or "<h1>Demo title</h1>" not in html:
        raise SystemExit("legacy article renderer drifted")
    if "FOOT" not in html or 'src="../assets/img/demo.jpg"' not in html:
        raise SystemExit("legacy article renderer dropped the footer or image")
    card = render_card("demo", "Demo", "Blurb", "Deep-dive")
    if 'href="articles/demo.html"' not in card or "Deep-dive" not in card:
        raise SystemExit("legacy card renderer drifted")
    sample = f"<head>{JSONLD_START}\nOLD\n{JSONLD_END}</head>"
    once = inject_between(sample, JSONLD_START, JSONLD_END, "<script>{}</script>")
    twice = inject_between(once, JSONLD_START, JSONLD_END, "<script>{}</script>")
    if once != twice or "OLD" in once:
        raise SystemExit("JSON-LD injection is not idempotent")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except gear.GearError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

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
    _ensure_disclosure_redirect()
    _validate_emitted_jsonld(pages)
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


def _public_path(path: str) -> str:
    """Canonical path. Both /articles/name and /articles/name.html are the same page."""
    if path in ("", "/"):
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    if path.endswith("/index.html"):
        return "/"
    if path.endswith(".html"):
        path = path[: -len(".html")]
    return path


def _html_path(path: str) -> Path:
    """File on disk for a public path. Extensionless URLs are rewritten to .html."""
    public = _public_path(path)
    if public == "/":
        return ROOT / "index.html"
    direct = ROOT / public.lstrip("/")
    if direct.is_file():
        return direct
    return ROOT / f"{public.lstrip('/')}.html"


def _page_lastmod(page: dict) -> str:
    return page.get("updated") or page["date"]


def _validate_pages(pages: list[dict], restaurants: dict[str, dict]) -> None:
    paths = set()
    for page in pages:
        for key in ("title", "description", "date", "path", "image", "alt", "tag"):
            if not page.get(key):
                raise SystemExit(f"{page['slug']}: {key} is required")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", page["date"]):
            raise SystemExit(f"{page['slug']}: date must be YYYY-MM-DD")
        if page.get("updated") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", page["updated"]):
            raise SystemExit(f"{page['slug']}: updated must be YYYY-MM-DD")
        if not str(page["path"]).startswith("/"):
            raise SystemExit(f"{page['slug']}: path must start with /")
        page["path"] = _public_path(page["path"])
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
            target = _html_path(url.split("#", 1)[0])
            if not target.is_file() and _public_path(url.split("#", 1)[0]) != "/disclosure":
                raise SystemExit(f"{page['slug']}: missing link target {url}")
        for slug in page.get("restaurants") or []:
            if slug not in restaurants:
                raise SystemExit(f"{page['slug']}: unknown restaurant {slug}")
        if page.get("draft"):
            continue
        target = _html_path(page["path"])
        if page["path"] != "/disclosure" and not target.is_file():
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
        urls.append((_public_path(page["path"]), _page_lastmod(page)))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, lastmod in urls:
        path = _public_path(path)
        loc = SITE_URL + "/" if path == "/" else SITE_URL + path
        if loc.endswith(".html"):
            raise SystemExit(f"sitemap loc must be extensionless: {loc}")
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


def _author() -> dict:
    return {
        "@type": "Organization",
        "name": "Plates Around the World",
        "url": SITE_URL + "/",
    }


def _publisher() -> dict:
    return {
        "@type": "Organization",
        "name": "Plates Around the World",
        "logo": {
            "@type": "ImageObject",
            "url": SITE_URL + "/assets/img/icon.jpg",
        },
    }


def _section_crumb(page: dict) -> tuple[str, str]:
    lists = page.get("lists") or []
    # A guide that is also listed under recipes (ramen) stays a guide,
    # matching the breadcrumb already on the page.
    if "guides" in lists or page.get("section") == "guide":
        return "Restaurant Guides", "/guides"
    if page["type"] == "recipe" or "recipes" in lists:
        return "Recipes", "/recipes"
    return "Restaurant Guides", "/guides"


def _breadcrumb(page: dict) -> dict:
    section_name, section_path = _section_crumb(page)
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": SITE_URL + "/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": section_name,
                "item": _absolute(section_path),
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": page["title"],
            },
        ],
    }


def _jsonld_graph(page: dict, restaurants: dict[str, dict]) -> list[dict]:
    url = _absolute(_public_path(page["path"]))
    image = _absolute("/" + page["image"].lstrip("/"))
    modified = _page_lastmod(page)
    if page["type"] == "recipe":
        node = {
            "@type": "Recipe",
            "name": page["title"],
            "description": page["description"],
            "image": image,
            "datePublished": page["date"],
            "dateModified": modified,
            "recipeCuisine": page.get("recipe_cuisine"),
            "recipeCategory": page.get("recipe_category"),
            "recipeIngredient": _flat_ingredients(page),
            "recipeInstructions": [
                {"@type": "HowToStep", "position": index, "text": step}
                for index, step in enumerate(page.get("instructions") or [], start=1)
            ],
            "author": _author(),
            "publisher": _publisher(),
            "mainEntityOfPage": url,
        }
        node = {key: value for key, value in node.items() if value not in (None, "")}
        # Yield and times stay absent until the owner supplies them.
        for key, schema_key in (
            ("recipe_yield", "recipeYield"),
            ("prep_time", "prepTime"),
            ("cook_time", "cookTime"),
            ("total_time", "totalTime"),
        ):
            if page.get(key):
                node[schema_key] = page[key]
    else:
        node = {
            "@type": "Article",
            "headline": page["title"],
            "description": page["description"],
            "image": image,
            "datePublished": page["date"],
            "dateModified": modified,
            "author": _author(),
            "publisher": _publisher(),
            "mainEntityOfPage": url,
        }
    graph = [node, _breadcrumb(page)]
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
        for item in group.get("items") or []:
            flat.append(item)
    return flat


def _inject_jsonld(pages: list[dict]) -> None:
    for page in pages:
        if page.get("draft"):
            continue
        path = _html_path(page["path"])
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
        path = _html_path(page["path"])
        if not path.is_file():
            continue
        html = path.read_text(encoding="utf-8")
        if GEAR_START not in html and GEAR_END not in html:
            continue
        href = "/disclosure.html"
        data = gear_files.get(page["slug"], {"slug": page["slug"], "items": []})
        section = gear.render_gear_section(data, config, href)
        # An empty list omits the section and leaves the frontend's placeholder.
        if not section.strip():
            continue
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
            "url": _public_path(page["path"]),
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
            "url": _public_path(parent["path"]),
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
            "url": _public_path(meta.get("path") or "/disclosure"),
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


_BANNER_ALT = (
    "Plates Around the World logo: a terracotta plate with a small world map, "
    "on a dark background."
)
_DISCLOSURE_REDIRECT = "/disclosure /disclosure.html 200"


def _read_partial(name: str) -> str:
    path = ROOT / "partials" / name
    if not path.is_file():
        raise SystemExit(f"missing {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    # The partials start with a copy-instruction comment. The page uses the markup.
    stripped = text.lstrip()
    if stripped.startswith("<!--"):
        end = stripped.find("-->")
        if end != -1:
            text = stripped[end + 3 :].lstrip("\n")
    if not text.endswith("\n"):
        text += "\n"
    return text


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
    title = f"{meta['title']} | Plates Around the World"
    description = meta["description"]
    canonical = SITE_URL + "/disclosure"
    header = _read_partial("header.html")
    footer = _read_partial("footer.html")
    if "data-site-search" not in header:
        raise SystemExit("partials/header.html is missing the search hook")
    css = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")
    html = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f'<meta name="description" content="{escape(description)}">\n'
        f'<link rel="canonical" href="{canonical}">\n'
        "\n"
        '<meta property="og:site_name" content="Plates Around the World">\n'
        '<meta property="og:locale" content="en_GB">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:title" content="{escape(title)}">\n'
        f'<meta property="og:description" content="{escape(description)}">\n'
        f'<meta property="og:url" content="{canonical}">\n'
        f'<meta property="og:image" content="{SITE_URL}/assets/img/banner.jpg">\n'
        '<meta property="og:image:width" content="1280">\n'
        '<meta property="og:image:height" content="720">\n'
        f'<meta property="og:image:alt" content="{escape(_BANNER_ALT)}">\n'
        '<meta property="og:image:type" content="image/jpeg">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{escape(title)}">\n'
        f'<meta name="twitter:description" content="{escape(description)}">\n'
        f'<meta name="twitter:image" content="{SITE_URL}/assets/img/banner.jpg">\n'
        f'<meta name="twitter:image:alt" content="{escape(_BANNER_ALT)}">\n'
        '<link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">\n'
        '<link rel="preload" href="/assets/fonts/fraunces-normal-560-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
        f"<style>{css}</style>\n"
        "\n"
        "</head>\n"
        "<body>\n"
        f"{header}"
        "<main id=\"content\"><div class=\"page\">\n"
        f"{body}</div></main>\n"
        f"{footer}"
        "</body></html>\n"
    )
    if 'href="index.html"' in html or "style.css?v=4" in html:
        raise SystemExit("disclosure page still uses the pre-redesign header")
    if f'href="{canonical}"' not in html:
        raise SystemExit("disclosure canonical must be /disclosure")
    (ROOT / "disclosure.html").write_text(html, encoding="utf-8")


def _ensure_disclosure_redirect() -> None:
    path = ROOT / "_redirects"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if _DISCLOSURE_REDIRECT in lines or any(line.startswith("/disclosure ") for line in lines):
        return
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + _DISCLOSURE_REDIRECT + "\n", encoding="utf-8")


def _validate_emitted_jsonld(pages: list[dict]) -> None:
    for page in pages:
        if page.get("draft"):
            continue
        html_path = _html_path(page["path"])
        html = html_path.read_text(encoding="utf-8")
        blocks = re.findall(
            re.escape(JSONLD_START) + r"(.*?)" + re.escape(JSONLD_END),
            html,
            re.DOTALL,
        )
        if len(blocks) != 1:
            raise SystemExit(f"{page['slug']}: expected one JSON-LD marker pair, found {len(blocks)}")
        match = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            blocks[0],
            re.DOTALL,
        )
        if not match:
            raise SystemExit(f"{page['slug']}: JSON-LD marker has no script")
        payload = json.loads(match.group(1))
        graph = payload.get("@graph")
        if not isinstance(graph, list) or not graph:
            raise SystemExit(f"{page['slug']}: JSON-LD needs an @graph")
        primary = graph[0]
        url = _absolute(page["path"])
        if primary.get("mainEntityOfPage") != url or url.endswith(".html"):
            raise SystemExit(f"{page['slug']}: mainEntityOfPage must be the extensionless canonical")
        if page["type"] == "recipe":
            for key in ("name", "image", "recipeIngredient", "recipeInstructions", "datePublished"):
                if not primary.get(key):
                    raise SystemExit(f"{page['slug']}: Recipe is missing {key}")
            for step in primary["recipeInstructions"]:
                if step.get("@type") != "HowToStep" or not step.get("text"):
                    raise SystemExit(f"{page['slug']}: recipe step is incomplete")
        else:
            for key in ("headline", "image", "datePublished", "dateModified"):
                if not primary.get(key):
                    raise SystemExit(f"{page['slug']}: Article is missing {key}")
        logo = (primary.get("publisher") or {}).get("logo") or {}
        if not logo.get("url"):
            raise SystemExit(f"{page['slug']}: publisher logo is missing")
        crumbs = [node for node in graph if node.get("@type") == "BreadcrumbList"]
        if len(crumbs) != 1:
            raise SystemExit(f"{page['slug']}: BreadcrumbList must be in the same @graph")
        items = crumbs[0].get("itemListElement") or []
        if [item.get("name") for item in items[:2]] != ["Home", _section_crumb(page)[0]]:
            raise SystemExit(f"{page['slug']}: breadcrumb must be Home > section > page")
        if items[0].get("item") != SITE_URL + "/":
            raise SystemExit(f"{page['slug']}: home crumb must be the site root")
        if len(items) != 3 or items[2].get("name") != page["title"] or "item" in items[2]:
            raise SystemExit(f"{page['slug']}: the current page crumb is the title, with no URL")
        if any(".html" in str(item.get("item", "")) for item in items):
            raise SystemExit(f"{page['slug']}: breadcrumb URLs must be extensionless")
        if page["slug"] == "butter-chicken":
            if primary.get("recipeCuisine") != "Indian (Punjabi / Delhi)":
                raise SystemExit("butter chicken cuisine must stay Indian (Punjabi / Delhi)")
            if primary.get("recipeCategory") != "Main":
                raise SystemExit("butter chicken course must stay Main")
            if any(item.startswith(("Marinade:", "Sauce:")) for item in primary["recipeIngredient"]):
                raise SystemExit("recipe ingredients must stay the published strings")
        for slug in page.get("restaurants") or []:
            if not any(str(node.get("@id", "")).endswith("#" + slug) for node in graph):
                raise SystemExit(f"{page['slug']}: restaurant {slug} dropped from the graph")


def _assert_site_urls() -> None:
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    home = f"<loc>{SITE_URL}/</loc>"
    if home not in sitemap:
        raise SystemExit("sitemap homepage must be " + SITE_URL + "/")
    if "platesaroundtheworld.com" in sitemap:
        raise SystemExit("sitemap still points at platesaroundtheworld.com")
    if ".html</loc>" in sitemap or ".html<" in sitemap:
        raise SystemExit("sitemap locs must match the extensionless canonicals")
    if f"<loc>{SITE_URL}/disclosure</loc>" not in sitemap:
        raise SystemExit("sitemap must list /disclosure")


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
    return "\n".join(html) + "\n"


def _inline(text: str) -> str:
    parts = []
    pattern = re.compile(
        r"\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)]+)\)"
    )
    cursor = 0
    for match in pattern.finditer(text):
        parts.append(escape(text[cursor:match.start()], quote=False))
        if match.group(1) is not None:
            parts.append(f"<strong>{escape(match.group(1), quote=False)}</strong>")
        elif match.group(2) is not None:
            parts.append(f"<em>{escape(match.group(2), quote=False)}</em>")
        else:
            label, href = match.group(3), match.group(4)
            parts.append(
                f'<a href="{escape(href, quote=True)}">{escape(label, quote=False)}</a>'
            )
        cursor = match.end()
    parts.append(escape(text[cursor:], quote=False))
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

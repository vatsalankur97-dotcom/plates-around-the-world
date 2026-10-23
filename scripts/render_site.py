#!/usr/bin/env python3
"""Write the static pages for the redesign branch.

Netlify does not run this. Publish stays the committed HTML (netlify.toml
is intentionally untouched). Re-run after editing copy or partial strings:

    python3 scripts/render_site.py

Article prose is read from content/bodies/*.fragment.html (the pre-redesign
text). Patches below are the approved Content Studio edits and nothing else.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = "https://platesaroundtheworld.netlify.app"
BODIES = ROOT / "content" / "bodies"

CARD_SIZES = "(min-width: 980px) 340px, (min-width: 640px) 46vw, 92vw"
COVER_SIZES = "(min-width: 900px) 840px, 100vw"
INSTA_SIZES = "(min-width: 760px) 16vw, 30vw"
TRIP_SIZES = "(min-width: 700px) 30vw, 46vw"

SEARCH = """<div class="site-search">
  <label class="sr" for="site-search">Search</label>
  <input id="site-search" type="search" data-site-search placeholder="Search guides and recipes" autocomplete="off">
  <ul id="site-search-results" data-site-search-results hidden></ul>
</div>
<script src="/assets/search.js" defer></script>
"""

NEWSLETTER = """<!-- NEWSLETTER:START -->
<!-- Backend file: partials/newsletter-form.html
     Conflict, left visible on purpose: that file sets action="/" and the netlify
     attribute, and its note says "weekly plate". Approved copy (22 Oct 2026)
     keeps this placeholder action and does not promise a weekly send.
     Do not add data-subscribe. assets/main.js turns that attribute into a mailto. -->
<form name="newsletter" method="POST" action="[NEWSLETTER_FORM_ACTION: TBD]">
  <p hidden>
    <label>Leave this empty: <input name="bot-field"></label>
  </p>
  <input type="hidden" name="form-name" value="newsletter">
  <label for="newsletter-email">Email</label>
  <input id="newsletter-email" type="email" name="email" required autocomplete="email">
  <button class="btn" type="submit">Subscribe</button>
  <p class="privacy-note">We only use your email to send the newsletter. <a href="#privacy">Privacy note</a>.</p>
</form>
<!-- NEWSLETTER:END -->
"""

PRIVACY = """<!-- PRIVACY:START -->
<!-- Backend file: partials/privacy-section.html
     Conflict: that file says "weekly plate" and that Netlify Forms stores the
     submission. The tool is still TBD, so this note does not claim either.
     id="privacy" stays so the form link resolves. -->
<details id="privacy" class="privacy">
  <summary>Privacy</summary>
  <p>The newsletter form collects your email address and nothing else. We use it to send that newsletter. We don't sell it, and we don't use it for other mail.</p>
  <p>No sending tool is connected yet. The hidden honeypot field is spam protection; leave it empty. It is not a profile.</p>
  <p>To be removed, email <a href="mailto:plates.arounddtheworld@gmail.com">plates.arounddtheworld@gmail.com</a> and we will delete the address.</p>
</details>
<!-- PRIVACY:END -->
"""

AFFILIATE = """<!-- AFFILIATE:START -->
<!-- No affiliate links on this page, so the disclosure is not shown.
     When a link exists, put this above it and use rel="sponsored nofollow":
     Some links on this page are affiliate links. If you buy or book through them, we may earn a small commission at no extra cost to you. We only recommend things we'd use ourselves, and we say so when we haven't tried something.
     Recipe pages also have GEAR markers. Backend fills those from data/gear. -->
<!-- AFFILIATE:END -->
"""

TOKYO_CREDIT = "Our photo: Asakusa, Tokyo, Oct 2024."
RAMEN_CREDIT = 'Photo: <a href="https://commons.wikimedia.org/wiki/File:Ramen_with_eggs.jpg">Douglas Paul Perkins / Wikimedia Commons</a> (CC0). Stock photo, not from our trip.'
BANGKOK_CREDIT = 'Photo: <a href="https://commons.wikimedia.org/wiki/File:2016_Bangkok,_Dystrykt_Samphanthawong,_Ulica_Yaowarat,_Uliczne_jedzenie_(01).jpg">Marcin Konsek / Wikimedia Commons</a> (<a href="https://creativecommons.org/licenses/by-sa/4.0">CC BY-SA 4.0</a>), cropped. Stock photo, not from our trip.'
LISBON_CREDIT = 'Photo: <a href="https://commons.wikimedia.org/wiki/File:Manteigaria_(51156209498).jpg">Shinpachi Shimura / Wikimedia Commons</a> (<a href="https://creativecommons.org/licenses/by/2.0">CC BY 2.0</a>), cropped. Stock photo, not from our trip. Pastéis de nata at Manteigaria, Lisbon.'
BUTTER_CREDIT = 'Photo: <a href="https://commons.wikimedia.org/wiki/File:Murgh_Makhani_(Butter_Chicken)_(8039245631).jpg">Luca Nebuloni / Wikimedia Commons</a> (<a href="https://creativecommons.org/licenses/by/2.0">CC BY 2.0</a>), cropped. Stock photo, not our own cooking.'

NAV = [
    ("/guides", "Restaurant Guides", "guides"),
    ("/recipes", "Recipes", "recipes"),
    ("/about", "About", "about"),
    ("/contact", "Contact", "contact"),
]


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def picture(rel: str, alt: str, width: int, height: int, widths: tuple[int, ...], sizes: str, loading: str | None = "lazy", fetch: str | None = None) -> str:
    stem = Path(rel).stem
    avif = ", ".join(f"/assets/img/opt/{stem}-{w}.avif {w}w" for w in widths)
    webp = ", ".join(f"/assets/img/opt/{stem}-{w}.webp {w}w" for w in widths)
    extra = ""
    if loading:
        extra += f' loading="{loading}"'
    if fetch:
        extra += f' fetchpriority="{fetch}"'
    return (
        f'<picture><source type="image/avif" srcset="{avif}" sizes="{sizes}">'
        f'<source type="image/webp" srcset="{webp}" sizes="{sizes}">'
        f'<img src="/assets/img/{rel}" alt="{esc(alt)}" width="{width}" height="{height}"{extra}></picture>'
    )


def header(current: str | None) -> str:
    items = []
    for href, label, key in NAV:
        current_attr = ' aria-current="page"' if key == current else ""
        items.append(f'<li><a href="{href}"{current_attr}>{label}</a></li>')
    return f"""<a class="skip" href="#content">Skip to content</a>
<header>
<div class="nav">
<a class="brand" href="/"><img class="mark" src="/assets/img/icon.jpg" srcset="/assets/img/opt/icon-84.webp 84w" sizes="42px" alt="" width="42" height="42">Plates Around the World</a>
<button class="search-toggle" type="button" aria-label="Search" aria-expanded="false" aria-controls="site-search"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="10" cy="10" r="6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15 15l5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
<button class="menu" type="button" aria-label="Menu" aria-expanded="false" aria-controls="site-nav">Menu</button>
<nav id="site-nav" aria-label="Primary"><div class="search-slot">{SEARCH}</div><ul>
{''.join(items)}
</ul></nav>
</div>
</header>
"""


def footer() -> str:
    return """<footer>
<div class="wrap">
<p><strong>Plates Around the World</strong> · Restaurants. Recipes. Every corner of the map.</p>
<p><a href="https://www.instagram.com/platesaroundtheworld_/" target="_blank" rel="noopener">Instagram</a> · <a href="https://www.pinterest.com/platesarounddtheworld/" target="_blank" rel="noopener">Pinterest</a> · <a href="https://www.youtube.com/@platesaroundtheworld" target="_blank" rel="noopener">YouTube</a></p>
<p><a href="mailto:plates.arounddtheworld@gmail.com">plates.arounddtheworld@gmail.com</a></p>
<p>Guides are researched from public ratings and press coverage unless marked as a first-hand visit. <a href="/disclosure.html">Disclosure</a>. © 2026</p>
</div>
</footer>
<script src="/assets/main.js" defer></script>
"""


def head(title, description, path, og_type, image, iw, ih, ialt, jsonld=None, robots=None) -> str:
    canon = ""
    if path is not None:
        canon = f'<link rel="canonical" href="{HOST}{path}">'
    robots_tag = f'<meta name="robots" content="{robots}">' if robots else ""
    ld = ""
    if jsonld is not None:
        payload = json.dumps(jsonld, ensure_ascii=False, indent=2) if jsonld else ""
        ld = "<!-- JSON-LD:START -->\n"
        if payload:
            ld += '<script type="application/ld+json">\n' + payload + "\n</script>\n"
        ld += "<!-- JSON-LD:END -->"
    url = HOST + path if path is not None else HOST + "/"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{canon}
{robots_tag}
<meta property="og:site_name" content="Plates Around the World">
<meta property="og:locale" content="en_GB">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{HOST}{image}">
<meta property="og:image:width" content="{iw}">
<meta property="og:image:height" content="{ih}">
<meta property="og:image:alt" content="{esc(ialt)}">
<meta property="og:image:type" content="image/jpeg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{HOST}{image}">
<meta name="twitter:image:alt" content="{esc(ialt)}">
<link rel="icon" href="/assets/img/favicon.svg" type="image/svg+xml">
<link rel="preload" href="/assets/fonts/fraunces-normal-560-latin.woff2" as="font" type="font/woff2" crossorigin>
<style>__CSS__</style>
{ld}
</head>
<body>
""".replace("__CSS__", (ROOT / "assets" / "style.css").read_text(encoding="utf-8"))


def org():
    return {
        "@type": "Organization",
        "@id": HOST + "/#organization",
        "name": "Plates Around the World",
        "url": HOST + "/",
        "logo": {"@type": "ImageObject", "url": HOST + "/assets/img/icon.jpg", "width": 720, "height": 720},
        "sameAs": [
            "https://www.instagram.com/platesaroundtheworld_/",
            "https://www.pinterest.com/platesarounddtheworld/",
            "https://www.youtube.com/@platesaroundtheworld",
        ],
    }


def crumbs(items: list[tuple[str, str | None]]) -> str:
    lis = []
    for label, href in items:
        if href:
            lis.append(f'<li><a href="{href}">{esc(label)}</a></li>')
        else:
            lis.append(f"<li>{esc(label)}</li>")
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>'


def crumb_ld(items: list[tuple[str, str | None]]) -> dict:
    elements = []
    for index, (label, href) in enumerate(items, start=1):
        entry = {"@type": "ListItem", "position": index, "name": label}
        if href:
            entry["item"] = HOST + href
        elements.append(entry)
    return {"@type": "BreadcrumbList", "itemListElement": elements}


def meta_line(updated: str | None) -> str:
    if updated:
        return f'Published 16 Oct 2026 · Updated <time datetime="{updated[0]}">{updated[1]}</time>'
    return "Published 16 Oct 2026"


def newsletter_inline() -> str:
    return f'''<aside class="inline-news"><p class="kicker">Newsletter</p>
<h2>New recipes and guides in your inbox.</h2>
<p>Every source linked. No spam, unsubscribe any time.</p>
{NEWSLETTER}
</aside>'''


def newsletter_band() -> str:
    return f'''<section class="news"><div class="wrap"><p class="kicker">Newsletter</p>
<h2>New recipes and guides in your inbox.</h2>
<p>Every source linked. No spam, unsubscribe any time.</p>
{NEWSLETTER}
<div class="social"><a href="https://www.instagram.com/platesaroundtheworld_/" target="_blank" rel="noopener">Instagram</a><a href="https://www.pinterest.com/platesarounddtheworld/" target="_blank" rel="noopener">Pinterest</a><a href="https://www.youtube.com/@platesaroundtheworld" target="_blank" rel="noopener">YouTube</a></div>
</div></section>'''


def tile(href, heading, blurb, image=None, alt="", tag="", region="", credit="", stock=False, width=1200, height=750, widths=(480, 800, 1200)):
    media = picture(image, alt, width, height, widths, CARD_SIZES) if image else ""
    kick = []
    if tag:
        kick.append(f'<span class="tag">{esc(tag)}</span>')
    if stock:
        kick.append('<span class="tag">Stock photo</span>')
    if region:
        kick.append(f'<span class="region">{esc(region)}</span>')
    kicker = f'<p class="card-kicker">{"".join(kick)}</p>' if kick else ""
    credit_html = f'<p class="credit">{credit}</p>' if credit else ""
    return (
        f'<div class="tile"><a class="card" href="{href}">{media}<div class="card-body">{kicker}'
        f"<h3>{esc(heading)}</h3><p>{esc(blurb)}</p></div></a>{credit_html}</div>"
    )


def plain(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def upgrade_trips(body: str) -> str:
    def repl(match: re.Match) -> str:
        name = match.group(1)
        alt = html.unescape(match.group(2))
        return picture(f"trip/{name}", alt, 900, 1200, (480, 800), TRIP_SIZES)
    return re.sub(r'<img src="[^"]*/(img_\d+\.jpg)" alt="([^"]*)" loading="lazy">', repl, body)


def article_shell(spec, body, jsonld) -> str:
    updated = spec.get("updated")
    stock = '<p class="card-kicker"><span class="tag">Stock photo</span></p>' if spec.get("stock") else ""
    cover = picture(spec["file"], spec["cover_alt"], spec["w"], spec["h"], spec["widths"], COVER_SIZES, loading=None, fetch="high")
    tested = f'<p class="note">{spec["tested"]}</p>' if spec.get("tested") else ""
    band = "" if spec.get("newsletter_in_body") else newsletter_band()
    keep = f'<section class="keep-reading"><div class="wrap"><h2>Keep reading</h2><div class="grid">{"".join(spec["keep"])}</div></div></section>'
    main = f"""<main id="content">
<article>
{crumbs(spec["crumbs"])}
<span class="tag">{esc(spec["tag"])}</span>
<h1>{esc(spec["h1"])}</h1>
<p class="meta">{meta_line(updated)}</p>
<p class="byline">By Plates Around the World</p>
<p class="lead">{spec["lead"]}</p>
{tested}
{stock}
<figure>{cover}<figcaption class="credit">{spec["credit"]}</figcaption></figure>
{spec.get("card", "")}
{body}
</article>
{keep}
{AFFILIATE}
{band}
{PRIVACY}
</main>
"""
    page = head(spec["title"], spec["description"], spec["path"], "article", spec["og"], spec["ow"], spec["oh"], spec["oalt"], jsonld) + header(spec["nav"]) + main + footer() + "</body></html>\n"
    return page


def load_body(slug: str) -> str:
    return (BODIES / f"{slug}.fragment.html").read_text(encoding="utf-8")


def strip_chrome(body: str) -> str:
    body = re.sub(r'<span class="tag">.*?</span>', "", body, count=1)
    body = re.sub(r"<h1>.*?</h1>", "", body, count=1)
    body = re.sub(r'<p class="lead">.*?</p>', "", body, count=1)
    body = re.sub(r'<img class="cover"[^>]*>', "", body, count=1)
    body = re.sub(r'<p class="credit"[^>]*>.*?</p>', "", body, count=1)
    body = body.replace("<!-- Cover: founder photo IMG_1460, Asakusa, Oct 2024 -->", "")
    return body.strip()


def common_links(body: str) -> str:
    return (
        body.replace("../about.html#method", "/about#method")
        .replace('href="ramen-101.html"', 'href="/articles/ramen-101"')
        .replace('href="where-to-eat-tokyo.html"', 'href="/articles/where-to-eat-tokyo"')
        .replace("../assets/", "/assets/")
    )


def tokyo_body() -> str:
    body = load_body("where-to-eat-tokyo")
    old_note = "Researched guide: built from public guides and reference sources, not a first-hand visit."
    new_note = "Researched guide, illustrated with our own photos from Tokyo (Oct 2024). The neighbourhood picks are built from public guides and reference sources; we haven't reviewed the venues named here."
    if old_note not in body:
        raise SystemExit("tokyo note missing")
    body = body.replace(old_note, new_note, 1)
    old_rai = "The original closed in 1976, and Wikipedia reports a descendant of the founder reopened it in Asakusa in 2026, which makes Asakusa a fitting stop for noodle history fans."
    new_rai = "The original closed in 1976. Fifty years later, on 2 July 2026, Asakusa Rairaiken reopened a short walk from the Tsukuba Express Asakusa Station, The Japan Times reported, which makes Asakusa a fitting stop for noodle-history fans."
    if old_rai not in body:
        raise SystemExit("tokyo rairaiken sentence missing")
    body = body.replace(old_rai, new_rai, 1)
    old_sources = "<strong>Sources (checked 16 Oct 2026):</strong> <a href=\"https://en.wikipedia.org/wiki/Tsukiji_fish_market\">Wikipedia: Tsukiji fish market</a>; <a href=\"https://en.wikipedia.org/wiki/Ameya-Yokoch%C5%8D\">Wikipedia: Ameya-Yokochō</a>; <a href=\"https://www.japan-guide.com/e/e3011.html\">japan-guide.com: Shinjuku</a>; <a href=\"https://en.wikipedia.org/wiki/Ramen\">Wikipedia: Ramen</a>."
    new_sources = "<strong>Sources (checked 16 Oct 2026; Rairaiken updated 22 Oct 2026):</strong> <a href=\"https://en.wikipedia.org/wiki/Tsukiji_fish_market\">Wikipedia: Tsukiji fish market</a>; <a href=\"https://en.wikipedia.org/wiki/Ameya-Yokoch%C5%8D\">Wikipedia: Ameya-Yokochō</a>; <a href=\"https://www.japan-guide.com/e/e3011.html\">japan-guide.com: Shinjuku</a>; <a href=\"https://en.wikipedia.org/wiki/Ramen\">Wikipedia: Ramen</a>; <a href=\"https://www.japantimes.co.jp/life/2026/07/03/food-drink/first-ramen-shop-rairaiken-reopening-asakusa-tokyo-shoyu/\">The Japan Times: \"Japan's first standalone ramen shop reopens in Asakusa\" (3 Jul 2026)</a>."
    if old_sources not in body:
        raise SystemExit("tokyo sources missing")
    body = body.replace(old_sources, new_sources, 1)
    body = body.replace(
        "Sliced rolled meat with a green herb filling, Shibuya, Oct 2024",
        "Sliced rolled meat with a green herb filling and green sauce on a dark plate, Shibuya, Oct 2024",
    )
    body = body.replace(
        "Soup with mushrooms in a red lacquer bowl, Tsukiji, Oct 2024",
        "Mushroom soup in a red lacquer bowl, Tsukiji, Oct 2024",
    )
    body = body.replace(
        "Think bento, wagashi (Japanese sweets), pickles and immaculate fruit.</p>",
        "Think bento, wagashi (Japanese sweets), pickles and immaculate fruit.</p>\n<!-- FUTURE-LINK: Depachika 101, not published -->",
        1,
    )
    body = body.replace(
        "They're perfect for a cheap breakfast or a late-night bite on the way back to your hotel.</p>",
        "They're perfect for a cheap breakfast or a late-night bite on the way back to your hotel.</p>\n<!-- FUTURE-LINK: Konbini tier list, not published -->",
        1,
    )
    body = common_links(strip_chrome(body))
    body = upgrade_trips(body)
    if "<p class=\"sources\">" not in body:
        raise SystemExit("tokyo sources paragraph missing after strip")
    body = body.replace("<p class=\"sources\">", newsletter_inline() + "\n<p class=\"sources\">", 1)
    return body


def ramen_body() -> str:
    body = common_links(strip_chrome(load_body("ramen-101")))
    needle = "<h2>Where to learn more</h2>"
    if needle not in body:
        raise SystemExit("ramen heading missing")
    return body.replace(needle, newsletter_inline() + "\n" + needle, 1)


def guide_body(slug: str) -> str:
    return common_links(strip_chrome(load_body(slug)))


def butter_body() -> tuple[str, list[str], list[str]]:
    raw = load_body("butter-chicken")
    ingredients = [plain(item) for item in re.findall(r"<li>(.*?)</li>", raw.split("<h2>Method</h2>")[0])]
    steps = [plain(item) for item in re.findall(r"<li>(.*?)</li>", raw.split("<h2>Method</h2>")[1])]
    if len(ingredients) != 15 or len(steps) != 6:
        raise SystemExit(f"butter lists changed: {len(ingredients)} ingredients, {len(steps)} steps")
    body = raw.replace(" Our version keeps the char and the silky sauce. Serves 4.", " Our version keeps the char and the silky sauce.")
    if "Serves 4" in body:
        raise SystemExit("serves line still present")
    developed = " Recipe developed for home kitchens by Plates Around the World."
    if developed not in body:
        raise SystemExit("developed sentence missing")
    body = body.replace(developed, "")
    body = common_links(strip_chrome(body))
    body = body.replace("<h2>Ingredients</h2>", '<h2 id="ingredients">Ingredients</h2>', 1)
    gear = """<!-- GEAR:START -->
<!-- What we used: Backend replaces this interior from data/gear/butter-chicken.json. Empty list means no section. -->
<!-- GEAR:END -->
<!-- NOTES:START -->
<p class="missing">Notes and swaps: OWNER TO SUPPLY</p>
<!-- NOTES:END -->
<!-- MEASURES: US cups and ounces are OWNER TO SUPPLY. Ingredient lines stay as published. -->
"""
    if "<h2>Method</h2>" not in body:
        raise SystemExit("method heading missing")
    body = body.replace("<h2>Method</h2>", gear + '<h2 id="method">Method</h2>', 1)
    body += "\n<!-- FUTURE-LINK: India State by State #1: Punjab, not published. When it is live, list it first in Keep reading. -->"
    return body, ingredients, steps


def link_row(href: str, kicker: str, heading: str, blurb: str) -> str:
    return (
        f'<a class="more-link" href="{href}"><span class="more-copy"><span class="kicker">{esc(kicker)}</span>'
        f"<strong>{esc(heading)}</strong><span>{esc(blurb)}</span></span>"
        f'<span class="more-go" aria-hidden="true">→</span></a>'
    )


def recipe_card() -> str:
    pending = [
        ("serves", "Serves"),
        ("prep", "Prep"),
        ("marinate", "Marinate"),
        ("cook", "Cook"),
        ("total", "Total"),
        ("diet", "Diet"),
        ("difficulty", "Difficulty"),
        ("equipment", "Equipment"),
    ]
    slots = "".join(f'<span data-field="{key}">{label}: OWNER TO SUPPLY</span>' for key, label in pending)
    return f'''<section class="recipe-card" aria-label="Recipe card">
<p class="kicker">Recipe</p>
<p class="recipe-name">Butter Chicken (Murgh Makhani)</p>
<dl class="stats stats-known">
<div data-field="cuisine"><dt>Cuisine</dt><dd>Indian (Punjabi / Delhi)</dd></div>
<div data-field="course"><dt>Course</dt><dd>Main</dd></div>
</dl>
<p class="slot-note">Times and servings: owner to supply</p>
<div class="recipe-slots" aria-hidden="true">{slots}</div>
<!-- RECIPE-SLOTS: Backend can replace each data-field value. Known fields stay in the dl above. Do not invent times or servings. -->
<p class="btns"><a class="btn" href="#ingredients">Jump to recipe</a> <button class="btn line" type="button" data-print>Print</button></p>
</section>'''


def article_ld(spec) -> dict:
    url = HOST + spec["path"]
    article = {
        "@type": "Article",
        "headline": spec["h1"],
        "description": spec["description"],
        "image": HOST + spec["og"],
        "datePublished": "2026-10-16",
        "dateModified": spec["modified"],
        "author": {"@type": "Organization", "name": "Plates Around the World", "url": HOST + "/"},
        "publisher": {
            "@type": "Organization",
            "name": "Plates Around the World",
            "logo": {"@type": "ImageObject", "url": HOST + "/assets/img/icon.jpg"},
        },
        "mainEntityOfPage": url,
    }
    return {"@context": "https://schema.org", "@graph": [article, crumb_ld(spec["crumbs"])]}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def kept_span(path: Path, start: str, end: str) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    i = text.find(start)
    j = text.find(end)
    if i == -1 or j == -1 or j < i:
        return None
    return text[i:j + len(end)]


def restore_markers(path: Path, html: str) -> str:
    """Leave JSON-LD and gear interiors untouched. The content build owns them."""
    for start, end in (
        ("<!-- JSON-LD:START -->", "<!-- JSON-LD:END -->"),
        ("<!-- GEAR:START -->", "<!-- GEAR:END -->"),
    ):
        current = kept_span(path, start, end)
        if current is None:
            continue
        i = html.find(start)
        j = html.find(end)
        if i == -1 or j == -1 or j < i:
            continue
        html = html[:i] + current + html[j + len(end):]
    return html


def publish(path: Path, html: str) -> None:
    write(path, restore_markers(path, html))


def build_cards():
    tokyo_blurb = "Breakfast at Tsukiji, snacks under the tracks at Ameyoko, yakitori in Shinjuku's memory lane: Tokyo, one neighbourhood at a time."
    ramen_blurb = "Four bowls, one cheat-sheet: what each style means, where it comes from, and which to order first."
    bangkok_blurb = "From Jay Fai's crab omelette to the night stalls of Yaowarat, the Bangkok plates the critics keep coming back to."
    lisbon_blurb = "Custard tarts in Belém, garlic prawns at Ramiro and a market hall built for grazing: Lisbon's most-praised tables."
    butter_blurb = "Smoky charred chicken in a silky tomato, butter and cream sauce. Here's the Delhi classic, made at home."
    cards = {
        "tokyo": tile("/articles/where-to-eat-tokyo", "Where to eat in Tokyo", tokyo_blurb, "where-to-eat-tokyo.jpg", "Red-bean pancake sandwich and a white teapot on a tray in Asakusa, Tokyo (our photo, Oct 2024)", "Researched guide · our photos", "Japan", TOKYO_CREDIT, False, 1600, 1000, (480, 800, 1200)),
        "ramen": tile("/articles/ramen-101", "Ramen 101: shoyu, shio, miso & tonkotsu", ramen_blurb, "ramen-101.jpg", "Bowl of ramen with two soft-boiled eggs, chāshū pork, sweetcorn, sliced leek and nori (stock photo)", "Deep-dive", "Japan", RAMEN_CREDIT, True),
        "bangkok": tile("/articles/best-street-food-bangkok", "Best street food in Bangkok", bangkok_blurb, "bangkok.jpg", "Spring rolls, fried fritters and wrapped rolls stacked on a street-food stall on Yaowarat Road, Bangkok (stock photo)", "Researched guide", "Thailand", BANGKOK_CREDIT, True),
        "lisbon": tile("/articles/where-to-eat-lisbon", "Where to eat in Lisbon", lisbon_blurb, "lisbon.jpg", "Two pastéis de nata on a plate between two cups of coffee on a counter at Manteigaria, Lisbon (stock photo)", "Researched guide", "Portugal", LISBON_CREDIT, True),
        "butter": tile("/articles/butter-chicken", "Butter chicken (murgh makhani)", butter_blurb, "butter-chicken.jpg", "Murgh makhani (butter chicken) beside a piece of naan on a white plate (stock photo)", "Recipe", "Delhi", BUTTER_CREDIT, True),
        "guides": link_row("/guides", "Guides", "All restaurant guides", "Built from public guides, critics and reference sources, with every source linked."),
        "recipes": link_row("/recipes", "Recipes", "All recipes", "Step-by-step home versions of the world's favourite plates. More on the way."),
    }
    cards["tokyo_long"] = tile("/articles/where-to-eat-tokyo", "Where to Eat in Tokyo: A First-Timer's Neighbourhood Guide", tokyo_blurb, "where-to-eat-tokyo.jpg", "Red-bean pancake sandwich and a white teapot on a tray in Asakusa, Tokyo (our photo, Oct 2024)", "Researched guide · our photos", "Japan", TOKYO_CREDIT, False, 1600, 1000)
    cards["ramen_long"] = tile("/articles/ramen-101", "Ramen 101: Shoyu, Shio, Miso & Tonkotsu Explained", ramen_blurb, "ramen-101.jpg", "Bowl of ramen with two soft-boiled eggs, chāshū pork, sweetcorn, sliced leek and nori (stock photo)", "Deep-dive", "Japan", RAMEN_CREDIT, True)
    cards["bangkok_long"] = tile("/articles/best-street-food-bangkok", "Best Street Food in Bangkok", bangkok_blurb, "bangkok.jpg", "Spring rolls, fried fritters and wrapped rolls stacked on a street-food stall on Yaowarat Road, Bangkok (stock photo)", "Researched guide", "Thailand", BANGKOK_CREDIT, True)
    cards["lisbon_long"] = tile("/articles/where-to-eat-lisbon", "Where to Eat in Lisbon", lisbon_blurb, "lisbon.jpg", "Two pastéis de nata on a plate between two cups of coffee on a counter at Manteigaria, Lisbon (stock photo)", "Researched guide", "Portugal", LISBON_CREDIT, True)
    cards["butter_long"] = tile("/articles/butter-chicken", "Butter Chicken (Murgh Makhani) at Home", butter_blurb, "butter-chicken.jpg", "Murgh makhani (butter chicken) beside a piece of naan on a white plate (stock photo)", "Recipe", "Delhi", BUTTER_CREDIT, True)
    cards["ramen_short"] = tile("/articles/ramen-101", "Ramen 101", ramen_blurb, "ramen-101.jpg", "Bowl of ramen with two soft-boiled eggs, chāshū pork, sweetcorn, sliced leek and nori (stock photo)", "Deep-dive", "Japan", RAMEN_CREDIT, True)
    cards["tokyo_short"] = tile("/articles/where-to-eat-tokyo", "Where to Eat in Tokyo", tokyo_blurb, "where-to-eat-tokyo.jpg", "Red-bean pancake sandwich and a white teapot on a tray in Asakusa, Tokyo (our photo, Oct 2024)", "Researched guide · our photos", "Japan", TOKYO_CREDIT, False, 1600, 1000)
    return cards


def hero() -> str:
    return """<section class="hero"><div class="wrap hero-grid">
<div>
<p class="tagline">Restaurants. Recipes. Every corner of the map.</p>
<h1 aria-label="Every corner of the map, served.">Every corner of the map, <em>served.</em></h1>
<p class="rot">Tonight in <b data-list='["Bangkok…","Lisbon…","Delhi…","Tokyo…"]'>Bangkok…</b></p>
<p class="lead">Pull up a chair. We dig through the guides, critics and locals' favourites so you know where to eat, and how to cook it at home.</p>
<div class="btns"><a class="btn" href="/guides">Explore guides</a><a class="btn alt" href="/recipes">Cook a recipe</a></div>
</div>
<div class="logo-stage" aria-hidden="true">
<svg viewBox="0 0 400 400">
<g class="steam"><path d="M168 96c-12-18 8-30 0-48"/><path d="M200 86c-12-18 8-30 0-48"/><path d="M232 96c-12-18 8-30 0-48"/></g>
<circle cx="200" cy="228" r="150" fill="#241f1c"/>
<circle cx="200" cy="228" r="128" fill="none" stroke="#FBF6EC" stroke-width="16"/>
<circle class="rim" cx="200" cy="228" r="146" fill="none" stroke="#C8553D" stroke-width="7"/>
</svg>
<div class="plate-map"><span></span></div>
</div>
</div></section>
"""


def marquee() -> str:
    parts = ["Bangkok", "Pad Thai", "Lisbon", "Pastel de nata", "Delhi", "Butter chicken", "Tokyo", "Ramen", "Istanbul", "Simit", "Naples", "Pizza margherita"]
    one = "".join(f"<span>{esc(part)}</span><span>·</span>" for part in parts)
    return f'<div class="marquee" aria-hidden="true"><div class="track">{one}{one}</div></div>'


def pins() -> str:
    live = [
        ("/articles/best-street-food-bangkok", "77.9%", "47.4%", "Bangkok"),
        ("/articles/where-to-eat-lisbon", "47.5%", "29.5%", "Lisbon"),
        ("/articles/butter-chicken", "71.4%", "36.7%", "Delhi"),
        ("/articles/where-to-eat-tokyo", "88.8%", "31.7%", "Tokyo"),
    ]
    soon = [
        ("22.5%", "43.3%", "Mexico City · soon"),
        ("58.1%", "27.8%", "Istanbul · soon"),
        ("29.4%", "28.1%", "New York · soon"),
        ("55.1%", "81.3%", "Cape Town · soon"),
        ("28.6%", "65.8%", "Lima · soon"),
    ]
    html_pins = []
    for href, left, top, label in live:
        html_pins.append(f'<a class="pin" href="{href}" style="left:{left};top:{top}"><i></i><span>{label}</span></a>')
    for left, top, label in soon:
        html_pins.append(f'<span class="pin soon" style="left:{left};top:{top}"><i></i><span>{label}</span></span>')
    return f'<div class="worldmap"><img src="/assets/img/world.svg" alt="" width="360" height="140" loading="lazy">{"".join(html_pins)}</div>'


def homepage(cards) -> str:
    insta = [
        ("trip/img_1528.jpg", "Our Instagram: tray of small side dishes and rice at Tsukiji, Tokyo"),
        ("trip/img_1384.jpg", "Our Instagram: sliced rolled meat with a green herb filling, Shibuya, Tokyo"),
        ("trip/img_1537.jpg", "Our Instagram: ice cream with candy toppings, Ebisu, Tokyo"),
        ("trip/img_1460.jpg", "Our Instagram: red-bean pancake sandwich and tea, Asakusa, Tokyo"),
        ("trip/img_1529.jpg", "Our Instagram: mushroom soup in a red lacquer bowl, Tsukiji, Tokyo"),
        ("trip/img_1579.jpg", "Our Instagram: a plate of edamame, Shinjuku, Tokyo"),
    ]
    tiles = []
    for rel, alt in insta:
        tiles.append(f'<a href="https://www.instagram.com/platesaroundtheworld_/" target="_blank" rel="noopener">{picture(rel, alt, 900, 1200, (480, 800), INSTA_SIZES)}</a>')
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": "Plates Around the World", "url": HOST + "/", "description": HOME_DESC, "publisher": {"@id": HOST + "/#organization"}},
            org(),
        ],
    }
    title = "Plates Around the World: Restaurant Guides & Home Recipes"
    main = f"""<main id="content">
{hero()}
{marquee()}
<section class="rv" id="guides"><div class="wrap"><div class="sec-head"><div><p class="kicker">Featured guides</p><h2>Where the <em>critics</em> keep going back.</h2></div><p class="sub">Researched city guides, with sources on every page. First-hand visits are always marked.</p></div>
<div class="grid grid-2">{cards["tokyo"]}{cards["ramen"]}{cards["bangkok"]}{cards["lisbon"]}</div>
</div></section>
<section class="mapsec rv"><div class="wrap"><div class="sec-head"><div><p class="kicker">Where to next?</p><h2>Pick a pin. Pack an appetite.</h2></div><p class="sub">Glowing pins are live. The rest are simmering, coming soon.</p></div>
{pins()}
</div></section>
<section class="rv"><div class="wrap"><div class="sec-head"><div><p class="kicker">Latest recipes</p><h2>Bring it <em>home.</em></h2></div><p class="sub">Dishes from the road, written for your kitchen.</p></div>
<div class="grid grid-2">{cards["butter"]}
<div class="spin"><div class="spinplate"><b>Feeling hungry?</b></div><div><p class="spin-result"></p><button class="btn" id="spin" type="button">Spin the plate</button></div></div>
</div></div></section>
{newsletter_band()}
{PRIVACY}
<section class="rv"><div class="wrap"><div class="sec-head"><div><p class="kicker">@platesaroundtheworld_</p><h2>On the gram.</h2></div><p class="sub"><a href="https://www.instagram.com/platesaroundtheworld_/" target="_blank" rel="noopener">Follow @platesaroundtheworld_</a></p></div>
<div class="insta">{''.join(tiles)}</div></div></section>
</main>
"""
    return head(title, HOME_DESC, "/", "website", "/assets/img/banner.jpg", 1280, 720, BANNER_ALT, graph) + header("home") + main + footer() + "</body></html>\n"


HOME_DESC = "Researched restaurant guides, street-food tips and home recipes from Tokyo to Bangkok, Lisbon and Delhi, with every source cited and our own trip photos marked."
BANNER_ALT = "Plates Around the World logo: a terracotta plate with a small world map, on a dark background."


def guides_page(cards) -> str:
    title = "Restaurant & Street Food Guides | Plates Around the World"
    desc = "City food guides for Tokyo, Bangkok and Lisbon: where to eat, what to order and when to go. Researched from critics and guides, with every source cited."
    sub = "Built from public guides, critics and reference sources, with every source linked. Where we use our own trip photos or visited first-hand, we say so on the page."
    main = f"""<main id="content"><section class="index-head"><div class="wrap">
<p class="kicker">Plates Around the World</p>
<h1>Restaurant Guides</h1>
<p class="sub">{sub}</p>
<h2 class="hub-label">Japan</h2>
<div class="grid">{cards["tokyo"]}{cards["ramen"]}</div>
<h2 class="hub-label">Thailand</h2>
<div class="grid">{cards["bangkok"]}</div>
<h2 class="hub-label">Portugal</h2>
<div class="grid">{cards["lisbon"]}</div>
</div></section></main>
"""
    return head(title, desc, "/guides", "website", "/assets/img/banner.jpg", 1280, 720, BANNER_ALT) + header("guides") + main + footer() + "</body></html>\n"


def recipes_page(cards) -> str:
    title = "Home Recipes from Around the World | Plates Around the World"
    desc = "Home versions of dishes from around the world, starting with Delhi-style butter chicken (murgh makhani). Clear ingredients, step-by-step method, sources cited."
    main = f"""<main id="content"><section class="index-head"><div class="wrap">
<p class="kicker">Plates Around the World</p>
<h1>Recipes</h1>
<p class="sub">Step-by-step home versions of the world's favourite plates. More on the way.</p>
<div class="grid">{cards["butter"]}</div>
</div></section></main>
"""
    return head(title, desc, "/recipes", "website", "/assets/img/banner.jpg", 1280, 720, BANNER_ALT) + header("recipes") + main + footer() + "</body></html>\n"


def about_page() -> str:
    title = "About | Plates Around the World"
    desc = "The story behind Plates Around the World, and how we research our guides."
    main = """<main id="content"><div class="page">
<h1>About us</h1>
<p>Plates Around the World started with a simple question every traveller asks: <em>where should we eat?</em> We're here to answer it like a well-travelled friend would: warmly, curiously, and honestly.</p>
<p>We publish city restaurant guides, street food round-ups and home recipes so you can taste the world on the road or in your own kitchen.</p>
<div class="note" id="method"><strong>How we research.</strong> Unless a guide is clearly marked <strong>"First-hand visit"</strong>, it is researched from public ratings and press coverage, such as the Michelin Guide, respected food media and well-known review platforms. We name our sources at the end of every guide. We never present research as a personal visit. Opening hours and prices change, so please check before you go.</div>
<p>Spotted something out of date? <a href="/contact">Tell us</a> and we'll fix it.</p>
</div></main>
"""
    return head(title, desc, "/about", "website", "/assets/img/banner.jpg", 1280, 720, BANNER_ALT) + header("about") + main + footer() + "</body></html>\n"


def contact_page() -> str:
    title = "Contact | Plates Around the World"
    desc = "Get in touch with Plates Around the World."
    main = """<main id="content"><div class="page">
<h1>Say hello</h1>
<p>Tips, corrections, collaborations: we read everything.</p>
<p>Email us at <a href="mailto:plates.arounddtheworld@gmail.com"><strong>plates.arounddtheworld@gmail.com</strong></a></p>
<p class="btns"><a class="btn" href="mailto:plates.arounddtheworld@gmail.com">Email us</a></p>
<form class="contact" action="mailto:plates.arounddtheworld@gmail.com" method="post" enctype="text/plain">
<label for="contact-name">Your name</label>
<input id="contact-name" name="name" autocomplete="name" placeholder="Your name" required>
<label for="contact-email">Email</label>
<input id="contact-email" type="email" name="email" autocomplete="email" placeholder="Email" required>
<label for="contact-body">Message</label>
<textarea id="contact-body" name="body" rows="6" placeholder="Message" required></textarea>
<button class="btn" type="submit">Send</button>
</form>
<p>Prefer your own mail app? Write to <a href="mailto:plates.arounddtheworld@gmail.com">plates.arounddtheworld@gmail.com</a>.</p>
</div></main>
"""
    return head(title, desc, "/contact", "website", "/assets/img/banner.jpg", 1280, 720, BANNER_ALT) + header("contact") + main + footer() + "</body></html>\n"


def not_found() -> str:
    title = "Page not found | Plates Around the World"
    desc = "That page isn't on Plates Around the World."
    main = """<main id="content" class="not-found">
<p class="kicker">404</p>
<h1>Page not found</h1>
<p>That page isn't on Plates Around the World.</p>
<p><a class="btn" href="/">Back to the homepage</a></p>
</main>
"""
    return head(title, desc, None, "website", "/assets/img/banner.jpg", 1280, 720, BANNER_ALT, robots="noindex") + header(None) + main + footer() + "</body></html>\n"


def template_page() -> str:
    title = "ARTICLE TITLE"
    desc = "META DESCRIPTION: 150–160 characters, specific dishes/places, no claims we can't source."
    card = recipe_card().replace("Butter Chicken (Murgh Makhani)", "RECIPE NAME")
    main = f"""<main id="content">
<article>
{crumbs([("Home", "/"), ("Section", "/guides"), ("ARTICLE TITLE", None)])}
<span class="tag">TAG</span>
<h1>ARTICLE TITLE</h1>
<p class="meta">Published <time datetime="YYYY-MM-DD">DD Mon YYYY</time></p>
<p class="byline">By Plates Around the World</p>
<p class="lead">ONE-LINE LEAD</p>
<!-- HONESTY: use one of these, and delete the others.
     (1) Researched guide: built from public guides and reference sources, not a first-hand visit.
     (2) Researched guide, illustrated with our own photos from PLACE (Mon YYYY). We haven't reviewed the venues named here.
     (3) First-hand visit: we ate here in Mon YYYY and paid our own way.
     Use (3) only with owner photos and notes. -->
<p class="card-kicker"><span class="tag">Stock photo</span></p>
<figure><img class="cover" src="/assets/img/SLUG.jpg" alt="DESCRIBE WHAT IS IN THE PHOTO (+ our photo, Mon YYYY or stock photo)" width="1200" height="750">
<figcaption class="credit">Photo: NAME / SITE (LICENCE). Stock photo, not from our trip.</figcaption></figure>
<!-- Credit alternative when the photo is ours: Our photo: PLACE, Mon YYYY. Strip EXIF/GPS. Do not edit faces here; flag non-owner faces for review. -->
<div class="recipe-card" hidden>
{card}
</div>
<!-- RECIPE-CARD: the block above is hidden until this is a recipe. Move it into view and delete hidden. Guides omit it. Keep the GEAR markers on recipe pages, directly after Ingredients. -->
<h2>Section heading</h2>
<p>Replace this paragraph. Do not paste another article's text here.</p>
<h2 id="ingredients">Ingredients</h2>
<p class="missing">RECIPE ONLY. Leave this heading out of a guide.</p>
<!-- GEAR:START -->
<!-- GEAR:END -->
<p class="sources"><strong>Sources (checked DD Mon YYYY):</strong> <a href="URL">Publisher: Title (date)</a>. Hours change, so check before you go.</p>
</article>
<section class="keep-reading"><div class="wrap"><h2>Keep reading</h2><div class="grid">
<!-- 3 cards. Copy the tile markup from index.html. href="/articles/SLUG" -->
</div></div></section>
{AFFILIATE}
<aside class="inline-news"><p class="kicker">Newsletter</p>
<h2>New recipes and guides in your inbox.</h2>
<p>Every source linked. No spam, unsubscribe any time.</p>
{NEWSLETTER}
</aside>
{PRIVACY}
</main>
"""
    page = head(title, desc, "/articles/SLUG", "article", "/assets/img/banner.jpg", 1280, 720, BANNER_ALT, jsonld="", robots="noindex") + header(None) + main + footer() + "</body></html>\n"
    return "<!-- 50–60 chars total; add \" | Plates\" only if it fits in the title. -->\n" + page


def robots() -> str:
    return """User-agent: *
Allow: /
Disallow: /templates/
Disallow: /partials/
Disallow: /scripts/
Disallow: /content/
Disallow: /docs/

Sitemap: https://platesaroundtheworld.netlify.app/sitemap.xml
"""


def redirects() -> str:
    rows = [
        "/guides /guides.html 200",
        "/recipes /recipes.html 200",
        "/about /about.html 200",
        "/contact /contact.html 200",
        "/disclosure /disclosure.html 200",
        "/articles/best-street-food-bangkok /articles/best-street-food-bangkok.html 200",
        "/articles/where-to-eat-lisbon /articles/where-to-eat-lisbon.html 200",
        "/articles/butter-chicken /articles/butter-chicken.html 200",
        "/articles/where-to-eat-tokyo /articles/where-to-eat-tokyo.html 200",
        "/articles/ramen-101 /articles/ramen-101.html 200",
    ]
    return "\n".join(rows) + "\n"


def headers() -> str:
    return """/assets/*
  Cache-Control: public, max-age=31536000, immutable

/*
  Cache-Control: public, max-age=0, must-revalidate
"""


def write_partials() -> None:
    partial = ROOT / "partials"
    partial.mkdir(exist_ok=True)
    write(partial / "header.html", "<!-- Copy into disclosure.html. Root-relative links. aria-current is added per page by scripts/render_site.py; leave it off on Disclosure. Search hooks: #site-search, [data-site-search], #site-search-results, [data-site-search-results]. -->\n" + header(None))
    write(partial / "footer.html", "<!-- Copy into disclosure.html, after <main>. Includes the Disclosure link Backend's partials/footer-disclosure.html asked for. -->\n" + footer())
    write(partial / "search.html", "<!-- Snippet. Hooks must stay: #site-search, data-site-search, #site-search-results, data-site-search-results. assets/search.js reads /data/search-index.json. -->\n" + SEARCH)
    write(partial / "newsletter-form.html", NEWSLETTER + "\n")
    write(partial / "privacy-section.html", PRIVACY + "\n")
    write(partial / "footer-disclosure.html", '<a href="/disclosure.html">Disclosure</a>\n')


def main() -> None:
    cards = build_cards()
    butter, ingredients, steps = butter_body()
    specs = {
        "where-to-eat-tokyo": {
            "title": "Where to Eat in Tokyo: A First-Timer's Neighbourhood Guide",
            "description": "Where to eat in Tokyo on a first trip: Tsukiji breakfasts, Ameyoko snacks, Shinjuku's Omoide Yokocho, ramen areas and konbini, one neighbourhood at a time.",
            "path": "/articles/where-to-eat-tokyo",
            "h1": "Where to Eat in Tokyo: A First-Timer's Neighbourhood Guide",
            "tag": "Researched guide · our photos",
            "lead": "Breakfast at Tsukiji, snacks under the tracks at Ameyoko, yakitori in Shinjuku's memory lane: Tokyo, one neighbourhood at a time.",
            "file": "where-to-eat-tokyo.jpg",
            "cover_alt": "Red-bean pancake sandwich beside a white teapot on a tray in Asakusa, Tokyo (our photo, Oct 2024)",
            "credit": TOKYO_CREDIT,
            "w": 1600, "h": 1000, "widths": (480, 800, 1200),
            "og": "/assets/img/where-to-eat-tokyo.jpg", "ow": 1600, "oh": 1000,
            "oalt": "Red-bean pancake sandwich beside a white teapot on a tray in Asakusa, Tokyo (our photo, Oct 2024)",
            "updated": ("2026-10-22", "22 Oct 2026"),
            "modified": "2026-10-22",
            "newsletter_in_body": True,
            "nav": None,
            "crumbs": [("Home", "/"), ("Restaurant Guides", "/guides"), ("Where to Eat in Tokyo: A First-Timer's Neighbourhood Guide", None)],
            "keep": [cards["ramen_long"], cards["bangkok_long"], cards["guides"]],
        },
        "ramen-101": {
            "title": "Ramen 101: Shoyu, Shio, Miso & Tonkotsu Explained | Plates",
            "description": "Shoyu, shio, miso or tonkotsu? What each ramen style means, where it comes from (Tokyo, Hakodate, Sapporo, Fukuoka) and which bowl to order first in Japan.",
            "path": "/articles/ramen-101",
            "h1": "Ramen 101: Shoyu, Shio, Miso & Tonkotsu Explained",
            "tag": "Researched guide",
            "lead": "Four bowls, one cheat-sheet: what shoyu, shio, miso and tonkotsu actually mean, where each comes from, and which one to order first.",
            "file": "ramen-101.jpg",
            "cover_alt": "Bowl of ramen with two soft-boiled eggs, chāshū pork, sweetcorn, sliced leek, wakame and nori (stock photo)",
            "credit": RAMEN_CREDIT,
            "stock": True,
            "w": 1200, "h": 750, "widths": (480, 800, 1200),
            "og": "/assets/img/ramen-101.jpg", "ow": 1200, "oh": 750,
            "oalt": "Bowl of ramen with two soft-boiled eggs, chāshū pork, sweetcorn, sliced leek, wakame and nori (stock photo)",
            "modified": "2026-10-16",
            "newsletter_in_body": True,
            "nav": None,
            "crumbs": [("Home", "/"), ("Restaurant Guides", "/guides"), ("Ramen 101: Shoyu, Shio, Miso & Tonkotsu Explained", None)],
            "keep": [cards["tokyo_long"], cards["bangkok_long"], cards["butter_long"]],
        },
        "best-street-food-bangkok": {
            "title": "Best Street Food in Bangkok: Jay Fai, Pad Thai & Yaowarat",
            "description": "Bangkok street food the critics keep coming back to: Jay Fai's crab omelette, Thipsamai's pad thai, oyster omelette and Yaowarat after dark. Sources cited.",
            "path": "/articles/best-street-food-bangkok",
            "h1": "Best Street Food in Bangkok",
            "tag": "Researched guide",
            "lead": "From Jay Fai's crab omelette to the night stalls of Yaowarat, the Bangkok plates the critics keep coming back to.",
            "file": "bangkok.jpg",
            "cover_alt": "Spring rolls, fried fritters and wrapped rolls stacked on a street-food stall on Yaowarat Road, Bangkok (stock photo)",
            "credit": BANGKOK_CREDIT,
            "stock": True,
            "w": 1200, "h": 750, "widths": (480, 800, 1200),
            "og": "/assets/img/bangkok.jpg", "ow": 1200, "oh": 750,
            "oalt": "Spring rolls, fried fritters and wrapped rolls stacked on a street-food stall on Yaowarat Road, Bangkok (stock photo)",
            "updated": ("2026-10-22", "22 Oct 2026"),
            "modified": "2026-10-22",
            "nav": None,
            "crumbs": [("Home", "/"), ("Restaurant Guides", "/guides"), ("Best Street Food in Bangkok", None)],
            "keep": [cards["tokyo_long"], cards["ramen_long"], cards["lisbon_long"]],
        },
        "where-to-eat-lisbon": {
            "title": "Where to Eat in Lisbon: Custard Tarts, Seafood & Petiscos",
            "description": "Where to eat in Lisbon: pastéis de nata in Belém, garlic prawns at Cervejaria Ramiro, Time Out Market and petiscos in Chiado. A researched guide, sources cited.",
            "path": "/articles/where-to-eat-lisbon",
            "h1": "Where to Eat in Lisbon",
            "tag": "Researched guide",
            "lead": "Custard tarts in Belém, garlic prawns at Ramiro and a market hall built for grazing: Lisbon's most-praised tables.",
            "file": "lisbon.jpg",
            "cover_alt": "Two pastéis de nata on a plate between two cups of coffee on a counter at Manteigaria, Lisbon (stock photo)",
            "credit": LISBON_CREDIT,
            "stock": True,
            "w": 1200, "h": 750, "widths": (480, 800, 1200),
            "og": "/assets/img/lisbon.jpg", "ow": 1200, "oh": 750,
            "oalt": "Two pastéis de nata on a plate between two cups of coffee on a counter at Manteigaria, Lisbon (stock photo)",
            "updated": ("2026-10-22", "22 Oct 2026"),
            "modified": "2026-10-22",
            "nav": None,
            "crumbs": [("Home", "/"), ("Restaurant Guides", "/guides"), ("Where to Eat in Lisbon", None)],
            "keep": [cards["bangkok_long"], cards["tokyo_long"], cards["butter_long"]],
        },
    }
    pages = {
        "where-to-eat-tokyo": tokyo_body(),
        "ramen-101": ramen_body(),
        "best-street-food-bangkok": guide_body("best-street-food-bangkok"),
        "where-to-eat-lisbon": guide_body("where-to-eat-lisbon"),
    }
    for slug, body in pages.items():
        spec = specs[slug]
        publish(ROOT / "articles" / f"{slug}.html", article_shell(spec, body, article_ld(spec)))
    recipe_ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Recipe",
                "name": "Butter Chicken (Murgh Makhani) at Home",
                "description": "Butter chicken (murgh makhani) at home: charred yoghurt-marinated chicken in a silky tomato, butter and cream sauce, and the court case over who invented it.",
                "image": HOST + "/assets/img/butter-chicken.jpg",
                "datePublished": "2026-10-16",
                "dateModified": "2026-10-22",
                "recipeCuisine": "Indian (Punjabi / Delhi)",
                "recipeCategory": "Main",
                "recipeIngredient": ingredients,
                "recipeInstructions": [{"@type": "HowToStep", "position": i, "text": step} for i, step in enumerate(steps, start=1)],
                "author": {"@type": "Organization", "name": "Plates Around the World", "url": HOST + "/"},
                "publisher": {"@type": "Organization", "name": "Plates Around the World", "logo": {"@type": "ImageObject", "url": HOST + "/assets/img/icon.jpg"}},
                "mainEntityOfPage": HOST + "/articles/butter-chicken",
            },
            crumb_ld([("Home", "/"), ("Recipes", "/recipes"), ("Butter Chicken (Murgh Makhani) at Home", None)]),
        ],
    }
    # Times and yield are OWNER TO SUPPLY. They are not in this graph.
    butter_spec = {
        "title": "Butter Chicken (Murgh Makhani) Recipe | Plates Around the World",
        "description": "Butter chicken (murgh makhani) at home: charred yoghurt-marinated chicken in a silky tomato, butter and cream sauce, and the court case over who invented it.",
        "path": "/articles/butter-chicken",
        "h1": "Butter Chicken (Murgh Makhani) at Home",
        "tag": "Recipe",
        "lead": "Smoky charred chicken in a silky tomato, butter and cream sauce. Here's the Delhi classic, made at home.",
        "tested": "A home-style version based on the standard method; we haven't photographed our own batch yet.",
        "file": "butter-chicken.jpg",
        "cover_alt": "Murgh makhani (butter chicken) beside a piece of naan on a white plate (stock photo)",
        "credit": BUTTER_CREDIT,
        "stock": True,
        "card": recipe_card(),
        "w": 1200, "h": 750, "widths": (480, 800, 1200),
        "og": "/assets/img/butter-chicken.jpg", "ow": 1200, "oh": 750,
        "oalt": "Murgh makhani (butter chicken) beside a piece of naan on a white plate (stock photo)",
        "updated": ("2026-10-22", "22 Oct 2026"),
        "modified": "2026-10-22",
        "nav": None,
        "crumbs": [("Home", "/"), ("Recipes", "/recipes"), ("Butter Chicken (Murgh Makhani) at Home", None)],
        "keep": [cards["ramen_short"], cards["tokyo_short"], cards["recipes"]],
    }
    # disclosure.html, sitemap.xml and data/search-index.json are written by
    # scripts/build_articles.py. publish() also puts back any JSON-LD or GEAR
    # interior already on disk, so this script cannot replace the build output.
    publish(ROOT / "articles" / "butter-chicken.html", article_shell(butter_spec, butter, recipe_ld))
    publish(ROOT / "index.html", homepage(cards))
    publish(ROOT / "guides.html", guides_page(cards))
    publish(ROOT / "recipes.html", recipes_page(cards))
    publish(ROOT / "about.html", about_page())
    publish(ROOT / "contact.html", contact_page())
    publish(ROOT / "404.html", not_found())
    publish(ROOT / "templates" / "article-template.html", template_page())
    write(ROOT / "robots.txt", robots())
    write(ROOT / "_redirects", redirects())
    write(ROOT / "_headers", headers())
    write_partials()
    required = {
        ROOT / "articles" / "butter-chicken.html": ["<!-- JSON-LD:START -->", "<!-- JSON-LD:END -->", "<!-- GEAR:START -->", "<!-- GEAR:END -->", "OWNER TO SUPPLY", "Luca Nebuloni"],
        ROOT / "articles" / "where-to-eat-tokyo.html": ["<!-- JSON-LD:START -->", "2 July 2026", "The Japan Times", "NEWSLETTER:START"],
        ROOT / "articles" / "ramen-101.html": ["<!-- JSON-LD:START -->", "Where to learn more"],
        ROOT / "templates" / "article-template.html": ["ONE-LINE LEAD", "noindex", "<!-- JSON-LD:START -->"],
        ROOT / "index.html": ["[NEWSLETTER_FORM_ACTION: TBD]", "data-site-search", "written for your kitchen"],
    }
    for path, needles in required.items():
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                raise SystemExit(f"missing {needle} in {path}")
        if text.count("<!-- JSON-LD:START -->") != 1 or text.count("<!-- JSON-LD:END -->") != 1:
            raise SystemExit(f"JSON-LD markers not exactly once in {path}")
    butter_html = (ROOT / "articles" / "butter-chicken.html").read_text(encoding="utf-8")
    if butter_html.count("<!-- GEAR:START -->") != 1:
        raise SystemExit("gear markers must appear once on the recipe")
    if "Serves 4" in butter_html or "Recipe developed for home kitchens" in butter_html:
        raise SystemExit("removed butter-chicken claims came back")
    if "Pastéis de Belém" in (ROOT / "templates" / "article-template.html").read_text(encoding="utf-8"):
        raise SystemExit("template still has the Lisbon body")
    print("rendered")


if __name__ == "__main__":
    main()

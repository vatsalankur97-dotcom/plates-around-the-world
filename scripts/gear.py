"""Gear lists and affiliate links for recipe and guide pages.

Called from scripts/build_articles.py. Renders HTML at build time.
No JavaScript, no network calls, no affiliate IDs in the default config.

EarnKaro and Cuelinks formats are not confirmed (no accounts yet).
Those adapters are stubs: they never invent a tracking URL. They only
pass through a prebuilt https URL stored on the item, and only when the
master flag and that network are both on.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from html import escape
from urllib.parse import urlsplit, urlunsplit

# Public retailer hosts. The stored URL must already be on this host.
# The helper never rewrites the host.
RETAILERS = {
    "amazon_in": {
        "label": "Amazon.in",
        "hosts": {"amazon.in", "www.amazon.in"},
    },
    "flipkart": {
        "label": "Flipkart",
        "hosts": {"flipkart.com", "www.flipkart.com"},
    },
    "myntra": {
        "label": "Myntra",
        "hosts": {"myntra.com", "www.myntra.com"},
    },
    "nykaa": {
        "label": "Nykaa",
        "hosts": {"nykaa.com", "www.nykaa.com"},
    },
    "brand_site": {
        "label": "Brand site",
        "hosts": None,
    },
}

NETWORKS = ("none", "amazon", "earnkaro", "cuelinks", "direct")
DISCLOSURES = ("affiliate", "free_gift", "affiliate_free_gift", "none")

# Amazon Associates: append ?tag= only. Anything else is out of scope
# until the programme is actually joined.
AMAZON_ADAPTER = "stub-append-tag"

# EarnKaro publishes per-product short links from its dashboard.
# The path shape is not confirmed. Do not build one here.
EARNKARO_ADAPTER = "stub-prebuilt-only"

# Cuelinks deep-link format is not confirmed. Same rule.
CUELINKS_ADAPTER = "stub-prebuilt-only"


class GearError(Exception):
    """Invalid gear data. The build must fail, not skip the item."""


def load_config(path) -> dict:
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config.get("AFFILIATE_LINKS_ENABLED"), bool):
        raise GearError("AFFILIATE_LINKS_ENABLED must be true or false")
    if config.get("PRE_ID_MODE") not in ("plain", "none"):
        raise GearError('PRE_ID_MODE must be "plain" or "none"')
    networks = config.get("networks")
    if not isinstance(networks, dict):
        raise GearError("networks must be an object")
    for name in ("amazon", "earnkaro", "cuelinks"):
        block = networks.get(name)
        if not isinstance(block, dict) or not isinstance(block.get("enabled"), bool):
            raise GearError(f"networks.{name}.enabled must be true or false")
    tag = networks["amazon"].get("tag", "")
    if not isinstance(tag, str):
        raise GearError("networks.amazon.tag must be a string")
    if tag.strip() and not config["AFFILIATE_LINKS_ENABLED"]:
        # An ID with the master switch off is still not emitted. Allowed,
        # but it must not be a secret: tags are public. Empty is the default.
        pass
    return config


def validate_gear(data: dict, filename: str, today: date | None = None) -> list[str]:
    """Return warnings. Raise GearError on anything that must not ship."""
    today = today or date.today()
    warnings: list[str] = []
    if not isinstance(data, dict):
        raise GearError(f"{filename}: gear file must be an object")
    slug = data.get("slug")
    if not isinstance(slug, str) or not slug:
        raise GearError(f"{filename}: slug is required")
    items = data.get("items")
    if not isinstance(items, list):
        raise GearError(f"{filename}: items must be a list")
    seen = set()
    for index, item in enumerate(items, start=1):
        where = f"{filename} item {index}"
        if not isinstance(item, dict):
            raise GearError(f"{where}: must be an object")
        _require_str(item, "name", where)
        why = _require_str(item, "why", where)
        if len(why) > 140:
            raise GearError(f"{where}: why is {len(why)} chars (max 140)")
        if not isinstance(item.get("used_by_us"), bool):
            raise GearError(f"{where}: used_by_us must be true or false")
        url = _require_str(item, "url", where)
        _check_clean_url(url, item.get("retailer"), where)
        network = item.get("network")
        if network not in NETWORKS:
            raise GearError(f"{where}: network must be one of {', '.join(NETWORKS)}")
        retailer = item.get("retailer")
        if retailer not in RETAILERS:
            raise GearError(
                f"{where}: retailer must be one of {', '.join(sorted(RETAILERS))}"
            )
        if network == "amazon" and retailer != "amazon_in":
            raise GearError(f"{where}: amazon network only matches retailer amazon_in")
        disclosure = item.get("disclosure")
        if disclosure not in DISCLOSURES:
            raise GearError(f"{where}: disclosure is missing or unknown")
        if disclosure == "none" and not (
            network == "none" and item["used_by_us"] is True
        ):
            raise GearError(
                f"{where}: disclosure none is only valid with network none "
                "and used_by_us true"
            )
        if disclosure in ("affiliate", "affiliate_free_gift") and network == "none":
            raise GearError(f"{where}: an affiliate disclosure needs a network")
        if not isinstance(item.get("active"), bool):
            raise GearError(f"{where}: active must be true or false")
        price_shown = item.get("price_shown", False)
        if not isinstance(price_shown, bool):
            raise GearError(f"{where}: price_shown must be true or false")
        if price_shown and not isinstance(item.get("price_inr"), (int, float)):
            raise GearError(f"{where}: price_shown requires price_inr")
        if item.get("price_inr") is not None and not isinstance(
            item.get("price_inr"), (int, float)
        ):
            raise GearError(f"{where}: price_inr must be a number or null")
        checked = _parse_date(item.get("last_checked"), where)
        if checked > today:
            raise GearError(f"{where}: last_checked is in the future")
        age = (today - checked).days
        if age > 90:
            warnings.append(
                f"{where}: last_checked {item['last_checked']} is {age} days old"
            )
        item_id = item.get("id")
        if item_id is not None:
            if not isinstance(item_id, str) or not item_id:
                raise GearError(f"{where}: id must be a non-empty string")
            if item_id in seen:
                raise GearError(f"{where}: duplicate id {item_id}")
            seen.add(item_id)
        affiliate_url = item.get("affiliate_url", {})
        if affiliate_url is None:
            affiliate_url = {}
        if not isinstance(affiliate_url, dict):
            raise GearError(f"{where}: affiliate_url must be an object")
        for key in ("earnkaro", "cuelinks"):
            value = affiliate_url.get(key)
            if value is None or value == "":
                continue
            if not isinstance(value, str) or not value.startswith("https://"):
                raise GearError(f"{where}: affiliate_url.{key} must be an https URL")
    return warnings


def build_link(item: dict, config: dict) -> tuple[str | None, str]:
    """Return (href, kind). kind is 'affiliate', 'plain', or 'none'.

    An affiliate href is returned only when the master flag is on, that
    network is enabled, and the adapter has a real ID or a prebuilt URL.
    A blank ID never produces `tag=` or any other half-built tracker.
    """
    if config.get("PRE_ID_MODE") == "none" and not _affiliate_ready(item, config):
        return None, "none"
    if _affiliate_ready(item, config):
        href = _adapt(item, config)
        if href:
            return href, "affiliate"
    if config.get("PRE_ID_MODE") == "none":
        return None, "none"
    return item["url"], "plain"


def render_gear_section(
    data: dict,
    config: dict,
    disclosure_href: str,
    today: date | None = None,
) -> str:
    """Return the What we used section, or '' when there is nothing to show."""
    today = today or date.today()
    active = [item for item in data.get("items", []) if item.get("active")]
    active = active[:8]
    if not active:
        return ""
    rows = []
    kinds = []
    for item in active:
        href, kind = build_link(item, config)
        kinds.append((item, kind))
        rows.append(_render_item(item, href, kind, today))
    note = _section_note(kinds, config, disclosure_href)
    body = "\n".join(rows)
    note_html = f"\n  {note}" if note else ""
    return (
        '<section class="gear" id="gear" aria-labelledby="gear-h">\n'
        '  <h2 id="gear-h">What we used</h2>'
        f"{note_html}\n"
        '  <ul class="gear-list">\n'
        f"{body}\n"
        "  </ul>\n"
        "</section>"
    )


def top_of_article_note(data: dict, config: dict, disclosure_href: str) -> str:
    """One line for the existing research note, only when a real affiliate link renders."""
    for item in data.get("items", []):
        if not item.get("active"):
            continue
        _href, kind = build_link(item, config)
        if kind == "affiliate":
            return (
                'This page includes affiliate links '
                f'(<a href="{escape(disclosure_href, quote=True)}">details</a>).'
            )
    return ""


def _affiliate_ready(item: dict, config: dict) -> bool:
    if not config.get("AFFILIATE_LINKS_ENABLED"):
        return False
    network = item.get("network")
    if network in (None, "none"):
        return False
    block = config.get("networks", {}).get(network, {})
    if network == "direct":
        return False
    if not block.get("enabled"):
        return False
    if network == "amazon":
        return bool(str(block.get("tag", "")).strip())
    if network == "earnkaro":
        return bool(_prebuilt(item, "earnkaro"))
    if network == "cuelinks":
        return bool(_prebuilt(item, "cuelinks"))
    return False


def _adapt(item: dict, config: dict) -> str | None:
    network = item["network"]
    if network == "amazon":
        tag = str(config["networks"]["amazon"].get("tag", "")).strip()
        if not tag:
            return None
        return _amazon_tag(item["url"], tag)
    if network == "earnkaro":
        # STUB. Format unconfirmed. Prebuilt dashboard link only.
        return _prebuilt(item, "earnkaro")
    if network == "cuelinks":
        # STUB. Format unconfirmed. Prebuilt deep link only. No JS converter.
        return _prebuilt(item, "cuelinks")
    return None


def _amazon_tag(url: str, tag: str) -> str:
    parts = urlsplit(url)
    # Drop any query that slipped past validation. Keep the clean path.
    return urlunsplit((parts.scheme, parts.netloc, parts.path, f"tag={tag}", ""))


def _prebuilt(item: dict, key: str) -> str | None:
    block = item.get("affiliate_url") or {}
    value = block.get(key)
    if isinstance(value, str) and value.startswith("https://"):
        return value
    return None


def _render_item(item: dict, href: str | None, kind: str, today: date) -> str:
    name = escape(item["name"])
    if href:
        rel = (
            "sponsored nofollow noopener"
            if kind == "affiliate"
            else "nofollow noopener"
        )
        link = (
            f'<a href="{escape(href, quote=True)}" rel="{rel}" '
            f'target="_blank">{name}</a>'
        )
    else:
        link = name
    labels = []
    if kind == "affiliate":
        labels.append('<span class="gear-label">(affiliate link)</span>')
    if item["disclosure"] in ("free_gift", "affiliate_free_gift"):
        labels.append('<span class="gear-label">(free gift)</span>')
    why = item["why"]
    if item["used_by_us"] is False:
        why = f"We haven't tried this one: {why}"
    label_html = (" " + " ".join(labels)) if labels else ""
    meta = _price_meta(item, today)
    meta_html = f'\n      <span class="gear-meta">{meta}</span>' if meta else ""
    return (
        '    <li class="gear-item">\n'
        f"      {link}{label_html}\n"
        f'      <span class="gear-why">{escape(why)}</span>'
        f"{meta_html}\n"
        "    </li>"
    )


def _price_meta(item: dict, today: date) -> str:
    if not item.get("price_shown"):
        return ""
    checked = _parse_date(item["last_checked"], item["name"])
    if (today - checked).days > 30:
        return ""
    return (
        f'{escape(RETAILERS[item["retailer"]]["label"])} · price '
        f'{_format_inr(item["price_inr"])} as of {escape(_format_date(checked))}'
    )


def _section_note(kinds: list[tuple[dict, str]], config: dict, disclosure_href: str) -> str:
    affiliate = any(kind == "affiliate" for _item, kind in kinds)
    gifted = any(
        item["disclosure"] in ("free_gift", "affiliate_free_gift") for item, _kind in kinds
    )
    if not affiliate and not gifted:
        return ""
    href = escape(disclosure_href, quote=True)
    if affiliate and gifted:
        text = (
            "<strong>Affiliate | Free gift:</strong> a brand sent us a product "
            "listed below for free. Some links below are affiliate links, so we "
            "may earn a small commission at no extra cost to you. Opinions are "
            f'our own. <a href="{href}">Details</a>'
        )
    elif affiliate:
        text = (
            "<strong>Affiliate:</strong> some links below are affiliate links. "
            "If you buy through them we may earn a small commission, at no extra "
            f'cost to you. <a href="{href}">How we make money</a>'
        )
    else:
        text = (
            "<strong>Free gift:</strong> a product below was sent to us for free. "
            f'Opinions are our own. <a href="{href}">Details</a>'
        )
    amazon_on = (
        affiliate
        and config.get("networks", {}).get("amazon", {}).get("enabled")
        and any(item["network"] == "amazon" and kind == "affiliate" for item, kind in kinds)
    )
    if amazon_on:
        text += " As an Amazon Associate I earn from qualifying purchases."
    return f'<div class="note gear-disclosure">{text}</div>'


def _check_clean_url(url: str, retailer: str, where: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise GearError(f"{where}: url must be an https URL")
    if parts.query or parts.fragment:
        raise GearError(
            f"{where}: url must be a clean product URL with no tracking query"
        )
    if retailer not in RETAILERS:
        return
    hosts = RETAILERS[retailer]["hosts"]
    if hosts is not None and parts.netloc.lower() not in hosts:
        raise GearError(f"{where}: url host does not match retailer {retailer}")


def _require_str(item: dict, key: str, where: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GearError(f"{where}: {key} is required")
    return value.strip()


def _parse_date(value, where: str) -> date:
    if not isinstance(value, str):
        raise GearError(f"{where}: last_checked is required (YYYY-MM-DD)")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise GearError(f"{where}: last_checked must be YYYY-MM-DD") from exc


def _format_date(value: date) -> str:
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    return f"{value.day} {months[value.month - 1]} {value.year}"


def _format_inr(amount) -> str:
    rupees = int(amount)
    sign = "-" if rupees < 0 else ""
    digits = str(abs(rupees))
    if len(digits) <= 3:
        grouped = digits
    else:
        head, tail = digits[:-3], digits[-3:]
        chunks = []
        while head:
            chunks.append(head[-2:])
            head = head[:-2]
        grouped = ",".join(reversed(chunks)) + "," + tail
    return f"₹{sign}{grouped}"


def self_check() -> None:
    """In-memory checks. They must not write affiliate URLs into the site."""
    today = date(2026, 10, 22)
    example = {
        "slug": "butter-chicken",
        "items": [
            {
                "id": "heavy-kadai",
                "name": "Heavy-bottomed kadai, 26 cm",
                "why": "Holds heat evenly so the tomato-butter sauce doesn't catch.",
                "used_by_us": True,
                "retailer": "amazon_in",
                "network": "amazon",
                "url": "https://www.amazon.in/dp/EXAMPLEASIN",
                "price_shown": False,
                "price_inr": None,
                "last_checked": "2026-10-22",
                "disclosure": "affiliate",
                "active": True,
            }
        ],
    }
    warnings = validate_gear(example, "example", today)
    if warnings:
        raise GearError(f"example should not warn: {warnings}")
    off = {
        "AFFILIATE_LINKS_ENABLED": False,
        "PRE_ID_MODE": "plain",
        "networks": {
            "amazon": {"enabled": False, "tag": ""},
            "earnkaro": {"enabled": False, "mode": "prebuilt"},
            "cuelinks": {"enabled": False, "cid": "", "mode": "prebuilt"},
        },
    }
    plain = render_gear_section(example, off, "../disclosure.html", today)
    if "tag=" in plain or "sponsored" in plain or "(affiliate link)" in plain:
        raise GearError("flag off must render a plain link with no affiliate label")
    if 'rel="nofollow noopener"' not in plain:
        raise GearError("plain links need rel=nofollow noopener")
    if "Affiliate" in plain:
        raise GearError("flag off must not show an Affiliate note")
    if plain.find("gear-disclosure") != -1:
        raise GearError("disclosure note rendered while the flag is off")
    on = {
        "AFFILIATE_LINKS_ENABLED": True,
        "PRE_ID_MODE": "plain",
        "networks": {
            "amazon": {"enabled": True, "tag": "example-tag"},
            "earnkaro": {"enabled": False, "mode": "prebuilt"},
            "cuelinks": {"enabled": False, "cid": "", "mode": "prebuilt"},
        },
    }
    tagged = render_gear_section(example, on, "../disclosure.html", today)
    if "tag=example-tag" not in tagged:
        raise GearError("amazon adapter should append the tag")
    if 'rel="sponsored nofollow noopener"' not in tagged:
        raise GearError("affiliate links need rel=sponsored nofollow noopener")
    if "(affiliate link)" not in tagged:
        raise GearError("affiliate links need a visible label")
    if tagged.find("gear-disclosure") > tagged.find("<a "):
        raise GearError("disclosure note must sit above the first link")
    blank = {
        "AFFILIATE_LINKS_ENABLED": True,
        "PRE_ID_MODE": "plain",
        "networks": {
            "amazon": {"enabled": True, "tag": ""},
            "earnkaro": {"enabled": True, "mode": "prebuilt"},
            "cuelinks": {"enabled": True, "cid": "", "mode": "prebuilt"},
        },
    }
    fallback = render_gear_section(example, blank, "../disclosure.html", today)
    if "tag=" in fallback or "sponsored" in fallback:
        raise GearError("blank amazon tag must fall back to a plain link")
    earn = dict(example["items"][0])
    earn["network"] = "direct"
    # direct is not a stub that invents URLs; covered below via earnkaro.
    earnkaro_item = dict(example["items"][0])
    earnkaro_item["network"] = "cuelinks"
    earnkaro_item["retailer"] = "flipkart"
    earnkaro_item["url"] = "https://www.flipkart.com/example-kadai/p/EXAMPLE"
    earnkaro_item["affiliate_url"] = {}
    section = {"slug": "butter-chicken", "items": [earnkaro_item]}
    validate_gear(section, "cuelinks-stub", today)
    rendered = render_gear_section(section, blank, "../disclosure.html", today)
    if "cuelinks" in rendered or "tag=" in rendered:
        raise GearError("cuelinks stub invented a tracking URL")
    if "https://www.flipkart.com/example-kadai/p/EXAMPLE" not in rendered:
        raise GearError("stub should keep the clean retailer URL")
    try:
        bad = json.loads(json.dumps(example))
        bad["items"][0]["price_shown"] = True
        bad["items"][0]["price_inr"] = None
        validate_gear(bad, "bad-price", today)
    except GearError:
        pass
    else:
        raise GearError("price_shown without a price must fail")
    empty = render_gear_section({"slug": "butter-chicken", "items": []}, off, "../disclosure.html", today)
    if empty:
        raise GearError("an empty gear list must omit the section")

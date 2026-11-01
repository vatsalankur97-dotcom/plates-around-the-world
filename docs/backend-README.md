# Backend: content, build, search, gear

This branch is `backend/content-pipeline`, rebased onto `redesign`. Do not merge it, and do not open a pull request: Netlify Deploy Previews are on and each one spends credits.

## Run the build

```bash
python3 scripts/build_articles.py
```

Python 3.12, standard library only. No `pip`. Netlify's build image already has Python. The same command is the production build in `netlify.toml`. Publish directory stays `.`.

The build checks content, rewrites `sitemap.xml`, `data/jsonld/*.json`, `data/search-index.json`, and `disclosure.html`, and stops if gear data is invalid. It does not edit existing article HTML, `robots.txt`, styles, or `assets/main.js`.

`SITE_URL` lives only in `scripts/build_articles.py`:

```python
SITE_URL = "https://platesaroundtheworld.netlify.app"
```

Field names, paths, and the JSON-LD markers are in `docs/content-schema.md`.

## Add an article, recipe, or restaurant

1. Create `content/articles/<slug>.md`, `content/recipes/<slug>.md`, or `content/restaurants/<slug>.json`.
2. Set `path` to the extensionless canonical (`/articles/<slug>`). `_redirects` serves that and the `.html` file, both with status 200. Do not invent a new article URL.
3. Put the image in `assets/img/` and set `image` to that root-relative path. `alt` is stored for the frontend; the build does not write it into the page.
4. Run the build. Fix any error. It fails on a missing image, an unknown restaurant slug, or front matter it cannot parse.
5. Ask the frontend to put this in the page. The build replaces only the interior, and doing it twice is safe:

```html
<!-- JSON-LD:START -->
<!-- JSON-LD:END -->
```

`templates/README.md` still describes copying HTML by hand. Use this file instead.

## Photo privacy

Run this on `assets/img/` (including `assets/img/trip/`) before committing a photo:

```bash
python3 scripts/strip_exif.py
python3 scripts/strip_exif.py --check
```

`scripts/strip_exif.py` removes EXIF, GPS, XMP, and IPTC in place and keeps the ICC colour profile. It applies the EXIF orientation to the pixels, then drops the tag, so the photo is not rotated twice.

This is a dev dependency. CI installs exiftool and runs `--check`, and fails if a committed image still has EXIF or GPS data. The Netlify production build stays `python3 scripts/build_articles.py` (stdlib only) and does not install the tool.

- Preferred: `exiftool` (`libimage-exiftool-perl`) and `jpegtran` (`libjpeg-turbo-progs`). Metadata edits are lossless. JPEG orientation uses `jpegtran -copy icc`, which keeps the colour profile and does not recompress the photo.
- Fallback: `pip install Pillow`, when exiftool or jpegtran is missing. Pillow re-encodes JPEG (`quality="keep"` when the pixels are not rotated, quality 95 when they are). Animated GIFs are not rewritten with Pillow.

Faces are a separate step. This script does not crop or blur them. Crop or blur anyone other than the owner before publishing, unless they have consented. That is an editorial decision, done by hand.

## Search

`data/search-index.json` is the index (title, url, type, description, text). URLs are the extensionless canonicals. The header already has `[data-site-search]` and `[data-site-search-results]`. `assets/search.js` filters the index in the browser. No paid search, no Pagefind binary.

## Newsletter

`partials/newsletter-form.html` is the form named `newsletter`, with honeypot `bot-field`. Its action stays `[NEWSLETTER_FORM_ACTION: TBD]`. `partials/privacy-section.html` is the `#privacy` note: email only, not sold, how to be removed. It does not name a sending tool.

Do not put `data-subscribe` on that form. `assets/main.js` turns those forms into a `mailto:`. Netlify will not see the form until the snippet is in published HTML.

## Gear lists and the affiliate flag

`scripts/gear.py` renders the "What we used" section at build time. `build_articles.py` calls it. There is no client-side link rewriting.

Add `data/gear/<slug>.json` (one file per article or recipe). A documented inactive example is `docs/examples/gear-butter-chicken.example.json`. The live file `data/gear/butter-chicken.json` has an empty `items` list, so the section is omitted.

Required fields and the failure rules are in the Growth spec. The build fails on a missing field, `price_shown` without `price_inr`, `disclosure: none` on an affiliate network, or a URL host that does not match `retailer`. `last_checked` older than 90 days prints a warning and does not fail. Stored URLs must be clean `https` product links with no query string. The helper adds affiliate parameters later. Never store them in the JSON.

`data/affiliate-config.json`:

- `AFFILIATE_LINKS_ENABLED` is `false`.
- `PRE_ID_MODE` is `"plain"` (clean retailer links). `"none"` renders the name and reason with no link.
- `networks.amazon.tag` is `""`.
- EarnKaro and Cuelinks are stubs. Their link formats are not confirmed and there are no accounts. They only pass through `affiliate_url.earnkaro` or `affiliate_url.cuelinks` when that network is enabled and the value is an `https` URL. They never construct a short link. Cuelinks' JavaScript converter is not used.

While the flag is off, an active item is a plain link: `rel="nofollow noopener"`, `target="_blank"`, no "(affiliate link)" label, and no Affiliate note. A free-gift label still shows if the item says so. An empty list omits the section.

To turn links on later, after a programme is approved:

1. Put real items in `data/gear/<slug>.json` with `active: true`, a clean product URL, and `last_checked` set to the day someone opened the link.
2. For Amazon, set `networks.amazon.enabled` to `true` and `tag` to the Associates tracking id, then set `AFFILIATE_LINKS_ENABLED` to `true`. The adapter appends `?tag=` and nothing else. A blank tag falls back to the plain URL and does not emit `tag=`.
3. For EarnKaro or Cuelinks, paste the dashboard's prebuilt `https` URL into `affiliate_url` and set that network's `enabled` to `true`. Do not guess the format.
4. Run the build. Affiliate links get `rel="sponsored nofollow noopener"` and the visible text `(affiliate link)`. The disclosure note is the first thing in the section, above the first link. The Amazon sentence is added on the disclosure page and in the note only when Amazon is actually enabled.
The gear markers are already on `articles/butter-chicken.html`, after Ingredients. `.gear-list`, `.gear-label`, and `.gear-meta` are in `assets/style.css`. An empty list leaves the placeholder comment in place.

`partials/footer.html` already links to `/disclosure.html`. `disclosure.html` is rebuilt from that partial and `partials/header.html`, with canonical `/disclosure`.

## CI

`.github/workflows/ci.yml` runs on pull requests to `main` and `redesign`, and on pushes to every other branch. It runs the build, fails if the build would change committed files, installs exiftool, and fails if a published image still has EXIF, GPS, XMP, or IPTC. It then runs lychee offline on HTML. Root-absolute links such as `/guides` resolve with `--root-dir` and `--fallback-extensions html`, so the extensionless canonicals are checked against the `.html` files. The newsletter placeholder `[NEWSLETTER_FORM_ACTION: TBD]` is excluded. `templates/`, `partials/`, `docs/`, and `content/bodies/` are excluded. External URLs are not checked.

Locally, after a content change, run the build and commit the generated files before pushing. A second build should leave `git diff` empty.

## robots.txt

Do not edit it here. It should keep:

```
Sitemap: https://platesaroundtheworld.netlify.app/sitemap.xml
```

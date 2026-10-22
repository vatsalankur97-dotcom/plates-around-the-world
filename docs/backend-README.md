# Backend: content, build, search, gear

`redesign` was not on GitHub while this was written. The branch is `backend/content-pipeline`, cut from current `main`. Do not merge it, and do not open a pull request: Netlify Deploy Previews are on and each one spends credits.

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
2. Set `path` to the public URL that already exists (`/articles/<slug>.html`). Do not invent a new article URL. Nothing in the current set changed, so there is no `_redirects` file.
3. Put the image in `assets/img/` and set `image` to that root-relative path. `alt` is stored for the frontend; the build does not write it into the page.
4. Run the build. Fix any error. It fails on a missing image, an unknown restaurant slug, or front matter it cannot parse.
5. Ask the frontend to put this in the page. The build replaces only the interior, and doing it twice is safe:

```html
<!-- JSON-LD:START -->
<!-- JSON-LD:END -->
```

`templates/README.md` still describes copying HTML by hand. Use this file instead.

## Search

`data/search-index.json` is the index (title, url, type, description, text). `partials/search.html` and `assets/search.js` filter it in the browser. Drop the partial into a template. No paid search, no Pagefind binary.

## Newsletter

`partials/newsletter-form.html` is a Netlify Form named `newsletter` with honeypot `bot-field`. `partials/privacy-section.html` is the `#privacy` note: email only, weekly plate, not sold, how to be removed.

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
5. Ask the frontend to add the gear markers on the recipe, after Ingredients:

```html
<!-- GEAR:START -->
<!-- GEAR:END -->
```

Paste `partials/gear.css` into `assets/style.css` when they do. This branch does not edit `style.css` or the `?v=4` query.

`partials/footer-disclosure.html` is the footer link. `disclosure.html` already includes it. The other footers do not, because `redesign` had no slot and those templates are frontend-owned.

## CI

`.github/workflows/ci.yml` runs on pull requests to `main` and `redesign`, and on pushes to every other branch. It runs the build, fails if the build would change committed files, then runs lychee offline on HTML. External URLs are not checked. `templates/` is excluded because `SLUG.jpg` is a placeholder. `partials/` and `docs/` are excluded because they are snippets, not pages.

Locally, after a content change, run the build and commit the generated files before pushing. A second build should leave `git diff` empty.

## robots.txt

Do not edit it here. It should keep:

```
Sitemap: https://platesaroundtheworld.netlify.app/sitemap.xml
```

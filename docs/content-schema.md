# Content schema and build interface

Contract for the frontend. Branch: `backend/content-pipeline`, rebased onto `redesign`. Slots are the ones in `docs/frontend-templates.md`.

The build does **not** write meta, Open Graph, canonical, robots.txt, or alt text. On article and recipe pages it replaces only the interior of the JSON-LD and gear markers.

## One site URL

```python
SITE_URL = "https://platesaroundtheworld.netlify.app"
```

Defined once in `scripts/build_articles.py`. Sitemap locations and JSON-LD URLs are `SITE_URL` plus a path. Do not hard-code the host anywhere else.

The homepage path is `/`, so the sitemap loc is `https://platesaroundtheworld.netlify.app/`. The frontend sets the homepage canonical (it will be `/`). This build does not edit that tag.

## Where files live

| Kind | Path | Format |
| --- | --- | --- |
| Articles and city guides | `content/articles/<slug>.md` | Markdown + YAML front matter |
| Recipes | `content/recipes/<slug>.md` | Markdown + YAML front matter |
| Restaurants | `content/restaurants/<slug>.json` | JSON |
| Static pages in the sitemap | `content/site.json` | JSON |
| Generated JSON-LD | `data/jsonld/<slug>.json` | JSON, overwritten by the build |
| Generated search index | `data/search-index.json` | JSON, overwritten by the build |
| Snippets to drop into templates | `partials/*.html` | HTML fragments, not pages |

Public URLs do not follow the content folder. Every article and recipe keeps the URL it already has, in `path`.

Current paths (do not change):

- `/articles/best-street-food-bangkok.html`
- `/articles/where-to-eat-lisbon.html`
- `/articles/where-to-eat-tokyo.html`
- `/articles/ramen-101.html`
- `/articles/butter-chicken.html`

Restaurants do not have their own pages. A guide's JSON-LD lists them. No new public URLs, so no redirects.

`templates/README.md` still describes hand-copying HTML. That is the old path. Add content here instead.

## Front matter the build accepts

YAML subset only (no anchors, no multiline `|`, no tabs). Lists and one level of nesting. Quote a value that contains a colon. `scripts/build_articles.py` exits non-zero on anything it cannot parse.

### Shared fields

| Field | Required | Use |
| --- | --- | --- |
| `type` | yes | `article` or `recipe` |
| `slug` | yes | Must match the filename |
| `title` | yes | On-page title. Not written into `<title>` or `og:title` |
| `description` | yes | Lead paragraph. Frontend may copy it into meta |
| `date` | yes | `YYYY-MM-DD`. Published date |
| `updated` | no | `YYYY-MM-DD`. Sitemap `lastmod` and JSON-LD `dateModified`. Falls back to `date` |
| `path` | yes | Extensionless canonical, starting with `/` (`/articles/ramen-101`, `/disclosure`). The HTML file is that path plus `.html`. Both URLs return 200 via `_redirects` |
| `image` | yes | Root-relative, e.g. `assets/img/lisbon.jpg`. File must exist |
| `alt` | yes | Stored for the frontend. The build does not write it into `<img>` |
| `tag` | yes | Label already used on the page (`Researched guide`, `Recipe`, …) |
| `draft` | no | Default `false`. Drafts are left out of the sitemap, search index, and JSON-LD |

### Articles (`type: article`)

| Field | Required | Use |
| --- | --- | --- |
| `section` | yes | `guide` or `deep-dive` |
| `note` | no | Research note, without the "How we research" link. Empty means the page has no note |
| `card_blurb` | yes | Short text for a listing card |
| `card_tag` | no | Card label when it differs from `tag` (Ramen 101 cards say `Deep-dive`; the page tag is `Researched guide`) |
| `lists` | yes | Where a card appears today: any of `home`, `guides`, `recipes`. Data only. The build does not edit `index.html`, `guides.html`, or `recipes.html` |
| `city` | no | City name |
| `country` | no | Country name |
| `restaurants` | no | Slugs in `content/restaurants/` |
| `sources` | yes | List of `{name, url}` |
| `sources_checked` | yes | `YYYY-MM-DD` shown in the sources line |
| `sources_suffix` | no | Sentence after the source links. Guides use `Hours change, so check before you go.` |

Body is Markdown after the closing `---`. Internal links in the body use root-relative paths (`/articles/ramen-101.html`, `/about.html#method`).

### Recipes (`type: recipe`)

All shared fields, plus:

| Field | Required | Use |
| --- | --- | --- |
| `recipe_yield` | no | e.g. `4 servings`. Omitted from JSON-LD when absent |
| `recipe_cuisine` | no | Only when the copy states it |
| `recipe_category` | no | Only when the copy states it |
| `ingredients` | yes | List of `{group, items[]}`. `recipeIngredient` is the item text, without the group name |
| `instructions` | yes | List of strings, in order. Become `HowToStep`s |
| `restaurants` | no | Same as articles |
| `sources`, `sources_checked`, `sources_suffix` | yes / yes / no | Same as articles |

Do not invent `prep_time`, `cook_time`, or a star rating. The build will emit `prepTime` / `cookTime` / `totalTime` only if those fields are present as ISO 8601 durations, and `reviewRating` only if a restaurant has both `rating_value` and `best_rating`. None of the migrated pages have those, so they are not set.

### Restaurants (`content/restaurants/<slug>.json`)

| Field | Required | Use |
| --- | --- | --- |
| `slug` | yes | Filename stem |
| `name` | yes | |
| `description` | yes | Fact already published on the guide or recipe. Not a new claim |
| `schema_type` | no | Default `Restaurant`. `FoodEstablishment` for a food hall |
| `address` | no | Only fields we actually have: `street`, `locality`, `region`, `country` |
| `url` | no | Official site only, not a guide or review URL |
| `serves_cuisine` | no | |
| `featured_in` | yes | Slug of the article or recipe that mentions it |
| `review_body` | no | When present, a `Review` is emitted. No rating unless `rating_value` and `best_rating` are both set |
| `role` | no | `context` for a historical mention that is not a recommendation. Those get a `Restaurant` node and no `Review` |

Areas (Yaowarat, Tsukiji, Ameyoko) stay in the article body. They are not restaurant records.

## What the build writes into a template

Run:

```bash
python3 scripts/build_articles.py
```

Stdlib only. No pip. Safe for the Netlify Free build image.

### JSON-LD slot (frontend adds this; the build fills it)

On the **published page** for that content `path` (not on `templates/article-template.html`):

```html
<!-- JSON-LD:START -->
<!-- JSON-LD:END -->
```

The build replaces only the bytes between those two markers with one pretty-printed script tag. Running it again replaces that same block. Pages without both markers are not modified.

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": []
}
</script>
```

- Article pages: `Article`, plus a `Restaurant` (or `FoodEstablishment`) for each linked restaurant, plus a `Review` only when `review_body` is set.
- Recipe pages: `Recipe`, plus linked restaurants the same way.
- `Article.headline`, `description`, `image`, `datePublished`, `dateModified`, `author`, `publisher` (with the icon logo), `mainEntityOfPage`. The URL is the extensionless canonical.
- `Recipe` uses `recipeIngredient`, `recipeInstructions` (`HowToStep` with `position`), and, when the copy states them, `recipeCuisine` and `recipeCategory`. Butter chicken keeps `Indian (Punjabi / Delhi)` and `Main`. Yield and times are omitted until the owner supplies them.
- `BreadcrumbList` is in the same `@graph`: Home, then Restaurant Guides (`/guides`) or Recipes (`/recipes`), then the page title with no URL. A page listed under both (Ramen 101) uses Restaurant Guides.
- Restaurant and Review nodes follow the breadcrumb. Reviews have no `reviewRating` unless both rating fields exist. Do not add ratings that were not published.

A copy of each graph is also written to `data/jsonld/<slug>.json` so it can be reviewed when the page has no markers yet. That file is not a public schema block until the markers are in the HTML.

### Snippets the frontend styles and drops in

These are fragments, not pages. Search and the newsletter are already in the redesigned header and article shells. The build does not insert a second copy.

| File | Slot contents |
| --- | --- |
| `partials/newsletter-form.html` | Form `newsletter`, honeypot `bot-field`. `action` stays `[NEWSLETTER_FORM_ACTION: TBD]` |
| `partials/privacy-section.html` | Section `#privacy`. The tool is not chosen, so the note does not name one |
| `partials/header.html` | Header and search. Hooks: `[data-site-search]`, `[data-site-search-results]` |
| `assets/search.js` | Client-side filter of `data/search-index.json` |
| `partials/footer.html` | Footer, including the link to `/disclosure.html` |
| `assets/style.css` | Already contains `.gear-list`, `.gear-label`, `.gear-meta`. There is no separate gear stylesheet |

`assets/main.js` turns `form[data-subscribe]` into a `mailto:`. The Netlify form does **not** use `data-subscribe`, so that handler will not swallow a real submission. The form has to be in published HTML before Netlify will register it. A partial sitting in `partials/` is not registered.

### Gear lists (`scripts/gear.py`)

One file per page that has gear: `data/gear/<slug>.json`. Validated on every build. Invalid entries fail the build. `data/affiliate-config.json` holds `AFFILIATE_LINKS_ENABLED` (default `false`) and per-network adapters. No affiliate IDs are stored. EarnKaro and Cuelinks adapters are stubs and never invent a tracking URL.

With the flag off, an active item renders as a plain link (`rel="nofollow noopener"`, no "(affiliate link)" label). An empty `items` list omits the section. The live recipe list is empty, so nothing is injected.

When the published HTML contains both markers, the build replaces only the interior:

```html
<!-- GEAR:START -->
<!-- GEAR:END -->
```

On butter chicken the markers already sit after Ingredients. Gear links use `/disclosure.html`. An empty `items` list leaves the placeholder inside the markers.

`disclosure.html` is generated from `content/disclosure.md`, `partials/header.html`, and `partials/footer.html`. Its canonical is `/disclosure`. `_redirects` already rewrites that to `disclosure.html` with status 200. The Amazon Associates sentence is added only when `networks.amazon.enabled` is true and a tag is set.

### Legacy `page()` / `card()` helpers

Content Studio's local `build_articles.py` was not in the repo. It string-replaced `templates/article-template.html` (`ARTICLE TITLE`, `SLUG`, and the Lisbon description sentence), wrote `articles/*.html`, and spliced cards into the homepage, guides, and recipes. `lib.py` was **not** imported by that script. It is a Playwright social-image renderer with machine-local paths, and it is not part of this build.

The port keeps `render_article_html()` and `render_card()` so a generated article still comes out as: tag, `h1`, lead, cover image, optional research note, body, sources line. The default build does **not** call them on the live pages. Doing that would overwrite canonical, Open Graph, and alt text, and it would drop pieces the old script never knew about (the Tokyo trip gallery, the ramen photo credit). The default command only validates content, writes `sitemap.xml`, writes `data/jsonld/` and `data/search-index.json`, generates `disclosure.html`, and fills `<!-- JSON-LD:START -->` … `<!-- JSON-LD:END -->` and `<!-- GEAR:START -->` … `<!-- GEAR:END -->` when both markers of a pair are already in that page.

## Sitemap

`content/site.json` lists static paths in order: `/`, `/guides`, `/recipes`, `/about`, `/contact`, `/disclosure`. Content paths follow, sorted by `path`, also extensionless. `lastmod` is `updated`, otherwise `date`, or the static page's `lastmod`. Drafts are excluded. Homepage loc is `https://platesaroundtheworld.netlify.app/`.

`robots.txt` is frontend-owned and already contains `Sitemap: https://platesaroundtheworld.netlify.app/sitemap.xml`. Keep that line pointed at `/sitemap.xml` on `SITE_URL`. This build does not edit `robots.txt`.

## Search index record

```json
{
  "title": "Where to Eat in Lisbon",
  "url": "/articles/where-to-eat-lisbon",
  "type": "article",
  "description": "…",
  "text": "plain text of the body"
}
```

Restaurant records use the guide URL in `url` and `type: "restaurant"`, because there is no restaurant page.

## Adding a piece of content

1. Add `content/articles/<slug>.md`, `content/recipes/<slug>.md`, or `content/restaurants/<slug>.json`.
2. Set `path` to the extensionless canonical (`/articles/<slug>`). `_redirects` already serves that and the `.html` file, both with status 200. Do not invent a new article URL.
3. Put the image under `assets/img/` and point `image` at it.
4. Run `python3 scripts/build_articles.py`.
5. Ask the frontend to add `<!-- JSON-LD:START -->` / `<!-- JSON-LD:END -->` on that page, then run the build again so the script tag is injected.

## Files the frontend also owns

Not edited by this pipeline:

- Existing HTML pages and `templates/` (no meta, canonical, Open Graph, or alt changes)
- `assets/style.css`, `assets/main.js`
- `robots.txt`

`disclosure.html` is written by the build from `partials/header.html` and `partials/footer.html`. Article and recipe HTML is only changed between `<!-- JSON-LD:START -->` / `<!-- JSON-LD:END -->` and `<!-- GEAR:START -->` / `<!-- GEAR:END -->`.

Edited by the build: `sitemap.xml`, `disclosure.html`, `data/jsonld/*.json`, `data/search-index.json`. JSON-LD and gear HTML are written into an existing page only between the markers above.

`netlify.toml` is shared deploy config. The build command is `python3 scripts/build_articles.py`, publish stays `.`. Deploy Previews and branch deploys set `ignore = "exit 0"` so those contexts skip the build. Production does not set `ignore`.

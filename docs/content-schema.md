# Content schema and build interface

Contract for the frontend. Branch: `backend/content-pipeline` (cut from `main` at the netlify.app URL hotfix). `redesign` was not on GitHub when this was written. Rebase onto `redesign` once that branch exists.

The build does **not** write meta, Open Graph, canonical, robots.txt, or alt text. It does **not** rewrite article markup. Those stay in the templates the frontend owns.

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
| `date` | yes | `YYYY-MM-DD`. Sitemap `lastmod` |
| `path` | yes | Public path, starting with `/`. Must match an existing HTML file unless the frontend has added JSON-LD markers there |
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
| `ingredients` | yes | List of `{group, items[]}`. Flattened into `recipeIngredient` |
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
- `Article.headline`, `description`, `image`, `datePublished`, `dateModified`, `author`, `publisher`, `mainEntityOfPage`.
- `Recipe` uses `recipeIngredient` and `recipeInstructions`. Image and main entity URLs use `SITE_URL`.
- Reviews have no `reviewRating` unless both rating fields exist. Do not add ratings that were not published.

A copy of each graph is also written to `data/jsonld/<slug>.json` so it can be reviewed when the page has no markers yet. That file is not a public schema block until the markers are in the HTML.

### Snippets the frontend styles and drops in

These are fragments, not pages. The build does not insert them until `docs/frontend-templates.md` on `redesign` names the slots.

| File | Slot contents |
| --- | --- |
| `partials/newsletter-form.html` | Netlify Forms form `newsletter`, honeypot `bot-field`, one-line privacy note |
| `partials/privacy-section.html` | Section `#privacy`: email only, weekly plate, not sold, how to be removed |
| `partials/search.html` | Label, search input, results list. Loads `assets/search.js` |
| `assets/search.js` | Client-side filter of `data/search-index.json` |
| `partials/affiliate-disclosure.html` | Reusable disclosure |
| `partials/affiliate-example.html` | One example link, `https://example.com/example-pan`, not a real program |

`assets/main.js` turns `form[data-subscribe]` into a `mailto:`. The Netlify form does **not** use `data-subscribe`, so that handler will not swallow a real submission. The form has to be in published HTML before Netlify will register it. A partial sitting in `partials/` is not registered.

Affiliate links in Markdown (rendered only if a page is generated later; nothing on the live pages uses this yet):

```text
[[affiliate href="https://example.com/example-pan" text="example pan"]]
```

Output:

```html
<a href="https://example.com/example-pan" rel="sponsored nofollow noopener" target="_blank">example pan</a>
```

The same helper is `render_affiliate_link(href, text)` in `scripts/build_articles.py`. `href` must be `https`. No real affiliate URLs are checked in.

### Legacy `page()` / `card()` helpers

Content Studio's local `build_articles.py` was not in the repo. It string-replaced `templates/article-template.html` (`ARTICLE TITLE`, `SLUG`, and the Lisbon description sentence), wrote `articles/*.html`, and spliced cards into the homepage, guides, and recipes. `lib.py` was **not** imported by that script. It is a Playwright social-image renderer with machine-local paths, and it is not part of this build.

The port keeps `render_article_html()` and `render_card()` so a generated article still comes out as: tag, `h1`, lead, cover image, optional research note, body, sources line. The default build does **not** call them on the live pages. Doing that would overwrite canonical, Open Graph, and alt text, and it would drop pieces the old script never knew about (the Tokyo trip gallery, the ramen photo credit). The default command only validates content, writes `sitemap.xml`, writes `data/jsonld/` and `data/search-index.json`, and fills `<!-- JSON-LD:START -->` … `<!-- JSON-LD:END -->` when both markers are present.

## Sitemap

`content/site.json` lists static paths in order: `/`, `/guides.html`, `/recipes.html`, `/about.html`, `/contact.html`. Content paths follow, sorted by `path`. `lastmod` is the content `date` or the static page's `lastmod`. Drafts are excluded.

`robots.txt` is frontend-owned and already contains `Sitemap: https://platesaroundtheworld.netlify.app/sitemap.xml`. Keep that line pointed at `/sitemap.xml` on `SITE_URL`. This build does not edit `robots.txt`.

## Search index record

```json
{
  "title": "Where to eat in Lisbon",
  "url": "/articles/where-to-eat-lisbon.html",
  "type": "article",
  "description": "…",
  "text": "plain text of the body"
}
```

Restaurant records use the guide URL in `url` and `type: "restaurant"`, because there is no restaurant page.

## Adding a piece of content

1. Add `content/articles/<slug>.md`, `content/recipes/<slug>.md`, or `content/restaurants/<slug>.json`.
2. Set `path` to the existing public URL. Do not invent a new article URL without a redirect (there is no `_redirects` file; none of the current URLs changed).
3. Put the image under `assets/img/` and point `image` at it.
4. Run `python3 scripts/build_articles.py`.
5. Ask the frontend to add `<!-- JSON-LD:START -->` / `<!-- JSON-LD:END -->` on that page, then run the build again so the script tag is injected.

## Files the frontend also owns

Not edited by this pipeline:

- Every HTML page and `templates/`
- `assets/style.css`, `assets/main.js`
- `robots.txt`
- Meta, Open Graph, canonical, and alt text

Edited by the build, and not frontend-owned: `sitemap.xml`, `data/jsonld/*.json`, `data/search-index.json`.

`netlify.toml` is shared deploy config. The build command is `python3 scripts/build_articles.py`, publish stays `.`. Deploy Previews and branch deploys set `ignore = "exit 0"` so those contexts skip the build. Production does not set `ignore`.

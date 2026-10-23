# Frontend templates

The live pages are static HTML. `python3 scripts/render_site.py` writes shell markup from `content/bodies/*.fragment.html` plus the strings in that script. It does not write `sitemap.xml`, `disclosure.html`, or `data/search-index.json`, and if a page already has `<!-- JSON-LD:START -->` or `<!-- GEAR:START -->` it puts the existing interior back. `scripts/build_articles.py` owns those four outputs. Netlify runs that build, not this renderer.

`scripts/serve.py` is a local preview server only.

## What to copy

| File | What it is |
| --- | --- |
| `partials/header.html` | Skip link, header, nav, search. Root-relative URLs, so the same file works at `/` and `/articles/`. |
| `partials/footer.html` | Footer, including the link to `/disclosure.html`, then `assets/main.js`. |
| `partials/search.html` | The search box already inside the header. Do not insert it a second time. |
| `partials/newsletter-form.html` | One newsletter form. One per page. |
| `partials/privacy-section.html` | `#privacy`, on the same page as the form. |
| `partials/footer-disclosure.html` | The single disclosure link. Already in the footer. |
| `templates/article-template.html` | Empty article skeleton. `noindex`. No sample city. |

`disclosure.html` is generated here with that header and footer so `/disclosure` is not a 404 before the content build runs. `_write_disclosure` in `scripts/build_articles.py` still pastes the old header (relative `index.html`, Google Fonts, `style.css?v=4`). On rebase, read `partials/header.html` and `partials/footer.html` instead of that string.

## Slots the content build fills

Markers are exact. The build replaces only the bytes between each pair.

```html
<!-- JSON-LD:START -->
<script type="application/ld+json">…</script>
<!-- JSON-LD:END -->
```

Every article and recipe has this pair once, in `<head>`. The homepage has the same pair for `WebSite` and `Organization`. Guides, recipes, about, and contact do not.

```html
<!-- GEAR:START -->
<!-- GEAR:END -->
```

On `articles/butter-chicken.html` this pair sits immediately after the Ingredients lists and before Notes. The template has the same pair after its Ingredients placeholder. Guides do not have it.

Other markers, not filled by the build:

- `<!-- NEWSLETTER:START -->` … `<!-- NEWSLETTER:END -->` around the form.
- `<!-- PRIVACY:START -->` … `<!-- PRIVACY:END -->` around `#privacy`.
- `<!-- AFFILIATE:START -->` … `<!-- AFFILIATE:END -->` is an HTML comment. Nothing is visible, because no page has an affiliate link yet.
- `<!-- NOTES:START -->` and `<!-- MEASURES: … -->` on the recipe. Visible text says `OWNER TO SUPPLY`.
- `<!-- FUTURE-LINK: … -->` names pieces that are not published. They are not links.

## Search hooks

`assets/search.js` is the file from `backend/content-pipeline`, unchanged. It needs:

- `[data-site-search]` on the input
- `#site-search` so the label's `for` matches
- `[data-site-search-results]` and `#site-search-results` on the results list

The label has class `sr` (hidden visually, still the accessible name). Under 760px the field is inside `.search-slot` and stays closed until `.search-toggle` adds `.open`. `#site-search-results` stays `display: none` while it has the `hidden` attribute. `nav ul { display: flex }` would otherwise paint the empty list, because that author rule beats the browser's `[hidden]` style.

It fetches `/data/search-index.json`, which the content build writes.

## Newsletter hooks

The form keeps Backend's field names: `name="newsletter"`, honeypot `bot-field`, hidden `form-name`, `id="newsletter-email"`. It does not use `data-subscribe`. `assets/main.js` still turns `form[data-subscribe]` into a mailto, and it blocks submit while `action` contains `NEWSLETTER_FORM_ACTION`.

Visible copy, from the approved 22 Oct 2026 sheet:

- Kicker: Newsletter
- Heading: New recipes and guides in your inbox.
- Body: Every source linked. No spam, unsubscribe any time.
- Button: Subscribe
- Small print: We only use your email to send the newsletter.

Placement: the home band; Tokyo after Good to know; Ramen after the cheat-sheet and before Where to learn more; the other articles once, before the footer. One form per page, so the email id stays unique.

## Gear styles

`partials/gear.css` is folded into `assets/style.css` as `.gear-list`, `.gear-item`, `.gear-label`, `.gear-meta`, `.gear-why`, and `.gear-disclosure`. Colours use the site tokens. `scripts/render_site.py` inlines `assets/style.css` in each page so the first paint does not wait on a stylesheet request. Edit the CSS file, then re-run the renderer. That run refreshes the shell and the inlined CSS. It does not replace JSON-LD, gear HTML, the sitemap, the disclosure page, or the search index.

## Page shape

Article order: breadcrumb, tag, `h1`, `p.meta` date line, byline, lead, optional tested note, cover with credit, recipe card on the recipe only, body, Keep reading, privacy, footer.

Listing cards are a `div.tile` so the credit line (which contains links) is not nested inside the card link.

Both `/articles/butter-chicken` and `/articles/butter-chicken.html` return 200. Canonicals, the sitemap, and internal links use the extensionless form. The homepage canonical is `/`. `_redirects` uses `200` rewrites, not `301`.

## Content build

`backend/content-pipeline` is merged. `python3 scripts/build_articles.py` is the Netlify command in `netlify.toml`. Deploy previews and branch deploys set `ignore = "exit 0"`. Production does not. Publish stays `.`.

Running the build twice changes nothing. It rewrites only:

- the interior of `<!-- JSON-LD:START -->` … `<!-- JSON-LD:END -->` on each published article and recipe
- the interior of `<!-- GEAR:START -->` … `<!-- GEAR:END -->` when that page has gear items
- `data/jsonld/<slug>.json`
- `sitemap.xml`
- `data/search-index.json`
- `disclosure.html`, from `content/disclosure.md` plus `partials/header.html` and `partials/footer.html`

The graph is `Article` or `Recipe`, plus `BreadcrumbList`, plus `Restaurant` and `Review` when the content lists a place. `mainEntityOfPage` and sitemap locs are extensionless. The homepage canonical stays `/`. Breadcrumb, canonical, and search-index URLs do not use `.html`. Both the extensionless URL and the `.html` file still return 200 via `_redirects`.

`data/gear/butter-chicken.json` has an empty `items` list, so the gear interior stays the placeholder. The disclosure link the helper would use is `/disclosure.html`.

The newsletter action is still `[NEWSLETTER_FORM_ACTION: TBD]`. The form has no `netlify` attribute and does not promise a weekly send. Privacy is the `<details id="privacy" class="privacy">` note. Recipe times and yield stay `OWNER TO SUPPLY` outside the JSON-LD script; the `Recipe` node has cuisine `Indian (Punjabi / Delhi)` and category `Main`, and no yield or times.

`robots.txt` still points at `https://platesaroundtheworld.netlify.app/sitemap.xml` and disallows `/templates/`, `/partials/`, `/scripts/`, `/content/`, and `/docs/`. The build does not edit it.

Keep reading hubs are `.more-link` rows. The homepage guide and recipe rows use `.grid-2`. Card and Instagram pictures fill their frames. The search label is `.sr`, the results list is hidden until it has hits, and viewports under 760px open search from `.search-toggle`.

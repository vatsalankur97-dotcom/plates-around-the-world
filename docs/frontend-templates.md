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

## Conflicts with `backend/content-pipeline`

Do not merge that branch over this one. Rebase it onto `redesign`, then keep the HTML from this branch and re-run the content build so it only fills the markers.

1. **Article HTML.** This branch rewrote the pages. The pipeline branch still has the old article markup plus its own JSON-LD. Keep these pages. Run the build to replace the JSON-LD interior.
2. **JSON-LD contents.** The hand-written graphs include `BreadcrumbList`. The build's graph does not, and it will delete the breadcrumb node when it replaces the interior. Say if breadcrumbs should be emitted too.
3. **Canonicals vs `path`.** Canonicals here are extensionless (`/articles/ramen-101`, homepage `/`). Content `path` and the pipeline sitemap use `/articles/ramen-101.html`. Both URLs return 200. The build does not edit canonical tags. After a build, JSON-LD `mainEntityOfPage` may be the `.html` URL while the canonical is extensionless.
4. **Sitemap.** `sitemap.xml` here is hand-maintained and extensionless, with `lastmod` 2026-10-22. The build overwrites it from `content/site.json`.
5. **`netlify.toml`.** Not edited here. The pipeline adds `command = "python3 scripts/build_articles.py"` and `ignore = "exit 0"` for deploy previews and branch deploys. That file will come back on rebase. This repo still has no build command until that lands.
6. **Newsletter.** The pipeline partial uses `action="/"` and the `netlify` attribute, and says "weekly plate". Approved copy forbids a weekly promise and sets `action="[NEWSLETTER_FORM_ACTION: TBD]"`. The `netlify` attribute is omitted until the owner picks the tool. Field names match the partial.
7. **Privacy.** The visible block is `<details id="privacy" class="privacy">`, a short note under the newsletter. It does not say the list is weekly and it does not say Netlify stores the address. `assets/main.js` opens it when a link to `#privacy` is clicked. The removal email is unchanged.
8. **Disclosure shell.** `_write_disclosure` hardcodes the pre-redesign header and a relative `disclosure.html` link. Copy `partials/header.html` and `partials/footer.html`. The footer link here is `/disclosure.html`.
9. **Gear disclosure URL.** `gear.py` links articles at `../disclosure.html`. The footer uses `/disclosure.html`. Both resolve. Root-relative is the one that also works if a page moves.
10. **Search URLs.** The starter index uses extensionless URLs. The build writes whatever `path` says, currently `.html`.
11. **`robots.txt`.** Still points at `https://platesaroundtheworld.netlify.app/sitemap.xml`. Also disallows `/templates/`, `/partials/`, `/scripts/`, `/content/`, and `/docs/`. The pipeline does not edit this file.
12. **Recipe times.** The visible card shows Cuisine and Course, then one line: `Times and servings: owner to supply`. Yield, prep, marinate, cook, total, diet, difficulty, and equipment stay `OWNER TO SUPPLY` on `span[data-field]` inside `.recipe-slots` (visually hidden, with a `RECIPE-SLOTS` comment). Do not estimate them. When a value is real, put it in the visible `dl` and update that span. Cuisine `Indian (Punjabi / Delhi)` and course `Main` are the approved labels. JSON-LD omits yield and the times.

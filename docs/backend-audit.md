# Backend audit

Findings are for `main` at `69b8897` (the netlify.app URL hotfix), before this branch. The live site is https://platesaroundtheworld.netlify.app/. `platesaroundtheworld.com` did not resolve.

## How content is stored

Hand-written HTML. Guides and the butter chicken recipe are full pages in `articles/`. Listing cards are copied into `index.html`, `guides.html`, and `recipes.html`. There is no Markdown or JSON content on `main`.

`templates/article-template.html` is a copy-paste starter. Its cover image is the placeholder `../assets/img/SLUG.jpg`, which is not a file.

Content Studio's local `build_articles.py` was never committed. It string-replaced that template for Tokyo and Ramen, then spliced cards into the listings and patched `assets/main.js` and `sitemap.xml`. Those edits are already in the HTML. `lib.py` is a separate Playwright social-image script and is not imported by the article generator. Neither file belonged in the site build.

## Build, Netlify, redirects

`netlify.toml` on `main` is only `publish = "."`. No build command. Deploy Previews are enabled in the Netlify UI (frontend audit). There is no `_redirects`, `_headers`, or `[[redirects]]`.

A production deploy of the static tree costs about 15 of 300 monthly credits. This branch adds a Python build command and tells deploy-preview and branch-deploy contexts to skip (`ignore = "exit 0"`). Do not open a pull request while previews are on.

## Sitemap, robots, structured data, meta

`sitemap.xml` lists `/` (not `/index.html`) plus the four section pages and five articles, on `https://platesaroundtheworld.netlify.app`. `robots.txt` already points at `Sitemap: https://platesaroundtheworld.netlify.app/sitemap.xml`. Leave that file alone; it is frontend-owned. Keep the sitemap line on `/sitemap.xml`.

No JSON-LD on `main`. Title, description, canonical, and Open Graph tags are in each HTML head. The homepage canonical is still `…/index.html`. The frontend will set it to `/`. This branch does not edit that tag. The sitemap homepage stays `/`.

## Forms, search, affiliates, analytics, privacy

The newsletter form is `form[data-subscribe]`. `assets/main.js` cancels submit and opens a `mailto:` to plates.arounddtheworld@gmail.com. The contact form is also `mailto:`. Neither is a Netlify Form. No privacy page, no search, no analytics snippet, no affiliate links. Social links use `rel="noopener"` only.

## Links and secrets

Internal `href` and `src` targets resolve, except the template's `SLUG.jpg` placeholder. External links were not treated as failures.

No API keys, tokens, or private credentials are committed. The public contact address is intentional. Affiliate IDs do not exist and must stay out of the repo until a programme is actually joined; a tracking tag is public, but an empty tag must never be emitted as `tag=`.

## What this branch adds

Structured content under `content/`, `scripts/build_articles.py` plus `scripts/gear.py`, generated sitemap, JSON-LD files, search index, and `/disclosure.html`. Live article HTML is unchanged until a page contains `<!-- JSON-LD:START -->` / `<!-- JSON-LD:END -->` or `<!-- GEAR:START -->` / `<!-- GEAR:END -->`. Newsletter, search, and the footer disclosure link are snippets in `partials/`. `AFFILIATE_LINKS_ENABLED` is false. The gear list for butter chicken is empty, so the section is omitted.

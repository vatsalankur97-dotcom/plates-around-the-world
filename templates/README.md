# Adding a post

`article-template.html` is an empty skeleton. It is `noindex`, and it does not contain another article's text.

1. Copy it to `articles/<slug>.html`.
2. Replace `ARTICLE TITLE`, `SLUG`, the meta description, the lead, the cover alt, and the body.
3. Set the date line. Add `Updated` only when the body or the cover actually changes.
4. Pick one honesty note from the comments in the template.
5. Add a credit line. Stock photos use `Photo: NAME / SITE (LICENCE). Stock photo, not from our trip.`
6. Strip EXIF and GPS from the image before it is committed. Do not edit faces. Flag any face that might not be the owner.
7. For a recipe, show the recipe card and leave prep, cook, total, marinate, and serves as `OWNER TO SUPPLY` until a real value exists. Keep `<!-- GEAR:START -->` / `<!-- GEAR:END -->` directly after Ingredients, and `<!-- JSON-LD:START -->` / `<!-- JSON-LD:END -->` once in the head.
8. Add a Keep reading block of pages that already exist.
9. Add the card to `index.html` and to `guides.html` or `recipes.html`. Ramen 101 is a guide, not a recipe.
10. Ask Backend to add the content file and run `python3 scripts/build_articles.py`, which fills the JSON-LD and gear markers and rewrites `sitemap.xml`.

The redesign pages were generated with `python3 scripts/render_site.py`. See `docs/frontend-templates.md`.

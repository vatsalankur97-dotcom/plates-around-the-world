# Google Search Console

No sign-in was done. Nothing below submits the site or creates a verification token.

## Which property

Verify the host that actually serves the site:

`https://platesaroundtheworld.netlify.app/`

Use a URL-prefix property for that origin. `platesaroundtheworld.com` did not resolve at the time of the audit, and the canonicals on `main` now use the netlify.app host.

DNS verification is not available for a `netlify.app` subdomain. The DNS for `netlify.app` belongs to Netlify, not to this project. A custom domain would be required before a DNS TXT record could prove ownership.

## How to verify

Prefer the HTML-file method. It does not touch the meta tags the frontend owns.

1. In Search Console, choose the HTML file method. Google shows a file name like `google1234abcd.html` and a one-line body.
2. Put that file, unchanged, in the repo root. `netlify.toml` publishes `.`, so the file is served at `https://platesaroundtheworld.netlify.app/google1234abcd.html`.
3. Deploy production (a merge to `main`, not a pull request). Confirm the file returns 200, then click Verify.

The HTML-tag method also works on this host. Google's meta tag would go in `<head>`:

```html
<meta name="google-site-verification" content="TOKEN">
```

That is a meta tag, so the frontend adds it. Do not invent a token in the repo.

## Sitemap

After the property is verified:

1. Open Sitemaps.
2. Submit `sitemap.xml`.
3. The full URL is `https://platesaroundtheworld.netlify.app/sitemap.xml`.

The file lists the homepage as `https://platesaroundtheworld.netlify.app/` (path `/`). Every loc matches the extensionless canonical, including `/disclosure` and `/articles/butter-chicken`. The `.html` files still return 200. This repo does not edit the canonical tags.

## Not done from here

Search Console, Analytics, and Netlify's domain settings all need a signed-in owner. This branch does not add a verification file, a measurement id, or a DNS record.

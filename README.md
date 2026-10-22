# Plates Around the World

Restaurant guides and home recipes from every corner of the map. Researched city guides and recipes you can cook at home.

Live site: https://platesaroundtheworld.netlify.app/

This is a static site. Netlify publishes the committed HTML. There is no build command on this branch. `python3 scripts/render_site.py` regenerates the pages locally from `content/bodies/` and is not part of the deploy. See `docs/frontend-templates.md` for the header, footer, and the slots the content build fills.

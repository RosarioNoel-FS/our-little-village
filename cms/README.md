# Editing the site (Pages CMS)

**What the client can edit:** the six category pages (headings, text, cards, prices, buttons, photos, gallery) and the homepage "What we do" panels. Everything else (intro film, layout, colors, animations, contact page) stays locked.

**How it works:** she edits at app.pagescms.org → Pages CMS commits the JSON in `content/` (and photos in `assets/work/`) → `.github/workflows/cms.yml` shrinks big photos, runs `cms/build.py`, commits the HTML and asks GitHub Pages to publish. It takes about 1–2 minutes. If an edit is invalid, the build stops and the live site stays as it was. Check the repo's Actions tab.

**Text tip for her:** put `*stars*` around words to get the accent style, like `Birthday *Parties*`.

## Noel's one-time setup
1. Go to pagescms.org, sign in with GitHub and install the Pages CMS app on `RosarioNoel-FS/our-little-village` only.
2. Open the repo in Pages CMS, then go to Settings → Collaborators and invite her email. She doesn't need a GitHub account.

## Working on the site locally after she starts editing
The GitHub repo is now the source of truth for `content/` and `assets/work/`. Before changing anything locally, pull those two folders from the repo. Otherwise the next publish (rsync) overwrites her edits. Rebuild locally with `python3 cms/build.py`.

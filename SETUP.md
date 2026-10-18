# Running the ycgNem site

The site is plain HTML built by `build.py` (Python, no installs) from the `content/` folder.
GitHub builds and publishes it on every push, and once a day so each game's "updated" date stays current.

## See it on your PC

Double-click **`Preview site.bat`**. It builds the site and opens http://localhost:8090.

## Put it online (once, about 5 minutes)

The repo must be named exactly `ycgnem.github.io` so the site lives at https://ycgnem.github.io.
Your games already live at `ycgnem.github.io/<game>/`, so they'll sit under the same address.

In a terminal in this folder:

```bash
git init -b main
git add -A
git commit -m "Launch the ycgNem site"
gh repo create ycgnem.github.io --public --source . --push
gh api -X POST repos/ycgNem/ycgnem.github.io/pages -f build_type=workflow
```

Then open https://github.com/ycgNem/ycgnem.github.io/actions and wait for the green check (about a minute).
After that, double-click **`Publish site.bat`** whenever you change something.

## Turn on comments (giscus, free, about 5 minutes)

Comments are stored as GitHub Discussions on this repo. Commenters sign in with GitHub.

1. Turn on Discussions: `gh repo edit ycgNem/ycgnem.github.io --enable-discussions`
2. Install the giscus app on this repo only: https://github.com/apps/giscus
3. On GitHub, go to the repo → Discussions → the pencil next to Categories → **New category**.
   Name it `Comments` and choose the **Announcement** format, so only giscus and you can start threads.
4. Get the IDs:
   ```bash
   gh api graphql -f query='{repository(owner:"ycgNem",name:"ycgnem.github.io"){id discussionCategories(first:20){nodes{id name}}}}'
   ```
5. In `content/site.json`, paste the repository `id` into `giscus.repoId` and the Comments category `id`
   into `giscus.categoryId`. Publish. Every game page and devlog post now has its own thread.

## Add your social links

Paste each profile URL into `socials` in `content/site.json`. Empty ones stay hidden.
Adding the Discord invite also switches the header button to "Join the Discord".
Make the Discord invite **never expire** (Server Settings → Invites, or the invite dialog's settings).

## Add a game

1. Add an entry to `content/games.json` (copy one that's similar). `status` is one of
   `released`, `playable` (shows as Early access), `playtest`, `prototype`, `indev`.
2. Put screenshots in `assets/games/<id>/`: `cover.webp` (1280×720), `cover-640.webp` (640×360),
   and any number of `shot1.webp`, `shot2.webp`... They show up in the game page's gallery.
3. Publish.

## Change what's featured on the home page

The big switcher at the top of the home page is `spotlight` in `content/site.json`: one to four games, each with
the amber line under its title (`kicker`), the line on its tab (`short`), a 1280×720 screenshot (`image`) and where
"What's new" goes (`link`). Put the newest update first.

Below it, games sit on shelves by `status`: Released, Early access, In playtest, Prototypes. The game marked
`"featured": true` gets the big card on its shelf.

## Write a devlog post

Make a file in `content/devlog/` named `YYYY-MM-DD-short-name.md`:

```
---
title: The post title
date: 2026-10-20
summary: One sentence for the list and for link previews.
cover: /assets/games/last-watt/cover.webp
game: last-watt
---

Write here. ## for headings, - for lists, **bold**, [links](https://...), ![alt](/path.webp).
```

`game:` is optional. It adds a Play button and lists the post on that game's page. Posts also go out on the RSS feed at `/feed.xml`.

## Files

| Path | What it is |
|---|---|
| `content/games.json` | every game: text, status, controls, links |
| `content/site.json` | socials, Discord, comments settings |
| `content/devlog/` | devlog posts |
| `assets/` | CSS, JS, logos, screenshots |
| `build.py` | turns all of that into `_site/` |
| `.github/workflows/deploy.yml` | builds and publishes on GitHub |

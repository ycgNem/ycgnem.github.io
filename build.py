"""Build the ycgNem site into _site/.

No dependencies: plain Python 3.  Edit content/ (games.json, site.json, devlog/*.md), then run
`python build.py` (or double-click "Preview site.bat").  GitHub Actions runs this on every push.
"""
import html
import json
import os
import re
import shutil
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
SITE = json.loads((ROOT / "content/site.json").read_text(encoding="utf8"))
GAMES = json.loads((ROOT / "content/games.json").read_text(encoding="utf8"))
BASE = SITE["url"].rstrip("/")
e = html.escape

STATUS = {
    "released": "Released",
    "playable": "Early access",
    "playtest": "Playtest",
    "prototype": "Prototype",
    "indev": "In development",
}
SOCIAL_NAMES = {
    "discord": "Discord", "youtube": "YouTube", "tiktok": "TikTok", "x": "X", "bluesky": "Bluesky",
    "instagram": "Instagram", "itch": "itch.io", "reddit": "Reddit", "github": "GitHub",
}
FONTS = ("https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400"
         "&family=JetBrains+Mono:wght@400;600&family=Pixelify+Sans:wght@400..700&family=Silkscreen&display=swap")
PLAY_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M4 2h2v1h2v1h2v1h2v1h1v4h-1v1h-2v1H8v1H6v1H4z"/></svg>'


# ---------------------------------------------------------------- helpers

def fetch_updated():
    """Last push date per repo from the GitHub API (best effort; build works offline)."""
    out = {}
    token = os.environ.get("GITHUB_TOKEN")
    for g in GAMES:
        if not g.get("repo"):
            continue
        req = urllib.request.Request(f"https://api.github.com/repos/ycgNem/{g['repo']}",
                                     headers={"User-Agent": "ycgnem-site-build"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=6) as r:
                out[g["id"]] = json.load(r)["pushed_at"][:10]
        except Exception:
            pass
    return out


def nice_date(iso):
    d = date.fromisoformat(iso)
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def inline_md(s):
    s = e(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" loading="lazy">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def md(text):
    """Small Markdown subset: headings, paragraphs, lists, quotes, images, links, bold, code."""
    out, para, lst = [], [], None

    def flush():
        nonlocal para, lst
        if para:
            joined = " ".join(para)
            if re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", joined.strip()):
                out.append(inline_md(joined))
            else:
                out.append(f"<p>{inline_md(joined)}</p>")
            para = []
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{inline_md(i)}</li>" for i in items) + f"</{tag}>")
            lst = None

    for line in text.splitlines():
        s = line.rstrip()
        if not s.strip():
            flush(); continue
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if m:
            flush(); n = len(m.group(1)) + 1
            out.append(f"<h{n}>{inline_md(m.group(2))}</h{n}>"); continue
        m = re.match(r"\s*([-*]|\d+\.)\s+(.*)", s)
        if m:
            if para: flush()
            tag = "ol" if m.group(1)[0].isdigit() else "ul"
            if lst and lst[0] != tag: flush()
            if not lst: lst = (tag, [])
            lst[1].append(m.group(2)); continue
        if s.startswith(">"):
            flush(); out.append(f"<blockquote>{inline_md(s[1:].strip())}</blockquote>"); continue
        if lst:
            lst[1][-1] += " " + s.strip(); continue
        para.append(s.strip())
    flush()
    return "\n".join(out)


def load_posts():
    posts = []
    for f in sorted((ROOT / "content/devlog").glob("*.md"), reverse=True):
        raw = f.read_text(encoding="utf8")
        m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
        meta = {}
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", f.stem)
        posts.append({**meta, "slug": slug, "body": md(m.group(2))})
    posts.sort(key=lambda p: (p["date"], p.get("time", "")), reverse=True)
    return posts


def socials_html(cls="socials"):
    links = [f'<a href="{e(u)}" rel="me noopener">{SOCIAL_NAMES[k]}</a>'
             for k, u in SITE["socials"].items() if u]
    return f'<div class="{cls}">' + "".join(links) + "</div>"


def chip(status):
    return f'<span class="chip st-{status}">{STATUS[status]}</span>'


def layout(path, title, desc, body, image="/assets/brand/og-image.png", kind="website", wide=False):
    wrap = "wrap wide" if wide else "wrap"
    full_title = f"{title} · ycgNem" if title != "ycgNem" else "ycgNem — free browser games, built in the open"
    nav = [("/#games", "Games"), ("/devlog/", "Devlog"), ("/community/", "Community")]
    nav_html = "".join(
        f'<a href="{h}"{" aria-current=\"page\"" if path.startswith(h) and h != "/#games" else ""}>{t}</a>'
        for h, t in nav)
    discord = SITE["socials"].get("discord")
    cta = (f'<a class="btn btn-primary btn-sm head-cta" href="{e(discord)}">Join the Discord</a>' if discord else
           f'<a class="btn btn-ghost btn-sm head-cta" href="{e(SITE["socials"]["github"])}">GitHub</a>')
    img_abs = image if image.startswith("http") else BASE + image
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{BASE}{path}">
<meta property="og:type" content="{kind}">
<meta property="og:site_name" content="ycgNem">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{img_abs}">
<meta property="og:url" content="{BASE}{path}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#15101c">
<link rel="icon" href="/assets/brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/brand/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/brand/avatar-180.png">
<link rel="alternate" type="application/rss+xml" title="ycgNem devlog" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/assets/css/site.css">
</head>
<body>
<header class="site-head">
  <div class="{wrap}">
    <a class="logo" href="/" aria-label="ycgNem home"><img src="/assets/brand/ycgnem-lockup.svg" alt="ycgNem" width="113" height="30"></a>
    <nav class="nav" aria-label="Main">{nav_html}</nav>
    {cta}
  </div>
</header>
<main>
{body}
</main>
<footer class="site-foot">
  <div class="{wrap}">
    <img src="/assets/brand/ycgnem-wordmark.svg" alt="ycgNem" width="95" height="22">
    <nav aria-label="Footer">
      <a href="/devlog/">Devlog</a><a href="/community/">Community</a>
      <a href="/feed.xml">RSS</a><a href="{e(SITE['socials']['github'])}">GitHub</a>
    </nav>
    <p>Built with Claude Opus. Free games, public code, no ads, no trackers. © <span data-year>{date.today().year}</span> ycgNem</p>
  </div>
</footer>
<script src="/assets/js/site.js" defer></script>
</body>
</html>
"""


def giscus(term):
    g = SITE["giscus"]
    if not g.get("repoId") or not g.get("categoryId"):
        return ('<div class="comments-off">Comments open soon. Until then, '
                + (f'<a href="{e(SITE["socials"]["discord"])}">say it in the Discord</a>' if SITE["socials"].get("discord")
                   else f'<a href="{e(SITE["socials"]["github"])}">find me on GitHub</a>')
                + ".</div>")
    return f"""<script src="https://giscus.app/client.js" data-repo="{e(g['repo'])}" data-repo-id="{e(g['repoId'])}"
 data-category="{e(g['category'])}" data-category-id="{e(g['categoryId'])}" data-mapping="specific"
 data-term="{e(term)}" data-strict="1" data-reactions-enabled="1" data-emit-metadata="0"
 data-input-position="top" data-theme="transparent_dark" data-lang="en" data-loading="lazy"
 crossorigin="anonymous" async></script>"""


# ---------------------------------------------------------------- pages

def ver(g):
    v = g["version"]
    return e(f"v{v}" if v[:1].isdigit() else v)


def card(g, updated):
    href = f"/games/{g['id']}/"
    play = (f'<a class="btn btn-primary btn-sm" href="{href}#play">{PLAY_ICON}Play</a>' if g["play"]
            else '<span class="btn btn-ghost btn-sm" aria-disabled="true">Coming soon</span>')
    upd = f' · updated {nice_date(updated[g["id"]])}' if g["id"] in updated else ""
    return f"""<article class="card{" feature" if g.get("featured") else ""}">
  <a class="card-img" href="{href}" tabindex="-1"><img src="/assets/games/{g['id']}/cover-640.webp" alt="{e(g['title'])} screenshot" loading="lazy" width="640" height="360">{chip(g['status'])}</a>
  <div class="card-body">
    <div class="card-title"><h3><a href="{href}">{e(g['title'])}</a></h3><span class="ver">{ver(g)}</span></div>
    <p class="genre">{e(g['genre'])}{upd}</p>
    <p class="pitch">{e(g['pitch'])}</p>
    <p class="stat">{e(g['number'])}</p>
    <div class="card-actions">{play}<a class="btn btn-ghost btn-sm" href="{href}">Details</a></div>
  </div>
</article>"""


def post_rows(posts):
    return '<div class="posts">' + "".join(f"""<a class="post-row" href="/devlog/{p['slug']}/">
  <time datetime="{p['date']}">{nice_date(p['date'])}</time>
  <img src="{e(p['cover'])}" alt="" loading="lazy">
  <div><h3>{e(p['title'])}</h3><p>{e(p['summary'])}</p></div>
</a>""" for p in posts) + "</div>"


# Home page shelves: which statuses go on which shelf, in order. Empty shelves are skipped.
SHELVES = [
    (("released",), "Released", "Finished, polished, and still getting updates.", False),
    (("playable",), "Early access", "Playable and growing. Updates land often.", False),
    (("playtest",), "In playtest", "Playable start to finish, with rough edges.", False),
    (("prototype", "indev"), "Prototypes", "Small builds that test whether an idea is fun.", True),
]


def spotlight():
    """The big switcher at the top of the home page. Pure CSS: one radio per slide."""
    items = [(s, next(g for g in GAMES if g["id"] == s["game"])) for s in SITE.get("spotlight", [])][:4]
    radios = "".join(f'<input class="spot-radio" type="radio" name="spot" id="spot-{i}"{" checked" if i == 0 else ""}>'
                     for i in range(len(items)))
    slides = "".join(f"""<article class="slide s{i}">
      <img src="{e(s['image'])}" alt="{e(g['title'])} screenshot" width="1280" height="720"{' loading="lazy"' if i else ""}>
      <div class="slide-panel">
        <div class="meta">{chip(g['status'])}<span class="ver">{ver(g)}</span></div>
        <h2>{e(g['title'])}</h2>
        <p class="kicker">{e(s['kicker'])}</p>
        <p class="pitch">{e(g['pitch'])}</p>
        <div class="slide-actions">
          <a class="btn btn-primary" href="/games/{g['id']}/#play">{PLAY_ICON}Play free</a>
          <a class="btn btn-ghost" href="{e(s['link'])}">What's new</a>
        </div>
      </div>
    </article>""" for i, (s, g) in enumerate(items))
    tabs = "".join(f"""<label class="spot-tab" for="spot-{i}">
      <img src="/assets/games/{g['id']}/cover-640.webp" alt="" width="640" height="360" loading="lazy">
      <span><b>{e(g['title'])}</b><span>{e(s['short'])}</span></span>
    </label>""" for i, (s, g) in enumerate(items))
    tabs_html = f'<div class="spot-tabs">{tabs}</div>' if len(items) > 1 else ""
    return f'<div class="spot">{radios}<div class="spot-stage">{slides}</div>{tabs_html}</div>'


def feature_card(g):
    return f"""<a class="feature-card" href="/games/{g['id']}/">
  <img src="/assets/games/{g['id']}/cover.webp" alt="{e(g['title'])} screenshot" width="1280" height="720" loading="lazy">
  <div class="feature-body">
    <div class="meta">{chip(g['status'])}<span class="ver">{ver(g)}</span></div>
    <h3>{e(g['title'])}</h3>
    <p class="genre">{e(g['genre'])} · {e(g['platforms'])}</p>
    <p class="pitch">{e(g['pitch'])}</p>
    <p class="stat">{e(g['number'])}</p>
  </div>
</a>"""


def shelf_card(g, small):
    body = (f'<p class="genre">{e(g["genre"])}</p>' if small
            else f'<p class="pitch">{e(g["pitch"])}</p><p class="stat">{e(g["number"])}</p>')
    soon = "" if g["play"] else '<p class="soon">Not playable online yet</p>'
    return f"""<a class="shelf-card" href="/games/{g['id']}/">
  <img src="/assets/games/{g['id']}/cover-640.webp" alt="{e(g['title'])} screenshot" width="640" height="360" loading="lazy">
  <div class="shelf-title"><h3>{e(g['title'])}</h3><span class="ver st-{g['status']}">{ver(g)}</span></div>
  {body}{soon}
</a>"""


def shelves():
    out = []
    for statuses, title, blurb, small in SHELVES:
        games = [g for g in GAMES if g["status"] in statuses]
        if not games:
            continue
        feature = next((g for g in games if g.get("featured")), None)
        rest = [g for g in games if g is not feature]
        grid = (f'<div class="shelf-grid{" sm" if small else ""}">{"".join(shelf_card(g, small) for g in rest)}</div>'
                if rest else "")
        out.append(f"""<div class="shelf">
  <div class="shelf-head"><h3>{title}</h3><p class="muted">{blurb}</p></div>
  {feature_card(feature) if feature else ""}{grid}
</div>""")
    return "".join(out)


def post_list(posts):
    return '<div class="post-list">' + "".join(f"""<a href="/devlog/{p['slug']}/">
  <time datetime="{p['date']}">{nice_date(p['date'])}</time>
  <div><h3>{e(p['title'])}</h3><p>{e(p['summary'])}</p></div>
</a>""" for p in posts) + "</div>"


def page_index(posts, updated):
    playable = [g for g in GAMES if g["play"]]
    discord = SITE["socials"].get("discord")
    join = [f'<a class="btn btn-primary" href="{e(discord)}">Join the Discord</a>' if discord
            else '<span class="btn btn-ghost" aria-disabled="true">Discord opens soon</span>']
    join += [f'<a class="btn btn-ghost" href="{e(u)}" rel="me noopener">Follow on {SOCIAL_NAMES[k]}</a>'
             for k, u in SITE["socials"].items() if u and k != "discord"]
    join.append('<a class="btn btn-ghost" href="/feed.xml">RSS feed</a>')
    body = f"""
<h1 class="vh">ycgNem: free browser games, built in the open</h1>
<section class="showcase">
  <div class="wrap wide">{spotlight()}</div>
</section>

<section class="band" id="games">
  <div class="wrap wide">
    <div class="band-head">
      <div><p class="eyebrow">The cabinet</p><h2>Every game, free in your browser</h2></div>
      <ul class="proof">
        <li><b>{len(playable)}</b> playable now</li>
        <li><b>{len(GAMES)}</b> public repos</li>
        <li><b>0</b> ads, accounts or downloads</li>
      </ul>
    </div>
    <div class="shelves">{shelves()}</div>
    <p class="muted shelf-note">Best on a computer with a keyboard and mouse.</p>
  </div>
</section>

<section class="band">
  <div class="wrap wide home-devlog">
    <div class="home-devlog-head">
      <p class="eyebrow">Devlog</p>
      <h2>What shipped lately</h2>
      <p class="muted">What changed, why, and the numbers behind it.</p>
      <a class="btn btn-ghost btn-sm" href="/devlog/">All posts</a>
    </div>
    {post_list(posts[:3])}
  </div>
</section>

<section class="band">
  <div class="wrap wide">
    <div class="join">
      <div class="join-copy">
        <p class="eyebrow" style="color:var(--teal)">Free play · built in the open</p>
        <h2>Playtest with me</h2>
        <p class="muted">New builds land in the Discord first. Vote on what gets built next, and get your name in the credits of the games you shaped. Every repo is public and every update gets patch notes.</p>
      </div>
      <div class="join-actions">{"".join(join)}</div>
    </div>
  </div>
</section>
"""
    return layout("/", "ycgNem", SITE["description"], body, wide=True)


def page_game(g, updated, posts):
    others = [o for o in GAMES if o["id"] != g["id"]][:3]
    shots = sorted(p.name for p in (ROOT / f"assets/games/{g['id']}").glob("shot*.webp"))
    gallery = "".join(f'<a href="/assets/games/{g["id"]}/{s}"><img src="/assets/games/{g["id"]}/{s}" alt="{e(g["title"])} screenshot" loading="lazy"></a>' for s in shots)
    if g["play"]:
        player = f"""<div class="player" data-player="{e(g['play'])}" data-title="{e(g['title'])}" id="play">
      <img class="poster" src="/assets/games/{g['id']}/cover.webp" alt="" width="1280" height="720">
      <button class="start" type="button"><span class="press">▶ PRESS START</span><span class="hint">Loads the game right here. {e(g['session'])}.</span></button>
    </div>
    <div class="player-bar">
      <button class="btn btn-primary btn-sm" type="button" data-fullscreen>Fullscreen</button>
      <a class="btn btn-ghost btn-sm" href="{e(g['play'])}" target="_blank" rel="noopener">Open in its own tab</a>
      <a class="btn btn-ghost btn-sm" href="https://github.com/ycgNem/{g['repo']}">Source code</a>
      <a class="btn btn-ghost btn-sm" href="https://github.com/ycgNem/{g['repo']}/issues/new">Report a bug</a>
      {f'<a class="btn btn-ghost btn-sm" href="{e(g["notesUrl"])}">Read the {e(g["notes"])}</a>' if g.get("notesUrl") else ""}
    </div>
    <p class="mobile-note">These games are built for a keyboard and mouse. On a phone, save the link and play on a computer.</p>"""
    else:
        player = f"""<div class="player"><img class="poster" src="/assets/games/{g['id']}/cover.webp" alt="" style="filter:brightness(.7)">
      <div class="start" style="cursor:default"><span class="press">IN DEVELOPMENT</span><span class="hint">Not playable online yet. Follow the devlog for the first build.</span></div></div>"""
    keys = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in g["controls"])
    upd = f"<div><dt>Updated</dt><dd class=\"mono\">{nice_date(updated[g['id']])}</dd></div>" if g["id"] in updated else ""
    related = [p for p in posts if p.get("game") == g["id"]]
    body = f"""
<div class="wrap">
  <header class="game-head">
    <p class="crumbs"><a href="/#games">Games</a> / {e(g['title'])}</p>
    <h1>{e(g['title'])}</h1>
    <div class="meta">{chip(g['status'])}<span class="muted">{e(g['genre'])}</span><span class="stat">{e(g['number'])}</span></div>
  </header>
  {player}
  <div class="game-body">
    <div class="prose">
      <p class="lede">{e(g['pitch'])}</p>
      {"".join(f"<p>{e(p)}</p>" for p in g['about'])}
      {f'<h2>Screenshots</h2><div class="gallery">{gallery}</div>' if gallery else ""}
      {('<h2>Devlog</h2>' + post_rows(related)) if related else ""}
    </div>
    <aside class="facts">
      <dl>
        <div><dt>Status</dt><dd>{STATUS[g['status']]} · <span class="mono">{ver(g)}</span></dd></div>
        <div><dt>Session</dt><dd>{e(g['session'])}</dd></div>
        <div><dt>Plays on</dt><dd>{e(g['platforms'])}</dd></div>
        {upd}
        <div><dt>Price</dt><dd>Free</dd></div>
      </dl>
      {f'<div><p class="eyebrow" style="margin-bottom:6px">Controls</p><table class="keys">{keys}</table></div>' if keys else ""}
      <p class="made"><strong>How it's made:</strong> {e(g['madeWith'])}</p>
    </aside>
  </div>
  <section class="comments" id="comments">
    <h2>Comments</h2>
    <p class="muted">What did it make you feel? What would you change? I read and reply to everything.</p>
    {giscus("game:" + g["id"])}
  </section>
  <section class="band" style="padding-top:40px">
    <div class="band-head"><h2>More games</h2></div>
    <div class="grid">{"".join(card(o, updated) for o in others)}</div>
  </section>
</div>"""
    return layout(f"/games/{g['id']}/", g["title"], g["pitch"], body, f"/assets/games/{g['id']}/cover.webp", "game")


def page_devlog(posts):
    body = f"""
<div class="wrap">
  <header class="post-head"><p class="eyebrow">Devlog</p><h1>What I'm building</h1>
  <p class="lede">Releases, patch notes in plain words, and how things got made. Also on <a href="/feed.xml">RSS</a>.</p></header>
  {post_rows(posts)}
  <div style="height:72px"></div>
</div>"""
    return layout("/devlog/", "Devlog", "Releases, patch notes and how the games get made.", body)


def page_post(p):
    game = next((g for g in GAMES if g["id"] == p.get("game")), None)
    cta = (f'<p><a class="btn btn-primary" href="/games/{game["id"]}/#play">{PLAY_ICON}Play {e(game["title"])}</a></p>' if game and game["play"] else "")
    body = f"""
<div class="wrap">
  <header class="post-head">
    <p class="crumbs"><a href="/devlog/">Devlog</a></p>
    <h1>{e(p['title'])}</h1>
    <time datetime="{p['date']}">{nice_date(p['date'])}</time>
  </header>
  <img class="post-cover" src="{e(p['cover'])}" alt="">
  <article class="post-body prose">{p['body']}{cta}</article>
  <section class="comments">{giscus("post:" + p["slug"])}</section>
</div>"""
    return layout(f"/devlog/{p['slug']}/", p["title"], p["summary"], body, p["cover"], "article")




def page_community():
    discord = SITE["socials"].get("discord")
    discord_btn = (f'<a class="btn btn-primary" href="{e(discord)}">Join the Discord</a>' if discord
                   else '<span class="btn btn-ghost" aria-disabled="true">Discord opens soon</span>')
    body = f"""
<div class="wrap">
  <header class="post-head">
    <p class="eyebrow">Community</p>
    <h1>Help shape the games</h1>
    <p class="lede">The games get better when people play them and tell me the truth. Here's where that happens.</p>
  </header>
  <section class="band" style="padding-top:24px">
    <div class="community">
      <div class="discord-card">
        <h2>The Discord</h2>
        <p class="muted">The home base. New builds drop here first, with a playtest channel for each game, a place to share runs and builds, and polls on what gets made next.</p>
        <div>{discord_btn}</div>
      </div>
      <div style="display:grid;gap:16px">
        <h3>Everywhere else</h3>
        {socials_html()}
        <p class="muted">RSS: <a href="/feed.xml">{BASE}/feed.xml</a></p>
      </div>
    </div>
  </section>
  <section class="band">
    <div class="split">
      <div class="panel">
        <h3>Good feedback looks like</h3>
        <ul>
          <li>What you felt: bored, tense, confused, hooked</li>
          <li>The moment it happened ("wave 4, when the Shades cut my Node")</li>
          <li>What you expected instead</li>
          <li>Bugs: what you did, what happened, your browser</li>
        </ul>
      </div>
      <div class="panel">
        <h3>House rules</h3>
        <ul>
          <li>Be kind. Critique the game, not people.</li>
          <li>No spam, no self-promo without asking.</li>
          <li>Spoilers go behind spoiler tags.</li>
          <li>Disagree with a design call? Great. Say why.</li>
        </ul>
      </div>
    </div>
  </section>
  <section class="band">
    <h2 style="margin-bottom:12px">Credits</h2>
    <p class="muted" style="max-width:62ch">Playtesters whose feedback changes a game get their name in that game's credits. First names on the list go here soon.</p>
  </section>
</div>"""
    return layout("/community/", "Community", "Playtest ycgNem's games, give feedback, and follow along.", body)


def page_404():
    body = """<div class="wrap"><header class="post-head" style="padding-block:96px">
<p class="eyebrow">404</p><h1>GAME OVER</h1><p class="lede">That page isn't here. Insert coin to continue.</p>
<p><a class="btn btn-primary" href="/">Continue</a></p></header></div>"""
    return layout("/404.html", "Not found", "Page not found.", body)


def feed(posts):
    items = "".join(f"""<item><title>{e(p['title'])}</title><link>{BASE}/devlog/{p['slug']}/</link>
<guid>{BASE}/devlog/{p['slug']}/</guid><pubDate>{datetime.fromisoformat(p['date']).replace(tzinfo=timezone.utc).strftime('%a, %d %b %Y 12:00:00 +0000')}</pubDate>
<description>{e(p['summary'])}</description></item>""" for p in posts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>ycgNem devlog</title><link>{BASE}/</link>
<description>{e(SITE['description'])}</description>{items}</channel></rss>
"""


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "assets", OUT / "assets")
    updated = fetch_updated()
    posts = load_posts()
    write("index.html", page_index(posts, updated))
    for g in GAMES:
        write(f"games/{g['id']}/index.html", page_game(g, updated, posts))
    write("devlog/index.html", page_devlog(posts))
    for p in posts:
        write(f"devlog/{p['slug']}/index.html", page_post(p))
    write("community/index.html", page_community())
    write("404.html", page_404())
    write("feed.xml", feed(posts))
    urls = ["/", "/devlog/", "/community/"] + [f"/games/{g['id']}/" for g in GAMES] + [f"/devlog/{p['slug']}/" for p in posts]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{BASE}{u}</loc></url>" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    write(".nojekyll", "")
    print(f"Built {len(urls)} pages into {OUT} ({len(updated)} repo dates from GitHub)")


if __name__ == "__main__":
    main()

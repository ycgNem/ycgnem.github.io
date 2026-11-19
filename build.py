"""Build the ycgNem site into _site/.

Plain Python 3, no packages.  Edit content/ (games.json, site.json, devlog/*.md), then run
`npm run build` (or double-click "Preview site.bat").  GitHub Actions runs it on every push.
The site script is TypeScript in src/; `npm run build:js` bundles it to assets/js/site.js first.
"""
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
SITE = json.loads((ROOT / "content/site.json").read_text(encoding="utf8"))
GAMES = json.loads((ROOT / "content/games.json").read_text(encoding="utf8"))
BASE = SITE["url"].rstrip("/")
TODAY = date.today()
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
PROMPT = '<span class="prompt" aria-hidden="true">&gt;_</span>'

# Home page shelves: which statuses go on which shelf, in order, and how big its cards are.
SHELVES = [
    (("released",), "Released", "Finished, polished, and still getting updates.", "lg"),
    (("playable",), "Early access", "Playable and growing. Updates land often.", "md"),
    (("playtest",), "In playtest", "Playable start to finish, with rough edges.", "md"),
    (("prototype", "indev"), "Prototypes", "Small builds that test whether an idea is fun.", "sm"),
]
PROMISES = [
    ("Free in your browser", "Every game is free to play in your browser."),
    ("Public code", "Every repo is public."),
    ("Honest about AI", "I'll always say what the AI did."),
    ("Patch notes", "Every update gets patch notes."),
    ("A reply", "If you leave feedback, you get a reply."),
]
# What counts as which tool on the "How it's made" page: label, then words to look for in madeWith.
TOOLBOX = [
    ("TypeScript", ("TypeScript",)),
    ("Canvas 2D or WebGL, no engine", ("no engine",)),
    ("Three.js", ("Three.js",)),
    ("PixelLab pixel art", ("PixelLab",)),
    ("Models built by Blender scripts", ("Blender",)),
    ("Synthesized sound", ("synthesized",)),
]


# ---------------------------------------------------------------- GitHub (the receipts)

def gh_get(path, token):
    req = urllib.request.Request("https://api.github.com" + path,
                                 headers={"User-Agent": "ycgnem-site-build", "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r), r.headers.get("Link", "")


def fetch_github():
    """Per game: created, last push, commit count and newest commit.  Best effort: the build works
    offline, and a local build reuses .cache/github.json for an hour to stay under the API limit."""
    cache = ROOT / ".cache/github.json"
    old = json.loads(cache.read_text(encoding="utf8")) if cache.exists() else {}
    if old and time.time() - old.get("_at", 0) < 3600 and not os.environ.get("CI"):
        return old
    token = os.environ.get("GITHUB_TOKEN")
    try:
        repos, _ = gh_get("/users/ycgNem/repos?per_page=100", token)
    except Exception:
        return old
    by_name = {r["name"]: r for r in repos}
    out = {}
    for g in GAMES:
        r = by_name.get(g.get("repo"))
        if not r:
            continue
        m = {"created": r["created_at"][:10], "pushed": r["pushed_at"][:10]}
        try:
            commits, link = gh_get(f"/repos/ycgNem/{g['repo']}/commits?per_page=1", token)
            last = re.search(r'[?&]page=(\d+)>; rel="last"', link)
            m["commits"] = int(last.group(1)) if last else len(commits)
            c = commits[0]
            m["last"] = {"msg": c["commit"]["message"].splitlines()[0],
                         "date": c["commit"]["committer"]["date"][:10], "url": c["html_url"]}
        except Exception:
            pass
        out[g["id"]] = m
    out["_at"] = time.time()
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(out), encoding="utf8")
    return out


GH = fetch_github()


def meta(g):
    return GH.get(g["id"], {})


def updated(g):
    """ISO date of the game's newest commit, or None when GitHub couldn't be reached."""
    m = meta(g)
    return m.get("last", {}).get("date") or m.get("pushed")


# ---------------------------------------------------------------- helpers

def nice_date(iso, year=True):
    d = date.fromisoformat(iso)
    return d.strftime("%b ") + str(d.day) + (d.strftime(", %Y") if year else "")


def time_tag(iso, cls="", rel=True):
    """A date the site script may rewrite as "3 days ago" (the full date stays in the tooltip)."""
    return (f'<time{f" class={chr(34)}{cls}{chr(34)}" if cls else ""} datetime="{iso}"{" data-rel" if rel else ""}>'
            f'{nice_date(iso)}</time>')


def inline_md(s):
    s = e(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" loading="lazy">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def md_list(items):
    """items: [indent, tag, text].  Deeper indents nest inside the item above them."""
    out, i = [], 0
    base, tag = items[0][0], items[0][1]
    while i < len(items):
        text = inline_md(items[i][2])
        j = i + 1
        while j < len(items) and items[j][0] > base:
            j += 1
        out.append(f"<li>{text}{md_list(items[i + 1:j]) if j > i + 1 else ''}</li>")
        i = j
    return f"<{tag}>{''.join(out)}</{tag}>"


def md(text):
    """Small Markdown subset: headings, paragraphs, nested lists, quotes, images, links, bold, code."""
    out, para, lst = [], [], []

    def flush():
        nonlocal para, lst
        if para:
            joined = " ".join(para)
            if re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", joined.strip()):
                alt, src = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", joined.strip()).groups()
                out.append(f'<figure><a href="{e(src)}" data-zoom><img src="{e(src)}" alt="{e(alt)}" loading="lazy"></a>'
                           f'<figcaption>{e(alt, quote=False)}</figcaption></figure>')
            else:
                out.append(f"<p>{inline_md(joined)}</p>")
            para = []
        if lst:
            out.append(md_list(lst))
            lst = []

    for line in text.splitlines():
        s = line.rstrip()
        if not s.strip():
            flush(); continue
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if m:
            flush(); n = len(m.group(1)) + 1
            out.append(f"<h{n}>{inline_md(m.group(2))}</h{n}>"); continue
        m = re.match(r"(\s*)([-*]|\d+\.)\s+(.*)", s)
        if m:
            if para: flush()
            lst.append([len(m.group(1)), "ol" if m.group(2)[0].isdigit() else "ul", m.group(3)]); continue
        if s.startswith(">"):
            flush(); out.append(f"<blockquote>{inline_md(s[1:].strip())}</blockquote>"); continue
        if lst:
            lst[-1][2] += " " + s.strip(); continue
        para.append(s.strip())
    flush()
    return "\n".join(out)


def load_posts():
    posts = []
    for f in sorted((ROOT / "content/devlog").glob("*.md"), reverse=True):
        raw = f.read_text(encoding="utf8")
        m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
        info = {}
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip().strip('"')
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", f.stem)
        words = len(re.findall(r"\w+", m.group(2)))
        posts.append({**info, "slug": slug, "body": md(m.group(2)), "mins": max(1, round(words / 220))})
    posts.sort(key=lambda p: (p["date"], p.get("time", "")), reverse=True)
    return posts


def game_by_id(gid):
    return next((g for g in GAMES if g["id"] == gid), None)


def ver(g):
    v = g["version"]
    return e(f"v{v}" if v[:1].isdigit() else v)


def chip(status):
    return f'<span class="chip st-{status}">{STATUS[status]}</span>'


def badge(g):
    """NEW for three weeks after a repo appears, UPDATED for ten days after a push."""
    m, up = meta(g), updated(g)
    if m.get("created") and (TODAY - date.fromisoformat(m["created"])).days <= 21:
        return '<span class="tag tag-new">New</span>'
    if up and (TODAY - date.fromisoformat(up)).days <= 10:
        return '<span class="tag tag-upd">Updated</span>'
    return ""


def accent(g):
    return f' style="--a:{e(g["accent"])}"' if g.get("accent") else ""


def dim(g):
    return "3d" if "Three.js" in g["madeWith"] else "2d"


def keys_html(value):
    """Controls as keycaps when every part is short ("WASD / Shift"); long phrases stay plain text."""
    parts = re.split(r"( / | or |, )", value)
    if any(len(p) > 13 for p in parts[::2]):
        return e(value)
    return "".join(f"<kbd>{e(p)}</kbd>" if i % 2 == 0 else f'<span class="sep">{e(p.strip())}</span>'
                   for i, p in enumerate(parts))


def socials_html(cls="socials"):
    links = [f'<a href="{e(u)}" rel="me noopener">{SOCIAL_NAMES[k]}</a>'
             for k, u in SITE["socials"].items() if u]
    return f'<div class="{cls}">' + "".join(links) + "</div>"


# ---------------------------------------------------------------- page shell

def layout(path, title, desc, body, image="/assets/brand/og-image.png", kind="website", page="page"):
    full_title = f"{title} · ycgNem" if title != "ycgNem" else "ycgNem — free browser games, built in the open"
    nav = [("/#cabinet", "Games"), ("/devlog/", "Devlog"), ("/about/", "How it's made"), ("/community/", "Community")]
    nav_html = "".join(
        f'<a href="{h}"{" aria-current=\"page\"" if path.startswith(h) or (h == "/#cabinet" and path.startswith("/games/")) else ""}>{t}</a>'
        for h, t in nav)
    discord = SITE["socials"].get("discord")
    foot_social = "".join(f'<a href="{e(u)}" rel="me noopener">{SOCIAL_NAMES[k]}</a>'
                          for k, u in SITE["socials"].items() if u)
    img_abs = image if image.startswith("http") else BASE + image
    boot = ('<div class="boot" aria-hidden="true"><img src="/assets/brand/ycgnem-icon.svg" alt="" width="64" height="64">'
            '<p class="boot-word">ycgNem<i></i></p><p class="boot-sub">Free play</p></div>') if page == "home" else ""
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
<script>(function(d,s){{d.classList.add("js");try{{if(s.getItem("ycg.boot"))d.classList.add("booted");else s.setItem("ycg.boot","1")}}catch(_){{d.classList.add("booted")}}}})(document.documentElement,sessionStorage)</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/assets/css/site.css">
</head>
<body class="p-{page}">
<a class="skip" href="#main">Skip to content</a>
{boot}
<header class="top">
  <div class="wrap top-in">
    <a class="logo" href="/" aria-label="ycgNem home"><img src="/assets/brand/ycgnem-lockup.svg" alt="ycgNem" width="120" height="32"></a>
    <nav class="nav" aria-label="Main">{nav_html}</nav>
    <button class="find" type="button" data-palette-open aria-label="Search games and posts">{PROMPT}<span class="find-t">Find a game</span><kbd>/</kbd></button>
    {f'<a class="btn btn-primary btn-sm top-cta" href="{e(discord)}">Join the Discord</a>' if discord else ""}
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="foot">
  <div class="wrap foot-in">
    <div class="foot-brand">
      <img src="/assets/brand/ycgnem-lockup.svg" alt="ycgNem" width="180" height="48">
      <p class="foot-tag">{e(SITE["tagline"])}</p>
      <p class="freeplay">Free play</p>
    </div>
    <nav class="foot-nav" aria-label="Footer">
      <div><h2>Play</h2><a href="/#cabinet">All {len(GAMES)} games</a><a href="/games/" data-random>Surprise me</a></div>
      <div><h2>Read</h2><a href="/devlog/">Devlog</a><a href="/about/">How it's made</a><a href="/feed.xml">RSS</a></div>
      <div><h2>Follow</h2><a href="/community/">Community</a>{foot_social}</div>
    </nav>
    <p class="foot-legal">Built with Claude. Free games, public code, no ads, no trackers. © <span data-year>{TODAY.year}</span> ycgNem</p>
  </div>
</footer>
<dialog class="palette" data-palette aria-label="Search games and posts">
  <form method="dialog" class="palette-in">
    <label class="palette-bar">{PROMPT}<input type="text" data-palette-input placeholder="Type a game, a genre or a post" autocomplete="off" spellcheck="false" aria-label="Search"><kbd>Esc</kbd></label>
    <ul class="palette-list" data-palette-list role="listbox"></ul>
    <p class="palette-help"><kbd>↑</kbd><kbd>↓</kbd> move <kbd>Enter</kbd> open <kbd>/</kbd> search from anywhere</p>
  </form>
</dialog>
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


# ---------------------------------------------------------------- components

def gcard(g, size="md"):
    """One game in the cabinet.  size: lg (wide feature), md, sm."""
    up = updated(g)
    img = "cover.webp" if size == "lg" else "cover-640.webp"
    dims = 'width="1280" height="720"' if size == "lg" else 'width="640" height="360"'
    text = e(f"{g['title']} {g['genre']} {g['pitch']} {STATUS[g['status']]} {dim(g)}".lower())
    soon = "" if g["play"] else '<span class="gcard-soon">Not playable online yet</span>'
    return f"""<a class="gcard gcard-{size}" href="/games/{g['id']}/" data-id="{g['id']}" data-status="{g['status']}" data-dim="{dim(g)}" data-updated="{up or ''}" data-text="{text}"{accent(g)}>
  <span class="gcard-art"><img src="/assets/games/{g['id']}/{img}" alt="{e(g['title'])} screenshot" {dims} loading="lazy">{badge(g)}</span>
  <span class="gcard-body">
    <span class="gcard-top"><b class="gcard-title">{e(g['title'])}</b><span class="ver st-{g['status']}">{ver(g)}</span></span>
    <span class="gcard-genre">{e(g['genre'])}{f'<span class="gcard-upd"> · {time_tag(up)}</span>' if up else ''}</span>
    <span class="gcard-pitch">{e(g['pitch'])}</span>
    <span class="stat">{e(g['number'])}</span>{soon}
  </span>
</a>"""


def shelves():
    out = []
    for statuses, title, blurb, size in SHELVES:
        games = [g for g in GAMES if g["status"] in statuses]
        if not games:
            continue
        out.append(f"""<section class="shelf" data-shelf>
  <header class="shelf-head"><h3>{title}</h3><span class="shelf-n" data-shelf-n>{len(games):02d}</span><p>{blurb}</p></header>
  <div class="shelf-grid shelf-{size}">{"".join(gcard(g, size) for g in games)}</div>
</section>""")
    return "".join(out)


def cabinet(heading="h2"):
    groups = [("all", "All"), ("released", "Released"), ("playtest", "Playtest"), ("prototype", "Prototypes")]
    status_btns = "".join(f'<button type="button" data-status="{k}"{" aria-pressed=\"true\"" if k == "all" else " aria-pressed=\"false\""}>{t}</button>'
                          for k, t in groups)
    return f"""<section class="cab band" id="cabinet" data-cab>
  <div class="wrap">
    <header class="cab-head">
      <div><p class="eyebrow">The cabinet</p><{heading}>Every game, free in your browser</{heading}></div>
      <p class="cab-count"><b data-cab-count>{len(GAMES)}</b> of {len(GAMES)} games</p>
    </header>
    <div class="cab-tools" data-cab-tools>
      <div class="seg" role="group" aria-label="Filter by status">{status_btns}</div>
      <div class="seg" role="group" aria-label="Filter by look"><button type="button" data-dim="2d" aria-pressed="false">2D</button><button type="button" data-dim="3d" aria-pressed="false">3D</button></div>
      <label class="cab-search">{PROMPT}<input type="search" data-cab-search placeholder="filter: factory, cozy, roguelite" aria-label="Filter games"></label>
      <div class="seg" role="group" aria-label="Order"><button type="button" data-order="shelves" aria-pressed="true">Shelves</button><button type="button" data-order="latest" aria-pressed="false">Latest</button></div>
      <button class="btn btn-ghost btn-sm" type="button" data-random>Surprise me</button>
    </div>
    <div class="shelves" data-shelves>{shelves()}</div>
    <div class="shelf-grid shelf-md cab-flat" data-flat hidden></div>
    <p class="cab-empty" data-cab-empty hidden>No game matches that. <button type="button" class="link" data-cab-clear>Clear the filters</button></p>
    <p class="cab-note">Best on a computer with a keyboard and mouse.</p>
  </div>
</section>"""


def hero():
    """The attract screen: up to five spotlight games from site.json.  Works without the script
    (first slide shows, tabs are links); the script cycles it."""
    items = [(s, game_by_id(s["game"])) for s in SITE.get("spotlight", [])][:5]
    amb = "".join(f'<img src="/assets/games/{g["id"]}/cover-640.webp" alt="" data-i="{i}"{" class=\"on\"" if i == 0 else " loading=\"lazy\""}>'
                  for i, (s, g) in enumerate(items))
    panels = "".join(f"""<article class="hero-panel{" on" if i == 0 else ""}" data-i="{i}"{accent(g)}>
        <p class="hero-meta">{chip(g['status'])}<span class="ver">{ver(g)}</span><span class="kicker">{e(s['kicker'])}</span></p>
        <h2>{e(g['title'])}</h2>
        <p class="hero-pitch">{e(g['pitch'])}</p>
        <p class="stat">{e(g['number'])}</p>
        <p class="hero-actions">
          <a class="btn btn-primary" href="/games/{g['id']}/#play">{PLAY_ICON}Play free</a>
          <a class="btn btn-ghost" href="{e(s['link'])}">What's new</a>
        </p>
      </article>""" for i, (s, g) in enumerate(items))
    shots = "".join(f'<img src="{e(s["image"])}" alt="{e(g["title"])} screenshot" width="1280" height="720" data-i="{i}"'
                    f'{" class=\"on\" fetchpriority=\"high\"" if i == 0 else " loading=\"lazy\""}>' for i, (s, g) in enumerate(items))
    tabs = "".join(f"""<a class="hero-tab{" on" if i == 0 else ""}" href="/games/{g['id']}/" data-i="{i}"{accent(g)}>
        <span class="hero-tab-n">{i + 1}</span>
        <span class="hero-tab-t"><b>{e(g['title'])}</b><span>{e(s['short'])}</span></span>
        <i class="hero-tab-bar"></i>
      </a>""" for i, (s, g) in enumerate(items))
    return f"""<section class="hero" data-hero aria-label="Now showing">
  <div class="hero-amb" aria-hidden="true">{amb}</div>
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow hero-eyebrow">Now showing</p>
      {panels}
    </div>
    <div class="hero-screen">
      <div class="screen" data-screen>{shots}<span class="scan" aria-hidden="true"></span></div>
      <p class="screen-bar" aria-hidden="true"><span data-hero-ch>CH 1</span><span class="freeplay">Free play</span></p>
    </div>
  </div>
  <div class="wrap"><nav class="hero-tabs" aria-label="Spotlight games" style="--n:{len(items)}">{tabs}</nav></div>
</section>"""


def stats_strip():
    playable = sum(1 for g in GAMES if g["play"])
    commits = sum(meta(g).get("commits", 0) for g in GAMES)
    ups = [u for u in (updated(g) for g in GAMES) if u]
    nums = [(str(len(GAMES)), "games, all playable" if playable == len(GAMES) else f"games, {playable} playable now")]
    if commits:
        nums.append((f"{commits:,}", "commits, all public"))
    nums.append(("0", "ads, accounts or downloads"))
    if ups:
        nums.append((nice_date(max(ups), year=False), "latest update"))
    return f"""<section class="strip">
  <div class="wrap strip-in">
    <h1>Free browser games, built with AI, <em>shown in the open.</em></h1>
    <ul class="nums">{"".join(f'<li><b>{a}</b><span>{b}</span></li>' for a, b in nums)}</ul>
  </div>
</section>"""


def log_panel():
    """The newest commit from each game: the raw record next to the written devlog."""
    rows = sorted(((meta(g)["last"], g) for g in GAMES if meta(g).get("last")), key=lambda x: x[0]["date"], reverse=True)[:8]
    if not rows:
        return ""
    commits = sum(meta(g).get("commits", 0) for g in GAMES)
    lines = "".join(f"""<a class="log-row" href="{e(c['url'])}" rel="noopener"{accent(g)}>
      {time_tag(c['date'], rel=False).replace(', ' + c['date'][:4], '')}<b>{e(g['title'])}</b><span>{e(c['msg'])}</span></a>""" for c, g in rows)
    return f"""<div class="term">
    <p class="term-bar">{PROMPT}<span>git log --all --oneline</span><span class="term-live">rebuilt daily</span></p>
    <div class="term-body">{lines}</div>
    <p class="term-foot"><b>{commits:,}</b> commits across <b>{len(GAMES)}</b> public repos. <a href="{e(SITE['socials']['github'])}">Read any of them</a></p>
  </div>"""


def post_card(p, big=False):
    g = game_by_id(p.get("game"))
    return f"""<a class="pcard{" pcard-big" if big else ""}" href="/devlog/{p['slug']}/">
  <span class="pcard-art"><img src="{e(p['cover'])}" alt="" loading="lazy"></span>
  <span class="pcard-body">
    <span class="pcard-meta">{time_tag(p['date'])}{f'<span>{e(g["title"])}</span>' if g else ''}<span>{p['mins']} min read</span></span>
    <b class="pcard-title">{e(p['title'])}</b>
    <span class="pcard-sum">{e(p['summary'])}</span>
  </span>
</a>"""


def promises():
    return ('<ol class="promises">' + "".join(
        f'<li><span class="promise-n">{i}</span><b>{e(t)}</b><span>{e(d)}</span></li>' for i, (t, d) in enumerate(PROMISES, 1))
        + "</ol>")


def join_band():
    discord = SITE["socials"].get("discord")
    join = [f'<a class="btn btn-primary" href="{e(discord)}">Join the Discord</a>' if discord
            else '<span class="btn btn-ghost" aria-disabled="true">Discord opens soon</span>']
    join += [f'<a class="btn btn-ghost" href="{e(u)}" rel="me noopener">Follow on {SOCIAL_NAMES[k]}</a>'
             for k, u in SITE["socials"].items() if u and k != "discord"]
    join.append('<a class="btn btn-ghost" href="/feed.xml">RSS feed</a>')
    return f"""<section class="band">
  <div class="wrap">
    <div class="join">
      <div class="join-copy">
        <p class="freeplay">Free play · built in the open</p>
        <h2>Playtest with me</h2>
        <p>New builds land in the Discord first. Vote on what gets built next, and get your name in the credits of the games you shaped. Every repo is public and every update gets patch notes.</p>
      </div>
      <div class="join-actions">{"".join(join)}</div>
    </div>
  </div>
</section>"""


# ---------------------------------------------------------------- pages

def page_index(posts):
    body = f"""
{hero()}
{stats_strip()}
<section class="recent band" data-recent hidden>
  <div class="wrap">
    <header class="band-head"><div><p class="eyebrow">Saved on this device only</p><h2>Jump back in</h2></div>
      <button type="button" class="link" data-recent-clear>Forget these</button></header>
    <div class="shelf-grid shelf-md" data-recent-list></div>
  </div>
</section>
{cabinet()}
<section class="band workshop">
  <div class="wrap">
    <header class="band-head">
      <div><p class="eyebrow">The workshop</p><h2>What shipped lately</h2>
        <p class="band-sub">The devlog says what changed and why. The commit log is the proof.</p></div>
      <a class="btn btn-ghost btn-sm" href="/devlog/">All posts</a>
    </header>
    <div class="workshop-grid">
      <div class="pcards">{post_card(posts[0], True) if posts else ""}</div>
      <div class="workshop-side">{log_panel()}<div class="pcards">{"".join(post_card(p) for p in posts[1:3])}</div></div>
    </div>
  </div>
</section>
<section class="band deal">
  <div class="wrap">
    <header class="band-head">
      <div><p class="eyebrow">The deal</p><h2>Five promises</h2>
        <p class="band-sub">I make these with AI and I won't hide it. Here's what you get in return.</p></div>
      <a class="btn btn-ghost btn-sm" href="/about/">How it's made</a>
    </header>
    {promises()}
  </div>
</section>
{join_band()}
"""
    return layout("/", "ycgNem", SITE["description"], body, page="home")


def page_games():
    body = f"""{cabinet("h1")}"""
    return layout("/games/", "Games", f"All {len(GAMES)} ycgNem games, free to play in your browser.", body, page="games")


def page_game(g, posts):
    i = GAMES.index(g)
    prev_g, next_g = GAMES[i - 1], GAMES[(i + 1) % len(GAMES)]
    same = [o for o in GAMES[i + 1:] + GAMES[:i] if o["status"] == g["status"] and o not in (prev_g, next_g)]
    rest = [o for o in GAMES[i + 1:] + GAMES[:i] if o not in same and o not in (prev_g, next_g)]
    more = (same + rest)[:4]
    shots = sorted((p.name for p in (ROOT / f"assets/games/{g['id']}").glob("shot*.webp")),
                   key=lambda n: int(re.sub(r"\D", "", n)))
    gallery = "".join(f'<a href="/assets/games/{g["id"]}/{s}" data-zoom><img src="/assets/games/{g["id"]}/{s}" alt="{e(g["title"])} screenshot {n}" loading="lazy" width="1280" height="720"></a>'
                      for n, s in enumerate(shots, 1))
    m, up = meta(g), updated(g)
    repo = f"https://github.com/ycgNem/{g['repo']}"
    if g["play"]:
        player = f"""<div class="cabinet-frame">
      <div class="player" data-player="{e(g['play'])}" data-title="{e(g['title'])}" data-id="{g['id']}" id="play">
        <img class="poster" src="/assets/games/{g['id']}/cover.webp" alt="" width="1280" height="720" fetchpriority="high">
        <span class="scan" aria-hidden="true"></span>
        <button class="start" type="button"><span class="press">{PLAY_ICON} Press start</span><span class="hint">Loads the game right here. {e(g['session'])}.</span></button>
      </div>
      <div class="player-bar">
        <button class="btn btn-primary btn-sm" type="button" data-fullscreen>Fullscreen</button>
        <button class="btn btn-ghost btn-sm" type="button" data-theater aria-pressed="false">Theater mode</button>
        <button class="btn btn-ghost btn-sm" type="button" data-restart hidden>Restart</button>
        <a class="btn btn-ghost btn-sm" href="{e(g['play'])}" target="_blank" rel="noopener">Open in its own tab</a>
        <span class="freeplay">Free play</span>
      </div>
    </div>
    <p class="mobile-note">These games are built for a keyboard and mouse. On a phone, save the link and play on a computer.</p>"""
    else:
        player = f"""<div class="cabinet-frame"><div class="player"><img class="poster" src="/assets/games/{g['id']}/cover.webp" alt="" width="1280" height="720">
      <div class="start" style="cursor:default"><span class="press">In development</span><span class="hint">Not playable online yet. Follow the devlog for the first build.</span></div></div></div>"""
    keys = "".join(f"<tr><th scope=\"row\">{e(a)}</th><td>{keys_html(b)}</td></tr>" for a, b in g["controls"])
    facts = [("Status", f"{STATUS[g['status']]} · <span class=\"mono\">{ver(g)}</span>"),
             ("Session", e(g["session"])), ("Plays on", e(g["platforms"]))]
    if up:
        facts.append(("Updated", time_tag(up, "mono")))
    if m.get("commits"):
        facts.append(("Commits", f'<a class="mono" href="{repo}/commits">{m["commits"]:,}</a>'))
    facts.append(("Price", "Free"))
    last = m.get("last")
    related = [p for p in posts if p.get("game") == g["id"]]
    links = [(repo, "Source code"), (f"{repo}/issues/new", "Report a bug")]
    if g.get("notesUrl"):
        links.insert(1, (g["notesUrl"], f"Read the {g['notes']}"))
    body = f"""
<div class="ghead"{accent(g)}>
  <div class="ghead-amb" aria-hidden="true"><img src="/assets/games/{g['id']}/cover-640.webp" alt=""></div>
  <div class="wrap">
    <p class="crumbs"><a href="/#cabinet">The cabinet</a> / {e(g['title'])}</p>
    <div class="ghead-row">
      <div>
        <h1>{e(g['title'])}</h1>
        <p class="ghead-meta">{chip(g['status'])}<span class="ver">{ver(g)}</span><span>{e(g['genre'])}</span>{badge(g)}</p>
      </div>
      <p class="stat">{e(g['number'])}</p>
    </div>
    {player}
  </div>
</div>
<div class="wrap">
  <div class="game-body">
    <div class="prose">
      <p class="lede">{e(g['pitch'])}</p>
      {"".join(f"<p>{e(p)}</p>" for p in g['about'])}
      {f'<h2>Screenshots</h2><div class="gallery">{gallery}</div>' if gallery else ""}
      {('<h2>From the devlog</h2><div class="pcards pcards-row">' + "".join(post_card(p) for p in related[:4]) + '</div>') if related else ""}
    </div>
    <aside class="side">
      <div class="panel facts">
        <dl>{"".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)}</dl>
      </div>
      {f'<div class="panel"><h2 class="panel-h">Controls</h2><table class="keys">{keys}</table></div>' if keys else ""}
      <div class="panel">
        <h2 class="panel-h">How it's made</h2>
        <p class="made">{e(g['madeWith'])}</p>
        {f'<a class="last-commit" href="{e(last["url"])}" rel="noopener">{PROMPT}<span>{e(last["msg"])}</span>{time_tag(last["date"])}</a>' if last else ""}
        <p class="side-links">{"".join(f'<a href="{e(h)}" rel="noopener">{e(t)}</a>' for h, t in links)}</p>
      </div>
    </aside>
  </div>
  <nav class="pager" aria-label="More games">
    <a class="pager-prev" href="/games/{prev_g['id']}/"><span>Previous</span><b>{e(prev_g['title'])}</b></a>
    <a class="pager-all" href="/#cabinet">The cabinet</a>
    <a class="pager-next" href="/games/{next_g['id']}/"><span>Next</span><b>{e(next_g['title'])}</b></a>
  </nav>
  <section class="comments" id="comments">
    <h2>Comments</h2>
    <p class="muted">What would you change? I read and reply to everything.</p>
    {giscus("game:" + g["id"])}
  </section>
  <section class="band more">
    <header class="band-head"><div><p class="eyebrow">Keep playing</p><h2>More from the cabinet</h2></div></header>
    <div class="shelf-grid shelf-md">{"".join(gcard(o, "md") for o in more)}</div>
  </section>
</div>"""
    return layout(f"/games/{g['id']}/", g["title"], g["pitch"], body, f"/assets/games/{g['id']}/cover.webp", "game", page="game")


def page_devlog(posts):
    groups, out = {}, []
    for p in posts[1:]:
        groups.setdefault(p["date"][:7], []).append(p)
    for ym, items in groups.items():
        label = date.fromisoformat(ym + "-01").strftime("%B %Y")
        out.append(f'<section class="month"><h2><span>{label}</span><i>{len(items):02d}</i></h2>'
                   f'<div class="pcards pcards-list">{"".join(post_card(p) for p in items)}</div></section>')
    body = f"""
<div class="wrap">
  <header class="page-head"><p class="eyebrow">Devlog</p><h1>What I'm building</h1>
  <p class="lede">Releases, patch notes in plain words, and how things got made. Also on <a href="/feed.xml">RSS</a>.</p></header>
  <div class="pcards devlog-top">{post_card(posts[0], True) if posts else ""}</div>
  <div class="months">{"".join(out)}</div>
</div>"""
    return layout("/devlog/", "Devlog", "Releases, patch notes and how the games get made.", body, page="devlog")


def page_post(p, posts):
    game = game_by_id(p.get("game"))
    i = posts.index(p)
    newer = posts[i - 1] if i > 0 else None
    older = posts[i + 1] if i + 1 < len(posts) else None
    cta = (f'<aside class="post-cta"{accent(game)}><img src="/assets/games/{game["id"]}/cover-640.webp" alt="" width="640" height="360" loading="lazy">'
           f'<div><p class="eyebrow">Play it</p><b>{e(game["title"])}</b><p>{e(game["pitch"])}</p>'
           f'<a class="btn btn-primary btn-sm" href="/games/{game["id"]}/#play">{PLAY_ICON}Play free</a></div></aside>'
           if game and game["play"] else "")
    pager = "".join([
        f'<a class="pager-prev" href="/devlog/{older["slug"]}/"><span>Older</span><b>{e(older["title"])}</b></a>' if older else "<span></span>",
        '<a class="pager-all" href="/devlog/">All posts</a>',
        f'<a class="pager-next" href="/devlog/{newer["slug"]}/"><span>Newer</span><b>{e(newer["title"])}</b></a>' if newer else "<span></span>"])
    body = f"""
<div class="wrap post">
  <header class="page-head">
    <p class="crumbs"><a href="/devlog/">Devlog</a></p>
    <h1>{e(p['title'])}</h1>
    <p class="post-meta">{time_tag(p['date'], rel=False)}<span>{p['mins']} min read</span></p>
    <p class="lede">{e(p['summary'])}</p>
  </header>
  <img class="post-cover" src="{e(p['cover'])}" alt="" width="1280" height="720">
  <article class="post-body prose">{p['body']}</article>
  {cta}
  <nav class="pager" aria-label="More posts">{pager}</nav>
  <section class="comments">{giscus("post:" + p["slug"])}</section>
</div>"""
    return layout(f"/devlog/{p['slug']}/", p["title"], p["summary"], body, p["cover"], "article", page="post")


def page_about():
    commits = sum(meta(g).get("commits", 0) for g in GAMES)
    tools = "".join(
        f'<li><b>{n}</b><span>{e(label)}</span><i style="--w:{n / len(GAMES):.3f}"></i></li>'
        for label, words in TOOLBOX
        for n in [sum(1 for g in GAMES if any(w in g["madeWith"] for w in words))] if n)
    receipts = [(str(len(GAMES)), "public repos")]
    if commits:
        receipts.append((f"{commits:,}", "commits you can read"))
    receipts.append((str(sum(1 for g in GAMES if g.get("notesUrl"))), "games with patch notes or a roadmap"))
    body = f"""
<div class="wrap">
  <header class="page-head">
    <p class="eyebrow">How it's made</p>
    <h1>A gamer, with AI on the crew</h1>
    <p class="lede">I'm ycgNem. I've played games my whole life, and this year I started making them. I build with AI and I'm not going to hide that. Here's what it actually means.</p>
  </header>
  <section class="band about-who">
    <div class="split">
      <div class="panel"><p class="panel-n">01</p><h2>I decide what the game is</h2><p>Every game starts as a design doc: the loop, the numbers, what should feel good. I write what I want and why.</p></div>
      <div class="panel"><p class="panel-n">02</p><h2>Claude writes most of the code</h2><p>It works in milestones from those docs. I play every build, decide what stays, and send it back when something feels wrong.</p></div>
      <div class="panel"><p class="panel-n">03</p><h2>Art is a mix</h2><p>Some sprites come from PixelLab, an AI pixel-art tool. Some are drawn pixel by pixel by Claude in a script. The 3D games use models built by Blender scripts. Each game page says which.</p></div>
      <div class="panel"><p class="panel-n">04</p><h2>The numbers are mine to own</h2><p>If a tower does 6 kJ/s, that number is on screen, and I can tell you why it's that number.</p></div>
    </div>
  </section>
  <section class="band">
    <header class="band-head"><div><p class="eyebrow">The deal</p><h2>Five promises</h2></div></header>
    {promises()}
  </section>
  <section class="band">
    <header class="band-head"><div><p class="eyebrow">The toolbox</p><h2>What the {len(GAMES)} games are built with</h2>
      <p class="band-sub">Counted from each game's own "How it's made" line.</p></div></header>
    <ul class="toolbox">{tools}</ul>
  </section>
  <section class="band">
    <header class="band-head"><div><p class="eyebrow">The receipts</p><h2>You can check all of it</h2>
      <p class="band-sub">Every game's source is public, design docs and decision logs included.</p></div>
      <a class="btn btn-primary btn-sm" href="{e(SITE['socials']['github'])}">Open GitHub</a></header>
    <ul class="nums nums-wide">{"".join(f'<li><b>{a}</b><span>{b}</span></li>' for a, b in receipts)}</ul>
    {log_panel()}
  </section>
</div>
{join_band()}"""
    return layout("/about/", "How it's made", "How ycgNem builds games with AI: who does what, five promises, and the receipts.", body, page="about")


def page_community():
    discord = SITE["socials"].get("discord")
    discord_btn = (f'<a class="btn btn-primary" href="{e(discord)}">Join the Discord</a>' if discord
                   else '<span class="btn btn-ghost" aria-disabled="true">Discord opens soon</span>')
    body = f"""
<div class="wrap">
  <header class="page-head">
    <p class="eyebrow">Community</p>
    <h1>Help shape the games</h1>
    <p class="lede">The games get better when people play them and tell me the truth. Here's where that happens.</p>
  </header>
  <section class="band">
    <div class="split">
      <div class="panel panel-hot">
        <p class="freeplay">Home base</p>
        <h2>The Discord</h2>
        <p>New builds drop here first, with a playtest channel for each game, a place to share runs and builds, and polls on what gets made next.</p>
        <p>{discord_btn}</p>
      </div>
      <div class="panel">
        <h2>Everywhere else</h2>
        {socials_html()}
        <p>RSS: <a href="/feed.xml">{BASE}/feed.xml</a></p>
      </div>
    </div>
  </section>
  <section class="band">
    <div class="split">
      <div class="panel">
        <h2>Good feedback looks like</h2>
        <ul>
          <li>What happened and when ("wave 4, when the Shades cut my Node")</li>
          <li>What you expected instead</li>
          <li>Bugs: what you did, what happened, your browser</li>
        </ul>
      </div>
      <div class="panel">
        <h2>House rules</h2>
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
    <header class="band-head"><div><p class="eyebrow">Credits</p><h2>Your name in the game</h2>
    <p class="band-sub">Playtesters whose feedback changes a game get their name in that game's credits. First names on the list go here soon.</p></div></header>
  </section>
</div>"""
    return layout("/community/", "Community", "Playtest ycgNem's games, give feedback, and follow along.", body, page="community")


def page_404():
    body = """<div class="wrap over" data-over>
  <p class="eyebrow">404</p>
  <h1>Game over</h1>
  <p class="lede">That page isn't here.</p>
  <p class="over-count">Continue? <b data-over-n>9</b></p>
  <p class="over-actions"><a class="btn btn-primary" href="/">Continue</a><a class="btn btn-ghost" href="/games/" data-random>Surprise me</a></p>
</div>"""
    return layout("/404.html", "Not found", "Page not found.", body, page="over")


def feed(posts):
    items = "".join(f"""<item><title>{e(p['title'])}</title><link>{BASE}/devlog/{p['slug']}/</link>
<guid>{BASE}/devlog/{p['slug']}/</guid><pubDate>{datetime.fromisoformat(p['date']).replace(tzinfo=timezone.utc).strftime('%a, %d %b %Y 12:00:00 +0000')}</pubDate>
<description>{e(p['summary'])}</description></item>""" for p in posts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>ycgNem devlog</title><link>{BASE}/</link>
<description>{e(SITE['description'])}</description>{items}</channel></rss>
"""


def search_index(posts):
    """What the >_ palette searches.  k: g game, p post, l link."""
    rows = [{"k": "g", "t": g["title"], "s": f"{g['genre']} · {STATUS[g['status']]}", "u": f"/games/{g['id']}/",
             "i": f"/assets/games/{g['id']}/cover-640.webp", "x": g["pitch"], "play": bool(g["play"])} for g in GAMES]
    rows += [{"k": "p", "t": p["title"], "s": f"Devlog · {nice_date(p['date'])}", "u": f"/devlog/{p['slug']}/",
              "i": p["cover"], "x": p["summary"]} for p in posts]
    rows += [{"k": "l", "t": t, "s": s, "u": u, "x": ""} for t, s, u in [
        ("Devlog", "Every post", "/devlog/"), ("How it's made", "Who does what, and the receipts", "/about/"),
        ("Community", "Playtest and feedback", "/community/"), ("GitHub", "Every repo", SITE["socials"]["github"])]]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf8")


def main():
    if not (ROOT / "assets/js/site.js").exists():
        sys.exit("assets/js/site.js is missing. Run `npm install` once, then `npm run build:js` (or `npm run build`).")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "assets", OUT / "assets")
    posts = load_posts()
    write("index.html", page_index(posts))
    write("games/index.html", page_games())
    for g in GAMES:
        write(f"games/{g['id']}/index.html", page_game(g, posts))
    write("devlog/index.html", page_devlog(posts))
    for p in posts:
        write(f"devlog/{p['slug']}/index.html", page_post(p, posts))
    write("about/index.html", page_about())
    write("community/index.html", page_community())
    write("404.html", page_404())
    write("feed.xml", feed(posts))
    write("search.json", search_index(posts))
    urls = (["/", "/games/", "/devlog/", "/about/", "/community/"] + [f"/games/{g['id']}/" for g in GAMES]
            + [f"/devlog/{p['slug']}/" for p in posts])
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{BASE}{u}</loc></url>" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    write(".nojekyll", "")
    print(f"Built {len(urls)} pages into {OUT} ({len(GH) - 1 if GH else 0} repos read from GitHub)")


if __name__ == "__main__":
    main()

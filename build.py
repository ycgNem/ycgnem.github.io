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
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def socials_html(cls="socials"):
    links = [f'<a href="{e(u)}" rel="me noopener">{SOCIAL_NAMES[k]}</a>'
             for k, u in SITE["socials"].items() if u]
    return f'<div class="{cls}">' + "".join(links) + "</div>"


def chip(status):
    return f'<span class="chip st-{status}">{STATUS[status]}</span>'


def layout(path, title, desc, body, image="/assets/brand/og-image.png", kind="website"):
    full_title = f"{title} · ycgNem" if title != "ycgNem" else "ycgNem — free browser games, built in the open"
    nav = [("/#games", "Games"), ("/devlog/", "Devlog"), ("/how-i-build/", "How I build"), ("/community/", "Community")]
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
  <div class="wrap">
    <a class="logo" href="/" aria-label="ycgNem home"><img src="/assets/brand/ycgnem-lockup.svg" alt="ycgNem" width="113" height="30"></a>
    <nav class="nav" aria-label="Main">{nav_html}</nav>
    {cta}
  </div>
</header>
<main>
{body}
</main>
<footer class="site-foot">
  <div class="wrap">
    <img src="/assets/brand/ycgnem-wordmark.svg" alt="ycgNem" width="95" height="22">
    <nav aria-label="Footer">
      <a href="/devlog/">Devlog</a><a href="/how-i-build/">How I build</a><a href="/community/">Community</a>
      <a href="/feed.xml">RSS</a><a href="{e(SITE['socials']['github'])}">GitHub</a>
    </nav>
    <p>Free games, public code, no ads, no trackers. © <span data-year>{date.today().year}</span> ycgNem</p>
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

def card(g, updated):
    href = f"/games/{g['id']}/"
    play = (f'<a class="btn btn-primary btn-sm" href="{href}#play">{PLAY_ICON}Play</a>' if g["play"]
            else '<span class="btn btn-ghost btn-sm" aria-disabled="true">Coming soon</span>')
    upd = f' · updated {nice_date(updated[g["id"]])}' if g["id"] in updated else ""
    return f"""<article class="card">
  <a class="card-img" href="{href}" tabindex="-1"><img src="/assets/games/{g['id']}/cover-640.webp" alt="{e(g['title'])} screenshot" loading="lazy" width="640" height="360">{chip(g['status'])}</a>
  <div class="card-body">
    <div class="card-title"><h3><a href="{href}">{e(g['title'])}</a></h3><span class="ver">v{e(g['version'])}</span></div>
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


def page_index(posts, updated):
    playable = [g for g in GAMES if g["play"]]
    featured = next(g for g in GAMES if g.get("featured"))
    attract = "".join(
        f'<img src="/assets/games/{g["id"]}/cover.webp" alt="{e(g["title"])}" data-href="/games/{g["id"]}/" width="1280" height="720"{" loading=\"lazy\"" if i else ""}>'
        for i, g in enumerate(GAMES))
    discord = SITE["socials"].get("discord")
    discord_btn = (f'<a class="btn btn-primary" href="{e(discord)}">Join the Discord</a>' if discord
                   else '<span class="btn btn-ghost" aria-disabled="true">Discord opens soon</span>')
    workshop = "".join(f"""<a class="workshop" href="/games/{g['id']}/">
      <img src="/assets/games/{g['id']}/cover-640.webp" alt="{e(g['title'])} screenshot" width="640" height="360">
      <div><p class="eyebrow">In the workshop</p><h3>{e(g['title'])}</h3><p class="muted">{e(g['genre'])} · not playable online yet</p>
      <p>{e(g['pitch'])}</p></div></a>""" for g in GAMES if not g["play"])
    body = f"""
<section class="hero">
  <div class="wrap">
    <div class="hero-copy">
      <p class="eyebrow">Solo dev · {len(GAMES)} games · free in your browser</p>
      <h1>Play it now. See how it's made.</h1>
      <p class="lede">I'm ycgNem, a gamer making the games I want to play, with AI on the crew. Every game here is free in your browser. Every repo is public, every number is on screen, and I'll tell you exactly what the AI did.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="/games/{featured['id']}/#play">{PLAY_ICON}Play {e(featured['title'])}</a>
        <a class="btn btn-ghost" href="/how-i-build/">How I build with AI</a>
      </div>
      <ul class="proof">
        <li><b>{len(playable)}</b> playable now</li>
        <li><b>{len(GAMES)}</b> public repos</li>
        <li><b>0</b> ads, accounts or downloads</li>
      </ul>
    </div>
    <div class="cabinet">
      <div class="screen" data-attract role="link" aria-label="Game previews">{attract}</div>
      <div class="marquee"><span class="now" data-attract-label></span><span class="free-play">FREE PLAY</span></div>
    </div>
  </div>
</section>

<section class="band" id="games">
  <div class="wrap">
    <div class="band-head">
      <div><p class="eyebrow">The cabinet</p><h2>Every game, playable here</h2></div>
      <p class="muted">Best on a computer with a keyboard and mouse.</p>
    </div>
    <div class="grid">{"".join(card(g, updated) for g in playable)}</div>
    {workshop}
  </div>
</section>

<section class="band">
  <div class="wrap">
    <div class="band-head">
      <div><p class="eyebrow">Built in the open</p><h2>Who does what</h2></div>
      <a class="btn btn-ghost btn-sm" href="/how-i-build/">The full process</a>
    </div>
    <div class="open-grid">
      <div class="open-col me"><h3>What I do</h3><ul>
        <li>Decide what the game is and why it's fun</li>
        <li>Write the design docs: the loop, the numbers, the feel</li>
        <li>Play every build and say what stays</li>
        <li>Own every decision and every number</li></ul></div>
      <div class="open-col ai"><h3>What the AI does</h3><ul>
        <li>Claude Code writes most of the code, milestone by milestone</li>
        <li>PixelLab and Claude make much of the pixel art</li>
        <li>Runs the tests and balance sims I ask for</li>
        <li>Each game page lists exactly which tools it used</li></ul></div>
      <div class="open-col you"><h3>What you can check</h3><ul>
        <li>Every repo is public, design docs included</li>
        <li>Every update ships with patch notes</li>
        <li>Odds, damage and rates are shown in game</li>
        <li>Feedback gets a reply</li></ul></div>
    </div>
  </div>
</section>

<section class="band">
  <div class="wrap">
    <div class="band-head">
      <div><p class="eyebrow">Devlog</p><h2>What shipped lately</h2></div>
      <a class="btn btn-ghost btn-sm" href="/devlog/">All posts</a>
    </div>
    {post_rows(posts[:3])}
  </div>
</section>

<section class="band">
  <div class="wrap community">
    <div class="discord-card">
      <p class="eyebrow">Community</p>
      <h2>Playtest with me</h2>
      <p class="muted">New builds land in the Discord first. Tell me what you felt, vote on what gets built next, and get your name in the credits of the games you shaped.</p>
      <div>{discord_btn}</div>
    </div>
    <div style="display:grid;gap:16px">
      <h3>Follow along</h3>
      <p class="muted">Short clips of new builds, the numbers behind the design, and the honest version of how it got made.</p>
      {socials_html()}
      <p class="muted">Or subscribe to the <a href="/feed.xml">devlog RSS feed</a>.</p>
    </div>
  </div>
</section>
"""
    return layout("/", "ycgNem", SITE["description"], body)


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
        <div><dt>Status</dt><dd>{STATUS[g['status']]} · <span class="mono">v{e(g['version'])}</span></dd></div>
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


def page_how():
    body = """
<div class="wrap">
  <header class="post-head">
    <p class="eyebrow">How I build</p>
    <h1>Made with AI, shown in the open</h1>
    <p class="lede">A lot of people are tired of AI being used to fake effort. Fair. So here's exactly how my games get made, and how you can check every claim.</p>
  </header>

  <section class="band" style="padding-top:24px">
    <h2 style="margin-bottom:20px">The process</h2>
    <ol class="steps">
      <li><div><h3>A design doc first</h3><p>Every game starts as a written plan: what the player does every minute, what should feel good, and the math behind it. Damage, odds and rates are derived on paper before any code exists. The docs live in each repo.</p></div></li>
      <li><div><h3>Built in milestones</h3><p>Claude Code builds one milestone at a time from those docs: a foundation, a playable slice, then content. Each milestone has a gate it must pass before the next one starts.</p></div></li>
      <li><div><h3>I play it and decide</h3><p>I play every build. What stays, what gets cut and what feels wrong are my calls, and every big one is written down in the repo's DECISIONS.md with the reason.</p></div></li>
      <li><div><h3>Measured, not guessed</h3><p>Balance gets checked with simulations. Trotline's season was played by a reference strategy hundreds of times and resized when it won too often. Carpet Joint replays the night 500 times to show you the odds.</p></div></li>
      <li><div><h3>Shipped with notes</h3><p>Every update goes live in the browser for free, with patch notes saying what changed and what's still weak.</p></div></li>
    </ol>
  </section>

  <section class="band">
    <div class="split">
      <div class="panel" style="border-color:var(--teal)">
        <h3>The tools</h3>
        <ul>
          <li><strong>Claude Code</strong> (Anthropic) writes most of the code</li>
          <li><strong>PixelLab</strong> generates much of the pixel art</li>
          <li><strong>Claude</strong> also draws sprites pixel by pixel in Python scripts</li>
          <li><strong>TypeScript, Canvas, Three.js, Vite</strong>: no game engine</li>
          <li><strong>GitHub Pages</strong> hosts every game for free</li>
        </ul>
      </div>
      <div class="panel" style="border-color:var(--amber)">
        <h3>What stays human</h3>
        <ul>
          <li>The ideas, and the taste that picks between them</li>
          <li>The numbers and why they're those numbers</li>
          <li>Every playtest and every keep-or-cut call</li>
          <li>The replies when you leave feedback</li>
        </ul>
      </div>
    </div>
  </section>

  <section class="band">
    <h2 style="margin-bottom:20px">Questions people ask</h2>
    <div class="faq">
      <details><summary>Isn't this just AI slop?</summary><p>Slop is stuff nobody played before shipping. Play one of these for ten minutes and judge for yourself. The design docs, the decisions and the playtesting are the work, and you can read all of it in the repos.</p></details>
      <details><summary>Did you write the code?</summary><p>Mostly no. Claude Code writes most of it from my docs and my feedback. I'm not going to claim otherwise.</p></details>
      <details><summary>Is the art AI?</summary><p>Much of it, yes. Each game page says how its art was made. Some sprites come from PixelLab; some are drawn pixel by pixel by Claude in a script.</p></details>
      <details><summary>Why are the games free?</summary><p>Because I'd rather have players than a price tag right now. If a game earns a bigger version later, the browser version stays free.</p></details>
      <details><summary>Can I use your code?</summary><p>Every repo is public on GitHub so you can read how it works. Check each repo for its license before reusing anything.</p></details>
    </div>
  </section>

  <section class="band">
    <h2 style="margin-bottom:12px">Press kit</h2>
    <p class="muted" style="margin-bottom:20px">Logos for anyone writing about the games. Screenshots are on each game page.</p>
    <div class="kit">
      <a href="/assets/brand/ycgnem-lockup.svg"><img src="/assets/brand/ycgnem-lockup.svg" alt="">Lockup (SVG)</a>
      <a class="light" href="/assets/brand/ycgnem-lockup-dark.svg"><img src="/assets/brand/ycgnem-lockup-dark.svg" alt="">On light (SVG)</a>
      <a href="/assets/brand/ycgnem-icon.svg"><img src="/assets/brand/ycgnem-icon.svg" alt="">Icon (SVG)</a>
      <a href="/assets/brand/avatar-1024.png"><img src="/assets/brand/avatar-1024.png" alt="">Avatar (PNG)</a>
    </div>
  </section>
</div>"""
    return layout("/how-i-build/", "How I build", "Exactly how ycgNem's games get made with AI, and how to check every claim.", body)


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
    write("how-i-build/index.html", page_how())
    write("community/index.html", page_community())
    write("404.html", page_404())
    write("feed.xml", feed(posts))
    urls = ["/", "/devlog/", "/how-i-build/", "/community/"] + [f"/games/{g['id']}/" for g in GAMES] + [f"/devlog/{p['slug']}/" for p in posts]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{BASE}{u}</loc></url>" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    write(".nojekyll", "")
    print(f"Built {len(urls)} pages into {OUT} ({len(updated)} repo dates from GitHub)")


if __name__ == "__main__":
    main()

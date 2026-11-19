"""Pick an accent colour for each game from its cover and save it in content/games.json.

Needs Pillow (`pip install pillow`), which is why this isn't part of build.py.
Run it after adding a game or changing a cover:  python tools/accents.py
Games without an accent fall back to amber, so skipping this never breaks the build.
"""
import colorsys
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GAMES = ROOT / "content/games.json"
BINS = 24


def accent(cover):
    """The strongest hue in the cover, at a fixed lightness so it reads on the dark page."""
    im = Image.open(cover).convert("RGB").resize((64, 36))
    bins = [[0.0, 0.0, 0.0] for _ in range(BINS)]  # weight, weighted saturation, weighted hue
    px = im.tobytes()
    for i in range(0, len(px), 3):
        r, g, b = px[i], px[i + 1], px[i + 2]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        w = s * s * v
        slot = bins[int(h * BINS) % BINS]
        slot[0] += w
        slot[1] += s * w
        slot[2] += h * w
    weight, sat, hue = max(bins, key=lambda b: b[0])
    if weight < 8:  # a nearly grey cover has no hue worth using
        return None
    r, g, b = colorsys.hls_to_rgb(hue / weight, 0.64, min(0.9, max(0.72, sat / weight)))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def main():
    games = json.loads(GAMES.read_text(encoding="utf8"))
    for g in games:
        cover = ROOT / f"assets/games/{g['id']}/cover-640.webp"
        colour = accent(cover) if cover.exists() else None
        if colour:
            g["accent"] = colour
        else:
            g.pop("accent", None)
        print(f"{g['id']:28} {colour or '(amber)'}")
    GAMES.write_text(json.dumps(games, indent=2, ensure_ascii=False), encoding="utf8")


if __name__ == "__main__":
    main()

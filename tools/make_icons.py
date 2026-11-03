#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): the port's icons, drawn here from plain hexagons: no game artwork. The NRO's JPEG (256x256) and the Windows
build's .ico, replacing Katamari's cover art.
  python tools/make_icons.py [--title "Hexic HD"] [--jpg tools/switch/icon/hexichd_icon.jpg] [--ico app/icon/app.ico]
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLOURS = [(208, 80, 74), (232, 160, 48), (92, 168, 84), (88, 112, 208), (176, 144, 144)]


def hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(60 * i)), cy + r * math.sin(math.radians(60 * i))) for i in range(6)]


def draw_icon(size, title):
    # Drawn at 4x and scaled down, for smooth edges.
    s = size * 4
    im = Image.new('RGB', (s, s), (16, 20, 32))
    d = ImageDraw.Draw(im)
    r = s * 0.115
    pick = 0
    for col in range(-1, 6):
        for row in range(-1, 7):
            cx = s * 0.10 + col * r * 1.56
            cy = s * 0.10 + row * r * 1.78 + (r * 0.89 if col % 2 else 0)
            d.polygon(hexagon(cx, cy, r * 0.94), fill=COLOURS[pick % len(COLOURS)], outline=(10, 12, 20))
            d.polygon(hexagon(cx, cy, r * 0.5), fill=tuple(min(255, c + 34) for c in COLOURS[pick % len(COLOURS)]))
            pick += 3 + col
    if title:
        band = (0, int(s * 0.36), s, int(s * 0.64))
        d.rectangle(band, fill=(10, 14, 24))
        try:
            font = ImageFont.truetype('arialbd.ttf', int(s * 0.17))
        except OSError:
            font = ImageFont.load_default()
        box = d.textbbox((0, 0), title, font=font)
        d.text(((s - box[2] + box[0]) / 2 - box[0], (s - box[3] + box[1]) / 2 - box[1]), title, font=font, fill=(240, 244, 255))
    return im.resize((size, size), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--title', default='Hexic 2')
    ap.add_argument('--jpg', default=os.path.join(ROOT, 'tools', 'switch', 'icon', 'hexichd_icon.jpg'))
    ap.add_argument('--ico', default=os.path.join(ROOT, 'app', 'icon', 'app.ico'))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.jpg), exist_ok=True)
    draw_icon(256, a.title).save(a.jpg, quality=92)
    draw_icon(256, a.title).save(a.ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(a.jpg, os.path.getsize(a.jpg), a.ico, os.path.getsize(a.ico))


if __name__ == '__main__':
    main()

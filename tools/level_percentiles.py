#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): brightness percentiles over a run's captures, for comparing two renderers where pixels do not line up: this game's
camera moves with the cursor and its boards are random, so comparing pixel by pixel (tools/gamma_curve.py) measures the misalignment. A
gamma ramp moves the percentiles and the board does not, over enough frames.

  python tools/level_percentiles.py <label=folder[:first-last]> ... [--crop x1,y1,x2,y2]

first and last pick captures by their seconds. All runs are scaled to the first run's size. Prints each run's percentiles per channel.
"""
import argparse
import glob
import os
import re

from PIL import Image

POINTS = (5, 10, 25, 50, 75, 90, 95)


def percentiles(hist):
    total = sum(hist)
    out = []
    for p in POINTS:
        goal = total * p / 100
        seen = 0
        for level, n in enumerate(hist):
            seen += n
            if seen >= goal:
                out.append(level)
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--crop')
    a = ap.parse_args()
    crop = tuple(int(v) for v in a.crop.split(',')) if a.crop else None
    size = None
    print('run'.ljust(12) + 'frames ch  ' + ' '.join(f'p{p:<3d}' for p in POINTS) + '  mean')
    for spec in a.runs:
        label, _, rest = spec.partition('=')
        folder, _, window = rest.partition(':')
        first, last = (float(v) for v in window.split('-')) if window else (0.0, 1e9)
        files = []
        for f in sorted(glob.glob(os.path.join(folder, '*.png'))):
            m = re.search(r'_(\d+)s\.png$', f)
            if m and first <= float(m.group(1)) <= last:
                files.append(f)
        hist = [[0] * 256 for _ in range(3)]
        used = 0
        for f in files:
            try:
                im = Image.open(f).convert('RGB')
            except OSError:
                continue  # a capture cut off when the run stopped
            size = size or im.size
            if im.size != size:
                im = im.resize(size, Image.BILINEAR)
            if crop:
                im = im.crop(crop)
            for c, band in enumerate(im.split()):
                for level, n in enumerate(band.histogram()):
                    hist[c][level] += n
            used += 1
        for c, name in enumerate('RGB'):
            total = max(sum(hist[c]), 1)
            mean = sum(level * n for level, n in enumerate(hist[c])) / total
            print(f'{label:12s}{used:5d}  {name}  ' + ' '.join(f'{v:4d}' for v in percentiles(hist[c])) + f'  {mean:6.1f}')


if __name__ == '__main__':
    main()

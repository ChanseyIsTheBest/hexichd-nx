#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): a renderer's picture against a reference's, pixel by pixel in regions that do not change between runs: for each
level of the first image, the second's average at those pixels. A gamma ramp the first image lacks shows as a curve away from the diagonal.
The boards differ between runs and the title background animates, so give regions of the fixed scenery, and captures of the same screen.

  python tools/gamma_curve.py ours.png reference.png [--region x1,y1,x2,y2 ...] [--bucket 16]

Regions are in the larger image's pixels and scaled with it. Prints, per level bucket: the pixels in it, ours, the reference's, the
difference; then the mean absolute difference over all the pixels, which is what to compare between settings.
"""
import argparse

from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ours')
    ap.add_argument('reference')
    ap.add_argument('--region', action='append', default=[])
    ap.add_argument('--bucket', type=int, default=16)
    ap.add_argument('--quiet', action='store_true', help='the summary line only')
    a = ap.parse_args()
    ours = Image.open(a.ours).convert('RGB')
    reference = Image.open(a.reference).convert('RGB')
    if reference.size != ours.size:
        reference = reference.resize(ours.size, Image.BILINEAR)
    width, height = ours.size
    regions = [tuple(int(v) for v in r.split(',')) for r in a.region] or [(0, 0, width, height)]
    buckets = {}
    total = count = 0
    for x1, y1, x2, y2 in regions:
        o = ours.crop((x1, y1, x2, y2)).tobytes()
        r = reference.crop((x1, y1, x2, y2)).tobytes()
        for i in range(len(o)):
            b = buckets.setdefault(o[i] // a.bucket, [0, 0, 0])
            b[0] += 1
            b[1] += o[i]
            b[2] += r[i]
            total += abs(o[i] - r[i])
            count += 1
    if not a.quiet:
        print('level   pixels    ours    ref   ref-ours')
        for key in sorted(buckets):
            n, so, sr = buckets[key]
            print(f'{key * a.bucket:5d} {n:8d} {so / n:7.1f} {sr / n:6.1f} {(sr - so) / n:+8.1f}')
    print(f'mean absolute difference {total / max(count, 1):.2f} levels over {count} samples')


if __name__ == '__main__':
    main()

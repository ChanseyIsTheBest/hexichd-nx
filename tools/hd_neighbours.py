#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): a function the pairs did not reach (too small for a unique shape), found by its neighbours: the paired functions
either side of it in Ridge Racer 6 bracket it in this game, the libraries being linked in the same order. Prints both sides' instructions so
the match is read, not assumed.

  python tools/hd_neighbours.py 0x82254368 [0x...] [--count 14]
"""
import argparse
import glob
import json
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RR6 = 'D:/ridge racer 6/rr6-nx'


def starts(gen):
    out = set()
    pat = re.compile(r'DEFINE_REX_FUNC\(sub_([0-9A-Fa-f]{8})\)')
    for path in glob.glob(os.path.join(gen, '*_recomp.*.cpp')):
        out.update(int(m, 16) for m in pat.findall(open(path, errors='replace').read()))
    return sorted(out)


def dis(image, address, count):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'ppc_dis.py'), hex(address), str(count), '--image', image],
                       stdout=subprocess.PIPE, text=True, cwd=ROOT)
    return [line[:50] for line in r.stdout.splitlines()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('addresses', nargs='+')
    ap.add_argument('--count', type=int, default=14)
    a = ap.parse_args()
    raw = json.load(open(os.path.join(ROOT, 'out', 'renut_map', 'rr6_to_hd.json')))
    pairs = {}
    for k, v in raw.items():
        target = (v.get('nights') or next(iter(v.values()))) if isinstance(v, dict) else v
        pairs[int(str(k), 16)] = int(str(target), 16)
    keys = sorted(pairs)
    rr6_starts = starts(os.path.join(RR6, 'app', 'generated'))
    hd_starts = starts(os.path.join(ROOT, 'app', 'generated'))
    rr6_image = os.path.join(RR6, 'out', 'renut_image.bin')
    hd_image = os.path.join(ROOT, 'out', 'renut_image.bin')
    for text in a.addresses:
        address = int(text, 16)
        before = max((k for k in keys if k < address), default=None)
        after = min((k for k in keys if k > address), default=None)
        position = sum(1 for s in rr6_starts if before < s <= address)
        low, high = pairs[before], pairs[after]
        between = [s for s in hd_starts if low < s < high]
        print(f'=== RR6 {address:08X}: between pairs {before:08X}={low:08X} and {after:08X}={high:08X}; function {position} after the first in RR6; '
              f'{sum(1 for s in rr6_starts if before < s < after)} functions between in RR6, {len(between)} in HD: ' +
              ' '.join(f'{s:08X}' for s in between[:12]))
        print('\n'.join(dis(rr6_image, address, a.count)))
        guess = between[position - 1] if 0 < position <= len(between) else None
        if guess:
            print(f'--- HD candidate {guess:08X}')
            print('\n'.join(dis(hd_image, guess, a.count)))


if __name__ == '__main__':
    main()

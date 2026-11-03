#!/usr/bin/env python3
"""hexic2-nx (2026-11-03): who reaches a Direct3D ring function without going through a Renut hook. A function that writes the
ring runs the game's own PM4 code on Renut's device, fills a ring nobody drains and ends in a fence wait that never completes.
Walks the static call graph upward from the given functions, stopping at hooked functions, and names each caller by its
Katamari or N&B counterpart when the hook map's pairs know one.

  python -I tools/renut_unhooked_callers.py 0x921261C8 [more] [--depth 4] [--code 9208E000:92589AD4]
"""
import argparse
import json
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x92000000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('addrs', nargs='+')
    ap.add_argument('--depth', type=int, default=4)
    ap.add_argument('--code', default='9208E000:92589AD4')
    a = ap.parse_args()
    lo, hi = (int(x, 16) for x in a.code.split(':'))
    img = open(os.path.join(ROOT, 'out', 'renut_image.bin'), 'rb').read()
    # What is registered: the hook lines themselves (out/renut_map/hook_map.json describes the tree before the move).
    hooks = {}
    hdir = os.path.join(ROOT, 'app', 'src', 'renut_engine', 'gpu', 'd3d', 'hooks')
    for n in os.listdir(hdir):
        for m in re.finditer(r'^\s*BANJO_RENUT_HOOK(?:_RAW)?(?:_SHARED)?\(sub_([0-9A-F]{8})(?:,\s*(\w+))?', open(os.path.join(hdir, n), encoding='utf-8', errors='replace').read(), re.M):
            hooks[int(m.group(1), 16)] = m.group(2) or 'raw'
    kat = {int(v['nights'], 16): k for k, v in json.load(open(os.path.join(ROOT, 'out', 'renut_map', 'kat_to_hx2.json'))).items()}
    starts = set()
    gen = os.path.join(ROOT, 'app', 'generated')
    for n in os.listdir(gen):
        if n.startswith('renut_recomp.') and n.endswith('.cpp'):
            for m in re.finditer(r'^DEFINE_REX_FUNC\(sub_([0-9A-F]{8})\)', open(os.path.join(gen, n), errors='replace').read(), re.M):
                starts.add(int(m.group(1), 16))
    order = sorted(starts)
    import bisect

    def owner(pc):
        i = bisect.bisect_right(order, pc) - 1
        return order[i] if i >= 0 else None

    callers = {}
    for off in range(lo - BASE, hi - BASE, 4):
        w = struct.unpack_from('>I', img, off)[0]
        if w >> 26 != 18:
            continue
        d = w & 0x03FFFFFC
        if d & 0x02000000:
            d -= 0x04000000
        pc = off + BASE
        t = (pc + d) & 0xFFFFFFFF if not w & 2 else d & 0xFFFFFFFF
        callers.setdefault(t, set()).add(owner(pc))

    def name(f):
        s = f'sub_{f:08X}'
        if f in kat:
            s += f' (Katamari {kat[f]})'
        if f in hooks:
            s += f' HOOKED {hooks[f]}'
        return s

    seen = set()

    def walk(f, depth):
        for c in sorted(x for x in callers.get(f, ()) if x is not None and x != f):
            print('  ' * depth + name(c))
            if c in hooks or c in seen or depth >= a.depth:
                continue
            seen.add(c)
            walk(c, depth + 1)

    for x in a.addrs:
        f = int(x, 16)
        print(name(f))
        walk(f, 1)


if __name__ == '__main__':
    main()

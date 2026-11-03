#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): this game's Direct3D library against Renut's hooks. Each function of the library (the ranges below, from where the
pairs of tools/d3d_propagate.py land) with: hooked or not, its callers from outside the library, what it calls, and the displacements it uses on
anything but the stack. An unhooked function a game function calls runs the game's own code on Renut's device: its fields are the ones whose
offsets have to be this game's.

  python tools/hd_lib_census.py [--min 0x400] [--outside-only]
"""
import argparse
import collections
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNC = re.compile(r'^\s*DEFINE_REX_FUNC\(sub_([0-9A-Fa-f]{8})\)')
INSN = re.compile(r'^\s*//\s*(\w+\.?)\s+(.*)$')
DFORM = re.compile(r'^(?:[rfv]\d+,)?(-?\d+)\((r\d+)\)$')
LIB = [(0x920B0000, 0x920C9000), (0x9221C000, 0x9221E000)]


def in_lib(a):
    return any(lo <= a < hi for lo, hi in LIB)


def hooks():
    out = set()
    folder = os.path.join(ROOT, 'app', 'src', 'renut_engine', 'gpu', 'd3d', 'hooks')
    for name in os.listdir(folder):
        text = open(os.path.join(folder, name), encoding='utf-8', errors='replace').read()
        out.update(int(m, 16) for m in re.findall(r'BANJO_RENUT_HOOK(?:_RAW)?(?:_SHARED)?\(sub_([0-9A-Fa-f]{8})', text))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min', type=lambda s: int(s, 0), default=0x400)
    ap.add_argument('--outside-only', action='store_true')
    a = ap.parse_args()
    hooked = hooks()
    fields = collections.defaultdict(collections.Counter)
    calls = collections.defaultdict(set)
    callers = collections.defaultdict(set)
    size = collections.Counter()
    for path in glob.glob(os.path.join(ROOT, 'app', 'generated', 'renut_recomp.*.cpp')):
        fn = None
        for raw in open(path, errors='replace'):
            m = FUNC.match(raw)
            if m:
                fn = int(m.group(1), 16)
                continue
            m = INSN.match(raw)
            if not m or fn is None:
                continue
            op, args = m.group(1), m.group(2).strip()
            size[fn] += 1
            if op in ('bl', 'b') and args.startswith('0x'):
                target = int(args, 16)
                if op == 'bl' or not (fn <= target < fn + 0x4000):
                    calls[fn].add(target)
                    callers[target].add(fn)
                continue
            d = DFORM.match(args)
            if d and d.group(2) != 'r1' and in_lib(fn) and int(d.group(1)) >= a.min:
                fields[fn][int(d.group(1))] += 1
    names = sorted(f for f in size if in_lib(f))
    print(f'{len(names)} library functions, {sum(1 for f in names if f in hooked)} hooked')
    for f in names:
        if f in hooked:
            continue
        outside = sorted(c for c in callers[f] if not in_lib(c))
        inside = sorted(c for c in callers[f] if in_lib(c))
        if a.outside_only and not outside:
            continue
        offs = ' '.join(f'{o:#x}' for o in sorted(fields[f]))
        print(f'sub_{f:08X} {size[f]:4d} ins, callers out {len(outside)} in {len(inside)} (hooked in {sum(1 for c in inside if c in hooked)}),'
              f' calls {len(calls[f])}; fields: {offs}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): device-offset literals in Renut's D3D layer and renderer that no port pass marked. XDK 2.0.5426's
device fields from the constants on sit 128 bytes below Katamari's; tools/renut_port_hexic2.py moves the literals it knows, and marks
each moved line. A literal it missed still names Katamari's field: `bits(0x294C, 0, 1)`, GetRenderState's ViewportEnable, read the
guard band instead, and the game's state save/restore then turned the viewport transform off for the whole main pass.

  python tools/renut_unshifted_literals.py [--low 0x400] [--high 0x5700]

Prints every line with a literal in the range and no port mark, with the fields it would be in Katamari's and this XDK's layouts left
for a reader to judge: not every such literal is a device offset.
"""
import argparse
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'src', 'renut_engine', 'gpu')
LIT = re.compile(r'\b0x([0-9A-Fa-f]{3,4})\b')
MARK = 'hexic'
# What a device access looks like.
ACCESS = re.compile(r'(\.(?:W|F|H|B|Q|U32|SetW|SetF|SetH|SetB|SetQ|Dirty)\(|bits\(|bytes \+|d\.bytes|device\.|\bd\.|constexpr u32 k|constexpr u32 [A-Z]|LoadU32\(|StoreU32\(|\bkDeviceOffset|U32\()')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--low', type=lambda s: int(s, 0), default=0x400)
    ap.add_argument('--high', type=lambda s: int(s, 0), default=0x5700)
    ap.add_argument('--all', action='store_true', help='also lines that do not look like device accesses')
    args = ap.parse_args()
    for folder, _, files in os.walk(ROOT):
        for name in sorted(files):
            if not name.endswith(('.cpp', '.h', '.inl')):
                continue
            path = os.path.join(folder, name)
            for number, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
                code = line.split('//')[0]
                if MARK in line:
                    continue
                hits = [m.group(0) for m in LIT.finditer(code) if args.low <= int(m.group(1), 16) < args.high]
                if not hits:
                    continue
                if args.all or ACCESS.search(code):
                    print(f'{os.path.relpath(path, ROOT)}:{number}: {line.strip()[:150]}')


if __name__ == '__main__':
    main()

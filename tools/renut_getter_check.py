#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): each render state getter of the image against native::GetRenderState: the device offset the guest's getter
loads (first lwz/lhz/lbz/lfs off r3), beside the case line in d3d_native_state.cpp. A mismatch names a literal the layout port missed.

  python tools/renut_getter_check.py --tables out/renut_map/state_tables.txt --image out/renut_image.bin [--base 0x92000000]
"""
import argparse
import os
import re
import struct

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'src', 'renut_engine', 'gpu', 'd3d', 'd3d_native_state.cpp')
LOADS = {32: 'lwz', 34: 'lbz', 40: 'lhz', 42: 'lha', 48: 'lfs', 50: 'lfd'}


def first_loads(img, base, addr, limit=24):
    """The D-form loads off r3 before the function's first blr."""
    out = []
    for i in range(limit):
        word = struct.unpack_from('>I', img, addr - base + i * 4)[0]
        op = word >> 26
        ra = (word >> 16) & 31
        if op in LOADS and ra == 3:
            d = word & 0xFFFF
            out.append((LOADS[op], d))
        if word == 0x4E800020:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', default='out/renut_map/state_tables.txt')
    ap.add_argument('--image', default='out/renut_image.bin')
    ap.add_argument('--base', type=lambda s: int(s, 0), default=0x92000000)
    args = ap.parse_args()
    img = open(args.image, 'rb').read()
    rows = {}
    for line in open(args.tables):
        m = re.match(r'render (\d+) get \S+ ([0-9A-Fa-f]{8})', line)
        if m:
            rows[int(m.group(1))] = int(m.group(2), 16)
    cases = {}
    for line in open(SRC, encoding='utf-8', errors='replace'):
        m = re.match(r'\s*case (\d+): return (.*)', line)
        if m:
            cases.setdefault(int(m.group(1)), m.group(2).strip()[:70])
    for row in sorted(rows):
        loads = first_loads(img, args.base, rows[row])
        text = ' '.join(f'{op} 0x{d:X}' for op, d in loads)
        case = cases.get(row, '')
        lits = [int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{3,4})\b', case.split('//')[0])]
        flag = ''
        if lits and loads and not any(d in lits for _, d in loads):
            flag = '   <== DIFFERS'
        print(f'{row:3d} {rows[row]:08X} [{text}] | {case}{flag}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): a Ridge Racer 6 function the pairs did not reach (too small or too changed for a unique shape), against every
function of this game: opcode sequences compared, registers and immediates ignored, device offsets listed so a match is read and not assumed.
The two libraries are not linked in the same order, so neighbours say nothing.

  python tools/hd_nearest.py 0x82254368 [0x...] [--top 4]
"""
import argparse
import difflib
import glob
import json
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RR6 = 'D:/ridge racer 6/rr6-nx'
PAT = re.compile(r'DEFINE_REX_FUNC\(sub_([0-9A-Fa-f]{8})\)')


def starts(gen):
    out = set()
    for path in glob.glob(os.path.join(gen, '*_recomp.*.cpp')):
        out.update(int(m, 16) for m in PAT.findall(open(path, errors='replace').read()))
    return sorted(out)


def words(image, base, start, end):
    n = (end - start) // 4
    return list(struct.unpack_from(f'>{n}I', image, start - base))


def token(w):
    op = w >> 26
    if op in (19, 31, 63, 59, 4):
        return (op, (w >> 1) & 0x3FF)
    if op == 16:
        return (16, (w >> 16) & 0x3FF)  # the condition and the CR field
    return (op,)


def trim(ws):
    """Up to the first blr or the padding after it, so a function's tail of zeros does not count."""
    for i, w in enumerate(ws):
        if w == 0x4E800020:
            rest = ws[i + 1:]
            if not rest or all(x == 0 for x in rest):
                return ws[:i + 1]
    while ws and ws[-1] == 0:
        ws = ws[:-1]
    return ws


def offsets(ws):
    """The D-form displacements off a base register, in order: what a device function reads and writes."""
    out = []
    for w in ws:
        op = w >> 26
        if op in (32, 34, 40, 42, 36, 38, 44, 48, 50, 52, 54):
            d = w & 0xFFFF
            out.append(d - 0x10000 if d & 0x8000 else d)
        elif op == 58 or op == 62:
            out.append(w & 0xFFFC)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('addresses', nargs='+')
    ap.add_argument('--top', type=int, default=4)
    a = ap.parse_args()
    rr6_image = open(os.path.join(RR6, 'out', 'renut_image.bin'), 'rb').read()
    hd_image = open(os.path.join(ROOT, 'out', 'renut_image.bin'), 'rb').read()
    rr6 = starts(os.path.join(RR6, 'app', 'generated'))
    hd = starts(os.path.join(ROOT, 'app', 'generated'))
    bodies = []
    for s, e in zip(hd, hd[1:] + [0x922526E4]):
        ws = trim(words(hd_image, 0x92000000, s, e))
        bodies.append((s, ws, [token(w) for w in ws]))
    raw = json.load(open(os.path.join(ROOT, 'out', 'renut_map', 'rr6_to_hd.json')))
    taken = {int(str((v.get('nights') or next(iter(v.values()))) if isinstance(v, dict) else v), 16) for v in raw.values()}
    for text in a.addresses:
        address = int(text, 16)
        index = rr6.index(address)
        ws = trim(words(rr6_image, 0x82000000, address, rr6[index + 1]))
        toks = [token(w) for w in ws]
        scored = []
        for s, hw, ht in bodies:
            if not ht or abs(len(ht) - len(toks)) > max(4, len(toks) // 2):
                continue
            ratio = difflib.SequenceMatcher(None, toks, ht, autojunk=False).ratio()
            scored.append((ratio, s, hw))
        scored.sort(key=lambda r: -r[0])
        print(f'RR6 {address:08X}: {len(ws)} instructions, offsets {offsets(ws)[:14]}')
        for ratio, s, hw in scored[:a.top]:
            note = ' (already paired)' if s in taken else ''
            print(f'   {ratio:.3f} {s:08X} {len(hw)} instructions, offsets {offsets(hw)[:14]}{note}')


if __name__ == '__main__':
    main()

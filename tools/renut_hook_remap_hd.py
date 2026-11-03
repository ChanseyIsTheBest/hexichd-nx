#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): moves the addresses of rr6-nx's renderer layer (tools/hd_import_rr6.py) to this game's, through the pairs of
tools/d3d_propagate.py (out/renut_map/rr6_to_hd.json) and the state tables, row for row (97 + 20).

Each `sub_82XXXXXX` and `0x82XXXXXX` in code, not in a comment: a function with a partner is rewritten. One without is reported; with
--apply-unmapped-off its hook line becomes BANJO_RENUT_UNHOOKED_HOOK, compiled and unregistered, as tools/renut_hook_remap_rr6.py does for a
function this game does not link. Data addresses have no pairs: they are reported for tools/d3d_data_addrs*.py and reading by hand.
A moved line ends with `hexichd-nx: rr6 sub_X`, so a second run leaves it alone.

  python tools/renut_hook_remap_hd.py --report
  python tools/renut_hook_remap_hd.py --apply
"""
import argparse
import json
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPU = os.path.join(ROOT, 'app', 'src', 'renut_engine', 'gpu')
RR6_IMAGE = 'D:/ridge racer 6/rr6-nx/out/renut_image.bin'
RR6_TABLES = (0x823763E0, 0x82376870)
HD_TABLES = (0x92254438, 0x922548C8)
ROWS = (97, 20)
SCAN = ['d3d/d3d.h', 'd3d/d3d_native.h', 'd3d/d3d_native_state.cpp', 'd3d/hooks/device.cpp', 'd3d/hooks/draw.cpp', 'd3d/hooks/resource.cpp',
        'd3d/hooks/shader.cpp', 'd3d/hooks/state.cpp', 'render/draw.cpp', 'render/surfaces.cpp', 'banjo_renut_tuning.cpp']
TOKEN = re.compile(r'\b(sub_|unlinked_|0x)(82[0-9A-Fa-f]{6})\b')
LIVE_HOOK = re.compile(r'\bBANJO_RENUT_HOOK(_RAW|_SHARED)?\(sub_(82[0-9A-Fa-f]{6})')
# Read by hand (docs/hexichd-notes.md, "Renut at XDK 2.0.1884"). VB Unlock: opcode similarity 1.000 at +12 (tools/hd_nearest.py). The data:
# VdGlobalDevice's slot, the image's only word 0xFFCAE000; caps and format blocks by RR6's bytes (one match each); the tables from
# tools/renut_state_tables.py; the build qword from sub_920C0CE0, RR6's sub_82261260, `lis r11,-28123; ld r11,18976(r11)`.
HAND = {0x82254D90: 0x920B9F38, 0x82000598: 0x92000548, 0x8206BF58: 0x92002E80, 0x8206C088: 0x92002408,
        0x823763E0: 0x92254438, 0x82376870: 0x922548C8, 0x82376960: 0x92254A20}


def load_pairs():
    with open(os.path.join(ROOT, 'out', 'renut_map', 'rr6_to_hd.json')) as f:
        raw = json.load(f)
    pairs = {}
    for k, v in raw.items():
        target = v.get('nights') or v.get('hd') or next(iter(v.values())) if isinstance(v, dict) else v
        pairs[int(str(k), 16)] = int(str(target), 16)
    # The state tables, row for row: getter and setter.
    rr6 = open(RR6_IMAGE, 'rb').read()
    hd = open(os.path.join(ROOT, 'out', 'renut_image.bin'), 'rb').read()
    for ra, ha, rows in zip(RR6_TABLES, HD_TABLES, ROWS):
        for i in range(rows):
            r = struct.unpack_from('>3I', rr6, ra - 0x82000000 + 12 * i)
            h = struct.unpack_from('>3I', hd, ha - 0x92000000 + 12 * i)
            pairs[r[0]] = h[0]
            pairs[r[1]] = h[1]
    pairs.update(HAND)
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    pairs = load_pairs()
    missing = {}
    moved = 0
    for rel in SCAN:
        path = os.path.join(GPU, rel.replace('/', os.sep))
        with open(path, encoding='utf-8', errors='surrogateescape', newline='') as f:
            text = f.read()
        nl = '\r\n' if '\r\n' in text[:4000] else '\n'
        out = []
        for number, line in enumerate(text.split(nl), 1):
            code, sep, comment = line.partition('//')
            changed = False
            names = []

            def repl(m):
                nonlocal changed
                address = int(m.group(2), 16)
                if address in pairs:
                    changed = True
                    names.append(m.group(2).upper())
                    return f'{m.group(1)}{pairs[address]:08X}'
                missing.setdefault(address, []).append(f'{rel}:{number}: {line.strip()[:110]}')
                return m.group(0)

            # A live hook with no partner: this game does not link the function (a search of its code by the fields it uses).
            hook = LIVE_HOOK.search(code)
            if hook and int(hook.group(2), 16) not in pairs:
                new = f'BANJO_RENUT_UNHOOKED_HOOK{hook.group(1) or ""}(unlinked_{hook.group(2)}'
                line = line.replace(hook.group(0), new) + ' hexichd-nx: this game does not link it'
                code, sep, comment = line.partition('//')
            new_code = TOKEN.sub(repl, code)
            if changed:
                moved += 1
                line = new_code + sep + comment
                line = line.rstrip() + ('' if sep else '  //') + ' hexichd-nx: rr6 ' + ','.join(names)
            out.append(line)
        if a.apply:
            with open(path, 'w', encoding='utf-8', errors='surrogateescape', newline='') as f:
                f.write(nl.join(out))
    hooks = {k: v for k, v in missing.items() if any('HOOK' in s for s in v)}
    print(f'{moved} lines {"moved" if a.apply else "would move"}; {len(missing)} addresses with no partner, {len(hooks)} of them on hook lines')
    for address in sorted(missing):
        for site in missing[address][:2]:
            print(f'  {address:08X} {site}')


if __name__ == '__main__':
    main()

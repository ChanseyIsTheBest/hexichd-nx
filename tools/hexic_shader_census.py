#!/usr/bin/env python3
"""hexic2-nx / hexichd-nx (2026-11-03): where this game keeps its shaders (the renderer guide's section 2): the image, and every
file of the game folder, whole shader files (.xpu, .xvu) and containers inside other files, at any byte offset. Writes each
unique container as <out>/{vs,ps}_<xxh3>.bin, the name Renut looks shaders up by, and prints the census.

  python tools/hexic_shader_census.py --image out/renut_image.bin --game app/assets --out out/shader_census [--magic 11,0E]
"""
import argparse
import collections
import os
import re
import struct

import xxhash


def containers(data, magic, aligned=False):
    """(offset, size, is_vertex) of each shader container in data: tools/renut_shader_dump.py's checks."""
    out = []
    for m in re.finditer(rb'\x10\x2a' + bytes([magic]), data):
        o = m.start()
        if (aligned and o % 4) or o + 0x24 > len(data):
            continue
        virt, phys = struct.unpack_from('>II', data, o + 4)
        ct, dt, so = struct.unpack_from('>III', data, o + 0x10)
        if not (0x24 <= virt < 0x10000 and 0 < phys < 0x100000 and o + virt <= len(data)):
            continue
        if ct >= virt or dt >= virt or not (0x24 <= so < virt - 8):
            continue
        size = virt + phys
        if o + size > len(data):
            continue
        out.append((o, size, data[o + 3] & 1 == 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True)
    ap.add_argument('--game', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--magic', default='11,0E', help='container versions (hex)')
    a = ap.parse_args()
    magics = [int(x, 16) for x in a.magic.split(',')]
    os.makedirs(a.out, exist_ok=True)
    seen = {}
    where = collections.Counter()
    versions = collections.Counter()

    def take(data, label, whole=False):
        n = 0
        for magic in magics:
            for o, size, vs in containers(data, magic):
                body = data[o:o + size]
                key = ('vs' if vs else 'ps') + '_' + xxhash.xxh3_64_hexdigest(body).upper()
                versions[f'0x{magic:02X}'] += 1
                if key not in seen:
                    seen[key] = label
                    with open(os.path.join(a.out, key + '.bin'), 'wb') as f:
                        f.write(body)
                n += 1
        if n:
            where[label] += n
        return n

    take(open(a.image, 'rb').read(), 'image')
    per_ext = collections.Counter()
    empties = []
    for d, _, fs in os.walk(a.game):
        for f in fs:
            p = os.path.join(d, f)
            ext = os.path.splitext(f)[1].lower()
            if f.lower() in ('default.xex', 'default.xexp'):
                continue
            data = open(p, 'rb').read()
            n = take(data, ext or '(none)')
            per_ext[ext] += n
            if ext in ('.xpu', '.xvu') and not n:
                empties.append(os.path.relpath(p, a.game))
    vs = sum(1 for k in seen if k.startswith('vs_'))
    print(f'{len(seen)} unique containers ({vs} vertex, {len(seen) - vs} pixel); versions {dict(versions)}')
    print('containers found, by where:', dict(where))
    print('first seen in:', dict(collections.Counter(seen.values())))
    if empties:
        print('shader files with no valid container:', empties)


if __name__ == '__main__':
    main()

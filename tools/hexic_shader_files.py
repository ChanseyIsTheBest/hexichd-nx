#!/usr/bin/env python3
"""hexic2-nx / hexichd-nx (2026-11-04): where each of the game's shaders is in its own files, for the web installer (it makes deko3d_glsl.bin
in the player's browser, and the NRO holds no shader of the game). katamari-nx's tools/katamari_shader_files.py, for this game's places:

  image    the whole container is in the patched executable: the page finds it by scanning, its SHA-256 is listed
  files    the whole container is in a file of the game, at one offset (Media/Shaders/*.xpu, *.xvu)
  split    the mesh files (CAFF, Meshes/*.bin) keep the virtual and the physical part apart: the game joins them when it registers the shader,
           so the page does too. Listed by file and both offsets; the join's SHA-256 is the check
  runtime  in none of the game's files: the game assembles it at run time. These stay built into the NRO (pacman-nx's four, the same way)

Writes out/hexic_shader_files.json. Takes the shader bins by the names Renut looks them up by (vs_<xxh3>.bin, ps_<xxh3>.bin).

  python tools/hexic_shader_files.py --image out/renut_image.bin --game app/assets --shaders out/renut_shader_dump --out out/hexic_shader_files.json
"""
import argparse
import collections
import hashlib
import json
import os
import re
import struct


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True)
    ap.add_argument('--game', required=True)
    ap.add_argument('--shaders', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    image = open(a.image, 'rb').read()
    game = {}
    for dirpath, _, names in os.walk(a.game):
        for n in names:
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, a.game).replace(os.sep, '/')
            if rel.lower() in ('default.xex', 'default.xexp'):
                continue
            if n.lower().endswith(('.xma', '.wma', '.png', '.dds', '.ttf')):
                continue
            game[rel] = open(p, 'rb').read()
    print('files searched:', len(game), 'bytes', sum(len(v) for v in game.values()))
    names = sorted(f for f in os.listdir(a.shaders) if re.fullmatch(r'((vs|ps)_)?[0-9A-Fa-f]{16}\.bin', f))
    out = {'image_sha256': [], 'files': [], 'split': [], 'runtime': []}
    counts = collections.Counter()
    for n in names:
        b = open(os.path.join(a.shaders, n), 'rb').read()
        # A version 0x0E container's bin has its hash alone for a name (Hexic HD's): its low bit is 1 for a vertex shader.
        stem = n[:-4] if n[2] == '_' else ('vs_' if b[3] & 1 else 'ps_') + n[:-4]
        virt, phys = struct.unpack_from('>II', b, 4)
        hash_ = sha(b)
        if b in image or image.find(b) >= 0:
            out['image_sha256'].append(hash_)
            counts['image'] += 1
            continue
        whole = None
        for rel, data in game.items():
            at = data.find(b)
            if at >= 0:
                whole = (rel, at)
                break
        if whole:
            out['files'].append({'name': stem, 'file': whole[0], 'at': whole[1], 'length': len(b), 'sha256': hash_})
            counts['files'] += 1
            continue
        vpart, ppart = b[:virt], b[virt:virt + phys]
        found = None
        for rel, data in game.items():
            v = data.find(vpart)
            if v < 0:
                continue
            p = data.find(ppart)
            if p >= 0:
                found = (rel, v, p)
                break
        if found and len(b) == virt + phys:
            out['split'].append({'name': stem, 'file': found[0], 'virtual_at': found[1], 'virtual': virt, 'physical_at': found[2], 'physical': phys,
                                 'sha256': hash_})
            counts['split'] += 1
            continue
        out['runtime'].append({'name': stem, 'virtual': virt, 'physical': phys, 'length': len(b)})
        counts['runtime'] += 1
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(dict(counts), 'of', len(names))
    for r in out['runtime'][:40]:
        print('  not in the files:', r['name'], r['virtual'], r['physical'], r['length'])
    print('files that hold split shaders:', len({s['file'] for s in out['split']}))


if __name__ == '__main__':
    main()

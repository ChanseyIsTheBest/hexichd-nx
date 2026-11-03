#!/usr/bin/env python3
"""hexic2-nx (2026-11-03, from pacman-nx's d3d_data_addrs_pacman.py): the guest data addresses Renut's Direct3D layer reads,
at Hexic 2's: constant blocks by content (Beautiful Katamari's bytes, word for word; the build qword by its value), variables
by the instruction that builds them in the paired function (out/renut_map/kat_to_hx2.json).

  python -I tools/d3d_data_addrs_hexic2.py
"""
import json
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = 0x82000000
B = 0x92000000
K = open(r'D:\beautifulkatamari\katamari-nx\out\renut_image.bin', 'rb').read()
P = open(os.path.join(ROOT, 'out', 'renut_image.bin'), 'rb').read()
pairs = json.load(open(os.path.join(ROOT, 'out', 'renut_map', 'kat_to_hx2.json')))


def find_all(data, needle, align=4):
    out, i = [], data.find(needle)
    while i >= 0:
        if i % align == 0:
            out.append(i + B)
        i = data.find(needle, i + 1)
    return out


def refs(img, base, fn, n=400):
    """(index, address, opcode) of every lis + D-form / addi use in the first n instructions of fn."""
    hi, out = {}, []
    for k in range(n):
        w = struct.unpack_from('>I', img, fn - base + 4 * k)[0]
        op, rd, ra, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        s = imm - 0x10000 if imm & 0x8000 else imm
        if op == 15 and ra == 0:
            hi[rd] = (imm << 16) & 0xFFFFFFFF
        elif ra in hi and op in (14, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 44, 45, 48, 50, 52, 54, 58, 62):
            out.append((k, (hi[ra] + s) & 0xFFFFFFFF, op))
        if w == 0x4E800020 and k > 8:
            break
    return out


print('content searches')
for name, addr, size in (('format table', 0x820FA9D0, 128), ('full viewport', 0x820FAEB4, 24), ('D3DCAPS9', 0x820FC1F8, 304)):
    print(f'  {name}: Katamari {addr:08X} -> {[hex(x) for x in find_all(P, K[addr - KB:addr - KB + size])]}')
q = struct.pack('>HHHH', 2, 0, 5426, 0x4002)
print('  the build qword 2.0.5426 (QFE 2, approval 2):', [hex(x) for x in find_all(P, q, 8)])
print('variables through the paired functions (Katamari -> Hexic 2)')
for name, kfn, kaddr in (('VdGlobalDevice record (D3D_LockResource)', 0x824DB210, 0x82000750),
                         ('HiZ owner (CreateSurface)', 0x824D23F8, 0x8315E830),
                         ('HiZ owner (Destroy)', 0x824DB028, 0x8315E830)):
    k = f'{kfn:08X}'
    pfn = pairs.get(k, {}).get('nights')
    krefs = refs(K, KB, kfn)
    print(f'  {name}: Katamari fn {k} refs {[hex(a) for _, a, _ in krefs][:12]}; this game fn {pfn}')
    if pfn:
        prefs = refs(P, B, int(pfn, 16))
        print(f'     this game refs {[hex(a) for _, a, _ in prefs][:12]}')
        for i in [i for i, (_, a, _) in enumerate(krefs) if a == kaddr]:
            if i < len(prefs):
                print(f'     Katamari ref #{i} {kaddr:08X} -> {prefs[i][1]:08X}')
# XPhysicalAlloc: the shape, Katamari's 0x824C1C30 (the no-large-pages word).
print('XPhysicalAlloc by its first words (Katamari 0x824C1C30):')
kw = [struct.unpack_from('>I', K, 0x824C1C30 - KB + 4 * i)[0] for i in range(40)]
krefs = refs(K, KB, 0x824C1C30, 40)
print('  Katamari refs', [hex(a) for _, a, _ in krefs])
mask = lambda w: w & 0xFC00F800 if (w >> 26) in (15, 32, 14) else w
for off in range(0x9208E000 - B, 0x92589AD4 - B, 4):
    hits = sum(1 for i in range(12) if mask(struct.unpack_from('>I', P, off + 4 * i)[0]) == mask(kw[i]))
    if hits >= 10:
        print(f'  candidate {off + B:08X} ({hits} of 12): refs', [hex(a) for _, a, _ in refs(P, B, off + B, 40)])

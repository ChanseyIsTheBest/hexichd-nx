#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): the PE section table of an image dump (out/renut_image.bin): the code range the analysis tools take as --code.
  python tools/pe_sections.py [--image out/renut_image.bin] [--base 0x92000000]
"""
import argparse
import struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', default='out/renut_image.bin')
    ap.add_argument('--base', type=lambda s: int(s, 0), default=0x92000000)
    a = ap.parse_args()
    d = open(a.image, 'rb').read()
    if d[:2] != b'MZ':
        print('no MZ header at the image start')
        return
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    if d[pe:pe + 4] != b'PE\0\0':
        print('no PE header')
        return
    # The headers are little-endian even on the Xbox 360 (machine 0x01F2).
    machine, count = struct.unpack_from('<HH', d, pe + 4)
    optional = struct.unpack_from('<H', d, pe + 20)[0]
    table = pe + 24 + optional
    print(f'machine {machine:04X}, {count} sections')
    low, high = None, None
    for i in range(count):
        s = table + i * 40
        name = d[s:s + 8].rstrip(b'\0').decode('latin1')
        vsize, vaddr = struct.unpack_from('<II', d, s + 8)
        flags = struct.unpack_from('<I', d, s + 36)[0]
        code = bool(flags & 0x20)
        print(f'{name:10s} {a.base + vaddr:08X}-{a.base + vaddr + vsize:08X} flags {flags:08X}{"  code" if code else ""}')
        if code:
            low = a.base + vaddr if low is None else min(low, a.base + vaddr)
            high = a.base + vaddr + vsize if high is None else max(high, a.base + vaddr + vsize)
    if low is not None:
        print(f'code range {low:08X}:{high:08X}')


if __name__ == '__main__':
    main()

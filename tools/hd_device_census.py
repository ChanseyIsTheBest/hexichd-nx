#!/usr/bin/env python3
"""hexichd-nx (2026-11-04, rr6-nx's tools/rr6_device_census.py for this game): who touches the D3D device directly, and where. The device
pointer is read from one global (the image's global `lis/lwz`, found from the setter tables' users); a function that loads it and then accesses
fields off that register is code that runs on Renut's device with whatever layout that field has, so those are the offsets that have to agree.

  python tools/hd_device_census.py --global 0x9225XXXX [--hooks] [--min 0x400]
Prints each offset with its functions (reads and writes), most used first, and with --hooks whether each function is hooked.
"""
import argparse
import collections
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNC = re.compile(r'^\s*DEFINE_REX_FUNC\((sub_[0-9A-Fa-f]+)\)')
INSN = re.compile(r'^\s*//\s*(\w+\.?)\s+(.*)$')


def hooks():
    out = set()
    folder = os.path.join(ROOT, 'app', 'src', 'renut_engine', 'gpu', 'd3d', 'hooks')
    for name in os.listdir(folder):
        text = open(os.path.join(folder, name), encoding='utf-8', errors='replace').read()
        out.update(m.upper() for m in re.findall(r'BANJO_RENUT_HOOK(?:_RAW)?(?:_SHARED)?\(sub_([0-9A-Fa-f]{8})', text))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--global', dest='device_global', required=True, help='the address of the word holding the device pointer')
    ap.add_argument('--min', type=lambda s: int(s, 0), default=0)
    ap.add_argument('--top', type=int, default=60)
    a = ap.parse_args()
    target = int(a.device_global, 16)
    hooked = hooks()
    fields = collections.defaultdict(lambda: collections.Counter())
    users = collections.Counter()
    for path in glob.glob(os.path.join(ROOT, 'app', 'generated', 'renut_recomp.*.cpp')):
        fn = None
        hi = {}
        device = set()
        for raw in open(path, errors='replace'):
            m = FUNC.match(raw)
            if m:
                fn, hi, device = m.group(1), {}, set()
                continue
            m = INSN.match(raw)
            if not m or not fn:
                continue
            op, args = m.group(1), m.group(2).split(',')
            if op == 'lis' and len(args) == 2:
                hi[args[0].strip()] = (int(args[1], 0) << 16) & 0xFFFFFFFF
            elif op in ('lwz', 'addi') and len(args) == 2 and '(' in args[1]:
                d, base = args[1].rstrip(')').split('(')
                base = base.strip()
                reg = args[0].strip()
                value = hi.get(base)
                if value is not None and ((value + int(d)) & 0xFFFFFFFF) == target and op == 'lwz':
                    device.add(reg)
                    users[fn] += 1
                    continue
                if base in device and int(d) >= a.min:
                    fields[int(d)][fn] += 1
                if reg in device:
                    device.discard(reg)
            elif len(args) >= 2 and '(' in args[-1]:
                d, base = args[-1].rstrip(')').split('(')
                base = base.strip()
                try:
                    disp = int(d)
                except ValueError:
                    continue
                if base in device and disp >= a.min:
                    fields[disp][fn] += 1
                if not op.startswith('st') and args[0].strip() in device:
                    device.discard(args[0].strip())
            elif args and args[0].strip() in device and not op.startswith(('st', 'cmp', 'b')):
                device.discard(args[0].strip())
    print(f'{len(users)} functions load the device pointer; {sum(1 for f in users if f[4:].upper() in hooked)} of them hooked')
    for offset in sorted(fields, key=lambda o: -sum(fields[o].values()))[:a.top]:
        names = fields[offset]
        unhooked = [n for n in names if n[4:].upper() not in hooked]
        print(f'  +0x{offset:04X} ({offset:5d}): {sum(names.values()):4d} accesses in {len(names):3d} functions ({len(unhooked)} unhooked) e.g. {" ".join(list(names)[:3])}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): app/config/hot_functions.txt and hot_edges.txt from sampled runs, for tools/hot_layout.py and tools/inline_leaves.py --hot.

Banjo made both from console profiles. Neither changes what the code does: one is where a function is placed, the other which file holds a copy of a
callee, so they do not wait for a console profile the way a hand-written native does. Samples from Ryujinx show which functions run, which is what placement
needs; a console profile can replace these lists later.

  hot_functions.txt  every generated function with at least --min samples, except the machine copies' originals (the copy is what runs; its own code is
                     in the bulk shards already)
  hot_edges.txt      "caller callee" for a sampled generated function's direct call of another sampled generated function. inline_leaves.py keeps only the
                     callees that are leaves of at most 128 guest instructions in another file

  python tools/hot_lists.py <rex_profile.log> [...] [--map app/out/switch/renut.map] [--min 2] [--write]
"""
import argparse
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINE = re.compile(r'^\s*[\d.]+%\s+(\d+)\s+(\S+)\s+(\S+)')
FUNC = re.compile(r'^DEFINE_REX_FUNC\((\w+)\) \{$')
CALL = re.compile(r'\b(?:__imp__)?(sub_[0-9A-F]{8})\(ctx, base\)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('logs', nargs='+')
    ap.add_argument('--map', default=os.path.join(ROOT, 'app', 'out', 'switch', 'renut.map'))
    ap.add_argument('--min', type=int, default=2)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    samples = {}
    for log in a.logs:
        res = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'switch_hot_functions.py'), log, '--map', a.map, '--top', '100000'],
                             stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
        section = False
        for line in res.stdout.split('\n'):
            if line.startswith('== '):
                section = line.startswith('== all threads')
                continue
            m = LINE.match(line) if section else None
            if m and m.group(2) == 'default':
                name = m.group(3)
                name = name[7:] if name.startswith('__imp__') else name
                samples[name] = samples.get(name, 0) + int(m.group(1))
    copies = set()
    bulk = os.path.join(ROOT, 'app', 'src', 'cpu', 'hot', 'localized_bulk.txt')
    for line in open(bulk, encoding='utf-8'):
        m = re.match(r'([0-9A-F]{8})\b', line)
        if m:
            copies.add('sub_' + m.group(1))
    hot = {n for n, c in samples.items() if c >= a.min and n not in copies}
    edges = set()
    for path in glob.glob(os.path.join(ROOT, 'app', 'generated', '*_recomp.*.cpp')):
        name = None
        for line in open(path, encoding='utf-8'):
            if name is None:
                m = FUNC.match(line.rstrip('\n'))
                if m and m.group(1) in hot:
                    name = m.group(1)
                continue
            if line.startswith('}'):
                name = None
                continue
            for m in CALL.finditer(line):
                if m.group(1) in hot and m.group(1) != name:
                    edges.add((name, m.group(1)))
    print('samples in %d generated functions (%d samples); %d are copies\' originals; hot_functions %d, hot_edges %d' % (
        len(samples), sum(samples.values()), len(set(samples) & copies), len(hot), len(edges)))
    top = sorted(((samples[n], n) for n in hot), reverse=True)[:12]
    print('top without a copy: ' + ', '.join('%s %d' % (n, c) for c, n in top))
    if a.write:
        head = '# tools/hot_lists.py, from Ryujinx samples: placement and inlining only (nothing a console profile must prove).\n'
        with open(os.path.join(ROOT, 'app', 'config', 'hot_functions.txt'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(head + ''.join(n + '\n' for n in sorted(hot)))
        with open(os.path.join(ROOT, 'app', 'config', 'hot_edges.txt'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(head + ''.join('%s %s\n' % e for e in sorted(edges)))


if __name__ == '__main__':
    main()

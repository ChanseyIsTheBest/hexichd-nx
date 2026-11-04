#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): which generated functions are worth tools/switch_goto.py's threaded dispatch: a jump-table switch big enough to be an
interpreter's, weighed by what ran. Banjo's list named its five script interpreters from a console profile; this prints a game's candidates.

For each function with a plain switch of at least --min cases: the largest switch, how many it has, whether a machine copy replaces it, calls per run from
the verify runs' counts (hexic_hot_counts.txt, any number), and self samples from a sample list (tools/switch_hot_functions.py's output as "name count").

  python tools/switch_census.py [--gen app/generated] [--min 8] [--counts <file> ...] [--samples <file>]
"""
import argparse
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNC = re.compile(r'^DEFINE_REX_FUNC\((\w+)\) \{$')
SW = re.compile(r'^\t+switch \(([\w.]+)\) \{$')
CASE = re.compile(r'^\t+case (\d+):$')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', default=os.path.join(ROOT, 'app', 'generated'))
    ap.add_argument('--min', type=int, default=8)
    ap.add_argument('--counts', nargs='*', default=[])
    ap.add_argument('--samples')
    ap.add_argument('--top', type=int, default=40)
    a = ap.parse_args()
    bulk = set()
    p = os.path.join(ROOT, 'app', 'src', 'cpu', 'hot', 'localized_bulk.txt')
    if os.path.isfile(p):
        bulk = {'sub_' + m for m in re.findall(r'\b(?:sub_)?([0-9A-F]{8})\b', open(p, encoding='utf-8').read())}
    calls = {}
    for f in a.counts:
        for line in open(f, encoding='utf-8'):
            m = line.split()
            if len(m) >= 5 and m[0].startswith('sub_'):  # function, ..., calls compared, calls not comparable, ...
                calls[m[0]] = calls.get(m[0], 0) + int(m[3]) + int(m[4])
    samples = {}
    if a.samples:
        for line in open(a.samples, encoding='utf-8'):
            m = re.match(r'(\S+)\s+(\d+)', line)
            if m:
                samples[m.group(1)] = samples.get(m.group(1), 0) + int(m.group(2))
    rows = []
    for path in sorted(glob.glob(os.path.join(a.gen, '*_recomp.*.cpp'))):
        name = None
        best = n = sites = 0
        for line in open(path, encoding='utf-8'):
            if name is None:
                m = FUNC.match(line.rstrip('\n'))
                if m:
                    name, best, n, sites = m.group(1), 0, 0, 0
                continue
            if line.startswith('}'):
                if best >= a.min:
                    rows.append((name, best, sites, name in bulk, calls.get(name, 0), samples.get(name, 0)))
                name = None
                continue
            if SW.match(line):
                sites += 1
                n = 0
            elif CASE.match(line):
                n += 1
                best = max(best, n)
    rows.sort(key=lambda r: (-r[5], -r[4], -r[1]))
    print('%d functions with a switch of at least %d cases' % (len(rows), a.min))
    print('%-16s %6s %6s %5s %14s %8s' % ('function', 'cases', 'sites', 'copy', 'copy calls', 'samples'))
    for r in rows[:a.top]:
        print('%-16s %6d %6d %5s %14d %8d' % (r[0], r[1], r[2], 'yes' if r[3] else '', r[4], r[5]))


if __name__ == '__main__':
    main()

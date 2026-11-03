#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): a run's verify result from its log: the warnings the verify keys print, and from each report's last line every
count of differences, so a run is judged on numbers and not on a search that also matches the reports' wording.

  python tools/verify_counts.py <log> [--all]

Prints each kind of warning with its count; then each report (the text before its first number, as a key) with the difference counts of
its last line. Exit 1 when a difference count is not zero.
"""
import argparse
import re
import sys

STAMP = re.compile(r'^\[[^]]*\] \[(\w+)\] \[(\w+)\] \[t\d+\] ')
# "0 differ", "3 differences", "differences 2", "2 differed": the number beside the word.
COUNT = re.compile(r'(\d+) (?:differ\w*|DIFFERENCE\w*|mismatch\w*)|(?:differences?|differ|mismatches)[:=]? (\d+)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--all', action='store_true', help='also reports whose counts are all zero')
    a = ap.parse_args()
    warnings = {}
    last = {}
    for line in open(a.log, encoding='utf-8', errors='replace'):
        m = STAMP.match(line)
        if not m:
            continue
        level, text = m.group(1), line[m.end():].rstrip()
        if level in ('warning', 'error', 'critical'):
            key = re.sub(r'[0-9A-Fa-f]{6,}|\d+', 'N', text)[:110]
            warnings[key] = warnings.get(key, 0) + 1
        if 'differ' in text.lower() or 'mismatch' in text.lower():
            key = re.split(r'\d', text, 1)[0][:70]
            last[key] = text
    print(f'{sum(warnings.values())} warnings and errors, {len(warnings)} kinds')
    for key, n in sorted(warnings.items(), key=lambda kv: -kv[1]):
        print(f'  {n:6d}  {key}')
    bad = 0
    print(f'{len(last)} reports with difference counts')
    for key, text in sorted(last.items()):
        counts = [int(x or y) for x, y in COUNT.findall(text)]
        nonzero = [c for c in counts if c]
        bad += len(nonzero)
        if nonzero or a.all:
            print(f'  {"NONZERO" if nonzero else "zero   "} {counts} {key}')
    print('differences:', 'none' if not bad else f'{bad} non-zero counts')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""halo3-nx (2026-11-03): finds a miscompile of tools/loop_locals.py in code already generated, and repairs it with --fix.

A region of that pass ran from a loop header to its last jump back. When that jump is a case of a switch, the region ended in
the middle of the switch: the later cases are reached from inside the region, but jump out without storing its locals, so the
code after them reads stale registers. tools/loop_locals.py no longer does this (switch_end); a fresh codegen is the clean
repair, and --fix adds the missing stores for a tree that has not been regenerated. Idempotent.

  python tools/loop_switch_check.py [--gen app/generated] [--fix]

Prints each function with the shape and how many case jumps lack the stores.
"""
import argparse
import glob
import os
import re

FUNC = re.compile(r'^DEFINE_REX_FUNC\((\w+)\)')
OUT = re.compile(r'^\tREX_LOOP_OUT\(')
CASE_GOTO = re.compile(r'^\t\tgoto loc_[0-9A-F]+;$')


def process(lines, fix):
    """Returns the lines and [(function, unsynced case jumps)]."""
    result = []
    found = []
    name = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = FUNC.match(line)
        if m:
            name = m.group(1)
        if not line.startswith('\tswitch ('):
            result.append(line)
            i += 1
            continue
        end = i
        while end < len(lines) and lines[end] != '\t}':
            end += 1
        body = lines[i:end + 1]
        first_out = next((k for k, l in enumerate(body) if OUT.match(l)), None)
        if first_out is None:
            result.extend(body)
            i = end + 1
            continue
        outs = []
        for l in body[first_out:]:
            if not OUT.match(l):
                break
            outs.append(l)
        # The stubs end at the last label; the cases below them jump out of the region.
        last_label = max(k for k, l in enumerate(body) if re.match(r'^loc_[0-9A-F]+:', l))
        unsynced = 0
        new = body[:last_label + 1]
        for k in range(last_label + 1, len(body)):
            if CASE_GOTO.match(body[k]) and not OUT.match(body[k - 1].strip() and body[k - 1].replace('\t\t', '\t', 1)):
                unsynced += 1
                if fix:
                    new.extend('\t' + o for o in outs)
            new.append(body[k])
        found.append((name, unsynced))
        result.extend(new)
        i = end + 1
    return result, found


def main():
    ap = argparse.ArgumentParser()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--gen', default=os.path.join(root, 'app', 'generated'))
    ap.add_argument('--fix', action='store_true')
    a = ap.parse_args()
    total = 0
    for path in sorted(glob.glob(os.path.join(a.gen, '**', '*_recomp.*.cpp'), recursive=True)):
        with open(path, newline='', encoding='utf-8', errors='replace') as f:
            text = f.read()
        if 'REX_LOOP_OUT' not in text or 'switch (' not in text:
            continue
        crlf = '\r\n' in text
        lines = text.replace('\r\n', '\n').split('\n')
        new, found = process(lines, a.fix)
        for name, unsynced in found:
            print('%s %s: %d case jumps out of a region without its stores' % (os.path.basename(path), name, unsynced))
            total += unsynced
        if a.fix and new != lines:
            out = '\n'.join(new)
            with open(path, 'w', newline='', encoding='utf-8') as f:
                f.write(out.replace('\n', '\r\n') if crlf else out)
    print('%d case jumps%s' % (total, ' repaired' if a.fix else ' to repair (0: this tree does not have the miscompile)'))


if __name__ == '__main__':
    main()

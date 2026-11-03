#!/usr/bin/env python3
"""halo3-nx (2026-11-02): vector instructions whose destination is also a source, and whose generated statements read the destination again
after writing it: a piecewise write over a value still to be read. The form of the vpkuwus / vpkuhus bug reported by another port (a ray missing
the floor at the edge of a collision tree). Reads each instruction's statements from the generated code, whatever builder wrote them.

  python tools/vector_alias_scan.py [app/generated]

Reports, per opcode, how many aliased sites there are and how many read the destination after a write, with examples. A statement that only
reads the element it is about to write (dst.u32[i] = f(dst.u32[i])) is the same index and is not reported; the operands of the report are worth
reading by hand against the builder.
"""
import collections
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
gen = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'app', 'generated')
INSN = re.compile(r'^\s*// ([a-z][a-z0-9.]*) (v\d+),(.*)$')
ELEM = re.compile(r'\.(u8|s8|u16|s16|u32|s32|f32|u64|s64)\[(\d+)\]')
SIZES = {'u8': 1, 's8': 1, 'u16': 2, 's16': 2, 'u32': 4, 's32': 4, 'f32': 4, 'u64': 8, 's64': 8}


def bytes_of(field, index):
    n = SIZES[field]
    return set(range(int(index) * n, int(index) * n + n))


sites = collections.Counter()
hazards = collections.Counter()
examples = collections.defaultdict(list)
for path in glob.glob(os.path.join(gen, '**', '*recomp*.cpp'), recursive=True):
    fn = ''
    lines = open(path, errors='replace').read().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('DEFINE_REX_FUNC('):
            fn = line[16:line.find(')')]
        m = INSN.match(line)
        i += 1
        if not m:
            continue
        op, dst, rest = m.group(1), m.group(2), m.group(3)
        sources = [s.strip() for s in rest.split(',')]
        if dst not in sources:
            continue
        sites[op] += 1
        body = []
        j = i
        while j < len(lines) and not re.match(r'^\s*//', lines[j]) and not lines[j].startswith('loc_') and len(body) < 60:
            body.append(lines[j])
            j += 1
        name = r'(?<![\w.])(?:ctx\.)?' + dst + r'\b'
        written = set()
        whole = False
        hazard = None
        for s in body:
            left, eq, right = s.partition('=') if re.search(r'[^=!<>]=[^=]', s) else ('', '', s)
            # What the statement reads first.
            for r in re.finditer(name + r'(\.(u8|s8|u16|s16|u32|s32|f32|u64|s64)\[(\d+)\])?', right):
                if whole:
                    hazard = s.strip()
                elif r.group(2):
                    if bytes_of(r.group(2), r.group(3)) & written:
                        # Reading back the element this statement itself wrote earlier is the same-index case only if
                        # that element is what the statement writes now (`dst.u16[7] |= ...` reads a source word).
                        hazard = s.strip()
                elif written:
                    hazard = s.strip()
            wm = re.search(name + r'\.(u8|s8|u16|s16|u32|s32|f32|u64|s64)\[(\d+)\]\s*[|&^+-]?=[^=]', s)
            if wm:
                written |= bytes_of(wm.group(1), wm.group(2))
            elif re.search(name + r'\s*=[^=]', s):
                whole = True
            elif re.search(r'store[^(]*\(\s*\(simde__m128i\*\)\s*' + name.replace(r'(?<![\w.])', ''), s):
                whole = True
        if hazard:
            hazards[op] += 1
            if len(examples[op]) < 4:
                examples[op].append((os.path.relpath(path, gen), fn, line.strip()[:50], hazard[:90]))
print('aliased sites by opcode:', dict(sites.most_common()))
print('read of the destination after a write:', dict(hazards.most_common()))
for op, ex in examples.items():
    print(op)
    for e in ex:
        print('   ', e)

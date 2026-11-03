#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): a yield at each db16cyc, the Xenon's spin-loop delay hint, which the generator otherwise drops (a bare loop).

Hexic 2's XAudio mixer waits for its workers in sub_9221A438: a loop of `ld r11,0(r4); ...; db16cyc`, written for six hardware threads. In
Ryujinx that one function took 97 % of its thread's samples and 57 % of a core. On the console a spinning thread is worse than wasted time:
Horizon does not time-slice threads of the same priority on a core, so it can sit in front of the worker it is waiting for. The instruction
says "this is a spin", so here it gives way (rex_spin_yield, app/src/cpu/banjo_enhancements.cpp; key banjo_spin_yield, A/B target 78).

Only a host call in a loop the guest wrote as a delay: no guest register or memory changes. Declared at the top of each file it is used in,
with C linkage stated: inside a function, the declaration would take the linkage of DEFINE_REX_FUNC's body, which is extern "C" in a
normal build and not in a coverage build (tools/pch_coverage.py). Not in the pch, so a new list of functions does not rebuild everything.
Idempotent. Run before the copies: localize_native.py refuses a function with a host call in it, so these stay generated functions.

  python tools/spin_yield.py --gen app/generated [--report]
"""
import argparse
import glob
import os
import re

CALL = 'rex_spin_yield();'
DECLARATION = 'extern "C" void rex_spin_yield();  // tools/spin_yield.py'
OLD_CALL = '{ void rex_spin_yield(); rex_spin_yield(); }'
FUNC = re.compile(r'^\s*DEFINE_REX_FUNC\((sub_[0-9A-Fa-f]+)\)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', default='app/generated')
    ap.add_argument('--report', action='store_true', help='count only')
    a = ap.parse_args()
    functions = {}
    changed = 0
    for path in sorted(glob.glob(os.path.join(a.gen, 'renut_recomp.*.cpp'))):
        with open(path, encoding='utf-8', errors='surrogateescape', newline='') as f:
            text = f.read()
        if 'db16cyc' not in text:
            continue
        nl = '\r\n' if '\r\n' in text[:4000] else '\n'
        lines = [line for line in text.split(nl) if line.strip() != OLD_CALL]
        out = []
        current = None
        for i, line in enumerate(lines):
            m = FUNC.match(line)
            if m:
                current = m.group(1)
            out.append(line)
            if line.strip().startswith('// db16cyc'):
                functions[current] = functions.get(current, 0) + 1
                if i + 1 >= len(lines) or lines[i + 1].strip() != CALL:
                    out.append('\t' + CALL)
        if DECLARATION not in out:
            # Before the first function, after the file's includes.
            at = next(i for i, line in enumerate(out) if FUNC.match(line))
            out.insert(at, DECLARATION)
        new = nl.join(out)
        if new != text and not a.report:
            with open(path, 'w', encoding='utf-8', errors='surrogateescape', newline='') as f:
                f.write(new)
            changed += 1
    print(f'spin_yield: {sum(functions.values())} db16cyc in {len(functions)} functions ({", ".join(sorted(functions))}); {changed} files changed')


if __name__ == '__main__':
    main()

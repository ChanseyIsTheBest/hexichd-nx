#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): the per-function choices of the post-codegen steps, measured on the compiled A57 code, for a port with no such lists yet.

Banjo's lists came from tools/locals_choice.py and from its CPU agent's scratch scripts (banjo-nx/out/cpu_aggressive/tools/choice.py), which were never
tools of the port. An empty list means different things: tools/lr_preserve.py rewrites nothing, tools/r1_local.py rewrites EVERY function (+0.33 % on
Banjo: "only the per-function choice pays"). This makes all three from one set of compiles.

Each generated file of a scratch tree is compiled with the Switch build's own command line (tools/locals_choice.py's compile_command) in these forms:
    A  every step on: the locals, r1 as a local mirror, every proven link-register write-back dropped
    L  -DREX_LOOP_LOCALS_OFF -DREX_LEAF_LOCALS_OFF
    R  -DREX_R1_LOCAL_OFF
    W  -DREX_LR_WRITE_SAME_OFF
and each function's cost in A is compared with its cost in the other form (locals_choice's loop-weighted cost: a loop instruction weighs 10, a memory
instruction twice, code only after a guest trap left out). Static counts of what the compiler made, not run-time samples. The forms change only the shape
of the C++ (each is a step's own switch-back), so every choice is exact either way; the choice only decides which is cheaper.

  app/config/locals_optout.txt         functions where L is cheaper than A by more than --locals-margin percent (2, as locals_choice's)
  app/config/r1_local_choice.json      functions where A is cheaper than R by more than --r1-margin percent (1, as Banjo's)
  app/config/lr_write_same_choice.json functions where A is cheaper than W at all (a write-back left out can only cost through what GCC then does)

The tree must have every proven write-back rewritten: tools/post_codegen.py --gen <copy> with REX_CHOICE_ALL=1 in the environment.

  python tools/form_choice.py --gen out/choice/gen --ninja app/out/switch/build.ninja --out out/choice [--jobs 8] [--reuse] [--write]
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals_choice as lc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMS = {'A': [], 'L': ['-DREX_LOOP_LOCALS_OFF', '-DREX_LEAF_LOCALS_OFF'], 'R': ['-DREX_R1_LOCAL_OFF'], 'W': ['-DREX_LR_WRITE_SAME_OFF']}
COST = 6  # locals_choice's measure(): the loop-weighted cost by the control-flow graph


def markers(path):
    """{function: (has REX_R1_LOCAL, has REX_LR_WRITE_SAME)} of one generated file."""
    out = {}
    name = None
    r1 = lr = False
    for line in open(path, encoding='utf-8'):
        if name is None:
            m = lc.FUNC.match(line.rstrip('\n'))
            if m:
                name, r1, lr = m.group(1), False, False
            continue
        if line.startswith('}'):
            out[name] = (r1, lr)
            name = None
            continue
        if 'REX_R1_LOCAL()' in line:
            r1 = True
        if 'REX_LR_WRITE_SAME(' in line:
            lr = True
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--gen', required=True)
    ap.add_argument('--ninja', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--reuse', action='store_true')
    ap.add_argument('--write', action='store_true', help='write the three lists into app/config')
    ap.add_argument('--files', help='only these file numbers (a trial)')
    ap.add_argument('--locals-margin', type=float, default=2.0)
    ap.add_argument('--r1-margin', type=float, default=1.0)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    gen = os.path.abspath(a.gen)
    for form in FORMS:
        os.makedirs(os.path.join(out, 'obj' + form), exist_ok=True)
    cmd, prefix, orig_gen, _ = lc.compile_command(a.ninja, gen, out)
    if lc.norm(orig_gen) == lc.norm(gen):
        sys.exit('form_choice: --gen is the build\'s own generated folder, not a copy')
    files = sorted((int(lc.TU.search(f).group(2)), f) for f in os.listdir(gen) if lc.TU.search(f) and lc.TU.search(f).group(1) == prefix)
    if a.files:
        want = {int(x) for x in a.files.split(',')}
        files = [(n, f) for n, f in files if n in want]
    print('form_choice: %d files, %d forms, %d jobs' % (len(files), len(FORMS), a.jobs), flush=True)
    start = datetime.datetime.now()

    def build(job):
        n, form = job
        src = os.path.join(gen, '%s_recomp.%d.cpp' % (prefix, n))
        obj = os.path.join(out, 'obj' + form, '%d.o' % n)
        if not (a.reuse and os.path.exists(obj) and os.path.getmtime(obj) > os.path.getmtime(src)):
            p = subprocess.run(cmd + FORMS[form] + ['-o', obj, '-c', src], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding='utf-8', errors='replace')
            if p.returncode:
                raise RuntimeError('compile %s (%s):\n%s' % (src, form, p.stdout[-3000:]))
        return n, form, lc.function_costs(obj, 'cfg')

    costs = {}
    jobs = [(n, form) for n, _ in files for form in FORMS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for k, fut in enumerate(concurrent.futures.as_completed([ex.submit(build, j) for j in jobs])):
            n, form, c = fut.result()
            costs[(n, form)] = c
            if (k + 1) % 20 == 0 or k + 1 == len(jobs):
                print('  %d / %d objects (%s)' % (k + 1, len(jobs), str(datetime.datetime.now() - start)[:7]), flush=True)

    optout, r1_list, lr_list = [], [], []
    total = {k: [0, 0, 0] for k in 'LRW'}  # all on, all off, with the choice
    rows = []
    for n, f in files:
        path = os.path.join(gen, f)
        locals_here = lc.changed_functions(path)
        marks = markers(path)
        A = costs[(n, 'A')]
        for name in sorted(set(locals_here) | set(marks)):
            if name not in A:
                continue
            on = A[name][COST]
            off_l = costs[(n, 'L')].get(name, A[name])[COST]
            off_r = costs[(n, 'R')].get(name, A[name])[COST]
            off_w = costs[(n, 'W')].get(name, A[name])[COST]
            rows.append((name, n, on, off_l, off_r, off_w))
            if name in locals_here:
                lose = on and 100.0 * (on - off_l) / on > a.locals_margin
                if lose:
                    for tool in locals_here[name][0].split('+'):
                        optout.append('%s %s' % (tool, name))
                total['L'][0] += on
                total['L'][1] += off_l
                total['L'][2] += off_l if lose else on
            r1, lr = marks.get(name, (False, False))
            if r1:
                win = off_r and 100.0 * (off_r - on) / off_r > a.r1_margin
                if win:
                    r1_list.append(name)
                total['R'][0] += on
                total['R'][1] += off_r
                total['R'][2] += on if win else off_r
            if lr:
                win = on < off_w
                if win:
                    lr_list.append(name)
                total['W'][0] += on
                total['W'][1] += off_w
                total['W'][2] += on if win else off_w
    lines = ['form_choice, %s, %d files (%s)' % (datetime.date.today().isoformat(), len(files), prefix)]
    for key, label, count in (('L', 'loop and leaf locals', len(optout)), ('R', 'r1 as a local', len(r1_list)), ('W', 'dropped lr write-backs', len(lr_list))):
        on, off, choice = total[key]
        lines.append('%-24s step on everywhere %d, off everywhere %d (%+.2f %%), with the choice %d (%+.2f %% of off); %s %d' % (
            label, on, off, 100.0 * (on - off) / off if off else 0, choice, 100.0 * (choice - off) / off if off else 0,
            'opted out' if key == 'L' else 'chosen', count))
    report = '\n'.join(lines) + '\n'
    print(report, end='')
    with open(os.path.join(out, 'form_choice_report.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(report)
    with open(os.path.join(out, 'form_choice.csv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('function,file,all_on,locals_off,r1_off,lr_writes\n')
        for r in rows:
            f.write('%s,%d,%d,%d,%d,%d\n' % r)
    header = ('# Guest functions whose A57 code is cheaper WITHOUT the loop / leaf locals: tools/form_choice.py, %s (more than %.1f %% of the locals form).\n'
              % (datetime.date.today().isoformat(), a.locals_margin))
    lists = {'locals_optout.txt': header + ''.join(l + '\n' for l in sorted(optout)),
             'r1_local_choice.json': json.dumps(sorted(r1_list) or ['__none__']),  # an empty list would mean every function (tools/r1_local.py)
             'lr_write_same_choice.json': json.dumps(sorted(lr_list))}
    for name, text in lists.items():
        with open(os.path.join(out, name), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        if a.write:
            with open(os.path.join(ROOT, 'app', 'config', name), 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
    print('form_choice: lists in %s%s' % (out, ' and app/config' if a.write else ''))


if __name__ == '__main__':
    main()

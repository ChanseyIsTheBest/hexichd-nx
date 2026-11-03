#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): the compiled-in settings against a shipped toml, key by key (the request: runs with a full toml never exercise the
defaults, so a player with the short toml gets something no test ran unless the two agree).

What the NRO uses for a key with no full toml: the player's toml as written at the first start (app/<game>_switch.toml), else the built-in
settings (app/<game>_switch_defaults.toml), else the key's Switch default in the sources (REXCVAR_DEFINE_*, BANJO_SWITCH_DEFAULT's first
argument). Prints every key of the shipped toml whose value differs from that, and every key the sources do not define.

  python tools/compare_defaults.py --game hexic2 [--shipped dist/switch/hexichd-nx/renut.toml] [--ignore <regex>]
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFINE = re.compile(r'REXCVAR_DEFINE_(BOOL|INT32|INT64|UINT32|UINT64|DOUBLE|STRING|FLOAT)\(\s*([a-z0-9_]+)\s*,\s*(.+?)\s*,\s*"', re.S)


def toml_values(path):
    """The keys before and between tables; a table's keys come as table.key. Comments and blank lines dropped."""
    out = {}
    table = ''
    if not os.path.isfile(path):
        return out
    for raw in open(path, encoding='utf-8', errors='replace'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            table = line.strip('[]').strip() + '.'
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        value = value.strip()
        if not value.startswith('"'):
            value = value.split('#', 1)[0].strip()
        out[table + key.strip()] = value
    return out


def source_defaults():
    out = {}
    for base in ('app/src', 'sdk/src'):
        for folder, _, files in os.walk(os.path.join(ROOT, base)):
            for name in files:
                if not name.endswith(('.cpp', '.h', '.inl')):
                    continue
                text = open(os.path.join(folder, name), encoding='utf-8', errors='replace').read()
                for m in DEFINE.finditer(text):
                    value = m.group(3).strip()
                    switch = re.match(r'BANJO_SWITCH_DEFAULT\(\s*(.+?)\s*,\s*(.+?)\s*\)$', value, re.S)
                    if switch:
                        value = switch.group(1)
                    value = {'true': 'true', 'false': 'false'}.get(value, value)
                    out.setdefault(m.group(2), value)
    return out


def same(a, b):
    if a == b:
        return True
    try:
        return float(a.rstrip('f')) == float(b.rstrip('f'))
    except (ValueError, AttributeError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default='hexic2')
    ap.add_argument('--shipped')
    ap.add_argument('--ignore', default='', help='keys to leave out (a regex)')
    a = ap.parse_args()
    shipped_path = a.shipped or os.path.join(ROOT, 'dist', 'switch', f'{a.game}-nx', 'renut.toml')
    shipped = toml_values(shipped_path)
    player = toml_values(os.path.join(ROOT, 'app', f'{a.game}_switch.toml'))
    builtin = toml_values(os.path.join(ROOT, 'app', f'{a.game}_switch_defaults.toml'))
    source = source_defaults()
    ignore = re.compile(a.ignore) if a.ignore else None
    differ, undefined, same_count = [], [], 0
    for key, value in sorted(shipped.items()):
        if ignore and ignore.search(key):
            continue
        if key in player:
            effective, where = player[key], 'player toml'
        elif key in builtin:
            effective, where = builtin[key], 'built in'
        elif key in source:
            effective, where = source[key], 'source'
        else:
            undefined.append((key, value))
            continue
        if same(value, effective):
            same_count += 1
        else:
            differ.append((key, value, effective, where))
    print(f'{os.path.relpath(shipped_path, ROOT)}: {len(shipped)} keys; the same without it {same_count}; different {len(differ)}; '
          f'not defined in the sources {len(undefined)}')
    if differ:
        print('\nDifferent: shipped toml | what the NRO uses without it')
        for key, value, effective, where in differ:
            print(f'  {key}: {value} | {effective} ({where})')
    if undefined:
        print('\nNot defined in the sources (the key does nothing, or its form hides from this search):')
        for key, value in undefined:
            print(f'  {key} = {value}')


if __name__ == '__main__':
    main()

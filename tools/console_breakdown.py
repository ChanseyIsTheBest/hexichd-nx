#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): a console profile by kind of work, per thread: what the frame goes on. Uses tools/switch_hot_functions.py's table of one
thread, from the windows of steady play, and puts each function in a group by its symbol and object.

  python tools/console_breakdown.py <rex_profile.log> [--map app/out/switch/renut.map] [--from-report 3]
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINE = re.compile(r'^\s*([\d.]+)%\s+(\d+)\s+(\S+)\s+(\S+)')
GROUPS = [
    ('draw capture (CaptureDelta)', r'CaptureDelta'),
    ('draw queue and hand-over', r'QueueDraw|QueueCapture|render_thread|FlushDeferred|FlushRecorded|CapturePool'),
    ('texture and surface shadows', r'Rr6|records|Lookup|OwnsHeader'),
    ('D3D setters (native)', r'd3d_native|native\d|SetTexture|SetStreamSource|state\.cpp|sub_920B4|sub_9221D'),
    ('critical sections (game\'s locks)', r'CriticalSection'),
    ('mutexes (host locks)', r'mutex|rwlock|syscall_lock'),
    ('kernel and SDK other', r'xboxkrnl|librex|rex::|librexruntime'),
    ('memcpy and memset', r'memcpy|memset|memmove'),
    ('game code, machine copies', r'banjo3hot'),
    ('game code, generated', r'^(__imp__)?sub_'),
    ('draw submission', r'FastDrawLocked|DrawStateLocked|PrepareGeometry|ExpandIndices|GetStreamSource|ComputeViewport|SetViewport|SetDrawDepthBias|DescribeBoundFetches'),
    ('bindings and constants', r'FillTextures|BindStreams|BindTargets|PushFloat|PushShared|bindTextures|setVertexBuffers|setIndexBuffer|flushDescriptor|Deko3D|dkCmd|UploadRing|plume'),
    ('surfaces', r'surfaces|GetHostSurface|TransitionSurface|FramebufferEpoch'),
]


def group(obj, name):
    text = obj + ' ' + name
    for label, pattern in GROUPS:
        if re.search(pattern, name) or (label.startswith('D3D') and re.search(pattern, obj)) or (label.startswith('surfaces') and re.search(pattern, obj)):
            return label
    if 'libnx' in obj or 'libsysbase' in obj:
        return 'libnx and libc other'
    if obj == 'default':
        return 'game code, generated'
    return 'other host code'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--map', default=os.path.join(ROOT, 'app', 'out', 'switch', 'renut.map'))
    ap.add_argument('--from-report', type=int, default=3)
    a = ap.parse_args()
    res = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'switch_hot_functions.py'), a.log, '--map', a.map, '--top', '100000',
                          '--from-report', str(a.from_report)], stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
    thread = None
    tables = {}
    for line in res.stdout.split('\n'):
        m = re.match(r'== thread "([^"]*)" \((\d+) samples\)', line)
        if m:
            thread = (m.group(1), int(m.group(2)))
            tables[thread] = {}
            continue
        if line.startswith('== '):
            thread = None
            continue
        m = LINE.match(line) if thread else None
        if m:
            g = group(m.group(3), m.group(4))
            tables[thread][g] = tables[thread].get(g, 0) + int(m.group(2))
    for (name, total), groups in sorted(tables.items(), key=lambda kv: -kv[0][1]):
        if total < 100:
            continue
        print('%s: %d samples' % (name, total))
        for g, n in sorted(groups.items(), key=lambda kv: -kv[1]):
            print('  %5.1f %%  %s' % (100.0 * n / total, g))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""hexichd-nx (2026-11-04): rr6-nx's renderer layer at XDK 2.0.2135, the closest to this game's 2.0.1884 (the same 97 + 20 state tables,
1,823 functions paired with Ridge Racer 6's, tools/d3d_propagate.py). Copies its files from rr6-nx's HEAD (read-only) and names its keys
for this port. rr6-nx's Renut started from the same katamari-nx code this tree did: only package names changed between the two commits.

  python tools/hd_import_rr6.py [--rr6 "D:/ridge racer 6/rr6-nx"]

Left as they are here: the general fixes already in this tree that rr6-nx lacks (backend/present.cpp's whole-line trim, native_window.cpp's
window_hidden). shader_common.h's NORMAL1 and the spin yield's A/B name are put back after the copy.
"""
import argparse
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPU = 'app/src/renut_engine/gpu/'
XENOS = 'app/thirdparty/reblue-XenosRecomp/XenosRecomp/'
FILES = [GPU + f for f in (
    'd3d/d3d.h', 'd3d/d3d_native.h', 'd3d/d3d_native_state.cpp', 'd3d/hooks/device.cpp', 'd3d/hooks/draw.cpp', 'd3d/hooks/resource.cpp',
    'd3d/hooks/shader.cpp', 'd3d/hooks/state.cpp', 'render/draw.cpp', 'render/draw.h', 'render/pipeline.cpp', 'render/surfaces.cpp',
    'render/surfaces.h', 'banjo_renut_tuning.cpp', 'banjo_renut_tuning.h', 'banjo_renut_deko3d.cpp', 'backend/render_thread.cpp',
    'shaders/host/point_sprite_gs.hlsl', 'shaders/host/rectangle_list_gs.hlsl')] + [XENOS + f for f in (
        'container_0e.h', 'main.cpp', 'shader_common.h', 'shader_recompiler.cpp', 'shader_recompiler.h')]
TOOLS = ['tools/rr6_d3d_api.py', 'tools/rr6_device_census.py', 'tools/rr6_shader_dump.py',
         'tools/renut_hook_remap_rr6.py']
# Keys and helpers named for rr6-nx take this port's name; its addresses are moved afterwards (tools/renut_hook_remap_hd.py).
TOKENS = [('rr6_', 'hexichd_'), ('RR6_', 'HEXICHD_')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rr6', default='D:/ridge racer 6/rr6-nx')
    a = ap.parse_args()
    for rel in FILES + TOOLS:
        try:
            data = subprocess.run(['git', '-C', a.rr6, 'show', f'HEAD:{rel}'], check=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL).stdout
        except subprocess.CalledProcessError:
            print('not in rr6-nx:', rel)
            continue
        if rel in FILES:
            text = data.decode('utf-8', 'surrogateescape')
            for x, y in TOKENS:
                text = text.replace(x, y)
            data = text.encode('utf-8', 'surrogateescape')
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
    print(len(FILES), 'renderer files and', len(TOOLS), 'tools copied')


if __name__ == '__main__':
    main()

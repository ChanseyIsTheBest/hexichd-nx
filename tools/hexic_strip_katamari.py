#!/usr/bin/env python3
"""hexic2-nx / hexichd-nx (2026-11-03): takes what belonged to Beautiful Katamari out of the copy of katamari-nx-public.
One-off, from rr6-nx's tools/rr6_strip_katamari.py and pacman-nx's stripped copies of the same base (its commit 331c5ee1).

 1. Sources no CMake file names (other games' addresses): "Stale mentions" in docs/optimising-functions.md.
    title_update.cpp stays: these two games are built from their title updates (the base does not build it).
 2. The hot lists and natives: emptied, the common code kept.
 3. pgo/, the icon, the forwarder NPDM: removed. Function lists and analysis lists: emptied.
 4. katamari_* file names and identifiers in CMake and the app: <port>_*.

  python tools/hexic_strip_katamari.py hexic2 "Hexic HD"
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAC = r'D:\pacman\pacman-nx'
PAC_COMMIT = '331c5ee1'  # pacman-nx's stripped copy, before anything of its own game went in

DELETE = """app/src/cpu/banjo_pool_lock.cpp
app/src/cpu/banjo_reverb_native.cpp
app/src/cpu/banjo_xaudio_native.cpp
app/src/cpu/katamari_stage_diag.cpp
app/src/me/banjo_me_hooks.cpp
app/src/native/banjo_d3d_hooks.cpp
app/src/native/banjo_espera_anillo.cpp
app/src/native/banjo_nativo_stubs.cpp
app/src/native/banjo_shader_harvest.cpp
app/src/native/nfsmw_nativo_destinos.cpp
app/src/native/nfsmw_nativo_dibujos.cpp
app/src/native/nfsmw_nativo_ganchos.cpp
app/src/native/nfsmw_nativo_shaders.cpp
app/src/native/nfsmw_nativo_sistema.cpp
app/src/native/nfsmw_nativo_texturas_pool.cpp
app/src/native/nfsmw_shader_library.cpp
app/src/renut_engine/StopNSwap.cpp
app/src/renut_engine/cvar_menu.cpp
app/src/renut_engine/env_map_pool.cpp
app/src/renut_engine/frameHooks.cpp
app/src/renut_engine/frontend_debug_menu.cpp
app/src/renut_engine/hooks.cpp
app/src/renut_engine/shader_dump.cpp
app/src/renut_engine/texture_tools.cpp
app/src/renut_engine/thread_slots.cpp
app/src/renut_engine/townsfolk.cpp
tools/katamari_files.py
tools/katamari_shader_files.py
tools/cpdb.py
tools/forwarder/katamari_forwarder.json
tools/forwarder/katamari_main.npdm
tools/renut_hook_map_katamari.txt
tools/switch/icon/katamari_icon.jpg
docs/console-rc3-breakdown.md
docs/console-rc4-breakdown.md
docs/console-rc5-breakdown.md
docs/console-rc9-breakdown.md""".split()

# Stripped copies from pacman-nx at PAC_COMMIT (the same base files with the game's content out).
COPY = """app/src/cpu/hot/banjo_hand_natives.h
app/src/cpu/hot/hand.txt
app/src/cpu/hot/localized.txt
app/src/cpu/banjo_hot_guest.cpp
app/src/cpu/banjo_hot_guest.h
app/config/hot_edges.txt
app/config/hot_functions.txt
app/config/locals_optout.txt
app/config/lr_write_same_choice.json
app/config/r1_local_choice.json
app/config/renut_crt.toml
app/config/renut_hooks.toml
app/indirect_promotions.txt""".split()


def pac_blob(rel):
    return subprocess.run(['git', '-C', PAC, 'show', f'{PAC_COMMIT}:{rel}'], check=True, stdout=subprocess.PIPE).stdout


def main():
    port, title = sys.argv[1], sys.argv[2]
    upper = port.upper()
    camel = port[0].upper() + port[1:]
    for rel in DELETE:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            os.remove(p)
    for rel in COPY:
        text = pac_blob(rel).replace(b'pacman-nx', f'{port}-nx'.encode())
        with open(os.path.join(ROOT, rel), 'wb') as f:
            f.write(text)
    with open(os.path.join(ROOT, 'app/src/cpu/hot/localized_bulk.txt'), 'w', newline='\n') as f:
        f.write(f'# {port}-nx: machine copies by tools/switch_hot_bulk.py --merge (docs/optimising-functions.md).\n')
    pgo = os.path.join(ROOT, 'pgo')
    if os.path.isdir(pgo):
        shutil.rmtree(pgo)
    rename = {
        'app/katamari_switch.toml': f'app/{port}_switch.toml',
        'app/katamari_switch_defaults.toml': f'app/{port}_switch_defaults.toml',
        'app/src/katamari_keys.cpp': f'app/src/{port}_keys.cpp',
        'app/src/katamari_builtin_config.h.in': f'app/src/{port}_builtin_config.h.in',
        'tools/make_katamari_tomls.py': f'tools/make_{port}_tomls.py',
        'dist/switch/katamari-nx': f'dist/switch/{port}-nx',
        'docs/katamari-notes.md': 'docs/katamari-notes-reference.md',
    }
    for a, b in rename.items():
        pa, pb = os.path.join(ROOT, a), os.path.join(ROOT, b)
        if os.path.exists(pa):
            shutil.move(pa, pb)
    subs = [
        (r'KATAMARI_BUILTIN_TEXT', f'{upper}_BUILTIN_TEXT'),
        (r'KATAMARI_PLAYER_TEXT', f'{upper}_PLAYER_TEXT'),
        (r'KATAMARI_BUILTIN_CONFIG', f'{upper}_BUILTIN_CONFIG'),
        (r'kKatamariBuiltInConfig', f'k{camel}BuiltInConfig'),
        (r'kKatamariPlayerConfig', f'k{camel}PlayerConfig'),
        (r'katamari_builtin_config', f'{port}_builtin_config'),
        (r'katamari_switch_defaults', f'{port}_switch_defaults'),
        (r'katamari_switch\.toml', f'{port}_switch.toml'),
        (r'src/katamari_keys\.cpp', f'src/{port}_keys.cpp'),
        (r'/switch/katamari-nx/', f'/switch/{port}-nx/'),
        (r'katamari-nx\.nro', f'{port}-nx.nro'),
        (r'"Beautiful Katamari"', f'"{title}"'),
        (r'katamari\.toml', f'{port}.toml'),
        (r'tools/switch/icon/katamari_icon\.jpg', f'tools/switch/icon/{port}_icon.jpg'),
        (r'/switch/katamari_nx/', f'/switch/{port}_nx/'),
    ]
    files = ['app/CMakeLists.txt', 'app/src/renut_app.h', f'app/src/{port}_keys.cpp', f'app/src/{port}_builtin_config.h.in',
             'app/src/renut_engine/dlc_install.cpp', 'app/src/renut_engine/gpu/banjo_renut_deko3d.cpp',
             'app/cmake/banjo_renut_gpu.cmake', f'app/{port}_switch.toml', f'app/{port}_switch_defaults.toml',
             'tools/run_ryujinx.ps1', 'tools/run_ryujinx_rdc.ps1', 'tools/run_pc.ps1', 'tools/run_pc_verify.ps1',
             'tools/package_switch.ps1', 'tools/gate_ryujinx.ps1', 'tools/build_switch_release.bat',
             f'tools/make_{port}_tomls.py', 'tools/make_test_toml.py', 'tools/build_pc.bat']
    for rel in files:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print('not found:', rel)
            continue
        t = open(p, encoding='utf-8', errors='surrogateescape', newline='').read()
        n = t
        for a, b in subs:
            n = re.sub(a, b, n)
        if n != t:
            open(p, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(n)
    print('done')


if __name__ == '__main__':
    main()

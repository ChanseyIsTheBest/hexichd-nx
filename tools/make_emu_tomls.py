#!/usr/bin/env python3
"""hexic2-nx (from pacman-nx): the emulator's test tomls in out/emu, made from the package's tomls (tools/make_hexichd_tomls.py) so they keep
its settings. Each adds the scripted pad, captures every 15 s and what the test needs:
  emu_verify.toml   configs/renut_verify.toml: every verify key on, the pad to gameplay
  emu_attract.toml  the same with no pad input: the game's title and attract loop
  emu_profile.toml  renut_play.toml: no diagnostics, the pad to gameplay, the sampling profiler on
  emu_ab.toml       renut_ab.toml: the in-run A/B, the pad to gameplay
  emu_game.toml     configs/renut_verify.toml: a whole game and its results screens
  emu_abv.toml      configs/renut_verify.toml: the A/B list flipping on 8 s halves, the pad to gameplay
  python tools/make_emu_tomls.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "switch", "hexichd-nx")
OUT = os.path.join(ROOT, 'out', 'emu')
# Hexic 2 (out/pc_runs/play1): START at the title, then A through the main menu and the difficulty menu into a game; A presses in a
# game only swap pieces. The emulator starts slower than the PC, so the presses begin later and there are more than it needs.
PAD = 'input_script = "60:START@1.5,70:A@0.4,80:A@0.4,90:A@0.4,100:A,110:A,120:A,130:A,140:A,150:A,160:A"\ninput_script_sticks = 170\n'
NO_PAD = 'input_script = ""\ninput_script_sticks = 0\n'
CAPTURES = 'nfsmw_captura_cada_s = 15\nnfsmw_captura_max = 60\n'
# A longer stretch of play, with the stick moving the cursor, for profiles.
GAME = 'input_script = "60:START@1.5,70:A@0.4,80:A@0.4,90:A@0.4,100:A,110:A,120:A,130:A,140:A,150:A,160:A"\ninput_script_sticks = 170\n'
# The request's check of each enhancement: its A/B target flipping with the verify keys on (0 differences either way). 8 s
# halves over the shipped list: a check of the picture and the counts, not a measurement (that is renut_ab.toml's, on the console).
AB_LIST = next(l for l in open(os.path.join(DIST, 'renut_ab.toml'), encoding='utf-8') if l.startswith('banjo_renut_ab_targets'))
TESTS = {
    'emu_abv.toml': (os.path.join('configs', 'renut_verify.toml'), PAD + CAPTURES + AB_LIST + 'banjo_renut_ab_s = 8\n'),
    'emu_verify.toml': (os.path.join('configs', 'renut_verify.toml'), PAD + CAPTURES),
    'emu_game.toml': (os.path.join('configs', 'renut_verify.toml'), GAME + CAPTURES),
    'emu_attract.toml': (os.path.join('configs', 'renut_verify.toml'), NO_PAD + CAPTURES),
    # Shipping conditions (no guard, no verify keys), a whole game and its results, the stack sampler on and nothing else.
    'emu_profile.toml': ('renut_play.toml', GAME + CAPTURES + 'switch_profile_stacks = true\n'),
    'emu_ab.toml': ('renut_ab.toml', PAD),
    # rr6-nx's strip fix (A/B 77), as the request tests it: whole buffers off, the fix on and off.
    'emu_strip_on.toml': (os.path.join('configs', 'renut_verify.toml'),
                          PAD + CAPTURES + 'banjo_renut_whole_buffers = false\nhexichd_strip_markers = true\n'),
    'emu_strip_off.toml': (os.path.join('configs', 'renut_verify.toml'),
                           PAD + CAPTURES + 'banjo_renut_whole_buffers = false\nhexichd_strip_markers = false\n'),
    # The census of banjo-nx's porting guide, section 2.
    'emu_census.toml': ('renut.toml', PAD + CAPTURES + 'banjo_renut_diag_fast_census = true\nbanjo_renut_diag_shadow_census = true\n'
                                                       'banjo_renut_diag_unleashed_census = true\nbanjo_renut_diag_draw_kinds = true\n'),
    # The start's "[boot]" line and leaving from the main menu's last item, as the user's console run: the toml the SD folder ships.
    'emu_exit.toml': ('renut.toml', 'input_script = "60:START@1.5,72:DOWN@0.3,75:DOWN@0.3,78:DOWN@0.3,81:DOWN@0.3,84:DOWN@0.3,88:A@0.4,94:A@0.4,100:A@0.4"\n'
                                    'input_script_sticks = 0\nnfsmw_captura_cada_s = 5\nnfsmw_captura_max = 60\n'),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, (source, extra) in TESTS.items():
        lines = open(os.path.join(DIST, source), encoding='utf-8').read().split('\n')
        keys = {l.split('=', 1)[0].strip() for l in extra.split('\n') if '=' in l}
        kept = [l for l in lines if not ('=' in l and l.split('=', 1)[0].strip() in keys)]
        # Before the first [table]: a key after one belongs to that table and the game never reads it.
        at = next((i for i, l in enumerate(kept) if l.startswith('[')), len(kept))
        kept[at:at] = ['# tools/make_emu_tomls.py'] + extra.rstrip('\n').split('\n') + ['']
        with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(kept).rstrip('\n') + '\n')
        print(name, 'from', source, 'keys at line', at + 2)


if __name__ == '__main__':
    main()

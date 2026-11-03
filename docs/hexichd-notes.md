# hexichd-nx notes

Hexic HD (title 584107D1, Xbox Live Arcade, XDK 2.0.1884, Title Update 1 to 2.0.1885) on the PC and the Nintendo Switch, from hexic2-nx's clean state and its general fixes. Nothing from Hexic 2 carries over untested.

## The game

- `default.xex` 1.2 MB, image 2,785,280 bytes with the update, load address `0x92000000`. Sections: `.rdata 92000400-92042D94`, `.pdata 92042E00-9204CAE0`, `.text 9204D000-922526E4`, `.data 92253000-922773D0`, `.idata 92278000`.
- The patch applies: "base version: 2.0.1884.0, new version: 2.0.1885.0".
- `.swf`: `HexicDeluxe.swf` (CWS v6, 1280x720, 60 fps, 427 frames, 124 KB of actions, 279 sprites, 29 sounds, 12 lossless bitmaps) and `HexicHDLoading.swf` (CWS v7, 749 frames). `KeyMap_HXIC.xml` names screen states. The image has no player's name in its strings, but it does name these two files, so the game and its interface look to run inside a Flash player in `default.xex`. **To confirm on the first run.**
- Music: 8 `.wma` at the folder root (WMA v2 `0x161`, 44.1 kHz stereo, 192 kbps, block align 8917, one packet span). The image holds their names as UTF-16 `game:\` paths at `0x9203DD60`, read by `sub_920510A0` only. That function calls `sub_921CF460`, `sub_921CF440`, `sub_921CF500` and `sub_921CF470`, small wrappers of `XMsgStartIORequest` next to each other. It looks like the XMP title playlist route Hexic 2 uses, which `sdk/src/kernel/xam/apps/xmp_app.cpp` and `sdk/src/audio/wma_player.cpp` serve. **Not yet heard: to test.**

## Code generation (2026-11-04)

- Config: `app/renut_config.toml`. `0x921B54E8` is a function the generator's first run asked for (`app/config/renut_funcs.toml`).
- **setjmp / longjmp** by shape, each the only one: setjmp `0x922133C0`, longjmp `0x922132A0`.
- **memcpy** `0x920A9A90` (first instructions as Hexic 2's, 243 calls), **memset** `0x920A5AB0` (37 of 37 words as Hexic 2's, 155 calls).
- **Pointer and gap sweeps**: 40 entries, of which 3 are not functions and were removed, with the reason in `app/overrides.toml` (`tools/override_labels_check.py`): `0x920AF40C`, `0x92216678`, `0x920A3A38`. 37 remain.
- **Wide scan** (`tools/wide_pointer_scan.py`): 8 hits, none a missing function (save and restore helpers reached mid-way, import thunks' words).
- **Jump tables** (`tools/switch_check.py --gen app/generated`): truncated 0, wrong targets 0, missed 0. 3 have no bound in the code, 2 odd shapes.

### Codegen options: the register diet

All on, as Hexic 2. `tools/non_argument_audit.py app/generated --noreturn=922132A0`: 64 ENTRY and 2 RET functions kept (`tools/diet_keep_list.py`).

`tools/read_before_write.py` on code generated WITH the options: 18 reports. 7 are setjmp's callers' `env.*` copies and setjmp itself, handled by the generator. The other 11 each save what they read in their prologue (each `__savegprlr` entry checked against the registers read), so those are paths a state machine never takes. **No `share_registers` needed.**

## Renut at XDK 2.0.1884 (2026-11-04)

Worked example: rr6-nx at 2.0.2135 (`docs/rr6-notes.md`, "Renut at XDK 2.0.2135").

- **State tables** (`tools/renut_state_tables.py`): render `0x92254438` x97, sampler `0x922548C8` x20. N&B's rows 96-100 have no partner, and row 57 is a state N&B lacks: Ridge Racer 6's shape exactly.
- **Pairs** (`tools/d3d_propagate.py`, `out/renut_map/rr6_to_hd.json`): 1,823 with Ridge Racer 6, 8 conflicts. The libraries are not in the same link order.
- **Import**: `tools/hd_import_rr6.py` copies rr6-nx HEAD's Direct3D layer and renderer files, renaming `rr6_` keys to `hexichd_`. `tools/renut_hook_remap_hd.py --apply`: 260 lines moved.
- **Data**, measured: `VdGlobalDevice`'s slot `0x92000548` (the image's only word `0xFFCAE000`); caps `0x92002E80` and format table `0x92002408` (RR6's bytes, one match each); the build qword `0x92254A20` from `sub_920C0CE0` (`0x0002000007604000`: the library says 2.0.1888).
- **Not linked here** (a search of the code by the fields they use): `DrawIndexedVertices`, `SetIndices`, the index buffer's Create / Lock / Unlock, `GetRenderTarget`, `GetDepthStencilSurface`. `+12508`, where the index buffer would be, is read only by `sub_920C1420`.
- **Linked here, not in Ridge Racer 6** (Katamari's shapes, `tools/renut_sigmatch.py`, `out/renut_map/sigmatch_kat.txt`; arguments read from the code):
  - `BeginTiling` `0x920B9178` and `EndTiling` `0x920B94A0`: the full public form, as Katamari's. Three game callers each: the game's own render functions.
  - `SynchronizeToPresentationInterval` `0x920B4CA0` and `Swap` `0x920B4E10`: the game calls them directly as well as through `Present`.
  - `AcquireThreadOwnership` `0x920B2830`, `ReleaseThreadOwnership` `0x920B2870`.
  - `DrawIndexedVerticesUP` `0x9221D6C0`, the Flash renderer's one indexed draw. Its format argument is 0 for 16-bit and 1 for 32-bit.
  - `Suspend` `0x920B2880` and `Resume` `0x920B2918`: no-ops on Renut. They wait for the GPU and set a flag under a critical section at `+14000` that Renut's device does not initialise.
- **Device layout** (`tools/d3d_device_layout.py`, against RR6, `out/renut_map/layout_rr6.json`): the head and constants as RR6's (2,906 accesses, delta 0 to `0x494`; `0x2880-0x28A0` too), then -20 from `0x28C0`, -24 from `0x2CA0`, -32 from `0x34D0`, -36 from `0x4FD4`, -40 from `0x5030`. The real allocation is `0x5080` (`li r3,20608`). rr6's `d3d.h` keeps Katamari's layout where only Renut reads it, so the first build keeps it too and the game's reads decide: `tools/hd_lib_census.py` lists the unhooked functions the game calls with the fields they use.

## Open items

See `docs/progress-log.md`.

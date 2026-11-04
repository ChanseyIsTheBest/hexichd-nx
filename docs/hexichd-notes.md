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

## First runs on the PC (2026-11-04)

What stood between the first link and gameplay on Renut, in order:

- **A crash on the emulated GPU** after about 4 s, `0xC000008F` (float inexact) in the XAudio callback. Ridge Racer 6 Recomp's `SDK-NOTES.md`, item 1: the SDK's host threads enter guest code with no guest FP state, so the first flush-mode toggle unmasks FP exceptions. Fixed where those threads start, `XHostThread::Execute`, which also covers the graphics interrupt thread.
- **`renut.cfg`.** Renut on the PC waits in `PathSetupWizard` unless that file is beside the exe (pacman-nx's notes). It is in the build folder, not in git, so a fresh build tree needs it. The symptom is a process alive with a log that stops at "Renderer:".
- **No shaders.** The game assembles 3 shaders from text at run time (`sub_92055060`: the first is `vs.1.1`), with D3DX's assembler linked in. Until those are captured (`app/out/pc/shader_capture`) and a PC build translates them, every draw is skipped: "DRAWS NOT DRAWN".
- **No picture.** `Swap` and `EndTiling` are Katamari-form hooks that took the game's own textures, where rr6-nx's `Resolve` goes through their shadows (`Rr6TextureShadow`). Both now do.
- **The frame squashed into the top 256 lines.** The game never calls `SetViewport`. The surface it binds is one tile tall, and real `BeginTiling` and `EndTiling` end with `SetViewport(0x92002514)`, a constant meaning the whole frame. rr6-nx's `kFullViewport` was 0, since that game never tiles, so the call did nothing here.
- **No music.** The game starts it only on notification `0x0A000003` (the title has playback control) with a non-zero value (`sub_9204E068`). A console announces that; the SDK sent it only when a game changed the controller. `RegisterNotifyListener` now sends it to the first listener with the XMP area in its mask (47 here). It first plays `Oilyn.wma` as a one-song playlist, which is what `sub_920510A0` asks for.

## The coloured background hexagons are real

**The emulated GPU is wrong here and Renut is right.** The user's console screenshots show background hexagons lit cyan and yellow-green. Renut draws them. The emulated GPU, on both Vulkan and Direct3D 12, leaves them grey (1 or 2 of about 40 captures coloured, all title frames).

For the record, as it cost about an hour: I took this for a Renut bug because the reference disagreed. Ruled out by test, before the console shots arrived: frame rate (capped at 60), the non-CPU enhancements, device snapshot deltas, the stream cache, card proofs, and a late upload of the colour table. What the effect is, from draw logs and skipping classes of draws: 256x256 bitmaps drawn through the hexagon stencil mask, with Flash's colour transform. `texture × c0 + c1`, with `c0 = 0.398` and `c1 = (0.273, 0.508, 0.594)` on a white texel, gives exactly `(171, 231, 253)`. I did not find why the emulated GPU drops them, and it is not needed for this port.

Every way of running the emulated GPU was tried, at the user's suggestion, on the same scripted path (`out/pc_runs/ref_*`): Direct3D 12 on the NVIDIA GPU with `render_target_path_d3d12=rov` and `rtv`, Vulkan on it with `render_target_path_vulkan=fsi` and `fbo`, and earlier Direct3D 12 on the AMD adapter. None draws the coloured hexagons; their coloured captures are the title's falling gems only. As all the render paths lose them alike, the cause is probably not stencil or EDRAM handling, and the guest may take another route under the emulated GPU. That is a guess, not tested.

So **the emulated GPU is not a safe reference for this game's masked bitmaps, in any mode.** Console shots outrank it.

Flash's colour table, also from that work: `sub_9209B100` keeps up to 1024 de-duplicated colours in a 1024x1 texture, `sub_9209AF80` reads an entry on the CPU and writes it inline to pixel shader constant c2 at `device+6048`.

## Census (banjo-nx's porting guide, section 2)

From `out/emu_runs/emu_census`, deko3d in Ryujinx:

| What the guide asks | This game |
|---|---|
| Where draws come from | Direct calls, about 1,180 draws a frame in gameplay. No recorded command buffers |
| Indexed | 0 %: quad lists through the game's own vertex buffers, with `DrawVertices`. `DrawIndexedVerticesUP` once, `SetIndices` not linked |
| Whole buffers | 1.9 % of draws. Most come from ranges of a few large buffers, unlike Hexic 2's 96 % |
| Fast path | 99.4 % replayed, 0.3 % with no state change (Flash changes a texture or constant for nearly every shape) |
| Texture slots | 95.8 % answered by the memo |
| Shaders | 15: 2 vertex and 10 pixel containers (version `0x0E`) in the image, 1 vertex and 2 pixel assembled at run time. 15 compiled, 0 failed |
| Masks | Stencil, incremented and decremented around each mask, with colour writes off |
| Render size | 1280x720 at 4x MSAA in 3 tiles of 256, 256 and 208 lines. Handheld is 1x, docked 1.5x (1920x1080), with nothing trimmed |

## What rr6-nx's fixes mean here

Taken with its renderer, and what each means here:

- `hexichd_alpha_near_one`: the alpha test was at always in all 3,000 draws logged from one scene (colour control `0x87000007`). Other scenes were not logged.
- `hexichd_user_clip_plane`: no game caller. `SetClipPlane`'s one caller is the library's own `sub_920B8A98`.
- `hexichd_strip_markers`: the census counts 0 indexed draws, so it has nothing to act on.
- `hexichd_fetch_over_pointer`: matches the hardware, where a null `SetTexture` leaves the fetch constant.
- `hexichd_fog_nan_zero`: **not checked on this game.** It zeroes NaNs in constant registers 21 and 22, which were Ridge Racer 6's fog values.
- `hexichd_depth_covers_colour`: can apply, as the surfaces are tile-sized.

## The game's gamma ramp: for the user's decision

The XDK loads its default ramp at the first `Swap` (`sub_920C1128`, called from `sub_920B4E10`), through `sub_920B88B0` or `sub_920B8940` by the back buffer's format. On Renut that function does not run: its device stores the corrected ramp at creation, `[64]=193 [128]=462 [255]=1023`, and `banjo_renut_game_gamma` applies it at scan-out.

Measured on the static panels against the emulated GPU (`out/pc_runs/gamma_on`, `gamma_off`, `ref_d3d12_rov`). The panels do not move, so pixels can be compared directly:

| Point | Off | **On** | Emulated GPU |
|---|---|---|---|
| (200, 300) | 22, 18, 54 | 9, 7, 38 | 9, 7, 38 |
| (200, 600) | 53, 50, 84 | 37, 34, 69 | 37, 34, 69 |
| (1060, 60) | 220, 223, 228 | 216, 219, 225 | 216, 219, 225 |
| (1060, 300) | 176, 177, 193 | 167, 168, 186 | 167, 168, 186 |
| (1060, 500) | 116, 115, 145 | 102, 101, 133 | 102, 101, 133 |
| (1060, 650) | 72, 70, 104 | 56, 54, 90 | 56, 54, 90 |

On, every sampled point is exact. Off, darks are up to 16 levels too bright. It changes the picture, so **the default stays off** and `configs/renut_game_gamma.toml` turns it on: the user's decision.

## Open items

See `docs/progress-log.md`.

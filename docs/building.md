# Building hexichd-nx

You need your own copy of the game: the code generator and the shader tools read it. Nothing made from it is committed
(`.gitignore`): `app/assets`, `app/generated`, `out/`, `app/out/`.

## Tools

Windows; LLVM clang and the Visual Studio Build Tools (CMake and Ninja) for the PC build (`tools/pc_env.bat` names the
paths); devkitA64, libnx and deko3d from [devkitPro](https://devkitpro.org) for the Switch; Python 3 with `xxhash` and
`Pillow`. The deko3d host tools (`out/deko3d_tools`: SPIRV-Cross and the PC uam) come from `tools/deko3d_build_tools.sh`.

## 1. The game

Extract the game's PIRS package and Title Update 1 with `tools/stfs_extract.py`, copy the update's `default.xexp` beside
`default.xex`, and make `app/assets` a junction to that folder (no second copy). Codegen takes the patched image.

## 2. The PC build: code generation and the shader translator

```bat
tools\build_host.bat
tools\build_pc.bat
```

The PC build runs the code generator (`app/renut_manifest.toml`), the post-codegen passes (`tools/post_codegen.py`) and
Renut's XenosRecomp over `out/renut_shader_dump`. Run it with `tools/run_pc.ps1`.

## 3. The shaders

```bash
python tools/rr6_shader_dump.py --image out/renut_image.bin --out out/renut_shader_dump
```

That takes the 12 version `0x0E` containers in the image. The game assembles 3 more from text at run time (`sub_92055060`,
docs/hexichd-notes.md), so they come from a PC run's capture: `app/out/pc/shader_capture`, which the PC build adds to
`out/renut_shader_dump`. Then:

```bat
powershell -File tools\switch_shaders.ps1
python tools\hexic_shader_files.py --image out\renut_image.bin --game app\assets --shaders out\renut_shader_dump --out out\hexic_shader_files.json
python tools\renut_release_shaders.py
```

`switch_shaders.ps1` translates all of them to GLSL and makes the everyday build's files (`app/out/renut_switch`, every
shader built into the NRO). `hexic_shader_files.py` says where each shader is in the game's own files, and which are in none of
them. `renut_release_shaders.py` makes the release build's (`app/out/renut_switch_release`: the shader table without SPIR-V, the
shaders in none of the game's files, built in, and `sd/deko3d_glsl.bin` to put next to the NRO for tests). `BANJO_CENTROID=0` (or
`switch_shaders.ps1 -NoCentroid`) translates without centroid sampling.

## 4. The Switch build

The everyday build (`app/out/switch`, every shader built in, no LTO):

```bat
tools\build_switch.bat
```

The released NRO, in folders of their own (`BUILD_DIR` and `CMAKE_EXTRA` of `tools/build_switch.bat`):

1. **Instrumented:** `-DBANJO_PGO=generate` in `app/out/switch-pgo-gen` (no LTO needed: GCC instruments before its inliner). Play it: it writes `pgo/banjo_pgo_<N>.stream` next to
   the NRO every 2 minutes, at HOME and at exit.
2. **Merge** on the PC that built it (the streams name its folders): `python tools/pgo_merge.py <folder with the
   streams>` fills `pgo/` (it stops if `pgo/` already has `.gcda` files: move them aside first).
3. **Optimised:** `-DBANJO_PGO=use -DBANJO_SWITCH_LTO=ON -DBANJO_RENUT_RELEASE_SHADERS=ON`. `tools\build_switch_release.bat` does this one. It carries only the
   game shaders that are in none of the game's files and reads `deko3d_glsl.bin` beside itself. `pgo/` in this repository is the released
   build's profile, collected in the Ryujinx emulator. A function changed
   since the instrumented build keeps no profile.

Keep the temporary folder's path free of spaces (GCC's parallel LTO link writes a makefile with it unquoted), and never
run two of these builds at once: they share the SDK's archives in `sdk/out/switch-arm64`.

The fixed settings are `app/hexichd_switch_defaults.toml`, compiled in; the player's are `app/hexichd_switch.toml`,
written next to the NRO as `hexichd.toml` when it is missing. A key added to `hexichd.toml` overrides a fixed one (the
test runs use that: `tools/run_ryujinx.ps1 -Toml <file>`).

## 5. The installer

[hexichd-nx-installer](https://github.com/ChanseyIsTheBest/hexichd-nx-installer) makes the same `deko3d_glsl.bin` in the browser. For a new
release, run its `test/release_node.mjs` with `out/hexic_shader_files.json` (its README). Its `wasm/renut_hlsl` must be rebuilt after a
change to the translator (`app/thirdparty/reblue-XenosRecomp`, `tools/renut_hlsl_frontend.cpp`): its `wasm/src/deko3d/build_wasm_deko3d.sh`.

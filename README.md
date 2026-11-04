<div align=center>

<img src="tools/switch/icon/hexichd_icon.jpg" alt="Hexic HD" width="30%">

</div>
<h1 align=center>Hexic HD — Nintendo Switch port</h1>

A native Nintendo Switch port of the Xbox Live Arcade game **Hexic HD** (Carbonated Games and Microsoft, 2005), with its Title
Update 1.

It's not an emulator. The PowerPC code of the game's `default.xex`, with the title update applied, is statically recompiled to
C++ with [ReXGlue](https://github.com/rexglue/rexglue-sdk) and compiled for the Switch, and the game's Direct3D calls are drawn
directly on the Switch GPU's own API, deko3d, by [reNut](https://github.com/masterspike52/reNut)'s Direct3D-level renderer.

> [!NOTE]
> You need your own copy of the game, the Xbox 360 package (`Content/<profile>/584107D1/000D0000`), **and its Title Update 1**
> (`Content/0000000000000000/584107D1/000B0000`).

## How to install

1. Open the installer page: **https://chanseyisthebest.github.io/hexichd-nx-installer/**
2. Add your game and Title Update 1, each as its **package file** or a **folder** you extracted it into, together or one at a
   time. Then press **Create hexichd-nx.zip**. Everything runs in your browser and the game files never leave your computer: the
   page checks your copy, downloads the build and makes the shaders from your game's own files.
3. Extract the downloaded `hexichd-nx.zip` into `sdmc:/switch/`.

Your `hexichd-nx` folder should look like this:

```text
/switch/hexichd-nx/
  hexichd-nx.nro
  LICENSES.txt
  hexichd.toml              (your settings; written at the first start when it is missing)
  deko3d_glsl.bin           (the game's shaders, made from your copy)
  game_root/                (the game's files, and the title update's default.xexp)
```

The game adds `deko3d_shaders.bin` and `pipeline_list.bin` there as you play (the shaders compiled for the Switch GPU, and the
list of what it drew, so later sessions prepare it ahead).

Launch it with a game override (hold **R** while starting an installed title) or a forwarder. Album applet mode does not give
the game enough memory. If you use a forwarder, set it to a **39-bit address space**.

To build everything yourself instead, see [docs/building.md](docs/building.md).

> [!NOTE]
> **Updating:** open the installer page again, add your game and Title Update 1, and press **Create hexichd-nx-update.zip**. It
> holds the new `hexichd-nx.nro`, the shaders and the title update, so there is no need to copy the game again: extract it over
> your folder. Your `hexichd.toml` and your saves stay.

> [!CAUTION]
> **The first time you play** after installing or updating, the game compiles its shaders for the Switch GPU as it meets them,
> so **it can stutter for a moment** on new screens. They are saved next to the NRO and later sessions start smoothly.

## Controls

By default the face buttons work **by position, as on the Xbox 360 pad** the game was made for: the bottom button is the Xbox's
A, the right one is the Xbox's B, and so on.

<div align="center">

| Switch | Xbox 360 |
| --- | --- |
| B (bottom) | A |
| A (right) | B |
| Y (left) | X |
| X (top) | Y |
| ZR / ZL | RT / LT |
| R / L | RB / LB |
| + | Start |
| − | Back |
| Sticks / D-pad | Sticks / D-pad |

</div>

## Settings

`hexichd.toml`, next to the NRO, holds only your options. Everything else is built into the NRO.

<div align="center">

| Setting | Default | What it does |
| --- | --- | --- |
| `language` | `"auto"` | The Switch's language; or `english`, `japanese`, `french`, `german`, `spanish`, `italian`, `korean`, `tchinese`, `portuguese` |
| `input_xbox_layout` | `true` | Face buttons by position, as on an Xbox pad; `false` = by letter |
| `input_joycon_sideways` | `true` | Single Joy-Cons held sideways, one per player |
| `input_joycon_sideways_stick` | `true` | The single Joy-Con's stick turned for the sideways grip |
| `[input_p1]` | | Button mapping: the Switch buttons that press each Xbox button, e.g. `a = "B, ZR"` |

</div>

The game draws 1280x720: 720 lines in handheld and 1080 docked. If you delete `hexichd.toml`, the game writes the default one again at
the next start.

## Performance

The port runs at the console's stock clocks on three cores. On the console, on the first build, gameplay ran at 46-58 fps with the
main thread full: this game is a Flash title, at about 1,600 small draws a frame. The released build adds a round of work on that
thread (99 more machine-optimised functions, read-ahead in the display-list walkers, a faster value release, fewer checks per draw)
and PGO + LTO with a profile collected in an emulator. The released build's frame rate had not been measured on a console when this
was written.

## How it works

- **The game's code is translated, not emulated.** [ReXGlue](https://github.com/rexglue/rexglue-sdk) translates every function of
  the game's program to C++, which is then compiled for the Switch. ReXGlue also gives the game what it expects from an Xbox 360:
  its system, files, audio and controllers.
- **A Direct3D-level renderer on deko3d.** The game's Direct3D calls are replaced by
  [reNut](https://github.com/masterspike52/reNut)'s renderer (as the Banjo-Kazooie: Nuts & Bolts port adapted it), which draws them
  with [plume](https://github.com/renderbag/plume) on [deko3d](https://github.com/devkitPro/deko3d), the Switch GPU's own API: no
  GPU command stream is written or parsed and no EDRAM is modelled.
- **Shaders made from your copy.** 12 of the game's 15 shaders are in its executable, in an old container version (0x0E). The installer
  page applies the title update to your `default.xex`, takes them from the result and makes `deko3d_glsl.bin` in your browser: Renut's
  [XenosRecomp](https://github.com/hedge-dev/XenosRecomp) translates each one to HLSL, DXC compiles it to SPIR-V,
  [SPIRV-Cross](https://github.com/KhronosGroup/SPIRV-Cross) turns that into GLSL and banjo-nx's passes trim it. All 12 come out
  identical to the native tool chain's. The game assembles the other 3 at run time, so they are in none of its files; those 3 are built
  into the NRO. The console compiles each shader with [uam](https://github.com/devkitPro/uam) the first time it is used and keeps
  the result.
- **Fewer checks per draw.** Over six game modes (160 million draws), only 8 of the 39 chunks of the Direct3D device's state ever changed
  inside a frame, so a draw compares those and all 39 every eighth draw. If a state that test never saw does change inside a frame,
  up to 7 draws use the old state before the full compare corrects it. `hexichd_delta_hot_chunks = false` in `hexichd.toml` turns this off.
- **Machine-optimised functions.** 745 of the game's functions run as optimised machine copies (`tools/localize_native.py`), picked from
  console profiles and compared call by call with the generated originals on the PC. A few leave for another function on every call,
  so they could not be compared; they are kept because a console profile sampled them.
- **Hand-written functions.** The Flash value release and two display-list walkers' read-ahead: `app/src/cpu/hot/hand.txt` holds the
  console evidence for each.
- **PGO + LTO.** The released NRO is compiled as one program, with a branch profile collected by playing an instrumented build in
  the Ryujinx emulator: `pgo/` is that profile.

## Documentation

<div align="center">

| Document | What it explains |
| --- | --- |
| [docs/building.md](docs/building.md) | How to build the PC test build, the NRO and the shader files |
| [docs/hexichd-notes.md](docs/hexichd-notes.md) | The port step by step: findings in the game's code, each fix and how it was checked |
| [docs/optimising-functions.md](docs/optimising-functions.md) | How the game's functions are made faster |
| [docs/codegen-crash-fixes.md](docs/codegen-crash-fixes.md) | Code generation crashes other ports found |
| [docs/progress-log.md](docs/progress-log.md) | The work in order |

</div>

## Build

Windows, LLVM clang and the VS Build Tools for the PC build; devkitA64, libnx and deko3d from [devkitPro](https://devkitpro.org) for
the Switch; Python; and your own copy of the game for the code generator and the shaders. The whole process is in
[docs/building.md](docs/building.md).

<div align="center">

| Folder | Contents |
| --- | --- |
| `app/` | The game: hooks, renderer, settings, CMake project |
| `sdk/` | ReXGlue SDK with the Horizon layer and the code generator changes |
| `tools/` | Code generation steps, build and test scripts, shader tools, analysis tools |
| `pgo/` | The released build's branch profile |
| `dist/` | The settings of the test builds |
| `docs/` | Documentation |

</div>

## Credits

- **Carbonated Games and Microsoft** — creators of Hexic HD. This is an unofficial, fan-made port with no affiliation.
- **ChanseyIsTheBest** — this port.
- **[Tom Clay](https://github.com/rexglue/rexglue-sdk)** — the ReXGlue SDK, built on the work of the **[Xenia](https://xenia.jp)** team.
- **[StevensND](https://github.com/StevensND/nfsmw-nx)** — nfsmw-nx: the Switch layer of the SDK and much of the method; and
  [nfsmw-nx-installer](https://github.com/StevensND/nfsmw-nx-installer), which the installer page is built on.
- **[nebadasSwifty](https://github.com/nebadasSwifty/masseffect-nx)** — masseffect-nx.
- **[hedge-dev](https://github.com/hedge-dev/XenosRecomp)** — XenosRecomp, the Xenos shader translator.
- **reNut and [masterspike52](https://github.com/masterspike52/reNut)** — reNut's Direct3D-level renderer (reused with its author's
  permission).
- **[plume](https://github.com/renderbag/plume)** (from UnleashedRecomp), **[deko3d](https://github.com/devkitPro/deko3d)** and
  **[uam](https://github.com/devkitPro/uam)** by fincs, with SwitchWakerHD's uam patches.
- **[devkitPro](https://devkitpro.org) and [switchbrew](https://github.com/switchbrew/libnx)** — devkitA64 and libnx.
- The ports this one builds on and takes fixes from: [katamari-nx](https://github.com/ChanseyIsTheBest/katamari-nx), this port's base;
  [renut-nx](https://github.com/ChanseyIsTheBest/renut-nx) (banjo-nx), [pacman-nx](https://github.com/ChanseyIsTheBest/pacman-nx),
  vivapinata-nx, halo3-nx, rr6-nx (this XDK's device layout and the shadow objects),
  [feedingfrenzy-nx](https://github.com/ChanseyIsTheBest/feedingfrenzy-nx) (version 0x0E shader containers),
  [peggle1-nx](https://github.com/ChanseyIsTheBest/peggle1-nx), [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx),
  [battd_nx](https://github.com/ChanseyIsTheBest/battd_nx), [bejeweled3-nx](https://github.com/ChanseyIsTheBest/bejeweled3-nx), and the
  zuma ports; **NetherSX2_nx** by NaGaa95 (the four-core layout, MIT); and **Ridge Racer 6 Recomp** by Sirhalo23 (its BSD notice stays
  on anything taken from it).
- **[KhronosGroup](https://github.com/KhronosGroup/SPIRV-Cross)** — SPIRV-Cross.
- The other libraries listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Legal

No affiliation with Microsoft or Nintendo. This repository contains no game files and no code generated from the game. Users must
provide their own legally obtained copy. The released NRO holds the game's recompiled code but none of its data files, and everything
else made from your copy is made on your own computer. Running homebrew requires custom firmware, which violates Nintendo's ToS and
can get a console banned — your call.

Source code is provided under the GPL-3.0 License (see [LICENSE](LICENSE)), like the ports it builds on. The SDK keeps its
BSD-3-Clause license (see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

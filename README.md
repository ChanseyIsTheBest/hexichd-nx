<h1 align=center>Hexic HD — Nintendo Switch port</h1>

A native Nintendo Switch port of the Xbox Live Arcade game **Hexic HD** (Microsoft, 2005).

It's not an emulator. The PowerPC code of the game's `default.xex`, with Title Update 1 applied, is statically recompiled to
C++ with [ReXGlue](https://github.com/rexglue/rexglue-sdk) and compiled for the Switch, and the game's Direct3D calls are drawn
directly on the Switch GPU's own API, deko3d, by [reNut](https://github.com/masterspike52/reNut)'s Direct3D-level renderer.

> [!NOTE]
> You need your own copy of the game: its PIRS package and Title Update 1. This repository holds no game files and no code
> generated from the game.

The state of the port, what was measured and what is left: [docs/hexichd-notes.md](docs/hexichd-notes.md) and
[docs/progress-log.md](docs/progress-log.md).

## Install

Copy these into `sdmc:/switch/hexichd-nx/`:

```text
hexichd-nx.nro
hexichd.toml               (your settings; written at the first start when it is missing)
game_root/                (the package's files, with Title Update 1's default.xexp beside default.xex)
```

Launch it with a game override (hold **R** while starting an installed title) or a forwarder. Album applet mode does not give
the game enough memory.

## Controls

The face buttons work **by position, as on the Xbox 360 pad**: the bottom button is the Xbox's A, the right one the Xbox's B.
To use them by letter, set `input_xbox_layout = false` in `hexichd.toml`. Each player has a button map there too.

## Documentation

| Document | What it explains |
| --- | --- |
| [docs/building.md](docs/building.md) | How to build the PC test build, the NRO and the shader files |
| [docs/hexichd-notes.md](docs/hexichd-notes.md) | The port step by step: findings in the game's code, each fix and how it was checked |
| [docs/optimising-functions.md](docs/optimising-functions.md) | How the game's functions are made faster |
| [docs/codegen-crash-fixes.md](docs/codegen-crash-fixes.md) | Code generation crashes other ports found |
| [docs/progress-log.md](docs/progress-log.md) | The work in order |

## Credits

- **Microsoft and Carbonated Games** — creators of Hexic HD. This is an unofficial, fan-made port with no affiliation.
- **ChanseyIsTheBest** — this port.
- **[Tom Clay](https://github.com/rexglue/rexglue-sdk)** — the ReXGlue SDK, built on the work of the
  **[Xenia](https://xenia.jp)** team.
- **reNut and [masterspike52](https://github.com/masterspike52/reNut)** — reNut's Direct3D-level renderer (reused with its
  author's permission).
- The ports this one builds on and takes fixes from: katamari-nx (its base), banjo-nx, pacman-nx, vivapinata-nx, halo3-nx,
  rr6-nx, peggle1-nx, sa2-nx, battd_nx, bejeweled3-nx and the zuma ports; **NetherSX2_nx** by NaGaa95 (the four-core layout,
  MIT); and **Ridge Racer 6 Recomp** by Sirhalo23 (its BSD notice stays on anything taken from it).
- **[StevensND](https://github.com/StevensND/nfsmw-nx)** — nfsmw-nx: the Switch layer of the SDK and much of the method.
- **[nebadasSwifty](https://github.com/nebadasSwifty/masseffect-nx)** — masseffect-nx.
- **[hedge-dev](https://github.com/hedge-dev/XenosRecomp)** — XenosRecomp, the Xenos shader translator.
- **[plume](https://github.com/renderbag/plume)**, **[deko3d](https://github.com/devkitPro/deko3d)** and
  **[uam](https://github.com/devkitPro/uam)** by fincs, with SwitchWakerHD's uam patches.
- **[devkitPro](https://devkitpro.org) and [switchbrew](https://github.com/switchbrew/libnx)** — devkitA64 and libnx.
- **[KhronosGroup](https://github.com/KhronosGroup/SPIRV-Cross)** — SPIRV-Cross.
- The other libraries listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Legal

No affiliation with Microsoft or Nintendo. Users must provide their own legally obtained copy of the game, and everything made
from it (`app/generated/`, the shaders) is made on their own computer. Running homebrew requires custom firmware, which violates
Nintendo's ToS and can get a console banned — your call.

Source code is provided under the GPL-3.0 License (see [LICENSE](LICENSE)), like the ports it builds on. The SDK keeps its
BSD-3-Clause license (see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

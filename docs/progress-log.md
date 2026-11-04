# hexichd-nx progress log (AEST)

| Time | What |
|---|---|
| 2026-11-04 04:20 | Tree made from hexic2-nx's clean-base tag and its general fixes. First codegen: 75 files. |
| 04:30 | State tables: 97 + 20, RR6's shape. Pairs with RR6: 1,823. rr6-nx's Direct3D layer imported. |
| 04:55 | Hook remap applied: 260 lines moved. Device layout measured against RR6's. |
| 05:05 | Sweeps, jump tables and the register diet audited: no `share_registers`. memcpy and memset found. |
| 05:15 | Tiling, Swap, thread ownership, Suspend / Resume and the indexed UP draw bound. Waiting for the first PC build, after Hexic 2's. |
| 09:22 | First PC link. `app/out/pc` 715 MB, `sdk/out` 60 MB, `app/generated` 36 MB. |
| 09:24 | **Title screen on the emulated GPU**, after seeding the guest FP state on the SDK's host threads. |
| 09:43 | **Gameplay on Renut (Vulkan) on the PC**, after `renut.cfg`, the 3 run-time shaders, the textures' shadows at `Swap` and `EndTiling`, and the full-frame viewport constant. |
| 09:50 | Music starts, after the XMP controller notification. Not yet heard. |
| 10:33 | The coloured background hexagons, chased as a bug: the user's console shots show them as the real look. The emulated GPU is what misses them, in all its modes. All temporary logging removed. |
| 10:46 | First Switch build: NRO 26.2 MB, `app/out/switch` 1.6 GB, `sdk/out/switch-arm64` 39 MB. rr6-nx's console-test switches for plume left out. 15 shaders compiled, 0 failed. |
| 10:51 | **deko3d in Ryujinx**: title, tutorial and live gameplay with the coloured hexagons, no crash, verify reports all at zero differences, music started. |
| 11:25 | peggle1-nx's SDK fixes, at the user's request: leaderboards, guest sign-in, zero on decommit, players 3 and 4. Nothing new there for achievements or exit. |
| 11:51-12:11 | PC build with 1,897 copies. Six every-call runs: 516.9 M calls compared, 0 differences. 646 copies compared, 1,250 reached and never compared, 1 never reached: list cut to the 646. |
| 12:00 | The user asked for every post-codegen step on both games. The list-driven steps had empty lists, and `r1_local.py` took an empty list as every function. |
| 12:11-12:26 | Indirect call census (3 runs, 378 M calls: 67 sites promoted). `tools/form_choice.py`: four compiles of each of the 34 files, 9 minutes: 32 functions off the locals, 1,360 on the r1 mirror, 1,430 with dropped write-backs. |
| 12:33-12:53 | Regenerated, PC build. Six every-call runs: 378.0 M calls compared, 120.7 M not comparable, 0 differences, all 646 copies compared. The generated code's own checks 0 differences. |
| 13:01 | Switch build: NRO 31.5 MB. Hot-placement lists skipped: the user wants to try the console first. |
| 13:05 | **Console package**: `D:\hexic\builds\2026-11-04_1305_hexichd_console1`, NRO SHA-256 `F6819DF5F2FB1406...`, source `e958e480`. **SD folder** with both games and their files: `D:\hexic\sd_card\switch`. |
| 13:07 | That NRO in Ryujinx, shipping settings with the sampler: logo, menus, gameplay and the coloured hexagons draw; no crash. Start 12.5 s in the emulator. Render thread ahead of the game threads in the samples. |
| 13:10 | Exit test on the packaged NRO: `ServiceAm Exit` at 2:12, no crash log. A/B list: 30 added back, since a shipping run shows those draws (the census had the fast draw off). |
| 13:40-15:09 | The user's console profile: 46-58 fps, main thread 100 %. 745 copies, three hand-written natives, the shadow lookup cache, hot chunks, the language key, the short toml, the icon. PC guard, three runs: 131.6 M compared, 0 differences. Ryujinx guard: 650,726 compared, 0 differences. French in Ryujinx on the last NRO. SD folder updated. |
| 15:17 | **The user: stop improving, make the final PGO + LTO builds with emulator data, a web installer like Katamari's, and upload all four repos and the release NRO.** |
| 15:24-15:28 | `pacman-nx-installer` as the base. 12 version 0x0E containers in the image, 3 in none of the files. The translator's front end reads 0x0E and is rebuilt from this tree. The page's chain against the native one: 12 of 12 shaders the same text. |
| 15:36 | Instrumented NRO, 43.5 MB, no LTO, 1.8 GB tree. pacman-nx's built-in plus beside-the-NRO shader lookup added afterwards: 3 shaders built in, 12 beside. |
| 15:36-16:08 | Five PGO sessions in Ryujinx, no crash: Marathon twice (a script's mistake ran it again), Timed, Survival, the menus and options. 123 profile files, 2.5 MB. The instrumented tree removed to save disk. |
| 16:21 | **Final NRO**, PGO + LTO: 32.5 MB, 1.8 GB tree, 12 minutes. |

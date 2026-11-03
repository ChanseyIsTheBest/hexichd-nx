hexichd-nx: Hexic HD (Xbox 360, title 584107D1) on the Nintendo Switch
======================================================================

A ReXGlue static recompilation built from katamari-nx, which was built from banjo-nx: its SDK fork, its post-codegen CPU
passes and reNut's Direct3D-level renderer on plume's deko3d back end (no NVK, no PM4 ring, no EDRAM model). Your own game
files are needed; nothing of the game is in this package except the recompiled code.

Credits: reNut's renderer by masterspike52 (its author permits its reuse in these ports), katamari-nx, banjo-nx, pacman-nx,
vivapinata-nx, halo3-nx, rr6-nx, peggle1-nx, sa2-nx (input, CPU items), NetherSX2_nx by NaGaa95 (the four-core layout, MIT),
battd_nx (the GPU arena), bejeweled3-nx and the zuma ports (the hot-function method), Ridge Racer 6 Recomp by Sirhalo23
(BSD notice kept on anything taken from it). GPL-3.0 where the sources are.

SD card layout
--------------
sdmc:/switch/hexichd-nx/hexichd-nx.nro     the program
sdmc:/switch/hexichd-nx/hexichd.toml       settings, the only toml the NRO reads (see "The tomls")
sdmc:/switch/hexichd-nx/game_root/        the game package's files: default.xex, the .swf, .wma, .ttf, .xml and .png files, with
                                         Title Update 1's default.xexp beside default.xex (tools/stfs_extract.py extracts both)

The tomls
---------
The settings are compiled into the NRO (app/hexichd_switch_defaults.toml), and it reads one file over them: hexichd.toml.
A toml under any other name does nothing and gives no log, so to use one of these, copy it over hexichd.toml. Delete
hexichd.toml and the next start writes the player's short default one. A build made with -DHEXICHD_BUILTIN_CONFIG=OFF compiles
nothing in and reads renut.toml instead; tools/package_switch.ps1 names the package's copy to match.

In configs/:
renut.toml        the built-in settings with logs, profiler and diagnostics on: Renut on deko3d, 720 lines handheld and 1080
                  docked, every exact enhancement on, the items measured SLOWER ON THE CONSOLE in banjo-nx off. A package
                  carries it as hexichd.toml.
renut_play.toml   the same with the render-thread diagnostics off (for playing).
renut_ab.toml     the same with an in-run A/B list, 30 s halves, target 1 as the do-nothing control. Stay on one screen for
                  10+ minutes; the log's "[renut A/B]" lines give each target.
the others        options that change the picture, one key away from renut.toml each, for you to decide on, and test settings
                  (renut_verify.toml, renut_pgo.toml).

Cores
-----
The port runs on the three cores a homebrew launch gets. Four cores are optional and off: with banjo_forwarder_program_id
in hexichd.toml set to your forwarder's id, the NRO writes that forwarder's four-core NPDM (NetherSX2_nx's layout, CPU 0-3) to
sdmc:/atmosphere/contents/<id>/exefs/main.npdm, and the next launch has CPU 0-3 (the log's "[banjo] system core:" line says
whether the fourth core was granted). Delete that main.npdm to go back to three cores.

Profiling
---------
The ELF (hexichd-nx.elf) and the source snapshot (source_<commit>.tgz) are the ones this NRO was built from: a console profile
(rex_profile.log, switch_profile_stacks) maps to source lines with them. PACKAGE_NOTES.txt says how to turn one on.

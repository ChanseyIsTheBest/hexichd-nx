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
| 10:33 | The coloured background hexagons, chased as a bug: the user's console shots show them as the real look. The emulated GPU is what misses them. All temporary logging removed. |

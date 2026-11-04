@echo off
rem katamari-nx: the released NRO, in a build folder of its own (docs/building.md): LTO, the PGO profile in pgo/, only the game
rem shaders that are in none of its files inside (it reads deko3d_glsl.bin beside itself). tools\renut_release_shaders.py makes the files it builds with.
rem Output: app\out\switch-pgo-use\renut.nro
set "BUILD_DIR=%~dp0..\app\out\switch-pgo-use"
set "CMAKE_EXTRA=-DBANJO_PGO=use -DBANJO_SWITCH_LTO=ON -DBANJO_RENUT_RELEASE_SHADERS=ON -DBANJO_SWITCH_LTO_JOBS=6"
if "%JOBS%"=="" set "JOBS=10"
call "%~dp0build_switch.bat" %*

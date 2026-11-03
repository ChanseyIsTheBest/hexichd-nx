#!/bin/bash
# hexic2-nx (2026-11-03): runs Renut's XenosRecomp on each shader of a folder by itself and lists the ones that crash it or
# fail: one bad container stops the whole translator with no name in its output.
#   bash tools/xenos_each.sh <dump folder> <work folder>   (prints one line per shader that did not pass, then a count)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXE="$ROOT/app/out/pc/xenos_recomp/build/XenosRecomp/XenosRecomp.exe"
COMMON="$ROOT/app/thirdparty/reblue-XenosRecomp/XenosRecomp/shader_common.h"
DUMP="$1"
WORK="$2"
mkdir -p "$WORK"
one() {
  f="$1"
  n="$(basename "$f" .bin)"
  d="$WORK/$n"
  mkdir -p "$d/in"
  cp "$f" "$d/in/"
  out="$("$EXE" "$d/in" "$d/o.cpp" "$COMMON" 2>&1)"
  code=$?
  if [ $code -ne 0 ]; then
    echo "$n exit $code: $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-160)"
  elif echo "$out" | grep -q "Recompile failures"; then
    echo "$n failed: $(echo "$out" | grep -m1 'reason=' | cut -c1-160)"
  fi
  rm -rf "$d"
}
export -f one
export EXE COMMON WORK
ls "$DUMP"/*.bin | xargs -P 8 -I{} bash -c 'one "{}"'
echo "done: $(ls "$DUMP"/*.bin | wc -l) shaders"

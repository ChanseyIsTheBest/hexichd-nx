#!/usr/bin/env python3
"""hexic2-nx (2026-11-03, from vivapinata-nx's renut_port_viva.py and pacman-nx's renut_port_pacman.py): moves Renut's Direct3D
layer from Beautiful Katamari's layout (XDK 2.0.5632) to Hexic 2's (XDK 2.0.5426), after tools/renut_hook_remap_hexic2.py.

Measured (tools/d3d_device_layout.py, 670 same-shape function pairs, out/layout_kat.txt; docs/hexic2-notes.md): the head to the
ring is the same; the state tables have 100 render rows, not 101 (sub_9212F2F0 `cmplwi cr6,r30,400`); the constants start at
0x400, not 0x480 (`addi r27,r31,1024`); and from there every field is exactly 128 bytes below Katamari's, to the device's end
(0x5700 -> 0x5680, `li r3,22144` in sub_92123790). A multiple of 64, so the snapshot's chunks keep their shape.

Three kinds of edit:
  EDITS     exact (file, old, new) text pairs; a pair whose new text is there is skipped, one whose old text is missing reported.
  ANNOTATED every `katamari-nx: X->Y` line: its literal Y moves by -128.
  LITERALS  in the listed files, on lines not yet marked, literals in Katamari's device range that katamari-nx did not annotate
            because N&B's and Katamari's layouts agree there.

  python -I tools/renut_port_hexic2.py [--check]
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPU = os.path.join(ROOT, 'app', 'src', 'renut_engine', 'gpu')
MARK = 'hexichd-nx'
DELTA = -128

PAIR = re.compile(r'katamari-nx: ?((?:0x[0-9A-Fa-f]+|\d+)->(?:0x[0-9A-Fa-f]+|\d+)(?:, ?(?:0x[0-9A-Fa-f]+|\d+)->(?:0x[0-9A-Fa-f]+|\d+))*)')
ONE = re.compile(r'(0x[0-9A-Fa-f]+|\d+)->(0x[0-9A-Fa-f]+|\d+)')
HEX = re.compile(r'(?<![0-9A-Za-z_.])0x(2[789A-F][0-9A-Fa-f]{2}|3[0-9A-Fa-f]{3}|4[0-9A-Fa-f]{3}|5[0-7][0-9A-Fa-f]{2})(?:[uU])?(?![0-9A-Za-z_.])')
DEC = re.compile(r'(?<![0-9A-Za-z_.])(1[0-9]{4}|2[0-2][0-9]{3})(?![0-9A-Za-z_.])')
LINE_USE = re.compile(r'(\.(W|B|F|Q|H|SetW|SetB|SetF|SetQ|SetH|U32|F32)\(|\bd\.bytes\b|device \+ 0x|kDeviceOffset\w+ =|kDeviceOffsetsMinusOne|constexpr u32 k\w+ = 0x[0-9A-F]{4};|Video::NoteGameGamma|Swap\(device, front_buffer)')
SKIP = re.compile(r'static_assert|0x3FFF\b|0x2A23B9')
LITERAL_FILES = ['d3d/d3d_native_state.cpp', 'd3d/hooks/device.cpp', 'd3d/hooks/state.cpp', 'd3d/hooks/draw.cpp', 'd3d/d3d.h', 'render/draw.cpp']


def hx(y):
    return y + DELTA if 0x480 <= y <= 0x5700 else None


EDITS = [
    # 1. Guest data addresses (tools/d3d_data_addrs_hexic2.py, tools/renut_state_tables.py).
    ('d3d/d3d_native_state.cpp', 'kRenderStateTable = 0x82AD8E48;', 'kRenderStateTable = 0x9258BA60;  // hexic2-nx: tools/renut_state_tables.py, 100 rows;'),
    ('d3d/d3d_native_state.cpp', 'kSamplerStateTable = 0x82AD9308;', 'kSamplerStateTable = 0x9258BF10;  // hexic2-nx: tools/renut_state_tables.py;'),
    ('d3d/d3d_native_state.cpp', 'kFormatTable = 0x820FA9D0;', "kFormatTable = 0x9200DCA0;  // hexic2-nx: Katamari's 128 bytes, word for word;"),
    ('d3d/hooks/resource.cpp', 'kFormatTable = 0x820FA9D0;', "kFormatTable = 0x9200DCA0;  // hexic2-nx: Katamari's 128 bytes, word for word;"),
    ('d3d/hooks/device.cpp', 'kGlobalQwordVa = 0x82AD93F8;', 'kGlobalQwordVa = 0x9258C068;  // hexic2-nx: the build qword 2.0.5426 (QFE 2);'),
    ('d3d/hooks/device.cpp', 'kVdGlobalDeviceImportSlot = 0x82000750;', 'kVdGlobalDeviceImportSlot = 0x920007C4;  // hexic2-nx: D3D_LockResource sub_92115C68, its first two references;'),
    ('d3d/hooks/device.cpp', 'kDeviceCapsVa = 0x820FC1F8;', "kDeviceCapsVa = 0x9200E8C8;  // hexic2-nx: Katamari's 304 bytes, word for word;"),
    ('d3d/hooks/draw.cpp', 'kFullViewport = 0x820FAEB4;', "kFullViewport = 0x9200DBFC;  // hexic2-nx: Katamari's 24 bytes, word for word;"),
    ('d3d/hooks/resource.cpp', 'kGameNoLargePagesVa = 0x8315DFE0;', 'kGameNoLargePagesVa = 0x92623084;  // hexic2-nx: XPhysicalAlloc sub_920F7B40;'),
    ('d3d/hooks/resource.cpp', 'kHiZOwnerVa = 0x8315E830;', 'kHiZOwnerVa = 0x926233EC;  // hexic2-nx: CreateSurface sub_921181A0, Destroy sub_92115A80;'),
    ('d3d/hooks/resource.cpp', 'REX_IMPORT(__imp__sub_824CAB98, GameXMemFree', 'REX_IMPORT(__imp__sub_920F76D8, GameXMemFree'),
    ('d3d/hooks/device.cpp', 'REX_IMPORT(__imp__sub_824C1C10, GuestGetCurrentThreadId', 'REX_IMPORT(__imp__sub_923C5520, GuestGetCurrentThreadId'),
    # 2. The state tables: XDK 2.0.5426's render table has 100 rows (N&B's and Katamari's last, Buffer2Frames, is not in this XDK).
    ('d3d/d3d_native_state.cpp', '''  for (u32 i = 0; i < kRenderStates; ++i) {
    device.SetW(off::SetRenderStateCall + i * 4, TableWord(kRenderStateTable, i, 1));
    device.SetW(off::GetRenderStateCall + i * 4, TableWord(kRenderStateTable, i, 0));
    kRenderStateFns[i](device, TableWord(kRenderStateTable, i, 2));
  }''', '''  // hexic2-nx: sub_9212F2F0 walks 100 rows (`cmplwi cr6,r30,400`), the sampler table right after them.
  for (u32 i = 0; i < kGuestRenderStates; ++i) {
    device.SetW(off::SetRenderStateCall + i * 4, TableWord(kRenderStateTable, i, 1));
    device.SetW(off::GetRenderStateCall + i * 4, TableWord(kRenderStateTable, i, 0));
    kRenderStateFns[i](device, TableWord(kRenderStateTable, i, 2));
  }'''),
    ('d3d/d3d_native_state.cpp', 'constexpr u32 kRenderStates = 101;', "constexpr u32 kRenderStates = 101;\nconstexpr u32 kGuestRenderStates = 100;  // hexic2-nx: this XDK's table"),
    # 3. The device's front (d3d_native.h off::, d3d.h Device): sub_9212F2F0 (the render table's setters at +0x40 + 4 i, getters +0x220, the sampler's +0x1D0 and +0x3B0, the constants at +0x400).
    ('d3d/d3d_native.h', '''constexpr u32 SetRenderStateCall = 0x40;   // [101]
constexpr u32 SetSamplerStateCall = 0x1D4; // [20]
constexpr u32 GetRenderStateCall = 0x224;  // [101]
constexpr u32 GetSamplerStateCall = 0x3B8; // [20]
constexpr u32 TextureFetch = 0x480;        // m_Constants.TextureFetch[26], 24 bytes each
constexpr u32 VertexFetch = 0x6F0;         // m_Constants.VertexFetch[18], 8 bytes each
constexpr u32 SurfaceInfo = 0x2880;        // m_DestinationPacket
constexpr u32 Color0Info = 0x2884;
constexpr u32 DepthInfo = 0x2888;
constexpr u32 WindowOffset = 0x28C0;       // m_WindowPacket
constexpr u32 WindowScissorTL = 0x28C4;
constexpr u32 WindowScissorBR = 0x28C8;
constexpr u32 ColorMask = 0x28DC;          // m_ValuesPacket
constexpr u32 DepthControl = 0x2934;       // m_ControlPacket
constexpr u32 BlendControl0 = 0x2938;
constexpr u32 ColorControl = 0x293C;
constexpr u32 HiControl = 0x2940;
constexpr u32 ClipControl = 0x2944;
constexpr u32 ModeControl = 0x2948;
constexpr u32 BlendControl1 = 0x2958;
constexpr u32 BlendControl2 = 0x295C;
constexpr u32 BlendControl3 = 0x2960;
constexpr u32 FenceCompletion = 0x2A90;    // -> the completed-fence word
constexpr u32 FenceTag = 0x2A9C;           // the current fence
constexpr u32 CommandBufferTagMask = 0x2AA0;  // Common bits a recorded buffer tracks
constexpr u32 TilePredication = 0x2AB4;    // SetPredication / SetCommandBufferPredication args
constexpr u32 RunPredication = 0x2AB8;
constexpr u32 Flags = 0x2ABC;              // bytes 0x2ABC-0x2ABF, see below
constexpr u32 Flags1 = 0x2ABD;
constexpr u32 Flags2 = 0x2ABE;
constexpr u32 Flags3 = 0x2ABF;''', '''// hexic2-nx: XDK 2.0.5426's layout (tools/renut_port_hexic2.py): 100 render states, the constants at 0x400, everything after
// them 128 bytes below Katamari's.
constexpr u32 SetRenderStateCall = 0x40;   // [100]
constexpr u32 SetSamplerStateCall = 0x1D0; // [20]
constexpr u32 GetRenderStateCall = 0x220;  // [100]
constexpr u32 GetSamplerStateCall = 0x3B0; // [20]
constexpr u32 TextureFetch = 0x400;        // m_Constants.TextureFetch[26], 24 bytes each
constexpr u32 VertexFetch = 0x670;         // m_Constants.VertexFetch[18], 8 bytes each
constexpr u32 SurfaceInfo = 0x2800;        // m_DestinationPacket
constexpr u32 Color0Info = 0x2804;
constexpr u32 DepthInfo = 0x2808;
constexpr u32 WindowOffset = 0x2840;       // m_WindowPacket
constexpr u32 WindowScissorTL = 0x2844;
constexpr u32 WindowScissorBR = 0x2848;
constexpr u32 ColorMask = 0x285C;          // m_ValuesPacket
constexpr u32 DepthControl = 0x28B4;       // m_ControlPacket
constexpr u32 BlendControl0 = 0x28B8;
constexpr u32 ColorControl = 0x28BC;
constexpr u32 HiControl = 0x28C0;
constexpr u32 ClipControl = 0x28C4;
constexpr u32 ModeControl = 0x28C8;
constexpr u32 BlendControl1 = 0x28D8;
constexpr u32 BlendControl2 = 0x28DC;
constexpr u32 BlendControl3 = 0x28E0;
constexpr u32 FenceCompletion = 0x2A10;    // -> the completed-fence word
constexpr u32 FenceTag = 0x2A1C;           // the current fence
constexpr u32 CommandBufferTagMask = 0x2A20;  // Common bits a recorded buffer tracks
constexpr u32 TilePredication = 0x2A34;    // SetPredication / SetCommandBufferPredication args
constexpr u32 RunPredication = 0x2A38;
constexpr u32 Flags = 0x2A3C;              // bytes 0x2A3C-0x2A3F (sub_92123CE8 `lbz r10,10812(r3)`)
constexpr u32 Flags1 = 0x2A3D;
constexpr u32 Flags2 = 0x2A3E;
constexpr u32 Flags3 = 0x2A3F;'''),
    ('d3d/d3d_native.h', 'constexpr u32 kTouchFetchBegin = 0x480, kTouchFetchEnd = 0x780, kTouchTailBegin = 0x2780;',
     'constexpr u32 kTouchFetchBegin = 0x400, kTouchFetchEnd = 0x700, kTouchTailBegin = 0x2700;  // hexic2-nx: -128'),
    ('d3d/d3d_native.h', 'TouchBits(0x2780, 0x300) | TouchBits(0x2DF4, 0x108);', 'TouchBits(0x2700, 0x300) | TouchBits(0x2D74, 0x108);  // hexic2-nx: -128;'),
    ('d3d/d3d.h', '''  be_u32 m_SetRenderStateCall[101];   // +0x0040
  be_u32 m_SetSamplerStateCall[20];   // +0x01D4
  be_u32 m_GetRenderStateCall[101];   // +0x0224
  be_u32 m_GetSamplerStateCall[20];   // +0x03B8
  u8 pad_0408[0x480 - 0x408];         // +0x0408
  Constants m_Constants;              // +0x0480
  be_f32 m_ClipPlanes[6][4];          // +0x2820
  DestinationPacket m_DestinationPacket;  // +0x2880
  WindowPacket m_WindowPacket;        // +0x28C0
  ValuesPacket m_ValuesPacket;        // +0x28CC
  ProgramPacket m_ProgramPacket;      // +0x2920
  ControlPacket m_ControlPacket;      // +0x2934
  u8 m_TessellatorPacket[84];         // +0x2964
  u8 m_MiscPacket[152];               // +0x29B8
  u8 m_PointPacket[32];               // +0x2A50
  u8 m_MaxAnisotropy[26];             // +0x2A70
  u8 m_ZFilter[26];                   // +0x2A8A
  u8 pad_2AA4[0x2B00 - 0x2AA4];       // +0x2AA4
  u8 private_[kDeviceAllocSize - 0x2B00];  // +0x2B00  CDevice private state''', '''  // hexic2-nx: XDK 2.0.5426: 100 render states, the constants at 0x400, all that follows 128 bytes below Katamari's.
  be_u32 m_SetRenderStateCall[100];   // +0x0040
  be_u32 m_SetSamplerStateCall[20];   // +0x01D0
  be_u32 m_GetRenderStateCall[100];   // +0x0220
  be_u32 m_GetSamplerStateCall[20];   // +0x03B0
  Constants m_Constants;              // +0x0400
  be_f32 m_ClipPlanes[6][4];          // +0x27A0
  DestinationPacket m_DestinationPacket;  // +0x2800
  WindowPacket m_WindowPacket;        // +0x2840
  ValuesPacket m_ValuesPacket;        // +0x284C
  ProgramPacket m_ProgramPacket;      // +0x28A0
  ControlPacket m_ControlPacket;      // +0x28B4
  u8 m_TessellatorPacket[84];         // +0x28E4
  u8 m_MiscPacket[152];               // +0x2938
  u8 m_PointPacket[32];               // +0x29D0
  u8 m_MaxAnisotropy[26];             // +0x29F0
  u8 m_ZFilter[26];                   // +0x2A0A
  u8 pad_2A24[0x2A80 - 0x2A24];       // +0x2A24
  u8 private_[kDeviceAllocSize - 0x2A80];  // +0x2A80  CDevice private state'''),
    ('d3d/d3d.h', '''static_assert(offsetof(Device, m_SetRenderStateCall) == 0x40);
static_assert(offsetof(Device, m_SetSamplerStateCall) == 0x1D4);
static_assert(offsetof(Device, m_GetRenderStateCall) == 0x224);
static_assert(offsetof(Device, m_GetSamplerStateCall) == 0x3B8);
static_assert(offsetof(Device, m_Constants) == 0x480);
static_assert(offsetof(Device, m_ClipPlanes) == 0x2820);
static_assert(offsetof(Device, m_DestinationPacket) == 0x2880);
static_assert(offsetof(Device, m_WindowPacket) == 0x28C0);
static_assert(offsetof(Device, m_ValuesPacket) == 0x28CC);
static_assert(offsetof(Device, m_ProgramPacket) == 0x2920);
static_assert(offsetof(Device, m_ControlPacket) == 0x2934);
static_assert(offsetof(Device, m_TessellatorPacket) == 0x2964);
static_assert(offsetof(Device, m_MiscPacket) == 0x29B8);
static_assert(offsetof(Device, m_PointPacket) == 0x2A50);
static_assert(offsetof(Device, m_MaxAnisotropy) == 0x2A70);
static_assert(offsetof(Device, m_ZFilter) == 0x2A8A);''', '''static_assert(offsetof(Device, m_SetRenderStateCall) == 0x40);
static_assert(offsetof(Device, m_SetSamplerStateCall) == 0x1D0);
static_assert(offsetof(Device, m_GetRenderStateCall) == 0x220);
static_assert(offsetof(Device, m_GetSamplerStateCall) == 0x3B0);
static_assert(offsetof(Device, m_Constants) == 0x400);
static_assert(offsetof(Device, m_ClipPlanes) == 0x27A0);
static_assert(offsetof(Device, m_DestinationPacket) == 0x2800);
static_assert(offsetof(Device, m_WindowPacket) == 0x2840);
static_assert(offsetof(Device, m_ValuesPacket) == 0x284C);
static_assert(offsetof(Device, m_ProgramPacket) == 0x28A0);
static_assert(offsetof(Device, m_ControlPacket) == 0x28B4);
static_assert(offsetof(Device, m_TessellatorPacket) == 0x28E4);
static_assert(offsetof(Device, m_MiscPacket) == 0x2938);
static_assert(offsetof(Device, m_PointPacket) == 0x29D0);
static_assert(offsetof(Device, m_MaxAnisotropy) == 0x29F0);
static_assert(offsetof(Device, m_ZFilter) == 0x2A0A);'''),
    # 4. The field map (render/draw.h) and the chain's layout.
    ('render/draw.h', '''  if (at < 0x480)
    return 0;
  if (at < 0x6F0)
    return kFieldFetch;
  if (at < 0x780)
    return kFieldVertexFetch;
  if (at < 0x2780)
    return 0;  // the float constants: by group (m_Pending)
  if (at < 0x2880)
    return kFieldBools;
  if (at < 0x28C0)
    return kFieldDest;
  if (at < 0x2968)
    return kFieldViewPackets;
  if (at >= 0x29C0 && at < 0x29C4)
    return kField29C0;
  if (at < 0x2A80)
    return kFieldMisc;''', '''  // hexic2-nx: every boundary 128 bytes below Katamari's (the constants at 0x400).
  if (at < 0x400)
    return 0;
  if (at < 0x670)
    return kFieldFetch;
  if (at < 0x700)
    return kFieldVertexFetch;
  if (at < 0x2700)
    return 0;  // the float constants: by group (m_Pending)
  if (at < 0x2800)
    return kFieldBools;
  if (at < 0x2840)
    return kFieldDest;
  if (at < 0x28E8)
    return kFieldViewPackets;
  if (at >= 0x2940 && at < 0x2944)
    return kField29C0;
  if (at < 0x2A00)
    return kFieldMisc;'''),
    ('render/draw.h', 'constexpr u32 kChainHeadChunks = 30;', 'constexpr u32 kChainHeadChunks = 28;  // hexic2-nx: the float constants at 0x700'),
    ('render/draw.h', 'constexpr u32 kChainTailBegin = 10112;', 'constexpr u32 kChainTailBegin = 9984;  // hexic2-nx: VertexShaderB at 0x2700'),
    ('render/draw.cpp', 'static_assert(FieldsOfRange(10112, 10600 - 10112) == (kFieldBools | kFieldDest | kFieldViewPackets));', 'static_assert(FieldsOfRange(9984, 10472 - 9984) == (kFieldBools | kFieldDest | kFieldViewPackets));  // hexic2-nx: -128'),
    ('render/draw.cpp', 'static_assert(FieldsOfRange(10432, 10600 - 10432) == kFieldViewPackets && FieldOfOffset(0x29C0) == kField29C0', 'static_assert(FieldsOfRange(10304, 10472 - 10304) == kFieldViewPackets && FieldOfOffset(0x2940) == kField29C0'),
    ('render/draw.cpp', 'key[11] = device.U32(0x29C0);', "key[11] = device.U32(0x2940);  // hexic2-nx: 128 below Katamari's"),
    ('render/draw.cpp', '!(device.U32(0x29C0) & 1)', '!(device.U32(0x2940) & 1)'),
    ('render/draw.cpp', 'constexpr u32 kDeviceDeclarationOffset = 0x2F98;', 'constexpr u32 kDeviceDeclarationOffset = 0x2F18;  // hexic2-nx: -128'),
    ('render/draw.cpp', 'static_assert(kCensusTailBegin < 10880 && 11776 < d3d::kDeviceSnapshotSize);', 'static_assert(kCensusTailBegin < 10752 && 11648 < d3d::kDeviceSnapshotSize);'),
    ('render/draw.cpp', 'state = XXH3_64bits_withSeed(device_state + kCensusTailBegin, 10880 - kCensusTailBegin, state);', 'state = XXH3_64bits_withSeed(device_state + kCensusTailBegin, 10752 - kCensusTailBegin, state);'),
    ('render/draw.cpp', 'state = XXH3_64bits_withSeed(device_state + 11776, d3d::kDeviceSnapshotSize - 11776, state);', 'state = XXH3_64bits_withSeed(device_state + 11648, d3d::kDeviceSnapshotSize - 11648, state);'),
    ('backend/queued.cpp', 'constexpr u32 kDeltaPrivateUnreadBegin = 10880, kDeltaPrivateUnreadEnd = 11776;', 'constexpr u32 kDeltaPrivateUnreadBegin = 10752, kDeltaPrivateUnreadEnd = 11648;  // hexic2-nx: -128'),
    ('backend/queued.cpp', 'static_assert(kDeltaUnreadEnd == 0x480 && kDeltaUnreadEnd % kDeltaUnitBytes == 0);', 'static_assert(kDeltaUnreadEnd == 0x400 && kDeltaUnreadEnd % kDeltaUnitBytes == 0);'),
]


def respell(old, new):
    return f'0x{new:X}' if old.lower().startswith('0x') else str(new)


def apply_annotated(check):
    changed = 0
    report = []
    for d, _, fs in os.walk(GPU):
        for f in fs:
            if not f.endswith(('.cpp', '.h', '.inc')):
                continue
            p = os.path.join(d, f)
            t = open(p, encoding='utf-8', errors='surrogateescape', newline='').read()
            lines = t.split('\n')
            dirty = False
            for i, line in enumerate(lines):
                if MARK in line:
                    continue
                m = PAIR.search(line)
                if not m:
                    continue
                code, sep, comment = line.partition('//')
                notes = []
                for xs, ys in ONE.findall(m.group(1)):
                    y = int(ys, 0)
                    if y >= 0x10000:  # a guest data address: EDITS
                        continue
                    new = hx(y)
                    if new is None:
                        continue
                    rx = re.compile(r'(?<![0-9A-Za-z_.])' + re.escape(ys) + r'(?:[uU])?(?![0-9A-Za-z_.])')
                    if rx.search(code):
                        code = rx.sub(respell(ys, new), code, count=1)
                        notes.append(f'{ys}->{respell(ys, new)}')
                    else:
                        report.append(f'NOT IN CODE {f}:{i + 1} {ys}: {code.strip()[:90]}')
                if notes:
                    eol = '\r' if line.endswith('\r') else ''
                    lines[i] = code + sep + comment.rstrip('\r') + f' ({MARK}: ' + ', '.join(notes) + ')' + eol
                    dirty = True
                    changed += 1
            if dirty and not check:
                open(p, 'w', encoding='utf-8', errors='surrogateescape', newline='').write('\n'.join(lines))
    print(f'{changed} annotated lines moved')
    print('\n'.join(report))


def apply_literals(check):
    moved = 0
    for rel in LITERAL_FILES:
        p = os.path.join(GPU, rel.replace('/', os.sep))
        t = open(p, encoding='utf-8', errors='surrogateescape', newline='').read()
        lines = t.split('\n')
        dirty = False
        for i, line in enumerate(lines):
            code, sep, comment = line.partition('//')
            if MARK in line or not code.strip() or not LINE_USE.search(code) or SKIP.search(code):
                continue
            notes = []

            def sub(m, base):
                text = m.group(0)
                v = int(m.group(1), base)
                new = hx(v)
                if new is None:
                    return text
                notes.append(f'{v:#x}->{new:#x}')
                return f'0x{new:X}' + ('u' if text[-1] in 'uU' else '') if base == 16 else str(new)
            code2 = HEX.sub(lambda m: sub(m, 16), code)
            code2 = DEC.sub(lambda m: sub(m, 10), code2)
            if notes:
                eol = '\r' if line.endswith('\r') else ''
                if sep:
                    lines[i] = code2 + sep + comment.rstrip('\r') + f' {MARK}: ' + ', '.join(notes) + eol
                else:
                    lines[i] = code2.rstrip('\r') + f'  // {MARK}: ' + ', '.join(notes) + eol
                dirty = True
                moved += 1
        if dirty and not check:
            open(p, 'w', encoding='utf-8', errors='surrogateescape', newline='').write('\n'.join(lines))
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    done = skipped = 0
    bad = []
    for rel, old, new in EDITS:
        p = os.path.join(GPU, rel.replace('/', os.sep))
        t = open(p, encoding='utf-8', errors='surrogateescape', newline='').read()
        crlf = '\r\n' in t
        o, n = (old.replace('\n', '\r\n'), new.replace('\n', '\r\n')) if crlf else (old, new)
        if n and n in t:
            skipped += 1
        elif o in t:
            if not a.check:
                t = t.replace(o, n)
                open(p, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(t)
            done += 1
        else:
            bad.append((rel, old[:70]))
    print(f'{done} edits applied, {skipped} already there, {len(bad)} missing')
    for b in bad:
        print('MISSING', b)
    apply_annotated(a.check)
    print(f'{apply_literals(a.check)} literal lines moved')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

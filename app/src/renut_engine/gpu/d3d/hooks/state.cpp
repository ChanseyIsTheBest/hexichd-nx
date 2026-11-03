/**
 * @file    gpu/d3d/hooks/state.cpp
 * @brief   N&B's D3D state calls, hooked with the native ports (d3d_native.h).
 *
 * The render and sampler state setters are the ones N&B's state tables name
 * (D3D::InitializeApiState puts them into every device's dispatch table,
 * which the game's inline SetRenderState / SetSamplerState call through).
 * The rest are D3DDevice_Set* and the CDevice internals that write the ring.
 */
#include <cstring>

#include <rex/hook.h>

#include "renut_engine/gpu/banjo_renut_select.h"
#include <rex/types.h>

#include "renut_engine/gpu/d3d/d3d_native.h"
#include "renut_engine/gpu/guest/guest_memory.h"

using namespace renut::gpu;

namespace {

template <u32 State>
void SetRenderStateHook(u32 device, u32 value) {
  native::SetRenderState(native::DeviceAt(device), State, value);
}

template <u32 State>
void SetSamplerStateHook(u32 device, u32 sampler, u32 value) {
  native::SetSamplerState(native::DeviceAt(device), sampler, State, value);
}

template <u32 State>
u32 GetRenderStateHook(u32 device) {
  return native::GetRenderState(native::DeviceAt(device), State);
}

template <u32 State>
u32 GetSamplerStateHook(u32 device, u32 sampler) {
  return native::GetSamplerState(native::DeviceAt(device), sampler, State);
}

// The device's AddRef of a resource it hands out (D3DResource_AddRef,
// resource.cpp).
u32 AddRefResource(u32 resource) {
  return native::AddRefResource(resource);
}

// rr6-nx (2026-11-02): XDK 2.0.2135's setters take the game's own objects and keep a binding on them (hooks/resource.cpp, "XDK
// 2.0.2135's own objects"). Renut's state code sees the object's shadow. What each slot holds as the game knows it is kept
// here: one title device in this game (1 CreateDevice call site).
constexpr u32 kRr6Samplers = 26, kRr6Streams = 16, kRr6Targets = 4;
u32 g_hexichd_textures[kRr6Samplers] = {}, g_hexichd_streams[kRr6Streams] = {}, g_hexichd_targets[kRr6Targets] = {};
u32 g_hexichd_depth = 0, g_hexichd_indices = 0, g_hexichd_declaration = 0;

// Binds the new and returns the old, for the caller to unbind after the native setter: that setter fences what it replaces
// (TagResourceFence), and an old object unbound first may be gone by then, its fence landing in the record heap's free list.
inline u32 Rr6Rebind(u32 &slot, u32 value) {
  if (slot == value)
    return 0;
  native::Rr6Bind(value);
  const u32 old = slot;
  slot = value;
  return old;
}

void Rr6SetTexture(u32 device, u32 sampler, u32 texture) {
  const u32 old = sampler < kRr6Samplers ? Rr6Rebind(g_hexichd_textures[sampler], texture) : 0;
  native::SetTexture(native::DeviceAt(device), sampler, native::Rr6TextureShadow(texture));
  native::Rr6Unbind(old);
}
void Rr6SetRenderTarget(u32 device, u32 index, u32 surface) {
  const u32 shadow = native::Rr6SurfaceShadow(surface);
  const u32 old = index < kRr6Targets ? Rr6Rebind(g_hexichd_targets[index], surface) : 0;
  native::SetRenderTarget(native::DeviceAt(device), index, shadow);
  native::Rr6Unbind(old);
}
void Rr6SetDepthStencil(u32 device, u32 surface) {
  const u32 shadow = native::Rr6SurfaceShadow(surface);
  const u32 old = Rr6Rebind(g_hexichd_depth, surface);
  native::SetDepthStencilSurface(native::DeviceAt(device), shadow);
  native::Rr6Unbind(old);
}
u32 Rr6GetRenderTarget(u32 device, u32 index) {
  const native::Device d = native::DeviceAt(device);
  const u32 shadow = d && index < 4 ? d.W(native::off::RenderTargets + index * 4) : 0;
  const u32 surface = shadow ? native::Rr6SurfaceGuest(shadow) : 0;
  if (surface)
    native::Rr6AddRefAny(surface);
  return surface;
}
u32 Rr6GetDepthStencil(u32 device) {
  const native::Device d = native::DeviceAt(device);
  const u32 shadow = d ? d.W(native::off::DepthStencil) : 0;
  const u32 surface = shadow ? native::Rr6SurfaceGuest(shadow) : 0;
  if (surface)
    native::Rr6AddRefAny(surface);
  return surface;
}
void Rr6SetStreamSource(u32 device, u32 stream, u32 vertex_buffer, u32 offset, u32 stride) {
  const u32 old = stream < kRr6Streams ? Rr6Rebind(g_hexichd_streams[stream], vertex_buffer) : 0;
  native::SetStreamSource(native::DeviceAt(device), stream, vertex_buffer, offset, stride);
  native::Rr6Unbind(old);
}
void Rr6SetIndices(u32 device, u32 index_buffer) {
  const u32 old = Rr6Rebind(g_hexichd_indices, index_buffer);
  native::SetIndices(native::DeviceAt(device), index_buffer);
  native::Rr6Unbind(old);
}
void Rr6SetVertexDeclaration(u32 device, u32 declaration) {
  const u32 old = Rr6Rebind(g_hexichd_declaration, declaration);
  native::SetVertexDeclaration(native::DeviceAt(device), declaration);
  native::Rr6Unbind(old);
}

// XDK 2135's render state 57 (between ColorWriteEnable3 and TessellationMode), which N&B's order does not have: its setter
// stores the value in four device words where Renut's device has its own fields, so it is kept here (zuma-nx's).
u32 g_hexichd_render_state57 = 0;
void Rr6SetRenderState57(u32 /*device*/, u32 value) {
  g_hexichd_render_state57 = value;
}
u32 Rr6GetRenderState57(u32 /*device*/) {
  return g_hexichd_render_state57;
}

// D3DSurface *GetRenderTarget(D3DDevice*, DWORD Index) [0x82636ED0]
u32 D3DDevice_GetRenderTarget_hook(u32 device, u32 index) {
  const native::Device d = native::DeviceAt(device);
  const u32 surface = d && index < 4 ? d.W(native::off::RenderTargets + index * 4) : 0;
  if (surface)
    AddRefResource(surface);
  return surface;
}

// D3DSurface *GetDepthStencilSurface(D3DDevice*) [0x82636F10]
u32 D3DDevice_GetDepthStencilSurface_hook(u32 device) {
  const native::Device d = native::DeviceAt(device);
  const u32 surface = d ? d.W(native::off::DepthStencil) : 0;
  if (surface)
    AddRefResource(surface);
  return surface;
}

// D3DVertexBuffer *GetStreamSource(D3DDevice*, UINT StreamNumber,
//     UINT *pOffsetInBytes, UINT *pStride) [0x82636E40]: the offset is the
// stream's fetch constant address less the buffer's.
u32 D3DDevice_GetStreamSource_hook(u32 device, u32 stream, mapped_u32 offset, mapped_u32 stride) {
  const native::Device d = native::DeviceAt(device);
  if (!d || stream >= 16)
    return 0;
  const u32 buffer = d.W(native::off::StreamSources + stream * 4);
  u32 bytes = 0;
  if (buffer) {
    const u32 fetch = d.W(native::off::TextureFetch + (95 - stream) * 8);
    bytes = fetch - native::GpuAddress(GuestPtr<const be_u32>(buffer)[6]);
    AddRefResource(buffer);
  }
  if (offset)
    *offset = bytes;
  if (stride)
    *stride = u32(d.B(native::off::StreamStrides + stream)) << 2;
  return buffer;
}

// void D3DDevice_GetViewport(D3DDevice*, D3DVIEWPORT9*) [0x82244B18]
void D3DDevice_GetViewport_hook(u32 device, mapped_u32 viewport) {
  const native::Device d = native::DeviceAt(device);
  if (!d || !viewport)
    return;
  for (u32 i = 0; i < 4; ++i)  // fctidz, the low word
    viewport[i] = u32(native::TruncateToI64(d.F(0x3160 + i * 4)));  // katamari-nx: 0x3170->0x3160
  viewport[4] = d.W(0x3170);  // katamari-nx: 0x3180->0x3170
  viewport[5] = d.W(0x3174);  // katamari-nx: 0x3184->0x3174
}

// void D3DDevice_SetClipPlane(D3DDevice*, DWORD Index, const float *pPlane) [0x826370E8]
void D3DDevice_SetClipPlane_hook(u32 device, u32 index, mapped_u32 plane) {
  native::Device d = native::DeviceAt(device);
  if (!d || !plane || index >= 6)
    return;
  for (u32 i = 0; i < 4; ++i)
    d.SetW(0x2820 + index * 16 + i * 4, plane[i]);
  d.Dirty(4, u64(1) << (54 - index));
}

// void D3DDevice_SetVertexFetchConstant(D3DDevice*, UINT VertexFetchRegister,
//     D3DVertexBuffer*, UINT Offset) [0x82637138]: a vertex fetch slot of the
// 3 in a fetch constant, made a vertex fetch constant first.
void D3DDevice_SetVertexFetchConstant_hook(u32 device, u32 reg, u32 vertex_buffer, u32 offset) {
  native::Device d = native::DeviceAt(device);
  const auto *vb = vertex_buffer ? GuestPtr<const be_u32>(vertex_buffer) : nullptr;
  if (!d || !vb || reg > 0x5F)
    return;
  const u32 slot = (0x5F - reg) / 3;
  const u32 part = (0x5F - reg) - slot * 3;
  const u32 constant = native::off::TextureFetch + slot * 24;
  const u32 type = d.W(constant) & 3;
  if (type == 0 || type == 2)
    std::memset(d.bytes + constant, 0, 24);
  d.TouchRange(constant, 24);  // banjo-nx (2026-10-26, banjo_renut_tags)
  d.SetW(constant, native::Insert(d.W(constant), 1, 0, 2));
  d.Dirty(3, u64(1) << (31 - slot));
  d.SetW(constant + part * 8, native::GpuAddress(u32(vb[6]) + offset));
  d.SetW(constant + part * 8 + 4, native::Insert(u32(vb[7]) - offset, 1, 28, 2));
}

// The boolean and integer shader constants (D3DDevice_Set{Vertex,Pixel}
// ShaderConstant{B,I}): bits from 0x2780 (vertex) / 0x2790 (pixel), a word
// of x, y, z bytes each from 0x27A0 / 0x27E0.
void SetShaderConstantsB(u32 device, u32 base, u32 start, mapped_u32 data, u32 count) {
  native::Device d = native::DeviceAt(device);
  if (!d || !data)
    return;
  for (u32 i = 0; i < count; ++i, ++start) {
    const u32 word = base + (start >> 5) * 4;
    const u32 bit = 1u << (start & 31);
    d.SetW(word, (d.W(word) & ~bit) | ((u32(data[i]) & 1) << (start & 31)));
  }
  d.Dirty(4, u64(1) << 56);
}

void SetShaderConstantsI(u32 device, u32 base, u32 start, mapped_u32 data, u32 count) {
  native::Device d = native::DeviceAt(device);
  if (!d || !data)
    return;
  for (u32 i = 0; i < count; ++i) {
    const u32 x = u32(data[i * 4]) & 0xFF, y = u32(data[i * 4 + 1]) & 0xFF;
    const u32 z = u32(data[i * 4 + 2]) & 0xFF;
    d.SetW(base + (start + i) * 4, (z << 16) | (y << 8) | x);
  }
  d.Dirty(4, u64(1) << 56);
}

// void D3DDevice_SetVertexShaderConstantB(D3DDevice*, UINT StartRegister,
//     const BOOL*, UINT BoolCount) [0x821F0B40], and the others alike.
void D3DDevice_SetVertexShaderConstantB_hook(u32 device, u32 start, mapped_u32 data, u32 count) {
  SetShaderConstantsB(device, 0x2780, start, data, count);
}
void D3DDevice_SetPixelShaderConstantB_hook(u32 device, u32 start, mapped_u32 data, u32 count) {
  SetShaderConstantsB(device, 0x2790, start, data, count);
}
void D3DDevice_SetVertexShaderConstantI_hook(u32 device, u32 start, mapped_u32 data, u32 count) {
  SetShaderConstantsI(device, 0x27A0, start, data, count);
}
void D3DDevice_SetPixelShaderConstantI_hook(u32 device, u32 start, mapped_u32 data, u32 count) {
  SetShaderConstantsI(device, 0x27E0, start, data, count);
}

// void D3DDevice_EndIndexedVertices(D3DDevice*) [0x8263ED90]: the inline end
// of BeginIndexedVertices, back to the ring pointer it saved.
void D3DDevice_EndIndexedVertices_hook(u32 device) {
  native::Device d = native::DeviceAt(device);
  if (d)
    d.SetW(native::off::Ring, d.W(0x3474));  // katamari-nx: 0x3484->0x3474
}

// void D3DDevice_SetTexture(D3DDevice*, DWORD Sampler, D3DBaseTexture*,
//     UINT64 PendingMask3) [0x821FE558]; the mask is the sampler's fetch
// constant bit, which the port derives from Sampler.
void D3DDevice_SetTexture_hook(u32 device, u32 sampler, u32 texture) {
  native::SetTexture(native::DeviceAt(device), sampler, texture);
}

// void D3DDevice_SetStreamSource(D3DDevice*, UINT StreamNumber, D3DVertexBuffer*,
//     UINT OffsetInBytes, UINT Stride, UINT64 PendingMask3) [0x821F9438]
void D3DDevice_SetStreamSource_hook(u32 device, u32 stream, u32 vertex_buffer, u32 offset,
                                    u32 stride) {
  native::SetStreamSource(native::DeviceAt(device), stream, vertex_buffer, offset, stride);
}

// void D3DDevice_SetIndices(D3DDevice*, D3DIndexBuffer*) [0x821DE438]
void D3DDevice_SetIndices_hook(u32 device, u32 index_buffer) {
  native::SetIndices(native::DeviceAt(device), index_buffer);
}

// void D3DDevice_SetVertexDeclaration(D3DDevice*, D3DVertexDeclaration*) [0x821D5060]
void D3DDevice_SetVertexDeclaration_hook(u32 device, u32 declaration) {
  native::SetVertexDeclaration(native::DeviceAt(device), declaration);
}

// void D3DDevice_SetViewport(D3DDevice*, const D3DVIEWPORT9*) [0x821F2090]
void D3DDevice_SetViewport_hook(u32 device, u32 viewport) {
  native::SetViewport(native::DeviceAt(device), viewport);
}

// void D3D::SetViewport(D3DDevice*, float X, float Y, float Width, float Height,
//     float MinZ, float MaxZ) [0x821F2110]
void D3D_SetViewport_hook(u32 device, float x, float y, float width, float height, float min_z,
                          float max_z) {
  native::SetViewport(native::DeviceAt(device), x, y, width, height, min_z, max_z);
}

// void D3DDevice_SetScissorRect(D3DDevice*, const RECT*) [0x821F2368]
void D3DDevice_SetScissorRect_hook(u32 device, mapped_u32 rect) {
  if (!rect)
    return;
  native::SetScissorRect(native::DeviceAt(device), i32(u32(rect[0])), i32(u32(rect[1])),
                         i32(u32(rect[2])), i32(u32(rect[3])));
}

// void D3D::SetSurfaceClip(CDevice*, int, int, int, int) [0x821F2460]: the
// window scissor and per-tile clip packets, nothing else.
void D3D_SetSurfaceClip_hook(u32 /*device*/, u32, u32, u32, u32) {}

// void D3DDevice_SetRenderTarget(D3DDevice*, DWORD Index, D3DSurface*) [0x82248BD0]
void D3DDevice_SetRenderTarget_hook(u32 device, u32 index, u32 surface) {
  native::SetRenderTarget(native::DeviceAt(device), index, surface);
}

// void D3DDevice_SetDepthStencilSurface(D3DDevice*, D3DSurface*) [0x82248FB0]
void D3DDevice_SetDepthStencilSurface_hook(u32 device, u32 surface) {
  native::SetDepthStencilSurface(native::DeviceAt(device), surface);
}

// void D3D::SetSurfaceInfo(CDevice*, D3DSurface*) [0x82248F20]
void D3D_SetSurfaceInfo_hook(u32 device, u32 surface) {
  native::SetSurfaceInfo(native::DeviceAt(device), surface);
}

// void D3DDevice_SetPredication(D3DDevice*, DWORD PredicationMask) [0x821F9A48]
void D3DDevice_SetPredication_hook(u32 device, u32 mask) {
  native::SetPredication(native::DeviceAt(device), mask);
}

// void D3DDevice_SetCommandBufferPredication(D3DDevice*, DWORD TilePredication,
//     DWORD RunPredication) [0x826411C0]
void D3DDevice_SetCommandBufferPredication_hook(u32 device, u32 tile_predication,
                                                u32 run_predication) {
  native::SetCommandBufferPredication(native::DeviceAt(device), tile_predication,
                                      run_predication);
}

// void D3DDevice_SetShaderGPRAllocation(D3DDevice*, DWORD Flags,
//     DWORD VertexShaderCount, DWORD PixelShaderCount) [0x821EFD38]
void D3DDevice_SetShaderGPRAllocation_hook(u32 device, u32 flags, u32 vertex_count,
                                           u32 pixel_count) {
  native::SetShaderGPRAllocation(native::DeviceAt(device), flags, vertex_count, pixel_count);
}

// void D3D::CleanupGprAllocationSetup(CDevice*) [0x82637208]
void D3D_CleanupGprAllocationSetup_hook(u32 device) {
  native::CleanupGprAllocationSetup(native::DeviceAt(device));
}

// void D3DDevice_SetScreenExtentQueryMode(D3DDevice*, D3DSCREENEXTENTQUERYMODE)
// [0x826414C0]
void D3DDevice_SetScreenExtentQueryMode_hook(u32 device, u32 mode) {
  native::SetScreenExtentQueryMode(native::DeviceAt(device), mode);
}

// void D3DDevice_UnsetAll(D3DDevice*) [0x82634C10]
void D3DDevice_UnsetAll_hook(u32 device) {
  native::UnsetAll(native::DeviceAt(device));
}

// void D3D::ResetAllState(CDevice*, BOOL) [0x82255C98]
void D3D_ResetAllState_hook(u32 device, u32 /*skip_packets*/) {
  native::ResetAllState(native::DeviceAt(device));
}

// void D3D::InvalidateConstants(D3DDevice*) [0x82634B90]
void D3D_InvalidateConstants_hook(u32 device) {
  native::InvalidateConstants(native::DeviceAt(device));
}

// void D3DDevice_BlockUntilIdle(D3DDevice*) [0x82640010] (IDA: the second
// D3D::InvalidateConstants): waits for the device's current fence (N&B calls
// it before releasing a device).
void D3DDevice_BlockUntilIdle_hook(u32 device) {
  native::InvalidateConstantsAndWait(native::DeviceAt(device));
}

} // namespace

// Render states, by their index in N&B's table (off_82E506F0).
BANJO_RENUT_HOOK(sub_920B69A8, SetRenderStateHook<10>);  // D3DDevice_SetRenderState_ZEnable  // rr6-nx: the game's state table; Katamari 824DC2F8 hexichd-nx: rr6 82255838
BANJO_RENUT_HOOK(sub_920B6A30, SetRenderStateHook<11>);  // D3DDevice_SetRenderState_ZFunc  // rr6-nx: the game's state table; Katamari 824DC368 hexichd-nx: rr6 822558C0
BANJO_RENUT_HOOK(sub_920B69F8, SetRenderStateHook<12>);  // D3DDevice_SetRenderState_ZWriteEnable  // rr6-nx: the game's state table; Katamari 824DC338 hexichd-nx: rr6 82255888
BANJO_RENUT_HOOK(sub_920B62F0, SetRenderStateHook<13>);  // D3DDevice_SetRenderState_FillMode  // rr6-nx: the game's state table; Katamari 824DBBD8 hexichd-nx: rr6 82255180
BANJO_RENUT_HOOK(sub_920B62B8, SetRenderStateHook<14>);  // D3DDevice_SetRenderState_CullMode  // rr6-nx: the game's state table; Katamari 824DBBA8 hexichd-nx: rr6 82255148
BANJO_RENUT_HOOK(sub_920B6370, SetRenderStateHook<15>);  // D3DDevice_SetRenderState_AlphaBlendEnable  // rr6-nx: the game's state table; Katamari 824DBC40 hexichd-nx: rr6 82255200
BANJO_RENUT_HOOK(sub_920B6740, SetRenderStateHook<16>);  // D3DDevice_SetRenderState_SeparateAlphaBlendEnable  // rr6-nx: the game's state table; Katamari 824DBFD0 hexichd-nx: rr6 822555D0
BANJO_RENUT_HOOK(sub_920B6888, SetRenderStateHook<17>);  // D3DDevice_SetRenderState_BlendFactor  // rr6-nx: the game's state table; Katamari 824DC100 hexichd-nx: rr6 82255718
BANJO_RENUT_HOOK(sub_920B64A8, SetRenderStateHook<18>);  // D3DDevice_SetRenderState_SrcBlend  // rr6-nx: the game's state table; Katamari 824DBD60 hexichd-nx: rr6 82255338
BANJO_RENUT_HOOK(sub_920B6540, SetRenderStateHook<19>);  // D3DDevice_SetRenderState_DestBlend  // rr6-nx: the game's state table; Katamari 824DBDF0 hexichd-nx: rr6 822553D0
BANJO_RENUT_HOOK(sub_920B6410, SetRenderStateHook<20>);  // D3DDevice_SetRenderState_BlendOp  // rr6-nx: the game's state table; Katamari 824DBCD0 hexichd-nx: rr6 822552A0
BANJO_RENUT_HOOK(sub_920B6650, SetRenderStateHook<21>);  // D3DDevice_SetRenderState_SrcBlendAlpha  // rr6-nx: the game's state table; Katamari 824DBEF0 hexichd-nx: rr6 822554E0
BANJO_RENUT_HOOK(sub_920B66C8, SetRenderStateHook<22>);  // D3DDevice_SetRenderState_DestBlendAlpha  // rr6-nx: the game's state table; Katamari 824DBF60 hexichd-nx: rr6 82255558
BANJO_RENUT_HOOK(sub_920B65D8, SetRenderStateHook<23>);  // D3DDevice_SetRenderState_BlendOpAlpha  // rr6-nx: the game's state table; Katamari 824DBE80 hexichd-nx: rr6 82255468
BANJO_RENUT_HOOK(sub_920B6328, SetRenderStateHook<24>);  // D3DDevice_SetRenderState_AlphaTestEnable  // rr6-nx: the game's state table; Katamari 824DBC08 hexichd-nx: rr6 822551B8
BANJO_RENUT_HOOK(sub_920B67E0, SetRenderStateHook<25>);  // D3DDevice_SetRenderState_AlphaRef  // rr6-nx: the game's state table; Katamari 824DC068 hexichd-nx: rr6 82255670
BANJO_RENUT_HOOK(sub_920B6850, SetRenderStateHook<26>);  // D3DDevice_SetRenderState_AlphaFunc  // rr6-nx: the game's state table; Katamari 824DC0D0 hexichd-nx: rr6 822556E0
BANJO_RENUT_HOOK(sub_920B6A78, SetRenderStateHook<27>);  // D3DDevice_SetRenderState_StencilEnable  // rr6-nx: the game's state table; Katamari 824DC3A0 hexichd-nx: rr6 82255908
BANJO_RENUT_HOOK(sub_920B6AC8, SetRenderStateHook<28>);  // D3DDevice_SetRenderState_TwoSidedStencilMode  // rr6-nx: the game's state table; Katamari 824DC3E0 hexichd-nx: rr6 82255958
BANJO_RENUT_HOOK(sub_920B6B48, SetRenderStateHook<29>);  // D3DDevice_SetRenderState_StencilFail  // rr6-nx: the game's state table; Katamari 824DC448 hexichd-nx: rr6 822559D8
BANJO_RENUT_HOOK(sub_920B6B90, SetRenderStateHook<30>);  // D3DDevice_SetRenderState_StencilZFail  // rr6-nx: the game's state table; Katamari 824DC480 hexichd-nx: rr6 82255A20
BANJO_RENUT_HOOK(sub_920B6BD8, SetRenderStateHook<31>);  // D3DDevice_SetRenderState_StencilPass  // rr6-nx: the game's state table; Katamari 824DC4B8 hexichd-nx: rr6 82255A68
BANJO_RENUT_HOOK(sub_920B6B10, SetRenderStateHook<32>);  // D3DDevice_SetRenderState_StencilFunc  // rr6-nx: the game's state table; Katamari 824DC418 hexichd-nx: rr6 822559A0
BANJO_RENUT_HOOK(sub_920B6D10, SetRenderStateHook<33>);  // D3DDevice_SetRenderState_StencilRef  // rr6-nx: the game's state table; Katamari 824DC5B8 hexichd-nx: rr6 82255BA0
BANJO_RENUT_HOOK(sub_920B6D38, SetRenderStateHook<34>);  // D3DDevice_SetRenderState_StencilMask  // rr6-nx: the game's state table; Katamari 824DC5D8 hexichd-nx: rr6 82255BC8
BANJO_RENUT_HOOK(sub_920B6D60, SetRenderStateHook<35>);  // D3DDevice_SetRenderState_StencilWriteMask  // rr6-nx: the game's state table; Katamari 824DC5F8 hexichd-nx: rr6 82255BF0
BANJO_RENUT_HOOK(sub_920B6C48, SetRenderStateHook<36>);  // D3DDevice_SetRenderState_CCWStencilFail  // rr6-nx: the game's state table; Katamari 824DC518 hexichd-nx: rr6 82255AD8
BANJO_RENUT_HOOK(sub_920B6C90, SetRenderStateHook<37>);  // D3DDevice_SetRenderState_CCWStencilZFail  // rr6-nx: the game's state table; Katamari 824DC550 hexichd-nx: rr6 82255B20
BANJO_RENUT_HOOK(sub_920B6CD8, SetRenderStateHook<38>);  // D3DDevice_SetRenderState_CCWStencilPass  // rr6-nx: the game's state table; Katamari 824DC588 hexichd-nx: rr6 82255B68
BANJO_RENUT_HOOK(sub_920B6C10, SetRenderStateHook<39>);  // D3DDevice_SetRenderState_CCWStencilFunc  // rr6-nx: the game's state table; Katamari 824DC4E8 hexichd-nx: rr6 82255AA0
BANJO_RENUT_HOOK(sub_920B6D88, SetRenderStateHook<40>);  // D3DDevice_SetRenderState_CCWStencilRef  // rr6-nx: the game's state table; Katamari 824DC618 hexichd-nx: rr6 82255C18
BANJO_RENUT_HOOK(sub_920B6DB0, SetRenderStateHook<41>);  // D3DDevice_SetRenderState_CCWStencilMask  // rr6-nx: the game's state table; Katamari 824DC638 hexichd-nx: rr6 82255C40
BANJO_RENUT_HOOK(sub_920B6DD8, SetRenderStateHook<42>);  // D3DDevice_SetRenderState_CCWStencilWriteMask  // rr6-nx: the game's state table; Katamari 824DC658 hexichd-nx: rr6 82255C68
BANJO_RENUT_HOOK(sub_920B6E00, SetRenderStateHook<43>);  // D3DDevice_SetRenderState_ClipPlaneEnable  // rr6-nx: the game's state table; Katamari 824DC678 hexichd-nx: rr6 82255C90
BANJO_RENUT_HOOK(sub_920B7148, SetRenderStateHook<44>);  // D3DDevice_SetRenderState_PointSize  // rr6-nx: the game's state table; Katamari 824DC9A0 hexichd-nx: rr6 82255FD8
BANJO_RENUT_HOOK(sub_920B71A0, SetRenderStateHook<45>);  // D3DDevice_SetRenderState_PointSizeMin  // rr6-nx: the game's state table; Katamari 824DCA00 hexichd-nx: rr6 82256030
BANJO_RENUT_HOOK(sub_920B7138, SetRenderStateHook<46>);  // D3DDevice_SetRenderState_PointSpriteEnable  // rr6-nx: the game's state table; Katamari 824DC990 hexichd-nx: rr6 82255FC8
BANJO_RENUT_HOOK(sub_920B71F0, SetRenderStateHook<47>);  // D3DDevice_SetRenderState_PointSizeMax  // rr6-nx: the game's state table; Katamari 824DCA58 hexichd-nx: rr6 82256080
BANJO_RENUT_HOOK(sub_920B6FB0, SetRenderStateHook<48>);  // D3DDevice_SetRenderState_MultiSampleAntiAlias  // rr6-nx: the game's state table; Katamari 824DC840 hexichd-nx: rr6 82255E40
BANJO_RENUT_HOOK(sub_920B6FE8, SetRenderStateHook<49>);  // D3DDevice_SetRenderState_MultiSampleMask  // rr6-nx: the game's state table; Katamari 824DC870 hexichd-nx: rr6 82255E78
BANJO_RENUT_HOOK(sub_920B8C70, SetRenderStateHook<50>);  // D3DDevice_SetRenderState_ScissorTestEnable  // rr6-nx: the game's state table; Katamari 824DE720 hexichd-nx: rr6 82257C68
BANJO_RENUT_HOOK(sub_920B6E48, SetRenderStateHook<51>);  // D3DDevice_SetRenderState_SlopeScaleDepthBias  // rr6-nx: the game's state table; Katamari 824DC6D0 hexichd-nx: rr6 82255CD8
BANJO_RENUT_HOOK(sub_920B6F08, SetRenderStateHook<52>);  // D3DDevice_SetRenderState_DepthBias  // rr6-nx: the game's state table; Katamari 824DC798 hexichd-nx: rr6 82255D98
BANJO_RENUT_HOOK(sub_920B7018, SetRenderStateHook<53>);  // D3DDevice_SetRenderState_ColorWriteEnable  // rr6-nx: the game's state table; Katamari 824DC890 hexichd-nx: rr6 82255EA8
BANJO_RENUT_HOOK(sub_920B7060, SetRenderStateHook<54>);  // D3DDevice_SetRenderState_ColorWriteEnable1  // rr6-nx: the game's state table; Katamari 824DC8D0 hexichd-nx: rr6 82255EF0
BANJO_RENUT_HOOK(sub_920B70A8, SetRenderStateHook<55>);  // D3DDevice_SetRenderState_ColorWriteEnable2  // rr6-nx: the game's state table; Katamari 824DC910 hexichd-nx: rr6 82255F38
BANJO_RENUT_HOOK(sub_920B70F0, SetRenderStateHook<56>);  // D3DDevice_SetRenderState_ColorWriteEnable3  // rr6-nx: the game's state table; Katamari 824DC950 hexichd-nx: rr6 82255F80
BANJO_RENUT_HOOK(sub_920B7990, SetRenderStateHook<57>);  // D3DDevice_SetRenderState_TessellationMode  // rr6-nx: the game's state table; Katamari 824DD190 hexichd-nx: rr6 82256820
BANJO_RENUT_HOOK(sub_920B7930, SetRenderStateHook<58>);  // D3DDevice_SetRenderState_MinTessellationLevel  // rr6-nx: the game's state table; Katamari 824DD120 hexichd-nx: rr6 822567C0
BANJO_RENUT_HOOK(sub_920B7960, SetRenderStateHook<59>);  // D3DDevice_SetRenderState_MaxTessellationLevel  // rr6-nx: the game's state table; Katamari 824DD158 hexichd-nx: rr6 822567F0
BANJO_RENUT_HOOK(sub_920B7240, SetRenderStateHook<60>);  // D3DDevice_SetRenderState_Wrap0  // rr6-nx: the game's state table; Katamari 824DCAB0 hexichd-nx: rr6 822560D0
BANJO_RENUT_HOOK(sub_920B7270, SetRenderStateHook<61>);  // D3DDevice_SetRenderState_Wrap1  // rr6-nx: the game's state table; Katamari 824DCAD0 hexichd-nx: rr6 82256100
BANJO_RENUT_HOOK(sub_920B72A0, SetRenderStateHook<62>);  // D3DDevice_SetRenderState_Wrap2  // rr6-nx: the game's state table; Katamari 824DCAF8 hexichd-nx: rr6 82256130
BANJO_RENUT_HOOK(sub_920B72D0, SetRenderStateHook<63>);  // D3DDevice_SetRenderState_Wrap3  // rr6-nx: the game's state table; Katamari 824DCB20 hexichd-nx: rr6 82256160
BANJO_RENUT_HOOK(sub_920B7300, SetRenderStateHook<64>);  // D3DDevice_SetRenderState_Wrap4  // rr6-nx: the game's state table; Katamari 824DCB48 hexichd-nx: rr6 82256190
BANJO_RENUT_HOOK(sub_920B7330, SetRenderStateHook<65>);  // D3DDevice_SetRenderState_Wrap5  // rr6-nx: the game's state table; Katamari 824DCB70 hexichd-nx: rr6 822561C0
BANJO_RENUT_HOOK(sub_920B7360, SetRenderStateHook<66>);  // D3DDevice_SetRenderState_Wrap6  // rr6-nx: the game's state table; Katamari 824DCB98 hexichd-nx: rr6 822561F0
BANJO_RENUT_HOOK(sub_920B7390, SetRenderStateHook<67>);  // D3DDevice_SetRenderState_Wrap7  // rr6-nx: the game's state table; Katamari 824DCBC0 hexichd-nx: rr6 82256220
BANJO_RENUT_HOOK(sub_920B73B8, SetRenderStateHook<68>);  // D3DDevice_SetRenderState_Wrap8  // rr6-nx: the game's state table; Katamari 824DCBE0 hexichd-nx: rr6 82256248
BANJO_RENUT_HOOK(sub_920B73E8, SetRenderStateHook<69>);  // D3DDevice_SetRenderState_Wrap9  // rr6-nx: the game's state table; Katamari 824DCC00 hexichd-nx: rr6 82256278
BANJO_RENUT_HOOK(sub_920B7418, SetRenderStateHook<70>);  // D3DDevice_SetRenderState_Wrap10  // rr6-nx: the game's state table; Katamari 824DCC28 hexichd-nx: rr6 822562A8
BANJO_RENUT_HOOK(sub_920B7448, SetRenderStateHook<71>);  // D3DDevice_SetRenderState_Wrap11  // rr6-nx: the game's state table; Katamari 824DCC50 hexichd-nx: rr6 822562D8
BANJO_RENUT_HOOK(sub_920B7478, SetRenderStateHook<72>);  // D3DDevice_SetRenderState_Wrap12  // rr6-nx: the game's state table; Katamari 824DCC78 hexichd-nx: rr6 82256308
BANJO_RENUT_HOOK(sub_920B74A8, SetRenderStateHook<73>);  // D3DDevice_SetRenderState_Wrap13  // rr6-nx: the game's state table; Katamari 824DCCA0 hexichd-nx: rr6 82256338
BANJO_RENUT_HOOK(sub_920B74D8, SetRenderStateHook<74>);  // D3DDevice_SetRenderState_Wrap14  // rr6-nx: the game's state table; Katamari 824DCCC8 hexichd-nx: rr6 82256368
BANJO_RENUT_HOOK(sub_920B7508, SetRenderStateHook<75>);  // D3DDevice_SetRenderState_Wrap15  // rr6-nx: the game's state table; Katamari 824DCCF0 hexichd-nx: rr6 82256398
BANJO_RENUT_HOOK(sub_920B75F0, SetRenderStateHook<76>);  // D3DDevice_SetRenderState_ViewportEnable  // rr6-nx: the game's state table; Katamari 824DCE10 hexichd-nx: rr6 82256480
BANJO_RENUT_HOOK(sub_920B7650, SetRenderStateHook<77>);  // D3DDevice_SetRenderState_HighPrecisionBlendEnable  // rr6-nx: the game's state table; Katamari 824DCE60 hexichd-nx: rr6 822564E0
BANJO_RENUT_HOOK(sub_920B7708, SetRenderStateHook<78>);  // D3DDevice_SetRenderState_HighPrecisionBlendEnable1  // rr6-nx: the game's state table; Katamari 824DCF10 hexichd-nx: rr6 82256598
BANJO_RENUT_HOOK(sub_920B77C0, SetRenderStateHook<79>);  // D3DDevice_SetRenderState_HighPrecisionBlendEnable2  // rr6-nx: the game's state table; Katamari 824DCFC0 hexichd-nx: rr6 82256650
BANJO_RENUT_HOOK(sub_920B7878, SetRenderStateHook<80>);  // D3DDevice_SetRenderState_HighPrecisionBlendEnable3  // rr6-nx: the game's state table; Katamari 824DD070 hexichd-nx: rr6 82256708
BANJO_RENUT_HOOK(sub_920B79C0, SetRenderStateHook<81>);  // D3DDevice_SetRenderState_HalfPixelOffset  // rr6-nx: the game's state table; Katamari 824DD1C8 hexichd-nx: rr6 82256850
BANJO_RENUT_HOOK(sub_920B79F8, SetRenderStateHook<82>);  // D3DDevice_SetRenderState_PrimitiveResetEnable  // rr6-nx: the game's state table; Katamari 824DD200 hexichd-nx: rr6 82256888
BANJO_RENUT_HOOK(sub_920B7A30, SetRenderStateHook<83>);  // D3DDevice_SetRenderState_PrimitiveResetIndex  // rr6-nx: the game's state table; Katamari 824DD230 hexichd-nx: rr6 822568C0
BANJO_RENUT_HOOK(sub_920B7A58, SetRenderStateHook<84>);  // D3DDevice_SetRenderState_AlphaToMaskEnable  // rr6-nx: the game's state table; Katamari 824DD258 hexichd-nx: rr6 822568E8
BANJO_RENUT_HOOK(sub_920B7A90, SetRenderStateHook<85>);  // D3DDevice_SetRenderState_AlphaToMaskOffsets  // rr6-nx: the game's state table; Katamari 824DD288 hexichd-nx: rr6 82256920
BANJO_RENUT_HOOK(sub_920B7AD0, SetRenderStateHook<86>);  // D3DDevice_SetRenderState_GuardBand_X  // rr6-nx: the game's state table; Katamari 824DD2C0 hexichd-nx: rr6 82256960
BANJO_RENUT_HOOK(sub_920B7B00, SetRenderStateHook<87>);  // D3DDevice_SetRenderState_GuardBand_Y  // rr6-nx: the game's state table; Katamari 824DD2F0 hexichd-nx: rr6 82256990
BANJO_RENUT_HOOK(sub_920B7B30, SetRenderStateHook<88>);  // D3DDevice_SetRenderState_DiscardBand_X  // rr6-nx: the game's state table; Katamari 824DD320 hexichd-nx: rr6 822569C0
BANJO_RENUT_HOOK(sub_920B7B60, SetRenderStateHook<89>);  // D3DDevice_SetRenderState_DiscardBand_Y  // rr6-nx: the game's state table; Katamari 824DD348 hexichd-nx: rr6 822569F0
BANJO_RENUT_HOOK(sub_920B7B90, SetRenderStateHook<90>);  // D3DDevice_SetRenderState_HiStencilEnable  // rr6-nx: the game's state table; Katamari 824DD410 hexichd-nx: rr6 82256A20
BANJO_RENUT_HOOK(sub_920B7BC8, SetRenderStateHook<91>);  // D3DDevice_SetRenderState_HiStencilWriteEnable  // rr6-nx: the game's state table; Katamari 824DD440 hexichd-nx: rr6 82256A58
BANJO_RENUT_HOOK(sub_920B7C00, SetRenderStateHook<92>);  // D3DDevice_SetRenderState_HiStencilFunc  // rr6-nx: the game's state table; Katamari 824DD470 hexichd-nx: rr6 82256A90
BANJO_RENUT_HOOK(sub_920B7C38, SetRenderStateHook<93>);  // D3DDevice_SetRenderState_HiStencilRef  // rr6-nx: the game's state table; Katamari 824DD4A0 hexichd-nx: rr6 82256AC8
BANJO_RENUT_HOOK(sub_920B7C60, SetRenderStateHook<94>);  // D3DDevice_SetRenderState_PresentInterval  // rr6-nx: the game's state table; Katamari 824DD4C0 hexichd-nx: rr6 82256AF0
BANJO_RENUT_HOOK(sub_920B7C70, SetRenderStateHook<95>);  // D3DDevice_SetRenderState_PresentImmediateThreshold  // rr6-nx: the game's state table; Katamari 824DD4D0 hexichd-nx: rr6 82256B00
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DD378, SetRenderStateHook<96>);  // D3DDevice_SetRenderState_HiZEnable  // rr6-nx: not hooked in this XDK; Katamari 824DD378
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DD3A8, SetRenderStateHook<97>);  // D3DDevice_SetRenderState_HiZWriteEnable  // rr6-nx: not hooked in this XDK; Katamari 824DD3A8
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DC220, SetRenderStateHook<98>);  // D3DDevice_SetRenderState_LastPixel  // rr6-nx: not hooked in this XDK; Katamari 824DC220
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DC258, SetRenderStateHook<99>);  // D3DDevice_SetRenderState_LineWidth  // rr6-nx: not hooked in this XDK; Katamari 824DC258
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DC2C8, SetRenderStateHook<100>);  // D3DDevice_SetRenderState_Buffer2Frames  // rr6-nx: not hooked in this XDK; Katamari 824DC2C8

// Sampler states, by their index in N&B's table (off_82E50BD0).
BANJO_RENUT_HOOK(sub_920B8280, SetSamplerStateHook<0>);  // D3DDevice_SetSamplerState_AddressU  // rr6-nx: the game's state table; Katamari 824DDC30 hexichd-nx: rr6 82257110
BANJO_RENUT_HOOK(sub_920B82D0, SetSamplerStateHook<1>);  // D3DDevice_SetSamplerState_AddressV  // rr6-nx: the game's state table; Katamari 824DDC80 hexichd-nx: rr6 82257160
BANJO_RENUT_HOOK(sub_920B8320, SetSamplerStateHook<2>);  // D3DDevice_SetSamplerState_AddressW  // rr6-nx: the game's state table; Katamari 824DDCD0 hexichd-nx: rr6 822571B0
BANJO_RENUT_HOOK(sub_920B8210, SetSamplerStateHook<3>);  // D3DDevice_SetSamplerState_BorderColor  // rr6-nx: the game's state table; Katamari 824DDBC0 hexichd-nx: rr6 822570A0
BANJO_RENUT_HOOK(sub_920B7DA0, SetSamplerStateHook<4>);  // D3DDevice_SetSamplerState_MagFilter  // rr6-nx: the game's state table; Katamari 824DD680 hexichd-nx: rr6 82256C30
BANJO_RENUT_HOOK(sub_920B7C90, SetSamplerStateHook<5>);  // D3DDevice_SetSamplerState_MinFilter  // rr6-nx: the game's state table; Katamari 824DD4F0 hexichd-nx: rr6 82256B20
BANJO_RENUT_HOOK(sub_920B7EA8, SetSamplerStateHook<6>);  // D3DDevice_SetSamplerState_MipFilter  // rr6-nx: the game's state table; Katamari 824DD810 hexichd-nx: rr6 82256D38
BANJO_RENUT_HOOK(sub_920B8070, SetSamplerStateHook<7>);  // D3DDevice_SetSamplerState_MipMapLodBias  // rr6-nx: the game's state table; Katamari 824DDA20 hexichd-nx: rr6 82256F00
BANJO_RENUT_HOOK(sub_920B8110, SetSamplerStateHook<8>);  // D3DDevice_SetSamplerState_MaxMipLevel  // rr6-nx: the game's state table; Katamari 824DDAC0 hexichd-nx: rr6 82256FA0
BANJO_RENUT_HOOK(sub_920B7F50, SetSamplerStateHook<9>);  // D3DDevice_SetSamplerState_MaxAnisotropy  // rr6-nx: the game's state table; Katamari 824DD900 hexichd-nx: rr6 82256DE0
BANJO_RENUT_HOOK(sub_920B7E60, SetSamplerStateHook<10>);  // D3DDevice_SetSamplerState_MagFilterZ  // rr6-nx: the game's state table; Katamari 824DD778 hexichd-nx: rr6 82256CF0
BANJO_RENUT_HOOK(sub_920B7D50, SetSamplerStateHook<11>);  // D3DDevice_SetSamplerState_MinFilterZ  // rr6-nx: the game's state table; Katamari 824DD5E8 hexichd-nx: rr6 82256BE0
BANJO_RENUT_HOOK(sub_920B7F00, SetSamplerStateHook<12>);  // D3DDevice_SetSamplerState_SeparateZFilterEnable  // rr6-nx: the game's state table; Katamari 824DD868 hexichd-nx: rr6 82256D90
BANJO_RENUT_HOOK(sub_920B8190, SetSamplerStateHook<13>);  // D3DDevice_SetSamplerState_MinMipLevel  // rr6-nx: the game's state table; Katamari 824DDB40 hexichd-nx: rr6 82257020
BANJO_RENUT_HOOK(sub_920B8370, SetSamplerStateHook<14>);  // D3DDevice_SetSamplerState_TrilinearThreshold  // rr6-nx: the game's state table; Katamari 824DDD20 hexichd-nx: rr6 82257200
BANJO_RENUT_HOOK(sub_920B7FC8, SetSamplerStateHook<15>);  // D3DDevice_SetSamplerState_AnisotropyBias  // rr6-nx: the game's state table; Katamari 824DD978 hexichd-nx: rr6 82256E58
BANJO_RENUT_HOOK(sub_920B83C8, SetSamplerStateHook<16>);  // D3DDevice_SetSamplerState_HGradientExpBias  // rr6-nx: the game's state table; Katamari 824DDD78 hexichd-nx: rr6 82257258
BANJO_RENUT_HOOK(sub_920B8420, SetSamplerStateHook<17>);  // D3DDevice_SetSamplerState_VGradientExpBias  // rr6-nx: the game's state table; Katamari 824DDDD0 hexichd-nx: rr6 822572B0
BANJO_RENUT_HOOK(sub_920B8478, SetSamplerStateHook<18>);  // D3DDevice_SetSamplerState_WhiteBorderColorW  // rr6-nx: the game's state table; Katamari 824DDE28 hexichd-nx: rr6 82257308
BANJO_RENUT_HOOK(sub_920B84D0, SetSamplerStateHook<19>);  // D3DDevice_SetSamplerState_PointBorderEnable  // rr6-nx: the game's state table; Katamari 824DDE80 hexichd-nx: rr6 82257360

BANJO_RENUT_HOOK(sub_920B4968, Rr6SetTexture);  // D3DDevice_SetTexture  // rr6-nx: Zuma pair of sub_8212A900; 51 sites; the game's texture, on its shadow; Katamari 824D2640 hexichd-nx: rr6 822530A8
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824A3D40, D3DDevice_SetTexture_hook);  // D3DDevice_SetTexture_Inline  // rr6-nx: not hooked in this XDK; Katamari 824A3D40
BANJO_RENUT_HOOK(sub_920B8810, Rr6SetStreamSource);  // D3DDevice_SetStreamSource  // rr6-nx: Zuma pair; 11 sites; keeps a reference, as this XDK does; Katamari 824DDFE0 hexichd-nx: rr6 822576F8
BANJO_RENUT_UNHOOKED_HOOK(unlinked_82257798, Rr6SetIndices);  // D3DDevice_SetIndices  // rr6-nx: stored at +12532, the old released; 7 sites; Katamari 824DE188 hexichd-nx: this game does not link it
BANJO_RENUT_HOOK(sub_920BD148, Rr6SetVertexDeclaration);  // D3DDevice_SetVertexDeclaration  // rr6-nx: Zuma pair; 47 sites; keeps a reference; Katamari 824D4B48 hexichd-nx: rr6 8224F018
BANJO_RENUT_HOOK(sub_920B85F8, D3DDevice_SetViewport_hook);  // D3DDevice_SetViewport  // rr6-nx: writes the 6 words at +12808 and the viewport floats; 3 sites; Katamari 824DE730 hexichd-nx: rr6 82257488
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DE4B8, D3D_SetViewport_hook);  // D3D_SetViewport  // rr6-nx: not hooked in this XDK; Katamari 824DE4B8
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DDEE0, D3DDevice_SetScissorRect_hook);  // D3DDevice_SetScissorRect  // rr6-nx: not hooked in this XDK; Katamari 824DDEE0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DB8C8, D3D_SetSurfaceClip_hook);  // D3D_SetSurfaceClip  // rr6-nx: not hooked in this XDK; Katamari 824DB8C8
BANJO_RENUT_HOOK(sub_920B8C80, Rr6SetRenderTarget);  // D3DDevice_SetRenderTarget  // rr6-nx: (dev, index, surface); 7 sites; the bind count in Common, on the surface's shadow; Katamari 824DE868 hexichd-nx: rr6 82257C78
BANJO_RENUT_HOOK(sub_920B8F30, Rr6SetDepthStencil);  // D3DDevice_SetDepthStencilSurface  // rr6-nx: (dev, surface); 11 sites; Katamari 824DEBD0 hexichd-nx: rr6 82257FE0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DE7D0, D3D_SetSurfaceInfo_hook);  // D3D_SetSurfaceInfo  // rr6-nx: not hooked in this XDK; Katamari 824DE7D0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824EFA58, D3DDevice_SetPredication_hook);  // D3DDevice_SetPredication  // rr6-nx: not hooked in this XDK; Katamari 824EFA58
BANJO_RENUT_UNHOOKED_HOOK_SHARED(unlinked_826411C0, D3DDevice_SetCommandBufferPredication_hook);  // D3DDevice_SetCommandBufferPredication  // rr6-nx: not hooked in this XDK; Katamari 826411C0
BANJO_RENUT_HOOK(sub_920BC008, D3DDevice_SetShaderGPRAllocation_hook);  // D3DDevice_SetShaderGPRAllocation  // rr6-nx: Feeding Frenzy pair of sub_820B6258, register 0x0D00 (imm 3328); 3 sites; Katamari 824D4CD8 hexichd-nx: rr6 8224EDA0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824D3FE0, D3D_CleanupGprAllocationSetup_hook);  // D3D_CleanupGprAllocationSetup  // rr6-nx: not hooked in this XDK; Katamari 824D3FE0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824E67C8, D3DDevice_SetScreenExtentQueryMode_hook);  // D3DDevice_SetScreenExtentQueryMode  // rr6-nx: not hooked in this XDK; Katamari 824E67C8
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824D0488, D3DDevice_UnsetAll_hook);  // D3DDevice_UnsetAll  // rr6-nx: not hooked in this XDK; Katamari 824D0488
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DE3C0, D3D_ResetAllState_hook);  // D3D_ResetAllState  // rr6-nx: not hooked in this XDK; Katamari 824DE3C0
BANJO_RENUT_UNHOOKED_HOOK_SHARED(unlinked_82634B90, D3D_InvalidateConstants_hook);  // D3D_InvalidateConstants  // rr6-nx: not hooked in this XDK; Katamari 82634B90
// rr6-nx (2026-11-02): paired by hand. The game's own spun on device+0x28FC with no yield, a render state on Renut's device.
BANJO_RENUT_HOOK(sub_920C0778, D3DDevice_BlockUntilIdle_hook);  // D3DDevice_BlockUntilIdle hexichd-nx: rr6 8225B828
// Through a thunk (j_D3DDevice_SetRenderTarget 0x82636EC8).
BANJO_RENUT_UNHOOKED_HOOK(unlinked_82636EC8, D3DDevice_SetRenderTarget_hook);  // D3DDevice_SetRenderTarget_Thunk  // rr6-nx: not hooked in this XDK; Katamari 82636EC8
BANJO_RENUT_UNHOOKED_HOOK(unlinked_82257818, Rr6GetRenderTarget);  // D3DDevice_GetRenderTarget  // rr6-nx: 18 instructions, AddRef; the game's surface back from its shadow; Katamari 82636ED0 hexichd-nx: this game does not link it
BANJO_RENUT_UNHOOKED_HOOK(unlinked_82257860, Rr6GetDepthStencil);  // D3DDevice_GetDepthStencilSurface  // rr6-nx: +12552, AddRef; Katamari 82636F10 hexichd-nx: this game does not link it
BANJO_RENUT_UNHOOKED_HOOK(unlinked_82636E40, D3DDevice_GetStreamSource_hook);  // D3DDevice_GetStreamSource  // rr6-nx: not hooked in this XDK; Katamari 82636E40
BANJO_RENUT_HOOK(sub_920B87E8, D3DDevice_GetViewport_hook);  // D3DDevice_GetViewport  // rr6-nx: copies 6 words from +12808; 6 sites; Katamari 82244B18 hexichd-nx: rr6 822576D0
BANJO_RENUT_HOOK(sub_920B89D0, D3DDevice_SetClipPlane_hook);  // D3DDevice_SetClipPlane  // rr6-nx: four floats at register 1480; 1 site; Katamari 826370E8 hexichd-nx: rr6 822579C0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_82637138, D3DDevice_SetVertexFetchConstant_hook);  // D3DDevice_SetVertexFetchConstant  // rr6-nx: not hooked in this XDK; Katamari 82637138
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824D4470, D3DDevice_SetVertexShaderConstantB_hook);  // D3DDevice_SetVertexShaderConstantB  // rr6-nx: not hooked in this XDK; Katamari 824D4470
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824D44D0, D3DDevice_SetPixelShaderConstantB_hook);  // D3DDevice_SetPixelShaderConstantB  // rr6-nx: not hooked in this XDK; Katamari 824D44D0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_826374B0, D3DDevice_SetVertexShaderConstantI_hook);  // D3DDevice_SetVertexShaderConstantI  // rr6-nx: not hooked in this XDK; Katamari 826374B0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_82637500, D3DDevice_SetPixelShaderConstantI_hook);  // D3DDevice_SetPixelShaderConstantI  // rr6-nx: not hooked in this XDK; Katamari 82637500
BANJO_RENUT_UNHOOKED_HOOK(unlinked_8263ED90, D3DDevice_EndIndexedVertices_hook);  // D3DDevice_EndIndexedVertices  // rr6-nx: not hooked in this XDK; Katamari 8263ED90

// Render state getters, by their index in N&B's table (off_82E506F0, field 0).
BANJO_RENUT_HOOK(sub_920B69F0, GetRenderStateHook<10>);  // D3DDevice_GetRenderState_ZEnable  // rr6-nx: the game's state table; Katamari 824DC330 hexichd-nx: rr6 82255880
BANJO_RENUT_HOOK(sub_920B6A68, GetRenderStateHook<11>);  // D3DDevice_GetRenderState_ZFunc  // rr6-nx: the game's state table; Katamari 824DC390 hexichd-nx: rr6 822558F8
BANJO_RENUT_HOOK(sub_920B6A20, GetRenderStateHook<12>);  // D3DDevice_GetRenderState_ZWriteEnable  // rr6-nx: the game's state table; Katamari 824DC358 hexichd-nx: rr6 822558B0
BANJO_RENUT_HOOK(sub_920B6318, GetRenderStateHook<13>);  // D3DDevice_GetRenderState_FillMode  // rr6-nx: the game's state table; Katamari 824DBBF8 hexichd-nx: rr6 822551A8
BANJO_RENUT_HOOK(sub_920B62E0, GetRenderStateHook<14>);  // D3DDevice_GetRenderState_CullMode  // rr6-nx: the game's state table; Katamari 824DBBC8 hexichd-nx: rr6 82255170
BANJO_RENUT_HOOK(sub_920B6400, GetRenderStateHook<15>);  // D3DDevice_GetRenderState_AlphaBlendEnable  // rr6-nx: the game's state table; Katamari 824DBCC0 hexichd-nx: rr6 82255290
BANJO_RENUT_HOOK(sub_920B67D0, GetRenderStateHook<16>);  // D3DDevice_GetRenderState_SeparateAlphaBlendEnable  // rr6-nx: the game's state table; Katamari 824DC058 hexichd-nx: rr6 82255660
BANJO_RENUT_HOOK(sub_920B6928, GetRenderStateHook<17>);  // D3DDevice_GetRenderState_BlendFactor  // rr6-nx: the game's state table; Katamari 824DC1A0 hexichd-nx: rr6 822557B8
BANJO_RENUT_HOOK(sub_920B6530, GetRenderStateHook<18>);  // D3DDevice_GetRenderState_SrcBlend  // rr6-nx: the game's state table; Katamari 824DBDE0 hexichd-nx: rr6 822553C0
BANJO_RENUT_HOOK(sub_920B65C8, GetRenderStateHook<19>);  // D3DDevice_GetRenderState_DestBlend  // rr6-nx: the game's state table; Katamari 824DBE70 hexichd-nx: rr6 82255458
BANJO_RENUT_HOOK(sub_920B6498, GetRenderStateHook<20>);  // D3DDevice_GetRenderState_BlendOp  // rr6-nx: the game's state table; Katamari 824DBD50 hexichd-nx: rr6 82255328
BANJO_RENUT_HOOK(sub_920B66B8, GetRenderStateHook<21>);  // D3DDevice_GetRenderState_SrcBlendAlpha  // rr6-nx: the game's state table; Katamari 824DBF50 hexichd-nx: rr6 82255548
BANJO_RENUT_HOOK(sub_920B6730, GetRenderStateHook<22>);  // D3DDevice_GetRenderState_DestBlendAlpha  // rr6-nx: the game's state table; Katamari 824DBFC0 hexichd-nx: rr6 822555C0
BANJO_RENUT_HOOK(sub_920B6640, GetRenderStateHook<23>);  // D3DDevice_GetRenderState_BlendOpAlpha  // rr6-nx: the game's state table; Katamari 824DBEE0 hexichd-nx: rr6 822554D0
BANJO_RENUT_HOOK(sub_920B6360, GetRenderStateHook<24>);  // D3DDevice_GetRenderState_AlphaTestEnable  // rr6-nx: the game's state table; Katamari 824DBC30 hexichd-nx: rr6 822551F0
BANJO_RENUT_HOOK(sub_920B6820, GetRenderStateHook<25>);  // D3DDevice_GetRenderState_AlphaRef  // rr6-nx: the game's state table; Katamari 824DC0A0 hexichd-nx: rr6 822556B0
BANJO_RENUT_HOOK(sub_920B6878, GetRenderStateHook<26>);  // D3DDevice_GetRenderState_AlphaFunc  // rr6-nx: the game's state table; Katamari 824DC0F0 hexichd-nx: rr6 82255708
BANJO_RENUT_HOOK(sub_920B6AC0, GetRenderStateHook<27>);  // D3DDevice_GetRenderState_StencilEnable  // rr6-nx: the game's state table; Katamari 824DC3D8 hexichd-nx: rr6 82255950
BANJO_RENUT_HOOK(sub_920B6B00, GetRenderStateHook<28>);  // D3DDevice_GetRenderState_TwoSidedStencilMode  // rr6-nx: the game's state table; Katamari 824DC408 hexichd-nx: rr6 82255990
BANJO_RENUT_HOOK(sub_920B6B80, GetRenderStateHook<29>);  // D3DDevice_GetRenderState_StencilFail  // rr6-nx: the game's state table; Katamari 824DC470 hexichd-nx: rr6 82255A10
BANJO_RENUT_HOOK(sub_920B6BC8, GetRenderStateHook<30>);  // D3DDevice_GetRenderState_StencilZFail  // rr6-nx: the game's state table; Katamari 824DC4A8 hexichd-nx: rr6 82255A58
BANJO_RENUT_HOOK(sub_920B6C00, GetRenderStateHook<31>);  // D3DDevice_GetRenderState_StencilPass  // rr6-nx: the game's state table; Katamari 824DC4D8 hexichd-nx: rr6 82255A90
BANJO_RENUT_HOOK(sub_920B6B38, GetRenderStateHook<32>);  // D3DDevice_GetRenderState_StencilFunc  // rr6-nx: the game's state table; Katamari 824DC438 hexichd-nx: rr6 822559C8
BANJO_RENUT_HOOK(sub_920B6D30, GetRenderStateHook<33>);  // D3DDevice_GetRenderState_StencilRef  // rr6-nx: the game's state table; Katamari 824DC5D0 hexichd-nx: rr6 82255BC0
BANJO_RENUT_HOOK(sub_920B6D58, GetRenderStateHook<34>);  // D3DDevice_GetRenderState_StencilMask  // rr6-nx: the game's state table; Katamari 824DC5F0 hexichd-nx: rr6 82255BE8
BANJO_RENUT_HOOK(sub_920B6D80, GetRenderStateHook<35>);  // D3DDevice_GetRenderState_StencilWriteMask  // rr6-nx: the game's state table; Katamari 824DC610 hexichd-nx: rr6 82255C10
BANJO_RENUT_HOOK(sub_920B6C80, GetRenderStateHook<36>);  // D3DDevice_GetRenderState_CCWStencilFail  // rr6-nx: the game's state table; Katamari 824DC540 hexichd-nx: rr6 82255B10
BANJO_RENUT_HOOK(sub_920B6CC8, GetRenderStateHook<37>);  // D3DDevice_GetRenderState_CCWStencilZFail  // rr6-nx: the game's state table; Katamari 824DC578 hexichd-nx: rr6 82255B58
BANJO_RENUT_HOOK(sub_920B6D00, GetRenderStateHook<38>);  // D3DDevice_GetRenderState_CCWStencilPass  // rr6-nx: the game's state table; Katamari 824DC5A8 hexichd-nx: rr6 82255B90
BANJO_RENUT_HOOK(sub_920B6C38, GetRenderStateHook<39>);  // D3DDevice_GetRenderState_CCWStencilFunc  // rr6-nx: the game's state table; Katamari 824DC508 hexichd-nx: rr6 82255AC8
BANJO_RENUT_HOOK(sub_920B6DA8, GetRenderStateHook<40>);  // D3DDevice_GetRenderState_CCWStencilRef  // rr6-nx: the game's state table; Katamari 824DC630 hexichd-nx: rr6 82255C38
BANJO_RENUT_HOOK(sub_920B6DD0, GetRenderStateHook<41>);  // D3DDevice_GetRenderState_CCWStencilMask  // rr6-nx: the game's state table; Katamari 824DC650 hexichd-nx: rr6 82255C60
BANJO_RENUT_HOOK(sub_920B6DF8, GetRenderStateHook<42>);  // D3DDevice_GetRenderState_CCWStencilWriteMask  // rr6-nx: the game's state table; Katamari 824DC670 hexichd-nx: rr6 82255C88
BANJO_RENUT_HOOK(sub_920B6E30, GetRenderStateHook<43>);  // D3DDevice_GetRenderState_ClipPlaneEnable  // rr6-nx: the game's state table; Katamari 824DC6B8 hexichd-nx: rr6 82255CC0
BANJO_RENUT_HOOK(sub_920B7190, GetRenderStateHook<44>);  // D3DDevice_GetRenderState_PointSize  // rr6-nx: the game's state table; Katamari 824DC9F0 hexichd-nx: rr6 82256020
BANJO_RENUT_HOOK(sub_920B71E0, GetRenderStateHook<45>);  // D3DDevice_GetRenderState_PointSizeMin  // rr6-nx: the game's state table; Katamari 824DCA48 hexichd-nx: rr6 82256070
BANJO_RENUT_HOOK(sub_920B7140, GetRenderStateHook<46>);  // D3DDevice_GetRenderState_PointSpriteEnable  // rr6-nx: the game's state table; Katamari 824DC998 hexichd-nx: rr6 82255FD0
BANJO_RENUT_HOOK(sub_920B7230, GetRenderStateHook<47>);  // D3DDevice_GetRenderState_PointSizeMax  // rr6-nx: the game's state table; Katamari 824DCAA0 hexichd-nx: rr6 822560C0
BANJO_RENUT_HOOK(sub_920B6FD8, GetRenderStateHook<48>);  // D3DDevice_GetRenderState_MultiSampleAntiAlias  // rr6-nx: the game's state table; Katamari 824DC860 hexichd-nx: rr6 82255E68
BANJO_RENUT_HOOK(sub_920B7010, GetRenderStateHook<49>);  // D3DDevice_GetRenderState_MultiSampleMask  // rr6-nx: the game's state table; Katamari 824DC888 hexichd-nx: rr6 82255EA0
BANJO_RENUT_HOOK(sub_920B6E40, GetRenderStateHook<50>);  // D3DDevice_GetRenderState_ScissorTestEnable  // rr6-nx: the game's state table; Katamari 824DC6C8 hexichd-nx: rr6 82255CD0
BANJO_RENUT_HOOK(sub_920B6EE8, GetRenderStateHook<51>);  // D3DDevice_GetRenderState_SlopeScaleDepthBias  // rr6-nx: the game's state table; Katamari 824DC778 hexichd-nx: rr6 82255D78
BANJO_RENUT_HOOK(sub_920B6FA0, GetRenderStateHook<52>);  // D3DDevice_GetRenderState_DepthBias  // rr6-nx: the game's state table; Katamari 824DC830 hexichd-nx: rr6 82255E30
BANJO_RENUT_HOOK(sub_920B7058, GetRenderStateHook<53>);  // D3DDevice_GetRenderState_ColorWriteEnable  // rr6-nx: the game's state table; Katamari 824DC8C8 hexichd-nx: rr6 82255EE8
BANJO_RENUT_HOOK(sub_920B70A0, GetRenderStateHook<54>);  // D3DDevice_GetRenderState_ColorWriteEnable1  // rr6-nx: the game's state table; Katamari 824DC908 hexichd-nx: rr6 82255F30
BANJO_RENUT_HOOK(sub_920B70E8, GetRenderStateHook<55>);  // D3DDevice_GetRenderState_ColorWriteEnable2  // rr6-nx: the game's state table; Katamari 824DC948 hexichd-nx: rr6 82255F78
BANJO_RENUT_HOOK(sub_920B7130, GetRenderStateHook<56>);  // D3DDevice_GetRenderState_ColorWriteEnable3  // rr6-nx: the game's state table; Katamari 824DC988 hexichd-nx: rr6 82255FC0
BANJO_RENUT_HOOK(sub_920B79B0, GetRenderStateHook<57>);  // D3DDevice_GetRenderState_TessellationMode  // rr6-nx: the game's state table; Katamari 824DD1B8 hexichd-nx: rr6 82256840
BANJO_RENUT_HOOK(sub_920B7950, GetRenderStateHook<58>);  // D3DDevice_GetRenderState_MinTessellationLevel  // rr6-nx: the game's state table; Katamari 824DD148 hexichd-nx: rr6 822567E0
BANJO_RENUT_HOOK(sub_920B7980, GetRenderStateHook<59>);  // D3DDevice_GetRenderState_MaxTessellationLevel  // rr6-nx: the game's state table; Katamari 824DD180 hexichd-nx: rr6 82256810
BANJO_RENUT_HOOK(sub_920B7530, GetRenderStateHook<60>);  // D3DDevice_GetRenderState_Wrap0  // rr6-nx: the game's state table; Katamari 824DCD10 hexichd-nx: rr6 822563C0
BANJO_RENUT_HOOK(sub_920B7540, GetRenderStateHook<61>);  // D3DDevice_GetRenderState_Wrap1  // rr6-nx: the game's state table; Katamari 824DCD20 hexichd-nx: rr6 822563D0
BANJO_RENUT_HOOK(sub_920B7550, GetRenderStateHook<62>);  // D3DDevice_GetRenderState_Wrap2  // rr6-nx: the game's state table; Katamari 824DCD30 hexichd-nx: rr6 822563E0
BANJO_RENUT_HOOK(sub_920B7560, GetRenderStateHook<63>);  // D3DDevice_GetRenderState_Wrap3  // rr6-nx: the game's state table; Katamari 824DCD40 hexichd-nx: rr6 822563F0
BANJO_RENUT_HOOK(sub_920B7570, GetRenderStateHook<64>);  // D3DDevice_GetRenderState_Wrap4  // rr6-nx: the game's state table; Katamari 824DCD50 hexichd-nx: rr6 82256400
BANJO_RENUT_HOOK(sub_920B7580, GetRenderStateHook<65>);  // D3DDevice_GetRenderState_Wrap5  // rr6-nx: the game's state table; Katamari 824DCD60 hexichd-nx: rr6 82256410
BANJO_RENUT_HOOK(sub_920B7590, GetRenderStateHook<66>);  // D3DDevice_GetRenderState_Wrap6  // rr6-nx: the game's state table; Katamari 824DCD70 hexichd-nx: rr6 82256420
BANJO_RENUT_HOOK(sub_920B75A0, GetRenderStateHook<67>);  // D3DDevice_GetRenderState_Wrap7  // rr6-nx: the game's state table; Katamari 824DCD80 hexichd-nx: rr6 82256430
BANJO_RENUT_HOOK(sub_920B75B0, GetRenderStateHook<68>);  // D3DDevice_GetRenderState_Wrap8  // rr6-nx: the game's state table; Katamari 824DCD90 hexichd-nx: rr6 82256440
BANJO_RENUT_HOOK(sub_920B75C0, GetRenderStateHook<69>);  // D3DDevice_GetRenderState_Wrap9  // rr6-nx: the game's state table; Katamari 824DCDA0 hexichd-nx: rr6 82256450
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DCDB0, GetRenderStateHook<70>);  // D3DDevice_GetRenderState_Wrap10  // rr6-nx: not hooked in this XDK; Katamari 824DCDB0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DCDC0, GetRenderStateHook<71>);  // D3DDevice_GetRenderState_Wrap11  // rr6-nx: not hooked in this XDK; Katamari 824DCDC0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DCDD0, GetRenderStateHook<72>);  // D3DDevice_GetRenderState_Wrap12  // rr6-nx: not hooked in this XDK; Katamari 824DCDD0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DCDE0, GetRenderStateHook<73>);  // D3DDevice_GetRenderState_Wrap13  // rr6-nx: not hooked in this XDK; Katamari 824DCDE0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DCDF0, GetRenderStateHook<74>);  // D3DDevice_GetRenderState_Wrap14  // rr6-nx: not hooked in this XDK; Katamari 824DCDF0
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DCE00, GetRenderStateHook<75>);  // D3DDevice_GetRenderState_Wrap15  // rr6-nx: not hooked in this XDK; Katamari 824DCE00
BANJO_RENUT_HOOK(sub_920B7640, GetRenderStateHook<76>);  // D3DDevice_GetRenderState_ViewportEnable  // rr6-nx: the game's state table; Katamari 824DCE50 hexichd-nx: rr6 822564D0
BANJO_RENUT_HOOK(sub_920B7700, GetRenderStateHook<77>);  // D3DDevice_GetRenderState_HighPrecisionBlendEnable  // rr6-nx: the game's state table; Katamari 824DCF08 hexichd-nx: rr6 82256590
BANJO_RENUT_HOOK(sub_920B77B8, GetRenderStateHook<78>);  // D3DDevice_GetRenderState_HighPrecisionBlendEnable1  // rr6-nx: the game's state table; Katamari 824DCFB8 hexichd-nx: rr6 82256648
BANJO_RENUT_HOOK(sub_920B7870, GetRenderStateHook<79>);  // D3DDevice_GetRenderState_HighPrecisionBlendEnable2  // rr6-nx: the game's state table; Katamari 824DD068 hexichd-nx: rr6 82256700
BANJO_RENUT_HOOK(sub_920B7928, GetRenderStateHook<80>);  // D3DDevice_GetRenderState_HighPrecisionBlendEnable3  // rr6-nx: the game's state table; Katamari 824DD118 hexichd-nx: rr6 822567B8
BANJO_RENUT_HOOK(sub_920B79E8, GetRenderStateHook<81>);  // D3DDevice_GetRenderState_HalfPixelOffset  // rr6-nx: the game's state table; Katamari 824DD1F0 hexichd-nx: rr6 82256878
BANJO_RENUT_HOOK(sub_920B7A20, GetRenderStateHook<82>);  // D3DDevice_GetRenderState_PrimitiveResetEnable  // rr6-nx: the game's state table; Katamari 824DD220 hexichd-nx: rr6 822568B0
BANJO_RENUT_HOOK(sub_920B7A50, GetRenderStateHook<83>);  // D3DDevice_GetRenderState_PrimitiveResetIndex  // rr6-nx: the game's state table; Katamari 824DD250 hexichd-nx: rr6 822568E0
BANJO_RENUT_HOOK(sub_920B7A80, GetRenderStateHook<84>);  // D3DDevice_GetRenderState_AlphaToMaskEnable  // rr6-nx: the game's state table; Katamari 824DD278 hexichd-nx: rr6 82256910
BANJO_RENUT_HOOK(sub_920B7AB8, GetRenderStateHook<85>);  // D3DDevice_GetRenderState_AlphaToMaskOffsets  // rr6-nx: the game's state table; Katamari 824DD2A8 hexichd-nx: rr6 82256948
BANJO_RENUT_HOOK(sub_920B7AF8, GetRenderStateHook<86>);  // D3DDevice_GetRenderState_GuardBand_X  // rr6-nx: the game's state table; Katamari 824DD2E8 hexichd-nx: rr6 82256988
BANJO_RENUT_HOOK(sub_920B7B28, GetRenderStateHook<87>);  // D3DDevice_GetRenderState_GuardBand_Y  // rr6-nx: the game's state table; Katamari 824DD318 hexichd-nx: rr6 822569B8
BANJO_RENUT_HOOK(sub_920B7B58, GetRenderStateHook<88>);  // D3DDevice_GetRenderState_DiscardBand_X  // rr6-nx: the game's state table; Katamari 824DD340 hexichd-nx: rr6 822569E8
BANJO_RENUT_HOOK(sub_920B7B88, GetRenderStateHook<89>);  // D3DDevice_GetRenderState_DiscardBand_Y  // rr6-nx: the game's state table; Katamari 824DD370 hexichd-nx: rr6 82256A18
BANJO_RENUT_HOOK(sub_920B7BB8, GetRenderStateHook<90>);  // D3DDevice_GetRenderState_HiStencilEnable  // rr6-nx: the game's state table; Katamari 824DD430 hexichd-nx: rr6 82256A48
BANJO_RENUT_HOOK(sub_920B7BF0, GetRenderStateHook<91>);  // D3DDevice_GetRenderState_HiStencilWriteEnable  // rr6-nx: the game's state table; Katamari 824DD460 hexichd-nx: rr6 82256A80
BANJO_RENUT_HOOK(sub_920B7C28, GetRenderStateHook<92>);  // D3DDevice_GetRenderState_HiStencilFunc  // rr6-nx: the game's state table; Katamari 824DD490 hexichd-nx: rr6 82256AB8
BANJO_RENUT_HOOK(sub_920B7C58, GetRenderStateHook<93>);  // D3DDevice_GetRenderState_HiStencilRef  // rr6-nx: the game's state table; Katamari 824DD4B8 hexichd-nx: rr6 82256AE8
BANJO_RENUT_HOOK(sub_920B7C68, GetRenderStateHook<94>);  // D3DDevice_GetRenderState_PresentInterval  // rr6-nx: the game's state table; Katamari 824DD4C8 hexichd-nx: rr6 82256AF8
BANJO_RENUT_HOOK(sub_920B7C80, GetRenderStateHook<95>);  // D3DDevice_GetRenderState_PresentImmediateThreshold  // rr6-nx: the game's state table; Katamari 824DD4E0 hexichd-nx: rr6 82256B10
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DD398, GetRenderStateHook<96>);  // D3DDevice_GetRenderState_HiZEnable  // rr6-nx: not hooked in this XDK; Katamari 824DD398
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DD400, GetRenderStateHook<97>);  // D3DDevice_GetRenderState_HiZWriteEnable  // rr6-nx: not hooked in this XDK; Katamari 824DD400
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DC248, GetRenderStateHook<98>);  // D3DDevice_GetRenderState_LastPixel  // rr6-nx: not hooked in this XDK; Katamari 824DC248
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DC298, GetRenderStateHook<99>);  // D3DDevice_GetRenderState_LineWidth  // rr6-nx: not hooked in this XDK; Katamari 824DC298
BANJO_RENUT_UNHOOKED_HOOK(unlinked_824DC2E8, GetRenderStateHook<100>);  // D3DDevice_GetRenderState_Buffer2Frames  // rr6-nx: not hooked in this XDK; Katamari 824DC2E8

// Sampler state getters (off_82E50BD0, field 0).
BANJO_RENUT_HOOK(sub_920B82B8, GetSamplerStateHook<0>);  // D3DDevice_GetSamplerState_AddressU  // rr6-nx: the game's state table; Katamari 824DDC68 hexichd-nx: rr6 82257148
BANJO_RENUT_HOOK(sub_920B8308, GetSamplerStateHook<1>);  // D3DDevice_GetSamplerState_AddressV  // rr6-nx: the game's state table; Katamari 824DDCB8 hexichd-nx: rr6 82257198
BANJO_RENUT_HOOK(sub_920B8358, GetSamplerStateHook<2>);  // D3DDevice_GetSamplerState_AddressW  // rr6-nx: the game's state table; Katamari 824DDD08 hexichd-nx: rr6 822571E8
BANJO_RENUT_HOOK(sub_920B8260, GetSamplerStateHook<3>);  // D3DDevice_GetSamplerState_BorderColor  // rr6-nx: the game's state table; Katamari 824DDC10 hexichd-nx: rr6 822570F0
BANJO_RENUT_HOOK(sub_920B7E28, GetSamplerStateHook<4>);  // D3DDevice_GetSamplerState_MagFilter  // rr6-nx: the game's state table; Katamari 824DD740 hexichd-nx: rr6 82256CB8
BANJO_RENUT_HOOK(sub_920B7D18, GetSamplerStateHook<5>);  // D3DDevice_GetSamplerState_MinFilter  // rr6-nx: the game's state table; Katamari 824DD5B0 hexichd-nx: rr6 82256BA8
BANJO_RENUT_HOOK(sub_920B7EE8, GetSamplerStateHook<6>);  // D3DDevice_GetSamplerState_MipFilter  // rr6-nx: the game's state table; Katamari 824DD850 hexichd-nx: rr6 82256D78
BANJO_RENUT_HOOK(sub_920B80D0, GetSamplerStateHook<7>);  // D3DDevice_GetSamplerState_MipMapLodBias  // rr6-nx: the game's state table; Katamari 824DDA80 hexichd-nx: rr6 82256F60
BANJO_RENUT_HOOK(sub_920B8180, GetSamplerStateHook<8>);  // D3DDevice_GetSamplerState_MaxMipLevel  // rr6-nx: the game's state table; Katamari 824DDB30 hexichd-nx: rr6 82257010
BANJO_RENUT_HOOK(sub_920B7FB8, GetSamplerStateHook<9>);  // D3DDevice_GetSamplerState_MaxAnisotropy  // rr6-nx: the game's state table; Katamari 824DD968 hexichd-nx: rr6 82256E48
BANJO_RENUT_HOOK(sub_920B7E98, GetSamplerStateHook<10>);  // D3DDevice_GetSamplerState_MagFilterZ  // rr6-nx: the game's state table; Katamari 824DD800 hexichd-nx: rr6 82256D28
BANJO_RENUT_HOOK(sub_920B7D90, GetSamplerStateHook<11>);  // D3DDevice_GetSamplerState_MinFilterZ  // rr6-nx: the game's state table; Katamari 824DD670 hexichd-nx: rr6 82256C20
BANJO_RENUT_HOOK(sub_920B7F40, GetSamplerStateHook<12>);  // D3DDevice_GetSamplerState_SeparateZFilterEnable  // rr6-nx: the game's state table; Katamari 824DD8F0 hexichd-nx: rr6 82256DD0
BANJO_RENUT_HOOK(sub_920B8200, GetSamplerStateHook<13>);  // D3DDevice_GetSamplerState_MinMipLevel  // rr6-nx: the game's state table; Katamari 824DDBB0 hexichd-nx: rr6 82257090
BANJO_RENUT_HOOK(sub_920B83B0, GetSamplerStateHook<14>);  // D3DDevice_GetSamplerState_TrilinearThreshold  // rr6-nx: the game's state table; Katamari 824DDD60 hexichd-nx: rr6 82257240
BANJO_RENUT_HOOK(sub_920B8028, GetSamplerStateHook<15>);  // D3DDevice_GetSamplerState_AnisotropyBias  // rr6-nx: the game's state table; Katamari 824DD9D8 hexichd-nx: rr6 82256EB8
BANJO_RENUT_HOOK(sub_920B8408, GetSamplerStateHook<16>);  // D3DDevice_GetSamplerState_HGradientExpBias  // rr6-nx: the game's state table; Katamari 824DDDB8 hexichd-nx: rr6 82257298
BANJO_RENUT_HOOK(sub_920B8460, GetSamplerStateHook<17>);  // D3DDevice_GetSamplerState_VGradientExpBias  // rr6-nx: the game's state table; Katamari 824DDE10 hexichd-nx: rr6 822572F0
BANJO_RENUT_HOOK(sub_920B84B8, GetSamplerStateHook<18>);  // D3DDevice_GetSamplerState_WhiteBorderColorW  // rr6-nx: the game's state table; Katamari 824DDE68 hexichd-nx: rr6 82257348
BANJO_RENUT_HOOK(sub_920B8518, GetSamplerStateHook<19>);  // D3DDevice_GetSamplerState_PointBorderEnable  // rr6-nx: the game's state table; Katamari 824DDEC8 hexichd-nx: rr6 822573A8
BANJO_RENUT_HOOK(sub_920B75D0, Rr6SetRenderState57);  // rr6-nx: the state table, row 57 hexichd-nx: rr6 82256460
BANJO_RENUT_HOOK(sub_920B75E8, Rr6GetRenderState57);  // rr6-nx: the state table, row 57 hexichd-nx: rr6 82256478

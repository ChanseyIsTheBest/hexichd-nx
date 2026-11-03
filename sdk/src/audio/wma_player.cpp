/**
 * @file    audio/wma_player.cpp
 * @brief   See rex/audio/wma_player.h.
 *
 * The ASF layout: "Advanced Systems Format Specification", the header's File Properties and Stream Properties objects and the Data
 * object's packets. Audio spread with a span above 1 (interleaved blocks) is not handled: it is refused with a log line. All 15 of the
 * two Hexic games' files have span 1.
 */
#include <rex/audio/wma_player.h>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>

#include <rex/audio/audio_system.h>
#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/memory.h>

extern "C" {
#include "libavcodec/avcodec.h"
#include "libavutil/mem.h"
}

REXCVAR_DEFINE_STRING(xmp_dump_pcm, "", "Audio",
                      "Diagnostic: the path of a file for the music player's output, as it leaves the resampler: 48 kHz, stereo interleaved, "
                      "32-bit float (hexic2-nx: tools/pcm_stats.py measures it)");

namespace rex::audio {

namespace {

// As they appear in the file (the GUIDs' mixed-endian bytes).
constexpr uint8_t kGuidHeader[16] = {0x30, 0x26, 0xB2, 0x75, 0x8E, 0x66, 0xCF, 0x11, 0xA6, 0xD9, 0x00, 0xAA, 0x00, 0x62, 0xCE, 0x6C};
constexpr uint8_t kGuidData[16] = {0x36, 0x26, 0xB2, 0x75, 0x8E, 0x66, 0xCF, 0x11, 0xA6, 0xD9, 0x00, 0xAA, 0x00, 0x62, 0xCE, 0x6C};
constexpr uint8_t kGuidFileProperties[16] = {0xA1, 0xDC, 0xAB, 0x8C, 0x47, 0xA9, 0xCF, 0x11, 0x8E, 0xE4, 0x00, 0xC0, 0x0C, 0x20, 0x53, 0x65};
constexpr uint8_t kGuidStreamProperties[16] = {0x91, 0x07, 0xDC, 0xB7, 0xB7, 0xA9, 0xCF, 0x11, 0x8E, 0xE6, 0x00, 0xC0, 0x0C, 0x20, 0x53, 0x65};
constexpr uint8_t kGuidAudioMedia[16] = {0x40, 0x9E, 0x69, 0xF8, 0x4D, 0x5B, 0xCF, 0x11, 0xA8, 0xFD, 0x00, 0x80, 0x5F, 0x5C, 0x44, 0x2B};
constexpr uint8_t kGuidAudioSpread[16] = {0x50, 0xCD, 0xC3, 0xBF, 0x8F, 0x61, 0xCF, 0x11, 0x8B, 0xB2, 0x00, 0xAA, 0x00, 0xB4, 0xE2, 0x20};

uint16_t Le16(const uint8_t* p) { return uint16_t(p[0] | p[1] << 8); }
uint32_t Le32(const uint8_t* p) { return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24; }
uint64_t Le64(const uint8_t* p) { return uint64_t(Le32(p)) | uint64_t(Le32(p + 4)) << 32; }

struct AsfInfo {
  uint32_t packet_size = 0;
  uint64_t data_offset = 0;
  uint32_t stream = 0;
  uint32_t tag = 0;
  uint32_t channels = 0;
  uint32_t rate = 0;
  uint32_t bit_rate = 0;
  uint32_t block_align = 0;
  std::vector<uint8_t> extra;
};

bool ParseHeader(const WmaPlayer::Reader& read, AsfInfo& info, const std::string& name) {
  uint8_t head[30];
  if (read(head, sizeof(head), 0) != sizeof(head) || std::memcmp(head, kGuidHeader, 16) != 0) {
    REXAPU_WARN("[xmp] {}: not an ASF file", name);
    return false;
  }
  const uint64_t header_size = Le64(head + 16);
  if (header_size < 30 || header_size > (uint64_t(1) << 22)) {
    REXAPU_WARN("[xmp] {}: ASF header of {} bytes", name, header_size);
    return false;
  }
  std::vector<uint8_t> header(size_t(header_size) + 24);
  if (read(header.data(), header.size(), 0) != header.size()) {
    return false;
  }
  for (size_t at = 30; at + 24 <= size_t(header_size);) {
    const uint8_t* object = header.data() + at;
    const uint64_t size = Le64(object + 16);
    if (size < 24 || at + size > size_t(header_size)) {
      break;
    }
    const uint8_t* body = object + 24;
    if (std::memcmp(object, kGuidFileProperties, 16) == 0 && size >= 24 + 80) {
      info.packet_size = Le32(body + 68);
    } else if (std::memcmp(object, kGuidStreamProperties, 16) == 0 && size >= 24 + 54 + 18 && !info.tag &&
               std::memcmp(body, kGuidAudioMedia, 16) == 0) {
      const uint32_t type_size = Le32(body + 40);
      const uint32_t ec_size = Le32(body + 44);
      const uint8_t* format = body + 54;
      if (type_size < 18 || 24 + 54 + uint64_t(type_size) + ec_size > size) {
        break;
      }
      if (std::memcmp(body + 16, kGuidAudioSpread, 16) == 0 && ec_size >= 1 && format[type_size] > 1) {
        REXAPU_WARN("[xmp] {}: audio spread with a span of {} is not handled", name, format[type_size]);
        return false;
      }
      info.stream = Le16(body + 48) & 0x7F;
      info.tag = Le16(format);
      info.channels = Le16(format + 2);
      info.rate = Le32(format + 4);
      info.bit_rate = Le32(format + 8) * 8;
      info.block_align = Le16(format + 12);
      const uint32_t extra = std::min<uint32_t>(Le16(format + 16), type_size - 18);
      info.extra.assign(format + 18, format + 18 + extra);
    }
    at += size_t(size);
  }
  const uint8_t* data = header.data() + size_t(header_size);
  if (std::memcmp(data, kGuidData, 16) != 0 || !info.packet_size || !info.tag || !info.block_align) {
    REXAPU_WARN("[xmp] {}: no audio stream or data object in the ASF header", name);
    return false;
  }
  info.data_offset = header_size + 50;  // the Data object's own header
  return true;
}

// A field of the size a two-bit type gives: none, a byte, a word, a dword. False past the end.
bool ReadField(const uint8_t* packet, size_t end, size_t& at, uint32_t type, uint32_t& out) {
  static constexpr uint32_t kSizes[4] = {0, 1, 2, 4};
  const uint32_t bytes = kSizes[type & 3];
  if (at + bytes > end) {
    return false;
  }
  out = bytes == 0 ? 0 : bytes == 1 ? packet[at] : bytes == 2 ? Le16(packet + at) : Le32(packet + at);
  at += bytes;
  return true;
}

// Appends the packet's payloads of 'stream' to 'pending'. A bad packet is dropped.
void ParsePacket(const uint8_t* packet, size_t size, uint32_t stream, std::vector<uint8_t>& pending) {
  size_t at = 0;
  if (size < 8) {
    return;
  }
  uint8_t flags = packet[at++];
  if (flags & 0x80) {  // error correction data, then the length type flags
    at += flags & 0x0F;
    if (at + 2 > size) {
      return;
    }
    flags = packet[at++];
  }
  const uint8_t properties = packet[at++];
  uint32_t packet_length = 0, sequence = 0, padding = 0;
  if (!ReadField(packet, size, at, (flags >> 5) & 3, packet_length) || !ReadField(packet, size, at, (flags >> 1) & 3, sequence) ||
      !ReadField(packet, size, at, (flags >> 3) & 3, padding)) {
    return;
  }
  at += 6;  // send time, duration
  size_t end = packet_length && packet_length <= size ? packet_length : size;
  if (padding >= end || at >= end - padding) {
    return;
  }
  end -= padding;
  const bool multiple = flags & 1;
  uint32_t payloads = 1, length_type = 0;
  if (multiple) {
    const uint8_t payload_flags = packet[at++];
    payloads = payload_flags & 0x3F;
    length_type = payload_flags >> 6;
  }
  for (uint32_t i = 0; i < payloads && at < end; ++i) {
    const uint32_t number = packet[at++] & 0x7F;
    uint32_t object = 0, offset = 0, replicated = 0;
    if (!ReadField(packet, end, at, (properties >> 4) & 3, object) || !ReadField(packet, end, at, (properties >> 2) & 3, offset) ||
        !ReadField(packet, end, at, properties & 3, replicated)) {
      return;
    }
    const bool compressed = replicated == 1;
    at += replicated;
    uint32_t length = 0;
    if (multiple) {
      if (!ReadField(packet, end, at, length_type, length)) {
        return;
      }
    } else if (at <= end) {
      length = uint32_t(end - at);
    }
    if (at + length > end) {
      return;
    }
    if (number == stream) {
      if (compressed) {  // sub-payloads: a length byte before each
        for (size_t sub = at; sub < at + length;) {
          const uint32_t sub_length = packet[sub++];
          if (sub + sub_length > at + length) {
            break;
          }
          pending.insert(pending.end(), packet + sub, packet + sub + sub_length);
          sub += sub_length;
        }
      } else {
        pending.insert(pending.end(), packet + at, packet + at + length);
      }
    }
    at += length;
  }
}

// Catmull-Rom through four samples, t from b to c: music at 44.1 kHz going up to 48 kHz.
inline float Cubic(float a, float b, float c, float d, float t) {
  const float t2 = t * t;
  return b + 0.5f * t * (c - a) + t2 * (a - 2.5f * b + 2.0f * c - 0.5f * d) + t2 * t * (1.5f * (b - c) + 0.5f * (d - a));
}

}  // namespace

WmaPlayer::WmaPlayer(AudioSystem* audio) : audio_(audio), ring_(size_t(kRingFrames) * 2) {}

WmaPlayer::~WmaPlayer() { Shutdown(); }

bool WmaPlayer::ClientUp() {
  if (client_up_) {
    return true;
  }
  auto* memory = audio_->memory();
  if (!frame_va_) {
    frame_va_ = memory->SystemHeapAlloc(kFrameFloats * sizeof(float));
    if (!frame_va_) {
      return false;
    }
    std::memset(memory->TranslateVirtual(frame_va_), 0, kFrameFloats * sizeof(float));  // the four other channels stay silent
  }
  if (XFAILED(audio_->RegisterHostClient(&WmaPlayer::FrameCallback, this, &client_))) {
    REXAPU_WARN("[xmp] no audio client for the music");
    return false;
  }
  client_up_ = true;
  return true;
}

void WmaPlayer::Play(Reader reader, std::string name, SongEnded on_end) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (shutting_down_.load(std::memory_order_acquire) || !ClientUp()) {
    return;
  }
  if (!thread_) {
    rex::thread::Thread::CreationParameters params;
    params.stack_size = 256 * 1024;
    thread_ = rex::thread::Thread::Create(params, [this]() { ThreadMain(); });
    if (!thread_) {
      REXAPU_WARN("[xmp] no thread for the music");
      return;
    }
    thread_->set_name("WMA player");
  }
  next_reader_ = std::move(reader);
  next_name_ = std::move(name);
  next_on_end_ = std::move(on_end);
  {
    std::lock_guard<std::mutex> ring_lock(ring_mutex_);
    generation_.fetch_add(1, std::memory_order_acq_rel);
    ring_read_ = ring_used_ = 0;
  }
  wake_.notify_all();
}

void WmaPlayer::Stop() {
  bool unregister = false;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    next_reader_ = nullptr;
    next_on_end_ = nullptr;
    {
      std::lock_guard<std::mutex> ring_lock(ring_mutex_);
      generation_.fetch_add(1, std::memory_order_acq_rel);
      ring_read_ = ring_used_ = 0;
    }
    unregister = client_up_;
    client_up_ = false;
  }
  wake_.notify_all();
  if (unregister) {
    audio_->UnregisterClient(client_);  // no frames for a music that is not playing
  }
}

void WmaPlayer::Shutdown() {
  if (shutting_down_.exchange(true, std::memory_order_acq_rel)) {
    return;
  }
  {
    std::lock_guard<std::mutex> lock(mutex_);
    std::lock_guard<std::mutex> ring_lock(ring_mutex_);
    generation_.fetch_add(1, std::memory_order_acq_rel);
  }
  wake_.notify_all();
  if (thread_) {
    rex::thread::Wait(thread_.get(), false, std::chrono::seconds(2));
    thread_.reset();
  }
  // The audio system destroys its clients after this.
}

void WmaPlayer::FrameCallback(void* self) { static_cast<WmaPlayer*>(self)->OnFrame(); }

void WmaPlayer::OnFrame() {
  // On the audio worker, once for each frame the output consumed: a client that submits nothing gets no more callbacks, so a frame goes
  // out every time, silent if need be.
  float left[kChannelSamples], right[kChannelSamples];
  uint32_t frames = 0;
  if (!paused_.load(std::memory_order_relaxed)) {
    std::lock_guard<std::mutex> lock(ring_mutex_);
    frames = std::min(ring_used_, kChannelSamples);
    for (uint32_t i = 0; i < frames; ++i) {
      left[i] = ring_[size_t(ring_read_) * 2];
      right[i] = ring_[size_t(ring_read_) * 2 + 1];
      ring_read_ = ring_read_ + 1 == kRingFrames ? 0 : ring_read_ + 1;
    }
    ring_used_ -= frames;
  }
  for (uint32_t i = frames; i < kChannelSamples; ++i) {
    left[i] = right[i] = 0.0f;
  }
  const float gain = volume_.load(std::memory_order_relaxed);
  auto* out = audio_->memory()->TranslateVirtual<uint32_t*>(frame_va_);
  for (uint32_t i = 0; i < kChannelSamples; ++i) {
    const float l = left[i] * gain, r = right[i] * gain;
    uint32_t lw, rw;
    std::memcpy(&lw, &l, 4);
    std::memcpy(&rw, &r, 4);
    out[i] = rex::byte_swap(lw);
    out[kChannelSamples + i] = rex::byte_swap(rw);
  }
  audio_->SubmitFrame(client_, frame_va_);
}

bool WmaPlayer::WaitForRoom(uint64_t generation) {
  // Half the ring empties in a quarter of a second: decode in bursts rather than wake for each block.
  std::unique_lock<std::mutex> lock(mutex_);
  wake_.wait_for(lock, std::chrono::milliseconds(200),
                 [&] { return generation_.load(std::memory_order_acquire) != generation; });
  return generation_.load(std::memory_order_acquire) == generation;
}

bool WmaPlayer::PushOutput(const float* stereo, uint32_t frames, uint64_t generation) {
  // Diagnostic (xmp_dump_pcm): the output before the ring, for measuring what the player makes without an ear on it.
  static const std::string dump_path = REXCVAR_GET(xmp_dump_pcm);
  if (!dump_path.empty()) [[unlikely]] {
    static FILE* dump = std::fopen(dump_path.c_str(), "wb");
    if (dump) {
      std::fwrite(stereo, sizeof(float) * 2, frames, dump);
      std::fflush(dump);
    }
  }
  while (frames) {
    uint32_t pushed = 0;
    {
      std::lock_guard<std::mutex> lock(ring_mutex_);
      if (generation_.load(std::memory_order_acquire) != generation) {
        return false;
      }
      pushed = std::min(frames, kRingFrames - ring_used_);
      uint32_t write = ring_read_ + ring_used_;
      write = write >= kRingFrames ? write - kRingFrames : write;
      for (uint32_t i = 0; i < pushed; ++i) {
        ring_[size_t(write) * 2] = stereo[size_t(i) * 2];
        ring_[size_t(write) * 2 + 1] = stereo[size_t(i) * 2 + 1];
        write = write + 1 == kRingFrames ? 0 : write + 1;
      }
      ring_used_ += pushed;
    }
    stereo += size_t(pushed) * 2;
    frames -= pushed;
    if (frames && !WaitForRoom(generation)) {
      return false;
    }
  }
  return true;
}

void WmaPlayer::Resample(const float* left, const float* right, uint32_t count, uint64_t generation) {
  in_left_.insert(in_left_.end(), left, left + count);
  in_right_.insert(in_right_.end(), right, right + count);
  out_.clear();
  const size_t available = in_left_.size();
  double position = position_;
  while (position + 2.0 < double(available)) {
    const size_t i = size_t(position);
    const float t = float(position - double(i));
    out_.push_back(Cubic(in_left_[i - 1], in_left_[i], in_left_[i + 1], in_left_[i + 2], t));
    out_.push_back(Cubic(in_right_[i - 1], in_right_[i], in_right_[i + 1], in_right_[i + 2], t));
    position += step_;
  }
  // What the next call still needs: the sample before the position on.
  const size_t keep_from = std::min(size_t(position) - 1, available);
  in_left_.erase(in_left_.begin(), in_left_.begin() + keep_from);
  in_right_.erase(in_right_.begin(), in_right_.begin() + keep_from);
  position_ = position - double(keep_from);
  PushOutput(out_.data(), uint32_t(out_.size() / 2), generation);
}

void WmaPlayer::PlaySong(const Reader& read, const std::string& name, uint64_t generation) {
  AsfInfo info;
  if (!ParseHeader(read, info, name)) {
    return;
  }
  const AVCodecID id = info.tag == 0x0161 ? AV_CODEC_ID_WMAV2 : info.tag == 0x0162 ? AV_CODEC_ID_WMAPRO : AV_CODEC_ID_NONE;
  const AVCodec* codec = id == AV_CODEC_ID_NONE ? nullptr : avcodec_find_decoder(id);
  if (!codec) {
    REXAPU_WARN("[xmp] {}: no decoder for codec 0x{:04X}", name, info.tag);
    return;
  }
  AVCodecContext* context = avcodec_alloc_context3(codec);
  AVPacket* packet = av_packet_alloc();
  AVFrame* frame = av_frame_alloc();
  uint8_t* extra = nullptr;
  if (context && packet && frame) {
    context->sample_rate = int(info.rate);
    context->channels = int(info.channels);
    context->bit_rate = info.bit_rate;
    context->block_align = int(info.block_align);
    if (!info.extra.empty()) {
      extra = static_cast<uint8_t*>(av_mallocz(info.extra.size() + AV_INPUT_BUFFER_PADDING_SIZE));
      if (extra) {
        std::memcpy(extra, info.extra.data(), info.extra.size());
        context->extradata = extra;  // the context frees it
        context->extradata_size = int(info.extra.size());
      }
    }
  }
  if (!context || !packet || !frame || avcodec_open2(context, codec, nullptr) < 0) {
    REXAPU_WARN("[xmp] {}: the decoder would not open ({} Hz, {} channels, block {})", name, info.rate, info.channels, info.block_align);
    av_frame_free(&frame);
    av_packet_free(&packet);
    avcodec_free_context(&context);
    return;
  }
  REXAPU_INFO("[xmp] {}: codec 0x{:04X}, {} Hz, {} channels, {} kbps, blocks of {} in packets of {}", name, info.tag, info.rate,
              info.channels, info.bit_rate / 1000, info.block_align, info.packet_size);

  in_left_.assign(1, 0.0f);
  in_right_.assign(1, 0.0f);
  position_ = 1.0;
  step_ = double(info.rate) / double(kOutputRate);

  const auto started = std::chrono::steady_clock::now();
  std::chrono::steady_clock::duration waited{};
  uint64_t decoded_samples = 0;
  std::vector<uint8_t> packet_bytes(info.packet_size);
  std::vector<uint8_t> pending;
  std::vector<uint8_t> block(size_t(info.block_align) + AV_INPUT_BUFFER_PADDING_SIZE);
  std::vector<float> mono;

  const auto take_frames = [&]() {
    while (avcodec_receive_frame(context, frame) == 0) {
      const uint32_t samples = uint32_t(frame->nb_samples);
      decoded_samples += samples;
      if (frame->format != AV_SAMPLE_FMT_FLTP || !frame->data[0]) {
        continue;
      }
      const float* left = reinterpret_cast<const float*>(frame->data[0]);
      const float* right = info.channels >= 2 && frame->data[1] ? reinterpret_cast<const float*>(frame->data[1]) : left;
      const auto before = std::chrono::steady_clock::now();
      Resample(left, right, samples, generation);
      waited += std::chrono::steady_clock::now() - before;
    }
  };

  uint64_t offset = info.data_offset;
  bool current = true;
  while ((current = generation_.load(std::memory_order_acquire) == generation)) {
    if (read(packet_bytes.data(), packet_bytes.size(), offset) != packet_bytes.size()) {
      break;  // the end of the file
    }
    offset += packet_bytes.size();
    ParsePacket(packet_bytes.data(), packet_bytes.size(), info.stream, pending);
    size_t used = 0;
    while (pending.size() - used >= info.block_align) {
      std::memcpy(block.data(), pending.data() + used, info.block_align);
      used += info.block_align;
      packet->data = block.data();
      packet->size = int(info.block_align);
      if (avcodec_send_packet(context, packet) == 0) {
        take_frames();
      }
    }
    pending.erase(pending.begin(), pending.begin() + used);
  }
  if (current) {
    avcodec_send_packet(context, nullptr);
    take_frames();
  }
  av_frame_free(&frame);
  av_packet_free(&packet);
  avcodec_free_context(&context);

  const double busy_ms =
      std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started - waited).count();
  REXAPU_INFO("[xmp] {}: {:.1f} s of audio decoded, {:.0f} ms reading and decoding{}", name, double(decoded_samples) / double(info.rate),
              busy_ms, current ? "" : " (stopped)");

  // Let the ring play out before the song counts as ended.
  while (generation_.load(std::memory_order_acquire) == generation) {
    {
      std::lock_guard<std::mutex> lock(ring_mutex_);
      if (!ring_used_) {
        break;
      }
    }
    std::unique_lock<std::mutex> lock(mutex_);
    wake_.wait_for(lock, std::chrono::milliseconds(20),
                   [&] { return generation_.load(std::memory_order_acquire) != generation; });
  }
}

void WmaPlayer::ThreadMain() {
  for (;;) {
    Reader reader;
    std::string name;
    SongEnded on_end;
    uint64_t generation;
    {
      std::unique_lock<std::mutex> lock(mutex_);
      wake_.wait(lock, [&] { return shutting_down_.load(std::memory_order_acquire) || next_reader_ != nullptr; });
      if (shutting_down_.load(std::memory_order_acquire)) {
        return;
      }
      reader = std::move(next_reader_);
      next_reader_ = nullptr;
      name = std::move(next_name_);
      on_end = std::move(next_on_end_);
      next_on_end_ = nullptr;
      generation = generation_.load(std::memory_order_acquire);
    }
    const auto started = std::chrono::steady_clock::now();
    PlaySong(reader, name, generation);
    reader = nullptr;  // closes the file
    // A song that could not be played ends at once: without this pause a playlist of them spins through the files as fast as they open.
    if (std::chrono::steady_clock::now() - started < std::chrono::seconds(1)) {
      std::unique_lock<std::mutex> lock(mutex_);
      wake_.wait_for(lock, std::chrono::seconds(5),
                     [&] { return generation_.load(std::memory_order_acquire) != generation; });
    }
    if (generation_.load(std::memory_order_acquire) == generation && on_end) {
      on_end();
    }
  }
}

}  // namespace rex::audio

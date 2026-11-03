/**
 * @file    rex/audio/wma_player.h
 * @brief   Plays WMA files as a host audio client: the Xbox's media player's title playlists (kernel/xam/apps/xmp_app.cpp).
 *
 * hexic2-nx (2026-11-04): the SDK answered XMPPlayTitlePlaylist with a warning and no sound, so a game that plays its music this way
 * (both Hexic games: WMA v2, 44.1 kHz stereo, in ASF files beside the game) was silent. A thread reads a song from the file system,
 * decodes it with the SDK's FFmpeg and resamples it to the audio system's 48 kHz into a half-second ring; the audio worker takes one
 * frame from the ring for each frame the output consumes (AudioSystem::RegisterHostClient). Reading and decoding stay off the worker:
 * an SD read must not hold up the game's own audio callback.
 */
#pragma once

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include <rex/thread.h>

namespace rex::audio {

class AudioSystem;

class WmaPlayer {
 public:
  // Reads up to 'size' bytes at 'offset'; returns the bytes read (0 at the end or on an error). Called on the player's thread only.
  using Reader = std::function<size_t(uint8_t* out, size_t size, uint64_t offset)>;
  // The song played out, or could not be played. On the player's thread: it may call Play or Stop.
  using SongEnded = std::function<void()>;

  explicit WmaPlayer(AudioSystem* audio);
  ~WmaPlayer();

  // Replaces whatever is playing.
  void Play(Reader reader, std::string name, SongEnded on_end);
  void Stop();
  void SetPaused(bool paused) { paused_.store(paused, std::memory_order_relaxed); }
  void SetVolume(float volume) { volume_.store(volume, std::memory_order_relaxed); }
  // Before the audio system goes away.
  void Shutdown();

 private:
  static constexpr uint32_t kOutputRate = 48000;
  static constexpr uint32_t kChannelSamples = 256;  // of a frame of the audio system
  static constexpr uint32_t kFrameFloats = kChannelSamples * 6;
  static constexpr uint32_t kRingFrames = kOutputRate / 2;

  static void FrameCallback(void* self);
  void OnFrame();
  void ThreadMain();
  void PlaySong(const Reader& read, const std::string& name, uint64_t generation);
  // False when this song is no longer the current one.
  bool WaitForRoom(uint64_t generation);
  bool PushOutput(const float* stereo, uint32_t frames, uint64_t generation);
  void Resample(const float* left, const float* right, uint32_t count, uint64_t generation);
  bool ClientUp();

  AudioSystem* audio_;
  std::unique_ptr<rex::thread::Thread> thread_;

  std::mutex mutex_;
  std::condition_variable wake_;  // a new song, a stop, the shutdown
  Reader next_reader_;
  std::string next_name_;
  SongEnded next_on_end_;
  std::atomic<uint64_t> generation_{0};
  std::atomic<bool> shutting_down_{false};

  std::mutex ring_mutex_;
  std::vector<float> ring_;  // stereo interleaved
  uint32_t ring_read_ = 0;
  uint32_t ring_used_ = 0;

  // The audio system's client.
  size_t client_ = 0;
  bool client_up_ = false;
  uint32_t frame_va_ = 0;
  std::atomic<bool> paused_{false};
  std::atomic<float> volume_{1.0f};

  // The resampler (the player's thread).
  std::vector<float> in_left_, in_right_;
  std::vector<float> out_;
  double position_ = 1.0;
  double step_ = 1.0;
};

}  // namespace rex::audio

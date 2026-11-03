#!/usr/bin/env python3
"""hexic2-nx (2026-11-04): measures the music player's output (the key xmp_dump_pcm: 48 kHz, stereo interleaved, 32-bit float), since a
test run has no ear on it: length, level, silence, clipping, how far the two channels differ, and where the sound's energy sits by second.
Music has a level that moves and its energy low in the spectrum; a decoder fed the wrong bytes gives flat noise or silence.

  python tools/pcm_stats.py <file.pcm> [--rate 48000] [--wav out.wav]
"""
import argparse
import array
import math
import wave


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--rate', type=int, default=48000)
    ap.add_argument('--wav', help='also write a 16-bit WAV, to listen to')
    a = ap.parse_args()
    samples = array.array('f')
    with open(a.path, 'rb') as f:
        data = f.read()
        samples.frombytes(data[:len(data) // 4 * 4])
    frames = len(samples) // 2
    if not frames:
        print('no samples')
        return
    print(f'{frames} frames, {frames / a.rate:.1f} s')
    peak = max(abs(x) for x in samples)
    bad = sum(1 for x in samples if x != x or abs(x) > 4.0)
    clipped = sum(1 for x in samples if abs(x) >= 1.0)
    print(f'peak {peak:.3f}, samples at or over full scale {clipped}, not finite or wild {bad}')
    per_second = []
    for s in range(frames // a.rate):
        start = s * a.rate * 2
        block = samples[start:start + a.rate * 2]
        rms = math.sqrt(sum(x * x for x in block) / len(block))
        left = block[0::2]
        right = block[1::2]
        side = math.sqrt(sum((l - r) ** 2 for l, r in zip(left, right)) / len(left))
        crossings = sum(1 for i in range(1, len(left)) if (left[i - 1] < 0) != (left[i] < 0))
        # Sample-to-sample change against the level: a smooth waveform is low, white noise near 1.4.
        roughness = math.sqrt(sum((left[i] - left[i - 1]) ** 2 for i in range(1, len(left))) / max(1, len(left) - 1)) / max(rms, 1e-9)
        per_second.append((rms, side, crossings, roughness))
    silent = sum(1 for r in per_second if r[0] < 1e-4)
    rms_values = [r[0] for r in per_second]
    print(f'{len(per_second)} seconds: {silent} silent; level {min(rms_values):.4f} to {max(rms_values):.4f}')
    print(f'zero crossings a second, median {sorted(r[2] for r in per_second)[len(per_second) // 2]} (white noise would be about {a.rate // 2})')
    print(f'roughness, median {sorted(r[3] for r in per_second)[len(per_second) // 2]:.3f} (smooth music well under 1; white noise about 1.41)')
    print(f'left minus right against the level, median {sorted(r[1] / max(r[0], 1e-9) for r in per_second)[len(per_second) // 2]:.3f} (0 is mono)')
    step = max(1, len(per_second) // 20)
    print('level by second: ' + ' '.join(f'{r[0]:.3f}' for r in per_second[::step]))
    if a.wav:
        with wave.open(a.wav, 'wb') as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(a.rate)
            out = array.array('h', (max(-32768, min(32767, int(x * 32767))) for x in samples))
            w.writeframes(out.tobytes())
        print('wrote', a.wav)


if __name__ == '__main__':
    main()

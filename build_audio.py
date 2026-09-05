#!/usr/bin/env python3
"""real.html が記録した衝突イベントから効果音入りWAVを合成する。"""

import json
import math
import random
import struct
import sys
import wave


SAMPLE_RATE = 48000
CHANNELS = 1


def envelope(position, length, attack=0.0015):
    attack_samples = max(1, int(attack * SAMPLE_RATE))
    return min(1.0, position / attack_samples) * math.exp(-5.5 * position / length)


def add_tone(mix, start, duration, frequency, volume, rng, noise=0.0, overtone=0.0):
    first = max(0, int(start * SAMPLE_RATE))
    length = max(1, int(duration * SAMPLE_RATE))
    for i in range(length):
        target = first + i
        if target >= len(mix):
            break
        phase = 2.0 * math.pi * frequency * i / SAMPLE_RATE
        signal = math.sin(phase)
        if overtone:
            signal += overtone * math.sin(phase * 2.37 + 0.35)
        if noise:
            signal += noise * rng.uniform(-1.0, 1.0)
        mix[target] += volume * envelope(i, length) * signal


def add_event(mix, event, rng):
    start = max(0.0, float(event.get("t", 0.0)))
    kind = event.get("type")
    if kind == "pin":
        add_tone(mix, start, 0.030, 2050.0, 0.38, rng, noise=0.35, overtone=0.32)
    elif kind == "wind":
        for offset, frequency in ((0.000, 1700.0), (0.012, 2180.0), (0.025, 1460.0)):
            add_tone(mix, start + offset, 0.018, frequency, 0.24, rng, noise=0.42, overtone=0.22)
    elif kind == "heso":
        add_tone(mix, start, 0.060, 2850.0, 0.5, rng, noise=0.04, overtone=0.28)
    elif kind == "out":
        add_tone(mix, start, 0.040, 310.0, 0.2, rng, noise=0.28, overtone=0.15)
    elif kind == "launch":
        add_tone(mix, start, 0.020, 760.0, 0.16, rng, noise=0.18, overtone=0.48)


def add_hall_ambience(mix, rng):
    # 低域に重みを置いた複数の一次フィルタを混ぜ、薄いピンクノイズ風にする。
    slow = medium = fast = 0.0
    for i in range(len(mix)):
        white = rng.uniform(-1.0, 1.0)
        slow = 0.997 * slow + 0.003 * white
        medium = 0.975 * medium + 0.025 * white
        fast = 0.82 * fast + 0.18 * white
        hum = math.sin(2.0 * math.pi * 60.0 * i / SAMPLE_RATE)
        mix[i] += 0.018 * (1.8 * slow + 0.8 * medium + 0.22 * fast) + 0.0022 * hum


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python3 build_audio.py events.json output.wav")

    with open(sys.argv[1], encoding="utf-8") as file:
        events = json.load(file)
    if not isinstance(events, list):
        raise SystemExit("events.json must contain a JSON array")

    final_time = max((float(event.get("t", 0.0)) for event in events), default=0.0)
    duration = max(1.0, final_time + 0.5)
    mix = [0.0] * int(math.ceil(duration * SAMPLE_RATE))
    rng = random.Random(3160)
    add_hall_ambience(mix, rng)
    for event in sorted(events, key=lambda item: float(item.get("t", 0.0))):
        add_event(mix, event, rng)

    peak = max((abs(sample) for sample in mix), default=1.0)
    gain = min(1.0, 0.92 / peak)
    pcm = bytearray()
    for sample in mix:
        value = max(-1.0, min(1.0, sample * gain))
        pcm.extend(struct.pack("<h", int(round(value * 32767))))

    with wave.open(sys.argv[2], "wb") as output:
        output.setnchannels(CHANNELS)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm)
    print(f"WAV: {sys.argv[2]} ({duration:.3f}s, {len(events)} events)")


if __name__ == "__main__":
    main()

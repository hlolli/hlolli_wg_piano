#!/usr/bin/env python3
"""Report simple, dependency-free measurements for PCM WAV renders."""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class WavData:
    sample_rate: int
    channels: List[List[float]]
    sample_width: int

    @property
    def frame_count(self) -> int:
        return len(self.channels[0]) if self.channels else 0

    @property
    def duration(self) -> float:
        return self.frame_count / self.sample_rate


def _decode_pcm(raw: bytes, sample_width: int) -> List[float]:
    if sample_width == 1:
        return [(value - 128) / 128.0 for value in raw]
    if sample_width == 2:
        count = len(raw) // 2
        return [value / 32768.0
                for value in struct.unpack("<{}h".format(count), raw)]
    if sample_width == 3:
        result = []
        for offset in range(0, len(raw), 3):
            value = raw[offset] | (raw[offset + 1] << 8) | (raw[offset + 2] << 16)
            if value & 0x800000:
                value -= 0x1000000
            result.append(value / 8388608.0)
        return result
    if sample_width == 4:
        count = len(raw) // 4
        return [value / 2147483648.0
                for value in struct.unpack("<{}i".format(count), raw)]
    raise ValueError("unsupported PCM sample width: {} bytes".format(sample_width))


def read_pcm_wav(path: Path) -> WavData:
    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE":
            raise ValueError("compressed WAV files are not supported")
        channel_count = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frame_count = source.getnframes()
        raw = source.readframes(frame_count)

    interleaved = _decode_pcm(raw, sample_width)
    channels = [interleaved[index::channel_count]
                for index in range(channel_count)]
    return WavData(sample_rate, channels, sample_width)


def _bounds(data: WavData, start: float, end: Optional[float]) -> Tuple[int, int]:
    stop_time = data.duration if end is None else end
    first = max(0, min(data.frame_count, int(round(start * data.sample_rate))))
    last = max(first, min(data.frame_count,
                          int(round(stop_time * data.sample_rate))))
    return first, last


def rms(data: WavData, start: float = 0.0,
        end: Optional[float] = None) -> float:
    first, last = _bounds(data, start, end)
    count = (last - first) * len(data.channels)
    if count == 0:
        return 0.0
    power = math.fsum(sample * sample
                      for channel in data.channels
                      for sample in channel[first:last])
    return math.sqrt(power / count)


def dbfs(value: float) -> float:
    return 20.0 * math.log10(max(value, 1.0e-300))


def peak_and_finite(data: WavData, clip_level: float) -> Tuple[float, bool, int]:
    peak = 0.0
    finite = True
    clipped = 0
    for channel in data.channels:
        for sample in channel:
            if not math.isfinite(sample):
                finite = False
                continue
            magnitude = abs(sample)
            peak = max(peak, magnitude)
            if magnitude >= clip_level:
                clipped += 1
    return peak, finite, clipped


def estimate_tuning(data: WavData, midi_note: float, start: float,
                    end: Optional[float], search_cents: float) -> Dict[str, float]:
    expected = 440.0 * math.pow(2.0, (midi_note - 69.0) / 12.0)
    first, last = _bounds(data, start, end)
    if last - first < 16:
        raise ValueError("the tuning window is too short")

    # Use the strongest channel to avoid phase cancellation in a stereo sum.
    channel = max(data.channels,
                  key=lambda values: math.fsum(
                      sample * sample for sample in values[first:last]))
    values = channel[first:last]
    mean = math.fsum(values) / len(values)
    denominator = max(1, len(values) - 1)
    values = [
        (sample - mean) *
        (0.5 - 0.5 * math.cos(2.0 * math.pi * index / denominator))
        for index, sample in enumerate(values)
    ]

    ratio = math.pow(2.0, search_cents / 1200.0)
    lower = expected / ratio
    upper = expected * ratio
    duration = len(values) / data.sample_rate
    point_count = max(
        5, min(2049, int(math.ceil((upper - lower) * duration * 8.0)) + 1))
    step = (upper - lower) / (point_count - 1)
    powers = []
    for point in range(point_count):
        frequency = lower + point * step
        coefficient = 2.0 * math.cos(
            2.0 * math.pi * frequency / data.sample_rate)
        previous = 0.0
        before_previous = 0.0
        for value in values:
            current = value + coefficient * previous - before_previous
            before_previous = previous
            previous = current
        power = (previous * previous + before_previous * before_previous -
                 coefficient * previous * before_previous)
        powers.append(max(power, 1.0e-300))

    best_point = max(range(point_count), key=powers.__getitem__)
    fractional_point = float(best_point)
    if 0 < best_point < point_count - 1:
        previous = math.log(powers[best_point - 1])
        centre = math.log(powers[best_point])
        following = math.log(powers[best_point + 1])
        curvature = previous - 2.0 * centre + following
        if abs(curvature) > 1.0e-15:
            offset = 0.5 * (previous - following) / curvature
            fractional_point += max(-1.0, min(1.0, offset))

    measured = lower + fractional_point * step
    cents = 1200.0 * math.log(measured / expected, 2.0)
    sorted_powers = sorted(powers)
    median_power = sorted_powers[len(sorted_powers) // 2]
    return {
        "expected_hz": expected,
        "measured_hz": measured,
        "cents": cents,
        "prominence_db": 10.0 * math.log10(
            powers[best_point] / median_power),
    }


def parse_window(specification: str) -> Tuple[str, float, float]:
    fields = specification.split(":")
    if len(fields) != 3 or not fields[0]:
        raise argparse.ArgumentTypeError(
            "windows use LABEL:START_SECONDS:END_SECONDS")
    try:
        start = float(fields[1])
        end = float(fields[2])
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if start < 0.0 or end <= start:
        raise argparse.ArgumentTypeError("window end must be greater than start")
    return fields[0], start, end


def analyse(path: Path, clip_level: float,
            windows: Iterable[Tuple[str, float, float]],
            midi_note: Optional[float], tuning_start: float,
            tuning_end: Optional[float], search_cents: float) -> Dict[str, object]:
    data = read_pcm_wav(path)
    peak, finite, clipped = peak_and_finite(data, clip_level)
    whole_rms = rms(data)
    result: Dict[str, object] = {
        "path": str(path),
        "sample_rate": data.sample_rate,
        "channels": len(data.channels),
        "sample_width_bits": 8 * data.sample_width,
        "frames": data.frame_count,
        "duration_seconds": data.duration,
        "finite": finite,
        "peak": peak,
        "clipped_samples": clipped,
        "rms": whole_rms,
        "rms_dbfs": dbfs(whole_rms),
    }
    window_results = {}
    for label, start, end in windows:
        value = rms(data, start, end)
        window_results[label] = {
            "start_seconds": start,
            "end_seconds": end,
            "rms": value,
            "rms_dbfs": dbfs(value),
        }
    result["windows"] = window_results
    if midi_note is not None:
        if tuning_end is None:
            tuning_end = min(data.duration, tuning_start + 1.0)
        result["tuning"] = estimate_tuning(
            data, midi_note, tuning_start, tuning_end, search_cents)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--clip-level", type=float, default=0.999)
    parser.add_argument("--window", action="append", type=parse_window,
                        default=[], metavar="LABEL:START:END")
    parser.add_argument("--midi", type=float)
    parser.add_argument("--tuning-start", type=float, default=0.10)
    parser.add_argument("--tuning-end", type=float)
    parser.add_argument("--search-cents", type=float, default=75.0)
    parser.add_argument("--max-abs-cents", type=float)
    parser.add_argument("--max-clipped-samples", type=int)
    arguments = parser.parse_args(argv)

    try:
        result = analyse(
            arguments.wav, arguments.clip_level, arguments.window,
            arguments.midi, arguments.tuning_start, arguments.tuning_end,
            arguments.search_cents)
    except (OSError, ValueError, wave.Error) as error:
        print("audio analysis failed: {}".format(error), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    failed = not bool(result["finite"])
    if (arguments.max_clipped_samples is not None and
            int(result["clipped_samples"]) > arguments.max_clipped_samples):
        failed = True
    if arguments.max_abs_cents is not None:
        tuning = result.get("tuning")
        if tuning is None:
            parser.error("--max-abs-cents requires --midi")
        if abs(float(tuning["cents"])) > arguments.max_abs_cents:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Check per-piano handles, isolation, and persistent wet state."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from audio_analysis import read_pcm_wav, rms


def run_csound(
    csound: Path, module: Path, csd: Path,
    definitions: List[str], output: Optional[Path],
    options: Optional[List[str]] = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        str(csound),
        "--opcode-lib={}".format(module),
        *(options or []),
        *["--omacro:{}".format(definition) for definition in definitions],
    ]
    if output is None:
        command.extend(["-n", "-d", "-m128"])
    else:
        command.extend(["-W", "-l", "-o", str(output)])
    command.append(str(csd))
    return subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=30, check=False)


def render(csound: Path, module: Path, csd: Path,
           output: Path, definitions: List[str],
           options: Optional[List[str]] = None) -> None:
    completed = run_csound(
        csound, module, csd, definitions, output, options)
    if completed.returncode != 0:
        raise RuntimeError(
            "Csound failed with status {}:\n{}".format(
                completed.returncode, completed.stdout))


def channel_rms(data, channel: int, start: float = 0.0,
                end: Optional[float] = None) -> float:
    stop = data.frame_count if end is None else min(
        data.frame_count, int(round(end * data.sample_rate)))
    first = max(0, min(stop, int(round(start * data.sample_rate))))
    values = data.channels[channel][first:stop]
    if not values:
        return 0.0
    return math.sqrt(math.fsum(value * value for value in values) / len(values))


def same_audio(left, right) -> bool:
    return (
        left.sample_rate == right.sample_rate and
        left.sample_width == right.sample_width and
        left.channels == right.channels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--isolation-csd", required=True, type=Path)
    parser.add_argument("--handoff-csd", required=True, type=Path)
    arguments = parser.parse_args()

    try:
        with tempfile.TemporaryDirectory(
                prefix="hlolli-wg-piano-handle-") as folder:
            temporary = Path(folder)
            piano_a_path = temporary / "piano-a.wav"
            piano_b_path = temporary / "piano-b.wav"
            piano_a_threads_path = temporary / "piano-a-threads.wav"
            continuous_path = temporary / "continuous.wav"
            continuous_threads_path = temporary / "continuous-threads.wav"
            split_path = temporary / "split.wav"
            split_threads_path = temporary / "split-threads.wav"
            boundary_path = temporary / "boundary.wav"
            boundary_threads_path = temporary / "boundary-threads.wav"
            early_boundary_path = temporary / "early-boundary.wav"
            early_boundary_threads_path = temporary / "early-boundary-threads.wav"

            render(arguments.csound, arguments.module, arguments.isolation_csd,
                   piano_a_path, [])
            render(arguments.csound, arguments.module, arguments.isolation_csd,
                   piano_b_path,
                   ["TEST_A_VELOCITY=0", "TEST_B_VELOCITY=0.72"])
            render(arguments.csound, arguments.module, arguments.isolation_csd,
                   piano_a_threads_path, [], ["--num-threads=4"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   continuous_path, [], ["--sample-accurate"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   continuous_threads_path, [],
                   ["--sample-accurate", "--num-threads=4"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   split_path, ["TEST_SPLIT_OUTPUT=1"],
                   ["--sample-accurate"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   split_threads_path, ["TEST_SPLIT_OUTPUT=1"],
                   ["--sample-accurate", "--num-threads=4"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   boundary_path,
                   ["TEST_SPLIT_OUTPUT=1", "TEST_SPLIT_TIME=1.5"],
                   ["--sample-accurate"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   boundary_threads_path,
                   ["TEST_SPLIT_OUTPUT=1", "TEST_SPLIT_TIME=1.5"],
                   ["--sample-accurate", "--num-threads=4"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   early_boundary_path,
                   ["TEST_SPLIT_OUTPUT=1",
                    "TEST_SPLIT_TIME=0.0106666666666667"],
                   ["--sample-accurate"])
            render(arguments.csound, arguments.module, arguments.handoff_csd,
                   early_boundary_threads_path,
                   ["TEST_SPLIT_OUTPUT=1",
                    "TEST_SPLIT_TIME=0.0106666666666667"],
                   ["--sample-accurate", "--num-threads=4"])

            piano_a = read_pcm_wav(piano_a_path)
            piano_b = read_pcm_wav(piano_b_path)
            piano_a_threads = read_pcm_wav(piano_a_threads_path)
            continuous = read_pcm_wav(continuous_path)
            continuous_threads = read_pcm_wav(continuous_threads_path)
            split = read_pcm_wav(split_path)
            split_threads = read_pcm_wav(split_threads_path)
            boundary = read_pcm_wav(boundary_path)
            boundary_threads = read_pcm_wav(boundary_threads_path)
            early_boundary = read_pcm_wav(early_boundary_path)
            early_boundary_threads = read_pcm_wav(
                early_boundary_threads_path)
            a_active = channel_rms(piano_a, 0, 0.02, 2.0)
            a_leak = max(abs(value) for value in piano_a.channels[1])
            b_active = channel_rms(piano_b, 1, 0.02, 2.0)
            b_leak = max(abs(value) for value in piano_b.channels[0])
            isolation_lsb = 1.0 / float(
                1 << (8 * piano_a.sample_width - 1))
            handoff_tail = rms(split, 1.55, 2.20)
            same_handoff = same_audio(continuous, split)
            same_threaded = same_audio(piano_a, piano_a_threads)
            same_threaded_handoff = same_audio(
                continuous_threads, split_threads)
            same_boundary_handoff = same_audio(continuous, boundary)
            same_threaded_boundary = same_audio(
                continuous_threads, boundary_threads)
            same_early_boundary = same_audio(continuous, early_boundary)
            same_threaded_early_boundary = same_audio(
                continuous_threads, early_boundary_threads)
            same_continuous_threads = same_audio(
                continuous, continuous_threads)

            duplicate = run_csound(
                arguments.csound, arguments.module, arguments.handoff_csd,
                ["TEST_DUPLICATE_OUTPUT=1"], None)
            bad_handle = run_csound(
                arguments.csound, arguments.module, arguments.handoff_csd,
                ["TEST_BAD_HANDLE=1"], None)
            local_create = run_csound(
                arguments.csound, arguments.module, arguments.handoff_csd,
                ["TEST_LOCAL_CREATE=1"], None)
            local_note = run_csound(
                arguments.csound, arguments.module, arguments.handoff_csd,
                ["TEST_LOCAL_NOTE=1"], None)
            local_output = run_csound(
                arguments.csound, arguments.module, arguments.handoff_csd,
                ["TEST_LOCAL_OUTPUT=1"], None)
            local_bus = run_csound(
                arguments.csound, arguments.module, arguments.handoff_csd,
                ["TEST_LOCAL_BUS=1"], None)

            failures = []
            if a_active <= 1.0e-8:
                failures.append("piano A produced no wet output")
            if b_active <= 1.0e-8:
                failures.append("piano B produced no wet output")
            if a_leak > isolation_lsb:
                failures.append("piano A leaked into piano B")
            if b_leak > isolation_lsb:
                failures.append("piano B leaked into piano A")
            if handoff_tail <= 1.0e-9:
                failures.append("the wet tail stopped at output handoff")
            if not same_handoff:
                failures.append("output handoff changed the persistent state")
            if not same_threaded:
                failures.append("four worker threads changed the piano output")
            if not same_continuous_threads:
                failures.append(
                    "worker threads changed the continuous handle output")
            if not same_threaded_handoff:
                failures.append(
                    "four worker threads changed the sample-accurate handoff")
            if not same_boundary_handoff:
                failures.append("a block-boundary handoff changed state")
            if not same_threaded_boundary:
                failures.append(
                    "worker threads changed a block-boundary handoff")
            if not same_early_boundary:
                failures.append("an early block-boundary handoff changed state")
            if not same_threaded_early_boundary:
                failures.append(
                    "worker threads changed an early boundary handoff")
            if (duplicate.returncode == 0 or
                    "already has an output opcode" not in duplicate.stdout):
                failures.append("a duplicate output owner was not rejected")
            if (bad_handle.returncode == 0 or
                    "unknown piano handle" not in bad_handle.stdout):
                failures.append("an unknown piano handle was not rejected")
            for label, completed in (
                    ("handle creation", local_create),
                    ("handled note", local_note),
                    ("handle output", local_output),
                    ("explicit-bus output", local_bus)):
                if (completed.returncode == 0 or
                        "engine ksmps" not in completed.stdout):
                    failures.append(
                        "local-ksmps {} was not rejected".format(label))

            print(
                "piano handles: A={:.6g}, A_leak={:.6g}, B={:.6g}, "
                "B_leak={:.6g}, handoff_tail={:.6g}, exact_handoff={}, "
                "exact_threads={}, exact_threaded_handoff={}, "
                "exact_boundary={}, exact_threaded_boundary={}, "
                "exact_early_boundary={}, "
                "exact_threaded_early_boundary={}, "
                "exact_continuous_threads={}".format(
                    a_active, a_leak, b_active, b_leak,
                    handoff_tail, same_handoff, same_threaded,
                    same_threaded_handoff, same_boundary_handoff,
                    same_threaded_boundary, same_early_boundary,
                    same_threaded_early_boundary,
                    same_continuous_threads))
            for failure in failures:
                print("failure: {}".format(failure), file=sys.stderr)
            return 1 if failures else 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
        print("piano handle test failed: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

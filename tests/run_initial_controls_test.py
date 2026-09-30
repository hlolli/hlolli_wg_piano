#!/usr/bin/env python3
"""Check that initial k-rate values choose the note's sound and held key."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from audio_analysis import read_pcm_wav, rms


def render(csound: Path, module: Path, csd: Path, output: Path,
           ksmps: int, assignment: bool) -> None:
    command = [
        str(csound), "--opcode-lib={}".format(module), "--sample-accurate",
        "--omacro:TEST_KSMPS={}".format(ksmps),
        *(["--omacro:TEST_K_ASSIGNMENT=1"] if assignment else []),
        "-W", "-l", "-o", str(output), str(csd),
    ]
    completed = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=30, check=False)
    if completed.returncode:
        raise RuntimeError("Csound render failed:\n{}".format(completed.stdout))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()

    try:
        with tempfile.TemporaryDirectory(prefix="hlolli-wg-piano-controls-") as folder:
            temporary = Path(folder)
            for ksmps in (1, 32, 128):
                initial_path = temporary / "initial.wav"
                assigned_path = temporary / "assigned.wav"
                render(arguments.csound, arguments.module, arguments.csd,
                       initial_path, ksmps, False)
                render(arguments.csound, arguments.module, arguments.csd,
                       assigned_path, ksmps, True)
                initial = read_pcm_wav(initial_path)
                assigned = read_pcm_wav(assigned_path)
                if rms(initial) <= 1.0e-5:
                    raise AssertionError("reference render is silent")
                if (initial.sample_rate != assigned.sample_rate or
                        initial.channels != assigned.channels):
                    raise AssertionError(
                        "At ksmps {}: k-rate assignment changes the "
                        "initial note sound or shared key state".format(
                            ksmps))
                print("At ksmps {}: identical audio".format(ksmps))
    except (AssertionError, OSError, RuntimeError, ValueError,
            subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

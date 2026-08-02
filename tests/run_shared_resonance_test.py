#!/usr/bin/env python3
"""Render and check persistent shared-resonance state."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from audio_analysis import analyse, read_pcm_wav, rms


def render(csound: Path, module: Path, csd: Path, output: Path,
           definitions: List[str],
           options: Optional[List[str]] = None) -> None:
    command = [
        str(csound),
        "--opcode-lib={}".format(module),
        *(options or []),
        *["--omacro:{}".format(definition) for definition in definitions],
        "-W", "-l", "-o", str(output), str(csd),
    ]
    completed = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "Csound failed with status {}:\n{}".format(
                completed.returncode, completed.stdout))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csound", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--csd", required=True, type=Path)
    arguments = parser.parse_args()

    try:
        with tempfile.TemporaryDirectory(prefix="hlolli-wg-piano-") as folder:
            temporary = Path(folder)
            short_path = temporary / "short-source.wav"
            kept_path = temporary / "kept-source.wav"
            disabled_path = temporary / "body-disabled.wav"
            pedal_closed_path = temporary / "pedal-closed.wav"
            handoff_continuous_path = temporary / "handoff-continuous.wav"
            handoff_split_path = temporary / "handoff-split.wav"

            render(arguments.csound, arguments.module, arguments.csd,
                   short_path, ["TEST_KEEP_SOURCE=0"])
            render(arguments.csound, arguments.module, arguments.csd,
                   kept_path, ["TEST_KEEP_SOURCE=1"])
            render(arguments.csound, arguments.module, arguments.csd,
                   disabled_path, ["TEST_KEEP_SOURCE=0", "TEST_BODY=0"])
            render(arguments.csound, arguments.module, arguments.csd,
                   pedal_closed_path,
                   ["TEST_KEEP_SOURCE=0", "TEST_PEDAL=0"])
            render(arguments.csound, arguments.module, arguments.csd,
                   handoff_continuous_path,
                   ["TEST_KEEP_SOURCE=0", "TEST_CONTROL_MOTION=1"],
                   ["--sample-accurate"])
            render(arguments.csound, arguments.module, arguments.csd,
                   handoff_split_path,
                   ["TEST_KEEP_SOURCE=0", "TEST_SPLIT_OUTPUT=1",
                    "TEST_CONTROL_MOTION=1"],
                   ["--sample-accurate"])

            metrics = analyse(
                short_path, 0.999,
                [("early_tail", 0.10, 0.30),
                 ("late_tail", 0.80, 1.15),
                 ("second_tail", 1.60, 2.20)],
                None, 0.0, None, 75.0)
            short_data = read_pcm_wav(short_path)
            kept_data = read_pcm_wav(kept_path)
            disabled_data = read_pcm_wav(disabled_path)
            pedal_closed_data = read_pcm_wav(pedal_closed_path)
            handoff_continuous_data = read_pcm_wav(handoff_continuous_path)
            handoff_split_data = read_pcm_wav(handoff_split_path)
            early = rms(short_data, 0.10, 0.30)
            late = rms(short_data, 0.80, 1.15)
            open_pedal_tail = rms(short_data, 0.50, 1.15)
            closed_pedal_tail = rms(pedal_closed_data, 0.50, 1.15)
            disabled_peak = max(
                (abs(sample) for channel in disabled_data.channels
                 for sample in channel), default=0.0)
            disabled_lsb = 1.0 / float(
                1 << (8 * disabled_data.sample_width - 1))
            exact_handoff = (
                handoff_continuous_data.sample_rate ==
                handoff_split_data.sample_rate and
                handoff_continuous_data.sample_width ==
                handoff_split_data.sample_width and
                handoff_continuous_data.channels ==
                handoff_split_data.channels)

            failures = []
            if not bool(metrics["finite"]):
                failures.append("wet output contains a nonfinite sample")
            if int(metrics["clipped_samples"]) != 0:
                failures.append("wet output clips")
            if float(metrics["peak"]) <= 1.0e-7:
                failures.append("enabled body produced no wet output")
            if early <= 1.0e-9:
                failures.append("the first excitation produced no early tail")
            if late <= max(1.0e-10, early * 1.0e-5):
                failures.append("shared tail stopped too soon")
            if late > early * 2.0:
                failures.append("shared tail grew by more than 6 dB")
            if (short_data.sample_rate != kept_data.sample_rate or
                    short_data.channels != kept_data.channels):
                failures.append("source lifetime changed persistent body output")
            if disabled_peak > disabled_lsb:
                failures.append("kBody=0 did not mute the wet path")
            if open_pedal_tail <= 1.10 * closed_pedal_tail:
                failures.append("opening the pedal did not lengthen the tail")
            if not exact_handoff:
                failures.append("explicit-bus output handoff changed state")

            print("shared resonance: peak={:.6g}, early={:.6g}, "
                  "late={:.6g}, pedal_open={:.6g}, pedal_closed={:.6g}, "
                  "disabled_peak={:.6g}, exact_handoff={}".format(
                      float(metrics["peak"]), early, late,
                      open_pedal_tail, closed_pedal_tail, disabled_peak,
                      exact_handoff))
            for failure in failures:
                print("failure: {}".format(failure), file=sys.stderr)
            return 1 if failures else 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
        print("shared resonance test failed: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

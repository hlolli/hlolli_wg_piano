#!/usr/bin/python3
"""Build and run the analyzer's checked piano renderer adapter."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave


FROZEN_CONFIG = None
ROOT = Path(__file__).resolve().parents[1]
FIT_MANIFEST = ROOT / "fit" / "piano_fit_v1.json"
CSD = ROOT / "tests" / "measure_note.csd"


class AdapterError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def regular(path: Path, name: str) -> Path:
    path = path.absolute()
    if not path.is_file() or path.is_symlink():
        raise AdapterError(f"{name} must be a regular file: {path}")
    return path


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise AdapterError(f"JSON root must be an object: {path}")
    return value


def copy_at_rate(source: Path, output: Path, target_rate: int = 48000) -> None:
    with wave.open(str(source), "rb") as stream:
        rate = stream.getframerate()
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        frames = stream.getnframes()
        audio = stream.readframes(frames)
    if width != 2 or channels not in (1, 2) or frames < 1:
        raise AdapterError(f"reference must be mono or stereo PCM16: {source}")
    if len(audio) != frames * channels * width:
        raise AdapterError(f"cannot read reference: {source}")
    if rate != target_rate:
        audio = resample_pcm16(audio, channels, rate, target_rate)
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(width)
        stream.setframerate(target_rate)
        stream.writeframes(audio)


def resample_pcm16(audio: bytes, channels: int,
                   source_rate: int, target_rate: int) -> bytes:
    if channels < 1 or source_rate < 1 or target_rate < 1:
        raise AdapterError("invalid resampler arguments")
    samples = array("h")
    samples.frombytes(audio)
    if sys.byteorder != "little":
        samples.byteswap()
    frames = len(samples) // channels
    if frames < 1 or frames * channels != len(samples):
        raise AdapterError("invalid PCM16 frame layout")
    if source_rate == target_rate:
        return audio
    output_frames = max(1, round(frames * target_rate / source_rate))
    output = array("h")
    # A Blackman-windowed sinc preserves the fit bands and removes frequencies
    # that would fold into them when reducing the sample rate. Cache each
    # fractional phase, since common audio rates reuse a small set of phases.
    cutoff = 0.95 * min(1.0, target_rate / source_rate)
    radius = 16.0 / cutoff
    phases = {}
    for frame in range(output_frames):
        numerator = frame * source_rate
        centre, phase = divmod(numerator, target_rate)
        if phase not in phases:
            fraction = phase / target_rate
            weights = []
            for offset in range(math.ceil(fraction - radius),
                                math.floor(fraction + radius) + 1):
                distance = offset - fraction
                argument = math.pi * cutoff * distance
                sinc = 1.0 if argument == 0.0 else math.sin(argument) / argument
                window = (0.42 + 0.5 * math.cos(math.pi * distance / radius) +
                          0.08 * math.cos(2.0 * math.pi * distance / radius))
                weights.append((offset, sinc * window))
            total = math.fsum(weight for _, weight in weights)
            phases[phase] = [(offset, weight / total) for offset, weight in weights]
        weights = phases[phase]
        if centre + weights[0][0] < 0 or centre + weights[-1][0] >= frames:
            positions = [(max(0, min(frames - 1, centre + offset)) * channels, weight)
                         for offset, weight in weights]
        else:
            positions = [((centre + offset) * channels, weight)
                         for offset, weight in weights]
        for channel in range(channels):
            value = math.fsum(samples[position + channel] * weight
                              for position, weight in positions)
            output.append(max(-32768, min(32767, round(value))))
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


def parameter_rows() -> list[dict]:
    rows = []
    for row in load_json(FIT_MANIFEST)["parameters"]:
        rows.append({
            "id": row["id"], "unit": row["unit"],
            "minimum": row["minimum"], "maximum": row["maximum"],
            "baseline": row["baseline"], "levels": [],
        })
    return sorted(rows, key=lambda row: row["id"])


def stem(resource_id: str, side: str, input_id: str | None,
         output: str | None, channels: int) -> dict:
    return {
        "id": resource_id, "side": side, "role": "final",
        "input_id": input_id, "output": output, "start_sample": 0,
        "gain_db": 0, "rate_hz": 48000, "channels": channels,
    }


def build_experiment(references: dict[str, Path], sample_count: int) -> dict:
    case_rows = (
        ("high-check", "check", "reference_high_check"),
        ("high-fit", "fit", "reference_high_fit"),
        ("low-check", "check", "reference_low_check"),
        ("low-fit", "fit", "reference_low_fit"),
        ("mid-check", "check", "reference_mid_check"),
        ("mid-fit", "fit", "reference_mid_fit"),
    )
    cases = []
    for case_id, split, binding in case_rows:
        with wave.open(str(references[binding]), "rb") as stream:
            channels = stream.getnchannels()
        cases.append({
            "id": case_id, "split": split, "weight": 1,
            "stems": [
                stem("model.final", "model", None, "model.wav", 2),
                stem("reference.final", "reference", binding, None, channels),
            ],
            "probes": [], "links": [],
        })
    bands = ((2, "120-250"), (6, "2-4k"), (7, "4-8k"))
    responses = [{
        "id": f"final.band.{name}", "role": "final",
        "feature": "band_level_dbfs", "index": index,
    } for index, name in bands]
    return {
        "schema": "hwa-experiment", "schema_version": 1,
        "method_version": "stage8-1", "clock_rate_hz": 48000,
        "inputs": [{"id": name, "sha256": sha256(path)}
                   for name, path in sorted(references.items())],
        "parameters": parameter_rows(),
        "plan": {"kind": "random", "seed": 22071988,
                 "sample_count": sample_count, "replicates": 1},
        "cases": cases,
        "responses": responses,
    }


def build_renderer(csound: Path, module: Path, library_path: Path | None,
                   output: Path) -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    marker = "FROZEN_CONFIG = None"
    lines = source.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines)
               if line.rstrip("\r\n") == marker]
    if len(matches) != 1:
        raise AdapterError("renderer source marker changed")
    files = {"csound": csound, "module": module, "csd": regular(CSD, "CSD")}
    config = {
        "adapter_id": "hlolli-wg-piano-v1",
        "files": {name: {"path": str(path), "sha256": sha256(path)}
                  for name, path in files.items()},
        "library_path": str(library_path) if library_path is not None else None,
        "parameters": load_json(FIT_MANIFEST)["parameters"],
        "cases": {
            "high-check": 91, "high-fit": 84,
            "low-check": 43, "low-fit": 36,
            "mid-check": 67, "mid-fit": 60,
        },
    }
    ending = "\n" if lines[matches[0]].endswith("\n") else ""
    lines[matches[0]] = "FROZEN_CONFIG = " + repr(config) + ending
    output.write_text("".join(lines), encoding="utf-8")
    output.chmod(0o755)


def build(arguments: argparse.Namespace) -> None:
    output = arguments.output_dir.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise AdapterError("output directory must be new with an existing parent")
    csound = regular(arguments.csound, "Csound")
    module = regular(arguments.module, "piano module")
    library_path = None
    if arguments.library_path is not None:
        library_path = arguments.library_path.absolute()
        if not library_path.is_dir():
            raise AdapterError("library path must be a directory")
    names = (
        "low_fit", "low_check", "mid_fit", "mid_check", "high_fit", "high_check"
    )
    source_references = {
        "reference_" + name: regular(getattr(arguments, "reference_" + name),
                                     name.replace("_", " ") + " reference")
        for name in names
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-",
                                      dir=output.parent))
    try:
        references = {}
        for name, source in source_references.items():
            target = temporary / f"{name}.wav"
            copy_at_rate(source, target)
            references[name] = target
        build_renderer(csound, module, library_path, temporary / "renderer")
        (temporary / "experiment.json").write_text(
            json.dumps(build_experiment(references, arguments.sample_count),
                       indent=2, sort_keys=True) + "\n",
            encoding="utf-8"
        )
        shutil.copyfile(FIT_MANIFEST, temporary / "fit.json")
        (temporary / "bindings.json").write_text(
            json.dumps({
                "schema": "hwa-fit-bindings", "schema_version": 1,
                "bindings": [{"id": name,
                              "path": str(output / path.name),
                              "sha256": sha256(path)}
                             for name, path in sorted(references.items())],
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.rename(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def checked_file(row: dict, name: str) -> Path:
    path = regular(Path(row["path"]), name)
    if sha256(path) != row["sha256"]:
        raise AdapterError(f"{name} hash changed")
    return path


def render_job(request_path: Path, output_dir: Path) -> None:
    if FROZEN_CONFIG is None:
        raise AdapterError("use a generated renderer")
    request = load_json(regular(request_path, "render request"))
    output_dir = output_dir.absolute()
    if request.get("schema") != "hwa-render-job" or request.get("schema_version") != 1:
        raise AdapterError("unsupported render request")
    note = FROZEN_CONFIG["cases"].get(request.get("case_id"))
    if note is None:
        raise AdapterError("unknown piano fit case")
    outputs = request.get("outputs")
    if type(outputs) is not list or len(outputs) != 1 or outputs[0].get("id") != "model.final":
        raise AdapterError("piano renderer needs one model.final output")
    output = Path(outputs[0]["path"]).absolute()
    if output.parent != output_dir or output.exists() or output.is_symlink():
        raise AdapterError("invalid renderer output path")
    values = {row["id"]: float(row["value"])
              for row in request.get("parameters", [])}
    expected = {row["id"] for row in FROZEN_CONFIG["parameters"]}
    if set(values) != expected:
        raise AdapterError("render parameter set changed")
    for row in FROZEN_CONFIG["parameters"]:
        value = values[row["id"]]
        if not math.isfinite(value) or not row["minimum"] <= value <= row["maximum"]:
            raise AdapterError(f"render parameter is out of range: {row['id']}")
    csound = checked_file(FROZEN_CONFIG["files"]["csound"], "Csound")
    module = checked_file(FROZEN_CONFIG["files"]["module"], "module")
    csd = checked_file(FROZEN_CONFIG["files"]["csd"], "CSD")
    command = [
        str(csound), f"--opcode-lib={module}", "--sample-accurate",
        "--num-threads=1", "-W", "-s", "--nopeaks", "-o", str(output),
        f"--omacro:TEST_NOTE={note}",
        f"--omacro:TEST_HARDNESS={values['hammer_hardness']}",
        f"--omacro:TEST_POSITION={values['hammer_position']}",
        f"--omacro:TEST_BODY={values['body_control']}",
        "--omacro:TEST_KEY_SECONDS=0.35", "--omacro:TEST_TAIL_SECONDS=3.0",
        str(csd),
    ]
    environment = {"LC_ALL": "C", "LANG": "C", "TZ": "UTC"}
    library_path = FROZEN_CONFIG.get("library_path")
    if library_path is not None:
        variable = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
        environment[variable] = library_path
    completed = subprocess.run(command, check=False, env=environment)
    if completed.returncode != 0 or not output.is_file() or output.is_symlink():
        raise AdapterError("Csound piano fit render failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hwa-experiment-job", type=Path)
    parser.add_argument("--output-dir", type=Path)
    commands = parser.add_subparsers(dest="command")
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--csound", required=True, type=Path)
    build_parser.add_argument("--module", required=True, type=Path)
    build_parser.add_argument("--library-path", type=Path)
    for name in ("low-fit", "low-check", "mid-fit", "mid-check",
                 "high-fit", "high-check"):
        build_parser.add_argument("--reference-" + name, required=True, type=Path)
    build_parser.add_argument("--sample-count", type=int, default=24)
    build_parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        arguments = parse_args()
        if arguments.hwa_experiment_job is not None:
            if arguments.output_dir is None:
                raise AdapterError("render job needs --output-dir")
            render_job(arguments.hwa_experiment_job, arguments.output_dir)
        elif arguments.command == "build":
            if arguments.sample_count < 1 or arguments.sample_count > 256:
                raise AdapterError("sample count must be 1..256")
            build(arguments)
        else:
            raise AdapterError("choose build or render job")
    except (AdapterError, OSError, ValueError, json.JSONDecodeError, wave.Error) as error:
        print(f"piano_fit_adapter.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

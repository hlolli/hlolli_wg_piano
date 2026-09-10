#!/usr/bin/python3
"""Build and run the analyzer's checked piano renderer adapter."""

from __future__ import annotations

import argparse
from array import array
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
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
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AdapterError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise AdapterError(f"invalid JSON number: {value}")

    value = json.loads(path.read_text(encoding="utf-8"),
                       object_pairs_hook=unique, parse_constant=invalid)
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


def parameter_rows(manifest=None) -> list[dict]:
    rows = []
    for row in (manifest or load_json(FIT_MANIFEST))["parameters"]:
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


def build_experiment(references: dict[str, Path], sample_count: int,
                     manifest=None) -> dict:
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
        "parameters": parameter_rows(manifest),
        "plan": {"kind": "random", "seed": 22071988,
                 "sample_count": sample_count, "replicates": 1},
        "cases": cases,
        "responses": responses,
    }


def build_renderer(csound: Path, module: Path, library_path: Path | None,
                   output: Path, fixed=None) -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    marker = "FROZEN_CONFIG = None"
    lines = source.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines)
               if line.rstrip("\r\n") == marker]
    if len(matches) != 1:
        raise AdapterError("renderer source marker changed")
    files = {"csound": csound, "csd": regular(CSD, "CSD")}
    if fixed is None:
        files["module"] = module
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
    if fixed is not None:
        config.update(fixed)
    ending = "\n" if lines[matches[0]].endswith("\n") else ""
    lines[matches[0]] = "FROZEN_CONFIG = " + repr(config) + ending
    output.write_text("".join(lines), encoding="utf-8")
    output.chmod(0o755)


def build(arguments: argparse.Namespace) -> None:
    output = arguments.output_dir.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise AdapterError("output directory must be new with an existing parent")
    csound = regular(arguments.csound, "Csound")
    profile_mode = getattr(arguments, "profile", None) is not None
    if profile_mode and arguments.module is not None:
        raise AdapterError("--profile and --module are separate fit modes")
    if not profile_mode and arguments.module is None:
        raise AdapterError("choose --module or --profile")
    if not profile_mode and any(getattr(arguments, name, None) is not None
                                for name in ("fit_manifest", "cc", "include_dir")):
        raise AdapterError("profile build options require --profile")
    module = None if profile_mode else regular(arguments.module, "piano module")
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
        fixed = None
        manifest = load_json(FIT_MANIFEST)
        if profile_mode:
            fixed, manifest = prepare_profile_build(arguments, temporary, output)
        build_renderer(csound, module, library_path, temporary / "renderer", fixed)
        (temporary / "experiment.json").write_text(
            json.dumps(build_experiment(references, arguments.sample_count, manifest),
                       indent=2, sort_keys=True) + "\n",
            encoding="utf-8"
        )
        if not profile_mode:
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


def profile_generator(path: Path):
    module = types.ModuleType("piano_profile_generator")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def profile_target(profile: dict, path: list):
    allowed = {"default_key", "keys", "strings", "felt_modes", "note_body_lines",
               "body_modes", "body_coupling", "mechanics", "fdn_lines"}
    if (type(path) is not list or len(path) < 2 or
            type(path[0]) is not str or path[0] not in allowed):
        raise AdapterError("profile path must name a saved acoustic field")
    parent = profile
    for key in path[:-1]:
        if type(parent) is dict and type(key) is str and key in parent:
            parent = parent[key]
        elif type(parent) is list and type(key) is int and 0 <= key < len(parent):
            parent = parent[key]
        else:
            raise AdapterError(f"profile path does not exist: {path}")
    key = path[-1]
    if not ((type(parent) is dict and type(key) is str and key in parent) or
            (type(parent) is list and type(key) is int and 0 <= key < len(parent))):
        raise AdapterError(f"profile path does not exist: {path}")
    if type(parent[key]) not in (int, float) or not math.isfinite(parent[key]):
        raise AdapterError(f"profile path is not a finite number: {path}")
    return parent, key


def profile_fit_manifest(profile: dict, custom: Path | None) -> dict:
    if custom is not None:
        manifest = load_json(regular(custom, "fit manifest"))
    else:
        manifest = load_json(FIT_MANIFEST)
        paths = [["default_key", "radiation_scale"]]
        paths.extend(["keys", key, "radiation_scale"]
                     for key, row in sorted(profile["keys"].items())
                     if "radiation_scale" in row)
        baseline = profile["default_key"]["radiation_scale"]
        manifest["adapter_id"] = "hlolli-wg-piano-profile-v1"
        manifest["parameters"] = [{
            "id": "radiation_scale", "unit": "ratio", "minimum": 0.25,
            "maximum": 2.0, "baseline": baseline, "profile_paths": paths,
        }]
    if (manifest.get("schema") != "hwa-instrument-fit" or
            manifest.get("schema_version") != 1 or
            manifest.get("adapter_id") != "hlolli-wg-piano-profile-v1"):
        raise AdapterError("profile fitting requires hlolli-wg-piano-profile-v1")
    rows = manifest.get("parameters")
    if type(rows) is not list or not 1 <= len(rows) <= 64:
        raise AdapterError("profile fitting needs 1..64 parameters")
    seen, targets = set(), set()
    for row in rows:
        if type(row) is not dict:
            raise AdapterError("invalid profile fit parameter")
        name = row.get("id")
        unit = row.get("unit")
        if (type(name) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or
                name in seen or type(unit) is not str or
                not re.fullmatch(r"[A-Za-z0-9_.-]+", unit)):
            raise AdapterError("invalid or duplicate profile parameter id/unit")
        seen.add(name)
        numbers = [row.get(key) for key in ("minimum", "maximum", "baseline")]
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in numbers):
            raise AdapterError("profile parameter bounds must be finite numbers")
        minimum, maximum, baseline = numbers
        if not minimum <= baseline <= maximum or minimum >= maximum:
            raise AdapterError("profile parameter baseline/range is invalid")
        paths = row.get("profile_paths")
        if type(paths) is not list or not paths:
            raise AdapterError("profile parameters need saved profile paths")
        for path in paths:
            parent, key = profile_target(profile, path)
            encoded = json.dumps(path)
            if encoded in targets:
                raise AdapterError("profile fit paths overlap")
            targets.add(encoded)
            if parent[key] != baseline:
                raise AdapterError("profile path differs from parameter baseline")
    return manifest


def apply_profile_parameters(profile: dict, parameters: list, values: dict) -> dict:
    candidate = copy.deepcopy(profile)
    for row in parameters:
        for path in row["profile_paths"]:
            parent, key = profile_target(candidate, path)
            parent[key] = values[row["id"]]
    return candidate


def prepare_profile_build(arguments, temporary: Path, output: Path):
    if sys.platform not in ("darwin", "linux"):
        raise AdapterError("profile compilation supports macOS and Linux")
    if arguments.cc is None or arguments.include_dir is None:
        raise AdapterError("--profile requires --cc and --include-dir")
    compiler = regular(arguments.cc, "C compiler")
    include = arguments.include_dir.absolute()
    if not include.is_dir() or include.is_symlink():
        raise AdapterError("include-dir must be a regular directory")
    for name in ("csdl.h", "version.h", "float-version.h"):
        regular(include / name, "Csound header")
    source = regular(arguments.profile, "source profile")
    generator_path = regular(ROOT / "tools" / "generate_profiles.py", "generator")
    generator = profile_generator(generator_path)
    generator.validate_profile(generator.load_json(source), source)
    profile = load_json(source)
    if profile["midi_min"] > 36 or profile["midi_min"] + profile["key_count"] <= 91:
        raise AdapterError("profile must cover all six fit notes (MIDI 36..91)")
    manifest = profile_fit_manifest(profile, arguments.fit_manifest)
    inputs = temporary / "profile-inputs"
    inputs.mkdir()
    headers = inputs / "include"
    headers.mkdir()
    for path in sorted(include.glob("*.h")):
        shutil.copyfile(regular(path, "Csound header"), headers / path.name)
    for name, path in {
        "generate_profiles.py": generator_path,
        "hlolli_wg_piano.c": regular(ROOT / "hlolli_wg_piano.c", "piano source"),
    }.items():
        shutil.copyfile(path, inputs / name)
    shutil.copyfile(source, temporary / "source-profile.json")
    (temporary / "fit.json").write_text(json.dumps(
        manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    frozen = {
        path.relative_to(temporary).as_posix(): {
            "path": str(output / path.relative_to(temporary)), "sha256": sha256(path),
        }
        for path in sorted(inputs.rglob("*")) if path.is_file()
    }
    for name in ("source-profile.json", "fit.json"):
        frozen[name] = {"path": str(output / name), "sha256": sha256(temporary / name)}
    return {
        "mode": "profile", "adapter_id": manifest["adapter_id"],
        "parameters": manifest["parameters"], "profile_inputs": frozen,
        "compiler": {"path": str(compiler), "sha256": sha256(compiler)},
        "platform": sys.platform,
    }, manifest


def checked_profile_inputs():
    if FROZEN_CONFIG is None or FROZEN_CONFIG.get("mode") != "profile":
        raise AdapterError("profile validation requires a profile-fit renderer")
    if sys.platform != FROZEN_CONFIG["platform"]:
        raise AdapterError("profile renderer platform changed")
    paths = {name: checked_file(row, name)
             for name, row in FROZEN_CONFIG["profile_inputs"].items()}
    generator = profile_generator(paths["profile-inputs/generate_profiles.py"])
    return paths, generator


def validate_candidate(path: Path) -> None:
    paths, generator = checked_profile_inputs()
    candidate = load_json(regular(path, "candidate profile"))
    source = load_json(paths["source-profile.json"])
    values = {}
    for row in FROZEN_CONFIG["parameters"]:
        values[row["id"]] = profile_target(candidate, row["profile_paths"][0])[0][
            row["profile_paths"][0][-1]]
        value = values[row["id"]]
        if not row["minimum"] <= value <= row["maximum"]:
            raise AdapterError("candidate profile parameter is out of range")
    expected = apply_profile_parameters(source, FROZEN_CONFIG["parameters"], values)
    if candidate != expected:
        raise AdapterError("candidate changed fields outside the fit parameters")
    generator.validate_profile(generator.load_json(path), path)


def compile_candidate(values: dict, directory: Path) -> Path:
    paths, generator = checked_profile_inputs()
    compiler = checked_file(FROZEN_CONFIG["compiler"], "C compiler")
    profile = apply_profile_parameters(load_json(paths["source-profile.json"]),
                                       FROZEN_CONFIG["parameters"], values)
    candidate = directory / "candidate.json"
    candidate.write_text(json.dumps(profile, allow_nan=False), encoding="utf-8")
    normalized = generator.validate_profile(generator.load_json(candidate), candidate)
    block = generator.generate_block([normalized], normalized["id"])
    source = directory / "piano.c"
    source.write_text(generator.replace_generated_block(
        paths["profile-inputs/hlolli_wg_piano.c"].read_text(encoding="utf-8"), block),
        encoding="utf-8")
    headers = directory / "include"
    headers.mkdir()
    for name, path in paths.items():
        if name.startswith("profile-inputs/include/"):
            shutil.copyfile(path, headers / path.name)
    module = directory / ("piano.dylib" if sys.platform == "darwin" else "piano.so")
    command = [
        str(compiler), "-std=c11", "-O2", "-fPIC", "-fvisibility=hidden",
        "-DBUILD_PLUGINS", "-dynamiclib" if sys.platform == "darwin" else "-shared",
        "-I", str(headers), str(source), "-o", str(module), "-lm",
    ]
    completed = subprocess.run(command, check=False, timeout=120,
                               env={"PATH": "/usr/bin:/bin", "LC_ALL": "C",
                                    "LANG": "C", "TZ": "UTC",
                                    "TMPDIR": str(directory)})
    if completed.returncode != 0 or not module.is_file():
        raise AdapterError("candidate piano module build failed")
    return module


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
    if (type(outputs) is not list or len(outputs) != 1 or
            type(outputs[0]) is not dict or outputs[0].get("id") != "model.final" or
            type(outputs[0].get("path")) is not str or not outputs[0]["path"]):
        raise AdapterError("piano renderer needs one model.final output")
    output = Path(outputs[0]["path"]).absolute()
    if output.parent != output_dir or output.exists() or output.is_symlink():
        raise AdapterError("invalid renderer output path")
    rows = request.get("parameters")
    if (type(rows) is not list or any(
            type(row) is not dict or type(row.get("id")) is not str or
            type(row.get("value")) not in (int, float) for row in rows)):
        raise AdapterError("invalid render parameters")
    values = {row["id"]: float(row["value"]) for row in rows}
    expected = {row["id"] for row in FROZEN_CONFIG["parameters"]}
    if set(values) != expected or len(rows) != len(expected):
        raise AdapterError("render parameter set changed")
    for row in FROZEN_CONFIG["parameters"]:
        value = values[row["id"]]
        if not math.isfinite(value) or not row["minimum"] <= value <= row["maximum"]:
            raise AdapterError(f"render parameter is out of range: {row['id']}")
    csound = checked_file(FROZEN_CONFIG["files"]["csound"], "Csound")
    csd = checked_file(FROZEN_CONFIG["files"]["csd"], "CSD")
    with tempfile.TemporaryDirectory(prefix="hwa-piano-candidate-") as text:
        profile_mode = FROZEN_CONFIG.get("mode") == "profile"
        module = (compile_candidate(values, Path(text)) if profile_mode else
                  checked_file(FROZEN_CONFIG["files"]["module"], "module"))
        controls = ({"hammer_hardness": 0.43, "hammer_position": 0.12,
                     "body_control": 0.72} if profile_mode else values)
        profile_id = None
        if profile_mode:
            profile_id = load_json(Path(text) / "candidate.json")["id"]
        try:
            render_audio(csound, module, csd, output, note, controls, profile_id)
        except BaseException:
            if output.is_file() and not output.is_symlink():
                output.unlink()
            raise


def render_audio(csound, module, csd, output, note, values, profile_id=None):
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
    if profile_id is not None:
        command.insert(-1, f'--omacro:TEST_PROFILE="{profile_id}"')
    environment = {"LC_ALL": "C", "LANG": "C", "TZ": "UTC"}
    library_path = FROZEN_CONFIG.get("library_path")
    if library_path is not None:
        variable = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
        environment[variable] = library_path
    completed = subprocess.run(command, check=False, env=environment, timeout=120)
    if completed.returncode != 0 or not output.is_file() or output.is_symlink():
        raise AdapterError("Csound piano fit render failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hwa-experiment-job", type=Path)
    parser.add_argument("--validate-profile", type=Path)
    parser.add_argument("--output-dir", type=Path)
    commands = parser.add_subparsers(dest="command")
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--csound", required=True, type=Path)
    build_parser.add_argument("--module", type=Path)
    build_parser.add_argument("--profile", type=Path,
                              help="fit saved profile fields, not live controls")
    build_parser.add_argument("--fit-manifest", type=Path,
                              help="optional saved-field parameter mappings")
    build_parser.add_argument("--cc", type=Path, help="native C compiler executable")
    build_parser.add_argument("--include-dir", type=Path,
                              help="generated Csound headers for profile builds")
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
        if arguments.validate_profile is not None:
            if arguments.command or arguments.hwa_experiment_job or arguments.output_dir:
                raise AdapterError("--validate-profile cannot combine with a job/build")
            validate_candidate(arguments.validate_profile)
        elif arguments.hwa_experiment_job is not None:
            if arguments.output_dir is None or arguments.command:
                raise AdapterError("render job needs --output-dir and no build command")
            render_job(arguments.hwa_experiment_job, arguments.output_dir)
        elif arguments.command == "build":
            if arguments.sample_count < 1 or arguments.sample_count > 256:
                raise AdapterError("sample count must be 1..256")
            build(arguments)
        else:
            raise AdapterError("choose build or render job")
    except (AdapterError, OSError, ValueError, json.JSONDecodeError, wave.Error,
            subprocess.TimeoutExpired) as error:
        print(f"piano_fit_adapter.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

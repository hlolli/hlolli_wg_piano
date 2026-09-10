#!/usr/bin/env python3
"""Check native piano rendering, analyzer selection, and saved-profile replay."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import wave


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "piano_fit_adapter.py"


def run(command):
    result = subprocess.run([str(item) for item in command], check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, timeout=300)
    if result.returncode:
        raise RuntimeError("{}\n{}\n{}".format(command, result.stdout, result.stderr))
    return result


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(arguments, output, profile, references):
    command = [
        sys.executable, "-B", ADAPTER, "build", "--profile", profile,
        "--csound", arguments.csound, "--cc", arguments.cc,
        "--include-dir", arguments.include_dir, "--sample-count", "1",
        "--output-dir", output,
    ]
    if arguments.library_path:
        command.extend(["--library-path", arguments.library_path])
    for name, path in references.items():
        command.extend(["--reference-" + name, path])
    run(command)


def render(bundle, directory, case, value):
    directory.mkdir()
    request = directory / "request.json"
    output = directory / "model.wav"
    write(request, {
        "schema": "hwa-render-job", "schema_version": 1, "case_id": case,
        "outputs": [{"id": "model.final", "path": str(output)}],
        "parameters": [{"id": "radiation_scale", "value": value}],
    })
    run([sys.executable, "-B", bundle / "renderer", "--hwa-experiment-job",
         request, "--output-dir", directory])
    with wave.open(str(output), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (
                48000, 2, 2):
            raise AssertionError("unexpected rendered sample format")
        if not any(stream.readframes(stream.getnframes())):
            raise AssertionError("piano render is silent")
    return output


def check(arguments, root):
    source = ROOT / "profiles" / "concert_grand_a.json"
    before = digest(source)
    silent = root / "silent.wav"
    with wave.open(str(silent), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        stream.writeframes(b"\0" * 19200)
    cases = ("high-check", "high-fit", "low-check", "low-fit", "mid-check", "mid-fit")
    bootstrap = root / "bootstrap"
    build(arguments, bootstrap, source, {name: silent for name in cases})
    references = {
        name: render(bootstrap, root / ("target-" + name), name, 1.5)
        for name in cases
    }
    bundle = root / "fit bundle"
    build(arguments, bundle, source, references)
    experiment = read(bundle / "experiment.json")
    experiment["plan"]["kind"] = "grid"
    experiment["plan"]["sample_count"] = 0
    experiment["parameters"][0]["levels"] = [1.0, 1.5]
    write(bundle / "experiment.json", experiment)
    result = root / "experiment"
    bindings = []
    for row in read(bundle / "bindings.json")["bindings"]:
        bindings.extend(["--bind", row["id"] + "=" + row["path"]])
    run([arguments.analyzer, "experiment", bundle / "experiment.json",
         "--renderer", bundle / "renderer", "--allow-run", "--output", result,
         *bindings])
    selected = root / "selected.json"
    run([sys.executable, "-B", arguments.fit_tool, "select", "--manifest",
         bundle / "fit.json", "--experiment", result / "result.hwa-experiment",
         "--analyzer", arguments.analyzer, "--profile", bundle / "source-profile.json",
         "--output", selected, *bindings])
    fit = read(selected)
    if fit["status"] != "pass" or fit["chosen_parameters"] != {"radiation_scale": 1.5}:
        raise AssertionError("fit did not recover the known target parameter")
    fitted, receipt = root / "fitted.json", root / "receipt.json"
    command = [
        sys.executable, "-B", arguments.fit_tool, "write-profile", "--manifest",
        bundle / "fit.json", "--fit", selected, "--source", bundle / "source-profile.json",
        "--adapter", bundle / "renderer", "--output", fitted, "--receipt", receipt,
    ]
    run(command)
    proof = read(receipt)
    if (proof["source_profile_sha256"] != before or
            proof["output_profile_sha256"] != digest(fitted) or
            not proof["changes"] or any(row["after"] != 1.5 for row in proof["changes"])):
        raise AssertionError("profile receipt does not bind the saved changes")
    refused = subprocess.run([str(item) for item in command], check=False,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if refused.returncode == 0:
        raise AssertionError("writer overwrote an existing profile")
    replay_bundle = root / "replay bundle"
    build(arguments, replay_bundle, fitted, references)
    replay = render(replay_bundle, root / "replay", "mid-fit", 1.5)
    if digest(replay) != digest(references["mid-fit"]):
        raise AssertionError("saved profile did not reproduce target audio exactly")
    if digest(source) != before:
        raise AssertionError("fit changed the source profile")
    return {
        "status": "pass", "chosen_parameters": fit["chosen_parameters"],
        "cases": len(cases), "profile_paths_written": len(proof["changes"]),
        "replay_sha256": digest(replay), "source_unchanged": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("csound", "cc", "include-dir", "analyzer", "fit-tool"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--library-path", type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="hwa piano profile fit ") as text:
        print(json.dumps(check(arguments, Path(text)), sort_keys=True))


if __name__ == "__main__":
    main()

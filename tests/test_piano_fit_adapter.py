#!/usr/bin/env python3

import importlib.util
import copy
import json
import math
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest import mock
import wave


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "piano_fit_adapter.py"
SPEC = importlib.util.spec_from_file_location("piano_fit_adapter", ADAPTER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def silent_wave(path: Path) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        stream.writeframes(b"\0\0" * 4800)


class PianoFitAdapterTests(unittest.TestCase):
    def profile_bundle(self, root):
        headers = root / "headers"
        headers.mkdir()
        for name in ("csdl.h", "version.h", "float-version.h"):
            (headers / name).write_text("/* test header */")
        source = root / "source.json"
        source.write_bytes((ROOT / "profiles" / "concert_grand_a.json").read_bytes())
        csound, compiler = root / "csound", root / "cc"
        csound.write_bytes(b"csound")
        compiler.write_bytes(b"compiler")
        reference = root / "reference.wav"
        silent_wave(reference)
        arguments = types.SimpleNamespace(
            output_dir=root / "bundle with spaces", csound=csound, module=None,
            profile=source, cc=compiler, include_dir=headers, fit_manifest=None,
            library_path=None, sample_count=1,
            **{"reference_" + name: reference for name in (
                "low_fit", "low_check", "mid_fit", "mid_check", "high_fit", "high_check")})
        MODULE.build(arguments)
        renderer = types.ModuleType("frozen_piano")
        renderer.__file__ = str(arguments.output_dir / "renderer")
        exec(compile(Path(renderer.__file__).read_bytes(), renderer.__file__, "exec"),
             renderer.__dict__)
        return arguments, renderer

    def test_profile_bundle_and_validator_preserve_unmapped_fields(self):
        with tempfile.TemporaryDirectory() as text:
            arguments, renderer = self.profile_bundle(Path(text))
            bundle = arguments.output_dir
            manifest = MODULE.load_json(bundle / "fit.json")
            profile = MODULE.load_json(bundle / "source-profile.json")
            self.assertEqual(manifest["adapter_id"], "hlolli-wg-piano-profile-v1")
            self.assertTrue(manifest["parameters"][0]["profile_paths"])
            candidate = MODULE.apply_profile_parameters(
                profile, manifest["parameters"], {"radiation_scale": 1.25})
            self.assertEqual(candidate["keys"]["36"]["hammer_string_gain"],
                             profile["keys"]["36"]["hammer_string_gain"])
            output = Path(text) / "candidate.json"
            output.write_text(json.dumps(candidate))
            renderer.validate_candidate(output)
            self.assertEqual(profile, MODULE.load_json(arguments.profile))
            candidate["mechanics"]["key_action_gain"] = 2.5
            output.write_text(json.dumps(candidate))
            with self.assertRaisesRegex(renderer.AdapterError, "outside"):
                renderer.validate_candidate(output)

    def test_profile_validator_rejects_unmapped_changes_and_out_of_range(self):
        with tempfile.TemporaryDirectory() as text:
            arguments, renderer = self.profile_bundle(Path(text))
            profile = MODULE.load_json(arguments.output_dir / "source-profile.json")
            manifest = MODULE.load_json(arguments.output_dir / "fit.json")
            output = Path(text) / "candidate.json"
            for value in (0.1, 2.1):
                candidate = MODULE.apply_profile_parameters(
                    profile, manifest["parameters"], {"radiation_scale": value})
                output.write_text(json.dumps(candidate))
                with self.assertRaisesRegex(renderer.AdapterError, "out of range"):
                    renderer.validate_candidate(output)
            for change in ("mechanics", "one-key"):
                candidate = copy.deepcopy(profile)
                if change == "mechanics":
                    candidate["mechanics"]["key_action_gain"] = 2.5
                else:
                    candidate["keys"]["36"]["radiation_scale"] = 1.3
                output.write_text(json.dumps(candidate))
                with self.assertRaisesRegex(renderer.AdapterError, "outside"):
                    renderer.validate_candidate(output)

    def test_profile_inputs_are_frozen_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as text:
            arguments, renderer = self.profile_bundle(Path(text))
            source = arguments.output_dir / "source-profile.json"
            arguments.profile.write_text("{}")
            renderer.validate_candidate(source)
            header = arguments.output_dir / "profile-inputs" / "include" / "csdl.h"
            header.write_text("changed")
            with self.assertRaisesRegex(renderer.AdapterError, "hash changed"):
                renderer.validate_candidate(source)

    def test_custom_profile_mapping_and_bad_paths(self):
        profile = MODULE.load_json(ROOT / "profiles" / "concert_grand_a.json")
        manifest = MODULE.profile_fit_manifest(profile, None)
        manifest["parameters"] = [{
            "id": "hammer_gain_36", "unit": "ratio", "minimum": 0.1,
            "maximum": 2.0, "baseline": profile["keys"]["36"]["hammer_string_gain"],
            "profile_paths": [["keys", "36", "hammer_string_gain"]],
        }]
        with tempfile.TemporaryDirectory() as text:
            path = Path(text) / "fit.json"
            path.write_text(json.dumps(manifest))
            self.assertEqual(MODULE.profile_fit_manifest(profile, path), manifest)
            for target in (["midi_min"], ["keys", "missing", "radiation_scale"],
                           ["body_modes", -1, "gain"], ["mechanics"]):
                with self.assertRaises(MODULE.AdapterError):
                    MODULE.profile_target(profile, target)
            for mutate in ("duplicate", "baseline", "boolean"):
                bad = copy.deepcopy(manifest)
                if mutate == "duplicate":
                    bad["parameters"][0]["profile_paths"] *= 2
                elif mutate == "baseline":
                    bad["parameters"][0]["baseline"] = 1.99
                else:
                    bad["parameters"][0]["minimum"] = False
                path.write_text(json.dumps(bad))
                with self.assertRaises(MODULE.AdapterError):
                    MODULE.profile_fit_manifest(profile, path)

    def test_profile_render_rejects_duplicate_and_boolean_parameters(self):
        with tempfile.TemporaryDirectory() as text:
            arguments, renderer = self.profile_bundle(Path(text))
            root = Path(text)
            request = {
                "schema": "hwa-render-job", "schema_version": 1,
                "case_id": "mid-fit", "outputs": [
                    {"id": "model.final", "path": str(root / "output.wav")}],
                "parameters": [{"id": "radiation_scale", "value": 1.0}],
            }
            path = root / "job.json"
            for rows in ([request["parameters"][0]] * 2,
                         [{"id": "radiation_scale", "value": True}]):
                request["parameters"] = rows
                path.write_text(json.dumps(request))
                with mock.patch.object(renderer, "compile_candidate") as compiler:
                    with self.assertRaises(renderer.AdapterError):
                        renderer.render_job(path, root)
                    compiler.assert_not_called()

    def test_json_rejects_duplicate_keys_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as text:
            path = Path(text) / "bad.json"
            for contents in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
                path.write_text(contents)
                with self.assertRaises(MODULE.AdapterError):
                    MODULE.load_json(path)

    def test_resampling_removes_content_above_target_nyquist(self):
        source_rate = 96000
        target_rate = 48000
        # Without a low-pass filter, 42 kHz aliases to the 4-8 kHz fit band.
        values = [round(16000 * math.sin(2 * math.pi * 42000 * i / source_rate))
                  for i in range(9600)]
        raw = struct.pack("<{}h".format(len(values)), *values)
        converted = MODULE.resample_pcm16(raw, 1, source_rate, target_rate)
        samples = struct.unpack("<{}h".format(len(converted) // 2), converted)
        interior = samples[100:-100]
        rms = math.sqrt(sum(value * value for value in interior) / len(interior))
        self.assertLess(rms, 16.0)
        self.assertEqual(len(samples), 4800)

    def test_failed_render_removes_partial_audio(self):
        with tempfile.TemporaryDirectory() as text:
            arguments, renderer = self.profile_bundle(Path(text))
            root = Path(text)
            output, request = root / "output.wav", root / "job.json"
            request.write_text(json.dumps({
                "schema": "hwa-render-job", "schema_version": 1,
                "case_id": "mid-fit", "outputs": [
                    {"id": "model.final", "path": str(output)}],
                "parameters": [{"id": "radiation_scale", "value": 1.0}],
            }))

            def compile_stub(values, directory):
                (directory / "candidate.json").write_text('{"id":"concert_grand_a"}')
                return directory / "fake.so"

            def fail(*args):
                output.write_bytes(b"partial wave")
                raise renderer.AdapterError("render failed")

            with mock.patch.object(renderer, "compile_candidate", compile_stub):
                with mock.patch.object(renderer, "render_audio", fail):
                    with self.assertRaisesRegex(renderer.AdapterError, "render failed"):
                        renderer.render_job(request, root)
            self.assertFalse(output.exists())

    def test_invalid_profile_stops_before_compiler_runs(self):
        with tempfile.TemporaryDirectory() as text:
            arguments, renderer = self.profile_bundle(Path(text))
            renderer.FROZEN_CONFIG["parameters"] = [{
                "id": "bad", "profile_paths": [["default_key", "radiation_scale"]]}]
            work = Path(text) / "work"
            work.mkdir()
            with mock.patch.object(renderer.subprocess, "run") as process:
                with self.assertRaises(ValueError):
                    renderer.compile_candidate({"bad": -1.0}, work)
                process.assert_not_called()

    def test_custom_mapping_never_flattens_key_variation(self):
        profile = MODULE.load_json(ROOT / "profiles" / "concert_grand_a.json")
        profile["keys"]["36"]["radiation_scale"] = 0.5
        with self.assertRaisesRegex(MODULE.AdapterError, "baseline"):
            MODULE.profile_fit_manifest(profile, None)

    def test_resampling_preserves_fit_band_and_stereo_channels(self):
        for source_rate in (44100, 96000):
            with self.subTest(source_rate=source_rate):
                values = []
                for i in range(source_rate // 10):
                    sample = round(16000 * math.sin(2 * math.pi * 6000 * i / source_rate))
                    values.extend((sample, -sample))
                raw = struct.pack("<{}h".format(len(values)), *values)
                converted = MODULE.resample_pcm16(raw, 2, source_rate, 48000)
                samples = struct.unpack("<{}h".format(len(converted) // 2), converted)
                self.assertEqual(len(samples), 9600)
                error = max(abs(samples[2 * i] -
                                16000 * math.sin(2 * math.pi * 6000 * i / 48000))
                            for i in range(100, 4700))
                self.assertLess(error, 16.0)
                self.assertTrue(all(samples[2 * i] == -samples[2 * i + 1]
                                    for i in range(4800)))

    def test_render_only_fit_contract(self):
        manifest = json.loads((ROOT / "fit" / "piano_fit_v1.json").read_text())
        self.assertTrue(all(not row["profile_paths"]
                            for row in manifest["parameters"]))
        with tempfile.TemporaryDirectory() as text:
            root = Path(text)
            references = {}
            for name in (
                "reference_low_fit", "reference_low_check",
                "reference_mid_fit", "reference_mid_check",
                "reference_high_fit", "reference_high_check",
            ):
                path = root / f"{name}.wav"
                silent_wave(path)
                references[name] = path
            experiment = MODULE.build_experiment(references, 2)
        self.assertEqual(experiment["schema"], "hwa-experiment")
        self.assertEqual(experiment["plan"]["sample_count"], 2)
        self.assertEqual({row["split"] for row in experiment["cases"]},
                         {"fit", "check"})
        self.assertEqual([row["id"] for row in experiment["parameters"]],
                         sorted(row["id"] for row in experiment["parameters"]))

    def test_bundle_lists_published_paths(self):
        with tempfile.TemporaryDirectory() as text:
            root = Path(text)
            files = {}
            for name in ("low_fit", "low_check", "mid_fit", "mid_check",
                         "high_fit", "high_check"):
                path = root / f"{name}.wav"
                silent_wave(path)
                files[name] = path
            csound = root / "csound"
            module = root / "module"
            csound.write_bytes(b"csound")
            module.write_bytes(b"module")
            output = root / "bundle"
            arguments = types.SimpleNamespace(
                output_dir=output, csound=csound, module=module,
                library_path=None, sample_count=1,
                reference_low_fit=files["low_fit"],
                reference_low_check=files["low_check"],
                reference_mid_fit=files["mid_fit"],
                reference_mid_check=files["mid_check"],
                reference_high_fit=files["high_fit"],
                reference_high_check=files["high_check"],
            )
            MODULE.build(arguments)
            bindings = json.loads((output / "bindings.json").read_text())
            self.assertTrue(all(Path(row["path"]).is_file()
                                for row in bindings["bindings"]))


if __name__ == "__main__":
    unittest.main()

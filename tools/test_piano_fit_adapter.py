#!/usr/bin/env python3

import importlib.util
import json
import math
from pathlib import Path
import struct
import tempfile
import types
import unittest
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

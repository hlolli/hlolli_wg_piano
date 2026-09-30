#!/usr/bin/env python3
"""Checks for the measurements used by the audio regression suite."""

import argparse
import contextlib
import io
import math
from pathlib import Path
import tempfile
import unittest
import wave


import audio_analysis as analysis


class AudioAnalysisTests(unittest.TestCase):
    def test_tuning_rejects_silence_and_dc(self):
        for level in (0.0, 0.125):
            with self.subTest(level=level):
                data = analysis.WavData(8000, [[level] * 8000], 2)
                with self.assertRaisesRegex(ValueError, "signal"):
                    analysis.estimate_tuning(data, 69.0, 0.0, None, 75.0)

    def test_tuning_measures_known_detuned_tone(self):
        rate = 8000
        frequency = 440.0 * 2.0 ** (17.0 / 1200.0)
        samples = [0.4 * math.sin(2.0 * math.pi * frequency * i / rate)
                   for i in range(rate)]
        # Opposite stereo polarity must not cancel the measured fundamental.
        data = analysis.WavData(rate, [samples, [-s for s in samples]], 2)
        result = analysis.estimate_tuning(data, 69.0, 0.0, None, 75.0)
        self.assertAlmostEqual(result["cents"], 17.0, delta=0.05)

    def test_wav_rejects_truncated_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(2)
                stream.setsampwidth(2)
                stream.setframerate(8000)
                stream.writeframes(b"\0" * 400)
            original = path.read_bytes()
            for missing_bytes in (1, 4, 400):
                with self.subTest(missing_bytes=missing_bytes):
                    path.write_bytes(original[:-missing_bytes])
                    with self.assertRaisesRegex(ValueError, "truncated"):
                        analysis.read_pcm_wav(path)

    def test_windows_reject_nonfinite_times(self):
        for window in ("tail:nan:1", "tail:0:inf", "tail:0:nan"):
            with self.subTest(window=window):
                with self.assertRaises(argparse.ArgumentTypeError):
                    analysis.parse_window(window)

    def test_cli_rejects_thresholds_that_disable_checks(self):
        for option, value in (("--search-cents", "0"),
                              ("--max-abs-cents", "nan"),
                              ("--clip-level", "inf")):
            with self.subTest(option=option):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        analysis.main(["unused.wav", option, value])
                self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

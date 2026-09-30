#!/usr/bin/env python3
"""Check that timbre comparisons separate level, onset, and harmonic decay."""
import unittest
from pathlib import Path
import sys

try:
    import numpy as np
except ImportError:
    print('NumPy is required for timbre analysis tests')
    raise SystemExit(77)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import piano_timbre as tone
import generate_profiles as generator


class TimbreTests(unittest.TestCase):
    rate = 48000

    def note(self, upper_decay=5.0):
        t=np.arange(round(3.4*self.rate))/self.rate
        envelope=np.minimum(t/.003,1)*np.exp(-.6*t)
        x=envelope*np.sin(2*np.pi*440*t)+.4*np.minimum(t/.003,1)*np.exp(-upper_decay*t)*np.sin(2*np.pi*1760*t)
        return np.stack((x,.8*x),axis=1)

    def test_level_and_leading_silence_do_not_change_timbre(self):
        x=self.note()
        reference=tone.features(x,self.rate,69)
        shifted=np.concatenate((np.zeros((33600,2)),x*.07))
        actual=tone.features(shifted,self.rate,69)
        self.assertAlmostEqual(actual['onset_seconds']-reference['onset_seconds'],.7,places=5)
        np.testing.assert_allclose(actual['band_db'],reference['band_db'],atol=1e-7)
        self.assertLess(tone.errors(actual,reference,69)['loss'],1e-10)

    def test_onset_ignores_quiet_action_before_the_string(self):
        x=self.note()
        prefix=np.zeros((12000,2));prefix[2000:2100]=.10
        combined=np.concatenate((prefix,x))
        found=tone.onset(combined,self.rate)/self.rate
        self.assertGreater(found,.249)
        self.assertLess(found,.260)

    def test_harmonic_decay_change_is_visible_after_level_matching(self):
        reference=tone.features(self.note(2.0),self.rate,69)
        faster=tone.features(self.note(15.0),self.rate,69)
        difference=tone.errors(faster,reference,69)
        self.assertGreater(difference['partial_decay_rmse_db'],8)
        self.assertGreater(difference['spectral_rmse_db'],3)

    def test_reference_room_noise_does_not_become_a_sustain_target(self):
        rng = np.random.default_rng(47)
        clean = self.note(15.0)
        # The string falls below the room floor in the upper bands.
        leading = np.zeros((12000, 2))
        recorded = np.concatenate((leading, clean))
        recorded += rng.normal(0, .025, recorded.shape)
        reference = tone.features(recorded, self.rate, 69)
        model = tone.features(clean, self.rate, 69)
        unmasked = tone.errors(model, reference, 69)['loss']
        tone.add_reference_confidence(reference, recorded, self.rate, 69)
        corrected = tone.errors(model, reference, 69)['loss']
        self.assertLess(corrected, unmasked * .15)
        self.assertFalse(reference['band_valid'][-1][-1])
        self.assertTrue(reference['partial_valid'][0][0])

    def test_radiation_fit_uses_a_bounded_stable_filter_shape(self):
        f=np.linspace(0,23999,1000)
        centre=[125,315,800,2000,5000,10500]
        np.testing.assert_allclose(tone.eq_response(f,centre,.707,[0]*6),0,atol=1e-10)
        gain=tone.eq_response(np.array([800.]),centre,.707,[0,0,6,0,0,0])
        self.assertAlmostEqual(float(gain[0]),6,places=8)

    def test_radiation_table_must_cover_every_key(self):
        model=generator.load_json(tone.MODEL)
        model['radiation']['key_gain_db'].pop()
        with self.assertRaises(generator.ProfileError): generator.validate_profile(model,'test')

    def test_invalid_radiation_or_hammer_data_fails_before_compile(self):
        from decimal import Decimal
        for field,value in [('q',Decimal('0')),('centres_hz',[Decimal('100')]*6)]:
            model=generator.load_json(tone.MODEL);model['radiation'][field]=value
            with self.assertRaises(generator.ProfileError): generator.validate_profile(model,'test')
        model=generator.load_json(tone.MODEL)
        model['keys']['60']['hammer_velocity_hardness']=Decimal('1')
        with self.assertRaises(generator.ProfileError): generator.validate_profile(model,'test')

    def test_saved_fit_protocol_can_reach_radiation_gains(self):
        import json
        import piano_fit_adapter as adapter
        model = json.loads(tone.MODEL.read_text())
        parent, key = adapter.profile_target(model, ['radiation', 'key_gain_db', 39, 2])
        self.assertEqual(parent[key], model['radiation']['key_gain_db'][39][2])

    def test_refitting_keeps_existing_eq_when_no_candidate_improves(self):
        import contextlib
        import copy
        import io
        import json
        from pathlib import Path
        import tempfile
        from types import SimpleNamespace

        model = json.loads(tone.MODEL.read_text())
        original = copy.deepcopy(model)
        feature = tone.features(self.note(), self.rate, 69)
        cases = [{'note': n, 'dynamic': 'mf', 'velocity': .65,
                  'split': 'check' if n == 67 else 'fit', 'features': feature}
                 for n in (36, 48, 60, 72, 84, 96, 67)]

        class NoImprovement:
            source = 'synthetic fitter check'
            counter = 0

            def evaluate(self, candidate, subset):
                self.counter += len(subset)
                loss = 1 + float(np.sum((np.array(candidate['radiation']['key_gain_db']) -
                                        original['radiation']['key_gain_db'])**2))
                return [dict(c, loss=loss) for c in subset]

        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(report=Path(folder)/'report.json',
                                   output=Path(folder)/'candidate.json')
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'did not improve'):
                    tone.fit(args, cases, NoImprovement(), model)
            self.assertFalse(args.output.exists())
        np.testing.assert_allclose(model['radiation']['key_gain_db'],
                                   original['radiation']['key_gain_db'], atol=1e-9)


if __name__=='__main__':
    unittest.main()

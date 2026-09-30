#!/usr/bin/env python3
"""Check first-pass fit error for regressions; this does not rate piano realism."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

try:
    import numpy as np
except ImportError:
    print('NumPy is required for the rendered timbre check')
    raise SystemExit(77)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import piano_timbre as tone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csound', required=True)
    parser.add_argument('--module', type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads((ROOT / 'fit/concert-grand-timbre.json').read_text())
    model = json.loads(tone.MODEL.read_text())
    with tempfile.TemporaryDirectory(prefix='piano-timbre-') as folder:
        args.work_dir = Path(folder)
        renderer = tone.Renderer(args)
        rows = renderer.evaluate(model, fixture['references'], args.module.resolve())
    failures = []
    for row, accepted in zip(rows, fixture['accepted_notes']):
        # Allow small platform differences, while catching a single-register
        # regression that a keyboard-wide average would hide.
        limit = accepted['loss'] * 1.15 + 5
        if row['loss'] > limit:
            failures.append(f"note {row['note']} {row['dynamic']}: loss {row['loss']:.1f} > {limit:.1f}")
    for split in ('fit', 'check'):
        loss = tone.mean_loss([r for r in rows if r['split'] == split])
        limit = fixture['accepted_summary'][split] * 1.10
        print(f'{split}: loss {loss:.2f}, limit {limit:.2f}')
        if loss > limit:
            failures.append(f'{split} notes exceed the saved first-pass error limit')
    # A harder strike should change tone as well as output level.
    for note in (48, 60, 72):
        by_dynamic = {r['dynamic']: r['features'] for r in rows if r['note'] == note}
        high = [i for i in range(len(tone.BANDS)-1) if tone.BANDS[i] >= 2500]
        def brightness(feature):
            bands = np.array(feature['band_db'])[0]
            energy = 10**(bands/10)
            return 10*np.log10(energy[high].sum()/energy.sum())
        change = brightness(by_dynamic['ff']) - brightness(by_dynamic['pp'])
        print(f'note {note}: pp to ff attack brightness +{change:.2f} dB')
        if change < 3:
            failures.append(f'note {note}: velocity no longer opens the attack')
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        return 1
    print(f'PASS: {len(rows)} notes stay within the saved first-pass error limits')
    print('Listening rejected this baseline; these limits do not establish piano realism.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

# Fit inputs and accepted sound data

Keep the data needed to reproduce tuning and listening decisions here.
Local experiments, plots, and audit reports belong in the ignored `dev/`
folder. Audio renders belong in the ignored `build/` folder.

The medium-strike baseline now covers all 88 keys of one concert grand.
The user praised its register sweep on 2026-09-30. Earlier listening also
approved A♭1, C4, G4, C5 and G5 at medium strength, plus soft and hard C5
strikes. The main opcode now uses these resonances and adds velocity control
and a quiet ring after key release.

| File | Purpose |
|---|---|
| [keyboard-modal-bank.json](keyboard-modal-bank.json) | Saved 88-key medium-strike baseline: coefficients, key map, gains, feedback, and sound hashes |
| [keyboard-treble-refinement.json](keyboard-treble-refinement.json) | Seven later treble refinements and comparisons against recording background |
| [keyboard-velocity.json](keyboard-velocity.json) | Per-key soft/hard excitation curves, level trims, and recording hashes |
| [keyboard-dynamic-decay.json](keyboard-dynamic-decay.json) | Bounded soft/hard damping changes, attack level trims, input hashes, and source hashes |
| [c5-modal-reconstruction.json](c5-modal-reconstruction.json) | Original accepted C5 coefficients and sound hashes |
| [bass-modal-reconstruction.json](bass-modal-reconstruction.json) | Accepted A♭1 coefficients, output gain, and sound hashes |
| [modal-extension.json](modal-extension.json) | Coefficients and output gains for all six approved notes and strikes |
| [modal-attack-refinement.json](modal-attack-refinement.json) | Accepted C4 opening, output gain, and sound hash; replaces the earlier C4 sound |
| [concert-grand-timbre.json](concert-grand-timbre.json) | Retired waveguide fit targets and limits; listening rejected this tone |
| [piano_fit_v1.json](piano_fit_v1.json) | Input for the maintained analyzer fit adapter |

Preserve the earlier reports as evidence. For C4, combine the resonance
coefficients in `modal-extension.json` with `accepted_synthesis` in
`modal-attack-refinement.json`. The other five accepted sounds keep their
original settings. File paths and script hashes in these reports describe
the runs that produced them; local research files may have moved since then.

The keyboard baseline contains 85 measured banks. A0 and B♭0 transpose B0;
C8 transposes B7. It preserves the six corrected treble recording labels and
recreates the tested native coefficient header byte for byte. The register
sweep feedback does not establish individual approval for every key. The
baseline's nine treble flags remain recorded. A later pass separated audible
ringing from recording background and retained seven improvements. All nine
reviewed notes now sit within the same limits using that background estimate.
These are fit checks, not new listening approvals.

Velocity curves use 260 recordings across the three strike labels. The decay
extension fits a separate soft/hard damping multiplier for each partial,
bounded between 0.5 and 2. It uses 175 soft/hard recordings. A change must
reduce error in both the early fit region and a later, separate region,
with at least 20 dB of signal above recording background. Native renders
must also improve both regions. These checks select the retained changes;
they are not blind tests or listening approval. Full diagnostic reports and
fitting scripts stay in the ignored folders.

Unchanged partials retain medium damping. The extension keeps medium
frequencies, phases and mode counts; C5 retains its separate soft/hard banks.
Small hard-strike level trims on B6 and E♭7 keep those notes below the output
safety limiter. Runtime oscillators with identical poles share their excitation.
The generator checks the hashes of the medium, treble and excitation inputs
to guard against applying damping factors to a changed bank. The default
tuning preserves the five
individually approved medium strikes within PCM rounding at 44.1 and 48 kHz.
The release ring uses a separate decaying state; its level and decay remain
tuning choices until key-release recordings support a closer fit. The Iowa
files have long natural fades but supply no known key-release times, so they
do not yet justify a measured damper-release fit.

For A♭1, use the coefficients in `bass-modal-reconstruction.json` with its
`accepted_synthesis` gain and onset settings. Its 248 resonances cover 39
measured spectral peaks. The keyboard baseline preserves this sound.

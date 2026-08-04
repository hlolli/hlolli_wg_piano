# `generic_2018` baseline

This baseline records the model before profile support. The source snapshot is
commit `f1685166c4267c33764fa71f52df179194c91908`.

The runs used:

- Csound 7.0 with double samples, commit
  `6a5297a06cd152716194d9dcd9952a88e0220024`;
- AppleClang 21;
- macOS arm64;
- the current machine, with no audio output during timing runs.

Timing results vary by machine, so normal CTest does not enforce them.

## Build and tests

| Item | Baseline |
|---|---:|
| C source size | 108,500 bytes |
| Native module size | 103,288 bytes |
| Native CTest | 4 of 4 passed in 9.00 seconds |

The source SHA-256 was
`519abaff7e33d649097ad0de7b7a2ed1e471bcb070fb4fa9b17eebddfffca4c3`.
The module SHA-256 was
`1c7e44b38a67d798dec04600fcb4d6077632686503c1174a26d0d9d8af9ab5b8`.

The shared-resonance test reported:

```text
peak=0.028047 early=0.000299945 late=5.26945e-06
pedal_open=1.8231e-05 pedal_closed=4.87273e-06
disabled_peak=0 exact_handoff=True
```

The handle test found no cross-piano signal. Its continuous, split,
block-boundary, early-boundary, and four-worker renders matched exactly.

## Fixed render checks

Handled notes use stable handle and voice values in their strike seed. A second
C4 render matched byte for byte. Detached notes also seed from the opcode
address, so their file hashes can change between processes.

All rows below use 48 kHz and a closed pedal.

| MIDI | Strike | Peak | Attack dBFS | Early release dBFS | SHA-256 |
|---:|---:|---:|---:|---:|---|
| 21 | 0.25 | 0.0171225 | -50.04 | -69.24 | `dfdc6fefce384db24c15263f44fe537835aae6f86e1d6b21a331d1ed2cd61ded` |
| 21 | 0.65 | 0.0527448 | -40.13 | -59.56 | `44137388cc75b64d91025ca7e99b344e48032f3799caefb0c84ee0a19b43aa89` |
| 21 | 1.00 | 0.0826297 | -36.07 | -55.66 | `c977109756e7845d70070986dd3b36d45ffdf4e128b238194bc0bf8940831278` |
| 60 | 0.25 | 0.0166213 | -43.39 | -63.88 | `5ca27b0212788b63c5b8968d23952d8d21a0c34fc7ba117fe228f362fe59eaf2` |
| 60 | 0.65 | 0.0641404 | -32.45 | -52.48 | `5bbe9b27c1d717464a929908afdafb07df8f7e0f05afaa5ae53b537903cfda37` |
| 60 | 1.00 | 0.120876 | -27.55 | -47.64 | `696f5f35c8f1b65461652c5ad012577442490e119f61ade56a144b90b2640f11` |
| 108 | 0.25 | 0.0113686 | -56.47 | -99.51 | `7b979bb6eeab7958ed3b5074c84e4f272a109ff897cc83c9e7eb04f7c109c691` |
| 108 | 0.65 | 0.0400864 | -45.88 | -89.15 | `946914fe8431939dea8520f1440d14d737a77328df2adc270baa5d545aafd1ce` |
| 108 | 1.00 | 0.0735502 | -40.61 | -85.31 | `49456b329e9cb7a1464be79b78fe23047156ce241b558b2febf36569258427c1` |

C4 at strike `0.65` had a 1 to 2 second RMS of -92.42 dBFS with the
pedal closed and -48.93 dBFS with the pedal at `0.82`. Its 3 to 6 second
pedal-open RMS was -76.95 dBFS.

The same C4 render peaked at 0.0632379 at 44.1 kHz and 0.0672970 at 96 kHz.
The basic chord render peaked at 0.0673525 and had no clipped samples.

## Timing

| Case | Score time | Sample rate | Real time | User time |
|---|---:|---:|---:|---:|
| One C4 note | 7.35 s | 48 kHz | 0.15 s | 0.14 s |
| 64 voices | 4.5 s | 48 kHz | 1.84 s | 1.82 s |
| 192 voices | 4.5 s | 48 kHz | 4.93 s | 4.89 s |
| 64 voices | 4.5 s | 96 kHz | 3.70 s | 3.67 s |

After the profile refactor, all 14 fixed renders still matched this baseline
byte for byte. These covered the nine note and strike rows above, pedal-open
C4, 44.1 and 96 kHz C4, the basic chord, and the named `generic_2018` creator.
The final C source was 120,438 bytes and the native module was 102,904 bytes.
Paired stress runs showed about 2 to 5 percent more CPU use for the 64-voice
cases, while the 192-voice case ranged from no change to 4 percent more.

## Reproduce a fixed note

Build the module, then render the handled measurement score. Use the same
Csound build and audio format when checking a file hash.

```sh
cmake --build build --parallel

csound --opcode-lib=build/libhlolli_wg_piano.dylib \
  --omacro:TEST_NOTE=60 --omacro:TEST_VELOCITY=0.65 \
  -W -l -d -m0 -o /tmp/handled-c4.wav tests/measure_note.csd
```

Set `TEST_PEDAL`, `TEST_SR`, or the other macros in
`tests/measure_note.csd` to render another baseline case.

# hlolli_wg_piano

`hlolli_wg_piano` is a Csound piano module written in C. It exports a note
opcode, a piano-handle creator, and a wet-output opcode. The model uses no
samples or external data files.

The note voice uses measured damped resonances across all 88 keys. Strike
velocity changes both level and tone. Releasing a key damps the strings and
leaves a quiet residual ring. The opcode requests its own release time;
callers need no note fade or `xtratim` to preserve that tail.

Create one handle for each piano:

```csound
giPiano hlolli_wg_piano_create
```

The note opcode keeps its ten controls and takes the handle as an optional
last input:

```csound
aLeft, aRight hlolli_wg_piano \
    kTrigger, kFrequency, kHardness, kHammerPosition, kDecay, \
    kStiffness, kDetune, kBody, kStrange, kPedal, giPiano
```

The wet opcode reads that piano's hidden send and returns wet signal only:

```csound
aWetLeft, aWetRight hlolli_wg_piano_resonance \
    giPiano, kBody, kPedal
```

The creator signature is `i <- ""`. The note and handled wet
signatures are `aa <- kkkkkkkkkko` and `aa <- ikk`. Keep the direct note
outputs in the mix; the wet opcode does not pass them through. The handle owns
the body, sympathetic strings, delay tail, control smoothing, and their phases
until Csound resets. Keep one wet-output instrument alive for each piano. If it
ends, a later one resumes the same stored state.

The old `aa <- aakk` wet form remains available. It takes an explicit stereo
bus and uses one default piano state. Use it when the score needs a custom send
level or routing path.

The project builds as a stand-alone Csound runtime module. It can also enter a
Csound source build through `add_subdirectory()` and Csound's `make_plugin()`
helper. The source was tested with Csound 7.0, double-precision samples, on
macOS arm64.

## Files

```text
CMakeLists.txt                 Stand-alone and Csound-tree build rules
hlolli_wg_piano.c              Complete opcode source
README.md                      Build and control reference
LICENSE                        MIT license
Custom.cmake.example           Optional local path settings
profiles/concert_grand_a.json  The concert grand's tuning data
profiles/schema/               Tuning-data format
tools/generate_profiles.py     Data checker and C-table generator
tools/generate_modal_bank.py   Resonance and velocity table generator
tools/piano_timbre.py          Offline hammer, decay, and radiation fit
fit/                          Fit inputs and accepted sound data
recordings/iowa-timbre.json    Fit and check recording manifest
recordings/README.md           Piano recording and data rules
recordings/example-capture.json  Small capture input example
examples/basic.csd             Short chord example
examples/timbre-check.csd      Isolated notes without added room reverb
examples/lpcs-playback.csd     LPCS piano-performance-v1 adapter
examples/chopin_aeolian_harp.csd  Longer musical example
tests/smoke.csd                Native load and render test
tests/measure_note.csd         Handled-note measurement render
tests/shared_resonance.csd     Shared-state and tail render
tests/handle_resonance.csd     Two-piano isolation render
tests/handle_handoff.csd       Wet-output handoff and error render
tests/held_renderer_gap.csd    Held-key renderer restart render
tests/stress.csd               Range and polyphony stress render
tests/audio_analysis.py        PCM WAV metrics and tuning checks
tests/initial_controls.csd     First-block note control render
tests/run_initial_controls_test.py  Initial and k-rate control comparison
tests/run_shared_resonance_test.py  Shared-tail test driver
tests/run_handle_state_test.py Piano-handle state test driver
tests/modal_voice.csd          Native strike and release fixture
tests/run_modal_voice_test.py  Approved-sound, velocity, and release checks
```

## Concert-grand data

All notes and handles use one concert grand. There is no runtime profile
selector, registry, or alternate instrument.

`fit/keyboard-modal-bank.json` preserves the praised medium-strike baseline.
`fit/keyboard-treble-refinement.json` supplies seven later treble refinements.
`fit/keyboard-velocity.json` supplies measured soft/hard excitation curves
for each key. `fit/keyboard-dynamic-decay.json` adds bounded soft/hard damping
changes for partials supported by the recordings and native render checks.
C5 retains its separately fitted soft and hard strikes from
`fit/modal-extension.json`. The velocity points are playing conventions;
the source recordings do not give measured hammer speeds.

`profiles/concert_grand_a.json` holds damper, stiffness-control, output-gain,
sympathetic, and shared-body tuning. Its version 4 format also retains the
earlier waveguide fields for saved-data and fit-tool compatibility. Hammer,
felt, rail-loss, and broad radiation-EQ fields no longer shape the direct
note voice. The resonance coefficients set its base timbre.

The generator checks the JSON and replaces only the marked profile-data block
inside `hlolli_wg_piano.c`:

```sh
python3 -B tools/generate_profiles.py --check
python3 -B tools/generate_modal_bank.py --check
python3 -B tools/generate_profiles.py
python3 -B tools/generate_modal_bank.py
```

In a stand-alone build, when CMake finds Python, the same actions are available
as targets:

```sh
cmake --build build --target hlolli_wg_piano_check_model
cmake --build build --target hlolli_wg_piano_generate_model
```

Edit the JSON, not the generated C block. The generator needs Python 3.8 or
newer, has no third-party packages, and writes no date or machine path. The
same input therefore gives the same C text. It also rejects output above the
browser compiler's 2 MiB source limit. Builds never run it on their own. The
checked-in C file still holds all runtime data and remains a single source file
for native and WASI builds.

The browser demo keeps a byte-for-byte copy of `hlolli_wg_piano.c` at
`demos/demo1/wg-piano.c` in the
[`csound-wasm-plugin-compiler`](https://github.com/hlolli/csound-wasm-plugin-compiler)
repository. Make model and profile changes here first, run the native checks,
then replace that demo file and run its piano build-and-play check. Both builds
use the same model and tables. The WASI build also uses double-precision SIMD
for note resonances and has host-specific mutex and reset cleanup code.

## Piano capture data

The [capture guide](recordings/README.md) sets out a practical recording method
for notes, pedals, sympathetic strings, body taps, and room sweeps. The small
[capture example](recordings/example-capture.json) shows the data needed by a
fitting tool.

Use a generic public piano ID and class. Keep the maker, model, serial number,
names, and exact place in local notes when needed. Raw audio stays out of Git.
Only fitted numbers enter the profile JSON and the fixed arrays in
`hlolli_wg_piano.c`; the runtime still uses no samples or data files.

Keep local sound experiments, audit reports, and scratch tests in `dev/`,
which Git ignores. Build tools stay in `tools/`; maintained tests stay in
`tests/` and run through CTest. The build does not need `dev/`.

[Accepted sound data](fit/README.md) stays in `fit/`, including refined C4.
The main opcode now uses this sound. Its five individually approved medium
strikes match the saved waveforms within PCM rounding at the default tuning.
Velocity changes both excitation and damping across the keyboard. Each
retained damping change improves two separate time regions in the reference
comparison. Partials without enough evidence keep their medium damping.
A0, B♭0, and C8 still use nearby medium-strike banks; A0 also borrows its soft
reference from B♭0. New treble and velocity settings still need listening.

## Stand-alone build

The Csound include directory must contain `csdl.h`, `version.h`, and
`float-version.h`. For a Csound source checkout, use the generated include
directory in the build tree. The raw source `include` directory is not enough.

```sh
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build \
  -DCSOUND_EXECUTABLE=/path/to/csound/build/csound
cmake --build build --target hlolli_wg_piano
ctest --test-dir build --output-on-failure
```

The timbre and partial-curve tests need NumPy. Set `HLOLLI_PIANO_ANALYSIS_PYTHON` to a Python
executable that has it; CTest reports those tests as skipped when it is absent.
The render test uses stored numeric targets and needs no reference downloads.

You can give the header directory instead:

```sh
cmake -S . -B build -G Ninja \
  -DHLOLLI_CSOUND_INCLUDE_DIR=/path/containing/csdl.h
```

`CSOUND_INCLUDE_DIR` also works for compatibility with older local plugin
projects. You may copy `Custom.cmake.example` to `Custom.cmake` instead of
putting local paths on every command line. Git ignores `Custom.cmake`.

The output name is normally:

| System | Module |
|---|---|
| macOS | `build/libhlolli_wg_piano.dylib` |
| Linux | `build/libhlolli_wg_piano.so` |
| Windows | `build/hlolli_wg_piano.dll` |

Run the short example on macOS with:

```sh
csound --opcode-lib=build/libhlolli_wg_piano.dylib examples/basic.csd
```

Change the module suffix for Linux or Windows. The CSD files do not contain a
fixed plugin path, so the same files work on all three systems.

## LPCS and browser playback

`examples/lpcs-playback.csd` reads the `piano-performance-v1` LPCS target with
the reader from `lilypond-csound-score-plugin`. It needs Csound 7 with typed
JSON opcodes and `lpcs-playback.inc` on the include path. Supply the JSON path
as the `LPCS_FILE` orchestra macro; it defaults to `performance.json`.

Each note releases its key at `extensionOne`, not at the longer sounding
duration. CC64 drives the dampers and shared resonance. The adapter adds no
room reverb and leaves three seconds after the score for decay. It supports
only sustain; it rejects nonzero soft and sostenuto commands. Tied notes must
be resolved before playback.

The `performance-learning` browser demo can load the same adapter and a WASM
build of the piano. To build it, install Bun and the dependencies in a local
`csound-wasm-plugin-compiler` checkout, then run:

```sh
export CSOUND_PLUGIN_COMPILER_REPO=/path/to/csound-wasm-plugin-compiler
export CSOUND_PLUGIN_SDK=/path/to/runtime/lib/csound-plugin-sdk.tar.gz
bun tools/build_wasm.mjs
```

Use the SDK from the exact Csound browser runtime that will load the plugin.
The helper compiles this repository's C source, including its math functions,
and writes `build/wasm/hlolli_wg_piano.wasm`. It uses the shared compiler's
browser plugin format, not a standalone WASI executable. Rebuild after any
source or runtime change. Build output stays out of Git.

The note engine computes four samples per resonance step and preserves every
fitted mode, velocity layer, and release tail. Clang's WebAssembly build uses
128-bit SIMD for pairs of double-precision samples, so the browser must support
WebAssembly SIMD. Native builds use the same four-sample calculation in C.

## Add it to a Csound source build

Add this after Csound has defined `make_plugin()`, for example from Csound's
`Opcodes/CMakeLists.txt`:

```cmake
add_subdirectory(
  "/absolute/path/to/hlolli_wg_piano"
  "${CMAKE_BINARY_DIR}/hlolli_wg_piano"
)
```

The project detects the Csound build helper and uses it. Csound then supplies
the public headers, compile definitions, output directory, and correct plugin
install directory. The target is `hlolli_wg_piano`; the build-tree alias is
`hlolli::wg_piano`.

When a parent project does not provide `make_plugin()`, this project creates
the runtime module itself. Set `HLOLLI_CSOUND_BUILD_DIR` or
`HLOLLI_CSOUND_INCLUDE_DIR` before `add_subdirectory()`.

Do not link another target to this module. Csound loads it at runtime. The alias
exists so a parent can test for the target or add a build dependency.

## Install

A stand-alone build derives a default such as
`lib/csound/plugins64-7.0` under `CMAKE_INSTALL_PREFIX`:

```sh
cmake --install build --prefix "$HOME/.local"
```

Set an exact user plugin directory when the local Csound install uses another
layout. For example, configure a Csound 7 macOS user install with:

```sh
cmake -S . -B build -G Ninja \
  -DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build \
  -DHLOLLI_CSOUND_PLUGIN_DIR="$HOME/Library/csound/7.0/plugins64"
cmake --build build
cmake --install build
```

When built inside Csound, Csound's own install rule takes over. No CMake package
export is installed because this is a loaded module, not a link library.

## Note opcode inputs

The ten sound controls run at k-rate. Values outside the accepted range are
clamped. Hardness and hammer position apply at each strike; the other tone
controls smooth changes during the ring. The optional last input is the i-rate handle from
`hlolli_wg_piano_create`. Omit it for a detached note with no hidden wet send.

| Input | Accepted range | Suggested range | Grand value | Effect |
|---|---:|---:|---:|---|
| `kTrigger` | 0 to 1.25 | 0.05 to 1.0 | about 0.65 | Strike velocity and key state. Values above 1 give a harder accent. Zero releases and rearms the hammer. |
| `kFrequency` | 20 Hz to `0.45*sr` | 27.5 to 4186 Hz | note pitch | Selects the nearest key at onset, then transposes that bank. Recorded tuning and beating remain at the nominal key frequency. |
| `kHardness` | 0 to 1 | 0.15 to 0.75 | 0.43 | Adds a gentle high-partial tilt to the velocity-dependent strike. |
| `kHammerPosition` | 0.025 to 0.45 | 0.07 to 0.20 | 0.12 | Changes the strike's partial balance around the measured setting. |
| `kDecay` | 0 to 1 | 0.40 to 0.90 | 0.70 | Scales measured resonance losses. Key state and pedal add damper loss. |
| `kStiffness` | 0 to 1 | 0.15 to 0.70 | 0.42 | Changes upper-partial stretch around the measured tuning. |
| `kDetune` | 0 to 1 | 0.20 to 0.80 | 0.60 | Changes spacing within nearby resonances; the default preserves measured beating. |
| `kBody` | 0 to 1 | 0.30 to 0.90 | 0.72 | Sets the quiet residual ring after damping and the shared body-mode send. |
| `kStrange` | -1 to 1 | -0.30 to 0.30 | 0 | Adds small opposing frequency shifts to the resonances. |
| `kPedal` | 0 to 1 | 0 to 1 | 0 or 0.82 held | Sets the local damper for a detached note. For a handled note, the wet opcode's shared pedal rail sets the damper. The dampers fully clear by about 0.82. |

The opcode also reads Csound's score/MIDI release flag. A constant positive
trigger therefore cannot hold a note after its instrument releases. It keeps
up to eight seconds of extra time, with a smooth close during the final
second. Explicit trigger release within a live instrument has no such limit.
Keep the shared wet-output instrument alive through the musical ending.
The local residual ring models stored energy with a separate decay; its
level and decay are tuning choices, not fitted damper-release measurements.

## Piano handle and wet output

Each call to `hlolli_wg_piano_create` returns a new positive i-rate handle.
Pass the same handle to all notes and the one wet-output opcode for that piano.
Create a second handle for a second piano. Their modes, phases, held keys, and
delay memory remain separate.

```csound
giPiano hlolli_wg_piano_create
```

The creator always uses the concert-grand data. Each handle keeps its own
strings, pedal state, and body tail. The former string-name creator overload
has been removed; replace named calls with the no-input form above.

The handle form of `hlolli_wg_piano_resonance` has one i-rate input and two
k-rate controls:

| Input | Range | Usual value | Effect |
|---|---:|---:|---|
| `iPiano` | valid handle | from `hlolli_wg_piano_create` | Selects the piano state and hidden note send. |
| `kBody` | 0 to 1 | 0.72 | Wet level, body-mode decay, and tail length and tone. Zero mutes the wet return. |
| `kPedal` | 0 to 1 | 0 or about 0.82 | Moves the piano's shared damper rail, opens the sympathetic bank, and lengthens the tail. The dampers fully clear by about 0.82. |

Handled notes write a tagged block buffer and the wet opcode reads the prior
block. This fixed one-`ksmps` delay makes the result independent of instrument
order and Csound worker count. The handle creator, handled notes, and handle
output must run at the orchestra's engine `ksmps`; the module rejects local
`setksmps` rates. Detached notes can still use a local rate. Use one live
wet-output opcode per handle.

For offline sample-accurate scores, two back-to-back instances of the same
output instrument can switch without resetting state. Csound may keep both
alive for one control block, so the module accepts only an exact,
non-overlapping handoff. Keep one output instance alive in real-time use.

The opcode clamps and smooths the controls. For handled notes, the wet opcode's
`kPedal` drives one shared damper rail for that piano. Half-pedal and repedalling
therefore affect the direct strings, sympathetic strings, and tail together. A
held note keeps its damper open even when the pedal is closed. Counts keep that
damper open until every overlapping voice for the key has released. Detached
notes still use their own `kPedal` input.

The sympathetic bank tracks three inharmonic partials for each of the 88 keys.
It uses the profile's per-key tuning, decay, and partial levels. The note opcode
can still bend a voice away from that stored pitch. A handled voice reports the
key nearest its initial frequency. Keep large pitch moves in a detached voice,
or start a new handled voice for the new key.

## Explicit-bus wet form

`hlolli_wg_piano_resonance` has two audio inputs and two k-rate controls:

| Input | Range | Usual value | Effect |
|---|---:|---:|---|
| `aBusLeft`, `aBusRight` | audio | summed note bus | Drives all shared modes and the common tail. |
| `kBody` | 0 to 1 | 0.72 | Wet level, body-mode decay, and tail length and tone. Zero mutes the wet return. |
| `kPedal` | 0 to 1 | 0 or about 0.82 | Opens the sympathetic modes and lengthens the shared tail. The dampers fully clear by about 0.82. |

This form has the old `aa <- aakk` signature. It uses a default global piano
state, so its modes also survive a wet-output instrument handoff. It has no
handle-tagged notes or held-key reports. Run only one live explicit-bus wet
opcode at a time. This persistent output form also requires engine `ksmps`.

## Two-opcode routing

The handle route needs no audio bus and does not depend on instrument order.
Schedule the wet output for the performance and final tail.

```csound
giPiano hlolli_wg_piano_create
gkPedal init 0.82

instr PianoNote
  iNote = p4
  iVelocity = p5
  kRelease release
  kTrigger = (kRelease == 0 ? iVelocity : 0)
  kFrequency init cpsmidinn(iNote)

  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, 0.43, 0.12, 0.70, \
      0.42, 0.60, 0.72, 0, gkPedal, giPiano

  outs aLeft, aRight
endin

instr PianoResonance
  aWetLeft, aWetRight hlolli_wg_piano_resonance \
      giPiano, 0.72, gkPedal
  outs 0.35 * aWetLeft, 0.35 * aWetRight
endin
```

For example, schedule `PianoResonance` from time zero through the last note and
tail, such as `i "PianoResonance" 0 3600`. Do not run two output instances for
the same handle at once. Back-to-back instances are valid: the second resumes
the state that belongs to the handle. Keep an output running while notes play;
with no output, the wet phases stop and the two-block send buffer keeps only the
newest note blocks.

## Note control details

A trigger above `0.0001` holds the key. The first positive value strikes;
zero releases and rearms it. A rise above `0.035` can restrike a live voice.
Repeated strikes add excitation to the current ring and preserve its phase.

The medium strike at `0.65` preserves the saved resonance bank. Soft and hard
strikes use measured attack colour and damping at `0.20` and `1.00`, with smooth
changes between them. Soft/hard damping uses bounded loss multipliers for
each fitted partial. C5 blends its three separately fitted banks. Loudness follows
velocity in addition to those tone changes. Hardness and hammer position add
small changes around the measured strike. A new strike preserves the decay
of energy left by earlier strikes.

`kFrequency` selects the nearest MIDI key at the first performance block.
Later changes transpose its frequencies with about 25 ms of smoothing.
Use `cpsmidinn()` for keys 21 through 108. Initial and ordinary k-rate
assignments produce the same first strike. The chosen key still determines
handled damping and body coupling throughout the voice.

At the default decay, stiffness, and detune settings, the medium strike preserves
the measured decay poles, partial spacing, and beating. Those controls scale loss,
upper-partial stretch, and nearby pole spacing. `kStrange` adds small opposing
frequency shifts; leave it at zero for the concert grand.

Key release adds damper loss smoothly. The highest undamped keys retain their
natural decay. A small part of the ring continues in a separate state that
loses energy more slowly than the damped strings. `kBody` sets this part's
level. The shared wet opcode separately supplies body and sympathetic resonance.

Handled notes send their output and a key-weighted body drive before any
outside gain or pan. The handle owns the shared state after a note ends.
Use the explicit-bus wet form when the send must follow an outside effect.
Half-pedal and repedalling act through the shared damper state for handled
notes, or through `kPedal` for detached notes.

## Starting settings

This is the main realistic starting point:

```text
kHardness        0.43
kHammerPosition  0.12
kDecay           0.70
kStiffness       0.42
kDetune          0.60
kBody            0.72
kStrange         0.00
kPedal           0.00 key up, about 0.82 for a held pedal
```

Some useful variants:

| Sound | Hardness | Position | Decay | Stiffness | Detune | Body | Strange |
|---|---:|---:|---:|---:|---:|---:|---:|
| Soft grand | 0.28 | 0.14 | 0.80 | 0.34 | 0.55 | 0.80 | 0 |
| Plain grand | 0.43 | 0.12 | 0.70 | 0.42 | 0.60 | 0.72 | 0 |
| Bright studio | 0.58 | 0.10 | 0.66 | 0.48 | 0.58 | 0.62 | 0 |
| Worn piano | 0.38 | 0.13 | 0.76 | 0.40 | 0.78 | 0.75 | 0.04 |
| Prepared | 0.64 | 0.08 | 0.72 | 0.70 | 0.82 | 0.66 | 0.55 |

## Nonfinite input handling

NaN and infinity are replaced before control clamping. The fallbacks are
trigger `0`, frequency `440`, hardness `0.43`, position `0.12`, decay `0.70`,
stiffness `0.42`, detune `0.60`, body `0.72`, strange `0`, and pedal `0`.
These are safety values, not optional arguments or the recommended preset.
The wet opcode uses `0.72` for a nonfinite body control and `0` for a
nonfinite pedal control. A nonfinite wet result clears its shared state.
Nonfinite shared audio inputs are replaced with zero before they reach that
state. Piano handles must be finite positive integers returned by
`hlolli_wg_piano_create`; an unknown handle stops the new opcode instance at
init time.

## Model notes

Each note keeps fitted damped resonances, the current strike, earlier strike
energy, and a quiet release state. These coefficients describe recorded
output, including the microphone and room. They do not identify physical string
counts or isolate the soundboard. The runtime evaluates recurrences; it never
plays recorded waveforms or envelopes.

Each piano handle owns 12 body modes, three sympathetic partials per key, an
eight-line feedback-delay tail, pedal and damper state, held-key counts, and
stereo sends. Csound allocates this shared state outside note instruments and
frees it at reset. Native builds use a plugin reset callback; the WASI host
frees its named globals and tracked blocks. A wet-output opcode advances and
reads that state.

The sympathetic bank models three inharmonic partials per key. The release
ring is a tuned approximation; measured key-release recordings would support
a closer fit.

## Examples

`examples/basic.csd` plays two sustained chords and shows one piano handle,
tagged notes, and a dry/wet mix.

`examples/timbre-check.csd` plays C3, C4, and C5 with the model's own body
response and stereo output. It adds no room reverb. Use it for timbre checks;
the basic and Chopin examples add room reverb after the piano.

`examples/chopin_aeolian_harp.csd` plays the opening of Chopin's Etude in
A-flat major, Op. 25 No. 1. Its top melody overlaps each next beat. It routes
all notes through one piano handle, then adds a small room.

`tests/smoke.csd` gives a short render that calls both opcodes.

`tests/run_initial_controls_test.py` compares direct and wet renders from
equivalent initial and k-rate controls across three block
sizes. `tests/test_audio_analysis.py` checks known pitch, silence, truncated
files, and measurement limits. Both run through CTest.

`tools/piano_fit_adapter.py` uses the analyzer's same checked renderer and
fit/check selector as the violin project. It sweeps the public body, hammer
hardness, and hammer-position controls over low, middle, and high notes. This
proves that the fit interface does not depend on violin strings or profiles.

The adapter's `--profile` option supplies an offline tuning candidate through
the shared analyzer protocol. It does not select a runtime piano.

`tools/piano_timbre.py` retains audio-analysis helpers and the earlier
waveguide fit workflow. Its hammer and radiation-EQ search does not tune the
new direct resonance voice. The rejected fit remains in
`fit/concert-grand-timbre.json` as evidence. Edit the current resonance and
velocity data in `fit/`, regenerate with `tools/generate_modal_bank.py`, then
run the native checks and compare recordings before keeping a new fit.

`tests/run_modal_voice_test.py` checks the approved held-note waveforms at
44.1 and 48 kHz, velocity tone and level, automatic score release, a quiet
residual ring, and pedal sustain. It replaces the old delay-line and rejected
timbre regression tests. Local experiments remain in ignored `dev/`.

The same C source and either CSD can also be pasted into the
[Csound opcode workbench](https://hlolli.github.io/plugin-compiler/).

## License

MIT. See `LICENSE`.

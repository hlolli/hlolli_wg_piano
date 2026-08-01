# hlolli_wg_piano

`hlolli_wg_piano` is a stereo Csound piano opcode written in C. It uses
dispersive delay rails, a felt hammer, detuned unisons, and a short soundboard
network. It uses no samples or external data files.

```csound
aLeft, aRight hlolli_wg_piano \
    kTrigger, kFrequency, kHardness, kHammerPosition, kDecay, \
    kStiffness, kDetune, kBody, kStrange, kPedal
```

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
examples/basic.csd             Short chord example
examples/chopin_aeolian_harp.csd  Longer musical example
tests/smoke.csd                Native load and render test
```

## Stand-alone build

The Csound include directory must contain `csdl.h`, `version.h`, and
`float-version.h`. For a Csound source checkout, use the generated include
directory in the build tree. The raw source `include` directory is not enough.

```sh
cmake -S . -B build -G Ninja \
  -DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build \
  -DCSOUND_EXECUTABLE=/path/to/csound/build/csound
cmake --build build --target hlolli_wg_piano
ctest --test-dir build --output-on-failure
```

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

## Inputs

All ten inputs are required and run at k-rate. Values outside the accepted
range are clamped. The suggested range is not a hard limit; it marks the area
that remains close to an acoustic grand.

| Input | Accepted range | Suggested range | Grand value | Effect |
|---|---:|---:|---:|---|
| `kTrigger` | 0 to 1.25 | 0.05 to 1.0 | about 0.65 | Strike velocity and key state. Values above 1 give a harder accent. Zero releases and rearms the hammer. |
| `kFrequency` | 20 Hz to `0.45*sr` | 27.5 to 4186 Hz | note pitch | Fundamental frequency. Use the 88-key piano range for normal use and stay below `0.43*sr` for reliable rail tuning. |
| `kHardness` | 0 to 1 | 0.15 to 0.75 | 0.43 | Soft, long felt contact to short, bright contact. It also changes soundboard brightness. |
| `kHammerPosition` | 0.025 to 0.45 | 0.07 to 0.20 | 0.12 | Strike point as a fraction of string length. It moves comb notches in the attack spectrum. |
| `kDecay` | 0 to 1 | 0.40 to 0.90 | 0.70 | Short to long string decay. Pitch, key state, and pedal also affect the measured tail. |
| `kStiffness` | 0 to 1 | 0.15 to 0.70 | 0.42 | Low to high dispersion. Large values spread upper partials and can sound metallic. |
| `kDetune` | 0 to 1 | 0.20 to 0.80 | 0.60 | Spread of the active unison strings. Zero keeps a small built-in spread and drift. |
| `kBody` | 0 to 1 | 0.30 to 0.90 | 0.72 | Dry bridge path to a stronger, longer, and denser per-voice soundboard response. |
| `kStrange` | -1 to 1 | -0.30 to 0.30 | 0 | Prepared and unstable colors. Both signs add detune, nonlinear partials, coupling, and soundboard motion. |
| `kPedal` | 0 to 1 | 0 to 1 | 0 or 0.82 held | Continuous damper amount. Half-pedal values work. It changes internal decay but does not keep a stopped Csound instrument alive. |

### Trigger and note life

A value above `0.0001` means key down. The first positive value strikes the
hammer. Return it to zero before the next ordinary strike. A rise of more than
about `0.035` can restrike a voice while it remains positive.

Velocity also makes the felt a little harder. A trigger of `1.25` is safe but
is meant for an accent, not a normal MIDI velocity map.

`kPedal` controls the damper inside the opcode only while the Csound instrument
exists. Give the host instrument enough release time and fade its output at the
end. A useful pattern is:

```csound
xtratim 2.60
kRelease release
kTrigger = (kRelease == 0 ? iVelocity : 0)
kPedal = 0.82
kTail linsegr 1, 0.01, 1, 2.60, 0

aLeft, aRight hlolli_wg_piano \
    kTrigger, kFrequency, 0.43, 0.12, 0.70, \
    0.42, 0.60, 0.72, 0, kPedal
outs aLeft * kTail, aRight * kTail
```

Each opcode instance owns its strings and soundboard. `kPedal` does not add
sympathetic vibration between separate notes. The Chopin example sends all
voices through a shared body filter and two `reverbsc` stages for that part of
the sound.

### Frequency

`kFrequency` can change while a note rings. Control values are smoothed over
about 25 ms and the string delay follows over about 18 ms, so pitch changes
glide instead of stepping. Normal piano use should pass `cpsmidinn()` values
from MIDI note 21 through 108.

The model uses one audible string in the low bass. A second string fades in
from about 39 to 49 Hz. The third fades in from about 116 to 147 Hz. Small
inactive-string floors keep the internal state safe but remain inaudible.

### Hammer hardness and position

`kHardness` sets felt contact time, attack brightness, and some soundboard
brightness. A low value gives a soft attack. A high value shortens contact and
passes more high-frequency energy. Velocity adds a small amount of hardness at
each strike.

`kHammerPosition` sets the delay of the hammer-position comb. Values near the
suggested range give common piano spectra. Large values move the notches lower
and can make the attack hollow. Hardness and position matter most at the next
strike.

### Decay, stiffness, and detune

`kDecay` scales a pitch-dependent decay target. Bass strings keep more energy
than short treble strings. When the key is released with no pedal, the damper
sets a short decay. Raising `kPedal` moves the released note toward its held
decay.

`kStiffness` controls four dispersion stages in each string. Keep it below
about `0.70` for a piano. Higher settings are useful for bell-like tones.

`kDetune` controls a curved unison spread. Before register scaling, the main
spread is about `0.18 + 1.05*kDetune^2` cents. Every strike also gets very small
errors in pitch, level, contact time, and comb position. Each string has its own
slow pitch drift. These changes stop repeated notes from being exact copies
without making a normal preset sound out of tune.

### Body

`kBody` controls the amount, brightness, and feedback of a four-line
soundboard. Low values expose more direct string. High values give more of the
filtered bridge and soundboard output. This soundboard belongs to one opcode
voice; use a shared Csound effect after the opcode when several notes should
feed the same body.

### Strange

Leave `kStrange` at zero for the acoustic preset.

- Negative values add loss and lower the third string. At `-1`, that string is
  one octave below its usual pitch.
- Positive values add more dispersion.
- Both signs add unison spread, nonlinear partials, stronger string coupling,
  and a signed cyclic path in the soundboard.

Values between about `-0.30` and `0.30` keep the note identity clear. The full
range is for prepared and unstable sounds.

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
trigger `0`, frequency `440`, hardness `0.45`, position `0.12`, decay `0.65`,
stiffness `0.45`, detune `0.35`, body `0.65`, strange `0`, and pedal `0`.
These are safety values, not optional arguments or the recommended preset.

## Model notes

The design follows the reduced models in Balazs Bank and Juliette Chabassier,
"Model-based digital pianos: from physics to sound synthesis" (IEEE Signal
Processing Magazine, 2019; manuscript dated 2018). The signal path contains:

- one to three detuned and dispersive string rails;
- a pitch-scaled felt contact with small filtered noise;
- fixed and slowly moving unison errors;
- low-level nonlinear string color;
- three short hammer and felt modes;
- direct bridge radiation and a four-line soundboard network;
- partial correction for fractional-delay loss in the treble.

This is a reduced real-time model, not a full finite-element piano model.

## Examples

`examples/basic.csd` plays two sustained chords with the realistic settings.

`examples/chopin_aeolian_harp.csd` plays the opening of Chopin's Etude in
A-flat major, Op. 25 No. 1. Its top melody overlaps each next beat. It also
shows one way to add a shared body response and room after the per-note opcode.

The same C source and either CSD can also be pasted into the
[Csound opcode workbench](https://hlolli.github.io/plugin-compiler/).

## License

MIT. See `LICENSE`.

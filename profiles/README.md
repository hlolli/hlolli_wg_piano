# Concert-grand tuning data

The concert-grand JSON file is the source for the piano tables compiled
into `hlolli_wg_piano.c`. Csound does not read them at run time. This keeps the
native and browser plugins self-contained.

`concert_grand_a.json` holds the sole concert grand. Tune this model as needed;
there is no runtime profile selection. `schema/piano-profile-v4.schema.json`
defines the format. The generator accepts version 4 only.

The direct voice now uses resonance and velocity data in `fit/`, embedded by
`tools/generate_modal_bank.py`. This version 4 file still supplies damper,
stiffness-control, output-gain, sympathetic, and shared-body tuning. Older
hammer, felt, rail-loss, and radiation-EQ fields remain for saved-data
compatibility; they no longer shape the direct voice. The descriptions below
record the format's original roles.

## Generate the C tables

Run the generator from the repository root:

```sh
python3 tools/generate_profiles.py
```

It needs Python 3.8 or newer and no third-party packages. It also rejects a
generated C source above the browser compiler's 2 MiB limit.

It validates the sole source and replaces only the marked profile-data
block in `hlolli_wg_piano.c`. It does not create an include file because the
browser compiler accepts one plugin C source file.

The script has built-in checks that match the version 4 schema, so it needs no
JSON Schema package. It parses the schema file and checks its version link, but
it does not act as a general JSON Schema engine. Keep the schema and script
rules in step when the format changes.

Check that the source and generated C agree without changing files:

```sh
python3 tools/generate_profiles.py --check
```

The generator emits stable text. Do not edit the generated C block by hand.

## Tune the concert grand

1. Edit `concert_grand_a.json` and its source notes.
2. Run the generator and its `--check` form.
3. Run the tests and render notes, chords, pedal changes, and a stress score.

An `id` uses lower-case ASCII letters, digits, and underscores. It starts with
a letter, has at most 63 characters, and matches the source filename. The
`display_name` holds the model's plain name. These fields track the data; they
do not add a runtime selector. The shared fitting protocol still calls saved
tuning data a profile.

`midi_min` and `key_count` set one continuous keyboard range. The last key must
not exceed MIDI 127. `sympathetic_mode_count` must be at least two and no more
than `key_count`. It counts keys in the sympathetic bank; the run-time model
uses three partial resonators for each of those keys. `variation_seed` is an
unsigned 32-bit integer.

The fixed array sizes match the real-time model:

- `strings`: 3
- `felt_modes`: 3
- `note_body_lines`: 4
- `body_modes`: 1 to 64
- `fdn_lines`: 8

Field names state their units. Frequencies use hertz; delays, contact times,
and T60 values use seconds; loss rates use per-second values; and tuning uses
cents. Fields ending in `_scale`, levels, gains, and filter mix have no unit.
The schema holds the same numeric bounds as the C code.

## Per-key data

`default_key` gives every key value. `keys` is an object whose names are MIDI
note numbers. Each entry can set one or more values from `default_key`:

```json
"keys": {
  "21": {
    "tuning_cents": -1.2,
    "inharmonicity_b": 0.00017,
    "second_string_level": 0.0,
    "third_string_level": 0.0
  },
  "60": {
    "hammer_contact_min_seconds": 0.00022,
    "hammer_filter_mix": 0.58
  }
}
```

The generator merges each entry over `default_key` and writes a dense C table.
An empty `keys` object uses only `default_key` and emits a null key-table
pointer. The concert grand lists all 88 MIDI keys. Sparse entries do not
cause interpolation; a fitting tool must write any fitted values it needs.

Version 4 stores the string, hammer, damper, and sympathetic bases for each
key:

- `inharmonicity_b` sets the string's base inharmonicity.
- `loss_rate_per_second` and `loss_slope_per_second` set partial decay as
  `lambda_n = loss_rate_per_second + loss_slope_per_second * n * n`.
- `second_string_level`, `third_string_level`, and `unison_width_cents` set
  the choir layout and its base tuning width.
- `hammer_gain`, the two contact-time fields, the two cutoff fields,
  `hammer_filter_mix`, and `hammer_string_gain` set the strike base.
- `hammer_velocity_hardness` adds hardness relative to velocity 0.65 at each
  strike. It changes both contact time and cutoff.
- `bridge_loss_per_second` sets the loss of shared unison motion through the
  bridge. The strings' own loss controls their longer tail.
- `felt_frequency_scale` and `felt_gain` tune the shared three-mode felt
  shape for that key.
- `damper_presence` states whether the key has a damper.
- `damper_closed_t60_seconds` sets the closed-damper decay.
- `damper_lift_start` and `damper_lift_end` set the useful pedal travel for
  that key.
- `sympathetic_open_t60_seconds` sets the open fundamental decay.
- `sympathetic_second_level` and `sympathetic_third_level` set the two upper
  inharmonic partial levels.
- `radiation_scale` and `sympathetic_scale` set direct output level and
  sympathetic drive.

The top-level `mechanics` object scales the short sounds made by the model:

- `key_action_gain` scales key-down and key-release sounds.
- `damper_noise_gain` scales damper landing sounds.
- `pedal_mechanical_gain` scales pedal movement and damper-rail sounds.

These sounds use small built-in filters and noise sources. They do not use
samples. Set a gain to zero to turn off that part.

`body_coupling` has one row per key and one value per shared body mode. Each
value sets how strongly that key's bridge signal drives that mode. The rows
follow MIDI order; the columns follow `body_modes`. The generator requires the
matrix dimensions to match `key_count` and the number of body modes.

The coupling matrix uses a smooth one-dimensional bridge model. Its values are not
measurements. A later body-tap fit can replace the matrix without changing the
opcodes. Key-aware coupling applies to notes
that use a piano handle. The explicit stereo-bus resonance form has no key
identity, so it keeps using the input-side value on each body mode.

Keep fitted rows near unit root-mean-square gain unless the capture supports a
key-level change. Row gain changes the wet body level for that key. A negative
value reverses that mode's drive polarity. The run-time code applies a fixed
`0.60` trim after the matrix to leave headroom for chords.

The shipped modeled rows use this formula. `k` and `m` start at zero:

```text
x = (k + 0.5) / key_count
order = 1 + floor(m / 2)
phase = 0 for even m, pi / 2 for odd m
raw[k,m] = 0.78 + 0.22 * cos(pi * order * x + phase)
body_coupling[k] = raw[k] / rms(raw[k])
```

The opcode controls still act on these bases. For example, `kStiffness`
changes `inharmonicity_b`, `kDecay` scales the two loss terms, `kDetune`
changes `unison_width_cents`, and `kHardness` moves through the contact and
cutoff ranges. Profile data does not change the opcode signatures.

`radiation` holds six increasing `centres_hz`, one `q` from 0.3 to 2, and
`key_gain_db`: one row per key with six gains from -12 to +12 dB. The runtime
designs stable peak EQ filters at the current sample rate. The fit uses broad
bands to shape the direct note signal before its final level limiter. It fits
recorded note spectra, not isolated soundboard modes or bridge impedance.
Room and microphone color can therefore enter these values.

## Source notes

`provenance.method` is `modeled`, `measured`, or `hybrid`. `sources` records the
papers, data sets, audio manifests, or analysis files used for the values. A
source has an `id`, a `kind`, and a title. Its `kind` is `paper`,
`audio_manifest`, `dataset`, or `other`. A source can also hold a stable URI.

Measured and hybrid profiles need an `instrument` with an `id` and the class
`grand`, `upright`, or `other`. Keep the maker, model, serial number, and other
details outside the profile. Use `display_name` for a plain name such as
`Concert Grand A`.

`derived_with` can record the fitting tool, its version or revision, and the
date. These fields track where values came from without fixing how later audio
capture and fitting tools must work.

Use repository paths or stable web links for sources. Do not commit local
`file:` links. Keep raw sound and session notes outside the generated C data.

## Model limits

The three string rows still hold lane details shared by the keyboard, such as
pan, strike error, drift direction, and small loss differences. The three felt
modes hold one shared shape; each key sets its frequency scale and gain. This
keeps the source small and avoids fitting separate felt peaks to string, body,
room, or microphone peaks.

The profile stores sound-model terms, not wire gauge, tension, hammer mass, or
speaking length. Those physical values cannot be split with confidence from
the current recordings. Each key's shared sympathetic bank uses its stored
tuning and damper data. It tracks three inharmonic partials rather than a full
dispersive string.

Body modes and FDN lines can include the room and microphone response if they
come from recorded sound. Keep those details in the source notes so later fits
can tell the piano from the recording setup.

Any change to the compiled profile layout or sound meaning needs a new profile
schema and a matching C schema version. A change to source notes alone does
not need to change the C layout version.

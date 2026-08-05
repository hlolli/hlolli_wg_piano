# Piano profile sources

The JSON files in this directory are the source for the piano tables compiled
into `hlolli_wg_piano.c`. Csound does not read them at run time. This keeps the
native and browser plugins self-contained.

`manifest.json` lists the profile source files. `generic_2018.json` holds the
default profile. `concert_grand_a.json` holds the first small recording-based
fit under a neutral public name. `schema/piano-profile-v1.schema.json` defines
the strict version 1 format.

## Generate the C tables

Run the generator from the repository root:

```sh
python3 tools/generate_profiles.py
```

It needs Python 3.8 or newer and no third-party packages. It also rejects a
generated C source above the browser compiler's 256 KiB limit.

It validates every listed source and replaces only the marked profile-data
block in `hlolli_wg_piano.c`. It does not create an include file because the
browser compiler accepts one plugin C source file.

The script has built-in checks that match the version 1 schema, so it needs no
JSON Schema package. It parses the schema file and checks its version link, but
it does not act as a general JSON Schema engine. Keep the schema and script
rules in step when the format changes.

Check that the source and generated C agree without changing files:

```sh
python3 tools/generate_profiles.py --check
```

The generator uses the manifest order for the public profile list and emits
stable text. Do not edit the generated C block by hand.

## Add a profile

1. Copy `generic_2018.json` to a file named after the new `id`.
2. Set `$schema` to `schema/piano-profile-v1.schema.json`.
3. Add the file to `manifest.json`.
4. Fill in the model data and its source notes.
5. Run the generator and its `--check` form.
6. Render fixed notes, chords, pedal changes, and a stress score before using
   the profile in a demo.

An `id` uses lower-case ASCII letters, digits, and underscores. It starts with
a letter, has at most 63 characters, and matches the source filename. The
`display_name` can hold a normal name for docs and user interfaces.

`midi_min` and `key_count` set one continuous keyboard range. The last key must
not exceed MIDI 127. `sympathetic_mode_count` must be at least two and no more
than `key_count`. `variation_seed` is an unsigned 32-bit integer.

The fixed array sizes match the real-time model:

- `strings`: 3
- `felt_modes`: 3
- `note_body_lines`: 4
- `body_modes`: 1 to 64
- `fdn_lines`: 8

Field names state their units. Frequencies use hertz, delays and T60 values use
seconds, tuning uses cents, and the fields ending in `_scale` have no unit.
The schema holds the same numeric bounds as the C code.

## Per-key data

`default_key` gives all nine key values. `keys` is an object whose names are
MIDI note numbers. Each entry can set one or more values from `default_key`:

```json
"keys": {
  "21": {
    "tuning_cents": -1.2,
    "inharmonicity_scale": 1.08
  },
  "60": {
    "hammer_scale": 0.97
  }
}
```

The generator merges each entry over `default_key` and writes a dense C table.
An empty `keys` object uses only `default_key` and emits a null key-table
pointer. Listing every MIDI key gives full per-key data. Sparse entries do not
cause interpolation; a fitting tool must write any fitted values it needs.

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

## Version 1 limits

Version 1 keeps the current synthesis layout. Its key fields scale curves that
still live in the C model; they do not replace those curves with measured
physical values.

The three string rows and three felt modes apply to every key. The format
cannot yet hold separate bass string counts, gauges, choir layouts, or a felt
spectrum for each key and strike level. The note opcode can apply per-key
stretch tuning, but the shared sympathetic modes still use A440 equal
temperament over the first `sympathetic_mode_count` keys.

Body modes and FDN lines can include the room and microphone response if they
come from recorded sound. Keep those details in the source notes so later fits
can tell the piano from the recording setup.

Any change to the compiled profile layout or sound meaning needs a new profile
schema and a matching C schema version. A change to source notes alone does not
need to change the C layout version.

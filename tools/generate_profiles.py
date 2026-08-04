#!/usr/bin/env python3
"""Validate piano profiles and update their marked C data block."""

import argparse
import json
import math
import os
import re
import stat
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path


SCHEMA_VERSION = 1
MIN_PYTHON = (3, 8)
MAX_WASI_SOURCE_BYTES = 256 * 1024
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "profiles" / "manifest.json"
SCHEMA_PATH = ROOT / "profiles" / "schema" / "piano-profile-v1.schema.json"
SOURCE_PATH = ROOT / "hlolli_wg_piano.c"
PROFILE_SCHEMA_REF = "schema/piano-profile-v1.schema.json"
BEGIN_MARKER = "/* BEGIN GENERATED PIANO PROFILE DATA */"
END_MARKER = "/* END GENERATED PIANO PROFILE DATA */"
PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
RFC3339_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt]"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
    r"(?:[Zz]|[+-][0-9]{2}:[0-9]{2})$"
)

KEY_FIELDS = (
    "tuning_cents",
    "inharmonicity_scale",
    "string_length_scale",
    "string_loss_scale",
    "unison_detune_scale",
    "hammer_scale",
    "damper_scale",
    "radiation_scale",
    "sympathetic_scale",
)
STRING_FIELDS = (
    "strike_seconds",
    "strike_error_depth",
    "detune_spread",
    "drift_sign",
    "loss_scale",
    "pan",
)
FELT_MODE_FIELDS = ("frequency_hz", "t60_seconds", "weight")
NOTE_BODY_LINE_FIELDS = ("delay_seconds", "injection")
BODY_MODE_FIELDS = (
    "frequency_hz",
    "t60_seconds",
    "gain",
    "input_side",
    "stereo_position",
)
FDN_LINE_FIELDS = (
    "delay_seconds",
    "input_side",
    "injection",
    "tone_scale",
)


class ProfileError(ValueError):
    """A clear input or generated-source error."""


def decimal(text):
    return Decimal(text)


def reject_constant(value):
    raise ProfileError("non-finite JSON number {!r}".format(value))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError("duplicate JSON key {!r}".format(key))
        result[key] = value
    return result


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(
                stream,
                parse_float=Decimal,
                parse_int=int,
                parse_constant=reject_constant,
                object_pairs_hook=unique_object,
            )
    except OSError as error:
        raise ProfileError("{}: {}".format(path, error)) from error
    except json.JSONDecodeError as error:
        raise ProfileError("{}: {}".format(path, error)) from error


def require_object(value, path, required, optional=()):
    if type(value) is not dict:
        raise ProfileError("{} must be an object".format(path))
    required = set(required)
    allowed = required | set(optional)
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        raise ProfileError(
            "{} lacks required field(s): {}".format(path, ", ".join(missing))
        )
    if unknown:
        raise ProfileError(
            "{} has unknown field(s): {}".format(path, ", ".join(unknown))
        )
    return value


def require_array(value, path, minimum=None, maximum=None, exact=None):
    if type(value) is not list:
        raise ProfileError("{} must be an array".format(path))
    count = len(value)
    if exact is not None and count != exact:
        raise ProfileError("{} must contain {} items".format(path, exact))
    if minimum is not None and count < minimum:
        raise ProfileError(
            "{} must contain at least {} items".format(path, minimum)
        )
    if maximum is not None and count > maximum:
        raise ProfileError(
            "{} must contain at most {} items".format(path, maximum)
        )
    return value


def require_string(value, path, maximum=None):
    if type(value) is not str or not value:
        raise ProfileError("{} must be a nonempty string".format(path))
    if maximum is not None and len(value) > maximum:
        raise ProfileError(
            "{} must contain at most {} characters".format(path, maximum)
        )
    return value


def require_enum(value, path, choices):
    value = require_string(value, path)
    if value not in choices:
        raise ProfileError(
            "{} must be one of {}".format(path, ", ".join(choices))
        )
    return value


def require_integer(value, path, low, high):
    if type(value) is not int:
        raise ProfileError("{} must be an integer".format(path))
    if value < low or value > high:
        raise ProfileError(
            "{} must be in the range {}..{}".format(path, low, high)
        )
    return value


def require_number(value, path, low, high, low_open=False):
    if type(value) is int:
        value = Decimal(value)
    elif type(value) is not Decimal:
        raise ProfileError("{} must be a number".format(path))
    if not value.is_finite():
        raise ProfileError("{} must be finite".format(path))
    c_value = float(value)
    if not math.isfinite(c_value) or (value != 0 and c_value == 0.0):
        raise ProfileError("{} cannot be represented as a C double".format(path))
    below = value <= low if low_open else value < low
    if below or value > high:
        left = "(" if low_open else "["
        raise ProfileError(
            "{} must be in {}{}, {}]".format(path, left, low, high)
        )
    return value


KEY_LIMITS = {
    "tuning_cents": (decimal("-1200"), decimal("1200"), False),
    "inharmonicity_scale": (decimal("0.01"), decimal("100"), False),
    "string_length_scale": (decimal("0.01"), decimal("100"), False),
    "string_loss_scale": (decimal("0.01"), decimal("100"), False),
    "unison_detune_scale": (decimal("0"), decimal("100"), False),
    "hammer_scale": (decimal("0"), decimal("100"), False),
    "damper_scale": (decimal("0.01"), decimal("100"), False),
    "radiation_scale": (decimal("0"), decimal("100"), False),
    "sympathetic_scale": (decimal("0"), decimal("100"), False),
}
STRING_LIMITS = {
    "strike_seconds": (decimal("0"), decimal("0.04"), False),
    "strike_error_depth": (decimal("0"), decimal("100"), False),
    "detune_spread": (decimal("-100"), decimal("100"), False),
    "drift_sign": (decimal("-100"), decimal("100"), False),
    "loss_scale": (decimal("0.01"), decimal("100"), False),
    "pan": (decimal("-1"), decimal("1"), False),
}
FELT_MODE_LIMITS = {
    "frequency_hz": (decimal("0"), decimal("100000"), True),
    "t60_seconds": (decimal("0"), decimal("120"), True),
    "weight": (decimal("-100"), decimal("100"), False),
}
NOTE_BODY_LINE_LIMITS = {
    "delay_seconds": (decimal("0"), decimal("2"), True),
    "injection": (decimal("-100"), decimal("100"), False),
}
BODY_MODE_LIMITS = {
    "frequency_hz": (decimal("0"), decimal("100000"), True),
    "t60_seconds": (decimal("0"), decimal("120"), True),
    "gain": (decimal("-100"), decimal("100"), False),
    "input_side": (decimal("-100"), decimal("100"), False),
    "stereo_position": (decimal("-1"), decimal("1"), False),
}
FDN_LINE_LIMITS = {
    "delay_seconds": (decimal("0"), decimal("2"), True),
    "input_side": (decimal("-100"), decimal("100"), False),
    "injection": (decimal("-100"), decimal("100"), False),
    "tone_scale": (decimal("0.01"), decimal("100"), False),
}


def validate_number_object(value, path, fields, limits):
    value = require_object(value, path, fields)
    result = {}
    for field in fields:
        low, high, low_open = limits[field]
        result[field] = require_number(
            value[field], "{}.{}".format(path, field), low, high, low_open
        )
    return result


def validate_number_array(value, path, fields, limits, exact=None,
                          minimum=None, maximum=None):
    values = require_array(value, path, minimum, maximum, exact)
    return [
        validate_number_object(item, "{}[{}]".format(path, index), fields, limits)
        for index, item in enumerate(values)
    ]


def validate_sparse_keys(value, path, default_key, midi_min, key_count):
    if type(value) is not dict:
        raise ProfileError("{} must be an object".format(path))
    values = value
    if len(values) > key_count:
        raise ProfileError(
            "{} must contain at most {} entries".format(path, key_count)
        )
    if not values:
        return None

    dense = [dict(default_key) for _ in range(key_count)]
    for midi_text, item in values.items():
        item_path = '{}["{}"]'.format(path, midi_text)
        if re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", midi_text) is None:
            raise ProfileError("{} has an invalid MIDI key".format(item_path))
        midi = int(midi_text, 10)
        if midi < midi_min or midi >= midi_min + key_count:
            raise ProfileError("{} lies outside the profile MIDI range".format(item_path))
        item = require_object(item, item_path, (), KEY_FIELDS)
        if not item:
            raise ProfileError("{} must override at least one field".format(item_path))
        target = dense[midi - midi_min]
        for field in KEY_FIELDS:
            if field in item:
                low, high, low_open = KEY_LIMITS[field]
                target[field] = require_number(
                    item[field], "{}.{}".format(item_path, field),
                    low, high, low_open
                )
    return dense


PROFILE_FIELDS = (
    "$schema",
    "schema_version",
    "id",
    "display_name",
    "midi_min",
    "key_count",
    "sympathetic_mode_count",
    "variation_seed",
    "default_key",
    "keys",
    "strings",
    "felt_modes",
    "note_body_lines",
    "body_modes",
    "fdn_lines",
    "provenance",
)


def validate_sha256(value, path):
    value = require_string(value, path)
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ProfileError("{} must be a lower-case SHA-256".format(path))


def validate_provenance(value, path):
    value = require_object(
        value, path, ("method", "sources"),
        ("instrument", "derived_with", "notes")
    )
    require_enum(
        value["method"], "{}.method".format(path),
        ("modeled", "measured", "hybrid")
    )

    sources = require_array(value["sources"], "{}.sources".format(path), minimum=1)
    source_ids = set()
    for index, source in enumerate(sources):
        source_path = "{}.sources[{}]".format(path, index)
        source = require_object(
            source, source_path, ("id", "kind", "title", "license"),
            ("uri", "sha256")
        )
        source_id = require_string(source["id"], "{}.id".format(source_path))
        if PROFILE_ID_RE.fullmatch(source_id) is None:
            raise ProfileError(
                "{}.id must match {}".format(source_path, PROFILE_ID_RE.pattern)
            )
        if source_id in source_ids:
            raise ProfileError("{} repeats source id {!r}".format(path, source_id))
        source_ids.add(source_id)
        require_enum(
            source["kind"], "{}.kind".format(source_path),
            ("paper", "audio_manifest", "dataset", "other")
        )
        require_string(source["title"], "{}.title".format(source_path), 512)
        require_string(source["license"], "{}.license".format(source_path), 512)
        if "uri" in source:
            uri = require_string(
                source["uri"], "{}.uri".format(source_path), 2048
            )
            if uri.lower().startswith("file:"):
                raise ProfileError(
                    "{}.uri must not use a local file URI".format(source_path)
                )
        if "sha256" in source:
            validate_sha256(source["sha256"], "{}.sha256".format(source_path))

    if "instrument" in value:
        instrument_path = "{}.instrument".format(path)
        instrument = require_object(
            value["instrument"], instrument_path, ("maker", "model"),
            ("serial_number", "year")
        )
        require_string(instrument["maker"], "{}.maker".format(instrument_path), 127)
        require_string(instrument["model"], "{}.model".format(instrument_path), 127)
        if "serial_number" in instrument:
            require_string(
                instrument["serial_number"],
                "{}.serial_number".format(instrument_path), 127
            )
        if "year" in instrument:
            require_integer(instrument["year"], "{}.year".format(instrument_path), 0, 9999)

    if "derived_with" in value:
        derived_path = "{}.derived_with".format(path)
        derived = require_object(
            value["derived_with"], derived_path, ("tool",),
            ("tool_version", "tool_revision", "parameters_sha256", "created_utc")
        )
        require_string(derived["tool"], "{}.tool".format(derived_path), 255)
        for field in ("tool_version", "tool_revision"):
            if field in derived:
                require_string(derived[field], "{}.{}".format(derived_path, field), 127)
        if "parameters_sha256" in derived:
            validate_sha256(
                derived["parameters_sha256"],
                "{}.parameters_sha256".format(derived_path)
            )
        if "created_utc" in derived:
            created = require_string(
                derived["created_utc"], "{}.created_utc".format(derived_path)
            )
            if RFC3339_RE.fullmatch(created) is None:
                raise ProfileError(
                    "{}.created_utc must use RFC 3339 date-time syntax".format(
                        derived_path
                    )
                )
            normalized = (
                created[:-1] + "+00:00"
                if created.endswith(("Z", "z"))
                else created
            )
            try:
                parsed = datetime.fromisoformat(normalized)
            except ValueError as error:
                raise ProfileError(
                    "{}.created_utc is not a valid date-time".format(derived_path)
                ) from error
            if parsed.tzinfo is None:
                raise ProfileError(
                    "{}.created_utc must include a UTC offset".format(derived_path)
                )

    if "notes" in value:
        require_string(value["notes"], "{}.notes".format(path), 4096)


def validate_profile(value, path):
    value = require_object(value, path, PROFILE_FIELDS)
    schema_ref = require_string(value["$schema"], "{}.$schema".format(path))
    if schema_ref != PROFILE_SCHEMA_REF:
        raise ProfileError(
            "{}.$schema must name {}".format(path, PROFILE_SCHEMA_REF)
        )
    schema_version = require_integer(
        value["schema_version"], "{}.schema_version".format(path),
        SCHEMA_VERSION, SCHEMA_VERSION
    )
    profile_id = require_string(value["id"], "{}.id".format(path))
    if PROFILE_ID_RE.fullmatch(profile_id) is None:
        raise ProfileError(
            "{}.id must match {}".format(path, PROFILE_ID_RE.pattern)
        )
    require_string(value["display_name"], "{}.display_name".format(path), 127)
    midi_min = require_integer(value["midi_min"], "{}.midi_min".format(path), 0, 127)
    key_count = require_integer(value["key_count"], "{}.key_count".format(path), 1, 97)
    if midi_min + key_count - 1 > 127:
        raise ProfileError("{} MIDI range ends above 127".format(path))
    sympathetic_mode_count = require_integer(
        value["sympathetic_mode_count"],
        "{}.sympathetic_mode_count".format(path), 2, key_count
    )
    variation_seed = require_integer(
        value["variation_seed"], "{}.variation_seed".format(path),
        0, 0xFFFFFFFF
    )
    default_key = validate_number_object(
        value["default_key"], "{}.default_key".format(path),
        KEY_FIELDS, KEY_LIMITS
    )
    keys = validate_sparse_keys(
        value["keys"], "{}.keys".format(path), default_key, midi_min, key_count
    )
    validate_provenance(value["provenance"], "{}.provenance".format(path))

    return {
        "schema_version": schema_version,
        "id": profile_id,
        "midi_min": midi_min,
        "key_count": key_count,
        "sympathetic_mode_count": sympathetic_mode_count,
        "variation_seed": variation_seed,
        "default_key": default_key,
        "keys": keys,
        "strings": validate_number_array(
            value["strings"], "{}.strings".format(path),
            STRING_FIELDS, STRING_LIMITS, exact=3
        ),
        "felt_modes": validate_number_array(
            value["felt_modes"], "{}.felt_modes".format(path),
            FELT_MODE_FIELDS, FELT_MODE_LIMITS, exact=3
        ),
        "note_body_lines": validate_number_array(
            value["note_body_lines"], "{}.note_body_lines".format(path),
            NOTE_BODY_LINE_FIELDS, NOTE_BODY_LINE_LIMITS, exact=4
        ),
        "body_modes": validate_number_array(
            value["body_modes"], "{}.body_modes".format(path),
            BODY_MODE_FIELDS, BODY_MODE_LIMITS, minimum=1, maximum=64
        ),
        "fdn_lines": validate_number_array(
            value["fdn_lines"], "{}.fdn_lines".format(path),
            FDN_LINE_FIELDS, FDN_LINE_LIMITS, exact=8
        ),
    }


def load_profiles():
    schema = load_json(SCHEMA_PATH)
    if type(schema) is not dict:
        raise ProfileError("{} must contain a JSON object".format(SCHEMA_PATH))
    try:
        schema_ref = schema["properties"]["$schema"]["const"]
        schema_version = schema["properties"]["schema_version"]["const"]
    except (KeyError, TypeError) as error:
        raise ProfileError(
            "{} does not define its profile reference and version".format(
                SCHEMA_PATH
            )
        ) from error
    if schema_ref != PROFILE_SCHEMA_REF:
        raise ProfileError(
            "{} does not use profile reference {}".format(
                SCHEMA_PATH, PROFILE_SCHEMA_REF
            )
        )
    if schema_version != SCHEMA_VERSION:
        raise ProfileError(
            "{} does not describe schema version {}".format(
                SCHEMA_PATH, SCHEMA_VERSION
            )
        )

    manifest = require_object(
        load_json(MANIFEST_PATH), "manifest",
        ("schema_version", "default_profile", "profiles")
    )
    require_integer(
        manifest["schema_version"], "manifest.schema_version",
        SCHEMA_VERSION, SCHEMA_VERSION
    )
    default_profile = require_string(
        manifest["default_profile"], "manifest.default_profile"
    )
    names = require_array(manifest["profiles"], "manifest.profiles", minimum=1)

    profiles = []
    seen_files = set()
    seen_ids = set()
    for index, name in enumerate(names):
        name = require_string(name, "manifest.profiles[{}]".format(index))
        profile_path = Path(name)
        if profile_path.name != name or profile_path.suffix != ".json":
            raise ProfileError(
                "manifest.profiles[{}] must be a JSON filename".format(index)
            )
        if name == MANIFEST_PATH.name:
            raise ProfileError("manifest cannot list itself as a profile")
        if name in seen_files:
            raise ProfileError("manifest repeats profile file {!r}".format(name))
        seen_files.add(name)
        profile = validate_profile(
            load_json(MANIFEST_PATH.parent / profile_path), name
        )
        if profile["id"] in seen_ids:
            raise ProfileError(
                "duplicate profile id {!r}".format(profile["id"])
            )
        seen_ids.add(profile["id"])
        if profile_path.stem != profile["id"]:
            raise ProfileError(
                "profile id {!r} must match filename {!r}".format(
                    profile["id"], profile_path.name
                )
            )
        profiles.append(profile)

    if default_profile not in seen_ids:
        raise ProfileError(
            "manifest.default_profile {!r} is not listed".format(default_profile)
        )
    return profiles, default_profile


def c_float(value):
    return repr(float(value))


def c_row(item, fields):
    return "{" + ", ".join(c_float(item[field]) for field in fields) + "}"


def append_rows(lines, rows, fields, indent):
    for row in rows:
        lines.append("{}{},".format(indent, c_row(row, fields)))


def generate_profile(lines, profile):
    symbol = "wg_{}".format(profile["id"])
    if profile["keys"] is not None:
        lines.append("static const WG_KEY_PROFILE {}_keys[] = {{".format(symbol))
        append_rows(lines, profile["keys"], KEY_FIELDS, "    ")
        lines.append("};")
        lines.append("")

    lines.append(
        "static const WG_BODY_MODE_PROFILE {}_body_modes[] = {{".format(symbol)
    )
    append_rows(lines, profile["body_modes"], BODY_MODE_FIELDS, "    ")
    lines.append("};")
    lines.append("")

    lines.append("static const WG_PIANO_PROFILE wg_profile_{} = {{".format(profile["id"]))
    lines.append('    .id = "{}",'.format(profile["id"]))
    lines.append("    .schema_version = WG_PROFILE_SCHEMA_VERSION,")
    lines.append("    .midi_min = {},".format(profile["midi_min"]))
    lines.append("    .key_count = {}U,".format(profile["key_count"]))
    lines.append(
        "    .sympathetic_mode_count = {}U,".format(
            profile["sympathetic_mode_count"]
        )
    )
    lines.append("    .body_mode_count = {}U,".format(len(profile["body_modes"])))
    lines.append("    .fdn_line_count = RESONANCE_BODY_LINES,")
    lines.append("    .variation_seed = {}U,".format(profile["variation_seed"]))
    lines.append(
        "    .default_key = {},".format(c_row(profile["default_key"], KEY_FIELDS))
    )
    if profile["keys"] is None:
        lines.append("    .keys = NULL,")
    else:
        lines.append("    .keys = {}_keys,".format(symbol))
    lines.append("    .strings = {")
    append_rows(lines, profile["strings"], STRING_FIELDS, "        ")
    lines.append("    },")
    lines.append("    .felt_modes = {")
    append_rows(lines, profile["felt_modes"], FELT_MODE_FIELDS, "        ")
    lines.append("    },")
    lines.append("    .note_body_lines = {")
    append_rows(
        lines, profile["note_body_lines"], NOTE_BODY_LINE_FIELDS, "        "
    )
    lines.append("    },")
    lines.append("    .body_modes = {}_body_modes,".format(symbol))
    lines.append("    .fdn_lines = {")
    append_rows(lines, profile["fdn_lines"], FDN_LINE_FIELDS, "        ")
    lines.append("    },")
    lines.append("};")


def generate_block(profiles, default_profile):
    lines = [
        BEGIN_MARKER,
        "/* Generated piano profile data. Do not edit by hand. */",
    ]
    for profile in profiles:
        lines.append("")
        generate_profile(lines, profile)

    lines.extend(("", "static const WG_PIANO_PROFILE *const wg_piano_profiles[] = {"))
    for profile in profiles:
        lines.append("    &wg_profile_{},".format(profile["id"]))
    lines.append("};")
    lines.append("")
    lines.append("static const WG_PIANO_PROFILE *const wg_default_piano_profile =")
    lines.append("    &wg_profile_{};".format(default_profile))
    lines.append(END_MARKER)
    return "\n".join(lines)


def replace_generated_block(source, block):
    if source.count(BEGIN_MARKER) != 1 or source.count(END_MARKER) != 1:
        raise ProfileError("C source must contain one generated profile block")
    begin = source.index(BEGIN_MARKER)
    end_marker = source.index(END_MARKER)
    if end_marker < begin:
        raise ProfileError("C source has reversed generated profile markers")
    end = end_marker + len(END_MARKER)
    return source[:begin] + block + source[end:]


def write_atomic(path, text):
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".{}-".format(path.name), text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check", action="store_true",
        help="fail if the marked C data block is stale"
    )
    actions.add_argument(
        "--stdout", action="store_true",
        help="print the marked C data block without changing the source"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if sys.version_info < MIN_PYTHON:
        print(
            "profile generation failed: Python {}.{} or newer is required".format(
                *MIN_PYTHON
            ),
            file=sys.stderr,
        )
        return 2
    try:
        profiles, default_profile = load_profiles()
        block = generate_block(profiles, default_profile)
        if args.stdout:
            sys.stdout.write(block + "\n")
            return 0

        try:
            source = SOURCE_PATH.read_text(encoding="utf-8")
        except OSError as error:
            raise ProfileError("{}: {}".format(SOURCE_PATH, error)) from error
        updated = replace_generated_block(source, block)
        source_bytes = len(updated.encode("utf-8"))
        if source_bytes > MAX_WASI_SOURCE_BYTES:
            raise ProfileError(
                "generated C source is {} bytes; the WASI limit is {}".format(
                    source_bytes, MAX_WASI_SOURCE_BYTES
                )
            )
        if args.check:
            if updated != source:
                print(
                    "{} has stale generated piano profile data".format(
                        SOURCE_PATH.name
                    ),
                    file=sys.stderr,
                )
                return 1
            return 0
        if updated != source:
            write_atomic(SOURCE_PATH, updated)
        return 0
    except ProfileError as error:
        print("profile generation failed: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

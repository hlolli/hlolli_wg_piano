# Piano capture guide

This guide gives a small, repeatable recording set for fitting piano profiles.
Use recordings we made or may analyse. Keep raw audio out of Git. The project
ships only fitted numbers in the generated C file.

Use a generic public ID such as `concert_grand_a` and a class such as `grand`.
Keep the maker, model, serial number, names, and exact place in local notes when
needed.

## Fix one setup

Use one piano, room, lid state, and microphone setup per session. Tune the piano
before the session and let it settle. Keep the doors, curtains, heating, music
desk, gains, and microphone positions fixed.

Note the room size, temperature, humidity, lid state, pitch standard, tuning
time, channel order, and all gain settings. Photograph each microphone and
sensor position with a ruler in view.

Set the origin on the floor below the centre of the front edge of middle C. Use
metres and these axes:

- `+x`: toward the treble end;
- `+y`: away from the player;
- `+z`: up from the floor.

## Record fixed channels

Use one interface and clock. A useful set has:

- bass, middle, and treble close microphones for the attack and string decay;
- one soundboard microphone or safe contact sensor for body modes;
- one fixed stereo pair for the whole piano;
- an optional room pair for the late tail;
- a hammer-speed sensor and pedal-position sensor on spare channels;
- a force sensor for body taps.

Record one aligned multichannel file per take. Do not move microphones, change
gain, sum channels, or add EQ, compression, limiting, noise removal, or sample
rate conversion.

## File format and levels

Record 96 kHz, 24-bit linear PCM WAV or BWF. Before the note set:

1. Record a level reference and a polarity pulse.
2. Set gain so the loudest safe strike stays below `-12 dBFS`.
3. Record at least 60 seconds of room noise.
4. Lock the gain and turn off recorder processing.

Repeat the level reference and room noise at the end.

## Measure the attack

MIDI velocity is a command, not a hammer-speed measure. Use a safe optical
sensor or a high-speed camera to measure hammer speed just before contact. If
only key speed is known, call it key speed.

Use seven speed bins from the quietest clear strike to the loudest safe strike.
Set the bins from a short pilot on that piano. Put more bins near the soft end.

## Note and decay set

Start with MIDI notes `21, 36, 48, 60, 72, 84, 96, 108` at all seven speed
bins and three repeats. Use the pilot to check headroom, noise, timing, channel
order, pedal readings, and safe speed limits.

For a full robot set, record all 88 keys at seven speeds and five repeats. For
a smaller played set, record:

- all 88 keys at soft, middle, and hard measured speeds;
- seven speeds on notes `21, 27, 33, 39, 45, 51, 57, 63, 69, 75, 81, 87,
  93, 99, 105, 108`;
- keys on both sides of each string-count, bridge, and capo break.

For each take, allow two seconds before the strike. Hold the key for five
seconds, then leave at least three seconds after release. Add middle-speed long
decays for every key: about 45 seconds below C3, 30 seconds from C3 to B5, and
15 seconds above C6, or until the sound reaches the room floor.

When a technician approves it, record a few isolated strings and the full
two- or three-string group at the same speed. These takes help fit detune and
loss.

## Pedals and sympathetic strings

For each anchor note, record:

- fast, middle, and slow key releases;
- sustain up, half, and full;
- sustain pressed before and after the strike;
- fast, middle, and slow sustain release;
- una corda up, half, and full;
- silent key and pedal presses.

Measure damper lift when possible. Pedal travel alone does not map well between
pianos.

For sympathetic response, hold a target damper open without sounding its key.
Excite the target with a short sine burst near one of its partials, stop the
burst, and record the free decay. Pair it with the same burst and the damper
down. Also record low, middle, and high chords with sustain down.

## Body and room

Only a piano technician should run body tests. Use a soft force hammer at six
or more marked bridge and soundboard points. Record several safe taps with
dampers down and sustain down. Capture the force and audio channels together.

Without moving the piano or microphones, place a measured speaker near the
piano and record three 20 to 30 second logarithmic sweeps plus the speaker
loopback. These takes help keep the piano body response apart from the room
tail.

## Capture file

[The small example](example-capture.json) lists the public piano ID, sample
format, channel roles, and take facts needed by a fitting tool. Paths are
relative to the capture file. The fitting tool can read file length and other
WAV header data on its own.

Use names that show the set, note, speed bin, pedal state, and repeat, for
example:

```text
concert_grand_a_s01_note_n060_v04_sus00_r03.wav
```

Keep raw files under an ignored local folder such as:

```text
recordings/raw/concert_grand_a/session_01/audio/
```

## Accept or repeat

Accept a take only when:

- the file, channel map, note, pedals, and sensors agree;
- all channels stay in sync and have no dropped samples;
- the strike falls within the session speed range;
- the attack is clear above the room noise;
- the decay reaches the room floor when required;
- no voice, step, chair, traffic, or heating noise masks the useful sound;
- the tuning and end level still match the start of the session.

Repeat a bad take. Do not repair the raw file.

## Safety

- Ask the owner and technician before adding mutes, sensors, an action drive,
  or an impact hammer.
- Do not tape or glue anything to the finish, strings, bridge, or soundboard.
- Set safe force and travel limits on a robot and test its stop control.
- Keep hands out of the action and keep cables clear of walking paths.
- Do not use web audio, mastered songs, lossy files, or samples with unknown
  gain, strike, or pedal state as measurement data.

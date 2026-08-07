<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_SNAPSHOT_TIME
#define TEST_SNAPSHOT_TIME #0.5#
#endif

sr = 48000
ksmps = 32
nchnls = 4
0dbfs = 1

giPiano hlolli_wg_piano_create

instr OldNote
  xtratim 2.8
  kRelease release
  kTrigger = (kRelease == 0 ? 0.75 : 0)
  kFrequency init cpsmidinn(60)
  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, 0.43, 0.12, 0.90, \
      0.42, 0.60, 0.72, 0, 0.82, giPiano
  outch 1, aLeft, 2, aRight
endin

instr QuietHeld
  kFrequency init cpsmidinn(60)
  aLeft, aRight hlolli_wg_piano \
      0.00011, kFrequency, 0.43, 0.12, 0.90, \
      0.42, 0.60, 0.72, 0, 0.82, giPiano
endin

; This zero-length note refreshes the held-key snapshot without adding audio.
instr SnapshotTouch
  kFrequency init cpsmidinn(67)
  aLeft, aRight hlolli_wg_piano \
      0.00011, kFrequency, 0.43, 0.12, 0.90, \
      0.42, 0.60, 0.72, 0, 0.82, giPiano
endin

instr Renderer
  aLeft, aRight hlolli_wg_piano_resonance giPiano, 0.72, 0
  outch 3, aLeft, 4, aRight
endin

instr ScheduleTest
  event_i "i", "Renderer", 0, 0.10
  event_i "i", "OldNote", 0.15, 0.10
  event_i "i", "QuietHeld", 0.5, 2.5
  event_i "i", "SnapshotTouch", $TEST_SNAPSHOT_TIME, 0
  event_i "i", "Renderer", 1.0, 2.0
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.01
e 3
</CsScore>
</CsoundSynthesizer>

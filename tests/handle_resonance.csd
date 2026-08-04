<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_A_VELOCITY
#define TEST_A_VELOCITY #0.72#
#endif
#ifndef TEST_B_VELOCITY
#define TEST_B_VELOCITY #0#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giPianoA hlolli_wg_piano_create
giPianoB hlolli_wg_piano_create "generic_2018"

instr PianoNote
  iPiano = p4
  iVelocity = p5
  iNote = p6
  xtratim 1.20
  kRelease release
  kTrigger = (kRelease == 0 ? iVelocity : 0)
  kFrequency init cpsmidinn(iNote)
  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, 0.43, 0.12, 0.72, \
      0.42, 0.60, 0.72, 0, 0.82, iPiano
endin

instr PianoOutputs
  aWetALeft, aWetARight hlolli_wg_piano_resonance \
      giPianoA, 0.72, 0.82
  aWetBLeft, aWetBRight hlolli_wg_piano_resonance \
      giPianoB, 0.72, 0.82
  outs 0.5 * (aWetALeft + aWetARight), \
       0.5 * (aWetBLeft + aWetBRight)
endin

instr ScheduleNotes
  event_i "i", "PianoNote", 0, 0.20, giPianoA, $TEST_A_VELOCITY, 60
  event_i "i", "PianoNote", 0, 0.20, giPianoB, $TEST_B_VELOCITY, 67
endin

</CsInstruments>
<CsScore>
i "ScheduleNotes" 0 0.01
i "PianoOutputs" 0 4
e
</CsScore>
</CsoundSynthesizer>

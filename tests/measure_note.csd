<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_SR
#define TEST_SR #48000#
#endif
#ifndef TEST_KSMPS
#define TEST_KSMPS #32#
#endif
#ifndef TEST_NOTE
#define TEST_NOTE #60#
#endif
#ifndef TEST_VELOCITY
#define TEST_VELOCITY #0.65#
#endif
#ifndef TEST_KEY_SECONDS
#define TEST_KEY_SECONDS #0.35#
#endif
#ifndef TEST_TAIL_SECONDS
#define TEST_TAIL_SECONDS #7.0#
#endif
#ifndef TEST_HARDNESS
#define TEST_HARDNESS #0.43#
#endif
#ifndef TEST_POSITION
#define TEST_POSITION #0.12#
#endif
#ifndef TEST_DECAY
#define TEST_DECAY #0.70#
#endif
#ifndef TEST_STIFFNESS
#define TEST_STIFFNESS #0.42#
#endif
#ifndef TEST_DETUNE
#define TEST_DETUNE #0.60#
#endif
#ifndef TEST_BODY
#define TEST_BODY #0.72#
#endif
#ifndef TEST_STRANGE
#define TEST_STRANGE #0.0#
#endif
#ifndef TEST_PEDAL
#define TEST_PEDAL #0.0#
#endif

sr = $TEST_SR
ksmps = $TEST_KSMPS
nchnls = 2
0dbfs = 1

giPiano hlolli_wg_piano_create

instr MeasureNote
  iNote = p4
  iVelocity = p5

  xtratim $TEST_TAIL_SECONDS
  kRelease release
  kTrigger = (kRelease == 0 ? iVelocity : 0)
  kFrequency init cpsmidinn(iNote)

  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, $TEST_HARDNESS, $TEST_POSITION, \
      $TEST_DECAY, $TEST_STIFFNESS, $TEST_DETUNE, $TEST_BODY, \
      $TEST_STRANGE, $TEST_PEDAL, giPiano

  ; The fade only closes the file cleanly. Metric windows must end before it.
  kClose linsegr 1, $TEST_TAIL_SECONDS - 0.02, 1, 0.02, 0
  outs aLeft * kClose, aRight * kClose
endin

instr MeasureResonance
  aLeft, aRight hlolli_wg_piano_resonance \
      giPiano, $TEST_BODY, $TEST_PEDAL
  outs aLeft, aRight
endin

instr ScheduleMeasure
  event_i "i", "MeasureResonance", 0, \
      $TEST_KEY_SECONDS + $TEST_TAIL_SECONDS
  event_i "i", "MeasureNote", 0, $TEST_KEY_SECONDS, $TEST_NOTE, \
      $TEST_VELOCITY
endin

</CsInstruments>
<CsScore>
i "ScheduleMeasure" 0 0.01
e
</CsScore>
</CsoundSynthesizer>

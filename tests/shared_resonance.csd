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
#ifndef TEST_BODY
#define TEST_BODY #0.72#
#endif
#ifndef TEST_PEDAL
#define TEST_PEDAL #0.82#
#endif
#ifndef TEST_KEEP_SOURCE
#define TEST_KEEP_SOURCE #0#
#endif
#ifndef TEST_SPLIT_OUTPUT
#define TEST_SPLIT_OUTPUT #0#
#endif
#ifndef TEST_CONTROL_MOTION
#define TEST_CONTROL_MOTION #0#
#endif

sr = $TEST_SR
ksmps = $TEST_KSMPS
nchnls = 2
0dbfs = 1

gaResonanceInputLeft init 0
gaResonanceInputRight init 0
gkResonanceBody init $TEST_BODY
gkResonancePedal init $TEST_PEDAL

; This source emits one deterministic sample. TEST_KEEP_SOURCE changes only
; its lifetime, so the two renders must have the same shared tail.
instr Exciter
  aPulse mpulse p4, 0
  gaResonanceInputLeft += aPulse
  gaResonanceInputRight += p5 * aPulse
endin

instr ScheduleExciters
  iLifetime = ($TEST_KEEP_SOURCE == 0 ? 0.05 : 0.75)
  event_i "i", "Exciter", 0, iLifetime, 0.72, 0.35
  event_i "i", "Exciter", 1.25, iLifetime, 0.51, -0.28
endin

instr SharedControls
  if $TEST_CONTROL_MOTION != 0 then
    gkResonanceBody linseg 0.20, 2.70, 0.92, 1.30, 0.35
    gkResonancePedal linseg 0.10, 1.10, 0.90, 1.40, 0.30, 1.50, 0.80
  else
    gkResonanceBody = $TEST_BODY
    gkResonancePedal = $TEST_PEDAL
  endif
endin

; This instrument, rather than either source, owns all resonance state.
instr SharedResonance
  aWetLeft, aWetRight hlolli_wg_piano_resonance \
      gaResonanceInputLeft, gaResonanceInputRight, \
      gkResonanceBody, gkResonancePedal
  outs aWetLeft, aWetRight
  clear gaResonanceInputLeft, gaResonanceInputRight
endin

instr ScheduleResonance
  event_i "i", "SharedControls", 0, 4
  if $TEST_SPLIT_OUTPUT == 0 then
    event_i "i", "SharedResonance", 0, 4
  else
    event_i "i", "SharedResonance", 0, 1.500125
    event_i "i", "SharedResonance", 1.500125, 2.499875
  endif
endin

</CsInstruments>
<CsScore>
i "ScheduleExciters" 0 0.01
i "ScheduleResonance" 0 0.01
e
</CsScore>
</CsoundSynthesizer>

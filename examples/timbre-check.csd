<CsoundSynthesizer>
<CsOptions>
-odac -d -m128
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

; Hear the instrument itself: no added room reverb, EQ, or mono fold-down.
giPiano hlolli_wg_piano_create

instr Piano
  kRelease release
  kTrigger = (kRelease == 0 ? p5 : 0)
  aLeft, aRight hlolli_wg_piano \
      kTrigger, cpsmidinn(p4), 0.43, 0.12, 0.70, \
      0.42, 0.60, 0.72, 0, 0, giPiano
  outs 0.70 * aLeft, 0.70 * aRight
endin

instr Body
  aLeft, aRight hlolli_wg_piano_resonance giPiano, 0.72, 0
  outs 0.36 * aLeft, 0.36 * aRight
endin
</CsInstruments>
<CsScore>
i "Body" 0 9.5
i "Piano" 0.10 2.0 48 0.65
i "Piano" 3.20 2.0 60 0.65
i "Piano" 6.30 2.0 72 0.65
e
</CsScore>
</CsoundSynthesizer>

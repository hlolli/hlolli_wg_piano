<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_KSMPS
#define TEST_KSMPS #32#
#endif
#ifndef TEST_PROFILE
#define TEST_PROFILE #"generic_2018"#
#endif

sr = 48000
ksmps = $TEST_KSMPS
nchnls = 4
0dbfs = 1

giPiano hlolli_wg_piano_create $TEST_PROFILE

instr Note
  xtratim 0.6
  kRelease release
  kTrigger init 0.65
  kTrigger = (kRelease == 0 ? 0.65 : 0)
#ifdef TEST_K_ASSIGNMENT
  kFrequency = cpsmidinn(p4)
  kHardness = 0.43
  kPosition = 0.12
  kDecay = 0.70
  kStiffness = 0.42
  kDetune = 0.60
  kBody = 0.72
  kStrange = 0.0
  kPedal = 0.0
#else
  kFrequency init cpsmidinn(p4)
  kHardness init 0.43
  kPosition init 0.12
  kDecay init 0.70
  kStiffness init 0.42
  kDetune init 0.60
  kBody init 0.72
  kStrange init 0.0
  kPedal init 0.0
#endif
  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, kHardness, kPosition, kDecay, \
      kStiffness, kDetune, kBody, kStrange, kPedal, giPiano
  outch 1, aLeft, 2, aRight
endin

instr Resonance
  aLeft, aRight hlolli_wg_piano_resonance giPiano, 0.72, 0
  outch 3, aLeft, 4, aRight
endin

</CsInstruments>
<CsScore>
i "Resonance" 0 2.5
i "Note" 0.013 0.45 21
i "Note" 0.217 0.40 60
i "Note" 0.419 0.50 84
i "Note" 0.613 0.45 108
e
</CsScore>
</CsoundSynthesizer>

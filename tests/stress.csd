<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_SR
#define TEST_SR #48000#
#endif
#ifndef TEST_KSMPS
#define TEST_KSMPS #32#
#endif
#ifndef TEST_VOICES
#define TEST_VOICES #192#
#endif

sr = $TEST_SR
ksmps = $TEST_KSMPS
nchnls = 2
0dbfs = 1

gaResonanceInputLeft init 0
gaResonanceInputRight init 0

instr PianoStress
  iNote = p4
  iVelocity = p5
  iHardness = p6
  iPosition = p7
  iDecay = p8
  iStiffness = p9
  iDetune = p10
  iBody = p11
  iStrange = p12
  iPedal = p13

  xtratim 1.20
  kRelease release
  kTrigger = (kRelease == 0 ? iVelocity : 0)
  kFrequency init cpsmidinn(iNote)

  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, iHardness, iPosition, iDecay, \
      iStiffness, iDetune, iBody, iStrange, iPedal
  outs 0.0025 * aLeft, 0.0025 * aRight
  gaResonanceInputLeft += 0.0025 * aLeft
  gaResonanceInputRight += 0.0025 * aRight
endin

instr RetriggerStress
  xtratim 0.80
  kRelease release
  kPhase phasor 37
  kTrigger = (kRelease == 0 && kPhase < 0.16 ? 1.25 : 0)
  ; Sweep almost the whole accepted range, including short two-sample rails.
  kFrequency linseg 20, p3 * 0.45, 0.44 * sr, p3 * 0.10, 0.44 * sr, \
      p3 * 0.45, 20
  kHardness linseg 0, p3 * 0.5, 1, p3 * 0.5, 0
  kPosition linseg 0.025, p3 * 0.5, 0.45, p3 * 0.5, 0.025
  kDecay linseg 0, p3 * 0.5, 1, p3 * 0.5, 0
  kStiffness linseg 0, p3 * 0.5, 1, p3 * 0.5, 0
  kDetune linseg 0, p3 * 0.5, 1, p3 * 0.5, 0
  kBody linseg 0, p3 * 0.5, 1, p3 * 0.5, 0
  kStrange linseg -1, p3 * 0.5, 1, p3 * 0.5, -1
  kPedal linseg 0, p3 * 0.5, 1, p3 * 0.5, 0

  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, kHardness, kPosition, kDecay, \
      kStiffness, kDetune, kBody, kStrange, kPedal
  outs 0.01 * aLeft, 0.01 * aRight
  gaResonanceInputLeft += 0.01 * aLeft
  gaResonanceInputRight += 0.01 * aRight
endin

instr SharedResonanceStress
  kBody linseg 0, 0.70, 1, 2.80, 1, 1.00, 0
  kPedal linseg 0, 0.35, 1, 3.50, 1, 0.65, 0
  aWetLeft, aWetRight hlolli_wg_piano_resonance \
      gaResonanceInputLeft, gaResonanceInputRight, kBody, kPedal
  outs aWetLeft, aWetRight
  clear gaResonanceInputLeft, gaResonanceInputRight
endin

instr ScheduleStress
  iIndex = 0
  while iIndex < $TEST_VOICES do
    iStart = 0.008 * iIndex
    iDuration = 0.025 + 0.005 * (iIndex % 9)
    iNote = 21 + ((37 * iIndex) % 88)
    iVelocity = 0.05 + 1.20 * ((17 * iIndex) % 32) / 31
    iHardness = ((11 * iIndex) % 17) / 16
    iPosition = 0.025 + 0.425 * ((7 * iIndex) % 19) / 18
    iDecay = ((13 * iIndex) % 23) / 22
    iStiffness = ((5 * iIndex) % 29) / 28
    iDetune = ((3 * iIndex) % 31) / 30
    iBody = ((19 * iIndex) % 37) / 36
    iStrange = -1 + 2 * ((23 * iIndex) % 41) / 40
    iPedal = ((29 * iIndex) % 43) / 42

    event_i "i", "PianoStress", iStart, iDuration, iNote, iVelocity, \
        iHardness, iPosition, iDecay, iStiffness, iDetune, iBody, \
        iStrange, iPedal
    iIndex += 1
  od
endin

</CsInstruments>
<CsScore>
i "ScheduleStress" 0 0.01
i "RetriggerStress" 0 3.0
i "SharedResonanceStress" 0 4.5
e 4.5
</CsScore>
</CsoundSynthesizer>

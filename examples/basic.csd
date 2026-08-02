<CsoundSynthesizer>
<CsOptions>
-odac -d -m128
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giPiano hlolli_wg_piano_create
gkPedal init 0.82
gkPedalTarget init 0.82
gaRoomLeft init 0
gaRoomRight init 0

instr Piano
  iNote = p4
  iVelocity = p5
  iPan = p6

  xtratim 2.40
  kRelease release
  kTrigger = (kRelease == 0 ? iVelocity : 0)
  kFrequency init cpsmidinn(iNote)
  kPedal = gkPedal
  kTail linsegr 1, 0.01, 1, 2.40, 0

  aModelLeft, aModelRight hlolli_wg_piano \
      kTrigger, kFrequency, 0.43, 0.12, 0.76, \
      0.40, 0.60, 0.72, 0, kPedal, giPiano
  aMono = 0.5 * (aModelLeft + aModelRight)
  aLeft, aRight pan2 aMono, iPan
  aLeft *= kTail
  aRight *= kTail
  outs 0.70 * aLeft, 0.70 * aRight
  gaRoomLeft += aLeft
  gaRoomRight += aRight
endin

instr Pedal
  gkPedalTarget = p4
endin

; This can stop and restart without clearing this piano's shared state.
instr Master
  gkPedal portk gkPedalTarget, 0.025
  aWetLeft, aWetRight hlolli_wg_piano_resonance \
      giPiano, 0.72, gkPedal
  aRoomLeft, aRoomRight reverbsc \
      gaRoomLeft + 0.34 * aWetLeft, \
      gaRoomRight + 0.34 * aWetRight, 0.91, 9000
  outs 0.36 * aWetLeft + 0.14 * aRoomLeft, \
       0.36 * aWetRight + 0.14 * aRoomRight
  clear gaRoomLeft, gaRoomRight
endin
</CsInstruments>
<CsScore>
i "Master" 0 8
i "Piano" 0.00 1.25 48 0.64 0.30
i "Piano" 0.05 1.20 55 0.54 0.42
i "Piano" 0.10 1.15 60 0.50 0.55
i "Piano" 0.15 1.10 64 0.58 0.66
i "Piano" 2.20 1.20 50 0.62 0.32
i "Piano" 2.25 1.15 57 0.52 0.44
i "Piano" 2.30 1.10 62 0.50 0.57
i "Piano" 2.35 1.05 65 0.57 0.68
i "Pedal" 2.08 0.03 0.08
i "Pedal" 2.18 0.03 0.82
i "Pedal" 4.65 0.03 0.00
e
</CsScore>
</CsoundSynthesizer>

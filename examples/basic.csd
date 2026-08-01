<CsoundSynthesizer>
<CsOptions>
-odac -d -m128
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

gaSendLeft init 0
gaSendRight init 0

instr Piano
  iNote = p4
  iVelocity = p5
  iPan = p6

  xtratim 2.40
  kRelease release
  kTrigger = (kRelease == 0 ? iVelocity : 0)
  kFrequency init cpsmidinn(iNote)
  kPedal = 0.82
  kTail linsegr 1, 0.01, 1, 2.40, 0

  aModelLeft, aModelRight hlolli_wg_piano \
      kTrigger, kFrequency, 0.43, 0.12, 0.76, \
      0.40, 0.60, 0.72, 0, kPedal
  aMono = 0.5 * (aModelLeft + aModelRight)
  aLeft, aRight pan2 aMono, iPan
  aLeft *= kTail
  aRight *= kTail
  outs 0.70 * aLeft, 0.70 * aRight
  gaSendLeft += 0.22 * aLeft
  gaSendRight += 0.22 * aRight
endin

instr Room
  aWetLeft, aWetRight reverbsc gaSendLeft, gaSendRight, 0.88, 8200
  outs 0.34 * aWetLeft, 0.34 * aWetRight
  clear gaSendLeft, gaSendRight
endin
</CsInstruments>
<CsScore>
i "Room" 0 8
i "Piano" 0.00 1.25 48 0.64 0.30
i "Piano" 0.05 1.20 55 0.54 0.42
i "Piano" 0.10 1.15 60 0.50 0.55
i "Piano" 0.15 1.10 64 0.58 0.66
i "Piano" 2.20 1.20 50 0.62 0.32
i "Piano" 2.25 1.15 57 0.52 0.44
i "Piano" 2.30 1.10 62 0.50 0.57
i "Piano" 2.35 1.05 65 0.57 0.68
e
</CsScore>
</CsoundSynthesizer>

<CsoundSynthesizer>
<CsOptions>
-odac -d -m128
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

gaDryLeft init 0
gaDryRight init 0
gaSendLeft init 0
gaSendRight init 0
gaBoardLeft init 0
gaBoardRight init 0

instr Piano
  iNote = p4
  iVelocity = p5
  iHardness = p6
  iHammerPosition = p7
  iDecay = p8
  iStiffness = p9
  iDetune = p10
  iBody = p11
  iStrange = p12
  iPedal = p13
  iPan = p14

  xtratim 2.60
  kRelease release
  kTrigger = (kRelease == 0 ? iVelocity : 0)
  kFrequency init cpsmidinn(iNote)
  ; Keep the damper raised while this voice fades. The former release branch
  ; set the pedal to zero and stopped each note before it could join the next.
  kPedal = iPedal
  kTail linsegr 1, 0.01, 1, 2.60, 0

  aModelLeft, aModelRight hlolli_wg_piano \
      kTrigger, kFrequency, iHardness, iHammerPosition, iDecay, \
      iStiffness, iDetune, iBody, iStrange, kPedal

  ; Keep some of the model's own width, then place each hand on the keyboard.
  aMono = 0.5 * (aModelLeft + aModelRight)
  aPanLeft, aPanRight pan2 aMono, iPan
  aLeft = (0.56 * aModelLeft + 0.62 * aPanLeft) * kTail
  aRight = (0.56 * aModelRight + 0.62 * aPanRight) * kTail

  gaDryLeft += 0.55 * aLeft
  gaDryRight += 0.55 * aRight
  gaSendLeft += 0.24 * aLeft
  gaSendRight += 0.24 * aRight
  gaBoardLeft += 0.20 * aLeft
  gaBoardRight += 0.20 * aRight
endin

instr HarpBeat
  iStep = p3 / 6
  iInnerDuration = 1.45 * iStep
  iBassDuration = 2.10 * iStep
  ; The melody crosses each beat line by about 48 ms, as a held piano phrase
  ; should. At 3.20 steps it ended 269 ms before the next melody note.
  iLeadDuration = 6.50 * iStep
  iPhrasePosition = max(0, min(1, (p2 - 0.576923) / 18.461539))
  iLead = 0.50 + 0.11 * sin(3.141592653589793 * iPhrasePosition)
  iInner = 0.44 * iLead
  iBass = 0.64 * iLead
  iLeftInner = 0.48 * iLead

  ; Right hand: the sung top note followed by five quiet triplet notes.
  event_i "i", "Piano", 0 * iStep, iLeadDuration, p4, iLead, \
      0.41, 0.12, 0.78, 0.38, 0.60, 0.70, 0, 0.82, 0.64
  event_i "i", "Piano", 1 * iStep, iInnerDuration, p5, iInner, \
      0.31, 0.12, 0.74, 0.36, 0.56, 0.66, 0, 0.78, 0.63
  event_i "i", "Piano", 2 * iStep, iInnerDuration, p6, 0.94 * iInner, \
      0.31, 0.12, 0.74, 0.36, 0.56, 0.66, 0, 0.78, 0.62
  event_i "i", "Piano", 3 * iStep, iInnerDuration, p7, 0.88 * iInner, \
      0.30, 0.12, 0.74, 0.36, 0.56, 0.66, 0, 0.78, 0.61
  event_i "i", "Piano", 4 * iStep, iInnerDuration, p8, 0.92 * iInner, \
      0.31, 0.12, 0.74, 0.36, 0.56, 0.66, 0, 0.78, 0.62
  event_i "i", "Piano", 5 * iStep, iInnerDuration, p9, iInner, \
      0.31, 0.12, 0.74, 0.36, 0.56, 0.66, 0, 0.78, 0.63

  ; Left hand: a low bass and the mirrored six-note harp figure.
  event_i "i", "Piano", 0 * iStep, iBassDuration, p10, iBass, \
      0.36, 0.14, 0.82, 0.34, 0.54, 0.72, 0, 0.88, 0.36
  event_i "i", "Piano", 1 * iStep, iInnerDuration, p11, iLeftInner, \
      0.32, 0.14, 0.77, 0.35, 0.54, 0.68, 0, 0.82, 0.37
  event_i "i", "Piano", 2 * iStep, iInnerDuration, p12, 0.94 * iLeftInner, \
      0.32, 0.14, 0.77, 0.35, 0.54, 0.68, 0, 0.82, 0.38
  event_i "i", "Piano", 3 * iStep, iInnerDuration, p13, 0.88 * iLeftInner, \
      0.32, 0.14, 0.77, 0.35, 0.54, 0.68, 0, 0.82, 0.39
  event_i "i", "Piano", 4 * iStep, iInnerDuration, p14, 0.94 * iLeftInner, \
      0.32, 0.14, 0.77, 0.35, 0.54, 0.68, 0, 0.82, 0.38
  event_i "i", "Piano", 5 * iStep, iInnerDuration, p15, iLeftInner, \
      0.32, 0.14, 0.77, 0.35, 0.54, 0.68, 0, 0.82, 0.37
endin

; A short shared board response sits before the room. Broad, uneven modes add
; wood colour without imposing a new pitch, and the first reverbsc keeps that
; response alive across note boundaries.
instr Master
  aBoardLowLeft reson gaBoardLeft, 118, 82, 1
  aBoardLowRight reson gaBoardRight, 127, 88, 1
  aBoardLowMidLeft reson gaBoardLeft, 285, 155, 1
  aBoardLowMidRight reson gaBoardRight, 303, 165, 1
  aBoardMidLeft reson gaBoardLeft, 690, 360, 1
  aBoardMidRight reson gaBoardRight, 728, 390, 1
  aBoardHighLeft reson gaBoardLeft, 1560, 820, 1
  aBoardHighRight reson gaBoardRight, 1640, 870, 1

  aBoardColourLeft = 0.16 * aBoardLowLeft + 0.13 * aBoardLowMidLeft + \
      0.09 * aBoardMidLeft + 0.055 * aBoardHighLeft
  aBoardColourRight = 0.15 * aBoardLowRight + 0.12 * aBoardLowMidRight + \
      0.10 * aBoardMidRight + 0.060 * aBoardHighRight
  aBoardWetLeft, aBoardWetRight reverbsc \
      gaBoardLeft + aBoardColourLeft, gaBoardRight + aBoardColourRight, \
      0.84, 6100
  aBoardOutLeft = 0.22 * aBoardColourLeft + 0.54 * aBoardWetLeft
  aBoardOutRight = 0.22 * aBoardColourRight + 0.54 * aBoardWetRight

  aWetLeft, aWetRight reverbsc \
      gaSendLeft + 0.34 * aBoardOutLeft, \
      gaSendRight + 0.34 * aBoardOutRight, 0.91, 9000
  kEndFade linseg 1, p3 - 1.75, 1, 1.75, 0
  aMixLeft = 2.55 * (gaDryLeft + 0.34 * aBoardOutLeft + \
      0.34 * aWetLeft) * kEndFade
  aMixRight = 2.55 * (gaDryRight + 0.34 * aBoardOutRight + \
      0.34 * aWetRight) * kEndFade
  aOutLeft limit aMixLeft, -0.98, 0.98
  aOutRight limit aMixRight, -0.98, 0.98
  outs aOutLeft, aOutRight
  clear gaDryLeft, gaDryRight, gaSendLeft, gaSendRight, \
      gaBoardLeft, gaBoardRight
endin

</CsInstruments>
<CsScore>
; Chopin: Etude in A-flat major, Op. 25 No. 1, "Aeolian Harp".
; Public-domain Mutopia score, opening eight bars and their tonic return.
; Allegro sostenuto, quarter = 104.
i "Master" 0 29.50

; E-flat pickup.
i "Piano" 0 0.66 75 0.52 0.41 0.12 0.78 0.38 0.60 0.70 0 0.82 0.64

; Each HarpBeat holds six right-hand notes followed by six left-hand notes.
i "HarpBeat" 0.576923 0.576923 75 68 72 63 68 72 32 51 56 60 56 51
i "HarpBeat" 1.153846 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 1.730769 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 2.307692 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 2.884615 0.576923 77 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 3.461538 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 4.038462 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 4.615385 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 5.192308 0.576923 75 70 73 63 70 73 44 51 55 61 55 51
i "HarpBeat" 5.769231 0.576923 75 70 73 63 70 73 44 51 55 61 55 51
i "HarpBeat" 6.346154 0.576923 77 70 73 63 70 73 44 51 55 61 55 51
i "HarpBeat" 6.923077 0.576923 75 70 73 63 70 73 44 51 55 61 55 51
i "HarpBeat" 7.500000 0.576923 82 72 75 63 72 75 44 51 56 60 56 51
i "HarpBeat" 8.076923 0.576923 80 72 75 63 72 75 44 51 56 60 56 51
i "HarpBeat" 8.653846 0.576923 80 72 76 64 72 76 44 52 56 60 56 52
i "HarpBeat" 9.230769 0.576923 80 72 76 64 72 76 44 52 56 60 56 52
i "HarpBeat" 9.807692 0.576923 80 73 77 68 73 77 37 56 61 65 61 56
i "HarpBeat" 10.384615 0.576923 80 73 77 68 73 77 49 56 61 65 61 56
i "HarpBeat" 10.961538 0.576923 80 73 77 68 73 77 49 56 61 65 61 56
i "HarpBeat" 11.538462 0.576923 82 73 77 67 73 77 49 55 61 65 61 55
i "HarpBeat" 12.115385 0.576923 84 72 77 67 72 77 48 55 60 65 60 55
i "HarpBeat" 12.692308 0.576923 82 72 76 67 72 76 48 55 60 64 60 55
i "HarpBeat" 13.269231 0.576923 80 72 77 68 72 77 53 56 60 65 60 56
i "HarpBeat" 13.846154 0.576923 77 71 75 65 71 75 47 53 56 63 56 53
i "HarpBeat" 14.423077 0.576923 77 70 75 65 70 75 46 53 56 63 56 53
i "HarpBeat" 15.000000 0.576923 79 70 75 65 70 75 46 53 56 63 56 53
i "HarpBeat" 15.576923 0.576923 80 70 74 65 68 70 46 53 56 62 56 53
i "HarpBeat" 16.153846 0.576923 70 65 68 58 65 68 46 53 56 62 56 53
i "HarpBeat" 16.730769 0.576923 70 63 68 58 63 68 39 46 51 61 51 46
i "HarpBeat" 17.307692 0.576923 72 63 68 58 63 68 39 46 51 56 51 46
i "HarpBeat" 17.884615 0.576923 73 63 67 58 61 63 39 46 51 55 51 46
i "HarpBeat" 18.461538 0.576923 63 58 61 51 58 61 39 46 51 55 51 46

; Bar nine returns to A-flat and gives the excerpt a settled ending.
i "HarpBeat" 19.038462 0.576923 75 68 72 63 68 72 32 51 56 60 56 51
i "HarpBeat" 19.615385 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 20.192308 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
i "HarpBeat" 20.769231 0.576923 75 68 72 63 68 72 44 51 56 60 56 51
e
</CsScore>
</CsoundSynthesizer>

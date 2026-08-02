<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>

#ifndef TEST_SPLIT_OUTPUT
#define TEST_SPLIT_OUTPUT #0#
#endif
#ifndef TEST_DUPLICATE_OUTPUT
#define TEST_DUPLICATE_OUTPUT #0#
#endif
#ifndef TEST_BAD_HANDLE
#define TEST_BAD_HANDLE #0#
#endif
#ifndef TEST_LOCAL_CREATE
#define TEST_LOCAL_CREATE #0#
#endif
#ifndef TEST_LOCAL_NOTE
#define TEST_LOCAL_NOTE #0#
#endif
#ifndef TEST_LOCAL_OUTPUT
#define TEST_LOCAL_OUTPUT #0#
#endif
#ifndef TEST_LOCAL_BUS
#define TEST_LOCAL_BUS #0#
#endif
#ifndef TEST_SPLIT_TIME
#define TEST_SPLIT_TIME #1.500125#
#endif

sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

giPiano hlolli_wg_piano_create

instr PianoNote
  xtratim 0.80
  kRelease release
  kTrigger = (kRelease == 0 ? 0.72 : 0)
  kFrequency init cpsmidinn(48)
  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, 0.43, 0.12, 0.76, \
      0.42, 0.60, 0.72, 0, 0.82, giPiano
endin

instr PianoOutput
  kNow elapsedtime
  kBody init 0.20
  kPedal init 0.10
  if kNow < 2.70 then
    kBody = 0.20 + (0.92 - 0.20) * kNow / 2.70
  else
    kBody = 0.92 + (0.35 - 0.92) * (kNow - 2.70) / 1.30
  endif
  if kNow < 1.10 then
    kPedal = 0.10 + (0.90 - 0.10) * kNow / 1.10
  elseif kNow < 2.50 then
    kPedal = 0.90 + (0.30 - 0.90) * (kNow - 1.10) / 1.40
  else
    kPedal = 0.30 + (0.80 - 0.30) * (kNow - 2.50) / 1.50
  endif
  aWetLeft, aWetRight hlolli_wg_piano_resonance \
      giPiano, kBody, kPedal
  outs aWetLeft, aWetRight
endin

instr BadPianoOutput
  aWetLeft, aWetRight hlolli_wg_piano_resonance p4, 0.72, 0.82
  outs aWetLeft, aWetRight
endin

instr LocalPianoCreate
  setksmps 16
  iLocalPiano hlolli_wg_piano_create
endin

instr LocalPianoNote
  setksmps 16
  kFrequency init cpsmidinn(48)
  aLeft, aRight hlolli_wg_piano \
      0.72, kFrequency, 0.43, 0.12, 0.76, \
      0.42, 0.60, 0.72, 0, 0.82, giPiano
endin

instr LocalPianoOutput
  setksmps 16
  aWetLeft, aWetRight hlolli_wg_piano_resonance \
      giPiano, 0.72, 0.82
  outs aWetLeft, aWetRight
endin

instr LocalBusOutput
  setksmps 16
  aZero init 0
  aWetLeft, aWetRight hlolli_wg_piano_resonance \
      aZero, aZero, 0.72, 0.82
  outs aWetLeft, aWetRight
endin

instr ScheduleTest
  if $TEST_BAD_HANDLE != 0 then
    event_i "i", "BadPianoOutput", 0, 4, 999
  elseif $TEST_LOCAL_CREATE != 0 then
    event_i "i", "LocalPianoCreate", 0, 0.20
  elseif $TEST_LOCAL_NOTE != 0 then
    event_i "i", "LocalPianoNote", 0, 0.20
  elseif $TEST_LOCAL_OUTPUT != 0 then
    event_i "i", "LocalPianoOutput", 0, 4
  elseif $TEST_LOCAL_BUS != 0 then
    event_i "i", "LocalBusOutput", 0, 4
  elseif $TEST_DUPLICATE_OUTPUT != 0 then
    event_i "i", "PianoOutput", 0, 4
    event_i "i", "PianoOutput", 0, 4
  elseif $TEST_SPLIT_OUTPUT == 0 then
    event_i "i", "PianoOutput", 0, 4
  else
    event_i "i", "PianoOutput", 0, $TEST_SPLIT_TIME
    event_i "i", "PianoOutput", $TEST_SPLIT_TIME, 4 - $TEST_SPLIT_TIME
  endif
  event_i "i", "PianoNote", 0, 0.20
endin

</CsInstruments>
<CsScore>
i "ScheduleTest" 0 0.01
e 4
</CsScore>
</CsoundSynthesizer>

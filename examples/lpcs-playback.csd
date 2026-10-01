<CsoundSynthesizer>
<CsOptions>
-d -m0 --sample-accurate
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

#include "lpcs-playback.inc"

giPiano hlolli_wg_piano_create

; LPCS piano-performance-v1: p25 is key duration, not sounding duration.
; Keep the voice alive for its resolved duration and let the model damp it.
instr 17
  if p16 == 262144 then
    LpcsRequire p25 == 64 || p26 == 0, "This piano adapter supports sustain (CC64) only"
    if p25 == 64 then
      chnset p26, "lpcs-pedal-64"
    endif
    turnoff
    igoto PIANO_DONE
  endif
  LpcsRequire p10 == -1 && p8 >= 21 && p8 <= 108, "Expected an 88-key piano pitch"
  LpcsRequire p25 > 0 && p25 <= p3 + 0.000000001, "Invalid piano key duration"
  LpcsRequire p26 == 0, "Soft pedal is not supported by this piano adapter"
  LpcsRequire p16 % 4 == 0, "Resolve tied notes before piano playback"
  kElapsed timeinsts
  kTrigger = (kElapsed < p25 ? p11 : 0)
  kPedal chnget "lpcs-pedal-64"
  aLeft, aRight hlolli_wg_piano kTrigger, cpsmidinn(p8), .43, .12, .70, \
      .42, .60, .72, 0, kPedal, giPiano
  iPan = (p14 + 1) / 2
  outs .7 * aLeft * sqrt(2 * (1 - iPan)), \
       .7 * aRight * sqrt(2 * iPan)
PIANO_DONE:
endin

; One shared renderer owns this piano's pedal rail and sympathetic strings.
; No room reverb: the pedal comparison should expose the instrument's decay.
instr 99
  kPedal chnget "lpcs-pedal-64"
  aLeft, aRight hlolli_wg_piano_resonance giPiano, .72, kPedal
  outs .36 * aLeft, .36 * aRight
endin

#ifndef LPCS_FILE
#define LPCS_FILE #performance.json#
#endif
document:LpcsPlayback jsonunmarshalfile "$LPCS_FILE"
LpcsRequire strcmp(document.target, "piano-performance-v1") == 0, "Expected piano-performance-v1"
giLength LpcsSchedule document, 17
schedule 99, 0, giLength + 3
eventi "e", 0, giLength + 3
</CsInstruments>
<CsScore>
f 0 z
</CsScore>
</CsoundSynthesizer>

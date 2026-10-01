<CsoundSynthesizer>
<CsOptions>
-d -m128
</CsOptions>
<CsInstruments>
#ifndef TEST_SR
#define TEST_SR #44100#
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
#ifndef TEST_PEDAL
#define TEST_PEDAL #0#
#endif
#ifndef TEST_BODY
#define TEST_BODY #0.72#
#endif
#ifndef TEST_KEY_SECONDS
#define TEST_KEY_SECONDS #0.5#
#endif
sr=$TEST_SR
ksmps=$TEST_KSMPS
nchnls=2
0dbfs=1
instr Note
 ; No xtratim, external fade, or release gate: the opcode owns key release.
 aL,aR hlolli_wg_piano $TEST_VELOCITY,cpsmidinn($TEST_NOTE), \
     .43,.12,.70,.42,.60,$TEST_BODY,0,$TEST_PEDAL
 outs aL,aR
endin
#ifdef TEST_RESTRIKE
instr Repeated
 kBlocks init 0
 kTrigger = (kBlocks < sr/ksmps ? .2 : 1)
 kBlocks += 1
 aL,aR hlolli_wg_piano kTrigger,cpsmidinn($TEST_NOTE), \
     .43,.12,.70,.42,.60,0,0,1
 outch 1,aL
endin
instr Separate
 aL,aR hlolli_wg_piano p4,cpsmidinn($TEST_NOTE), \
     .43,.12,.70,.42,.60,0,0,1
 outch 2,aL
endin
#endif
instr Start
#ifdef TEST_RESTRIKE
 event_i "i","Repeated",0,3.1
 event_i "i","Separate",0,3.1,.2
 event_i "i","Separate",1,2.1,1
#else
 event_i "i","Note",.35,$TEST_KEY_SECONDS
#endif
endin
</CsInstruments>
<CsScore>
i "Start" 0 .01
f 0 12
e
</CsScore>
</CsoundSynthesizer>

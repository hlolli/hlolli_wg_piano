<CsoundSynthesizer>
<CsOptions>
-n -d -m128
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 2
0dbfs = 1

instr Piano
  xtratim 0.60
  kRelease release
  kTrigger = (kRelease == 0 ? p5 : 0)
  kFrequency init cpsmidinn(p4)
  kTail linsegr 1, 0.01, 1, 0.60, 0
  aLeft, aRight hlolli_wg_piano \
      kTrigger, kFrequency, 0.43, 0.12, 0.70, \
      0.42, 0.60, 0.72, 0, 0
  outs aLeft * kTail, aRight * kTail
endin
</CsInstruments>
<CsScore>
i "Piano" 0 0.45 60 0.65
i "Piano" 0.25 0.45 67 0.55
e 1.40
</CsScore>
</CsoundSynthesizer>

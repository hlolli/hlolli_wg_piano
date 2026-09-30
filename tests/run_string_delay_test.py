#!/usr/bin/env python3
"""Check the production string delay for unwanted damping and unsafe motion."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r'static [^;{}]+\b' + name + r'\([^;]*?\)\s*\{', source)
    if not match:
        raise ValueError('missing C function: ' + name)
    end = match.end()
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--source', type=Path, default=ROOT / 'hlolli_wg_piano.c')
    args = parser.parse_args()
    source = args.source.read_text()
    struct = source[source.index('typedef struct {'):source.index('} WG_STRING;')+len('} WG_STRING;')]
    names = ['wg_delay_coefficients', 'wg_string_delay_read', 'wg_string_junction']
    call = 'wg_string_delay_read(&s)'
    harness = r'''
int main(void) {
  const double rates[] = {44100, 48000, 96000};
  const double delays[] = {2.1, 3.49, 3.51, 10.25, 10.5, 29.75, 76.2};
  double common = wg_string_junction(1, .98, .01);
  double difference = wg_string_junction(1, 0, .01);
  if (common >= difference || common < 0 || difference > 1) {
    fprintf(stderr,"FAIL: bridge must damp shared motion more than opposing motion\n");
    return 1;
  }
  double worst = 0;
  for (int r=0; r<3; ++r) for (int d=0; d<7; ++d) {
    for (double f=440; f<=10000; f+=2390) {
      double data[512] = {0};
      WG_STRING s = {0}; s.data=data; s.size=512; s.delay=delays[d];
      double in=0, out=0;
      for (int i=0; i<24000; ++i) {
        double y = CALL;
        double x = sin(6.283185307179586*f*i/rates[r]);
        data[s.write_index]=x;
        s.write_index=(s.write_index+1)%s.size;
        if(i>12000) {in+=x*x; out+=y*y;}
      }
      double db=10*log10(out/in);
      if(fabs(db)>worst) worst=fabs(db);
      if(!isfinite(db) || fabs(db)>.02) {
        fprintf(stderr,"FAIL: sr %.0f delay %.2f frequency %.0f gain %.3f dB\n",rates[r],delays[d],f,db);
        return 1;
      }
    }
  }
  /* Pitch slides cross integer taps and the short-delay fallback. */
  double data[512]={0}; WG_STRING s={0}; s.data=data; s.size=512;
  for(int i=0;i<100000;++i) {
    s.delay=2.1+35*(.5+.5*sin(i*.0002));
    double y=CALL;
    if(!isfinite(y) || fabs(y)>2) {fprintf(stderr,"FAIL: moving delay diverged\n");return 1;}
    data[s.write_index]=sin(i*.173);
    s.write_index=(s.write_index+1)%512;
  }
  printf("PASS: worst delay gain error %.4f dB; moving delay stays bounded\n",worst);
  return 0;
}
'''.replace('CALL', call)
    with tempfile.TemporaryDirectory(prefix='piano-delay-') as folder:
        folder = Path(folder)
        cfile=folder/'check.c'; binary=folder/'check'
        cfile.write_text('#include <stdint.h>\n#include <math.h>\n#include <stdio.h>\n#define DISPERSION_STAGES 8\n'+struct+'\n'+'\n'.join(function(source,n) for n in names)+harness)
        subprocess.run([args.cc,'-O2','-std=c11',str(cfile),'-lm','-o',str(binary)],check=True)
        return subprocess.run([str(binary)]).returncode

if __name__=='__main__':
    raise SystemExit(main())

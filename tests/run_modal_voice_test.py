#!/usr/bin/env python3
"""Check approved strikes, velocity tone, and the native key-release path."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

try:
    import numpy as np
except ImportError:
    print('NumPy is required for the resonance voice checks')
    raise SystemExit(77)

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import piano_timbre as tone


def render(args,folder,name,**macros):
    path=folder/(name+'.wav')
    command=[args.csound,'--opcode-lib='+str(args.module.resolve()),'--sample-accurate',
             '-W','-l','-o',str(path)]
    command+=['--omacro:TEST_'+key.upper()+'='+str(value) for key,value in macros.items()]
    command.append(str(ROOT/'tests/modal_voice.csd'))
    result=subprocess.run(command,capture_output=True,text=True,timeout=45)
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    rate,x=tone.read_wav(path)
    if not np.isfinite(x).all() or np.abs(x).max()>=1:
        raise AssertionError(name+': nonfinite or clipped output')
    return rate,x


def expected(bank,recipe,rate,seconds):
    t=np.arange(round(seconds*rate))/rate
    y=np.zeros(len(t))
    for frequency,loss,real,imag in bank['modes']:
        frequency*=recipe['frequency_ratio']
        if frequency>=.45*rate: continue
        y+=np.real(complex(real,imag)*np.exp(t*(-loss+2j*np.pi*frequency)))
    frames=np.floor(bank['trim_seconds']*rate+.5)
    u=np.minimum(np.arange(len(t))/frames,1) if frames else np.ones(len(t))
    return y*(1-np.exp(-t/.004))*(bank['trim_initial']+(1-bank['trim_initial'])*u*u*(3-2*u))*bank['gain']*recipe['gain']


def rms(x,rate,start,end):
    return float(np.sqrt(np.mean(x[round(start*rate):round(end*rate)]**2)))


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--csound',required=True)
    cli.add_argument('--module',type=Path,required=True)
    cli.add_argument('--output',type=Path)
    args=cli.parse_args()
    baseline=json.loads((ROOT/'fit/keyboard-modal-bank.json').read_text())
    banks={b['note']:b for b in baseline['banks']}
    keys={k['note']:k for k in baseline['keys']}
    failures=[]
    with tempfile.TemporaryDirectory(prefix='piano-modal-') as temp:
        folder=args.output or Path(temp);folder.mkdir(parents=True,exist_ok=True)
        # Odd blocks and sample-accurate note boundaries exercise the scalar
        # remainder after the four-sample resonance kernel.
        for rate,block in [(44100,32),(48000,64),(48000,31)]:
            for note in [32,60,67,72,79]:
                sr,x=render(args,folder,f'held-{rate}-{block}-{note}',note=note,sr=rate,ksmps=block,key_seconds=3.1)
                reference=expected(banks[keys[note]['bank_note']],keys[note],rate,3)
                start=round(.35*rate)
                error=min(float(np.max(np.abs(x[b:b+len(reference),0]-reference))) for b in (start-1,start,start+1))
                print(f'held {note} at {rate}, block {block}: maximum sample error {error:.3g}')
                if error>5e-7: failures.append(f'approved note {note} changed at {rate}')
        for case in json.loads((ROOT/'fit/modal-extension.json').read_text())['cases']:
            if case['dynamic']=='mf': continue
            velocity=.2 if case['dynamic']=='pp' else 1.0
            bank={'modes':[[m[k] for k in ('frequency_hz','loss_per_second','real','imag')]
                           for c in case['clusters'] for m in c['modes']],
                  'gain':case['native_check']['comparison_gain'],
                  'trim_initial':1.,'trim_seconds':0.}
            sr,x=render(args,folder,'accepted-C5-'+case['dynamic'],note=72,velocity=velocity,key_seconds=3.1)
            reference=expected(bank,{'frequency_ratio':1.,'gain':(velocity/.65)**1.35},sr,3)
            start=round(.35*sr)
            error=min(float(np.max(np.abs(x[b:b+len(reference),0]-reference))) for b in (start-1,start,start+1))
            print('C5',case['dynamic'],'maximum sample error',error)
            if error>5e-7: failures.append('approved C5 '+case['dynamic']+' changed')
        sr,closed=render(args,folder,'release-closed')
        _,dry=render(args,folder,'release-no-body',body=0)
        _,pedal=render(args,folder,'release-pedal',pedal=1)
        attack=rms(closed,sr,.45,.75)
        early=rms(closed,sr,1.0,1.15)
        residual=rms(closed,sr,1.25,1.65)
        later=rms(closed,sr,2.0,2.4)
        no_body=rms(dry,sr,1.25,1.65)
        sustained=rms(pedal,sr,1.25,1.65)
        print(f'release: attack={attack:.6g}, early={early:.6g}, residual={residual:.6g}, later={later:.6g}, no-body={no_body:.6g}, pedal={sustained:.6g}')
        if not attack*1e-5<residual<attack*.05: failures.append('residual tail absent or too loud')
        if not later<residual: failures.append('residual tail does not fade')
        if not residual>no_body*5: failures.append('body state does not survive string damping')
        if not sustained>residual*5: failures.append('pedal does not retain string energy')
        for note in [32,60,72,96]:
            sr,x=render(args,folder,f'restrike-{note}',note=note,sr=48000,ksmps=64,restrike=1)
            held=x[:round(2.8*sr)]
            error=float(np.max(np.abs(held[:,0]-held[:,1])))
            print('restrike',note,'superposition error',error)
            if error>5e-7: failures.append(f'note {note}: restrike changed the earlier strike decay')
        for note in [32,48,60,72,84,95,96,99]:
            levels=[];centroids=[]
            for velocity in [.2,.65,1.0]:
                rate,x=render(args,folder,f'dynamic-{note}-{velocity}',note=note,velocity=velocity,key_seconds=.4)
                if np.abs(x).max()>=.90: failures.append(f'note {note}: default strike reached the safety limiter')
                segment=x[round(.39*rate):round(.55*rate),0]
                power=np.abs(np.fft.rfft(segment*np.hanning(len(segment))))**2
                f=np.fft.rfftfreq(len(segment),1/rate)
                centroids.append(float(np.sum(f*power)/max(power.sum(),1e-30)))
                levels.append(float(np.sqrt(np.mean(segment**2))))
            print('velocity',note,'RMS',levels,'centroid',centroids)
            if not levels[0]<levels[1]<levels[2]: failures.append(f'note {note}: strike level is not ordered')
            if note<=84 and centroids[2]<centroids[0]*1.02: failures.append(f'note {note}: hard strike does not brighten')
    if failures: raise AssertionError('\n'.join(failures))
    print('PASS: approved strikes, measured velocity colour, automatic release, and residual tail')


if __name__=='__main__': main()

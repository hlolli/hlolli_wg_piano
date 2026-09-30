#!/usr/bin/env python3
"""Fit the concert grand against onset-aligned notes at several dynamics.

Requires NumPy. The runtime still contains only numbers and DSP, not samples.
Reference levels are normalized: pp/mf/ff are labels, not measured hammer speeds.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'profiles/concert_grand_a.json'
WINDOWS = ((.005,.055),(.055,.18),(.18,.5),(.8,1.3),(2.,3.))
BANDS = np.array([40,100,160,250,400,630,1000,1600,2500,4000,6300,10000,16000],float)
DYNAMICS = {'pp':.2,'mf':.65,'ff':1.0}


def read_wav(path):
    with wave.open(str(path),'rb') as f:
        rate, channels, width = f.getframerate(), f.getnchannels(), f.getsampwidth()
        frames=f.getnframes()
        raw=f.readframes(frames)
    if channels not in (1,2) or width not in (2,4):
        raise ValueError(f'{path}: expected mono/stereo PCM16 or PCM32')
    if len(raw) != frames * channels * width:
        raise ValueError(f'{path}: truncated PCM data')
    data=np.frombuffer(raw,dtype='<i2' if width==2 else '<i4').astype(float)
    data=data.reshape(-1,channels)/(32768 if width==2 else 2147483648)
    if not len(data) or not np.isfinite(data).all(): raise ValueError(f'{path}: empty/nonfinite audio')
    return rate,data


def onset(data, rate):
    size=max(1,round(.001*rate))
    power=np.mean(data**2,axis=1)
    envelope=np.convolve(power,np.ones(size)/size,'same')
    peak=float(envelope[:min(len(envelope),rate*4)].max())
    if peak<1e-14: raise ValueError('silent reference')
    indices=np.flatnonzero(envelope>peak*.08)
    return max(0,int(indices[0])-size//2)


def spectrum(data,rate,start,end):
    x=data[round(start*rate):round(end*rate)]
    if len(x)<16: raise ValueError('note is too short for timbre windows')
    window=np.hanning(len(x))
    power=np.mean(np.abs(np.fft.rfft((x-x.mean(axis=0))*window[:,None],axis=0))**2,axis=1)
    power *= 2/(len(x)*np.sum(window**2))
    return np.fft.rfftfreq(len(x),1/rate),power


def features(data,rate,note,inharmonicity=0.0,align=True):
    start=onset(data,rate) if align else 0
    data=data[start:]
    if len(data)<round(WINDOWS[-1][1]*rate): raise ValueError('need 3 seconds after onset')
    norm=float(np.mean(data[round(.005*rate):round(.18*rate)]**2))
    if norm<1e-14: raise ValueError('note attack is silent')
    band_rows=[]; harmonic_rows=[]; envelope=[]
    f0=440*2**((note-69)/12)
    for lo,hi in WINDOWS:
        f,p=spectrum(data,rate,lo,hi)
        band_rows.append([10*np.log10(max(p[(f>=a)&(f<b)].sum()/norm,1e-10)) for a,b in zip(BANDS,BANDS[1:])])
        harmonic_rows.append([10*np.log10(max(p[np.abs(f-f0*n*np.sqrt((1+inharmonicity*n*n)/(1+inharmonicity)))<max(1.5/(hi-lo),f0*.035*n)].sum()/norm,1e-10)) for n in range(1,13)])
        envelope.append(10*np.log10(max(float(np.mean(data[round(lo*rate):round(hi*rate)]**2))/norm,1e-10)))
    return {'onset_seconds':start/rate,'normalization_rms':math.sqrt(norm),
            'band_db':np.array(band_rows).tolist(),'partial_db':np.array(harmonic_rows).tolist(),
            'envelope_db':envelope,'peak':float(np.abs(data).max())}


def add_reference_confidence(reference, data, rate, note, inharmonicity=0.0):
    """Exclude targets within 12 dB of the room floor before the strike.

    Keep the recorded values unchanged. Confidence masks prevent the search
    from fitting noise as an upper partial or a long string tail.
    """
    stop = round((reference['onset_seconds'] - .05) * rate)
    if stop < round(.04 * rate):
        raise ValueError('reference needs at least 90 ms before the string attack')
    noise = data[:stop]
    norm = reference['normalization_rms']**2
    frequencies, power = spectrum(noise, rate, 0, len(noise)/rate)

    def noise_db(low, high):
        value = power[(frequencies >= low) & (frequencies < high)].sum()
        return 10*np.log10(max(value/norm, 1e-10))

    bands = np.array([noise_db(a, b) for a, b in zip(BANDS, BANDS[1:])])
    f0 = 440*2**((note-69)/12)
    partials = []
    for low, high in WINDOWS:
        row = []
        for n in range(1, 13):
            centre = f0*n*np.sqrt((1+inharmonicity*n*n)/(1+inharmonicity))
            width = max(1.5/(high-low), f0*.035*n)
            row.append(noise_db(centre-width, centre+width))
        partials.append(row)
    floor = 10*np.log10(max(float(np.mean(noise**2))/norm, 1e-10))
    reference['band_valid'] = (np.array(reference['band_db']) > bands[None,:]+12).tolist()
    reference['partial_valid'] = (np.array(reference['partial_db']) > np.array(partials)+12).tolist()
    reference['envelope_valid'] = (np.array(reference['envelope_db']) > floor+12).tolist()
    reference['noise_window_seconds'] = [0, stop/rate]
    reference['noise_floor_db'] = float(floor)


def errors(model,reference,note):
    m,r=np.array(model['band_db']),np.array(reference['band_db'])
    f0=440*2**((note-69)/12)
    active=(r>-65)&(BANDS[1:][None,:]>.8*f0)
    active &= np.array(reference.get('band_valid', np.ones_like(r, dtype=bool)))
    weights=np.array([.20,.25,.25,.20,.10])[:,None]*active
    spectral=float(np.sum(weights*np.minimum((m-r)**2,1600))/max(weights.sum(),1e-20))
    pm,pr=np.array(model['partial_db']),np.array(reference['partial_db'])
    # Compare harmonic envelopes between early and late windows, independently
    # of recording gain and a common radiation gain at that frequency.
    mask=(pr[1]>-45)&(pr[3]>-65)
    partial_valid=np.array(reference.get('partial_valid', np.ones_like(pr, dtype=bool)))
    mask &= partial_valid[1] & partial_valid[3]
    dm,dr=pm[3]-pm[1],pr[3]-pr[1]
    decay=float(np.mean(np.minimum((dm[mask]-dr[mask])**2,900))) if mask.any() else 0
    envelope_valid=np.array(reference.get('envelope_valid', [True]*len(WINDOWS)))
    delta=np.array(model['envelope_db'])-reference['envelope_db']
    envelope=float(np.mean(delta[envelope_valid]**2)) if envelope_valid.any() else 0
    return {'spectral_rmse_db':math.sqrt(spectral),'partial_decay_rmse_db':math.sqrt(decay),
            'envelope_rmse_db':math.sqrt(envelope),'loss':spectral+.15*decay+.10*envelope}


def reference_cases(manifest):
    values=json.loads(manifest.read_text())
    if values.get('schema')!='piano-timbre-references-v1': raise ValueError('unsupported reference manifest')
    cases=[]; seen=set()
    for row in values['takes']:
        if (type(row['note']) is not int or not 21 <= row['note'] <= 108 or
                row['dynamic'] not in DYNAMICS or row['split'] not in ('fit','check') or
                not 0 < row['velocity'] <= 1.25 or
                not 0 <= row.get('inharmonicity',0) <= .2):
            raise ValueError('invalid reference note, dynamic, split, velocity, or stiffness')
        identity=(row['note'],row['dynamic'])
        if identity in seen: raise ValueError('duplicate reference note and dynamic')
        seen.add(identity)
        path=(manifest.parent/row['file']).resolve()
        rate,data=read_wav(path)
        result=dict(row)
        result['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        result['features']=features(data,rate,row['note'],row.get('inharmonicity',0))
        add_reference_confidence(result['features'],data,rate,row['note'],row.get('inharmonicity',0))
        cases.append(result)
    if not cases or {r['split'] for r in cases}!={'fit','check'}: raise ValueError('need fit and check references')
    if {r['note'] for r in cases if r['split']=='fit'} & {r['note'] for r in cases if r['split']=='check'}:
        raise ValueError('fit and check pitches must be separate')
    return cases


class Renderer:
    def __init__(self,args):
        self.args=args
        self.work=args.work_dir.resolve();self.work.mkdir(parents=True,exist_ok=True)
        self.source=(ROOT/'hlolli_wg_piano.c').read_text()
        spec=importlib.util.spec_from_file_location('piano_generator',ROOT/'tools/generate_profiles.py')
        self.generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.generator)
        self.csd=ROOT/'tests/measure_note.csd'
        self.counter=0

    def compile(self,model):
        path=self.work/'candidate.json';path.write_text(json.dumps(model,allow_nan=False))
        normalized=self.generator.validate_profile(self.generator.load_json(path),path)
        text=self.generator.replace_generated_block(self.source,self.generator.generate_block(normalized))
        source=self.work/'candidate.c';source.write_text(text)
        module=self.work/('candidate.dylib' if sys.platform=='darwin' else 'candidate.so')
        cmd=[self.args.cc,'-std=c11','-O2','-fPIC','-fvisibility=hidden','-DBUILD_PLUGINS',
             '-dynamiclib' if sys.platform=='darwin' else '-shared','-I',str(self.args.include_dir),str(source),'-lm','-o',str(module)]
        subprocess.run(cmd,check=True,capture_output=True,timeout=120)
        return module

    def render(self,module,case,model):
        self.counter+=1
        output=self.work/'note.wav'
        cmd=[self.args.csound,'--opcode-lib='+str(module),'--sample-accurate','--num-threads=1','-W','-l','-o',str(output),
             '--omacro:TEST_SR='+str(case.get('sample_rate',48000)),
             '--omacro:TEST_NOTE='+str(case['note']),'--omacro:TEST_VELOCITY='+str(case['velocity']),
             '--omacro:TEST_KEY_SECONDS=3.2','--omacro:TEST_TAIL_SECONDS=0.2',str(self.csd)]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        rate,data=read_wav(output)
        if np.abs(data).max()>=.999: raise ValueError('candidate clips')
        key={**model['default_key'],**model['keys'].get(str(case['note']),{})}
        return features(data,rate,case['note'],key['inharmonicity_b'])

    def evaluate(self,model,cases,module=None):
        module=module or self.compile(model)
        results=[]
        for case in cases:
            value=self.render(module,case,model)
            results.append({'note':case['note'],'dynamic':case['dynamic'],'split':case['split'],
                            'features':value,**errors(value,case['features'],case['note'])})
        return results


def mean_loss(rows): return float(np.mean([r['loss'] for r in rows]))

def interpolate(model,anchors,field_values):
    notes=sorted(anchors)
    for midi_text,key in model['keys'].items():
        midi=int(midi_text)
        for field in field_values:
            key[field]=float(np.interp(midi,notes,[anchors[n][field] for n in notes]))


def eq_response(frequencies,centres,q,gains,sr=48000):
    z=np.exp(-2j*np.pi*np.asarray(frequencies)/sr)
    response=np.ones(len(z),complex)
    for fc,gain in zip(centres,gains):
        a=10**(gain/40);w=2*np.pi*min(fc,.42*sr)/sr;alpha=np.sin(w)/(2*q)
        response *= ((1+alpha*a)-2*np.cos(w)*z+(1-alpha*a)*z*z)/((1+alpha/a)-2*np.cos(w)*z+(1-alpha/a)*z*z)
    return 20*np.log10(np.maximum(np.abs(response),1e-12))


def fit(args,cases,renderer,model):
    base=copy.deepcopy(model)
    before=renderer.evaluate(base,cases)
    report={'method':'onset aligned; gain normalized; five time windows; 12 partial envelopes; 3 dynamics; targets at least 12 dB above pre-strike noise',
            'source_sha256':hashlib.sha256(renderer.source.encode()).hexdigest(),
            'references':[dict(row,features=row['features']) for row in cases], 'before':before,'steps':[]}
    anchors={}
    fields=['hammer_contact_min_seconds','hammer_contact_range_seconds','hammer_cutoff_base_hz',
            'hammer_cutoff_hardness_hz','hammer_filter_mix','bridge_loss_per_second']
    for note in sorted({r['note'] for r in cases if r['split']=='fit'}):
        subset=[r for r in cases if r['note']==note and r['split']=='fit']
        original=copy.deepcopy(base['keys'][str(note)])
        key=model['keys'][str(note)]
        best=mean_loss(renderer.evaluate(model,subset))
        for stage,levels in [('contact',[.22,.32,.45,.60,.80,1.0,1.25,1.6]),('cutoff',[.5,.75,1.,1.5,2.2,3.2]),('mix',[.15,.35,.55,.75]),('bridge',[.2,.5,1.,2.,3.5,5.])]:
            winner=copy.deepcopy(key);stage_loss=best
            for level in levels:
                candidate=copy.deepcopy(model);row=candidate['keys'][str(note)]
                if stage=='contact':
                    for f in fields[:2]: row[f]=original[f]*level
                elif stage=='cutoff':
                    for f in fields[2:4]: row[f]=original[f]*level
                elif stage=='mix': row['hammer_filter_mix']=level
                else: row['bridge_loss_per_second']=level
                # Later tuning starts from the accepted model. Wider searches
                # must still respect the same data bounds as the runtime.
                if (row['hammer_contact_min_seconds'] > .008 or
                        row['hammer_contact_range_seconds'] > .008 or
                        row['hammer_cutoff_base_hz'] > 100000 or
                        row['hammer_cutoff_base_hz'] < 100 or
                        row['hammer_cutoff_hardness_hz'] > 100000):
                    continue
                loss=mean_loss(renderer.evaluate(candidate,subset))
                if loss<stage_loss: stage_loss=loss;winner=copy.deepcopy(row)
            key.update(winner);best=stage_loss
            step={'note':note,'stage':stage,'loss':best,'parameters':{f:key[f] for f in fields}}
            report['steps'].append(step)
            print(json.dumps(step),flush=True)
        anchors[note]=copy.deepcopy(key)
    interpolate(model,anchors,fields)
    hammer=renderer.evaluate(model,cases);report['after_hammer']=hammer
    # Broad radiation correction, with an intercept to keep gain separate from
    # timbre. Ridge regularization and +/-12 dB limits prevent narrow inverses.
    centres=model['radiation']['centres_hz'];q=model['radiation']['q']
    band_centres=np.sqrt(BANDS[:-1]*BANDS[1:])
    basis=np.stack([eq_response(band_centres,centres,q,[1 if j==i else 0 for j in range(6)]) for i in range(6)],axis=1)
    eq_anchors={}
    for note in sorted(anchors):
        subset=[c for c in cases if c['note']==note and c['split']=='fit']
        current=[r for r in hammer if r['note']==note and r['split']=='fit']
        matrix=[];target=[]
        for c,r in zip(subset,current):
            desired=np.array(c['features']['band_db']);actual=np.array(r['features']['band_db'])
            valid=np.array(c['features'].get('band_valid', np.ones_like(desired, dtype=bool)))
            for w in (0,1,2):
                for band in range(len(band_centres)):
                    if valid[w,band] and desired[w,band]>-50 and BANDS[band+1]>.8*440*2**((note-69)/12):
                        matrix.append([*basis[band],1]);target.append(desired[w,band]-actual[w,band])
        matrix=np.asarray(matrix).reshape(-1, 7);target=np.asarray(target)
        penalty=np.diag([2.0]*6+[.001])
        gains=np.linalg.solve(matrix.T@matrix+penalty,matrix.T@target)[:6]
        gains=np.clip(gains,-12,12)
        current_gains=np.array(model['radiation']['key_gain_db'][note-model['midi_min']])
        best=mean_loss(current);chosen=current_gains.copy()
        for scale in (.5,1.0):
            candidate=copy.deepcopy(model)
            trial_gains=np.clip(current_gains+gains*scale,-12,12)
            candidate['radiation']['key_gain_db'][note-model['midi_min']]=trial_gains.tolist()
            rows=renderer.evaluate(candidate,subset);loss=mean_loss(rows)
            if loss<best: best=loss;chosen=trial_gains
        eq_anchors[note]=chosen
        print(json.dumps({'note':note,'stage':'radiation','loss':best,'gains_db':chosen.tolist()}),flush=True)
    notes=sorted(eq_anchors)
    for key in range(model['key_count']):
        midi=key+model['midi_min']
        model['radiation']['key_gain_db'][key]=[float(np.interp(midi,notes,[eq_anchors[n][b] for n in notes])) for b in range(6)]
    after=renderer.evaluate(model,cases);report['after']=after
    report['summary']={split:{label:mean_loss([r for r in rows if r['split']==split]) for label,rows in [('before',before),('after_hammer',hammer),('after',after)]} for split in ('fit','check')}
    # Never publish a fit that merely improves its training pitches.
    accepted=all(report['summary'][s]['after']<report['summary'][s]['before'] for s in ('fit','check'))
    report['accepted']=accepted;report['renders']=renderer.counter
    args.report.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    if not accepted: raise ValueError('fit did not improve both fit and check notes; model was not written')
    model['provenance']['notes'] += ' Hammer contact, filtering and shared bridge loss, plus broad per-key radiation EQ, were fitted to onset-aligned Iowa pp/mf/ff note spectra and partial envelopes; this is not an isolated soundboard or measured hammer-speed fit. See fit/concert-grand-timbre.json.'
    args.output.write_text(json.dumps(model,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report['summary'],indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['fit','measure'])
    parser.add_argument('--references',type=Path,required=True)
    parser.add_argument('--model',type=Path,default=MODEL)
    parser.add_argument('--module',type=Path)
    parser.add_argument('--csound',default='csound')
    parser.add_argument('--cc',default='cc')
    parser.add_argument('--include-dir',type=Path)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.command=='fit' and (args.output is None or args.include_dir is None): parser.error('fit needs --output and --include-dir')
    if args.command=='measure' and args.module is None: parser.error('measure needs --module')
    cases=reference_cases(args.references.resolve())
    model=json.loads(args.model.read_text());renderer=Renderer(args)
    if args.command=='fit': fit(args,cases,renderer,model)
    else:
        rows=renderer.evaluate(model,cases,args.module.resolve())
        args.report.write_text(json.dumps({'results':rows,'references':cases},indent=2,allow_nan=False)+'\n')
        print('mean loss',mean_loss(rows),'renders',renderer.counter)

if __name__=='__main__':
    main()

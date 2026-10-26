import argparse
import csv
import gzip
import itertools
import json
import math
from pathlib import Path
import statistics
import boot
from filtered import P


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args()
    grid=P['screen'];methods=[('lqr','none')]+list(itertools.product(P['profiles'],P['sources']))+[('nominal_psf','ppo')]
    rows=[];severe=0
    for pair in range(3):
        shard=args.run/f'pair-{pair}'
        with (shard/'episodes.csv').open() as handle:batch=list(csv.DictReader(handle))
        keys=[(int(r['speed']),r['path'],int(r['mirror']),r['scenario'],r['profile'],r['source']) for r in batch]
        expected={a+b for a in itertools.product(grid['speeds'],grid['paths'],grid['mirrors'],grid['scenarios']) for b in methods}
        assert len(keys)==len(set(keys))==len(expected) and set(keys)==expected
        def read(key):
            with gzip.open(shard/'traces'/('-'.join(map(str,key))+'.csv.gz'),'rt') as h:return list(csv.DictReader(h))
        for row,key in zip(batch,keys):
            trace=read(key);n=len(trace);horizon=int(row['scheduled']);profile=row['profile']
            rmse=math.sqrt((sum(float(r['lateral_error'])**2 for r in trace)+(horizon-n)*6.25)/horizon)
            heading=math.sqrt(sum(float(r['heading_error'])**2 for r in trace)/n)
            rate=math.sqrt(sum(float(r['steering_rate'])**2 for r in trace)/n)
            assert abs(rmse-float(row['rmse_m']))<1e-12
            assert abs(heading-float(row['heading_rmse_rad']))<1e-12
            assert abs(rate-float(row['rate_rms_rad_s']))<1e-12
            previous=0.
            for r in trace:
                command=float(r['command']);weight=float(r['weight']);filtered=float(r['filtered_residual'])
                assert abs(command)<=.5000001 and abs(float(r['steering_rate']))<=.3500001
                assert all(float(r[f'obs{i}'])==0 for i in (14,15,16,17,19))
                if profile in ('age_filtered','predictive_filtered','preview_filtered'):
                    if r['reason'] in ('missing','age','sequence','nonfinite','envelope','prediction_invalid'):
                        assert filtered==0. and weight==0.
                    else:
                        expected_filter=previous+(1-math.exp(-.1))*(float(r['packet_residual'])-previous)
                        assert abs(filtered-expected_filter)<1e-12
                    previous=filtered
                if profile!='nominal_psf':
                    assert abs(command-max(-.5,min(.5,float(r['baseline'])+weight*filtered)))<1e-12
                if weight>0:assert r['packet_age_s'] and 0<=float(r['packet_age_s'])<.05
            if row['scenario']=='delay100' and profile!='lqr':
                base=read(key[:4]+('lqr','none'));assert len(base)==n
                for a,b in zip(trace,base):assert all(a[k]==b[k] for k in ('x','y','heading','command','actuator'))
                severe+=1
        rows.extend(batch)
    assert len(rows)==P['episodes']
    mean=lambda rr,k:statistics.mean(float(r[k]) for r in rr)
    metrics={}
    base=[r for r in rows if r['profile']=='lqr']
    for profile,source in methods:
        group=[r for r in rows if r['profile']==profile and r['source']==source]
        value=mean(group,'rmse_m')
        metrics[f'{profile}/{source}']=dict(rmse_m=value,gain_vs_lqr_pct=100*(mean(base,'rmse_m')-value)/mean(base,'rmse_m'),
            heading_rmse_rad=mean(group,'heading_rmse_rad'),rate_rms_rad_s=mean(group,'rate_rms_rad_s'),
            movement_rad=mean(group,'movement_rad'),survived=sum(r['survived']=='True' for r in group),episodes=len(group),
            psf_calls=sum(int(r['psf_calls']) for r in group),psf_fallbacks=sum(int(r['psf_fallbacks']) for r in group))
    screens={};eligible=[]
    baseline=metrics['lqr/none']
    for profile in P['profiles'][1:]:
        c=metrics[f'{profile}/ppo'];reasons=[]
        for reference in ['lqr/none']+[f'{profile}/{s}' for s in ('negative','positive','student')]:
            b=metrics[reference]
            if c['rmse_m']>.99*b['rmse_m']:reasons.append('lacks1% gain vs '+reference)
            if c['survived']<b['survived']:reasons.append('survival vs '+reference)
        for key in ('heading_rmse_rad','rate_rms_rad_s'):
            if c[key]>1.05*baseline[key]:reasons.append(key+' exceeds5% LQR tradeoff')
        seed_gains=[]
        for pair in range(3):
            a=[r for r in rows if int(r['pair'])==pair and r['profile']==profile and r['source']=='ppo']
            b=[r for r in rows if int(r['pair'])==pair and r['profile']==profile and r['source']=='student']
            gain=100*(mean(b,'rmse_m')-mean(a,'rmse_m'))/mean(b,'rmse_m');seed_gains.append(gain)
            if gain<=0:reasons.append(f'pair{pair} no student gain')
        a=[r for r in rows if r['profile']==profile and r['source']=='ppo' and r['scenario']=='nominal']
        b=[r for r in base if r['scenario']=='nominal']
        if mean(a,'rmse_m')>1.02*mean(b,'rmse_m'):reasons.append('nominal >2% worse than LQR')
        screens[profile]=dict(eligible=not reasons,reasons=reasons,paired_seed_gains_vs_student_pct=seed_gains)
        if not reasons:eligible.append(profile)
    selected=min(eligible,key=lambda name:(metrics[f'{name}/ppo']['rmse_m'],P['profiles'].index(name))) if eligible else None
    decision=dict(selected=selected,profiles=screens,episodes=len(rows),severe_exact_pairs=severe,
        raw_metrics_and_causal_filter_verified=True,reserved_confirmation='unopened; independent10ms timing pass also required')
    (args.run/'summary.json').write_text(json.dumps(metrics,indent=2)+'\n')
    (args.run/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    with (args.run/'episodes.csv').open('w',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)
    lines=['# Frozen follow-up: same-gain attribution and smoothing','',
        '| Profile/source | RMSE m | Gain vs LQR | Heading rad | Rate RMS rad/s | Survival |',
        '|---|---:|---:|---:|---:|---:|']
    for name,m in metrics.items():lines.append(f'| {name} | {m["rmse_m"]:.6f} | {m["gain_vs_lqr_pct"]:.3f}% | {m["heading_rmse_rad"]:.6f} | {m["rate_rms_rad_s"]:.6f} | {m["survived"]}/{m["episodes"]} |')
    lines+=['',f'Selected eligible profile: {selected}.', '',
        'Nominal PSF is the disclosed Eq5/Algorithm1 linear specialization with terminal equilibrium. Its model certainty, fixed-curvature/dynamics and perfect-state assumptions do not hold exactly on this nonlinear noisy plant. Solver infeasibility and uncertified LQR fallbacks are retained; no transfer of the paper safety theorem or superiority to its full uncertainty-aware algorithm is claimed.', '',
        'No new training or after-outcome tuning. Same-gain controls identify whether any benefit comes from the proposal or from supervisory filtering. Previous failed campaigns remain unchanged.']
    (args.run/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps(decision,indent=2))


if __name__=='__main__':main()

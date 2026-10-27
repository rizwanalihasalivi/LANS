"""One fixed explicit-compensation ablation with frozen NumPy actors."""
import boot7
import argparse
import csv
import gzip
import itertools
import json
import math
import sys
sys.path.insert(0,str(boot7.ROOT/'tools/reviewer_v5'))
from history5 import HistoryEnv
from supervisor import observation
from compensation import CompensatedController
from laptop_full_controller import load_portable
import numpy as np

P=json.loads((boot7.HERE/'protocol.json').read_text())

class CompEnv(HistoryEnv):
    def __init__(self,case,source,service):self.configured_service=service;super().__init__(case=case,source=source,history=True)
    def reset(self,**kwargs):
        super().reset(**kwargs);self.service=self.configured_service
        if self.source=='compensated':
            self.ctrl=CompensatedController();self.ctrl.previews=self.obs[6:9].astype(float)*.02
            self.obs=observation(self.state,self.estimate,self.measured_speed,self.ctrl.previews,self.ctrl,self.tick*.01);self._history()
        return self.obs.copy(),{}
    def _sense(self):
        super()._sense()
        if hasattr(self.ctrl,'compensator') and self.ctrl.packet is not None:
            seq,observed,_=self.ctrl.packet
            self.ctrl.compensator.observe(int(seq),max(0.,self.tick*.01-observed))

def episode(case,source,service,model,portable,path):
    env=CompEnv(case,source,service);obs,_=env.reset();rows=[]
    while True:
        query=None;meta=None;residual=0.
        if env.ctrl.pending is None:
            query=obs.copy()
            if source=='compensated':query,meta=env.ctrl.prepare_query(query,env.estimate,env.state[5],env.measured_speed,env.ctrl.previews,env.gain)
            if source!='lqr':residual=[-.08,-.04,0.,.04,.08][int(portable.logits(model,query[None,:]).argmax(1)[0])]
        obs,_,failed,done,row=env.step_residual(residual)
        row.update(query_json=json.dumps(query.tolist()) if row['submitted'] else '',query_metadata_json=json.dumps(meta) if meta is not None else '')
        rows.append(row)
        if failed or done:break
    with gzip.open(path,'wt',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    h=env.horizon;n=len(rows)
    return dict(steps=n,scheduled=h,survived=not failed,rmse_m=math.sqrt((sum(r['lateral_error']**2 for r in rows)+(h-n)*6.25)/h),
        heading_rmse_rad=math.sqrt(sum(r['heading_error']**2 for r in rows)/n),rate_rms_rad_s=math.sqrt(sum(r['steering_rate']**2 for r in rows)/n),
        active_ticks=sum(r['weight']>0 for r in rows),compensated_queries=sum(bool(r['query_metadata_json']) for r in rows))

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot7.Path,required=True);a=p.parse_args();out=a.run
    assert not (out/'episodes.csv').exists(),'Do not overwrite or retry recorded outcomes'
    traces=out/'traces';traces.mkdir();portable=load_portable(out/'actor');portable.golden_check();rows=[];cfg=P['development']
    with (out/'episodes.csv').open('w',newline='') as stream:
        writer=None
        for pair,seed in enumerate(cfg['seeds']):
            model=portable.load(seed)
            for sign,service in itertools.product(cfg['mirrors'],cfg['services_s']):
                noise=cfg['noise_base']+pair*10000+cfg['services_s'].index(service)*100
                for source in cfg['sources']:
                    name=f'{seed}-{sign}-{round(service*1000)}-{source}'
                    metrics=episode((20,'dlc220',sign,'nominal',noise),source,service,model,portable,traces/f'{name}.csv.gz')
                    row=dict(seed=seed,pair=pair,mirror=sign,service_s=service,source=source,noise_id=noise,trace=name+'.csv.gz',**metrics)
                    if writer is None:writer=csv.DictWriter(stream,fieldnames=row,lineterminator='\n');writer.writeheader()
                    writer.writerow(row);stream.flush();rows.append(row)
                print(seed,sign,service,len(rows),flush=True)
    (out/'generated.json').write_text(json.dumps(dict(episodes=len(rows),new_training_steps=0),indent=2)+'\n')

if __name__=='__main__':main()

"""Real PPO-export worker, same new supervisor, actual 1s stalls and contention."""
import common
import json
from pathlib import Path
import sys
import realtime_optimized as runtime
from runtime_adapter import PredictiveGateAdapter


if __name__=='__main__':
    runtime.Gate=PredictiveGateAdapter
    runtime.CASES['delay1000']=1.
    runtime.main()
    output=Path(sys.argv[sys.argv.index('--output')+1])
    file=output/'summary.json';summary=json.loads(file.read_text())
    summary['limitations']=[s for s in summary['limitations'] if 'teacher labels' not in s]
    summary['limitations'].append('Actor is exact25k causal PPO export; this is not the old supervised student despite reused worker artifact naming.')
    summary['supervisor']='reviewer-causal-v1 predictive supervisor via runtime_adapter'
    for episode in summary['episodes']:
        if episode['case']=='delay1000':
            assert episode['paired_lqr_max_command_difference']==0
            assert episode['active_ticks']==0
    file.write_text(json.dumps(summary,indent=2)+'\n')

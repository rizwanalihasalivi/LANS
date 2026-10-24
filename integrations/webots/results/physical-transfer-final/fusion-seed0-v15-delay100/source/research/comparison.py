"""Development-selected common LQR setting, frozen before held-out comparisons."""
import json
from pathlib import Path
import core

COMPARISON=json.loads(Path(__file__).with_name('comparison-protocol.json').read_text())

def configure_lqr():
    core.PROTOCOL['lqr_R']=COMPARISON['lqr_R']
    core.PROTOCOL['lqr_Q']=COMPARISON['lqr_Q']
    core.GAINS.update({v:core.gain(v) for v in (15,20,25)})

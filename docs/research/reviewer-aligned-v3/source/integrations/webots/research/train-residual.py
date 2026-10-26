"""Fresh residual training with the development-selected baseline; full policies stay frozen."""
import hashlib,json,sys
from pathlib import Path
from comparison import configure_lqr
from train import main

if __name__=='__main__':
    if sys.argv[sys.argv.index('--role')+1]!='residual':raise ValueError('residual role required')
    configure_lqr()
    main()
    out=Path(sys.argv[sys.argv.index('--output')+1])
    comparison=Path(__file__).with_name('comparison-protocol.json')
    (out/'comparison-protocol.json').write_bytes(comparison.read_bytes())
    metadata=json.loads((out/'complete.json').read_text())
    metadata['comparison_protocol_sha256']=hashlib.sha256(comparison.read_bytes()).hexdigest()
    metadata['baseline_lqr_R']=100.
    metadata['source_sha256'].update({f:hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest() for f in ['train-residual.py','comparison.py']})
    (out/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n')

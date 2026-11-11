"""Four30s scalar-dispatch/GUI development cases, with every outcome retained."""
from pathlib import Path
from .native_loop import main


if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]/'results/v8-four-gates'
    for name,args in (('native-scalar-v1',()),('native-scalar-minimized-v1',('--minimize',))):
        main(output=root/name,seconds=30.,selected_variants=('c-loop',),extra_args=args)

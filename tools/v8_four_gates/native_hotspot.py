"""Two30-second exposed hotspot diagnostics; timings include profiling cost."""
from pathlib import Path
from .native_loop import main


if __name__=='__main__':
    main(output=Path(__file__).resolve().parents[2]/'results/v8-four-gates/native-hotspot-v1',seconds=30.,selected_variants=('c-loop',),entry_name='native_hotspot_entry.py')

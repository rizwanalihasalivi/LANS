from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent
for path in (RESEARCH/'revision7',RESEARCH/'revision5',RESEARCH,RESEARCH/'revision2'):
    if str(path) not in sys.path:sys.path.append(str(path))

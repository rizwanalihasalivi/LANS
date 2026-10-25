from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent
for path in [RESEARCH/'revision5',RESEARCH,RESEARCH/'revision2',RESEARCH/'revision3',RESEARCH/'revision4']:
    if str(path) not in sys.path:sys.path.append(str(path))

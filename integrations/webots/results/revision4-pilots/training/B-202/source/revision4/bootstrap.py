from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent
ROOT=RESEARCH.parent
for path in [RESEARCH,RESEARCH/'revision2',RESEARCH/'revision3']:
    if str(path) not in sys.path:sys.path.append(str(path))

from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.append(str(ROOT/'tools/reviewer_campaign'))
import common  # frozen causal interfaces, numerical libraries and thread limits
sys.path.append(str(ROOT/'integrations/webots/research/revision6'))

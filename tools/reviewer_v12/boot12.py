"""Versioned audit; previous evidence and its source dependencies stay frozen."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/reviewer_v11'))
sys.path.insert(0, str(ROOT / 'tools/reviewer_v6'))
import boot11


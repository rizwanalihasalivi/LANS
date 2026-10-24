"""Run corrected physical-path, single-fusion and observation contract checks."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent/'tests/test_controller_remediation.py'), run_name='__main__')

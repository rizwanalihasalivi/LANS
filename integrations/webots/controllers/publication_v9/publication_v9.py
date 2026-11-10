"""Webots entry point; guarded to keep multiprocessing child imports inert."""
import json,os,sys,traceback
from pathlib import Path

ROOT=Path(os.environ['LANS_ROOT'])
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from vehicle import Driver
    from tools.unified_control_v9.native_adapter import native_main
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text())
    driver=Driver()
    try:native_main(driver,case)
    except BaseException:
        (Path(case['output'])/'failure.txt').write_text(traceback.format_exc())
        traceback.print_exc();driver.simulationQuit(1)
    else:driver.simulationQuit(0)

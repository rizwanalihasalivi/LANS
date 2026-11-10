"""Copied into generated Webots projects; spawning workers has no side effects."""
import json,os,sys,traceback
from pathlib import Path

sys.path.insert(0,os.environ['LANS_ROOT'])

if __name__=='__main__':
    from vehicle import Driver
    from tools.v8_reliability.native_adapter import native_main
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text())
    driver=Driver()
    try:native_main(driver,case)
    except BaseException:
        (Path(case['output'])/'failure.txt').write_text(traceback.format_exc())
        traceback.print_exc();driver.simulationQuit(1)
    else:driver.simulationQuit(0)

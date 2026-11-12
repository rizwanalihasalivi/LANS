"""Webots-only actual driver entry; safe when policy workers are spawned."""
import json,os,traceback
from pathlib import Path

if __name__=='__main__':
    from vehicle import Driver
    from tools.ppo_complete_v13.native_adapter import native_main
    driver=Driver();case=json.loads(Path(os.environ['LANS_NATIVE_CASE']).read_text())
    try:native_main(driver,case)
    except BaseException:
        Path(case['output'],'failure.txt').write_text(traceback.format_exc());traceback.print_exc();driver.simulationQuit(1)
    else:driver.simulationQuit(0)

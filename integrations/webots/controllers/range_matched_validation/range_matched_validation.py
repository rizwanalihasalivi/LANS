"""Reuse the frozen native controller; adapt only new-policy output units."""
import csv,hashlib,importlib.util,json,os,sys,traceback
from pathlib import Path
ROOT=Path(os.environ['LANS_INTEGRATION_ROOT'])
sys.path[:0]=[str(ROOT/'research/revision3'),str(ROOT/'research')]
from mapping import map_worker_packet
from worker import PolicyWorker
spec=importlib.util.spec_from_file_location('frozen_native_controller',ROOT/'controllers/gated_validation/gated_validation.py')
controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)

class RangeWorker(PolicyWorker):
    def __init__(self,model_path,delay_s=0):
        path=Path(model_path);meta=json.loads((path.parent/'complete.json').read_text())
        assert meta['training_profile']=='range_matched_residual_v3' and meta['residual_scale_rad']==.08 and meta['steps']==1000000
        assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['policy_sha256']
        super().__init__(model_path,delay_s)
        try:
            case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text())
            self.mapping_log=(Path(case['output'])/'residual-packets.csv').open('w',newline='',buffering=1)
        except BaseException:
            super().close()
            raise
        self.writer=csv.writer(self.mapping_log,lineterminator='\n');self.writer.writerow(['sequence','observation_time_s','availability_time_s','legacy_encoded_rad','mapped_residual_rad'])
    def poll(self,t_sim):
        raw=super().poll(t_sim);mapped=map_worker_packet(raw)
        if mapped is not None:
            assert abs(mapped['angle_rad'])<=.08000001
            self.writer.writerow([mapped['sequence'],mapped['t_observation_s'],mapped['t_available_sim_s'],raw['angle_rad'],mapped['angle_rad']])
        return mapped
    def close(self):
        try:super().close()
        finally:self.mapping_log.close()

controller.PolicyWorker=RangeWorker
if __name__=='__main__':
    d=controller.Driver()
    try:controller.main(d)
    except Exception:
        Path(os.environ['LANS_CASE_CONFIG']).with_suffix('.failure.txt').write_text(traceback.format_exc());traceback.print_exc();d.simulationQuit(1)
    else:d.simulationQuit(0)

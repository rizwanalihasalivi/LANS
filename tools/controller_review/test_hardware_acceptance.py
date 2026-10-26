import unittest
from hardware_acceptance import assess

class EvidenceChecks(unittest.TestCase):
    def test_simulation_cannot_be_presented_as_hardware(self):
        for kind in ('simulation','native_webots',None):
            with self.assertRaisesRegex(ValueError,'physical target-hardware'):assess({'trace_kind':kind},[],b'')
    def test_empty_or_unproven_device_cannot_pass(self):
        with self.assertRaisesRegex(ValueError,'metadata'):assess({'trace_kind':'target_hardware'},[],b'')



# All rows below are synthetic unit-test fixtures, never hardware evidence.
class SyntheticArithmeticChecks(unittest.TestCase):
    def fixture(self):
        import hashlib
        from hardware_acceptance import REQUIRED_SCENARIOS
        meta=dict(trace_kind='target_hardware',device_id='unit-test-fixture-not-physical',cpu='fixture',os='fixture',
            controller_commit='fixture',firmware_id='fixture',clock_calibration_record='fixture',
            csv_sha256=hashlib.sha256(b'fixture').hexdigest(),timestamps_same_monotonic_domain=True,
            clock_uncertainty_ns=0,physical_acknowledgements=True)
        rows=[]
        for scenario in sorted(REQUIRED_SCENARIOS):
            for _ in range(1000):
                i=len(rows);t=1_000_000_000+i*10_000_000
                rows.append(dict(scenario=scenario,control_sequence=i,control_release_ns=t,
                    control_deadline_ns=t+10_000_000,current_sensor_ns=t,command_ns=t+500_000,
                    ack_ns=t+1_000_000,encoder_ns=t+1_000_001,actuator_angle_rad=0.,
                    learned_weight=0.,command_rad=.02,lqr_rad=.02,packet_sequence=1,
                    packet_observed_ns=t,request_ns=t+100, infer_start_ns=t+200,infer_end_ns=t+300,
                    worker_healthy='0' if scenario=='worker_crash' else '1'))
        return meta,rows
    def test_valid_arithmetic_is_not_vehicle_certification(self):
        meta,rows=self.fixture();result=assess(meta,rows,b'fixture')
        self.assertTrue(result['trace_checks_pass']);self.assertFalse(result['vehicle_readiness_certified'])
    def test_negative_clock_uncertainty_is_rejected(self):
        meta,rows=self.fixture();meta['clock_uncertainty_ns']=-1
        with self.assertRaisesRegex(ValueError,'uncertainty'):assess(meta,rows,b'fixture')
    def test_stale_learned_authority_rejects_trace(self):
        meta,rows=self.fixture();rows[0]['packet_observed_ns']-=60_000_000
        rows[0]['learned_weight']=.1;rows[0]['command_rad']=.03
        result=assess(meta,rows,b'fixture');self.assertFalse(result['trace_checks_pass'])
        self.assertEqual(result['stale_authority_violations'],1)

if __name__=='__main__':unittest.main()

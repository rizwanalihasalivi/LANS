"""Native stage authorization, grid, raw metric and private-world contracts."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import native13


class NativeContracts(unittest.TestCase):
    def proof_bundle(self, folder):
        candidate=dict(variant=2,residual_rad=.04)
        dev=folder/'development.json';reserved=folder/'reserved.json'
        name='balanced_light_fixed_p004'
        dev.write_text(json.dumps(dict(native_candidate=candidate,selected_candidate=name,
            phase='development',protocol=native13.P,assessments={name:dict(eligible=True)})))
        reserved.write_text(json.dumps(dict(native_candidate=candidate,selected_candidate=name,
            phase='reserved',protocol=native13.P,verified=True,confirmed=True,selection_sha256=native13.sha(dev))))
        value=dict(native_authorized=True,development_pass=True,reserved_confirmation_pass=True,
                   selected=candidate,source_commit='a'*40,
                   source_sha256={'revision13/gate13.py':'b'*64,'revision13/dynamics13.py':'c'*64},
                   development_selection_path=dev.name,development_selection_sha256=native13.sha(dev),
                   reserved_verification_path=reserved.name,reserved_verification_sha256=native13.sha(reserved))
        path=folder/'authorization.json';path.write_text(json.dumps(value))
        return path,value,dev,reserved

    def test_requires_passing_both_stages_and_matching_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,value,dev,reserved=self.proof_bundle(Path(tmp))
            checked,proofs=native13.validate_selection(path,verify_checkout=False)
            self.assertEqual(checked,value);self.assertEqual(set(proofs),{'development_selection','reserved_verification'})
            for key in ('native_authorized','development_pass','reserved_confirmation_pass'):
                altered=copy.deepcopy(value);altered[key]=False;path.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError,key):native13.validate_selection(path,verify_checkout=False)
            path.write_text(json.dumps(value));proof=json.loads(reserved.read_text());proof['confirmed']=False
            reserved.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError,'changed reserved'):native13.validate_selection(path,verify_checkout=False)
            value['reserved_verification_sha256']=native13.sha(reserved);path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'did not pass'):native13.validate_selection(path,verify_checkout=False)

    def test_cannot_replace_selected_method_or_load_a_learned_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,value,dev,reserved=self.proof_bundle(Path(tmp))
            proof=json.loads(dev.read_text());proof['selected_candidate']='balanced_light_student'
            dev.write_text(json.dumps(proof))
            value['development_selection_sha256']=native13.sha(dev);path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'selected method mismatch'):native13.validate_selection(path,verify_checkout=False)
        for candidate in ({'variant':1,'residual_rad':.04},{'variant':2,'residual_rad':.08},
                          {'variant':True,'residual_rad':.04},{'variant':2,'residual_rad':.04,'policy':'model.pt'}):
            with self.assertRaises(ValueError):native13.candidate_name(candidate)

    def test_claimed_passing_proofs_require_phase_protocol_eligibility_and_hash_link(self):
        mutations = [
            ('development', 'phase', 'confirmation', 'phase mismatch'),
            ('development', 'protocol', {}, 'protocol mismatch'),
            ('development', 'assessments', {}, 'not eligible'),
            ('development', 'assessments', {'balanced_light_fixed_p004': {'eligible': False}}, 'not eligible'),
            ('reserved', 'phase', 'development', 'phase mismatch'),
            ('reserved', 'protocol', {}, 'protocol mismatch'),
            ('reserved', 'verified', False, 'not verified'),
            ('reserved', 'selected_candidate', 'balanced_medium_fixed_p004', 'selected method mismatch'),
            ('reserved', 'selection_sha256', 'd'*64, 'does not confirm this development'),
        ]
        for stage, key, replacement, error in mutations:
            with self.subTest(stage=stage, key=key, replacement=replacement), tempfile.TemporaryDirectory() as tmp:
                path, value, development, reserved = self.proof_bundle(Path(tmp))
                proof_path = development if stage == 'development' else reserved
                proof = json.loads(proof_path.read_text()); proof[key] = replacement
                proof_path.write_text(json.dumps(proof))
                label = 'development_selection' if stage == 'development' else 'reserved_verification'
                value[label+'_sha256'] = native13.sha(proof_path)
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, error):
                    native13.validate_selection(path, verify_checkout=False)

    def test_full_grid_mirrors_noise_not_constant_sign(self):
        values=dict(native13.cases(dict(variant=3,residual_rad=-.04)))
        self.assertEqual(len(values),48)
        identities=set()
        for name,case in values.items():
            identities.add((case['repetition'],case['speed'],case['path_sign'],case['scenario'],case['mode']))
            other=values[name.replace('-signp-','-signm-') if '-signp-' in name else name.replace('-signm-','-signp-')]
            self.assertEqual(case['seed'],other['seed']);self.assertEqual(case['residual_rad'],other['residual_rad'])
            self.assertEqual(case['service_ticks'],10 if case['scenario']=='latency100' else 0)
        self.assertEqual(len(identities),48)

    def test_raw_metrics_include_initial_increment_and_failure_tail(self):
        rows=[]
        for i,(error,heading,delta,inc) in enumerate(((.3,.1,.002,.002),(.4,.2,.001,-.001))):
            rows.append(dict(error_m=error,heading_error_rad=heading,command_rad=.03,
                             actuator_rad=delta,actuator_increment_rad=inc,actuator_rate_rad_s=inc/.01,
                             measured_wheel_increment_rad=inc/2,measured_wheel_rate_rad_s=inc/.02,
                             weight=.1 if i==0 else 0.,packet_age_s=.02))
        result=native13.summarize_records(rows,dict(duration=.04),'tracking_envelope')
        self.assertAlmostEqual(result['rmse_m'],(.125)**.5)
        self.assertAlmostEqual(result['penalized_rmse_m'],((.09+.16+2*6.25)/4)**.5)
        self.assertAlmostEqual(result['heading_rmse_rad'],(.025)**.5)
        self.assertAlmostEqual(result['actuator_rate_rms_rad_s'],(.025)**.5)
        self.assertAlmostEqual(result['actuator_total_variation_rad'],.003)
        self.assertAlmostEqual(result['measured_wheel_total_variation_rad'],.0015)
        self.assertEqual(result['steps'],2);self.assertEqual(result['scheduled_steps'],4);self.assertFalse(result['survived'])

    def native_aggregate(self):
        rows, severe = [], []
        for name, case in native13.cases(dict(variant=2, residual_rad=.04)):
            active_selected = case['mode'] == 'selected' and case['scenario'] != 'latency100'
            rows.append(dict(name=name, repetition=case['repetition'], speed=case['speed'],
                sign=case['path_sign'], scenario=case['scenario'], method=case['mode'], survived=True,
                penalized_rmse_m=.097 if active_selected else .1,
                heading_rmse_rad=.103 if active_selected else .1,
                actuator_rate_rms_rad_s=.1, actuator_total_variation_rad=1.,
                measured_wheel_rate_rms_rad_s=.11 if active_selected else .1,
                measured_wheel_total_variation_rad=1.1 if active_selected else 1.))
            if case['mode'] == 'lqr' and case['scenario'] == 'latency100':
                severe.append(dict(repetition=case['repetition'], speed=case['speed'],
                    sign=case['path_sign'], exact=True, same_length=True))
        return rows, severe

    def test_native_pass_permits_teacher_only_and_uses_measured_smoothness(self):
        rows, severe = self.native_aggregate()
        assessment = native13.assess_native(rows, severe, bounds_verified=True)
        self.assertTrue(assessment['confirmed'])
        self.assertTrue(all(assessment['native_confirmation_checks'].values()))
        self.assertAlmostEqual(assessment['overall_lateral_reduction_percent'], 2.)
        self.assertEqual(assessment['next_action'], 'teacher_headroom_check')
        self.assertFalse(assessment['automatic_training_authorized'])
        for field, check, value in (
                ('measured_wheel_rate_rms_rad_s', 'actual_mean_wheel_rate_budget', .2),
                ('measured_wheel_total_variation_rad', 'actual_mean_wheel_tv_budget', 2.)):
            altered = copy.deepcopy(rows)
            for row in altered:
                if row['method'] == 'selected' and row['scenario'] != 'latency100': row[field] = value
            result = native13.assess_native(altered, severe, bounds_verified=True)
            self.assertFalse(result['native_confirmation_checks'][check])
            self.assertFalse(result['confirmed'])
            self.assertEqual(result['next_action'], 'stop_after_native_confirmation')
            self.assertTrue(all(row['actuator_rate_rms_rad_s'] == .1 and row['actuator_total_variation_rad'] == 1. for row in altered))

    def test_native_tradeoff_survival_bounds_and_fallback_fail_closed(self):
        mutations = [
            ('penalized_rmse_m', .0999, None, 'overall_lateral_reduction_at_least_1_percent'),
            ('penalized_rmse_m', .1001, 'nominal', 'nominal_lateral_preserved'),
            ('heading_rmse_rad', .12, None, 'overall_heading_budget'),
            ('survived', False, 'nominal', 'all_paired_survivors'),
        ]
        for field, value, region, check in mutations:
            with self.subTest(check=check):
                rows, severe = self.native_aggregate()
                for row in rows:
                    if row['method'] == 'selected' and row['scenario'] != 'latency100' and (region is None or row['scenario'] == region):
                        row[field] = value
                result = native13.assess_native(rows, severe, bounds_verified=True)
                self.assertFalse(result['native_confirmation_checks'][check]); self.assertFalse(result['confirmed'])
        rows, severe = self.native_aggregate()
        result = native13.assess_native(rows, severe, bounds_verified=False)
        self.assertFalse(result['confirmed']);self.assertFalse(result['native_confirmation_checks']['commanded_actuator_bounds_verified'])
        severe[0]['exact'] = False
        result = native13.assess_native(rows, severe, bounds_verified=True)
        self.assertFalse(result['confirmed']);self.assertFalse(result['native_confirmation_checks']['severe_delay_exact_fallback'])
        with self.assertRaisesRegex(ValueError, 'complete unique paired grid'):
            native13.assess_native(rows[:-1], severe, bounds_verified=True)
        with self.assertRaisesRegex(ValueError, 'every severe-delay pair'):
            native13.assess_native(rows, severe[:-1], bounds_verified=True)

    def test_world_generation_is_private_and_preserves_declared_contact(self):
        original_root=native13.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'worlds').mkdir();(root/'research').mkdir()
            (root/'worlds/research_validation.wbt').write_bytes((original_root/'worlds/research_validation.wbt').read_bytes())
            (root/'research/calibration.json').write_bytes((original_root/'research/calibration.json').read_bytes())
            template_hash=native13.sha(root/'worlds/research_validation.wbt')
            case=next(c for _,c in native13.cases(dict(variant=2,residual_rad=.04)) if c['scenario']=='contact_mismatch')
            left=root/'run-a'/'same';right=root/'run-b'/'same';left.mkdir(parents=True);right.mkdir(parents=True)
            with patch.object(native13,'ROOT',root),patch.object(native13,'RESEARCH',root/'research'):
                world_a,configured=native13.make_world(case,left)
                world_b,_=native13.make_world(case,right)
            self.assertNotEqual(world_a,world_b)
            self.assertIn('controller "revision13_validation"',world_a.read_text())
            self.assertAlmostEqual(configured['front_slip'],4*case['speed']/80000*1.06/.65)
            self.assertEqual(native13.sha(root/'worlds/research_validation.wbt'),template_hash)
            self.assertTrue((world_a.parent.parent/'controllers/revision13_validation/revision13_validation.py').is_file())


if __name__=='__main__':unittest.main()

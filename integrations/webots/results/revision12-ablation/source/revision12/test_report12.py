import copy
import csv
import hashlib
import itertools
import json
import math
import tempfile
import unittest
from pathlib import Path
from report12 import PROTOCOL as P, REQUIRED_SOURCES, assess, validate, write_report


def source_fixture():
    return {name:(json.dumps(P) if name=='revision12/protocol.json' else '# synthetic source fixture: '+name+'\n').encode() for name in REQUIRED_SOURCES}


def write_fixture(run, rows, meta):
    (run/'complete.json').write_text(json.dumps(meta))
    with (run/'episodes.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    for name,content in source_fixture().items():
        path=run/'source'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)


def fixture(preview=.094,lateral=.0935):
    rows=[]
    for rep,speed,path,region,method in itertools.product(P['repetitions'],P['speeds'],P['paths'],P['scenarios'],P['methods']):
        n=math.ceil((220/speed+2)/.01)
        value=.1 if method=='lqr' else .099
        if method=='legacy_student':value=.098
        elif method=='preview_student':value=preview
        elif method=='lateral_student':value=lateral
        if region=='latency100':value=.1
        active=0. if method=='lqr' or region=='latency100' else 10/n
        identity=f'{rep}:{speed}:{path}:{region}:'+('lqr' if region=='latency100' else method)
        rows.append(dict(repetition=rep,seed=P['student_seeds'][rep],noise_id=P['development_noise_base']+rep*10000+speed*100+P['paths'].index(path)*10+P['scenarios'].index(region),
            speed=speed,path=path,scenario=region,method=method,survived=True,steps=n,scheduled_steps=n,rmse=value,penalized_rmse=value,
            active_fraction=active,mean_weight=.2*active,max_rate=.1,max_command=.04,max_actuator=.03,
            trajectory_sha256=hashlib.sha256(identity.encode()).hexdigest(),wall_p99_s=.001,
            submissions=0 if method=='lqr' else n,max_packet_age_s=0. if method=='lqr' else .1 if region=='latency100' else 0.))
    complete=dict(episodes=1080,protocol=copy.deepcopy(P),source_commit='a'*40,submission_semantics='every-available-worker-v1',
        split='development',training_steps=0,reserved_split_opened=False,
        sources={name:hashlib.sha256(content).hexdigest() for name,content in source_fixture().items()},
        students={str(s):{name:'b'*64 for name in ['student.pt','normalization.npz','complete.json']} for s in P['student_seeds']})
    return rows,complete


def change(rows,method,region,value,rep=None):
    for row in rows:
        if row['method']==method and row['scenario']==region and (rep is None or row['repetition']==rep):
            row['rmse']=row['penalized_rmse']=value


class ReportContracts(unittest.TestCase):
    def test_complete_passing_grid_and_predeclared_tie(self):
        rows,complete=fixture();parsed,result=assess(rows,complete)
        self.assertEqual(len(parsed),1080)
        self.assertEqual(result['eligible_variants'],['preview','lateral'])
        self.assertEqual(result['selected_gate'],'preview')
        self.assertEqual(result['next_action'],'independent_development_teacher_confirmation')
        self.assertFalse(result['training_authorized_now']);self.assertFalse(result['reserved_opened'])
        self.assertEqual(result['additional_rl_steps_run'],0)
        for arm in ['preview','lateral']:
            self.assertTrue(all(result['assessments'][arm]['gate_progress_checks'].values()))
            self.assertTrue(all(result['assessments'][arm]['learning_benefit_checks'].values()))
            self.assertTrue(result['assessments'][arm]['five_percent_regional_target'])
        rows,complete=fixture(lateral=.09)
        self.assertEqual(assess(rows,complete)[1]['selected_gate'],'lateral')
        rows,complete=fixture(preview=.098)
        self.assertEqual(assess(rows,complete)[1]['selected_gate'],'lateral')

    def test_no_progress_stops_before_any_training_or_reserved(self):
        rows,complete=fixture(preview=.098,lateral=.098)
        _,result=assess(rows,complete)
        self.assertIsNone(result['selected_gate']);self.assertEqual(result['eligible_variants'],[])
        self.assertEqual(result['next_action'],'stop_retraining_path')
        self.assertFalse(result['training_authorized_now']);self.assertFalse(result['reserved_opened'])
        for value in result['assessments'].values():
            self.assertFalse(value['gate_progress_checks']['overall_gain_vs_legacy_student'])
            self.assertFalse(value['gate_progress_checks']['all_three_seed_means_better'])
            self.assertFalse(value['gate_progress_checks']['minimum_stress_regions_with_one_percent_gain'])

    def test_incomplete_duplicate_schema_noise_and_metadata_rejected(self):
        rows,complete=fixture()
        with self.assertRaises(ValueError):validate(rows[:-1],complete)
        with self.assertRaises(ValueError):validate(rows+[rows[0]],complete)
        for field,value in [('noise_id',1),('seed',999),('repetition',.5),('speed',17),('survived','maybe'),('trajectory_sha256','missing'),('rmse',float('nan')),('wall_p99_s',float('inf')),('max_packet_age_s',-1)]:
            bad=copy.deepcopy(rows);bad[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate(bad,complete)
        bad=copy.deepcopy(rows);del bad[0]['method']
        with self.assertRaises(ValueError):validate(bad,complete)
        for field,value in [('episodes',1079),('source_commit','unknown'),('submission_semantics','held-action-relabel'),('students',{}),('protocol',{}),('split','reserved'),('training_steps',1),('training_steps',False),('reserved_split_opened',True),('reserved_split_opened',None),('sources',{})]:
            meta=copy.deepcopy(complete);meta[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate(rows,meta)

    def test_penalty_horizon_physical_limits_and_severe_hash(self):
        rows,complete=fixture()
        for field,value in [('steps',0),('scheduled_steps',10),('penalized_rmse',.2),('max_rate',.36),('max_command',.51),('max_actuator',.51),('mean_weight',.6),('active_fraction',1.1),('submissions',99999)]:
            bad=copy.deepcopy(rows);bad[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate(bad,complete)
        bad=copy.deepcopy(rows);row=next(r for r in bad if r['method']=='preview_student' and r['scenario']=='latency100');row['trajectory_sha256']='f'*64
        with self.assertRaises(ValueError):validate(bad,complete)
        bad=copy.deepcopy(rows);row=next(r for r in bad if r['method']=='preview_student' and r['scenario']=='latency100');row['rmse']=row['penalized_rmse']=.09
        with self.assertRaises(ValueError):validate(bad,complete)
        # Explicit failed-tail score is accepted, while a truncated survivor is not.
        bad=copy.deepcopy(rows);r=bad[1];r['survived']=False;r['steps']=100;r['submissions']=100;r['active_fraction']=.1;r['mean_weight']=.02
        r['penalized_rmse']=math.sqrt((100*r['rmse']**2+(r['scheduled_steps']-100)*6.25)/r['scheduled_steps'])
        self.assertEqual(len(validate(bad,complete)),1080)
        r['survived']=True
        with self.assertRaises(ValueError):validate(bad,complete)

    def test_independent_progress_preservation_and_learning_guards(self):
        # A seed may regress even when pooled mean strongly improves.
        rows,meta=fixture()
        for region in P['scenarios']:
            if region!='latency100':change(rows,'preview_student',region,.099,rep=0)
        v=assess(rows,meta)[1]['assessments']['preview']
        self.assertTrue(v['gate_progress_checks']['overall_gain_vs_legacy_student'])
        self.assertFalse(v['gate_progress_checks']['all_three_seed_means_better'])
        # A region regression cannot be hidden by improvements in all other regions.
        rows,meta=fixture();change(rows,'preview_student','tire_mismatch',.1)
        self.assertFalse(assess(rows,meta)[1]['assessments']['preview']['gate_progress_checks']['active_regions_preserved'])
        rows,meta=fixture();change(rows,'preview_student','nominal',.1001)
        self.assertFalse(assess(rows,meta)[1]['assessments']['preview']['gate_progress_checks']['nominal_not_worse_than_lqr'])
        rows,meta=fixture()
        for region in ['tire_mismatch','low_friction']:change(rows,'preview_student',region,.098)
        self.assertFalse(assess(rows,meta)[1]['assessments']['preview']['gate_progress_checks']['minimum_stress_regions_with_one_percent_gain'])
        rows,meta=fixture();next(r for r in rows if r['method']=='preview_student' and r['scenario']=='nominal')['survived']=False
        v=assess(rows,meta)[1]['assessments']['preview']
        self.assertFalse(v['gate_progress_checks']['cellwise_survival_lqr']);self.assertFalse(v['gate_progress_checks']['cellwise_survival_legacy_student'])
        self.assertFalse(v['learning_benefit_checks']['cellwise_survival_vs_fixed_m004']);self.assertFalse(v['learning_benefit_checks']['cellwise_survival_vs_fixed_p004'])
        # Gate progress alone is insufficient when the same gate's constant wins.
        rows,meta=fixture()
        for region in P['scenarios']:
            if region!='latency100':change(rows,'preview_fixed_p004',region,.093)
        v=assess(rows,meta)[1]['assessments']['preview']
        self.assertTrue(v['gate_progress_pass']);self.assertFalse(v['learning_benefit_pass']);self.assertFalse(v['eligible'])

    def test_five_percent_is_separate_and_requires_all_seed_region_gains(self):
        rows,meta=fixture(preview=.096)
        v=assess(rows,meta)[1]['assessments']['preview']
        self.assertTrue(v['eligible']);self.assertFalse(v['five_percent_regional_target'])
        # Two region pooled gains exceed5%, but one pair is worse than LQR.
        rows,meta=fixture(preview=.09)
        for region in ['tire_mismatch','low_friction']:change(rows,'preview_student',region,.101,rep=0)
        v=assess(rows,meta)[1]['assessments']['preview']
        self.assertNotIn('tire_mismatch',v['five_percent_qualifying_stress_regions'])
        self.assertNotIn('low_friction',v['five_percent_qualifying_stress_regions'])
        self.assertFalse(v['five_percent_regional_target'])

    def test_outputs_use_recorded_source_and_only_development_files(self):
        rows,meta=fixture(preview=.098,lateral=.098)
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);write_fixture(run,rows,meta)
            result=write_report(run)
            self.assertEqual(set(p.name for p in run.iterdir()),{'complete.json','episodes.csv','source','report.md','selection.json','verification.json'})
            report=(run/'report.md').read_text()
            self.assertIn(meta['source_commit'],report)
            self.assertIn('| preview | False | False | False | False | False |\n| lateral | False | False | False | False | False |',report)
            self.assertEqual(json.loads((run/'verification.json').read_text())['episodes'],1080)
            self.assertIsNone(result['selected_gate'])

    def test_manifest_and_archive_reject_missing_tampered_or_unsafe_sources(self):
        rows,meta=fixture()
        for name in ['../outside.py','/tmp/outside.py','revision12/../outside.py','revision12\\outside.py']:
            bad=copy.deepcopy(meta);bad['sources'][name]='c'*64
            with self.subTest(name=name),self.assertRaises(ValueError):validate(rows,bad)
        bad=copy.deepcopy(meta);del bad['sources']['revision7/kernels.py']
        with self.assertRaises(ValueError):validate(rows,bad)
        bad=copy.deepcopy(meta);bad['sources']['core.py']='invalid'
        with self.assertRaises(ValueError):validate(rows,bad)
        for failure in ['missing','digest','protocol','symlink']:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
                run=Path(tmp);copy_meta=copy.deepcopy(meta);write_fixture(run,rows,copy_meta)
                source=run/'source/core.py'
                if failure=='missing':source.unlink()
                elif failure=='digest':source.write_text('# altered after freezing\n')
                elif failure=='protocol':
                    source=run/'source/revision12/protocol.json';source.write_text('{}')
                    copy_meta['sources']['revision12/protocol.json']=hashlib.sha256(source.read_bytes()).hexdigest()
                    (run/'complete.json').write_text(json.dumps(copy_meta))
                else:
                    outside=run/'outside.py';outside.write_bytes(source.read_bytes());source.unlink();source.symlink_to(outside)
                with self.assertRaises(ValueError):write_report(run)
                self.assertFalse((run/'selection.json').exists())

    def test_zero_reference_is_serializable_and_never_claims_improvement(self):
        rows,meta=fixture()
        for row in rows:
            if row['method']=='lqr' or row['scenario']=='latency100':row['rmse']=row['penalized_rmse']=0.
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);write_fixture(run,rows,meta);result=write_report(run)
            self.assertIsNone(result['selected_gate'])
            self.assertIsNone(result['summary']['preview_student']['reduction_vs_lqr_percent'])
            self.assertFalse(result['assessments']['preview']['overall_five_percent_reduction'])
            self.assertIn('undefined (zero reference)',(run/'report.md').read_text())
            self.assertEqual(json.loads((run/'selection.json').read_text()),result)


if __name__=='__main__':unittest.main()

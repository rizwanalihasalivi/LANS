"""Build the manuscript from audited results, one template and shared figures."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def build(root,report,output,tests):
    root,report,output=map(Path,(root,report,output))
    output.mkdir(parents=True,exist_ok=False)
    independent=json.loads((root/'independent-audit.json').read_text())
    dev,val=independent['development'],independent['validation']
    assert dev['passed'] and val['passed']
    proof=json.loads((root/'proof/proof.json').read_text())
    boundary=json.loads((root/'boundary.json').read_text())
    negatives=json.loads((root/'negative-checks.json').read_text())
    assert proof['passed'] and boundary['passed'] and negatives['passed']
    assert all(v['result']=='unsat' for v in proof['obligations'].values())
    profile_table=(report/'validation-tables.md').read_text().splitlines()
    profile_table='\n'.join(line for line in profile_table if line.startswith('|'))
    labels={'steady_connected':'Steady connected','leader_emergency':'Emergency brake',
        'v2v_blackout':'V2V blackout','dual_blackout':'Dual blackout',
        'bounded_sensor_error':'Bounded error','admissible_cutin':'Admissible entry',
        'adversarial_nominal':'Adversarial request','permanent_blackout':'Permanent blackout'}
    for key,label in labels.items():profile_table=profile_table.replace('| '+key+' |','| '+label+' |')
    verification='\n'.join([
        '| Evidence | Result |', '| --- | --- |',
        f"| Algebraic SMT obligations | {len(proof['obligations'])}/12 UNSAT |",
        f"| Deliberately weakened SMT controls | {len(proof['negative_controls'])}/5 SAT |",
        f"| Exact boundary cases | {boundary['boundary_cases']}/2160 passed |",
        f"| Independent development episodes | {dev['episodes']}/72 passed |",
        f"| Independent fresh episodes | {val['episodes']}/240 passed |",
        f"| Rehashed semantic corruptions | {len(negatives['checks'])}/3 rejected |",
        f"| Automated repository V2V tests | {tests} passed |",
    ])
    replacements=dict(DEV_N=str(dev['episodes']),VAL_N=str(val['episodes']),
        TICKS=f"{dev['ticks']+val['ticks']:,}",VAL_TICKS=f"{val['ticks']:,}",
        MIN_GAP=f"{val['minimum_continuous_gap_m']:.9f}",DEV_MIN_GAP=f"{dev['minimum_continuous_gap_m']:.9f}",
        MAX_RMS=f"{val['maximum_spacing_rms_m']:.3f}",MAX_STOP=f"{val['maximum_stopped_s']:.2f}",
        UNSAFE_GAP=f"{boundary['excluded_unsafe_cutin']['minimum_gap_m']:.6f}",
        WEAK_GAP=f"{boundary['excluded_weak_brake']['minimum_gap_m']:.6f}",
        TESTS=str(tests),VERIFICATION_TABLE=verification,PROFILE_TABLE=profile_table)
    text=Path(__file__).with_name('thesis-template.md').read_text()
    for name,value in replacements.items():text=text.replace('@@'+name+'@@',value)
    assert '@@' not in text,'unresolved manuscript values'
    md=output/'LANS_Simulation_Conditional_Safety_Thesis.md';md.write_text(text)
    figures=output/'figures';figures.mkdir()
    for path in report.iterdir():
        if path.suffix in ('.png','.pdf'):shutil.copyfile(path,figures/path.name)
    command=['pandoc',md.name,'--standalone','--toc','--number-sections']
    subprocess.run(command+['--pdf-engine=xelatex','-V','geometry:margin=25mm',
        '-V','mainfont=DejaVu Serif','-V','monofont=DejaVu Sans Mono','-V','colorlinks=true',
        '-o',md.with_suffix('.pdf').name],cwd=output,check=True)
    subprocess.run(command+['-o',md.with_suffix('.docx').name],cwd=output,check=True)
    return str(md)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--report',required=True)
    p.add_argument('--output',required=True);p.add_argument('--tests',required=True,type=int);a=p.parse_args()
    print(build(a.root,a.report,a.output,a.tests))

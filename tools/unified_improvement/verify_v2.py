"""Repair a missing auditor import without modifying frozen v2 code or raw data."""
import argparse
from pathlib import Path
from tools.unified_campaign import campaign as base
from integrations.unified_lans.physics import Command
from integrations.unified_lans.inference import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='results/python-campaign-v2')
    a=p.parse_args();root=base.check(Path(a.output))
    base.Command=Command
    base.write(root/'VERIFIER_REPAIR.json',dict(original_failure='NameError: Command was not imported in audit',
        repair='Bind the existing physical Command type in the auditor namespace; no frozen source edited',
        repair_source_sha256=sha(__file__),raw_episodes_rerun=False,raw_records_changed=False,
        metrics_tolerances_selection_thresholds_changed=False))
    gate=base.report(root,'development');stress=base.robustness(root)
    if gate['passed'] and stress:base.evaluate(root,'reserved');base.report(root,'reserved')
    else:print('Python gate closed; reserved and Webots are NOT_RUN.',flush=True)


if __name__=='__main__':main()

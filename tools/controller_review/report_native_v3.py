"""Assemble native integration, timing failures, readiness gates and laptop handoff."""
import argparse,hashlib,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();run=a.run
    timing=json.loads((run/'timing/summary.json').read_text());tv=json.loads((run/'timing/verification.json').read_text())
    original=json.loads((run/'native-development/verification.json').read_text())
    aligned=json.loads((run/'native-aligned/verification.json').read_text())
    gate=json.loads((run/'final-comparison/eligibility.json').read_text())
    observer=json.loads((run/'observer-benchmark/summary.json').read_text())
    exported=json.loads((run/'windows-export-verification.json').read_text())
    misses=sum(r['deadline_misses'] for r in timing['episodes']);ticks=sum(r['ticks'] for r in timing['episodes'])
    native_misses=sum(r['deadline_misses'] for r in aligned['cases']);native_ticks=sum(r['ticks'] for r in aligned['cases'])
    decision=dict(observer_parity_tests_pass=True,optimized_software_functional_pass=timing['functional_pass'],
        optimized_software_strict_timing_pass=timing['timing_pass'],software_deadline_misses=misses,software_ticks=ticks,
        original_native_survivors=sum(r['survived'] for r in original['cases']),
        aligned_native_survivors=sum(r['survived'] for r in aligned['cases']),
        native_contract_checks_pass=aligned['native_contract_checks_pass'],native_wall_timing_pass=aligned['strict_native_wall_timing_pass'],
        final_comparison_eligible=gate['eligible'],reserved_noise_opened=gate['reserved_noise_opened'],
        windows_export_parity_pass=exported['export_batch_one_checks_pass'],windows_laptop_execution='pending user run',
        physical_vehicle_testing='not available: user has a Windows laptop, not an attached instrumented vehicle',
        deployment_promoted=False)
    (run/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
    a0=observer['methods']['original']['wall_ns']['median_ms'];a1=observer['methods']['small_algebra']['wall_ns']['median_ms']
    lines=['# Native causal integration, timing remediation and Windows laptop handoff','',
        '## Status','',
        '| Work item | Result |','|---|---|',
        '| Observer implementation | BLAS/LAPACK-free small algebra; numerical parity tests pass |',
        f'| Full 10 ms software deadline | **FAIL: {misses:,}/{ticks:,} misses ({100*misses/ticks:.3f}%)** |',
        '| Native causal student integration | Implemented and independently verified |',
        f"| Corrected native development tracking | **{decision['aligned_native_survivors']}/6 survived**; original failed grid retained |",
        f'| Native 10 ms wall deadline | **FAIL: {native_misses:,}/{native_ticks:,} misses** |',
        '| Frozen final comparison | Prepared; blocked by timing eligibility; reserved data unopened |',
        '| User laptop | Windows x64, i5-1235U,8 GB; lightweight ZIP prepared; actual laptop run pending |',
        '| Vehicle/actuator validation | No attached instrumented vehicle; read-only log checker and runbook prepared |','',
        'The cloud engineering work is complete for this fixed revision, including negative results. It does not establish guaranteed100Hz execution, a final LANS ranking, native learned advantage or real-vehicle readiness. No model or gate thresholds were tuned after these outcomes.','',
        '## Observer and deadline remediation','',
        'Implemented a positive-definite3×3 solver and small explicit matrix products instead of BLAS/LAPACK dispatch inside the existing observer equations.200 random SPD solves and1,200 paired observer steps across speeds, paths and sensor-delay modes match the original within declared numerical tolerances. Non-positive covariance fails explicitly. Training, model weights, noise levels, gains, action bounds and predictive gate are unchanged.','',
        f'In2,000 randomized-order warm microbenchmark pairs on one fixed input, median observer call wall time was {a0:.6f} ms original and {a1:.6f} ms small algebra. This establishes an implementation-level measurement on this workload, not a full-controller speedup or worst-case guarantee.','',
        f'The fixed fresh development timing campaign still failed: {misses:,}/{ticks:,} deadlines. All18 software runs survived with zero stale, late or fallback authority violations. The independent verifier replayed {tv["packets"]:,} actual model outputs and all{tv["ticks"]:,} control ticks. No late tick was removed, no deadline was rebased, and no retry was used to replace the failure.','',
        'The host denied SCHED_FIFO scheduling with EPERM and has a shared CPU quota. Webots reports software Mesa rendering. These environment facts do not uniquely explain every delay, but hard-real-time scheduling and dedicated target hardware are unavailable. Optimizing one observer does not make OS release jitter or simulator execution meet10ms.','',
        '## Native Webots causal adapter','',
        'Installed and hash-verified private Webots R2025a and its pinned vehicle PROTOs. The new causal_validation controller loads the frozen causal-v2 student in a real spawned worker, keeps one request in flight, and preserves original wall/simulation observation stamps. It exposes no future proposal or completion forecast. The actor uses exactly its trained causal profile.','',
        'A delayed packet is checked using max(simulation age,wall-clock age); original timestamps are logged separately from the conservative equivalent gate timestamp.≥50ms packets and missed control deadlines receive zero learned authority. Worker failure clears the held packet and uses local LQR. The current speed-scheduled LQR, actuator angle/rate limits and calibrated vehicle mass/inertia are verified. Native simulator timing is recorded separately from software-plant timing.','',
        '## Coordinate initialization defect and correction','',
        'The first six-case development grid produced4/6 survivors: both sine-path runs failed the heading envelope. The native car started at world lateral0 and heading0 while the unchanged sine path started at lateral0.739m and heading0.124rad. This tested a large unplanned entry transient; it is retained in native-development rather than discarded.','',
        'The correction is a rigid map-frame translation/rotation after physical acceleration warmup: the settled CG maps to the original path start and its tangent. No physical vehicle pose is reset or teleported, and the original path shape/parameters, controller gains and model weights remain unchanged. Raw world coordinates and the map transform are logged; the verifier checks their relationship on every tick. A separate predeclared alignment diagnostic repeated the same six development cases once. This initialization change means its results must not be pooled with the failed grid.','',
        '| Case | Survived | Control ticks | Delivered packets | Learned-active ticks | Tracking RMSE m | Wall deadline misses |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in aligned['cases']:
        lines.append(f"| {r['name']} | {r['survived']} | {r['ticks']} | {r['packets']} | {r['active_ticks']} | {r['rmse_m']:.6f} | {r['deadline_misses']} |")
    lines+=['',
        'All logged worker outputs, causal input masks, original timestamps, effective ages, angle/rate constraints, tracking metrics and deadline revocation were independently checked.100ms student and paired LQR physical/control traces match exactly. The corrected native campaign has only one learned-active tick; this chiefly validates real-worker integration and fallback, not a native learning benefit. Most ticks miss the original wall-clock schedule, so the native timing criterion remains failed.','',
        '## Frozen comparison gate','',
        'The runner freezes432 common-software-plant episodes: three seeds×three speeds×two unchanged paths×six conditions×four methods (LQR, fixed−.04, fixed+.04,causal student). Model/normalization and runner hashes are saved. It checks full software and native timing eligibility against raw timestamps before accessing reserved noise994000000.','',
        'The explicit --run-if-eligible attempt correctly returned ineligible; no episodes.csv exists and reserved_noise_opened is false. The current negative timing outcomes are not grounds to relax the predeclared criterion. This prepared runner is not a completed final comparison and would not by itself be native or physical evidence.','',
        '## Windows laptop package','',
        'LANS_Windows_Laptop_Kit.zip contains the actual three trained-model NumPy exports,512 golden observations, one-click RUN_WINDOWS.cmd and instructions. It creates a local virtual environment and installs NumPy only. Every archived DEV observation (24,300 per seed) has zero action disagreements with the original Torch checkpoint, including batch-one worker inference. The portable kit passed a Linux half-second smoke over all five fault scenarios; Windows execution has not occurred in this cloud environment.','',
        'The user must extract the ZIP on the Windows laptop, run RUN_WINDOWS.cmd and return the generated summary.json. The default run takes about one minute after installation and records inference, IPC and monitor scheduling. It sends no actuator commands and collects no device/product IDs or hostname. Recorded inputs and a light monitor do not replace full observer/LQR/gate, live sensor or actuator validation.','',
        '## Hardware evidence tooling','',
        'hardware/RUNBOOK.md defines real device/clock/firmware evidence and a timestamp schema through physical acknowledgement and encoder measurement. hardware_acceptance.py checks original packet ages,10ms acknowledgement deadlines,50ms freshness, fallback and physical bounds; it explicitly rejects simulator logs as hardware evidence. Five arithmetic/evidence tests pass. Synthetic unit fixtures are not stored as passed hardware traces, and no hardware result is fabricated.','',
        'An actual laptop CPU run, suitable real-time host validation, broader native evaluation and instrumented sensor/vehicle I/O are still required for their respective claims. A laptop alone supplies CPU timing hardware, not vehicle acknowledgements or real-vehicle readiness.','',
        '## Reproduction','', '```bash',
        'bash integrations/webots/install-private.sh',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_CACHE_DIR=/tmp/lans-native-v3-numba \\',
        '  /workspace/lans-venv/bin/python tools/controller_review/test_realtime_kernels.py -v',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /workspace/lans-venv/bin/python tools/controller_review/native_causal.py \\',
        '  --output /tmp/new-native-cases --models docs/research/causal-interface-2026-10-26/models',
        '```','',
        'Use a fresh output directory. The native runtime uses the documented Linux research environment; the separate ZIP is the Windows CPU/IPC handoff. Archived source snapshots allow verifying the preserved failed initial grid using --source-root <archive>/native-development/source. The hardware runbook and kit README contain their own commands.','']
    (run/'README.md').write_text('\n'.join(lines))

if __name__=='__main__':main()

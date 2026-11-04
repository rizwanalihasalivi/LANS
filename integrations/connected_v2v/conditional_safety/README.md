# Hardware-free conditional safety and simulation thesis

This is a **separate longitudinal reference shield and theorem**, added after
`9daa1487`. Read [THEOREM.md](THEOREM.md) and the
[execution/admission notes](PROOF_SCOPE_NOTES.md) before using a safety claim. It does not
retroactively certify the existing 2-D LANS/Webots controller. All old source and
evidence is preserved. Final controller benchmarking remains on hold.

The guarantee is bumper separation ≥m under valid initialization/admission,
complete forward-object coverage, valid bounded sensing/identity, non-reversing
obstacles, a valid ego acceleration envelope and updates within h. It allows
indefinite message loss by retaining valid *spatial* lower bounds; it never turns
expired observations into fresh nominal state. It may require an indefinite stop.

The exact guard is `2*b*next_distance + next_speed**2 <= 2*b*(B-X-m)`.
The emergency candidate `u=-b-delta` is recursively feasible. The written flow and
induction argument is supported by 12 Z3 real-arithmetic UNSAT obligations and
five SAT negative controls. It is not a proof-assistant-kernel certificate or
formal verification of every Python statement/2-D vehicle dynamics.

## Components

- `shield.py`: stdlib exact Fraction reference, valid bound retention, source replay
  checks, upper-state intersections, finite command lattice, emitted certificates.
- `prove.py`: pinned Z3 check and exported SMT-LIB; unknown/timeouts fail.
- `audit.py`: independent stdlib-only reconstruction, input/actuation/guard checks
  and exact piecewise-quadratic intersample minimum gap. Imports no shield/plant.
- `study.py`: deterministic sensor fixtures, explicit object-admission contract,
  source freezes and development/fresh-validation gates.
- `boundary.py`: 2,160 exact boundary cases and outside-contract collision examples.
- `negative_checks.py`: rehashed sensor/guard/transition corruption rejection.
- `report.py`, `build_thesis.py`, `thesis-template.md`: figures, tables and consistent
  English Markdown/PDF/Word research draft. Institutional front matter is not guessed.
- `package.py`: complete raw evidence and source inventories, ZIP CRC/member/outer
  SHA-256 verification; preserves the actual experiment source freeze separately.

The reference nominal request is
`min(.64*(observed_gap-6-1.2*ego_speed)+.832*(observed_front_speed-ego_speed),
.8*(cruise_speed-ego_speed))`, with braking when no nominal state is fresh.
The gains correspond numerically to the old damped configuration; this is a new
1-D reference policy with a cruise cap, not unchanged RobustFollower execution.
An adversarial profile always proposes positive acceleration to test the shield.
Admissible cut-in means a detected/recoverable 1-D object admission, not verified
autonomous lateral detection. All simulated target/ego errors have bounded support.

## Reproduce

Use the existing isolated `/workspace/LANS`; no worktree or hardware is needed.
The full V2V test suite requires a complete Git checkout (one correspondence test
imports the earlier LANS gains). The extracted reference runtime needs only Python,
the pinned Z3 package for the study/proof, and Matplotlib for optional figures.

```bash
cd /workspace/LANS
source /workspace/lans-setup/env.sh
uv pip install --python /workspace/lans-venv/bin/python \
  -r integrations/connected_v2v/conditional_safety/requirements-proof.txt
python -m pytest -q integrations/connected_v2v

# NEW roots only; never overwrite previous evidence.
python -m integrations.connected_v2v.conditional_safety.study \
  --output results/new-conditional --stage development
python -m integrations.connected_v2v.conditional_safety.boundary \
  --output results/new-conditional/boundary.json
python -m integrations.connected_v2v.conditional_safety.audit \
  results/new-conditional --stage development
python -m integrations.connected_v2v.conditional_safety.negative_checks \
  results/new-conditional > results/new-conditional/negative-checks.json
# Gate requires development, independent replay, proof and boundary passes.
python -m integrations.connected_v2v.conditional_safety.study \
  --output results/new-conditional --stage validation
python -m integrations.connected_v2v.conditional_safety.audit \
  results/new-conditional > results/new-conditional/independent-audit.json
python -m integrations.connected_v2v.conditional_safety.report \
  results/new-conditional --output results/new-conditional-report
python -m integrations.connected_v2v.conditional_safety.build_thesis \
  results/new-conditional --report results/new-conditional-report \
  --output results/new-conditional-thesis --tests 164
```

The last command needs Pandoc and XeLaTeX with DejaVu fonts. The prepared environment
contains them. Markdown is the shared source; Pandoc produces PDF and editable Word
equations. Existing opening reports are unchanged. Reusing the published seeds is
reproduction only; controller/scenario changes require new development and genuinely
fresh validation seeds. Read [PROTOCOL.md](PROTOCOL.md).

After extracting **all** evidence shards into a single new root, independently run:

```bash
python <extracted>/source/integrations/connected_v2v/conditional_safety/audit.py <extracted>
```

The source freeze reflects the files present during execution; later reporting,
packaging and manuscript code is separately inventoried as `release-source`.
Do not replace a frozen runtime with a later report snapshot silently.

## Claim wording

Suitable: “Under the stated longitudinal model, valid bounded observations,
non-reversing protected objects, initial recoverability and bounded actuation/
update intervals, the safety guard preserves a minimum bumper separation.”

Not established: physical-world validation, arbitrary hidden cut-ins, native speed
servo refinement, bounded Gaussian error, cryptographic trust, desired-headway
convergence, string stability, real-time deadlines or published-method superiority.
Existing 150 m recovery and broader formation-spacing limits remain disclosed.

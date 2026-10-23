# Webots vehicle interface validation

This isolated integration exercises full road-wheel steering commands with Webots R2025a's generic `Car`. It does not import the primary bicycle model, LQR, PPO, or phase-1 experiments. Positive adapter steering means left; distances, speed, angles and timestamps use SI units.

From the repository/worktree root on the documented Debian 13 x86-64 cloud image:

```bash
bash integrations/webots/install-private.sh
python3 -m unittest discover -s integrations/webots -p test_adapter.py -v
bash integrations/webots/run-tests.sh
```

The installer uses only `integrations/webots/.runtime/` (ignored). It does not install system packages or modify a shared Webots installation. It needs `curl`, `tar`, `sha256sum`, Debian apt/dpkg tools, the Debian archive keyring and Python 3. Downloads use verified HTTPS; apt verifies signed repository metadata. The runtime archive is about 143 MiB compressed. Extracted runtime, libraries and caches need additional disk space. Runtime PROTOs are fetched at the pinned upstream commit and checked against `runtime-sha256.txt`. These hashes record the files obtained over HTTPS, not a publisher-signed checksum manifest. The Debian package recipe remains distribution-resolved, not a complete binary lock. Upstream assets retain their upstream licensing and are not vendored in Git.

`run-tests.sh [new-output-directory]` runs straight, left, then right in fresh simulator processes under a private Xvfb display and software rendering. It refuses to overwrite an existing output directory, enforces per-process timeouts and propagates simulator/analysis failures. Each case writes a CSV, console log, and vehicle-parameter audit. Input hashes and configuration are saved; the analyzer refuses mismatched inputs or incomplete logs. `summary.json` is only produced after all acceptance checks pass. No background simulator is retained.

```bash
python3 integrations/webots/analyze.py integrations/webots/results/baseline
```

See [the validation record](../../docs/research/webots-validation.md) for conventions, parameter mismatches, thresholds, actual results, and limitations. `results/baseline/` and `results/repeat/` contain simulator evidence; other result directories are local development outputs, not automatically trusted results.

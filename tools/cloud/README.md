# Cloud setup and verification record

Checkpoint date: 24 October 2026 (Asia/Shanghai). Scripts target the original Linux x86-64 cloud layout, with repository at `/workspace/LANS`; they are not general OS installers. Prerequisites include uv, Git, curl, tar, Debian apt/dpkg tools and archive keyring. Network access to package indexes, GitHub releases and Debian mirrors is needed.

## Recreate environment

```bash
cd /workspace/LANS
mkdir -p /workspace/lans-setup /workspace/webots-setup
cp tools/cloud/install.sh tools/cloud/smoke.py tools/cloud/sumo_smoke.py /workspace/lans-setup/
cp tools/cloud/install-webots.sh tools/cloud/run-webots.sh /workspace/webots-setup/
cp -R tools/cloud/webots-demo /workspace/webots-setup/demo
bash tools/cloud/install.sh
bash tools/cloud/install-sumo.sh
bash /workspace/webots-setup/install-webots.sh
bash tools/cloud/install-aris.sh
```

The Python installer selects Python 3.10 and installs repository pins plus highway-env 1.8.2. Observed interpreter: 3.10.22. Main installed packages included torch 2.0.0+cpu, TensorFlow 2.12, NumPy 1.23.5, SciPy 1.10.1, stable-baselines3 2.0, gymnasium 0.28.1 and CARLA client 0.9.15. SWIG 4.4.1 supports Box2D installation. `install-sumo.sh` preserves SUMO 1.28.0 and matching Python packages. Install scripts are repeatable setup recipes, not a complete transitive binary lock.

Webots R2025a uses workspace-local Debian runtime libraries and Xvfb with Mesa CPU rendering. Debian packages come from signed trixie/bookworm indexes; this is the tested cloud workaround, not an upstream Webots system-support claim. The wrapper supplies writable XDG paths and cleans up its Xvfb process. No GPU acceleration was established.

ARIS is pinned to `23745b69a14880b5716d1773e5d20f5f1e6ab1d6` from https://github.com/wanshuiyin/auto-claude-code-research-in-sleep. The installer recreates 85 skills plus shared references (86 managed links), its local manifest and managed AGENTS block. Absolute local symlinks/manifest are ignored by Git and must be regenerated on a fresh checkout. No upstream skill content is modified or vendored. External review-service credentials and Claude CLI were not configured. Integration does not launch research workflows.

## Previously completed checks

- Dependency consistency and existing dynamics/environment/controller diagnostics passed.
- Both existing environments ran 100 simulation steps and 128 PPO training steps each, with save/load/predict and a headless plot. These were installation smoke checks, not scientific training or new-framework experiments.
- SUMO/TraCI tiny-network test: all 10 vehicles departed, moved and arrived.
- Webots smoke ran twice: 100 physics steps / 3.2 simulated seconds, falling box settled from 1 m to approximately 0.0996 m; 64×64 camera produced 16,384 bytes. The retained demo/result.json and camera.png are smoke evidence, not driving results.
- ARIS upstream installer/wiki tests: 34 passed at integration time.

Commands below rerun smoke checks; they were not rerun as research experiments for this publication checkpoint:

```bash
/workspace/lans-venv/bin/python /workspace/lans-setup/smoke.py
PATH=/workspace/lans-venv/bin:$PATH /workspace/lans-venv/bin/python /workspace/lans-setup/sumo_smoke.py
bash /workspace/webots-setup/run-webots.sh --batch --mode=fast --no-rendering /workspace/webots-setup/demo/worlds/smoke.wbt
```

CARLA **server was not installed or validated**; only its Python client is available. Webots vehicle/controller integration remains future work. No new full PPO training, paper experiments, manuscript edits or autonomous ARIS review loops have run. Virtual environments, downloaded simulator binaries, dependency caches and disposable smoke policy checkpoints are recreated, not committed.

Cloud onboarding configuration was saved as a draft requiring UI publication; Git push does not publish that separate environment configuration.

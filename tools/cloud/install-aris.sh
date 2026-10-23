#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
aris_root=${ARIS_REPO:-/workspace/auto-claude-code-research-in-sleep}
aris_commit=23745b69a14880b5716d1773e5d20f5f1e6ab1d6
if [ ! -d "$aris_root" ]; then
    git clone https://github.com/wanshuiyin/auto-claude-code-research-in-sleep.git "$aris_root"
    git -C "$aris_root" checkout --detach "$aris_commit"
fi
if [ "$(git -C "$aris_root" rev-parse HEAD)" != "$aris_commit" ]; then
    echo 'Existing ARIS checkout differs from the recorded commit; use a separate ARIS_REPO path.' >&2
    exit 1
fi
bash "$aris_root/tools/install_aris_codex.sh" "$project_root" --all --quiet

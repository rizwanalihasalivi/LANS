#!/usr/bin/env bash
set -euo pipefail
export WEBOTS_HOME=/workspace/webots-setup/webots
export PATH=/workspace/lans-venv/bin:$PATH
export WEBOTS_ORIGINAL_LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}
export LD_LIBRARY_PATH=/workspace/webots-setup/runtime/usr/lib/x86_64-linux-gnu:$WEBOTS_HOME/lib/webots${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export LIBGL_ALWAYS_SOFTWARE=1
export QT_QPA_PLATFORM=xcb
export WEBOTS_TMPDIR=/tmp
export XDG_CONFIG_HOME=/workspace/webots-setup/config
export XDG_CACHE_HOME=/workspace/webots-setup/cache
export XDG_RUNTIME_DIR=/workspace/webots-setup/xdg
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
display_file=$(mktemp /workspace/webots-setup/display.XXXXXX)
/workspace/webots-setup/runtime/usr/bin/Xvfb -displayfd 3 -screen 0 1024x768x24 -nolisten tcp -ac 3>"$display_file" >"$display_file.log" 2>&1 &
display_pid=$!
cleanup() {
    kill "$display_pid" 2>/dev/null || true
    wait "$display_pid" 2>/dev/null || true
    rm -f "$display_file" "$display_file.log"
}
trap cleanup EXIT
for attempt in {1..50}; do
    [ -s "$display_file" ] && break
    kill -0 "$display_pid" 2>/dev/null || { cat "$display_file.log"; exit 1; }
    sleep 0.1
done
[ -s "$display_file" ] || { cat "$display_file.log"; exit 1; }
export DISPLAY=:$(cat "$display_file")
"$WEBOTS_HOME/bin/webots-bin" "$@"

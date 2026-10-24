#!/usr/bin/env bash
set -euo pipefail
setup_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.runtime
export WEBOTS_HOME="$setup_root/webots"
export PYTHONDONTWRITEBYTECODE=1
export ALSOFT_DRIVERS=null
export WEBOTS_ORIGINAL_LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}
export LD_LIBRARY_PATH=${setup_root}/runtime/usr/lib/x86_64-linux-gnu:$WEBOTS_HOME/lib/webots${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export LIBGL_ALWAYS_SOFTWARE=1
export QT_QPA_PLATFORM=xcb
export WEBOTS_TMPDIR=/tmp
export XDG_CONFIG_HOME=${setup_root}/config
export XDG_CACHE_HOME=${setup_root}/cache
export XDG_RUNTIME_DIR=${setup_root}/xdg
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
display_file=$(mktemp ${setup_root}/display.XXXXXX)
${setup_root}/runtime/usr/bin/Xvfb -displayfd 3 -screen 0 1024x768x24 -nolisten tcp -ac -noreset 3>"$display_file" >"$display_file.log" 2>&1 &
display_pid=$!
cleanup() {
    kill "$display_pid" 2>/dev/null || true
    wait "$display_pid" 2>/dev/null || true
    if [ -n "${LANS_CASE_CONFIG:-}" ]; then cp "$display_file.log" "${LANS_CASE_CONFIG%.json}-xvfb.log"; fi
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
# Explicitly wait until the X display accepts clients; retain diagnostics per case.
for attempt in {1..100}; do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then break; fi
    kill -0 "$display_pid" 2>/dev/null || { cat "$display_file.log"; exit 1; }
    sleep 0.1
done
xdpyinfo -display "$DISPLAY" >/dev/null
"$WEBOTS_HOME/bin/webots-bin" "$@"

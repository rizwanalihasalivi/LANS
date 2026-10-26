"""Run a native simulator job; timeout cleanup includes its launcher descendants."""
import os
import signal
import subprocess


def run_native(command, *, env, stdout, timeout):
    process = subprocess.Popen(command, env=env, stdout=stdout,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        returncode = process.wait(timeout=timeout)
    except BaseException:
        # Killing only the shell leaves Webots/Xvfb alive and skips its EXIT trap.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        finally:
            # A launcher may exit before descendants which ignore SIGTERM.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        raise
    if returncode:
        raise subprocess.CalledProcessError(returncode, command)
    return subprocess.CompletedProcess(command, returncode)

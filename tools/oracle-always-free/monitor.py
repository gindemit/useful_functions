"""Windowless OCI task runner and daily Telegram health reporter (Windows)."""
import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(os.environ.get("OCI_MONITOR_ROOT", r"C:\Work\projects\oracle"))
DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MediaService"
HELPER = Path.home() / ".codex/skills/telegram-notify/scripts/send_notification.py"
TASK = "MediaService-OCI-AlwaysFree-A1"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def now():
    return dt.datetime.now().astimezone()


def read_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temp.replace(path)


def event(kind, **fields):
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "oci-monitor-events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(time=now().isoformat(), kind=kind, **fields)) + "\n")


@contextlib.contextmanager
def lock(name):
    import msvcrt
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / (name + ".lock")).open("a+b") as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def notify(key, title, message, status="info"):
    """Record attempt BEFORE sending: ambiguous deliveries must not be retried."""
    with lock("oci-notify") as acquired:
        if not acquired:
            event("notification_busy", key=key)
            return False
        path = DATA / "oci-notifications.json"
        state = read_json(path, {})
        if key in state:
            return state[key].get("delivered", False)
        state[key] = dict(attempted=now().isoformat(), delivered=False)
        save(path, state)
        try:
            result = subprocess.run(
                [sys.executable.replace("pythonw.exe", "python.exe"), str(HELPER),
                 "--project", "Oracle Always Free / Frankfurt", "--status", status,
                 "--title", title, "--message", message,
                 "--link", "Oracle console (sign in)", "https://cloud.oracle.com/compute/instances?region=eu-frankfurt-1"],
                capture_output=True, text=True, timeout=150, creationflags=FLAGS,
            )
            delivered = result.returncode == 0
            # Helper errors are sanitized; never store credential-bearing API URLs.
            detail = (result.stdout if delivered else result.stderr)[-1500:]
        except (OSError, subprocess.TimeoutExpired):
            delivered, detail = False, "Notification process failed or timed out; delivery may be ambiguous."
        state[key].update(delivered=delivered, detail=detail)
        save(path, state)
        event("notification", key=key, delivered=delivered)
        return delivered


def stats(text, since):
    counts = dict(runs=0, capacity_checks_ok=0, errors=0, provisioned=0)
    latest = None
    for line in text.splitlines():
        match = re.match(r"^(\d{4}-\d\d-\d\dT\S+) (.*)", line)
        if not match:
            continue
        # Windows PowerShell emits seven fractional digits; Python 3.10 accepts six.
        timestamp = re.sub(r'(\.\d{6})\d+(?=[+-]|Z|$)', r'\1', match[1])
        stamp = dt.datetime.fromisoformat(timestamp)
        if stamp < since:
            continue
        body = match[2]
        if "Starting Always Free A1 capacity check." in body:
            counts["runs"] += 1
            latest = stamp
        if "All availability domains are currently out of A1 capacity" in body:
            counts["capacity_checks_ok"] += 1
        if "ERROR:" in body:
            counts["errors"] += 1
        if "Created free-ubuntu-a1 (" in body:
            counts["provisioned"] += 1
    return counts, latest


def classify(code, output):
    if re.search(r'NotAuthenticated|InvalidAuthenticationInfo|ExpiredToken|token.{0,30}expir|"status"\s*:\s*401\b', output, re.I):
        return "authentication_error"
    if code:
        return "rate_limited" if "TooManyRequests" in output else "error"
    if "All availability domains are currently out of A1 capacity" in output:
        return "no_capacity"
    if "RUNNING" in output or "is running and its success notification" in output:
        return "instance_running"
    if "already exists in state" in output:
        return "instance_pending"
    return "unverified"


def check():
    with lock("oci-check") as acquired:
        if not acquired:
            return 0
        event("started")
        path = DATA / "oci-monitor-health.json"
        health = read_json(path, {})
        health["started"] = now().isoformat()
        save(path, health)
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        try:
            # No timeout that might kill a launch ambiguously. Scheduler retains its 30m limit.
            result = subprocess.run(
                [str(powershell), "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                 "-File", str(ROOT / "provision-oci-always-free-a1.ps1"), "-TaskName", TASK],
                cwd=ROOT, capture_output=True, text=True, errors="replace", creationflags=FLAGS,
            )
            code, output = result.returncode, result.stdout + result.stderr
        except OSError as error:
            code, output = 1, "Runner could not start PowerShell: " + str(error)
        with (DATA / "oci-monitor-output.log").open("a", encoding="utf-8") as stream:
            stream.write(now().isoformat() + "\n" + output + "\n")
        outcome = classify(code, output)
        good = outcome in ("no_capacity", "instance_running", "instance_pending")
        health.update(completed=now().isoformat(), outcome=outcome, exit_code=code,
                      consecutive_failures=0 if good else health.get("consecutive_failures", 0) + 1)
        if good:
            health["last_verified"] = health["completed"]
        save(path, health)
        event("completed", outcome=outcome, exit_code=code)
        success_alert()
        if outcome == "authentication_error" or health["consecutive_failures"] >= 3:
            notify("failure-" + now().date().isoformat(), "Oracle checks need attention",
                   f"Latest result: {outcome}. Consecutive failed/unverified checks: {health['consecutive_failures']}. "
                   "These are errors, not evidence of unavailable capacity. Check the local MediaService logs.", "attention")
        return code if code else (0 if good else 1)


def success_alert():
    success = read_json(DATA / "oci-a1-running.json", {})
    if success.get("instance_id"):
        notify("instance-" + success["instance_id"], "Oracle free server is running",
               f"{success['name']} is RUNNING in Frankfurt: 2 OCPUs / 12 GB RAM. "
               "Open the Oracle console to review the instance. No further instance will be launched.", "ready")


def report(force=False):
    with lock("oci-report") as acquired:
        if not acquired:
            return 0
        success_alert()
        current = now()
        if not force and current.hour < 20:
            return 0
        log = DATA / "oci-a1-provision.log"
        text = log.read_text(encoding="utf-8-sig", errors="replace") if log.exists() else ""
        counts, latest = stats(text, current - dt.timedelta(hours=24))
        health = read_json(DATA / "oci-monitor-health.json", {})
        verified = health.get("last_verified")
        stale = not verified or current - dt.datetime.fromisoformat(verified) > dt.timedelta(hours=2)
        running = read_json(DATA / "oci-a1-running.json", {}).get("instance_id")
        message = (
            f"Past 24 hours: {counts['runs']} runs started; {counts['capacity_checks_ok']} completed "
            f"all three domains successfully but found no capacity; {counts['errors']} script errors; "
            f"{counts['provisioned']} new servers.\n"
            f"Latest run: {latest.strftime('%d %b %H:%M %Z') if latest else 'none in 24 hours'}.\n"
            f"Latest monitored result: {health.get('outcome', 'no monitored run yet')}; "
            f"consecutive failed/unverified checks: {health.get('consecutive_failures', 0)}.\n"
            f"Last verified Oracle check: {verified or 'none'}.\n"
        )
        if running:
            message += "A server was observed RUNNING; provisioning stops after its existing success email is handled."
        elif stale:
            message += "ATTENTION: no verified check in over 2 hours. The computer/task or authentication needs checking."
        else:
            message += "Monitoring is healthy. Retry interval: 30 minutes. No capacity is a successful check, not an error."
        failures = read_json(DATA / "oci-notifications.json", {})
        failed = sum(not item.get("delivered", False) for item in failures.values())
        if failed:
            message += f"\nEarlier unconfirmed/failed Telegram deliveries: {failed}; details are logged locally."
        return 0 if notify("daily-" + current.date().isoformat(), "Oracle daily status", message,
                           "attention" if stale and not running else "info") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["check", "report", "report-now"])
    args = parser.parse_args()
    try:
        return check() if args.mode == "check" else report(args.mode == "report-now")
    except Exception as error:
        event("monitor_error", error_type=type(error).__name__)
        try:
            notify("monitor-error-" + now().date().isoformat(), "Oracle monitor needs attention",
                   "The background monitor failed internally (" + type(error).__name__ +
                   "). Inspect the local MediaService logs; this is not a capacity result.", "attention")
        except Exception:
            event("monitor_alert_failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

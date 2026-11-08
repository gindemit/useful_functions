"""Send a configured personal reminder once per scheduled slot (local Windows time)."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys


def due_slot(config, now):
    start = datetime.fromisoformat(config["start_date"]).date()
    if not start <= now.date() < start + timedelta(days=config["days"]):
        return None
    for hour in config["hours"]:
        slot = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if timedelta(0) <= now - slot < timedelta(minutes=10):
            return slot.isoformat(timespec="minutes")
    return None


def run(config_path, dry_run=False):
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    slot = due_slot(config, datetime.now())
    if not slot:
        print("No reminder due; expired or outside a scheduled slot.")
        return 0
    command = [sys.executable, config["helper"], "--status", "attention",
               "--project", config["project"], "--title", config["title"],
               "--message", config["message"]]
    if dry_run:
        return subprocess.run(command + ["--dry-run"], check=False).returncode
    state = config_path.parent / "attempts"
    state.mkdir(exist_ok=True)
    # Claim before network I/O. Ambiguous failures must never send duplicates.
    claim = state / (slot.replace(":", "-") + ".log")
    try:
        with claim.open("x", encoding="utf-8") as log:
            log.write("Claimed " + slot + "\n")
            log.flush()
            try:
                result = subprocess.run(command, stdout=log, stderr=log, timeout=180,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return result.returncode
            except (subprocess.TimeoutExpired, OSError):
                log.write("Delivery uncertain or unavailable; no automatic retry.\n")
                return 1
    except FileExistsError:
        print("Slot already attempted; skipping.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args.config, args.dry_run))

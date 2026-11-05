# Oracle Always Free background monitoring

Windows personal automation for the existing `C:\Work\projects\oracle` provisioning script.
No credentials or machine logs belong in this repository. Runtime state and backups are
in `%LOCALAPPDATA%\MediaService`; the deployed wrapper is beside the existing script.

`install.ps1` backs up the original task XML and provisioning script, installs two
windowless `pythonw.exe` actions under the existing interactive user, and preserves the
original provisioning trigger (30 minutes), principal and settings. It adds explicit
RUNNING evidence before the original success email and preserves full OCI errors.
It does not change shapes, regions, account type or the existing duplicate-instance guards.

The independent reporter wakes hourly, sends once per calendar day at/after 20:00
Windows local time (Berlin on this machine), and catches up when the logged-in computer
is available. It also runs after provisioning stops. It cannot run while the machine is
off or the user is logged out, and cannot alert if both scheduled tasks stop or Telegram
credentials/network access fail. The first report can be sent with `monitor.py report-now`.

Notifications use the installed telegram-notify helper and existing AI Notifications bot:

- One success alert per observed RUNNING instance, independently of the original email.
- Authentication failure immediately, or three consecutive failed/unverified checks;
  at most one failure alert each local day.
- Daily trailing-24-hour counts of starts, complete no-capacity checks, script errors and
  servers created; latest check, verified Oracle response and stale-check warning.
- Notification attempts and delivery outcomes persist locally. Ambiguous or failed
  sends are not automatically resent; inspect `oci-notifications.json`. A daily report
  includes the number of prior unconfirmed deliveries when Telegram is working again.

`oci-monitor-health.json` and `oci-monitor-events.jsonl` distinguish checked capacity,
authentication failure, throttling, unexpected output and incomplete runs. Detailed
captured output is in `oci-monitor-output.log`, alongside the original provisioning log.
No-capacity responses are successful authenticated checks, not successful provisioning.

Validation: `python -m unittest discover -s tools/oracle-always-free -p test_monitor.py -v`.
Install from Windows PowerShell with `-NoProfile -File tools/oracle-always-free/install.ps1`.
Deploy the synchronized telegram-notify helper, including hidden gcloud subprocesses.
Rollback: restore the backed-up script and task XML with `Register-ScheduledTask -Xml`,
then unregister only `MediaService-OCI-DailyStatus`. Runtime logs can be retained.

## Verification on 2026-11-05

Six unit tests passed, including authentication alert/recovery, 7-digit .NET timestamps,
daily stale detection, and suppression of ambiguous duplicate Telegram sends.
Installed task execution authenticated to Oracle and checked all three Frankfurt domains:
no capacity, exit 0, health state `no_capacity`, zero consecutive failures. Both pythonw
and its PowerShell child had a zero main-window handle. The reporting task exited 0 and
Telegram accepted its first daily summary. An initial timestamp parsing failure during
installation was detected by the internal-error alert and fixed before this verification.
Provisioning success delivery is covered with simulated RUNNING evidence; no live server
was created to test that path. Ordinary scheduling is retained at 30 minutes because
the existing log already includes occasional launch throttling at that interval.

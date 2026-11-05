# Oracle Always Free background monitoring

Windows personal automation for the existing `C:\Work\projects\oracle` provisioning script.
No credentials or machine logs belong in this repository. Runtime state and backups are
in `%LOCALAPPDATA%\MediaService`; the deployed wrapper is beside the existing script.

`install.ps1` backs up the original task XML and provisioning script, installs two
windowless `pythonw.exe` actions under the existing interactive user, and preserves the
original principal and settings. A one-minute windowless local wake checks the persisted
cooldown; only due wakes contact Oracle. Normal checks run about every five minutes.
It adds explicit RUNNING evidence before the original success email and preserves full OCI errors.
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

The adaptive retry algorithm uses capped exponential backoff with recovery hysteresis:
5 -> 10 -> 20 -> 30 minute levels on throttling (HTTP 429 / TooManyRequests), also backing
off other errors instead of hammering a broken service/authentication configuration.
Three consecutive verified, nonthrottled checks lower the interval by one level;
another failure resets that streak. Empty capacity counts as a successful check.
Elevated cooldowns have 0-10% downward random jitter; the normal level stays five minutes.
Due times round down to a minute boundary so the cooldown never exceeds 30 minutes;
observed intervals are approximate and include check duration and Windows scheduling.
State survives process restarts/reboots; skipped wakes never contact Oracle, send
notifications or count as capacity checks. Daily summaries include the current level,
recovery streak, next due time and last rate-limit timestamp. Oracle's API guidance
recommends exponential backoff on throttling; these longer minute-scale limits are the
owner's selected capacity-check policy, separate from individual API retries.

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
was created to test that path. The original 30-minute schedule was subsequently replaced
by the owner-requested adaptive 5-30 minute policy described above.

Adaptive-policy validation: nine tests passed, including repeated throttles reaching
the 30-minute cap, three-check recovery through each level, jitter bounds, resetting
the recovery streak and persisted cooldown skips without starting any subprocess.
The installed policy completed a live three-domain check successfully, persisted its
five-minute interval and next eligible time. The following natural scheduler wake
recorded `cooldown_skipped` and exited 0 without an Oracle check.
Backoff itself was tested with simulated
429 responses rather than deliberately rate-limiting the Oracle account.

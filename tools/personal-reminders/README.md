# Personal Telegram reminders

Uses the installed `telegram-notify` helper and Windows Task Scheduler. Personal
message content and delivery logs live under `%LOCALAPPDATA%/AI-Notifications/`,
outside Git. No bot credential is stored in the task or configuration.

Run `install.ps1 -Name <lowercase-id> -Title <title> -Message <message>` in PowerShell.
Defaults: 09:00, 15:00, 22:00, for seven calendar days including today, Berlin time.
Use `-Preview` to inspect without creating files or tasks. An existing task or data
directory is preserved; installation refuses to overwrite it.

The computer must be on, online, and the installing user logged in. Tasks run
silently, including on battery. Missed slots are not replayed; each invocation
allows only the first ten minutes of its slot. Expiration is checked by both
Task Scheduler and the runner. The disabled-by-expiry task remains for inspection.
Each slot is claimed before sending; ambiguous failures are logged and never
automatically retried. Telegram acceptance is not a read receipt.

Inspect with `Get-ScheduledTask -TaskName AI-Notifications-<id>` and
`Get-ScheduledTaskInfo -TaskName AI-Notifications-<id>`. Check the local `attempts`
directory for send results. Stop with
`Unregister-ScheduledTask -TaskName AI-Notifications-<id> -Confirm:$false`.

Validate: `python -m unittest discover -s tools/personal-reminders -v`.

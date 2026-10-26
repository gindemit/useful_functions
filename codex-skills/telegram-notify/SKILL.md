---
name: telegram-notify
description: Notify Konstantin on Telegram when builds or deployments are ready, a task needs review or input, or he requests an alert. Include direct links for easy access on Android across projects.
---

Konstantin explicitly requested this across projects on 2026-10-26: send routine Telegram notifications when a build or deployment is ready, something needs his check/input, or another task event needs his attention. Opening links in Orca Remote on Android is difficult; direct links in Telegram are his preferred way to access results. This is standing authorization for those routine alerts to his own private chat; do not ask him to repeat permission for each one. Honor a later opt-out or task-specific preference. This does not authorize sharing secrets or unrelated private files.

Use the skill from the agent doing the task. It does not monitor events independently or add CI hooks. Avoid routine progress spam; notify for actionable outcomes, failures needing intervention, and requested milestones. For a review/input request, also leave the question in the active conversation: Telegram replies are not routed to agents.

The bot display name is **AI Notifications**; its existing username is `@CryptoTradingDictLab_bot`. Its former crypto webhook and command menu were disabled on 2026-10-26. Do not restore the crypto handler or collect Telegram login codes.

Run the bundled helper with Python and RTK:

```powershell
rtk proxy python C:\Users\khind\.codex\skills\telegram-notify\scripts\send_notification.py --status ready --project "Project name" --title "Build ready" --message "The Android build is ready to install." --link "Download Android app" "https://example.com/app.apk" --link "View release" "https://example.com/releases/1"
```

The example URLs are placeholders: replace them with real, verified artifact or deployment URLs. Resolve the script relative to this skill's folder if installed elsewhere. `--link LABEL URL` is repeatable; the older `--url URL --button LABEL` also works. Links are optional for alerts without an available URL. Use `--status ready|attention|failed|info` and `--project` for a readable heading. The helper safely formats plain input with Telegram HTML, bold titles, status icons, and individual buttons; it also includes raw URLs for copying on Android. Do not pass HTML or Markdown markup in the message.

For a build include project, version/platform if known, validation result, and a direct download or install link. For a deployment include the live app URL. For attention include the exact decision/check and a review URL when available. Prefer phone-accessible HTTPS links; localhost and Windows file paths cannot be opened from the phone. Do not invent URLs, expose credentials, publish private artifacts just to make a link, or claim success before verification. Explain any link that requires sign-in. Signed/private download links require the user's authorization to share that artifact with Telegram.

Use `--dry-run` to preview formatting without credentials or sending. If sending fails, continue the main task where possible and report the notification failure in chat.

The recipient is fixed to the verified private chat for `@konstantin_gindemit`. The helper retrieves the existing bot token in memory from Google Cloud Runtime Config in `cryptotrading-dictlab`, using the local `dictionarylab@gmail.com` gcloud credential. Never print or commit the token. No Firebase function invocation is needed for outbound messages.

The helper sends once and prints the returned message ID. If it reports an ambiguous network failure, do not automatically resend: Telegram may have accepted the message. A success response confirms Telegram accepted it, not that the user read it.

For unattended CI, credentials and an explicit workflow integration must be configured separately; this local skill alone does not add CI notifications or a background service.

Canonical source: `C:\Work\git\gindemit\useful_functions\codex-skills\telegram-notify`. Keep the installed copy in `C:\Users\khind\.codex\skills\telegram-notify` synchronized when editing. The global preference is recorded in `C:\Users\khind\.codex\memories\telegram-notifications.md` and referenced by global `AGENTS.md`.

---
name: telegram-notify
description: Send Konstantin personal Telegram notifications when requested, including build or deployment results, direct download links, and items needing attention.
---

Use this skill when the user requests a Telegram alert or has authorized Telegram notifications for the current work. The user wants actionable notifications with direct clickable URLs. This skill does not monitor events independently: invoke it from the agent performing the authorized work, or wire it into a separately requested automation.

The bot display name is **AI Notifications**; its existing username is `@CryptoTradingDictLab_bot`. Its former crypto webhook and command menu were disabled on 2026-10-26. Do not restore the crypto handler or collect Telegram login codes.

Run the bundled helper with Python and RTK:

```powershell
rtk proxy python scripts/send_notification.py --title "Build ready" --message "The Android build is ready to install." --url "https://example.com/app.apk" --button "Download Android app"
```

Resolve the script relative to this skill's folder. `--url` is optional; use a real, verified artifact or deployment URL. Do not invent download links or report deployment success before verification. Explain failures and required action in the message. Keep routine notifications concise; avoid progress spam.

The recipient is fixed to the verified private chat for `@konstantin_gindemit`. The helper retrieves the existing bot token in memory from Google Cloud Runtime Config in `cryptotrading-dictlab`, using the local `dictionarylab@gmail.com` gcloud credential. Never print or commit the token. No Firebase function invocation is needed for outbound messages.

The helper sends once and prints the returned message ID. If it reports an ambiguous network failure, do not automatically resend: Telegram may have accepted the message. A success response confirms Telegram accepted it, not that the user read it.

For unattended CI, credentials and an explicit workflow integration must be configured separately; this local skill alone does not add CI notifications or a background service.

"""Send one personal Telegram alert without exposing the bot credential."""

import argparse
import base64
import html
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def request_json(url, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Exceptions include the request URL, which contains the Telegram token.
        raise RuntimeError(f"Service returned HTTP {error.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError(
            "Network failure; delivery may be ambiguous. Do not automatically resend."
        ) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--url")
    parser.add_argument("--button", default="Open link")
    parser.add_argument("--project", help="Project or task name shown above the message")
    parser.add_argument("--status", choices=["ready", "attention", "failed", "info"], default="info")
    parser.add_argument("--link", nargs=2, action="append", default=[], metavar=("LABEL", "URL"),
                        help="Add a clickable link and button; repeat for more links")
    parser.add_argument("--dry-run", action="store_true", help="Preview the payload without authentication or sending")
    args = parser.parse_args()
    links = list(args.link)
    if args.url:
        links.insert(0, [args.button, args.url])
    for label, url in links:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            parser.error("Use an HTTPS link without embedded login credentials.")
        if not label.strip() or len(label) > 64:
            parser.error("Link labels must contain 1 to 64 characters.")
    icons = {"ready": "\u2705", "attention": "\U0001f514", "failed": "\u274c", "info": "\u2139\ufe0f"}
    heading = f"{icons[args.status]} {args.title}"
    text = f"<b>{html.escape(heading)}</b>"
    if args.project:
        text += f"\n<i>{html.escape(args.project)}</i>"
    text += "\n\n" + html.escape(args.message)
    for label, url in links:
        text += f'\n\n<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>\n{html.escape(url)}'
    visible = heading + ("\n" + args.project if args.project else "") + "\n\n" + args.message
    visible += "".join(f"\n\n{label}\n{url}" for label, url in links)
    if not args.title.strip() or not args.message.strip() or len(visible.encode("utf-16-le")) // 2 > 4096:
        parser.error("Title and message must be nonempty and the rendered message at most 4096 characters.")
    payload = {"chat_id": 238548435, "text": text, "parse_mode": "HTML",
               "link_preview_options": {"is_disabled": True}}
    if links:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": label, "url": url}] for label, url in links]}
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return

    gcloud = shutil.which("gcloud.cmd") or shutil.which("gcloud")
    if not gcloud:
        raise RuntimeError("gcloud is required to retrieve the stored bot credential.")
    try:
        result = subprocess.run(
            [gcloud, "auth", "print-access-token", "--account=dictionarylab@gmail.com"],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except (subprocess.SubprocessError, OSError):
        raise RuntimeError("Could not authenticate with the local Dictionary Lab gcloud account.") from None
    variable = request_json(
        "https://runtimeconfig.googleapis.com/v1beta1/projects/cryptotrading-dictlab/"
        "configs/telegram/variables/token",
        headers={"Authorization": "Bearer " + result.stdout.strip()},
    )
    token = variable.get("text") or base64.b64decode(variable.get("value", "")).decode()
    if not token:
        raise RuntimeError("The stored bot token is empty.")
    api = "https://api.telegram.org/bot" + token + "/"
    chat = request_json(api + "getChat", {"chat_id": 238548435})
    recipient = chat.get("result", {})
    if not chat.get("ok") or recipient.get("type") != "private" or recipient.get("id") != 238548435:
        raise RuntimeError("The verified private recipient could not be confirmed; nothing sent.")
    sent = request_json(api + "sendMessage", payload)
    if not sent.get("ok"):
        raise RuntimeError("Telegram rejected the notification.")
    print(json.dumps({"sent": True, "message_id": sent["result"]["message_id"]}))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError) as error:
        print(f"Notification failed: {error}", file=sys.stderr)
        sys.exit(1)

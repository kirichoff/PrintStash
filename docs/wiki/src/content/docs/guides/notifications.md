---
title: Notifications
description: Get alerted when a print finishes, fails, or is cancelled, or when a printer goes offline — delivered to webhooks, Discord, Telegram, or ntfy.
---

PrintStash can tell you when something happens instead of making you watch the
dashboard. It sends a notification when a **print completes, fails, or is
cancelled**, and when a **printer goes offline**. Each notification goes to one
or more **channels** you configure: a generic webhook, Discord, Telegram, or
[ntfy](https://ntfy.sh).

:::note
Notifications are **opt-in and off by default**, and only a superuser can manage
them. Turn the master switch on under **Settings → Notifications** first.
:::

## Events

| Event | Fires when |
| --- | --- |
| `print_completed` | A print finishes successfully |
| `print_failed` | A print errors out |
| `print_cancelled` | A print is cancelled — a separate event so you can mute self-cancellations without silencing real failures |
| `printer_offline` | A printer that was online becomes unreachable (it does **not** fire on startup, only on a real transition) |

Each channel subscribes to the events you choose, and can optionally be scoped
to **specific printers** instead of all of them.

## Adding a channel

Open **Settings → Notifications**, flip on the master switch, then **Add
channel**. Pick a type and fill in its fields:

### Webhook (generic)

- **Webhook URL** — where PrintStash POSTs a JSON body `{"event": …, "data": …}`.
- **Signing secret** (optional) — if set, PrintStash adds an
  `X-PrintStash-Signature: sha256=<hmac>` header, an HMAC-SHA256 of the exact
  request body. Recompute it on your receiver to verify the request really came
  from PrintStash.

Every webhook request also carries an `Idempotency-Key` header that is stable
per delivery, so your receiver can safely de-duplicate retries.

### Discord

- **Discord webhook URL** — create one under *Server Settings → Integrations →
  Webhooks*. PrintStash posts a colour-coded embed per event.

### Telegram

- **Bot token** — from [@BotFather](https://t.me/BotFather).
- **Chat ID** — the chat or channel the bot should message (start a chat with
  your bot first, or add it to the group/channel).

### ntfy

- **Server URL** — defaults to `https://ntfy.sh`; set your own for self-hosted ntfy.
- **Topic** — the topic to publish to.
- **Access token** (optional) — for protected topics.

Use the **Test** button to send a sample notification and confirm the channel
works end to end. The card shows the **last delivery status** and, on failure,
the error.

## How delivery works

- Events are queued the instant the print/printer state changes, in the same
  database transaction — so an event is never lost and never duplicated.
- A background dispatcher delivers them. A failed send is **retried with
  exponential backoff** (about 30s, 2m, 10m, 30m) before giving up.
- If a target replies with a rate-limit (`429`/`503` and a `Retry-After`),
  PrintStash waits exactly that long and the rate limit does **not** count
  against the retry budget.
- A channel that keeps failing is **auto-disabled** after several consecutive
  failures, so a dead endpoint stops generating noise. Fix its configuration and
  re-enable it (re-enabling clears the failure count).

:::caution
Delivery URLs that resolve to private, loopback, or link-local addresses are
**blocked** (SSRF protection) — channels must point at a public host.
:::

## Limitations

Notification channel secrets are stored unencrypted in the database (like the
other configured secrets), so keep your install on a trusted network. The
dispatcher is designed for the default single-node deployment. See
[Known limitations](/reference/known-limitations/) for the full list.

---
name: bo3-match-alerts
description: "Use when maintaining BO3 starred-match Telegram alerts."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [bo3, cs2, alerts, telegram, cron]
---

# BO3 match alerts

## When to Use

Maintain, verify, or change the installed BO3 starred CS2 Telegram watchdog. Do not use for unrelated esports sources.

## Prerequisites

Use the profile-local `$HERMES_HOME/scripts/bo3_watch.py` script-only watchdog and its `bo3_pipeline.py` and `bo3_alert_core.py` modules. Find existing jobs with `cronjob_manage(action='list')` and update rather than duplicate. The task preference is CS2, BO3 source `/matches/current`, at least two filled rating stars (any tournament tier; no S-tier-only restriction), details and direct stream links, with a default 10-minute warning and 1-minute checks. Confirm altered timing with the user's current request.

## Source rules

- Count `.o-icon--star-1.filled`, not all five star placeholders. Tournament tier is not rating.
- Read live pages via Hermes' configured `tools.browser_use_cli.browser_exec`; direct HTML and API HTTP requests can return 403. Use a dedicated named browser session and the supported helper entry point, not guessed endpoints or archived schedules.
- Wait for actual content, not just navigation completion. Detail readiness must include JSON-LD with `startDate`; a visible h1/tournament alone can precede metadata.
- Force browser timezone UTC. Schedule JSON-LD can contain only the first few rows, so join it to DOM match links and use displayed UTC time plus date from the match slug for remaining rows. Before alerting, retrieve exact `startDate` and tournament from the match page.
- Streams are buttons, not outgoing anchors. Click `.c-nav-streams__item`, read the actual `.c-widget-streams iframe` src, then convert Twitch channel, Kick player path, or YouTube embed ID to the genuine public stream URL. Do not infer providers from channel names. Capture languages and prefer English. If absent, say streams are not yet listed and include the match page.
- Embed JavaScript selectors via Python `repr` where nesting quotes; test execution rather than trusting syntax checks alone.

## Scheduling and delivery

- Use `no_agent=true`, script filename relative to `$HERMES_HOME/scripts`, and an explicit `telegram:<chat_id>` resolved from the current profile's channel directory. Empty stdout must mean silence. This incurs no per-minute LLM usage.
- Preserve persistent dedupe under `$HERMES_HOME/data/bo3-match-alerts`; avoid overlapping scans with flock. Match URL identity, not start time, prevents reschedule duplicates.
- Gateway-managed Telegram delivery can work even when standalone `hermes send` fails for lack of a native token. Do not copy gateway secrets or invent credentials. Verify a one-shot no-agent delivery through the running gateway, then read cron execution history: `delivery_outcome=delivered` is stronger evidence than script completion alone.
- A durable enabled cron job still requires the host/gateway scheduler to run. Check `hermes cron status`, job health and `last_delivery_error` before claiming operational success.
- The watchdog currently records dedupe before handing stdout to the scheduler's durable delivery pipeline; an abrupt kill in that narrow handoff gap can lose an alert. Do not claim strict exactly-once delivery.

## Message layout

The user wants alerts without the scheduler's metadata header (job name/ID) or stop/manage footer. Use `hermes config set cron.wrap_response false` and verify with `hermes config get cron.wrap_response`. This is a profile-wide cron delivery setting, not part of the alert renderer; it applies to all cron jobs in this profile. The scheduler reads it at delivery time, so no gateway restart is needed.

Use the production `format_alert` renderer for both actual alerts and previews. The user prefers emoji-led sections, bold team/tournament names, a compact human countdown (for example `10m` or `5m 30s`, never fractional minutes), star emojis with bold BO format, an exact UTC timestamp, named clickable stream links with languages, and a named BO3 details link. Emit standard Markdown (`**bold**`, `[label](url)`); the Telegram adapter converts it to native entities/MarkdownV2. Do not emit raw HTML or pre-escape the whole message as MarkdownV2. Verify with the real Telegram adapter's `format_message` and a delivered real-match preview.

## Verification

- For a requested 1:1 test, use a real upcoming qualifying match from the live source and the production `format_alert` function, with real streams and the actual countdown. Send through the same cron delivery target without touching production dedupe. Do not substitute a settings-summary message or invent a ten-minute countdown.
- Re-arm a paused or completed one-shot verification job with `terminal(command="hermes cron resume <listed-job-id> --run-now")`. Plain resume can reject an old timestamp, and `cron run` can refuse a disabled job even when creation guidance suggests otherwise. Update its script if needed, then re-arm and verify a fresh execution's delivery outcome. Follow [live delivery verification](references/delivery-verification.md) for the tested preview and read-back procedure.
- Separate scan health, eligibility correctness, scheduling cadence, and delivery health when answering whether the job works. Read recent execution timestamps, `health.json`, and the actual `due_matches` predicate; a job label or health counter is not proof of the star threshold. Compare actual successive execution starts rather than equating `every 1m` with observed one-minute execution. Report any cadence discrepancy without changing timing unless requested.

For watchdog lock handling, the `with ...open(...) as lock` context releases the OS flock on close, including early return and exceptions. Never append a dangling `finally` or call nonexistent `lock.unlock()` on a file object. Cover the actual `main --inspect` path in tests as well as `run_once`, then verify a real cron run after edits.

Run core and watchdog tests with `python -m unittest -v test_bo3_alert_core test_bo3_watch` from `$HERMES_HOME/scripts`. Run the live integration test `test_bo3_pipeline.py` with Hermes' full Python environment; a bare host Python may lack dependencies. `bo3_watch.py --inspect` fetches the live schedule without sending or marking alerts. The ordinary watchdog emits eligible alerts, so do not run it manually during a due window merely to preview output. Read `data/bo3-match-alerts/health.json` and cron's durable run/delivery records after the first scheduled run.

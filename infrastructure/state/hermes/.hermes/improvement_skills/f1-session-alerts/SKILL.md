---
name: f1-session-alerts
description: "Use when maintaining F1 session Telegram reminders."
version: 0.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [formula1, f1, cron, telegram, alerts]
---

# F1 session reminders

## When to Use

Maintain the default profile's F1 daily planner, schedule sources, one-shot reminders and previews. Resolve `$HERMES_HOME`; do not modify other profiles or BO3 jobs. List jobs before editing. The existing planner is named `F1 hourly schedule refresh and reminder planner` and runs `f1_daily.py` at `0 * * * *` (the top of every hour). The user changed the preference from daily to hourly; keep the historical script filename. Do not reintroduce every-minute F1 polling.

## User intent and layout

Notify the requesting Telegram chat 10 minutes before Qualifying, Sprint Qualifying (including legacy Sprint Shootout), Sprint and Race. Exclude practice and testing. Use real countdown, UTC start, Grand Prix and circuit, official schedule link and subscription/regional caveat.

The user confirmed `https://f1tv.formula1.com/open` opens F1 TV from Telegram on their iPhone. Use `[Open F1 TV app](https://f1tv.formula1.com/open)` plus `[Watch in browser](https://f1tv.formula1.com/)`. The app link opens the app, not a specific session or guaranteed autoplay. F1 TV's apple-app-site-association includes /open and /detail/* but excludes the homepage; /open returned 404 in a desktop HTTP check, so retain the separate normal-web fallback. Never invent stream IDs or free stream links.

## Architecture and sources

- `f1_source.py`: primary Jolpica `/ergast/f1/{year}.json?limit=100`, fallback FastF1's public `https://raw.githubusercontent.com/theOehrly/f1schedule/master/schedule_{year}.json`. Both were verified live and agreed on upcoming times. Try fallback on HTTP, parsing or empty-source failure. API requests have timeout and bounded retry. Detect truncated Jolpica response. Query next season from November; unpublished next season must not invalidate current season.
- Do NOT use unauthenticated OpenF1 for this job. Its API can return 401 for ALL queries during any live F1 session, even schedule/historical queries. Initial successful tests outside a live window do not establish availability. A paid OpenF1 key is not needed for the replacement sources.
- `f1_alert_core.py`: normalize Jolpica UTC date+time, select exact session names; shared identity `f1:{year}:{round}:{session}` across primary/fallback prevents duplicates when a source changes. FastF1 dates are track-local naive strings: combine with the explicit gmt_offset, then normalize to UTC; never assume naive means UTC or guess missing times. Skip round-zero preseason tests.
- `f1_daily.py`: fetch once hourly and reconcile a rolling 14-day horizon of durable one-shot cron jobs at start minus 10 minutes. Each generated `scripts/f1_session_<sha256-prefix>.py` calls `deliver_session(id)`, which reads only the saved schedule and sent state, with no network or LLM. Use explicit Telegram delivery target and `no_agent=true` for all jobs. The current target is profile default's Telegram chat 5849017560; confirm current context before reusing elsewhere.
- Reconciliation lists existing owned script-prefix jobs, creates missing jobs, updates changed times and removes cancelled/unwanted pending jobs. Never recreate identical jobs on repeated refresh. It uses Hermes native job APIs and scheduler registration; verify stored jobs after writes. Do not hand-edit jobs.json. A source failure before reconciliation must retain the last-good snapshot and all already-queued reminders. If both fail, report daily refresh failure, not silent success.
- `data/f1-session-alerts/schedule.json`, `plan.json`, `sent.json`, `health.json`, `last_alert.json`, `last_error.json` persist state. Migrate legacy OpenF1 sent identities by session type and UTC start before replacing its snapshot. Failure history may remain after recovery: compare timestamps. Sent is recorded before stdout handoff, leaving a narrow crash gap; do not claim strict exactly-once delivery.

## Timing trade-off

Hourly refresh deliberately trades immediate reschedule detection for low overhead; changes between refreshes can still be missed. Last-minute timetable changes after the refresh may not be captured. Reminders are one-shot jobs at the desired instant, subject to gateway dispatch jitter, not a once-daily alert batch. Source outage cannot block previously queued sends. Host/gateway must still run. Planner stdout is empty on success; errors remain visible to the owner.

## Verification and previews

Run `python -m unittest -v test_f1_alert_core test_f1_watch test_f1_daily test_f1_jolpica` from scripts. Tests cover selected session types, UTC offsets, source failover, no guessed times, duplicate suppression, reschedule/cancel reconciliation and network-free delivery. Exercise real fallback by mocking only primary failure and letting FastF1 actually fetch; do not substitute fake schedule data for integration results. Compare upcoming starts across both real sources.

Run the actual planner via `hermes cron run <listed-planner-id>`, then read back cron list, health and plan. Repeat once to verify idempotency and stable queued job IDs. Confirm the next hourly run and individual reminder timestamps.

`f1_watch.py` is retained for manual --inspect/--preview and legacy tests, not scheduled production polling. Its source now uses `f1_source.collect_schedule`; preview cache may refresh manually. `--preview` renders the earliest real future session without changing sent state. If user merely wants to see the message, run it and paste the renderer output rather than re-arming a delivery job.

For an explicitly requested end-to-end delivery test, `f1_delivery_check.py` invokes production preview. Reuse a listed one-shot test via `hermes cron resume <id> --run-now` (plain run can refuse completed jobs). Require exact execution `delivery_outcome=delivered` in read-only `cron/executions.db`, not just completed. Preview/inspect uses blocking flock to wait for scans; routine legacy scans alone use LOCK_NB. Otherwise a preview can silently return empty and be suppressed. Never call nonexistent file.unlock or append unmatched finally. Keep lock-contention regression tests.

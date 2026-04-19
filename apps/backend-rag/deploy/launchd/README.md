# Cost Advisor launchd plists (Pro only)

Two macOS launchd agents for the weekly CostAdvisor pipeline. They run on
the Pro machine (dev/server), NOT on Fly.io (which never sees these).

## Install

```bash
cp apps/backend-rag/deploy/launchd/com.nuzantara.cost-advisor-weekly.plist \
   ~/Library/LaunchAgents/
cp apps/backend-rag/deploy/launchd/com.nuzantara.cost-advisor-daily-cap.plist \
   ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nuzantara.cost-advisor-weekly.plist
launchctl load ~/Library/LaunchAgents/com.nuzantara.cost-advisor-daily-cap.plist
```

## Schedule

- **Weekly report**: Monday 07:00 local time (WITA/WIB). Full CostAdvisor
  analysis: last 7 days by endpoint × model, spike detection vs 28d
  baseline, Claude OAuth Max for substitution proposals, persist top-N
  to `llm_cost_recommendations`, Telegram report to chat `1125336968`.
- **Daily cap check**: every day 08:00 local. Reads last-24h total spend;
  alerts Telegram if > `$20.00` (see
  `backend.scripts.cost_advisor_cli.DAILY_SPEND_ALERT_THRESHOLD_USD`).

## Required env

- `DATABASE_URL` — via the usual Pro dev env (venv + project .env)
- `TELEGRAM_BOT_TOKEN` — for delivery; missing → silent skip (logged)
- `TELEGRAM_OWNER_CHAT_ID` — defaults to `1125336968`
- **NEVER** `ANTHROPIC_API_KEY` — Claude via OAuth Max CLI only

## Logs

- `/tmp/cost-advisor-weekly.log` / `.err`
- `/tmp/cost-advisor-daily.log` / `.err`

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.nuzantara.cost-advisor-weekly.plist
launchctl unload ~/Library/LaunchAgents/com.nuzantara.cost-advisor-daily-cap.plist
rm ~/Library/LaunchAgents/com.nuzantara.cost-advisor-*.plist
```

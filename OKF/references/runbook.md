---
type: Reference
title: Runbook
description: Operations guide — startup, shutdown, monitoring, and troubleshooting for ToobitBot.
tags: [runbook, operations, troubleshooting]
status: stable
generated: { by: hermes/2.0, at: 2026-09-22T12:00:00Z }
---

# Runbook

## Startup

```bash
cd toobitbot
source venv/bin/activate
python main.py
```

## Shutdown

Ctrl+C — graceful shutdown (completes current tick).

## Monitoring

```bash
# Watch log
tail -f data/scanner.log

# Check open positions
cat data/positions.json | python3 -m json.tool

# Check equity
cat data/equity.json
```

## Troubleshooting

### No signals detected
- Check API connectivity: `curl https://api.toobit.com/api/v1/time`
- Verify symbol count: should be ~655
- Check logs: `data/scanner.log`

### Telegram not receiving
- Verify BOT_TOKEN and CHANNEL_ID in .env
- Check bot is admin in channel
- Test: `curl -s "https://api.telegram.org/bot<TOKEN>/getMe"`

### Position stuck in `signal`
- Check if signal candle left 250-bar window (>20h)
- Stale TTL: auto-closes after 48h at 0R
- Manual fix: edit `positions.json`, set `state: "expired"`

### High memory usage
- Reduce `symbols_limit` in config.yaml
- Reduce `max_workers` (default 8)

## Data Files

| File | Purpose | Reset |
|------|---------|-------|
| `data/positions.json` | All signals | `echo '[]' > data/positions.json` |
| `data/equity.json` | Equity tracking | `rm data/equity.json` (resets to $100) |
| `data/next_id.txt` | Signal ID counter | `echo "1" > data/next_id.txt` |
| `data/scanner.log` | Scan log | `> data/scanner.log` |

## Cron Deployment

```bash
# Every 3 minutes
*/3 * * * * cd /path/to/toobitbot && /path/to/venv/bin/python main.py >> data/cron.log 2>&1
```

Or use a systemd service for continuous operation.

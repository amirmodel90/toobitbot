---
type: Reference
title: Runbook
description: Operations guide — startup, shutdown, monitoring, and troubleshooting for ToobitBot.
tags: [runbook, operations, troubleshooting]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
---

# Runbook

## Startup

```bash
cd /home/hermes/toobitbot
source venv/bin/activate
python main.py
```

## Shutdown

Ctrl+C — graceful shutdown (completes current candle scan).

## Scan Loop (Candle-Aligned)

The main loop runs at **5-minute candle close + 3s buffer**:
```
Next boundary = ((now_ms // 300000) + 1) × 300000
Wait = (next_boundary + 3000) - now_ms
```

This ensures scans always start at candle open, eliminating drift.

## Monitoring

```bash
# Watch log
tail -f data/scanner.log

# Check open positions
cat data/positions.json | python3 -m json.tool

# Check equity
cat data/equity.json

# Check performance
grep "scan complete" data/scanner.log | tail -5
```

## Troubleshooting

### No signals detected
- Check API connectivity: `curl https://api.toobit.com/api/v1/time`
- Verify symbol count: should be ~214 (leverage > 10 + volume > 1M)
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
- Reduce `symbols_limit` in config.yaml (default 280)
- Reduce `max_workers` (default 8)
- Candle cache auto-cleared each scan (~3MB for 214 symbols)

### Async HTTP errors
- Check aiohttp installed: `pip show aiohttp`
- Verify `async_http.max_concurrent` in config.yaml (default 20)
- Rate limit: 3000 req/min — semaphore prevents bursts

### Margin check reducing volume
- Log: `[MARGIN ADJUST] SYM volume reduced to X.XXXXXX`
- Check equity.json — is equity too low?
- Check config `positions.margin_buffer_pct` (default 0.9)

## Data Files

| File | Purpose | Reset |
|------|---------|-------|
| `data/positions.json` | All signals | `echo '[]' > data/positions.json` |
| `data/equity.json` | Equity tracking | `rm data/equity.json` (resets to $100) |
| `data/next_id.txt` | Signal ID counter | `echo "1" > data/next_id.txt` |
| `data/scanner.log` | Scan log | `> data/scanner.log` |

## Cron Deployment (Legacy — main.py now runs continuously)

```bash
# Every 3 minutes (old fixed-interval mode)
*/3 * * * * cd /path/to/toobitbot && /path/to/venv/bin/python main.py >> data/cron.log 2>&1
```

**Recommended:** Run `main.py` directly as a continuous process (systemd, PM2, or screen). The candle-aligned loop handles timing automatically.

## Systemd Service Example

```ini
[Unit]
Description=ToobitBot
After=network.target

[Service]
Type=simple
User=hermes
WorkingDirectory=/home/hermes/toobitbot
ExecStart=/home/hermes/toobitbot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
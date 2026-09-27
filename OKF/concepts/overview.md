---
type: Reference
title: ToobitBot Overview
description: Project overview and architecture of the Toobit USDT-M perpetual futures trading bot.
tags: [overview, architecture]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-24T17:00:00Z }
---

# ToobitBot Overview

ToobitBot is a multi-strategy signal scanner and trading bot for Toobit USDT-M (perpetual futures) exchange. It detects entry signals using four strategies (str1-4), monitors open positions, and sends Telegram notifications with charts.

## Architecture

```
main.py (entry point)
  ├── config.yaml (configuration)
  ├── scanner/phase1_detect.py (signal detection)
  ├── scanner/phase2_monitor.py (position monitoring)
  ├── scanner/simulation.py (SL/TP/BE exit logic)
  ├── scanner/chart_gen.py (chart generation)
  ├── scanner/position_manager.py (positions.json + equity.json)
  ├── toobit_api/client.py (REST API)
  ├── toobit_api/ws_client.py (WebSocket streams)
  ├── notifications/telegram.py (chart + caption)
  └── strategies/str1-4.py (signal detection logic)
```

## Scan Loop (every 10 minutes)

1. Fetch exchange info → filter symbols with leverage > 10 AND 24h volume > 1M USDT
2. Sort by 24h quote volume → top 280 symbols
3. For each symbol × each strategy (parallel, 8 workers):
   - Fetch 250 candles (5m) → **sorted(oldest→newest)** for Toobit API
   - Run strategy.detect()
   - Compute SL (per-strategy sl_mode)
   - Compute TP (per-strategy tp_rr)
   - Apply distance filters (min/max_dist_pct)
   - Result-first replay (simulate exit on closed candles)
   - Save to positions.json
   - Send Telegram notification (chart + caption)
4. Monitor open positions (phase2):
   - Replay from signal candle
   - Update on state change (TP/SL/BE/MA exit)
   - Send update notification

**Performance:** ~0.33s per symbol, ~71s per strategy, **~5.4 min total for 215 syms × 4 strats**

## Risk Model

- Per-strategy risk percentage (from config.yaml)
- risk_usd = equity × risk_pct
- volume = risk_usd / |entry - SL|
- Fee: 0.045% per fill (entry + exits)
- Net PnL = Gross PnL − total fees

## Position States

| State | Meaning |
|-------|---------|
| `signal` | Open, monitoring |
| `tp_hit` | TP reached, SL→BE, trailing |
| `be_exit` | SL hit after TP (break-even) |
| `ma_exit` | MA trailing exit |
| `ma_half_exit` | 50% closed at MA cross (str4) |
| `sl_hit` | Stop loss hit |
| `expired` | Unresolved >48h, auto-closed at 0R |

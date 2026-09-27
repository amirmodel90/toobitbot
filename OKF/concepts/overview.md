---
type: Reference
title: ToobitBot Overview
description: Project overview and architecture of the Toobit USDT-M perpetual futures trading bot.
tags: [overview, architecture]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
---

# ToobitBot Overview

ToobitBot is a multi-strategy signal scanner and trading bot for Toobit USDT-M (perpetual futures) exchange. It detects entry signals using four strategies (str1-4), monitors open positions, and sends Telegram notifications with charts.

## Architecture

```
main.py (async entry point)
  ├── config.yaml (configuration)
  ├── scanner/phase1_detect.py (signal detection, async fetch)
  ├── scanner/phase2_monitor.py (position monitoring)
  ├── scanner/simulation.py (SL/TP/BE/MA exit logic)
  ├── scanner/chart_gen.py (chart generation)
  ├── scanner/position_manager.py (positions.json + equity.json)
  ├── toobit_api/client.py (async REST + sync private)
  ├── toobit_api/ws_client.py (WebSocket streams)
  ├── notifications/telegram.py (chart + caption)
  └── strategies/str1-4.py (signal detection logic — DO NOT MODIFY)
```

## Scan Loop (candle-aligned: runs at 5m candle close + 3s buffer)

1. Fetch exchange info → filter symbols with leverage > 10 AND 24h volume > 1M USDT
2. Sort by 24h quote volume → top 280 symbols (actual ~214)
3. **Async batch fetch**: Get 250 candles (5m) for all symbols concurrently (max 20 concurrent)
4. For each symbol × each strategy (parallel, 8 workers):
   - Use cached candles (sorted oldest→newest)
   - Run strategy.detect()
   - Compute SL (per-strategy sl_mode)
   - Compute TP (per-strategy tp_rr)
   - Apply distance filters (min/max_dist_pct)
   - **Margin check**: auto-reduce volume if required margin > 90% equity
   - Result-first replay (simulate exit on closed candles)
   - Save to positions.json
   - Send Telegram notification (chart + caption)
5. Monitor open positions (phase2, parallel):
   - Replay from signal candle
   - Update on state change (TP/SL/BE/MA exit)
   - Send update notification

**Performance (215 symbols × 4 strategies):**
- Async candle fetch: ~35s (vs 65s sync ThreadPool)
- Strategy processing: ~6s
- **Grand total: ~43s** (vs 73s sync) — **1.67× speedup**

## Risk Model

- Per-strategy risk percentage (from config.yaml)
- risk_usd = equity × risk_pct
- volume = risk_usd / \|entry - SL\|
- **Margin check**: margin_required = (volume × entry) / max_leverage; if > 90% equity → reduce volume
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
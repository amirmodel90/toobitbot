---
type: Reference
title: Notifications
description: Telegram notification format — chart image and HTML caption for signal and update events.
tags: [telegram, notification, chart, caption]
status: stable
generated: { by: hermes/2.0, at: 2026-09-22T12:00:00Z }
---

# Notifications

## Format

Each notification sends a chart image with an HTML caption to the configured Telegram channel.

## Caption Structure

```
🔔 SIGNAL | #BTC-SWAP-USDT (#s1)

📈 Strategy: str1 (5m)
🔤 Type: BUY
💵 Entry: $95000.0000
🛑 Stop Loss: $94000.0000
🎯 Take Profit: $97500.0000
📍 Status: SIGNAL

💰 Position & PnL ($):
💼 Volume: 5.25 BTC
💰 Risk/Trade: $5.25
📈 Equity: $100.00
🎯 TP → +$137.81
🛑 SL → -$5.25
🛡️ BE → $0.00

Events / Path:
• OPEN (Signal)

🕒 Time: 2026-09-22 12:00 UTC
```

## Event Emojis

| State | Emoji | Title |
|-------|-------|-------|
| `signal` | 🔔 | SIGNAL |
| `tp_hit` | 🎯 | TP HIT |
| `sl_hit` | ❌ | SL HIT |
| `be_exit` | 🛡️ | BE EXIT |
| `ma_exit` | 📊 | MA EXIT |
| `ma_half_exit` | 🔷 | MA EXIT 50% — OPEN |

## Chart Format

- Dark theme (#1e1e1e background)
- Candlestick chart with MA21 overlay
- TP line (lime dashed), SL line (red), BE line (orange)
- Entry marker (green/red triangle)
- Event markers (TP HIT, SL HIT, BE EXIT, MA EXIT, etc.)
- Volume subplot
- Text box with strategy, type, state, entry, and event path

## Window Logic

- Default: 15 candles before entry, 40 after (or to last event + 10)
- Max 100 candles: prioritize from exit backwards
- Min: entry candle must be closed (not forming)

## Realized PnL (on close)

```
✅ Realized: +$132.56$ (fee −$5.25$)
```

Shown only when position is closed (state != signal).

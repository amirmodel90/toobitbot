---
type: Reference
title: Order Lifecycle
description: The full lifecycle of a trade signal from detection through execution to close.
tags: [order, lifecycle, signal, execution]
status: stable
generated: { by: hermes/2.0, at: 2026-09-22T12:00:00Z }
---

# Order Lifecycle

## Phase 1: Signal Detection

1. Fetch 250 candles for symbol
2. Run `strategy.detect(cds, idx, cfg, ind)` for each closed candle
3. On signal: compute SL using `compute_sl()` with strategy's `sl_mode`
4. Compute TP: `entry ± risk × tp_rr`
5. Apply distance filters (`min_dist_pct`, `max_dist_pct`)
6. Result-first replay: `simulate_exit()` on closed candles after entry
7. Save to `positions.json`
8. Send Telegram notification with chart

## Phase 2: Position Monitoring

For each open position (`state == "signal"`):
1. Fetch 250 candles
2. Find signal candle by `open_time`
3. Replay using `simulate_exit()` or `simulate_forward_from()`
4. On state change: update `positions.json`, send Telegram update
5. Stale TTL: unresolved >48h → auto-close at 0R

## Order Placement (Future — API key required)

When API keys are provided:

**Entry:**
```
POST /api/v1/futures/order
  symbol=BTC-SWAP-USDT&side=BUY_OPEN&type=LIMIT&quantity=10
  &price=95000&priceType=INPUT&newClientOrderId=xxx
  &takeProfit=97500&stopLoss=94000
```

**Take-Profit/Stop-Loss attached:**
- `takeProfit` — TP trigger price
- `stopLoss` — SL trigger price
- `tpTriggerBy` / `slTriggerBy` — CONTRACT_PRICE or MARK_PRICE
- `tpOrderType` / `slOrderType` — MARKET or LIMIT

**Cancel:**
```
POST /api/v1/futures/order/cancel
  &symbol=BTC-SWAP-USDT&orderId=xxx
```

## Position Sides

| Value | Meaning |
|-------|---------|
| `BUY_OPEN` | Open long |
| `SELL_OPEN` | Open short |
| `BUY_CLOSE` | Close short |
| `SELL_CLOSE` | Close long |

## Order Types

| Type | Description |
|------|-------------|
| `LIMIT` | Standard limit order |
| `STOP` | Stop order (triggers at stopPrice) |
| `STOP_PROFIT_LOSS` | TP/SL attached to position |

## Margin Types

- `CROSS` — cross margin (shared across positions)
- `ISOLATED` — isolated margin (per-position)

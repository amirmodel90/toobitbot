---
type: Reference
title: Order Lifecycle
description: The full lifecycle of a trade signal from detection through execution to close.
tags: [order, lifecycle, signal, execution]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
---

# Order Lifecycle

## Phase 1: Signal Detection

1. Fetch 250 candles for symbol (async batch for all symbols)
2. Run `strategy.detect(cds, idx, cfg, ind)` for each closed candle
3. On signal: compute SL using `compute_sl()` with strategy's `sl_mode`
4. Compute TP: `entry ± risk × tp_rr`
5. Apply distance filters (`min_dist_pct`, `max_dist_pct`)
6. **Margin check**: 
   - `margin_required = (volume × entry) / max_leverage`
   - If `margin_required > 90% equity` → `volume = min(volume, (0.9 × equity × leverage) / entry)`
   - Recalculate `risk_usd = volume × risk_per_unit`
7. Result-first replay: `simulate_exit()` on closed candles after entry
8. Save to `positions.json` (includes `leverage_used`, `margin_required`)
9. Send Telegram notification with chart

## Phase 2: Position Monitoring

For each open position (`state == "signal"`):
1. Fetch 250 candles (sync wrapper, parallel per symbol)
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

## Position Fields (positions.json)

```json
{
  "signal_id": 123,
  "symbol": "BTC-SWAP-USDT",
  "type": "BUY",
  "strategy": "str1",
  "entry": 95000.0,
  "sl": 94000.0,
  "tp": 97500.0,
  "volume": 0.00525,
  "leverage_used": 20,
  "margin_required": 2.50,
  "risk_usd": 5.25,
  "state": "signal"
}
```
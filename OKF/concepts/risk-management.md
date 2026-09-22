---
type: Reference
title: Risk Management
description: Risk model, position sizing, fee structure, and drawdown controls.
tags: [risk, position-sizing, fees, drawdown]
status: stable
generated: { by: hermes/2.0, at: 2026-09-22T12:00:00Z }
---

# Risk Management

## Per-Strategy Risk

Each strategy has a fixed risk percentage of equity per trade:

| Strategy | Risk % |
|----------|--------|
| str1 | 5.25% |
| str2 | 7.00% |
| str3 | 3.75% |
| str4 | 5.75% |

```
risk_usd = current_equity × risk_pct[strategy]
```

## Position Sizing

```
risk_per_unit = |entry_price - stop_loss_price|
volume = risk_usd / risk_per_unit
```

Example: equity=$100, risk=5.25%, entry=$95000, SL=$94000
- risk_usd = $5.25
- risk_per_unit = $1000
- volume = 0.00525 BTC

## Fee Model

0.045% charged on every fill's notional value:
- Entry fill: `0.045% × entry_price × volume`
- Each exit fill: `0.045% × exit_price × volume`

For str4 (MA half-exit): 3 fills total
- 100% at entry
- 50% at MA cross price
- 50% at final exit price

```
total_fee = 0.00045 × Σ|price_i × qty_i|
net_pnl = gross_pnl − total_fee
```

## Distance Filters

- `min_dist_pct` — SL must be ≥ X% of entry (fee drag control)
- `max_dist_pct` — SL must be ≤ Y% of entry (wide-SL guard)

## Max Concurrent Positions

1 position at a time (configurable in `config.yaml`).

## Stale TTL

Positions unresolved for >48 hours are auto-closed at 0R (no PnL impact).

## Equity Tracking

`equity.json` stores:
```json
{
  "equity": 100.0,
  "risk_pct": 0.0525,
  "risk_usd": 5.25,
  "start": 100.0
}
```

Updated on every position close.

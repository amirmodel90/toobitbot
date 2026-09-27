---
type: Reference
title: Risk Management
description: Risk model, position sizing, fee structure, margin check, and drawdown controls.
tags: [risk, position-sizing, fees, drawdown, margin]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
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

**Step 1: Risk-based sizing (primary)**
```
risk_per_unit = |entry_price - stop_loss_price|
volume = risk_usd / risk_per_unit
```

**Step 2: Margin check (safety)**
```
notional = volume × entry_price
margin_required = notional / max_leverage   # Cross Margin
available_margin = equity × 0.9             # 90% buffer

if margin_required > available_margin:
    max_volume = (available_margin × max_leverage) / entry_price
    volume = min(volume, max_volume)
    risk_usd = volume × risk_per_unit       # Recalculate actual risk
```

Example: equity=$100, risk=5.25%, entry=$95000, SL=$94000
- risk_usd = $5.25
- risk_per_unit = $1000
- volume = 0.00525 BTC (risk-based)
- notional = $498.75, margin_required = $24.94 (20x)
- available = $90 → OK

Example: equity=$10, risk=5%, entry=$50000, SL=$49900 ($100/unit)
- risk_usd = $0.50
- volume = 0.005 BTC (risk-based)
- notional = $250, margin_required = $12.50 (20x)
- available = $9 → **EXCEEDED** → volume reduced to 0.0036 BTC, risk_usd = $0.36

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

## Leverage & Liquidation

- Leverage does NOT affect position size calculation (risk-based only)
- Leverage ONLY affects: Margin Required, Liquidation Price
- Liquidation (long): `entry × (1 - 1/leverage + maintenance_margin)`
- Higher leverage = closer liquidation = less buffer for spikes
- Recommended: 20x–50x balance between capital efficiency and safety
---
type: Attested Computation
title: Position Size Calculator
description: Calculates position size based on account equity, risk percentage, stop-loss distance, and margin constraints.
tags: [position-sizing, risk, margin]
status: stable
runtime: python
parameters:
  - { name: equity, type: float, required: true }
  - { name: risk_pct, type: float, required: true }
  - { name: entry_price, type: float, required: true }
  - { name: sl_price, type: float, required: true }
  - { name: max_leverage, type: float, required: true }
executor:
  resource: references/scripts/calc_position_size.py
  receipt: [risk_usd, risk_per_unit, volume, margin_required, volume_adjusted]
attester:
  resource: references/attesters/verify_position_size.py
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
---

# Computation

```python
# Step 1: Risk-based sizing
risk_usd = equity * risk_pct
risk_per_unit = abs(entry_price - sl_price)
volume = risk_usd / risk_per_unit if risk_per_unit > 0 else 0

# Step 2: Margin check (Cross Margin)
notional = volume * entry_price
margin_required = notional / max_leverage
available_margin = equity * 0.9  # 90% buffer

# Step 3: Adjust if margin exceeded
if margin_required > available_margin:
    max_volume = (available_margin * max_leverage) / entry_price
    volume = min(volume, max_volume)
    risk_usd = volume * risk_per_unit  # Recalculate actual risk
    margin_required = (volume * entry_price) / max_leverage
    volume_adjusted = True
else:
    volume_adjusted = False
```

## Example 1: Normal (margin OK)

- equity = $100
- risk_pct = 5.25%
- entry_price = $95000
- sl_price = $94000
- max_leverage = 20

```
risk_usd = 100 × 0.0525 = $5.25
risk_per_unit = |95000 - 94000| = $1000
volume = 5.25 / 1000 = 0.00525 BTC
notional = 0.00525 × 95000 = $498.75
margin_required = 498.75 / 20 = $24.94
available_margin = 100 × 0.9 = $90
→ OK (24.94 ≤ 90), volume_adjusted = False
```

## Example 2: Tight SL, small equity (margin EXCEEDED)

- equity = $10
- risk_pct = 5%
- entry_price = $50000
- sl_price = $49900
- max_leverage = 20

```
risk_usd = 10 × 0.05 = $0.50
risk_per_unit = |50000 - 49900| = $100
volume = 0.50 / 100 = 0.005 BTC
notional = 0.005 × 50000 = $250
margin_required = 250 / 20 = $12.50
available_margin = 10 × 0.9 = $9.00
→ EXCEEDED (12.50 > 9.00)

max_volume = (9.00 × 20) / 50000 = 0.0036 BTC
volume = min(0.005, 0.0036) = 0.0036 BTC
risk_usd = 0.0036 × 100 = $0.36
margin_required = (0.0036 × 50000) / 20 = $9.00
→ OK, volume_adjusted = True
```

## Key Principle

**Leverage does NOT determine position size.** Position size is determined by risk percentage and stop-loss distance. Leverage only determines whether the position fits in available margin. If not, volume is automatically reduced and actual risk becomes lower than the configured risk_pct.
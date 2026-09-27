---
type: Attested Computation
title: Position Size Calculator
description: Calculates position size based on account equity, risk percentage, and stop-loss distance.
tags: [position-sizing, risk]
status: stable
runtime: python
parameters:
  - { name: equity, type: float, required: true }
  - { name: risk_pct, type: float, required: true }
  - { name: entry_price, type: float, required: true }
  - { name: sl_price, type: float, required: true }
executor:
  resource: references/scripts/calc_position_size.py
  receipt: [risk_usd, risk_per_unit, volume]
attester:
  resource: references/attesters/verify_position_size.py
verified: { by: human:amirmodel90, at: 2026-09-24T17:00:00Z }
---

# Computation

```python
risk_usd = equity * risk_pct
risk_per_unit = abs(entry_price - sl_price)
volume = risk_usd / risk_per_unit if risk_per_unit > 0 else 0
```

## Example

- equity = $100
- risk_pct = 5.25%
- entry_price = $95000
- sl_price = $94000

```
risk_usd = 100 × 0.0525 = $5.25
risk_per_unit = |95000 - 94000| = $1000
volume = 5.25 / 1000 = 0.00525 BTC
```

---
type: Attested Computation
title: PnL Calculator
description: Calculates realized PnL for a closed position, including fee deduction (0.045% per fill).
tags: [pnl, fees, realized]
status: stable
runtime: python
parameters:
  - { name: entry, type: float, required: true }
  - { name: exit_price, type: float, required: true }
  - { name: sl, type: float, required: true }
  - { name: volume, type: float, required: true }
  - { name: side, type: string, required: true }
  - { name: half_price, type: float, required: false }
executor:
  resource: references/scripts/calc_pnl.py
  receipt: [gross_pnl, fee, net_pnl]
attester:
  resource: references/attesters/verify_pnl.py
verified: { by: human:amirmodel90, at: 2026-09-24T17:00:00Z }
---

# Computation

```python
FEE_RATE = 0.00045  # 0.045%

def pnl_usd(price):
    if side == "BUY":
        return (price - entry) * volume
    return (entry - price) * volume

# Gross PnL
if half_price is not None:
    # 50% at half_price, 50% at exit_price
    gross_pnl = 0.5 * pnl_usd(half_price) + 0.5 * pnl_usd(exit_price)
else:
    gross_pnl = pnl_usd(exit_price)

# Fee calculation
if half_price is not None:
    fills = [(entry, volume), (half_price, volume * 0.5), (exit_price, volume * 0.5)]
else:
    fills = [(entry, volume), (exit_price, volume)]

fee = FEE_RATE * sum(abs(price) * qty for price, qty in fills)
net_pnl = gross_pnl - fee
```

## Example (Long, no half-exit)

- entry = $95000, exit = $97500, SL = $94000, volume = 0.00525, side = BUY

```
gross_pnl = (97500 - 95000) × 0.00525 = $13.125
fee = 0.00045 × (95000 × 0.00525 + 97500 × 0.00525) = $0.4337
net_pnl = 13.125 - 0.4337 = $12.69
```

## Example (str4 MA half-exit)

- entry = $95000, half_price = $96000, exit = $97500, volume = 0.00525

```
gross_pnl = 0.5 × (96000-95000) × 0.00525 + 0.5 × (97500-95000) × 0.00525
          = 2.625 + 6.5625 = $9.1875
fee = 0.00045 × (95000 × 0.00525 + 96000 × 0.002625 + 97500 × 0.002625)
    = 0.00045 × (498.75 + 252 + 255.9375) = $0.4530
net_pnl = 9.1875 - 0.4530 = $8.73
```

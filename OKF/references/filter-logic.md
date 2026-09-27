---
type: Reference
title: Symbol Filter Logic
description: Exact logic for filtering USDT-M symbols in ToobitBot.
tags: [filter, symbols, scan]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-24T17:00:00Z }
---

# Symbol Filter Logic

## Filters Applied

```python
# From exchangeInfo API
for c in info.get("contracts", []):
    if c.get("quoteAsset") != "USDT":          # Only USDT-M
        continue
    if c.get("status") != "TRADING":           # Only active
        continue
    
    # Leverage filter
    risk_limits = c.get("riskLimits", [])
    max_lev = max(float(r.get("maxLeverage", 0)) for r in risk_limits)
    if max_lev <= 10:                            # Leverage > 10 only
        continue
    
    # Volume filter (from 24hr ticker)
    qv = ticker_map.get(c["symbol"], 0)          # quoteVolume in USDT
    if qv <= 1_000_000:                          # Volume > 1M USDT
        continue
    
    symbols.append(c["symbol"])
```

## Expected Results

| Filter | Count |
|--------|-------|
| All USDT-M contracts | ~757 |
| After leverage > 10 | ~655 |
| After volume > 1M USDT | **~214** |

## Sort & Limit

```python
symbols = sorted(symbols, key=lambda s: ticker_map.get(s, 0), reverse=True)
symbols = symbols[:280]  # Top 280 (or fewer if filter result < 280)
```

## Performance Impact

- Per symbol: **~0.33s** (fetch 250 candles + run 1 strategy)
- Full scan (214 syms × 4 strats): **~5.4 min**
- Configured scan_interval: **15 min** ✅ (no overlap)

---
type: Reference
title: OKF Usage Pipeline
description: How Hermes should use the ToobitBot OKF knowledge bundle.
tags: [pipeline, workflow, okf]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
---

# OKF Usage Pipeline

## When to Use OKF

For ANY question about ToobitBot, consult OKF FIRST before reading project files.

```
User Question → Check OKF → Answer (no file re-read needed)
```

## OKF File Map

| Question Type | File to Read |
|--------------|--------------|
| config, settings, risk values | `references/config-schema.md` |
| position sizing, PnL, fees, margin | `computations/` (position-size.md, pnl-calculation.md) |
| how scan works | `concepts/overview.md` |
| API endpoints | `references/toobit-api.md` |
| Telegram format | `concepts/notifications.md` |
| strategy logic | Read `strategies/*.py` directly (do NOT modify) |
| operations | `references/runbook.md` |
| changelog | `log.md` |

## Rules

1. **NEVER re-read source files** if OKF has the answer
2. **NEVER modify strategies** — they MUST match github.com/amirmodel90/signaltel
3. **ONLY change risk_pct** in config.yaml with explicit user approval
4. **ALWAYS sort candles** after fetching from Toobit API: `cds = sorted(cds, key=lambda c: c["open_time"])`
5. **ALWAYS consult OKF** before making project changes
6. **Margin check is automatic** — volume reduced if `margin_required > 90% equity`

## Token Savings

Using OKF saves ~5-10K tokens per question by avoiding re-reading Python files.
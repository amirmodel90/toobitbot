---
type: Reference
title: ToobitBot Update Log
description: Chronological history of changes to the ToobitBot project.
tags: [log, changelog]
status: stable
generated: { by: hermes/2.0, at: 2026-09-22T12:00:00Z }
---

# ToobitBot Update Log

## 2026-09-24
* **Fix**: Added `sorted(cds, key=lambda c: c["open_time"])` to fix Toobit API reverse-order candles
* **Update**: OKF knowledge bundle fully conformant with OKF v0.2 spec
* **Update**: Added `references/filter-logic.md` with exact filter logic and expected counts
* **Update**: Added `PIPELINE.md` for Hermes usage workflow
* **Test**: Full scan of 214 symbols × 4 strategies = 5.4 minutes
* **Config**: `symbols_limit` updated to 280 (actual filtered count: ~214)

## 2026-09-22
* **Initialization**: Created project structure, OKF knowledge bundle, Toobit API client, scanner modules, and Telegram notifications.
* **Creation**: Configured 4 strategies (str1-4) with risk percentages 5.25%, 7%, 3.75%, 5.75%.
* **Creation**: Implemented leverage filter (>10x) for 655 USDT-M symbols.

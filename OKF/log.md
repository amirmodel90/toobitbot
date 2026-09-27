---
type: Reference
title: ToobitBot Update Log
description: Chronological history of changes to the ToobitBot project.
tags: [log, changelog]
status: stable
generated: { by: hermes/2.0, at: 2026-09-27T07:00:00Z }
---

# ToobitBot Update Log

## 2026-09-27
* **Feat**: Candle-aligned scan loop — runs exactly at 5m candle close (+3s API buffer), removes fixed `scan_interval` config
* **Feat**: Margin check in position sizing — auto-reduces volume if required margin > 90% available equity
* **Perf**: Migrated public API endpoints to aiohttp (async HTTP) — 1.84× faster candle fetch, 1.67× overall scan speedup
* **Perf**: Phase 2 parallel monitoring with shared `fetch_candles_with_ma` — DRY, concurrent symbol monitoring
* **Perf**: Candle caching across strategies — fetch once per symbol, reuse for all 4 strategies (4× fewer API calls)

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
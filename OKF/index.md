---
type: Reference
title: ToobitBot Knowledge Bundle
description: OKF knowledge bundle for the ToobitBot trading bot project.
tags: [toobitbot, index, knowledge-bundle]
status: stable
generated: { by: hermes/2.0, at: 2026-09-27T07:00:00Z }
---

# ToobitBot Knowledge Bundle

## Concepts

| Concept | Description |
|---------|-------------|
| [Overview](concepts/overview.md) | Project overview, architecture, scan loop |
| [Market Data](concepts/market-data.md) | How market data is fetched (async REST + WebSocket) |
| [Order Lifecycle](concepts/order-lifecycle.md) | Signal → Order → Fill → Close flow with margin check |
| [Risk Management](concepts/risk-management.md) | Risk model, position sizing, fees, margin check |
| [Notifications](concepts/notifications.md) | Telegram chart + caption format |

## Computations

| Concept | Description |
|---------|-------------|
| [Position Size](computations/position-size.md) | Position sizing with risk-based + margin check |
| [PnL Calculation](computations/pnl-calculation.md) | Realized PnL with fee deduction |

## References

| Concept | Description |
|---------|-------------|
| [Toobit API Reference](references/toobit-api.md) | All used endpoints (sync + async) |
| [Config Schema](references/config-schema.md) | config.yaml structure (no scan_interval) |
| [Filter Logic](references/filter-logic.md) | Symbol filters and expected counts |
| [Runbook](references/runbook.md) | Operations and troubleshooting |
| [Usage Pipeline](PIPELINE.md) | How Hermes uses OKF to save tokens |

## Changelog

* [Update Log](log.md) — Chronological history of changes
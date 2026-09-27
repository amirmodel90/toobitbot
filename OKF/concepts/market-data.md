---
type: Reference
title: Market Data
description: How ToobitBot fetches and processes market data from the Toobit API.
tags: [market-data, api, klines, websocket]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
sources:
  - id: toobit-api-docs
    resource: https://api-docs.toobit.com/api/usdt-m-market-data.html
    title: Toobit Market Data API
---

# Market Data

## Symbol Discovery

`GET /api/v1/exchangeInfo` returns all trading rules and symbol info. ToobitBot filters for USDT-M perpetual contracts with leverage > 10.

**Filter logic:**
- `quoteAsset == "USDT"`
- `status == "TRADING"`
- `max(riskLimits.maxLeverage) > 10`

**Result:** ~655 symbols out of 757 total USDT-M contracts.

## OHLCV (Klines)

`GET /quote/v1/klines?symbol=X&interval=5m&limit=250`

Returns: `[[open_time, open, high, low, close, volume, close_time, quote_volume, trades, taker_buy_base, taker_buy_quote], ...]`

ToobitBot computes MA21 on the close prices:
```
ma21[i] = mean(closes[i-20:i+1])  if i >= 20 else None
```

**Critical:** Toobit API returns newest-first; ToobitBot sorts to oldest-first:
```
cds = sorted(cds, key=lambda c: c["open_time"])
```

## 24hr Ticker (Volume Ranking)

`GET /quote/v1/contract/ticker/24hr`

Used to sort symbols by `quoteVolume` for priority scanning.

## Async HTTP (aiohttp) — Since 2026-09-27

Public endpoints use async aiohttp client for 1.84× faster fetch:

| Method | Sync (requests) | Async (aiohttp) |
|--------|-----------------|-----------------|
| Candle fetch (215 syms) | 65s (ThreadPool 8) | **35s** (single event loop, 20 concurrent) |
| Connection pooling | Per-thread Session | Shared TCPConnector(limit=20) |
| Rate-limit handling | Manual sleep | Semaphore(20) |

**Endpoints using async:**
- `get_klines` — OHLCV candlesticks
- `get_exchange_info` — Trading rules & symbols
- `get_24hr_ticker` — 24hr price stats
- `get_symbol_price` — Latest price
- `get_index_price` — Index price
- `get_risk_limits` — Risk limits
- `fetch_multiple_klines` — Batch fetch with semaphore

**Endpoints remaining sync (requests):**
- All private/signed endpoints (account, positions, orders, trading)

## WebSocket Streams (Future)

For real-time data:
- Base: `wss://stream.toobit.com/quote/ws/v1`
- Topics: `trade`, `kline_5m`, `depth`, `realtimes`, `markPrice`
- Subscribe format: `{"symbol": "BTC-SWAP-USDT", "topic": "kline_5m", "event": "sub"}`

## Rate Limits

- REQUEST_WEIGHT: 3000/minute
- ORDERS: 60/2 seconds
- Klines endpoint: weight 1
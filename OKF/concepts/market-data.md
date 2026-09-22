---
type: Reference
title: Market Data
description: How ToobitBot fetches and processes market data from the Toobit API.
tags: [market-data, api, klines, websocket]
status: stable
generated: { by: hermes/2.0, at: 2026-09-22T12:00:00Z }
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

## 24hr Ticker (Volume Ranking)

`GET /quote/v1/contract/ticker/24hr`

Used to sort symbols by `quoteVolume` for priority scanning.

## WebSocket Streams (Future)

For real-time data:
- Base: `wss://stream.toobit.com/quote/ws/v1`
- Topics: `trade`, `kline_5m`, `depth`, `realtimes`, `markPrice`
- Subscribe format: `{"symbol": "BTC-SWAP-USDT", "topic": "kline_5m", "event": "sub"}`

## Rate Limits

- 3000 request weight per minute
- 60 orders per 2 seconds
- Klines endpoint: weight 1

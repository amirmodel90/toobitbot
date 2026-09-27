---
type: Reference
title: Toobit API Reference
description: All Toobit API endpoints used by ToobitBot, with parameters and response shapes.
tags: [api, toobit, reference]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
sources:
  - id: toobit-docs
    resource: https://api-docs.toobit.com
    title: Toobit API Documentation
---

# Toobit API Reference

## Base URLs

- REST: `https://api.toobit.com`
- WebSocket Market: `wss://stream.toobit.com/quote/ws/v1`
- WebSocket User: `wss://stream.toobit.com/api/v1/ws/<listenKey>`

## Authentication

Signed endpoints require:
- Header: `X-BB-APIKEY: ***`
- Query param: `timestamp` (milliseconds)
- Query param: `signature` (HMAC-SHA256 of sorted query string)

## ToobitClient Architecture (Since 2026-09-27)

```python
class ToobitClient:
    # Sync session (requests) — for private/signed endpoints
    _sync_session: requests.Session
    
    # Async session (aiohttp) — for public endpoints
    _async_session: aiohttp.ClientSession
    _async_connector: aiohttp.TCPConnector(limit=20)
```

## Endpoints Used

### Public Endpoints — Async (aiohttp)

| Method | Path | Weight | Description | Client Method |
|--------|------|--------|-------------|---------------|
| GET | `/api/v1/time` | 1 | Server time | `get_server_time()` |
| GET | `/api/v1/exchangeInfo` | 1 | Trading rules & symbols | `get_exchange_info()` |
| GET | `/quote/v1/klines` | 1 | OHLCV candlesticks | `get_klines()` |
| GET | `/quote/v1/depth` | 1-10 | Order book | `get_depth()` |
| GET | `/quote/v1/contract/ticker/24hr` | 1/40 | 24hr price stats | `get_24hr_ticker()` |
| GET | `/quote/v1/contract/ticker/price` | 1 | Latest price | `get_symbol_price()` |
| GET | `/quote/v1/index` | 1 | Index price | `get_index_price()` |
| GET | `/api/v1/futures/riskLimits` | 1 | Risk limits | `get_risk_limits()` |

**Batch operation:**
- `fetch_multiple_klines(symbols, interval, limit, max_concurrent=20)` — Concurrent fetch with semaphore

### Private Endpoints — Sync (requests, signed)

| Method | Path | Weight | Description | Client Method |
|--------|------|--------|-------------|---------------|
| GET | `/api/v1/account/info` | 1 | Account balance | `get_account_info()` |
| GET | `/api/v1/futures/position` | 1 | Open positions | `get_position()` |
| GET | `/api/v1/futures/openOrders` | 1 | All open orders | `get_open_orders()` |
| GET | `/api/v1/futures/order` | 1 | Query order | `query_order()` |
| GET | `/api/v1/futures/allOrders` | 5 | Historical orders | `get_all_orders()` |
| GET | `/api/v1/account/balanceFlow` | 5 | Fund flow history | `get_balance_flow()` |
| GET | `/api/v1/futures/commissionRate` | 5 | Trade fee rate | `get_commission_rate()` |
| GET | `/api/v1/futures/todayPnl` | 5 | Today's PnL | `get_today_pnl()` |
| GET | `/api/v1/futures/myTrades` | 5 | User trade history | `get_my_trades()` |
| GET | `/api/v1/futures/accountLeverage` | 5 | Leverage & margin mode | `get_leverage_and_margin_type()` |
| POST | `/api/v1/futures/order` | 1 | Place order | `new_order()` |
| POST | `/api/v1/futures/order/cancel` | 1 | Cancel order | `cancel_order()` |
| POST | `/api/v1/futures/order/cancelAll` | 1 | Cancel all orders | `cancel_all_orders()` |
| POST | `/api/v1/futures/order/update` | 2 | Modify order | `modify_order()` |
| POST | `/api/v1/futures/batchOrders` | 2 | Place multiple orders | — |
| POST | `/api/v1/futures/leverage` | 1 | Adjust leverage | `change_leverage()` |
| POST | `/api/v1/futures/marginType` | 1 | Change margin mode | `change_margin_type()` |
| POST | `/api/v1/listenKey` | 1 | Start user data stream | `create_listen_key()` |
| PUT | `/api/v1/listenKey` | 1 | Keepalive stream | `keepalive_listen_key()` |
| DELETE | `/api/v1/listenKey` | 1 | Close stream | `close_listen_key()` |

## Sync Wrappers (for backward compatibility)

Legacy sync code uses these wrappers which call requests directly:

- `get_exchange_info_sync()` → `_request("GET", "/api/v1/exchangeInfo")`
- `get_klines_sync()` → `_request("GET", "/quote/v1/klines", ...)`
- `get_24hr_ticker_sync()` → `_request("GET", "/quote/v1/contract/ticker/24hr", ...)`
- `get_symbol_price_sync()`, `get_index_price_sync()`, `get_risk_limits_sync()`

## Rate Limits

- REQUEST_WEIGHT: 3000/minute
- ORDERS: 60/2 seconds

## Symbol Format

- USDT-M Perpetual: `BTC-SWAP-USDT`, `ETH-SWAP-USDT`
- Inverse Perpetual: `BTC-SWAP` (margin in BTC)
- Index price uses: `BTCUSDT` (no `-SWAP-`)

## Async Performance (215 symbols)

| Metric | Sync (ThreadPool 8) | Async (aiohttp) |
|--------|---------------------|-----------------|
| Candle fetch | 65s | **35s** |
| Connections | 8 threads | Single event loop + 20 concurrent |
| Memory | ~64MB stacks | ~2MB |
| Rate-limit safety | Manual | Semaphore(20) |

---
type: Reference
title: Toobit API Reference
description: All Toobit API endpoints used by ToobitBot, with parameters and response shapes.
tags: [api, toobit, reference]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-24T17:00:00Z }
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
- Header: `X-BB-APIKEY: <api_key>`
- Query param: `timestamp` (milliseconds)
- Query param: `signature` (HMAC-SHA256 of sorted query string)

## Endpoints Used

### Public (No Signature)

| Method | Path | Weight | Description |
|--------|------|--------|-------------|
| GET | `/api/v1/time` | 1 | Server time |
| GET | `/api/v1/exchangeInfo` | 1 | Trading rules & symbols |
| GET | `/quote/v1/klines` | 1 | OHLCV candlesticks |
| GET | `/quote/v1/depth` | 1-10 | Order book |
| GET | `/quote/v1/contract/ticker/24hr` | 1/40 | 24hr price stats |
| GET | `/quote/v1/contract/ticker/price` | 1 | Latest price |
| GET | `/quote/v1/index` | 1 | Index price |
| GET | `/api/v1/futures/riskLimits` | 1 | Risk limits |

### Private (Signed)

| Method | Path | Weight | Description |
|--------|------|--------|-------------|
| GET | `/api/v1/account/info` | 1 | Account balance |
| GET | `/api/v1/futures/position` | 1 | Open positions |
| GET | `/api/v1/futures/openOrders` | 1 | All open orders |
| GET | `/api/v1/futures/order` | 1 | Query order |
| GET | `/api/v1/futures/allOrders` | 5 | Historical orders |
| GET | `/api/v1/account/balanceFlow` | 5 | Fund flow history |
| GET | `/api/v1/futures/commissionRate` | 5 | Trade fee rate |
| GET | `/api/v1/futures/todayPnl` | 5 | Today's PnL |
| GET | `/api/v1/futures/myTrades` | 5 | User trade history |
| GET | `/api/v1/futures/accountLeverage` | 5 | Leverage & margin mode |
| POST | `/api/v1/futures/order` | 1 | Place order |
| POST | `/api/v1/futures/order/cancel` | 1 | Cancel order |
| POST | `/api/v1/futures/order/cancelAll` | 1 | Cancel all orders |
| POST | `/api/v1/futures/order/update` | 2 | Modify order |
| POST | `/api/v1/futures/batchOrders` | 2 | Place multiple orders |
| POST | `/api/v1/futures/leverage` | 1 | Adjust leverage |
| POST | `/api/v1/futures/marginType` | 1 | Change margin mode |
| POST | `/api/v1/listenKey` | 1 | Start user data stream |
| PUT | `/api/v1/listenKey` | 1 | Keepalive stream |
| DELETE | `/api/v1/listenKey` | 1 | Close stream |

## Rate Limits

- REQUEST_WEIGHT: 3000/minute
- ORDERS: 60/2 seconds

## Symbol Format

- USDT-M Perpetual: `BTC-SWAP-USDT`, `ETH-SWAP-USDT`
- Inverse Perpetual: `BTC-SWAP` (margin in BTC)
- Index price uses: `BTCUSDT` (no `-SWAP-`)

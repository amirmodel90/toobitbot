---
type: Reference
title: Configuration Schema
description: Full structure and documentation of config.yaml for ToobitBot.
tags: [config, yaml, configuration]
status: stable
verified: { by: human:amirmodel90, at: 2026-09-27T07:00:00Z }
---

# Config Schema

## config.yaml

```yaml
# Toobit API (REST + WebSocket)
toobit:
  base_url: "https://api.toobit.com"
  ws_url: "wss://stream.toobit.com"
  # api_key and secret_key from .env

# Telegram
telegram:
  bot_token: "${BOT_TOKEN}"      # from .env
  channel_id: "${CHANNEL_ID}"    # from .env
  parse_mode: "HTML"

# Scanner
scanner:
  timeframes: ["5m"]             # Candlestick intervals
  min_leverage: 10               # Min leverage filter
  candles_limit: 250             # Candles per fetch
  monitor_candles_limit: 250     # For replay
  max_workers: 8                 # Thread pool size
  symbols_limit: 280             # Top N by volume (leverage > 10 + volume > 1M)
  # scan_interval removed: now candle-aligned (runs at 5m close + 3s buffer)

# Async HTTP settings
async_http:
  max_concurrent: 20             # Max concurrent aiohttp connections
  timeout_total: 15              # Total request timeout (seconds)
  timeout_connect: 5             # Connection timeout (seconds)

# Strategies
strategies:
  str1:
    risk_pct: 0.0525             # 5.25%
    enabled: true
  str2:
    risk_pct: 0.0700             # 7.00%
    enabled: true
  str3:
    risk_pct: 0.0375             # 3.75%
    enabled: true
  str4:
    risk_pct: 0.0575             # 5.75%
    enabled: true

# Position Management
positions:
  max_concurrent: 1              # Max open positions
  starting_equity: 100.0
  fee_rate: 0.00045              # 0.045% per fill
  default_timeframe: "5m"
  stale_ttl_hours: 48            # Auto-close unresolved
  margin_buffer_pct: 0.9         # 90% equity available for margin

# Logging
logging:
  level: "INFO"
  file: "data/scanner.log"
```

## .env

```env
TOOBIT_API_KEY=xxx
TOOBIT_SECRET_KEY=xxx
BOT_TOKEN=xxx
CHANNEL_ID=xxx
```

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `scanner.timeframes` | list | Candlestick intervals to scan |
| `scanner.min_leverage` | int | Minimum max leverage for symbols |
| `scanner.candles_limit` | int | Number of candles per fetch |
| `scanner.max_workers` | int | Thread pool for parallel scan |
| `scanner.symbols_limit` | int | Top N symbols by volume |
| `async_http.max_concurrent` | int | Max concurrent aiohttp connections |
| `async_http.timeout_total` | int | Total request timeout (seconds) |
| `strategies.*.risk_pct` | float | Risk fraction per trade |
| `strategies.*.enabled` | bool | Whether strategy is active |
| `positions.max_concurrent` | int | Max simultaneous open positions |
| `positions.fee_rate` | float | Fee per fill (0.00045 = 0.045%) |
| `positions.stale_ttl_hours` | int | Hours before auto-close unresolved |
| `positions.margin_buffer_pct` | float | Equity fraction available for margin (0.9 = 90%) |

## Removed Fields

| Field | Reason |
|-------|--------|
| `scanner.scan_interval` | Replaced by candle-aligned loop (runs at 5m close + 3s buffer) |
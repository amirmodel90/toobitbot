---
type: Reference
title: Configuration Schema
description: Full structure and documentation of config.yaml for ToobitBot.
tags: [config, yaml, configuration]
status: stable
generated: { by: hermes/2.0, at: 2026-09-22T12:00:00Z }
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
  scan_interval: 180             # Seconds between scans
  max_workers: 8                 # Thread pool size
  symbols_limit: 655             # Top N by volume

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

# Logging
logging:
  level: "INFO"
  file: "data/scanner.log"
```

## .env

```
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
| `scanner.scan_interval` | int | Seconds between scan ticks |
| `scanner.max_workers` | int | Thread pool for parallel scan |
| `strategies.*.risk_pct` | float | Risk fraction per trade |
| `strategies.*.enabled` | bool | Whether strategy is active |
| `positions.max_concurrent` | int | Max simultaneous open positions |
| `positions.fee_rate` | float | Fee per fill (0.00045 = 0.045%) |
| `positions.stale_ttl_hours` | int | Hours before auto-close unresolved |

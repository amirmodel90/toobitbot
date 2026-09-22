# ToobitBot - USDT-M Perpetual Futures Trading Bot
# Multi-strategy signal scanner with Telegram notifications

## Requirements
- Python 3.11+
- Toobit API key + secret
- Telegram bot token + channel ID

## Install
```bash
cd toobitbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configure
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Run
```bash
python main.py
```

## Project Structure
- `main.py` — Entry point (continuous scan loop)
- `config.yaml` — All configuration
- `strategies/str1-4.py` — Trading strategies (ported from signaltel)
- `scanner/` — Signal detection, monitoring, simulation
- `toobit_api/` — REST + WebSocket client for Toobit
- `notifications/telegram.py` — Chart + caption to Telegram
- `OKF/` — Knowledge bundle documentation
- `data/` — positions.json, equity.json, scanner.log

## Features
- 757 USDT-M perpetual futures symbols
- Leverage filter (>10x = 655 symbols)
- Multi-strategy: str1, str2, str3, str4
- Per-strategy risk: str1=5.25%, str2=7%, str3=3.75%, str4=5.75%
- Result-first replay (signal outcome sent immediately)
- Position monitoring with stale TTL (48h)
- Telegram notifications (chart + HTML caption)
- Fee model: 0.045% per fill

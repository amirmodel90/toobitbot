#!/usr/bin/env python3
"""ToobitBot Scanner v2.0 — Candle-aligned Multi-Strategy Signal Scanner.

Scan triggers exactly when 5m candles close (with small buffer for API latency).
"""
import sys
import os
import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import yaml
from toobit_api.client import ToobitClient
from scanner.phase1_detect import (
    detect_new_signals_async,
    get_symbols_with_leverage,
    load_strategy,
    fetch_candles_batch,
)
from scanner.phase2_monitor import monitor_positions
from scanner.position_manager import load_pos, apply_realized_pnl_to_equity


CANDLE_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes in milliseconds
API_BUFFER_MS = 3000  # 3 second buffer after candle close


def load_config():
    """Load config.yaml and .env."""
    config_path = Path(__file__).parent / "config.yaml"
    config = yaml.safe_load(config_path.read_text())

    # Load .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

    # Substitute env vars
    config["toobit"]["api_key"] = os.environ.get("TOOBIT_API_KEY", "")
    config["toobit"]["secret_key"] = os.environ.get("TOOBIT_SECRET_KEY", "")
    config["telegram"]["bot_token"] = os.environ.get("BOT_TOKEN", "")
    config["telegram"]["channel_id"] = os.environ.get("CHANNEL_ID", "")

    return config


async def run_scan_async(config, client):
    """Run single async scan tick aligned to candle close."""
    toobit_cfg = config["toobit"]
    telegram_cfg = config["telegram"]
    scanner_cfg = config["scanner"]

    bot_token = telegram_cfg["bot_token"]
    channel_id = telegram_cfg["channel_id"]

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] === TOOBITBOT SCANNER v2.0 SCAN START ===")

    strategy_list = [k for k, v in config["strategies"].items() if v.get("enabled")]

    scan_config = {
        "strategies": strategy_list,
        "strategies_dict": config["strategies"],
        "timeframes": scanner_cfg["timeframes"],
        "symbols_limit": scanner_cfg["symbols_limit"],
        "candles_limit": scanner_cfg["candles_limit"],
        "monitor_candles_limit": scanner_cfg["monitor_candles_limit"],
        "max_workers": scanner_cfg["max_workers"],
        "min_leverage": scanner_cfg["min_leverage"],
    }

    await detect_new_signals_async(
        config=scan_config,
        bot_token=bot_token,
        channel_id=channel_id,
        client=client,
        scanner_cfg=scanner_cfg,
    )

    # Monitor existing positions (sync, runs in thread pool)
    monitor_positions(
        bot_token=bot_token,
        channel_id=channel_id,
        client=client,
    )

    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] === TICK COMPLETE ===\n")


def get_next_candle_close_ms():
    """Calculate milliseconds until next 5m candle closes (+ buffer)."""
    now_ms = int(time.time() * 1000)
    # Next candle boundary (ceil to next 5-minute mark)
    next_boundary = ((now_ms // CANDLE_INTERVAL_MS) + 1) * CANDLE_INTERVAL_MS
    # Add buffer for API latency
    return next_boundary + API_BUFFER_MS


async def main_async():
    """Async main loop - runs scan at each 5m candle close."""
    config = load_config()

    toobit_cfg = config["toobit"]
    client = ToobitClient(
        api_key=toobit_cfg["api_key"],
        secret_key=toobit_cfg["secret_key"],
        base_url=toobit_cfg["base_url"],
    )

    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] === TOOBITBOT STARTED ===")
    print(f"[CONFIG] Candle interval: 5m, Buffer: {API_BUFFER_MS}ms")
    print(f"[CONFIG] Strategies: {[k for k, v in config['strategies'].items() if v.get('enabled')]}")
    print(f"[CONFIG] Symbols limit: {config['scanner']['symbols_limit']}")
    print(f"[CONFIG] Max workers: {config['scanner']['max_workers']}")

    try:
        while True:
            # Calculate wait time until next candle close
            next_close_ms = get_next_candle_close_ms()
            now_ms = int(time.time() * 1000)
            wait_ms = next_close_ms - now_ms

            if wait_ms > 0:
                wait_sec = wait_ms / 1000
                next_candle_time = datetime.fromtimestamp(next_close_ms / 1000, tz=timezone.utc)
                print(f"[WAIT] Next scan at {next_candle_time.strftime('%H:%M:%S UTC')} ({wait_sec:.1f}s)")
                await asyncio.sleep(wait_sec)
            else:
                # Already past the boundary, run immediately
                pass

            try:
                await run_scan_async(config, client)
            except Exception as e:
                print(f"[SCAN ERROR] {e}")
                import traceback
                traceback.print_exc()

    except KeyboardInterrupt:
        print(f"\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] [SHUTDOWN] Bot stopped by user.")
    finally:
        await client.close()
        print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] === TOOBITBOT STOPPED ===")


def main():
    """Entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
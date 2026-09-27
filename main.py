#!/usr/bin/env python3
"""ToobitBot Scanner v1.0 — Multi-Strategy Signal Scanner."""
import sys
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import yaml
from toobit_api.client import ToobitClient
from scanner.phase1_detect import detect_new_signals
from scanner.phase2_monitor import monitor_positions
from scanner.position_manager import load_pos, apply_realized_pnl_to_equity


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


def run_scan(config):
    """Run single scan tick."""
    toobit_cfg = config["toobit"]
    telegram_cfg = config["telegram"]
    scanner_cfg = config["scanner"]
    
    client = ToobitClient(
        api_key=toobit_cfg["api_key"],
        secret_key=toobit_cfg["secret_key"],
        base_url=toobit_cfg["base_url"],
    )
    
    bot_token = telegram_cfg["bot_token"]
    channel_id = telegram_cfg["channel_id"]
    
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] === TOOBITBOT SCANNER v1.0 START ===")
    
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
    
    detect_new_signals(
        config=scan_config,
        bot_token=bot_token,
        channel_id=channel_id,
        client=client,
        scanner_cfg=scanner_cfg,
    )
    
    monitor_positions(
        bot_token=bot_token,
        channel_id=channel_id,
        client=client,
    )
    
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] === TICK COMPLETE ===\n")


def main():
    """Main loop."""
    config = load_config()
    interval = config["scanner"]["scan_interval"]
    
    while True:
        try:
            run_scan(config)
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Bot stopped by user.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback; traceback.print_exc()
        
        # Sleep until next tick
        print(f"[SLEEP] Next scan in {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    main()

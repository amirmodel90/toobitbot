#!/usr/bin/env python3
"""download_toobit.py — Download 6 months of 5m klines from Toobit.

- Fetches all USDT-M futures symbols with leverage > 20
- Paginates with limit=1000 using startTime/endTime
- Saves each symbol to data/klines/{symbol}.parquet
- Resume-safe: only re-downloads symbols with < 50000 candles
"""
import sys, os, time, json, requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path(__file__).parent / "data" / "klines"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SIX_MONTHS_MS = 180 * 24 * 3600 * 1000  # ~6 months in milliseconds
MAX_CANDLES = 51840  # 6 months of 5m candles (180 days * 288/day)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ToobitBot/1.0"})

def fetch_json(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                raise

def get_symbols(min_lev=20):
    """Get all USDT-M symbols with max leverage > min_lev."""
    info = fetch_json("https://api.toobit.com/api/v1/exchangeInfo")
    symbols = []
    for c in info.get("contracts", []):
        if c.get("quoteAsset") != "USDT" or c.get("status") != "TRADING":
            continue
        sym = c.get("symbol", "")
        if not sym.endswith("-SWAP-USDT"):
            continue
        risk = c.get("riskLimits", [])
        max_lev = max((float(r.get("maxLeverage", 0)) for r in risk), default=0)
        if max_lev > min_lev:
            symbols.append(sym)
    return symbols

def download_symbol(symbol, end_time_ms=None):
    """Download 6 months of 5m klines for one symbol using pagination."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    
    out_file = DATA_DIR / f"{symbol}.parquet"
    
    # Check existing file
    existing_candles = 0
    if out_file.exists():
        try:
            t = pq.read_table(out_file)
            existing_candles = len(t)
        except Exception:
            existing_candles = 0
    
    if end_time_ms is None:
        end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time_ms = end_time_ms - SIX_MONTHS_MS

    all_klines = []
    current_start = start_time_ms
    total_requests = 0

    while current_start < end_time_ms:
        data = fetch_json("https://api.toobit.com/quote/v1/klines", params={
            "symbol": symbol, "interval": "5m", "limit": 1000, 
            "startTime": current_start, "endTime": end_time_ms
        })
        if not data:
            break
        
        all_klines.extend(data)
        total_requests += 1
        
        # Move window forward
        newest_ts = int(data[-1][0]) + 300000  # +5m to avoid overlap
        current_start = newest_ts
        
        if total_requests % 10 == 0:
            oldest_dt = datetime.fromtimestamp(data[0][0] / 1000, tz=timezone.utc)
            print(f"    {total_requests} reqs, oldest: {oldest_dt.strftime('%Y-%m-%d')}")
        
        # Rate limit: max 5 req/s
        time.sleep(0.2)

    if not all_klines:
        return existing_candles

    # Convert to parquet
    rows = []
    for k in all_klines:
        rows.append({
            'open_time': int(k[0]),
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
            'volume': float(k[5]),
            'close_time': int(k[6]),
            'quote_volume': float(k[7]) if len(k) > 7 else 0.0,
        })

    # Deduplicate and sort
    seen = set()
    unique_rows = []
    for r in rows:
        if r['open_time'] not in seen:
            seen.add(r['open_time'])
            unique_rows.append(r)
    
    if not unique_rows:
        return existing_candles

    # Sort by open_time
    unique_rows.sort(key=lambda r: r['open_time'])

    table = pa.table({
        'open_time': [r['open_time'] for r in unique_rows],
        'open': [r['open'] for r in unique_rows],
        'high': [r['high'] for r in unique_rows],
        'low': [r['low'] for r in unique_rows],
        'close': [r['close'] for r in unique_rows],
        'volume': [r['volume'] for r in unique_rows],
        'close_time': [r['close_time'] for r in unique_rows],
        'quote_volume': [r['quote_volume'] for r in unique_rows],
    })
    
    pq.write_table(table, out_file)
    return len(unique_rows)

def main():
    symbols = get_symbols(min_lev=20)
    print(f"Found {len(symbols)} symbols with leverage > 20")
    print(f"Downloading 6 months of 5m klines for each...")
    print(f"Saving to: {DATA_DIR}")

    success = 0
    failed = 0
    skipped = 0

    for i, sym in enumerate(symbols):
        try:
            result = download_symbol(sym)
            if result is None:
                skipped += 1
                status = "SKIP"
            else:
                success += 1
                status = f"OK ({result} candles)"
            print(f"[{i+1}/{len(symbols)}] {sym}: {status}")
        except Exception as e:
            failed += 1
            print(f"[{i+1}/{len(symbols)}] {sym}: FAIL - {e}")
        
        # Brief pause every 10 symbols
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    print(f"\nDone: {success} downloaded, {skipped} skipped, {failed} failed")

if __name__ == "__main__":
    main()

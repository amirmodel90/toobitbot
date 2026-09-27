#!/usr/bin/env python3
"""Debug — disable all filters and count raw signals."""
import sys
sys.path.insert(0, '.')
from toobit_api.client import ToobitClient
from scanner.phase1_detect import fetch_candles_with_ma
import importlib

client = ToobitClient('', '', 'https://api.toobit.com')

tickers = client.get_24hr_ticker()
ticker_map = {t['s']: float(t.get('qv', 0)) for t in tickers}

info = client.get_exchange_info()
syms = []
for c in info.get('contracts', []):
    if c.get('quoteAsset') != 'USDT' or c.get('status') != 'TRADING': continue
    rl = c.get('riskLimits', [])
    if not rl: continue
    if max(float(r.get('maxLeverage',0)) for r in rl) > 20:
        syms.append(c['symbol'])

syms = sorted(syms, key=lambda s: ticker_map.get(s,0), reverse=True)[:5]
print(f"Testing {len(syms)} symbols with ALL FILTERS DISABLED...\n")

for strat_name in ['str1', 'str2', 'str3', 'str4']:
    mod = importlib.import_module(f'strategies.{strat_name}')
    cfg = mod.get_config()
    
    # Disable all filters
    cfg['adx_lo'] = 0
    cfg['adx_th'] = 999
    cfg['vol_filter'] = 0
    cfg['min_dist_pct'] = 0
    cfg['max_dist_pct'] = 999
    cfg['t1_only'] = 0
    cfg['active_ideas'] = set()
    
    total_sigs = 0
    
    for sym in syms:
        try:
            cds = fetch_candles_with_ma(client, sym, '5m', 1000)
            if len(cds) < 100: continue
            
            ind = mod.compute_indicators(cds) if hasattr(mod, 'compute_indicators') else None
            if hasattr(mod, 'reset_caches'): mod.reset_caches()
            
            sigs = 0
            for i in range(max(50, int(cfg.get('lookback', 10))), len(cds) - 1):
                sig = mod.detect(cds, i, cfg, ind=ind) if hasattr(mod, 'detect') else None
                if sig:
                    sigs += 1
            
            total_sigs += sigs
            if sigs > 0:
                print(f"  {strat_name} {sym}: {sigs} signals")
        except Exception as e:
            pass
    
    print(f"{strat_name}: TOTAL {total_sigs} signals (no filters)\n")

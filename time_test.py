#!/usr/bin/env python3
import sys, time
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

syms = sorted(syms, key=lambda s: ticker_map.get(s,0), reverse=True)[:30]

# Time each strategy scan
for strat in ['str1','str2','str3','str4']:
    mod = importlib.import_module(f'strategies.{strat}')
    cfg = mod.get_config()
    
    t0 = time.time()
    for sym in syms:
        cds = fetch_candles_with_ma(client, sym, '5m', 500)
        if len(cds) < 75: continue
        ind = mod.compute_indicators(cds) if hasattr(mod,'compute_indicators') else None
        if hasattr(mod,'reset_caches'): mod.reset_caches()
        for i in range(max(50,int(cfg.get('lookback',10))), len(cds)-1):
            mod.detect(cds, i, cfg, ind=ind)
    elapsed = time.time() - t0
    print(f'{strat}: {elapsed:.1f}s ({elapsed/30:.2f}s per symbol)')

# Total
t0 = time.time()
for strat in ['str1','str2','str3','str4']:
    mod = importlib.import_module(f'strategies.{strat}')
    cfg = mod.get_config()
    for sym in syms:
        cds = fetch_candles_with_ma(client, sym, '5m', 500)
        if len(cds) < 75: continue
        ind = mod.compute_indicators(cds) if hasattr(mod,'compute_indicators') else None
        if hasattr(mod,'reset_caches'): mod.reset_caches()
        for i in range(max(50,int(cfg.get('lookback',10))), len(cds)-1):
            mod.detect(cds, i, cfg, ind=ind)

total = time.time() - t0
print(f'\nTOTAL: {total:.1f}s = {total/60:.1f} min')

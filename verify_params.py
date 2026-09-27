#!/usr/bin/env python3
"""Verify all strategies have original parameters."""
import sys, json
sys.path.insert(0, '.')
import importlib

print("=== Strategy Parameters Check\n")
for name in ['str1', 'str2', 'str3', 'str4']:
    mod = importlib.import_module(f'strategies.{name}')
    cfg = mod.get_config()
    print(f"{name}:")
    for k in ['risk_pct', 'tp_rr', 'adx_lo', 'adx_th', 'vol_filter', 'min_dist_pct', 'max_dist_pct', 't1_only', 'volume_spike_mult', 'max_vol5_ratio', 'trig_confirm_window', 'ma_stretch_atr', 'min_leg_length']:
        if k in cfg:
            print(f"  {k} = {cfg[k]}")
    print()

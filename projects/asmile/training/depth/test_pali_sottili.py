#!/usr/bin/env python3
"""test_pali_sottili.py — oggetti sottili (veto 2/3): una maschera di palo stretta o con poca disparita' valida (SGBM sul fondo)
NON deve dare una Z; una maschera larga/coerente si'. Sintetico (nessun video): disparita' palo 40 px (Z~6.6 m) su sfondo 12 px (Z~22 m).
Uso: ~/.asmile_depth_venv/bin/python training/depth/test_pali_sottili.py"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from depth_seg_001 import Rect, mask_depth, H, W

rc = Rect()


def caso(larg, frac_valid, classe="pole"):
    disp = np.full((H, W), 12.0, np.float32)              # sfondo
    disp[300:600, 600:600 + larg] = 40.0                  # palo
    mask = np.zeros((H, W), np.uint8); mask[300:600, 599:600 + larg + 1] = 1
    inv = np.random.default_rng(0).random((H, W)) > frac_valid
    disp[inv & (mask > 0)] = 0                            # pixel senza disparita'
    bw, bh = larg + 2, 300
    return mask_depth(rc, disp, mask, thin_frac=float(mask.sum()) / (bw * bh), classe=classe, width_px=float(mask.sum()) / bh)


ok = True
r = caso(6, 0.9); print("palo 6 px, 90% validi ->", r and round(r[0], 1)); ok &= r is None
r = caso(16, 0.3); print("palo 16 px, 30% validi ->", r and round(r[0], 1)); ok &= r is None
r = caso(16, 0.9); print("palo 16 px, 90% validi ->", r and round(r[0], 1)); ok &= r is not None and abs(r[0] - rc.Z(40.0)) / rc.Z(40.0) < 0.1
print("PASSA" if ok else "FALLISCE"); sys.exit(0 if ok else 1)

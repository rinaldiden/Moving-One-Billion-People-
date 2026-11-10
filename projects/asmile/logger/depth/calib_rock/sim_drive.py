#!/usr/bin/env python3
"""sim_drive.py - segmenti di guida sintetici (scena a piani texturizzati) per provare online.py."""
import numpy as np
import render


def simulate_segments(inst, rng, starts, ds_list, textures=None, enc_bias=0.004, enc_noise=0.003, still=False,
                      center_only=False):
    """Per ogni (s0, ds): 4 immagini grezze (L0,R0 a s0; L1,R1 a s0+ds) + ds misurato dall'encoder (con errore).
    still=True: bici ferma (ds vero 0). center_only: contenuto solo nella zona centrale (resto nero)."""
    textures = textures or render.scene_textures(rng)
    segs = []
    for s0, ds in zip(starts, ds_list):
        d_true = 0.0 if still else ds
        out = {}
        for name, s in (("0", s0), ("1", s0 + d_true)):
            pl = render.scene_planes(rng, inst, s, textures)
            e = rng.uniform(0.9, 1.1)
            a = render.render(inst, 1, pl, rng, exposure=e)
            b = render.render(inst, 2, pl, rng, exposure=e)
            if center_only:
                m = np.zeros_like(a)
                m[266:533, 426:853] = 1
                a, b = a * m, b * m
            out["L" + name], out["R" + name] = a, b
        out["ds"] = d_true * (1 + enc_bias + rng.normal(0, enc_noise)) if not still else abs(rng.normal(0, 0.01))
        segs.append(out)
    return segs

#!/usr/bin/env python3
"""
soglie.py — legge la tabella UNICA delle soglie di attuazione (config/soglie_attuazione_<unita>.json).

Depth video, ombra, planner e allievo sul Pi prendono da qui le distanze che fanno frenare/sterzare:
mai numeri scritti nel codice (Daniele 2026-11-12). Fra due velocità della tabella interpola lineare;
fuori tabella usa le formule con i parametri.

Uso:  from soglie import Soglie
      s = Soglie("asmile-001")
      s.a(2.8)   -> {"frena_entro_m": 4.5, "rallenta_entro_m": 8.4, "bordo_margine_m": 0.44}
      s.p["altezza_max_ostacolo_m"]
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(HERE, "..", "..", "config")
CAMPI = ("frena_entro_m", "rallenta_entro_m", "bordo_margine_m")


class Soglie:
    def __init__(self, unita="asmile-001", path=None):
        name = unita.replace("asmile-", "")
        self.path = path or os.path.join(CONFIG_DIR, f"soglie_attuazione_{name}.json")
        doc = json.load(open(self.path))
        self.versione = doc["versione"]
        self.stato = doc["stato"]
        self.p = {k: v for k, v in doc["parametri"].items() if not k.startswith("_")}
        self.righe = sorted(doc["tabella_per_velocita"], key=lambda r: r["v_ms"])

    def formula(self, v):
        p = v * self.p["t_latenza_s"] + v * v / (2 * self.p["decel_frenata_ms2"]) + self.p["cuscinetto_m"]
        return {"frena_entro_m": p,
                "rallenta_entro_m": max(1.5 * p, v * self.p["ttc_avviso_s"]),
                "bordo_margine_m": self.p["bordo_base_m"] + self.p["bordo_per_ms"] * v}

    def a(self, v_ms):
        """Soglie alla velocità v_ms (m/s): tabella interpolata, formule fuori tabella."""
        v = max(0.0, v_ms)
        r = self.righe
        if v < r[0]["v_ms"] or v > r[-1]["v_ms"]:
            return self.formula(v)
        for lo, hi in zip(r, r[1:]):
            if lo["v_ms"] <= v <= hi["v_ms"]:
                f = (v - lo["v_ms"]) / (hi["v_ms"] - lo["v_ms"]) if hi["v_ms"] > lo["v_ms"] else 0.0
                return {k: lo[k] + f * (hi[k] - lo[k]) for k in CAMPI}
        return {k: r[-1][k] for k in CAMPI}


if __name__ == "__main__":
    s = Soglie()
    print(f"{s.path} v{s.versione} — {s.stato}")
    for kmh in (5, 10, 15):
        print(kmh, "km/h", {k: round(x, 2) for k, x in s.a(kmh / 3.6).items()})

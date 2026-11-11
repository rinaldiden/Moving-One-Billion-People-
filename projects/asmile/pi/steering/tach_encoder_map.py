#!/usr/bin/env python3
"""
tach_encoder_map.py — #001: corrispondenza tachimetro VESC ↔ encoder sterzo (AMT22 sul piantone), come FALLBACK se
l'encoder sterzo sparisce durante la guida (Daniele 2026-11-11: "costruiamo la corrispondenza con i tac e mettiamola
come fallback", entro gli stessi limiti, anche se meno fluido).

Modello: enc ≈ enc_ancora + K·(tach − tach_ancora) ∓ gioco/2 (segno = ultimo verso di marcia del motore).
  - K (count encoder per tach) si impara in linea sui tratti in moto; nominale 16384/(35 giri el.·6) = −78.0
    (segno: tach che SALE = encoder che SCENDE, misurato sui log 2026-11-10: −76…−78).
  - gioco (backlash della riduzione 1:5) si impara alle inversioni di verso.
  - ancora = ultima coppia (tach, enc) con encoder valido: il tach è RELATIVO e riparte da 0 a ogni accensione del
    VESC, quindi il fallback vale solo se l'encoder è sparito DOPO essere stato visto in questa accensione.
    Encoder assente dall'avvio → posizione assoluta ignota → niente fallback (si ferma).
  - incertezza = |Δtach|·σK + 1 tach (quantizzazione, ~1.7°) + gioco/2: i limiti in fallback si stringono di questa.

Persistenza: /data/steering_tach_map_asmile-001.json (solo K, σK, gioco, n campioni: l'ancora non si salva mai).
Uso offline (fit sui log): python3 tach_encoder_map.py fit <csv con colonne pos,tach> ...
"""
import json, math, os, sys, time

MAP_FILE = "/data/steering_tach_map_asmile-001.json"
CPR = 16384; DEG = 360.0 / CPR
K_NOM = -16384 / (35 * 6)          # −78.0 count/tach
MIN_DTACH_FIT = 3                  # tratti più corti di 3 tach (~5°) non insegnano K: troppo quantizzati
ANCORA_MAX_S = 600                 # oltre: l'ancora è vecchia (il VESC potrebbe essere stato riacceso)


class TachMap:
    def __init__(self, path=MAP_FILE):
        self.path = path
        self.k, self.k_std, self.gioco, self.n = K_NOM, 4.0, 40.0, 0
        try:
            d = json.load(open(path))
            self.k, self.k_std, self.gioco, self.n = d["k"], d["k_std"], d["gioco"], d["n"]
        except (OSError, ValueError, KeyError):
            pass
        self.ancora = None          # (tach, enc, t)
        self._seg = None            # inizio tratto monotono (tach, enc, verso)
        self._verso = 0

    def update(self, tach, enc, t=None):
        """Chiamare a ogni lettura con encoder VALIDO e tach dalla telemetria VESC."""
        t = time.monotonic() if t is None else t
        if self.ancora is not None:
            dt_ = tach - self.ancora[0]
            if dt_:
                verso = 1 if dt_ > 0 else -1
                if self._verso and verso != self._verso and self._seg:
                    self._chiudi_tratto(self.ancora[0], self.ancora[1])
                    self._seg = (self.ancora[0], self.ancora[1], verso)
                elif self._seg is None:
                    self._seg = (self.ancora[0], self.ancora[1], verso)
                self._verso = verso
        self.ancora = (tach, enc, t)

    def _chiudi_tratto(self, tach, enc):
        t0, e0, _ = self._seg
        dt_ = tach - t0
        if abs(dt_) < MIN_DTACH_FIT:
            return
        k_mis = (enc - e0) / dt_
        if not (0.5 * abs(K_NOM) < abs(k_mis) < 1.5 * abs(K_NOM)) or k_mis * K_NOM < 0:
            return                                   # slittamento o lettura sbagliata: non insegna
        a = 1.0 / (self.n + 1) if self.n < 50 else 0.02
        err = k_mis - self.k
        self.k += a * err
        self.k_std = math.sqrt((1 - a) * self.k_std ** 2 + a * err ** 2)
        self.n += 1

    def stima(self, tach, t=None):
        """(enc stimato, incertezza in count) o None se l'ancora manca o è vecchia."""
        t = time.monotonic() if t is None else t
        if self.ancora is None or t - self.ancora[2] > ANCORA_MAX_S:
            return None
        dt_ = tach - self.ancora[0]
        enc = self.ancora[1] + self.k * dt_
        if dt_ and self._verso and (1 if dt_ > 0 else -1) != self._verso:
            enc -= math.copysign(self.gioco / 2, self.k * dt_)
        inc = abs(dt_) * self.k_std + abs(self.k) + self.gioco / 2
        return enc, inc

    def salva(self):
        try:
            tmp = self.path + ".tmp"
            json.dump({"k": self.k, "k_std": self.k_std, "gioco": self.gioco, "n": self.n,
                       "aggiornato": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(tmp, "w"), indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass


def fit_csv(paths):
    import csv
    m = TachMap(path=os.devnull)
    for p in paths:
        m.ancora, m._seg, m._verso = None, None, 0
        for r in csv.DictReader(open(p)):
            try:
                m.update(int(float(r["tach"])), int(r["pos"]), float(r["t"]))
            except (KeyError, ValueError):
                break
    print(f"K = {m.k:.2f} count/tach (nominale {K_NOM:.1f}), sigma {m.k_std:.2f}, tratti {m.n}")
    return m


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "fit":
        fit_csv(sys.argv[2:])
    else:
        print(__doc__)

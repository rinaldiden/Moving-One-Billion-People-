"""Fonti di velocita' e decelerazione: encoder ruota (primaria), fusione GPS+IMU, BLE CooSpo, arbitro.
Nessun import hardware. Tutto lavora su un 'Campione' che riempie hw.py (vero) o sim.py (CSV)."""
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

G = 9.81


@dataclass
class Campione:
    t: float                         # orologio monotonic dell'host, secondi
    enc: Optional[tuple] = None      # (t_enc_s, count_cumulati) SOLO se e' un dato nuovo
    imu: Optional[tuple] = None      # (ax, ay, az in g; gx, gy, gz in dps) se arrivato
    gps: Optional[tuple] = None      # (speed_ms, fix_bool) SOLO se nuovo
    ble: Optional[tuple] = None      # speed_ms SOLO se nuovo
    ina_ma: Optional[float] = None   # corrente servo
    emergenza: bool = False          # flag /tmp/emergency_brake


def _solve3(M, Y):
    def det(A):
        return (A[0][0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1])
                - A[0][1] * (A[1][0] * A[2][2] - A[1][2] * A[2][0])
                + A[0][2] * (A[1][0] * A[2][1] - A[1][1] * A[2][0]))
    D = det(M)
    if abs(D) < 1e-18:
        return None
    out = []
    for c in range(3):
        A = [r[:] for r in M]
        for r in range(3):
            A[r][c] = Y[r]
        out.append(det(A) / D)
    return out


class Encoder:
    """v e a dalla distanza percorsa: parabola ai minimi quadrati sugli ultimi 0.3 s (come WheelEncoder._fit)."""

    def __init__(self, cfg):
        self.k = cfg["m_per_count"]
        self.win = cfg["finestra_parabola_s"]
        self.max_step = cfg["max_salto_counts"]
        self.fresco_s = cfg["fresco_s"]
        self._last = None
        self._cum = 0
        self._hist = deque()
        self.v = 0.0
        self.a = 0.0
        self.t_nuovo = None          # istante host dell'ultimo dato nuovo
        self.glitch = 0

    def aggiorna(self, t, enc):
        if enc is None:
            return
        te, c = enc
        if self._last is None:
            self._last = c
            self._hist.clear()
            self._hist.append((te, 0.0))
            self._cum = 0
            self.t_nuovo = t
            return
        if self._hist and te <= self._hist[-1][0]:
            return
        d = c - self._last
        self._last = c
        if abs(d) > self.max_step:        # salto irreale: scarta e riparte la finestra
            self.glitch += 1
            self._hist.clear()
            self._hist.append((te, self._cum * self.k))
            self.t_nuovo = t
            return
        self._cum += abs(d)
        self.t_nuovo = t
        self._fit(te)

    def _fit(self, te):
        self._hist.append((te, self._cum * self.k))
        while len(self._hist) > 3 and te - self._hist[0][0] > self.win:
            self._hist.popleft()
        if len(self._hist) < 6 or te - self._hist[0][0] < 0.1:
            return
        s_now = self._hist[-1][1]
        tau = [p[0] - te for p in self._hist]
        sm = [p[1] - s_now for p in self._hist]
        S = [sum(x ** n for x in tau) for n in range(5)]
        Y = [sum(y * x ** n for x, y in zip(tau, sm)) for n in range(3)]
        sol = _solve3([[S[0], S[1], S[2]], [S[1], S[2], S[3]], [S[2], S[3], S[4]]], Y)
        if sol is not None:
            self.v = max(0.0, sol[1])
            self.a = 2.0 * sol[2]

    def fresco(self, t):
        return self.t_nuovo is not None and (t - self.t_nuovo) <= self.fresco_s and len(self._hist) >= 6


class ImuLong:
    """IMU: dec longitudinale (+ = frenata), variazione di beccheggio in 0.3 s (+ = muso giu'), bias da fermo."""

    def __init__(self, cfg, ant, scala=1.0):
        self.scala = scala
        self.ay_riposo = cfg["ay_riposo_g"]
        self.gx_bias = cfg["gx_bias_dps"]
        self.tau_ema = cfg["ema_dec_s"]
        self.morta_s = cfg["morta_dopo_s"]
        self.fin = ant["finestra_s"]
        self._t_ultimo = None
        self._t_prec = None
        self.dec = 0.0              # m/s2, + = frenata (scala IMU)
        self.a_avanti = 0.0         # m/s2 grezza (senza bias), + = accelerazione in avanti
        self.a_liscia = 0.0         # EMA 0.3 s di a_avanti
        self.d03 = 0.0              # gradi, + = muso giu'
        self.gx = 0.0
        self._h = deque()           # (t, gx-bias)
        self.riposo_calibrato = False
        self._vz = deque()          # (t, az) ultimo secondo, per la vibrazione (bici in moto o ferma)
        self._sz = 0.0
        self._sz2 = 0.0
        self.vibr = 0.0             # std di az su 1 s, in g
        self._t_moto = None
        self.vibr_on, self.vibr_off = 0.025, 0.015

    def aggiorna(self, t, imu, fermo):
        if imu is None:
            return
        ax, ay, az, gx, gy, gz = imu
        dt = 0.02 if self._t_prec is None else max(1e-3, min(0.2, t - self._t_prec))
        self._t_prec = t
        self._t_ultimo = t
        if fermo:                                    # ricalcola riposo e bias da fermo
            al = min(1.0, dt / 1.0)
            self.ay_riposo += al * (ay - self.ay_riposo)
            self.gx_bias += al * (gx - self.gx_bias)
            self.riposo_calibrato = True
        al = min(1.0, dt / self.tau_ema)
        self.dec += al * ((ay - self.ay_riposo) * G - self.dec)
        a_raw = -(ay - self.ay_riposo) * G / self.scala     # in scala ENCODER (la dec per l'anti-impuntata resta in scala IMU)
        self.a_avanti = a_raw
        self.a_liscia += min(1.0, dt / 0.3) * (a_raw - self.a_liscia)
        self._vz.append((t, az)); self._sz += az; self._sz2 += az * az
        while self._vz and t - self._vz[0][0] > 1.0:
            _, o = self._vz.popleft(); self._sz -= o; self._sz2 -= o * o
        n = len(self._vz)
        if n >= 20:
            self.vibr = math.sqrt(max(0.0, self._sz2 / n - (self._sz / n) ** 2))
            if self.vibr > (self.vibr_off if self._t_moto is not None else self.vibr_on):
                self._t_moto = t
        self.gx = gx - self.gx_bias
        self._h.append((t, self.gx, dt))
        while self._h and t - self._h[0][0] > self.fin + 1e-9:
            self._h.popleft()
        self.d03 = sum(g * d for _, g, d in self._h)

    def in_moto(self, t, memoria_s=3.0):
        """True se la vibrazione dell'IMU (std az 1 s) e' stata sopra soglia negli ultimi memoria_s secondi: la bici si muove.
        Misurato su #001: in moto p5 0.048 g, ferma p95 0.006 g."""
        return self._t_moto is not None and (t - self._t_moto) <= memoria_s

    def viva(self, t):
        return self._t_ultimo is not None and (t - self._t_ultimo) <= self.morta_s


class Fusione:
    """Filtro 1D [v, bias_acc]: l'accelerazione IMU fa da modello, GPS (10 Hz) o BLE correggono la velocita'.
    L'encoder NON entra in v (cosi' il controllo di plausibilita' resta indipendente): da' solo un suggerimento lento di bias."""

    def __init__(self, cfg):
        self.c = cfg
        self.v = 0.0
        self.b = 0.0
        self.P = [[4.0, 0.0], [0.0, 0.25]]
        self.init = False
        self.t_gps = None
        self.t_ble = None
        self.t_ult_buono = None      # ultimo istante con una misura (GPS o BLE)
        self._t_prec = None
        self.t_bias = -1e9

    def predici(self, t, a_avanti):
        if self._t_prec is None:
            self._t_prec = t
            return
        dt = max(0.0, min(0.2, t - self._t_prec))
        self._t_prec = t
        if self.t_ult_buono is None or t - self.t_ult_buono <= self.c["imu_solo_max_s"] * 2:
            self.v += (a_avanti - self.b) * dt        # senza GPS/BLE da troppo tempo l'IMU non integra piu' (deriva)
        self.v = min(self.v, 15.0)
        if self.v < 0.0:
            self.v = 0.0
        P = self.P
        P00 = P[0][0] + 2 * dt * P[0][1] + dt * dt * P[1][1] + self.c["q_v"] ** 2 * dt
        P01 = P[0][1] + dt * P[1][1]
        P11 = P[1][1] + self.c["q_bias"] ** 2 * dt
        self.P = [[P00, P01], [P01, P11]]

    def _upd(self, z, R, H):
        P = self.P
        y = z - (self.v if H == 0 else self.b)
        S = P[H][H] + R * R
        K0, K1 = P[0][H] / S, P[1][H] / S
        self.v = max(0.0, self.v + K0 * y)
        self.b = max(-1.0, min(1.0, self.b + K1 * y))
        P00 = P[0][0] - K0 * P[H][0]
        P01 = P[0][1] - K0 * P[H][1]
        P11 = P[1][1] - K1 * P[H][1]
        self.P = [[P00, P01], [P01, P11]]

    def misura(self, t, v, quale):
        if not self.init:
            self.v, self.init = v, True
            self.P[0][0] = 0.3 ** 2
        else:
            self._upd(v, self.c["r_gps_ms"] if quale == "gps" else self.c["r_ble_ms"], 0)
        if quale == "gps":
            self.t_gps = t
        else:
            self.t_ble = t
        self.t_ult_buono = t

    def suggerisci_bias(self, t, a_avanti_raw, a_enc):
        """Suggerimento LENTO di bias: tocca solo b (non v), solo con accelerazione piccola (niente scala IMU in gioco)."""
        if t - self.t_bias < 0.2 or abs(a_enc) > 0.4:
            return
        self.t_bias = t
        P = self.P
        R = self.c["r_enc_bias"]
        K = P[1][1] / (P[1][1] + R * R)
        self.b += K * ((a_avanti_raw - a_enc) - self.b)
        self.b = max(-1.0, min(1.0, self.b))
        self.P = [[P[0][0], P[0][1] * (1 - K)], [P[0][1] * (1 - K), P[1][1] * (1 - K)]]

    @property
    def sigma_v(self):
        return math.sqrt(max(0.0, self.P[0][0]))


class Arbitro:
    """Sceglie la fonte: ENC > GPS_IMU > BLE_IMU > IMU_SOLO > NESSUNA. Ogni cambio e' loggato col motivo.
    Al passaggio ENC -> fallback la differenza si smorza in 1 s: niente salti."""

    def __init__(self, cfg, imu_cfg, enc, imu, fus):
        self.cfg = cfg
        self.enc, self.imu, self.fus = enc, imu, fus
        self.pl = cfg["encoder"]["plausibilita"]
        self.fcfg = cfg["fusione_gps_imu"]
        self.fonte = "NESSUNA"
        self.eventi = []             # (t, da, a, motivo)
        self._t_bad_v = None
        self._t_bad_a = None
        self._t_ok = None
        self.enc_implausibile = False
        self._riamm = self.pl["riammissione_s"]
        self._t_riammesso = -1e9
        self._off = 0.0
        self._t_off = None
        self._v_enc_ult = 0.0
        self._ultimo_enc_buono = None
        self.motivo_corrente = "avvio"

    def _plausibile(self, t):
        """True se l'encoder concorda con GPS/IMU (non e' una prova di verita': cerca guasti grossi)."""
        pl = self.pl
        bad_v = False
        if self.fus.t_gps is not None and t - self.fus.t_gps <= self.fcfg["gps_fresco_s"]:
            vf = self.fus.v
            bad_v = abs(self.enc.v - vf) > max(pl["tol_v_gps_ms"], pl["tol_v_gps_rel"] * vf)
        bad_a = self.imu.viva(t) and abs(self.enc.a - self.imu.a_liscia) > pl["tol_a_imu_ms2"]
        self._t_bad_v = (self._t_bad_v if self._t_bad_v is not None else t) if bad_v else None
        self._t_bad_a = (self._t_bad_a if self._t_bad_a is not None else t) if bad_a else None
        durata = pl["tempo_s"]
        if (self._t_bad_v is not None and t - self._t_bad_v >= durata) or \
           (self._t_bad_a is not None and t - self._t_bad_a >= durata):
            return False, "encoder in disaccordo con " + ("GPS" if self._t_bad_v is not None and t - self._t_bad_v >= durata else "IMU")
        return True, ""

    def scegli(self, t):
        enc_ok = self.enc.fresco(t)
        motivo = ""
        if enc_ok:
            ok, m = self._plausibile(t)
            if not ok:
                if not self.enc_implausibile:
                    motivo = m
                    # ricaduta presto dopo una riammissione: attesa raddoppiata (niente va-e-vieni), max 60 s
                    if t - self._t_riammesso < 60.0:
                        self._riamm = min(60.0, self._riamm * 2.0)
                    elif t - self._t_riammesso > 300.0:
                        self._riamm = self.pl["riammissione_s"]
                self.enc_implausibile = True
                self._t_ok = None
            elif self.enc_implausibile:
                # riammissione: solo con prove IN MOVIMENTO (fermo = encoder 0 e GPS 0 concordano sempre, non prova nulla)
                prova = self.fus.t_gps is not None and t - self.fus.t_gps <= self.fcfg["gps_fresco_s"] \
                    and max(self.enc.v, self.fus.v) > 1.0
                if not prova:
                    self._t_ok = None
                else:
                    self._t_ok = self._t_ok if self._t_ok is not None else t
                    if t - self._t_ok >= self._riamm:
                        self.enc_implausibile = False
                        self._t_riammesso = t
                        motivo = "encoder di nuovo coerente (in movimento)"
        else:
            motivo = "encoder non fresco (nessun dato nuovo da %.2f s)" % (
                t - self.enc.t_nuovo if self.enc.t_nuovo is not None else -1)
        f = self.fus
        if enc_ok and not self.enc_implausibile:
            nuova = "ENC"
            motivo = motivo or ("encoder fresco e coerente" if self.fonte != "NESSUNA" else "avvio")
        elif f.t_gps is not None and t - f.t_gps <= self.fcfg["gps_fresco_s"]:
            nuova = "GPS_IMU"
            motivo = motivo or "GPS ok"
        elif f.t_ble is not None and t - f.t_ble <= self.fcfg["ble_fresco_s"]:
            nuova = "BLE_IMU"
            motivo = motivo or "GPS assente/senza fix"
        elif self.imu.viva(t) and f.t_ult_buono is not None and t - f.t_ult_buono <= self.fcfg["imu_solo_max_s"] \
                and f.sigma_v < self.fcfg["sigma_v_max_ms"]:
            nuova = "IMU_SOLO"
            motivo = motivo or "ne' GPS ne' BLE: solo IMU (breve)"
        else:
            nuova = "NESSUNA"
            motivo = motivo or "nessuna fonte di velocita'"
        if nuova in ("GPS_IMU", "BLE_IMU") and not self.imu.in_moto(t):
            nuova = "FERMO_IMU"                       # GPS/BLE dicono 'si muove' ma l'IMU non vibra: rumore GPS a bici ferma
            motivo = "IMU non vibra (bici ferma): GPS/BLE ignorati"
        if nuova != self.fonte:
            self.eventi.append((t, self.fonte, nuova, motivo or self.motivo_corrente))
            if self.fonte == "ENC" and nuova != "ENC":
                self._off = 0.0 if self.enc_implausibile else (self._v_enc_ult - f.v)
                self._t_off = t
            elif nuova == "ENC":
                self._off = 0.0
            self.fonte = nuova
        return self.fonte

    def stato(self, t):
        """(v, a, fonte) da usare nel controllo."""
        fonte = self.scegli(t)
        f = self.fus
        if fonte == "ENC":
            self._v_enc_ult = self.enc.v
            return self.enc.v, self.enc.a, fonte
        if fonte == "NESSUNA":
            return None, None, fonte
        if fonte == "FERMO_IMU":
            return 0.0, 0.0, fonte
        v = f.v
        if self._off and self._t_off is not None:
            v += self._off * math.exp(-(t - self._t_off) / 1.0)
        a = self.imu.a_liscia - f.b
        return max(0.0, v), a, fonte

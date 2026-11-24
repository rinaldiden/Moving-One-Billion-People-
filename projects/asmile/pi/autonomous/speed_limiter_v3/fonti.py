"""Fonti di velocita' e decelerazione: encoder ruota (primaria), fusione GPS+IMU, BLE CooSpo, arbitro.
Nessun import hardware. Tutto lavora su un 'Campione' che riempie hw.py (vero) o sim.py (CSV)."""
import math
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass
from typing import Optional

G = 9.81


def sanifica_velocita(x, vmax=15.0):
    """Velocita' esterna (GPS/BLE) -> float finito in [0, vmax] oppure None. Mai eccezioni: dato sporco = nessun dato."""
    try:
        v = float(x)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(v) or v < 0.0 or v > vmax:
        return None
    return v


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


BANDA_PEDALE_HZ = (1.5, 3.5)       # picco dell'accelerazione dovuto alle pedalate (2 spinte per giro di pedale)


class Encoder:
    """v e a dalla distanza percorsa dall'encoder ruota (t dell'encoder, non il clock del loop).
    24/11 STIMATORE A PETTINE: le pedalate (picco ~2.5 Hz, 2 spinte per giro) sono il 'rumore' dell'accelerazione, non
    l'encoder. v_ma = spostamento su UNA spinta (periodo T stimato online dal picco 1.5-3.5 Hz) / T = media mobile che
    cancella la pedalata e le sue armoniche, con meno ritardo di un EWMA; a = pendenza (regressione) di v_ma su ~T/2;
    v = v_ma + a*T/2 (compensa il ritardo della media). Prima del riempimento, o se il pettine non e' pronto:
    parabola ai minimi quadrati sugli ultimi 0.3 s (v_par, a_par, come WheelEncoder._fit)."""

    def __init__(self, cfg):
        self.k = cfg["m_per_count"]
        self.win = cfg["finestra_parabola_s"]
        self.max_step = cfg["max_salto_counts"]
        self.fresco_s = cfg["fresco_s"]
        self.sgn = 1 if cfg["verso_avanti"] >= 0 else -1
        self.indietro = False        # retromarcia: v firmata negativa
        self.v_firmata = 0.0
        self._last = None
        self._cum = 0
        self._hist = deque()
        self.v = 0.0
        self.a = 0.0
        self.t_nuovo = None          # istante host dell'ultimo dato nuovo
        self.glitch = 0
        self.v_par = 0.0
        self.a_par = 0.0
        self.T = cfg["pedale_T_default_s"]
        self.T_min, self.T_max = cfg["pedale_T_min_s"], cfg["pedale_T_max_s"]
        self.v_min_pedale = cfg["pedale_v_min_ms"]
        self._lt, self._ls = [], []          # storia lunga (te, s) per il pettine
        self._vma = deque()                  # (te, v_ma)
        self._t_spettro = -1e9
        self.pettine = False                 # True se v, a vengono dal pettine

    def aggiorna(self, t, enc):
        if enc is None:
            return
        try:
            te, c = float(enc[0]), int(enc[1])
        except (TypeError, ValueError, IndexError, OverflowError):
            return
        if not math.isfinite(te):
            return
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
            self._lt.clear()
            self._ls.clear()
            self._vma.clear()
            self.t_nuovo = t
            return
        self._cum += self.sgn * d       # FIRMATO: la retromarcia non conta come avanti
        self.t_nuovo = t
        self._fit(te)
        self._pettine(te)

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
            self.v_par, self.a_par = max(0.0, sol[1]), 2.0 * sol[2]
            if not self.pettine:
                self.v_firmata = sol[1]
                self.indietro = sol[1] < -0.3
                self.v = self.v_par
                self.a = self.a_par

    def _s_a(self, tau):
        """spostamento interpolato all'istante tau (None se fuori storia)."""
        lt, ls = self._lt, self._ls
        i = bisect_right(lt, tau)
        if i == 0 or i >= len(lt):
            return None
        f = (tau - lt[i - 1]) / (lt[i] - lt[i - 1])
        return ls[i - 1] + f * (ls[i] - ls[i - 1])

    def _stima_periodo(self, te):
        """picco di potenza dell'accelerazione in 1.5-3.5 Hz sugli ultimi 2 s (DFT diretta ai t veri dell'encoder)."""
        lt = self._lt
        i0 = bisect_right(lt, te - 2.0)
        ts, xs = [], []
        for i in range(i0 + 5, len(lt)):          # v su 0.1 s: spostamento fra i campioni a ~0.1 s
            s0 = self._s_a(lt[i] - 0.1)
            if s0 is None:
                continue
            ts.append(lt[i])
            xs.append((self._ls[i] - s0) / 0.1)
        if len(xs) < 60 or ts[-1] - ts[0] < 1.5:
            return None
        m = sum(xs) / len(xs)
        xs = [x - m for x in xs]
        pot = []
        for k in range(21):                       # 1.5 .. 3.5 Hz passo 0.1
            f = BANDA_PEDALE_HZ[0] + 0.1 * k
            w = 2 * math.pi * f
            c = sum(x * math.cos(w * t) for x, t in zip(xs, ts))
            sn = sum(x * math.sin(w * t) for x, t in zip(xs, ts))
            pot.append(f * f * (c * c + sn * sn))        # *f^2: spettro dell'accelerazione
        j = max(range(21), key=lambda q: pot[q])
        med = sorted(pot)[10]
        if pot[j] < 3.0 * med or pot[j] <= 0:
            return None
        return 1.0 / (BANDA_PEDALE_HZ[0] + 0.1 * j)

    def _pettine(self, te):
        self._lt.append(te)
        self._ls.append(self._cum * self.k)
        if len(self._lt) > 600:
            del self._lt[:200]
            del self._ls[:200]
        if self.v_par > self.v_min_pedale and te - self._t_spettro >= 0.5:
            self._t_spettro = te
            Tn = self._stima_periodo(te)
            if Tn is not None:
                self.T = min(self.T_max, max(self.T_min, 0.7 * self.T + 0.3 * Tn))
        T = self.T
        s0 = self._s_a(te - T)
        if s0 is None:
            self.pettine = False
            return
        vma = (self._cum * self.k - s0) / T
        self._vma.append((te, vma))
        while len(self._vma) > 3 and te - self._vma[0][0] > 0.5 * T:
            self._vma.popleft()
        if len(self._vma) < 6 or te - self._vma[0][0] < 0.3 * T:
            self.pettine = False
            return
        n = len(self._vma)
        tm = sum(p[0] for p in self._vma) / n
        vm = sum(p[1] for p in self._vma) / n
        den = sum((p[0] - tm) ** 2 for p in self._vma)
        a = sum((p[0] - tm) * (p[1] - vm) for p in self._vma) / den if den > 0 else 0.0
        v = vma + a * T / 2.0
        self.pettine = True
        self.v_firmata = v
        self.indietro = v < -0.3
        self.v = max(0.0, v)
        self.a = a

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
        self.vibr_on, self.vibr_off = cfg["vibr_moto_g"], cfg["vibr_fermo_g"]
        self.a_min, self.a_max = cfg["a_min_g"], cfg["a_max_g"]            # su MEDIA 1 s
        self.ai_min, self.ai_max = cfg["a_min_inst_g"], cfg["a_max_inst_g"]  # istantaneo: solo dati spazzatura
        self._wa = deque()
        self._swa = 0.0
        self.congelato = cfg["congelato_cicli"]
        self.ay0, self.gx0 = cfg["ay_riposo_g"], cfg["gx_bias_dps"]        # valori del file: ancora delle ricalibrazioni
        self.dev_ay, self.dev_gx = cfg["recal_max_dev_ay_g"], cfg["recal_max_dev_gx_dps"]
        self.rec_dec, self.rec_gx = cfg["recal_max_dec_ms2"], cfg["recal_max_gx_dps"]
        self._prec = None
        self._ripetuti = 0
        self.scartati = 0
        self.motivo_scarto = ""

    def _valido(self, imu):
        """Campione utile: 6 numeri finiti, |a| fra a_min e a_max g, e non uguale a quello prima per 'congelato' cicli."""
        try:
            ax, ay, az, gx, gy, gz = (float(x) for x in imu)
        except (TypeError, ValueError):
            return False, "campione IMU malformato"
        if not all(math.isfinite(x) for x in (ax, ay, az, gx, gy, gz)):
            return False, "IMU non finita"
        a = math.sqrt(ax * ax + ay * ay + az * az)
        if not (self.ai_min <= a <= self.ai_max):
            return False, "IMU |a|=%.2f g istantaneo fuori %.1f-%.1f" % (a, self.ai_min, self.ai_max)
        self._wa.append(a)
        self._swa += a
        if len(self._wa) > 50:
            self._swa -= self._wa.popleft()
        if len(self._wa) >= 25:
            m = self._swa / len(self._wa)
            if not (self.a_min <= m <= self.a_max):
                return False, "IMU |a| medio %.2f g fuori %.1f-%.1f" % (m, self.a_min, self.a_max)
        tup = (ax, ay, az, gx, gy, gz)
        self._ripetuti = self._ripetuti + 1 if tup == self._prec else 0
        self._prec = tup
        if self._ripetuti + 1 >= self.congelato:
            return False, "IMU congelata (%d campioni uguali)" % (self._ripetuti + 1)
        return True, ""

    def aggiorna(self, t, imu, fermo):
        if imu is None:
            return
        ok, motivo = self._valido(imu)
        if not ok:                       # dato non valido = come se non fosse arrivato (l'IMU invecchia e diventa 'morta')
            self.scartati += 1
            self.motivo_scarto = motivo
            return
        ax, ay, az, gx, gy, gz = (float(x) for x in imu)
        dt = 0.02 if self._t_prec is None else max(1e-3, min(0.2, t - self._t_prec))
        self._t_prec = t
        self._t_ultimo = t
        # ricalibra riposo/bias SOLO se: encoder fermo (fermo) E senza vibrazione E dec e gx piccoli, e con clamp vicino al file
        if fermo and not self.in_moto(t, 3.0) and abs((ay - self.ay_riposo) * G) < self.rec_dec \
                and abs(gx - self.gx_bias) < self.rec_gx:
            al = min(1.0, dt / 1.0)
            self.ay_riposo += al * (ay - self.ay_riposo)
            self.gx_bias += al * (gx - self.gx_bias)
            self.ay_riposo = max(self.ay0 - self.dev_ay, min(self.ay0 + self.dev_ay, self.ay_riposo))
            self.gx_bias = max(self.gx0 - self.dev_gx, min(self.gx0 + self.dev_gx, self.gx_bias))
            self.riposo_calibrato = True
        dt = min(dt, 0.12)                                # tempo VERO fino a 120 ms (redteam 23/11: col tetto a 50 ms un loop a 10 Hz
                                                          # non vedeva un'impuntata debole); oltre e' un buco di dati: non gonfiare
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
        if not math.isfinite(a_avanti):
            a_avanti = 0.0
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
        v = sanifica_velocita(v, self.c["v_max_valida_ms"])
        if v is None:
            return False
        if not math.isfinite(self.v) or not math.isfinite(self.b):     # stato corrotto: riparte pulito
            self.v, self.b, self.init = 0.0, 0.0, False
            self.P = [[4.0, 0.0], [0.0, 0.25]]
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
        return True

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
        self._t_av = None
        self.avviso_failopen = False
        self._t_bad_i = None

    def _plausibile(self, t):
        """True se l'encoder concorda con GPS/IMU (non e' una prova di verita': cerca guasti grossi)."""
        pl = self.pl
        bad_v = False
        if self.fus.t_gps is not None and t - self.fus.t_gps <= self.fcfg["gps_fresco_s"]:
            vf = self.fus.v
            bad_v = abs(self.enc.v - vf) > max(pl["tol_v_gps_ms"], pl["tol_v_gps_rel"] * vf)
        bad_a = self.imu.viva(t) and abs(self.enc.a - self.imu.a_liscia) > pl["tol_a_imu_ms2"]
        # l'encoder inventa velocita' (anche senza GPS): dice moto ma l'IMU non vibra (misurato: ferma p95 0.006 g, in moto p5 0.048 g)
        bad_i = self.imu.viva(t) and self.enc.v > pl["vel_senza_vibrazione_ms"] and not self.imu.in_moto(t, 1.0)
        self._t_bad_i = (self._t_bad_i if self._t_bad_i is not None else t) if bad_i else None
        self._t_bad_v = (self._t_bad_v if self._t_bad_v is not None else t) if bad_v else None
        self._t_bad_a = (self._t_bad_a if self._t_bad_a is not None else t) if bad_a else None
        durata = pl["tempo_s"]
        if self._t_bad_i is not None and t - self._t_bad_i >= durata:
            return False, "encoder dice moto ma l'IMU non vibra"
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
                prova = (self.fus.t_gps is not None and t - self.fus.t_gps <= self.fcfg["gps_fresco_s"]
                         and max(self.enc.v, self.fus.v) > 1.0) or (self.enc.v > 1.0 and self.imu.in_moto(t, 1.0))
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
        if nuova != "ENC" and self.imu.viva(t) and not self.imu.in_moto(t):
            nuova = "FERMO_IMU"                       # GPS/BLE/encoder dicono 'si muove' ma l'IMU non vibra: bici ferma
            motivo = "IMU non vibra (bici ferma): velocita' esterne ignorate"
        self._avvisa(t, nuova)
        if nuova != self.fonte:
            self.eventi.append((t, self.fonte, nuova, motivo or self.motivo_corrente))
            if self.fonte == "ENC" and nuova != "ENC":
                self._off = 0.0 if self.enc_implausibile else (self._v_enc_ult - f.v)
                self._t_off = t
            elif nuova == "ENC":
                self._off = 0.0
            self.fonte = nuova
        return self.fonte

    def _avvisa(self, t, nuova):
        """Fail-open da rendere VISIBILE: encoder fermo (o non plausibile) ma l'IMU vibra e non c'e' GPS/BLE = nessun limite."""
        cieco = nuova in ("NESSUNA", "IMU_SOLO") and self.imu.viva(t) and self.imu.in_moto(t, 1.0)
        enc_fermo = self.enc.fresco(t) and self.enc.v < 0.1
        cond = (nuova == "ENC" and enc_fermo and self.imu.in_moto(t, 1.0) and self.imu.vibr > 3 * self.imu.vibr_on
                and (self.fus.t_gps is None or t - self.fus.t_gps > self.fcfg["gps_fresco_s"])
                and (self.fus.t_ble is None or t - self.fus.t_ble > self.fcfg["ble_fresco_s"])) or cieco
        if cond:
            self._t_av = self._t_av if self._t_av is not None else t
            if t - self._t_av >= 3.0 and not self.avviso_failopen:
                self.avviso_failopen = True
                self.eventi.append((t, nuova, nuova, "AVVISO fail-open: la bici vibra ma la velocita' e' ferma/ignota e non c'e' GPS/BLE: nessun limite attivo"))
        else:
            self._t_av = None
            self.avviso_failopen = False

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

"""Freno: rampa, tetto 50 gradi, impulso+pin libero (50 Hz), guardia INA219, anti-impuntata.
Nessun import hardware: il backend (lgpio vero o finto) arriva da fuori con due metodi: pwm(angolo) e libera()."""
import math

TETTO_ASSOLUTO = 50.0       # nel codice: il file soglie puo' solo abbassarlo. Mai oltre (a 60 il servo stalla).
SERVO_HZ = 50               # mai 330 Hz


def angle_to_duty(angle):
    """0 gradi logici = rilasciato (raw 180), come speed_limiter v2. Duty % a 50 Hz, impulso 500-2500 us."""
    raw = 180.0 - angle
    pulse_us = 500 + (raw / 180.0) * 2000
    return pulse_us / (1_000_000 / SERVO_HZ) * 100.0


class Rampa:
    def __init__(self, cfg):
        self.c = cfg
        self.angolo = 0.0

    def passo(self, target, tetto, dt, su_max=None, sopra_vmax=False, r_su=None, r_giu=None):
        c = self.c
        tetto = min(tetto, c["tetto_deg"], TETTO_ASSOLUTO)
        target = max(0.0, min(target, tetto))
        if target > self.angolo:
            r = c["rampa_su_oltre_soglia_deg_s"] if self.angolo >= c["soglia_lenta_deg"] else c["rampa_su_deg_s"]
            if sopra_vmax and self.angolo < c["soglia_lenta_deg"]:
                r = c["rampa_su_sopra_vmax_deg_s"]       # sopra 15 km/h sale un po' piu' in fretta (sempre sotto 35)
            if r_su is not None:                         # fascia di contatto (Regolatore): rampa propria, mai oltre la lenta sopra soglia
                r = r_su if self.angolo < c["soglia_lenta_deg"] else min(r_su, c["rampa_su_oltre_soglia_deg_s"])
            if su_max is not None:
                r = min(r, su_max)
            self.angolo = min(target, self.angolo + r * dt)
        else:
            r = c["rampa_giu_deg_s"] if r_giu is None else r_giu
            if self.angolo > tetto:                      # tetto sceso: rilascio a rampa (veloce), niente salto secco
                r = max(r, c["rampa_tetto_deg_s"])
            self.angolo = max(target, self.angolo - r * dt)
        return self.angolo

    def azzera(self):
        self.angolo = 0.0


class ImpulsoServo:
    """Impulso + pin libero (hi-Z): nuovo impulso solo se l'angolo cambia di >= trigger (o per tornare a 0), PWM tenuto
    'tieni_s', poi pwm off + gpio_free. Mai LOW continuo. Chiamato DENTRO il loop di controllo."""

    def __init__(self, backend, cfg):
        self.b = backend
        self.c = cfg
        self.ultimo = 0.0          # ultimo angolo impulsato
        self.attivo = False
        self.t_inizio = -1e9
        self.n_impulsi = 0
        self.max_comandato = 0.0
        self.tieni = cfg["impulso_tieni_s"]
        self.n_riprova_zero = 0

    def _tieni(self, angolo, delta):
        """24/11: con 0,15 s fissi il ritorno a 0 non arrivava (freno rimasto chiuso, servo in stallo 3,2 A). Il PWM resta
        acceso il tempo della corsa (tieni_per_grado_s), e per tornare a 0 almeno tieni_zero_s (master ON usa 1,5 s e apre)."""
        c = self.c
        s = max(c["impulso_tieni_s"], delta * c["tieni_per_grado_s"])
        if angolo == 0.0:
            s = max(s, c["tieni_zero_s"])
        return s

    def _impulso(self, t, angolo, delta):
        self.b.pwm(angolo)
        self.attivo = True
        self.ultimo = angolo
        self.t_inizio = t
        self.tieni = self._tieni(angolo, delta)
        self.n_impulsi += 1
        self.max_comandato = max(self.max_comandato, angolo)

    def tick(self, t, angolo):
        c = self.c
        angolo = max(0.0, min(angolo, c["tetto_deg"], TETTO_ASSOLUTO))
        if angolo < c["libera_sotto_deg"]:
            angolo = 0.0
        delta = abs(angolo - self.ultimo)
        verso_zero = angolo == 0.0 and self.ultimo != 0.0
        if delta >= c["impulso_trigger_deg"] or verso_zero:
            # il tempo della corsa si somma a quello che restava dell'impulso precedente (rampa a gradini di 1 grado)
            resto = max(0.0, self.tieni - (t - self.t_inizio)) if self.attivo else 0.0
            self._impulso(t, angolo, delta)
            self.tieni = max(self.tieni, resto + delta * c["tieni_per_grado_s"])
            return
        if self.attivo and t - self.t_inizio >= self.tieni:
            self.b.libera()
            self.attivo = False

    RIPROVE_ZERO_MAX = 4

    def riprova_zero(self, t):
        """Comandato 0 ma il servo assorbe ancora corrente (non si e' aperto): nuovo impulso lungo a 0. Al massimo
        RIPROVE_ZERO_MAX volte (servo in stallo = rischio burnout): poi pin libero e solo avviso."""
        if self.n_riprova_zero >= self.RIPROVE_ZERO_MAX:
            return False
        self._impulso(t, 0.0, 0.0)
        self.n_riprova_zero += 1
        return True

    def fermo_da(self, t):
        """Da quanti secondi non parte un nuovo impulso."""
        return t - self.t_inizio

    def chiudi(self):
        if self.attivo:
            self.b.libera()
            self.attivo = False


class GuardiaIna:
    """Servo fermo + corrente > soglia per > tempo => arretra di qualche grado (tetto temporaneo)."""

    def __init__(self, cfg):
        self.c = cfg
        self.t_alto = None
        self.cap = None
        self.n_arretra = 0
        self.t_ma_ok = None          # ultimo istante con una lettura INA valida
        self.assente = False         # INA non risponde: guardia SPENTA, avviso visibile

    def passo(self, t, ma, fermo_da, angolo):
        c = self.c
        if ma is not None and not math.isfinite(ma):
            ma = None
        if ma is not None:
            self.t_ma_ok = t
            self.assente = False
        else:
            if self.t_ma_ok is None:
                self.t_ma_ok = t
            self.assente = (t - self.t_ma_ok) >= c["assente_dopo_s"]
        if ma is None or fermo_da < c["servo_fermo_s"] or ma <= c["ma_fermo_max"]:
            self.t_alto = None
            if angolo <= 0.0:
                self.cap = None
            return self.cap
        if self.t_alto is None:
            self.t_alto = t
        if t - self.t_alto >= c["tempo_s"]:
            self.cap = max(0.0, angolo - c["arretra_deg"])
            self.n_arretra += 1
            self.t_alto = None
        return self.cap


class AntiImpuntata:
    """Regola fissa sopra tutto. Condizione: dec IMU >= 2.0 E muso giu' >= 1.5 gradi in 0.3 s.
    Nello STESSO ciclo togli 'rilascio_gradi' (non per forza 0); se nel ciclo dopo il muso scende ancora togli ancora, fino a 0.
    Poi niente salita per 'fermo_s', e ripresa DOLCE (rampa lenta) col 70% della forza, solo con la bici in piano."""

    def __init__(self, cfg, tetto):
        self.c = cfg
        self.tetto = tetto
        self.cap = None
        self.t_cap = -1e9
        self.t_piano = None
        self.t_ult = -1e9            # ultimo scatto
        self.fermo_fino = -1e9
        self.ripresa_fino = -1e9
        self.cap_prec = None
        self.cap_prec_fino = -1e9
        self.scatti = []             # (t, angolo_prima, angolo_dopo, dec, d03, v): 1 riga per ciclo di scatto
        self.episodi = []            # t di inizio di ogni episodio (scatti separati da >1 s)
        self.precoci = 0

    def passo(self, t, v, imu, angolo):
        """Ritorna (nuovo_angolo_o_None, no_aumento, su_max_o_None, cap). nuovo_angolo e' l'angolo da applicare SUBITO."""
        c = self.c
        nuovo = None
        cond = imu.viva(t) and imu.dec >= c["dec_imu_min_ms2"] and imu.d03 >= c["muso_giu_min_deg"]
        if cond:
            prima_ciclo = (t - self.t_ult) > 0.05          # il ciclo subito prima non era di scatto: primo giro dell'episodio
            ancora_giu = imu.gx > c["ancora_giu_dps"]
            if prima_ciclo or ancora_giu:
                if t - self.t_ult > 1.0:
                    self.episodi.append(t)
                    self.cap = c["ripresa_frazione"] * angolo if angolo >= 5.0 else None
                    self.t_cap = t
                nuovo = max(0.0, angolo - c["rilascio_gradi"])
                self.scatti.append((t, angolo, nuovo, imu.dec, imu.d03, v))
            self.t_ult = t
            self.fermo_fino = t + c["fermo_s"]
            self.t_piano = None
        tp = c["tetto_precoce"]
        if tp["attivo"] and imu.viva(t) and imu.dec >= tp["dec_imu_ms2"] and angolo > 0 and nuovo is None:
            self.cap_prec = tp["frazione"] * angolo
            self.cap_prec_fino = t + 1.0
            self.precoci += 1
        piano = abs(imu.d03) < c["ripresa_in_piano_deg"] and abs(imu.gx) < c["ripresa_in_piano_dps"]
        self.t_piano = (self.t_piano if self.t_piano is not None else t) if piano else None
        no_aum = t < self.fermo_fino
        if not no_aum and self.cap is not None and t - self.t_cap < 5.0 and \
                (self.t_piano is None or t - self.t_piano < c["ripresa_in_piano_s"]):
            no_aum = True                                    # aspetta la bici in piano prima di risalire
        if self.cap is not None and t - self.t_cap > c["ripresa_ripristino_s"]:
            self.cap = None
        # ripresa lenta: parte quando finisce il fermo
        if t >= self.fermo_fino and self.ripresa_fino < self.fermo_fino and self.cap is not None and t - self.t_cap < 5.0:
            self.ripresa_fino = t + c["ripresa_rampa_s"]
        su_max = c["ripresa_rampa_deg_s"] if t < self.ripresa_fino else None
        cap = self.cap
        if self.cap_prec is not None and t < self.cap_prec_fino:
            cap = self.cap_prec if cap is None else min(cap, self.cap_prec)
        return nuovo, no_aum, su_max, cap


def fit_contatto(pt, cmin, cmax, passo=0.25):
    """Fit a CERNIERA: eccesso_decel = g*max(0, angolo - c0) + rumore, sui punti (angolo_ritardato, eccesso) di una salita lenta.
    Niente soglie sui singoli punti (il rumore dell'accelerazione, ~0.2-0.3 m/s2, sta sotto la soglia di rilevazione):
    si cerca c0 in [cmin, cmax] che minimizza lo scarto. Ritorna (c0, g) o None se la cerniera non batte la retta piatta."""
    if len(pt) < 12:
        return None
    xs = [p[0] for p in pt]
    ys = [p[1] for p in pt]
    n = len(pt)
    ym = sum(ys) / n
    sse_flat = sum((y - ym) ** 2 for y in ys)
    best = None
    c = cmin
    while c <= cmax + 1e-9:
        xx = [max(0.0, x - c) for x in xs]
        sxx = sum(q * q for q in xx)
        if sxx > 1e-6:
            g = sum(q * y for q, y in zip(xx, ys)) / sxx
            sse = sum((y - g * q) ** 2 for q, y in zip(xx, ys))
            if best is None or sse < best[0]:
                best = (sse, c, g)
        c += passo
    if best is None:
        return None
    sse, c0, g = best
    if g < 0.03 or g > 0.6 or sse > 0.5 * sse_flat or sum(1 for x in xs if x > c0 + 0.5) < 6:
        return None
    base = [y for x, y in pt if x < c0 - 0.5]            # prima del contatto l'eccesso deve essere ~0 (a_nat coerente)
    if len(base) < 6 or abs(sum(base) / len(base)) > 0.12:
        return None
    return c0, g


class Regolatore:
    """Regolatore sull'ENCODER RUOTA (24/11, Daniele: il loop vede da solo quando la decel compare, niente angoli a priori).
    v e a arrivano dallo stimatore a pettine (fonti.Encoder: pedalate cancellate). Fasi (campo `fase`, nel log):
      - 'libero': sotto zona-0.5 km/h, angolo 0.
      - 'avvicinamento_contatto': ingaggiato, angolo sotto contatto-margine: salita veloce (rampa_avvicinamento) se il contatto
        e' APPRESO, lenta (<= rampa_cerca, 12 gradi/s) col default prudente basso. NON frena ancora.
      - 'fine': PI sulla VELOCITA' attorno a v_obiettivo: angolo = (contatto-margine) + kp*e + I, kp ad hoc + termine solo sopra
        v_max, rampe piccole. Rilascio dolce: se la bici gia' rallenta quanto il profilo chiede (decel >= voluta) l'angolo
        non sale piu' e I cala piano; mai sotto contatto-margine finche' v >= zona-disimpegno (isteresi), poi 0.
    CONTATTO APPRESO: decel naturale a_nat (media lenta della a a freno sicuramente staccato). In ogni salita lenta
    dell'angolo si raccolgono (angolo ritardato, eccesso = a_nat - a): retta ai minimi quadrati sui punti 0.15-0.8 m/s2,
    intercetta a eccesso 0 = angolo di contatto; media lenta con la stima precedente (alfa), solo con fonte ENC e
    salita <= 12 gradi/s. Con fonte di riserva (GPS/BLE/IMU) niente apprendimento: default prudente e avvicinamento lento.
    a_des/livello (profilo di decel voluta per zona) restano per log e per i picchi massimi."""

    def __init__(self, cfg, contatto0=None):
        self.v = cfg["velocita"]
        self.d = cfg["decel_obiettivo_ms2"]
        self.f = cfg["freno"]
        self.r = cfg["regolatore"]
        self.v1 = self.v["zona_inizio_kmh"] / 3.6
        self.v2 = self.v["v_max_kmh"] / 3.6
        self.v_set = self.r["v_obiettivo_kmh"] / 3.6
        self.v_ing = self.v1 - self.r["ingaggio_sotto_zona_kmh"] / 3.6
        self.v_dis = self.v1 - self.r["disimpegno_sotto_zona_kmh"] / 3.6
        self.g = None                   # guadagno del freno appreso (m/s2 per grado oltre il contatto) o None
        self.lag = self.f["ritardo_comando_decel_s"] + self.r["ritardo_misura_a_s"]
        self.contatto = None            # stima appresa (gradi) o None
        self.n_stime = 0
        if contatto0 is not None and self._plausibile(contatto0):
            self.contatto = float(contatto0)
        self.a_des = 0.0
        self.livello = "-"
        self.fase = "-"
        self.frena = False
        self.a_f = 0.0
        self._init = False
        self.ingaggiato = False
        self.I = 0.0
        self.rate_su = None
        self.rate_giu = None
        self.fonte = "ENC"              # lo imposta Controllo: si apprende solo con l'encoder
        self.t = 0.0
        self.a_nat = None
        self._t_lib = 0.0               # tempo accumulato a freno staccato: a_nat e' affidabile dopo a_nat_tau_s
        self._ang_h = []                # (t, angolo) ultimi ~1.5 s
        self._scan = None               # dict: punti, angolo di partenza, rate max
        self._pre = []                  # ultimi punti (angolo ritardato, eccesso) prima dell'inizio della salita
        self.appreso_ora = False        # True nel ciclo in cui la stima cambia (per salvarla)

    def _plausibile(self, x):
        return isinstance(x, (int, float)) and x == x and abs(x) < 1e6 and \
            self.f["contatto_min_deg"] <= x <= self.f["contatto_max_deg"]

    @property
    def contatto_uso(self):
        return self.contatto if self.contatto is not None else self.f["contatto_default_deg"]    # solo per la finestra dello scan

    @property
    def base(self):
        """angolo di attesa: contatto appreso - margine; con contatto ignoto contatto_min - margine (sotto qualunque contatto
        plausibile: non frena mai) e poi si cerca il contatto con salita lenta."""
        if self.contatto is not None:
            return self.contatto - self.f["margine_contatto_deg"]
        return self.f["contatto_min_deg"] - self.f["margine_contatto_deg"]      # ignoto: sotto il minimo plausibile, mai a contatto

    def _apprendi(self, dt, angolo, a_f):
        """aggiorna a_nat e la ricerca del contatto. Chiamato a ogni ciclo con l'angolo comandato (prima della decisione)."""
        r, f = self.r, self.f
        self.appreso_ora = False
        self.t += dt
        t = self.t
        self._ang_h.append((t, angolo))
        while self._ang_h and t - self._ang_h[0][0] > 1.5:
            self._ang_h.pop(0)
        libero = angolo <= self.base + 1e-9      # sicuramente staccato (ignoto: sotto il minimo plausibile)
        if self.a_nat is None:
            self.a_nat = a_f
        elif libero:
            self.a_nat += min(1.0, dt / r["a_nat_tau_s"]) * (a_f - self.a_nat)
            self._t_lib += dt
        if self.fonte != "ENC" or not self.ingaggiato:
            self._scan = None
            return
        # angolo di ~lag secondi fa
        ang_d = angolo
        for (th, ah) in self._ang_h:
            if th >= t - self.lag:
                ang_d = ah
                break
        sal = angolo - self._ang_h[0][1]
        eccesso = self.a_nat - a_f
        sc = self._scan
        self._pre.append((ang_d, eccesso))
        if len(self._pre) > 75:
            self._pre.pop(0)
        if sc is None:
            if sal > 0.3 and eccesso < r["contatto_soglia_fit_a_ms2"] and self._t_lib >= r["a_nat_tau_s"]:
                self._scan = {"pt": list(self._pre), "t0": t, "a0": min(h[1] for h in self._ang_h), "ultimo": angolo,
                              "a_nat": self.a_nat}
            return
        sc["ultimo"] = max(sc["ultimo"], angolo)
        if angolo < sc["ultimo"] - 1.0:                  # l'angolo scende: la ricerca e' finita
            self._chiudi_scan(t, angolo)
            return
        sc["pt"].append((ang_d, eccesso))
        if eccesso >= r["contatto_soglia_fit_a_ms2"] or (t - sc["t0"] > 6.0):
            self._chiudi_scan(t, angolo)

    def _chiudi_scan(self, t, angolo):
        sc, r, f = self._scan, self.r, self.f
        self._scan = None
        dur = max(1e-3, t - sc["t0"])
        if (sc["ultimo"] - sc["a0"]) / dur > r["contatto_rate_max_deg_s"] + 1e-6:
            return                                       # salita troppo veloce: niente stima
        if abs(sc["a_nat"]) > r["contatto_a_nat_max_ms2"]:
            return                                       # impara solo in condizioni tranquille (non in forte accelerazione/transitorio)
        res = fit_contatto(sc["pt"], f["contatto_min_deg"] - 2.0, f["contatto_max_deg"] + 2.0)
        if res is None or not self._plausibile(res[0]):
            return
        c0, g = res
        self.g = g if self.g is None else self.g + r["contatto_alfa"] * (g - self.g)
        self.contatto = c0 if self.contatto is None else self.contatto + r["contatto_alfa"] * (c0 - self.contatto)
        self.n_stime += 1
        self.appreso_ora = True

    def passo(self, v, a, angolo, dt):
        d, f, r = self.d, self.f, self.r
        self.rate_su = self.rate_giu = None
        if v is None:
            self.a_des, self.livello, self.fase, self.frena = 0.0, "cieco", "cieco", False
            self.ingaggiato, self.I, self._scan = False, 0.0, None
            return 0.0
        if not self._init:
            self.a_f, self._init = a, True
        self.a_f += min(1.0, dt / r["a_filtro_s"]) * (a - self.a_f)
        dec = -self.a_f
        vp = v + self.a_f * f["ritardo_comando_decel_s"]      # anticipo del ritardo comando->decelerazione
        if vp <= self.v1:
            self.a_des = r["a_pos_max_ms2"] * min(1.0, (self.v1 - vp) / 0.5)      # continua: 0 a 12 km/h, a_pos a ~10 km/h
            self.livello = "libero" if angolo < 0.5 else "rilascio"
        elif vp < self.v2:
            x = (vp - self.v1) / (self.v2 - self.v1)
            self.a_des, self.livello = -d["normale"] * x ** r["esponente_zona"], "avvicinamento"
        else:
            self.a_des, self.livello = -min(d["forte"], d["normale"] + r["k_sopra_15_ms2_per_ms"] * (vp - self.v2)), "sopra15"
        self.frena = angolo > 0.5 or self.a_des < 0
        pmax = d["forte_picco_max"] if self.livello == "sopra15" else d["normale_picco_max"]
        self._apprendi(dt, angolo, self.a_f)
        base = self.base
        kp = min(r["kp_max_deg_per_ms"], max(r["kp_min_deg_per_ms"], r["guadagno_anello_1_s"] / (self.g if self.g is not None else r["g_default_ms2_per_deg"])))
        ki = kp / r["ti_s"]
        if dec > d["mai_oltre"]:
            self.fase = "mai_oltre"
            self.I = max(0.0, min(self.I, angolo * 0.5 - base))
            return angolo * 0.5
        # isteresi: ingaggio a zona - ingaggio, disimpegno a zona - disimpegno
        if not self.ingaggiato:
            if vp >= self.v_ing:
                self.ingaggiato = True
                self.I = max(0.0, angolo - base)
        elif vp < self.v_dis:
            self.ingaggiato = False
        if not self.ingaggiato:
            self.fase, self.I, self._scan = "libero", 0.0, None
            return 0.0                                   # rilascio a rampa (rampa_giu), come prima
        tetto = min(f["tetto_deg"], TETTO_ASSOLUTO)
        umax = max(0.0, tetto - base)
        e = vp - self.v_set
        sopra = max(0.0, vp - self.v2) * r["kp_sopra_rel"] * kp      # sopra la v_max piu' deciso (solo li')
        u = kp * e + sopra + self.I
        gia = dec > 0.1 and dec >= -self.a_des            # sta gia' rallentando quanto il profilo chiede
        if not (e > 0 and u >= umax) and not (gia and e > 0):      # niente windup; se gia' rallenta non spinge di piu'
            self.I += ki * e * dt
        if gia:                                          # rilascio dolce
            self.I -= r["rilascio_dolce_deg_s"] * dt
        # I non resta davanti all'angolo reale piu' di 3 gradi (rampe, tetti, anti-impuntata a valle)
        self.I = max(0.0, min(self.I, umax, max(0.0, angolo - base) + 3.0))
        u = max(0.0, min(kp * e + sopra + self.I, umax))
        target = base + u
        if self.g is not None and self.contatto is not None:
            # con contatto e guadagno appresi: mai oltre l'angolo che darebbe la decel massima voluta (+50% di margine)
            target = min(target, self.contatto + 1.5 * (d["forte"] + max(self.a_nat or 0.0, 0.0)) / self.g)
        if gia or dec >= d["forte"]:                     # gia' rallenta abbastanza, o decel gia' al massimo voluto: non spinge di piu'
            target = min(target, max(angolo, base))
        if angolo < base - 0.3:
            self.fase = "avvicinamento_contatto"
            self.rate_su = f["rampa_avvicinamento_deg_s"] if (self.contatto is not None and self.fonte == "ENC") else f["rampa_cerca_deg_s"]
            target = min(target, base)
        else:
            self.fase = "fine"
            self.rate_su = f["rampa_fine_su_sopra15_deg_s"] if self.livello == "sopra15" else f["rampa_fine_su_deg_s"]
            if self.contatto is None or self.fonte != "ENC":
                self.rate_su = min(self.rate_su, f["rampa_cerca_deg_s"])
        if self.fase == "fine":
            # fluidita': la decel arriva con ritardo (comando + misura): la salita rallenta man mano che dec si avvicina al
            # massimo voluto, cosi' non si supera. rate = (forte - dec)/(g * ritardo), mai sotto 1.5 gradi/s
            g_eff = self.g if self.g is not None else r["g_default_ms2_per_deg"]
            self.rate_su = min(self.rate_su, max(1.5, (d["forte"] - max(dec, 0.0)) / (g_eff * self.lag)))
        self.rate_giu = f["rampa_fine_giu_deg_s"]
        if dec > pmax:
            target = min(target, angolo - f["k_anello_deg_s_per_ms2"] * (dec - pmax) * dt)
            self.I = max(0.0, min(self.I, target - base))
        return max(0.0, target)

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

    def passo(self, target, tetto, dt, su_max=None, sopra_vmax=False):
        c = self.c
        tetto = min(tetto, c["tetto_deg"], TETTO_ASSOLUTO)
        target = max(0.0, min(target, tetto))
        if target > self.angolo:
            r = c["rampa_su_oltre_soglia_deg_s"] if self.angolo >= c["soglia_lenta_deg"] else c["rampa_su_deg_s"]
            if sopra_vmax and self.angolo < c["soglia_lenta_deg"]:
                r = c["rampa_su_sopra_vmax_deg_s"]       # sopra 15 km/h sale un po' piu' in fretta (sempre sotto 35)
            if su_max is not None:
                r = min(r, su_max)
            self.angolo = min(target, self.angolo + r * dt)
        else:
            r = c["rampa_giu_deg_s"]
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

    def tick(self, t, angolo):
        c = self.c
        angolo = max(0.0, min(angolo, c["tetto_deg"], TETTO_ASSOLUTO))
        if angolo < c["libera_sotto_deg"]:
            angolo = 0.0
        delta = abs(angolo - self.ultimo)
        verso_zero = angolo == 0.0 and self.ultimo != 0.0
        if delta >= c["impulso_trigger_deg"] or verso_zero:
            self.b.pwm(angolo)
            self.attivo = True
            self.ultimo = angolo
            self.t_inizio = t
            self.n_impulsi += 1
            self.max_comandato = max(self.max_comandato, angolo)
            return
        if self.attivo and t - self.t_inizio >= c["impulso_tieni_s"]:
            self.b.libera()
            self.attivo = False

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


class Regolatore:
    """Anello CHIUSO sull'accelerazione misurata (encoder), nessuna tabella gradi->decel (i dati non la danno).
    - sotto zona_inizio (12): decel voluta = +a_pos (l'angolo cala piano a 0, niente on/off)
    - 12..15: rallenti dolcemente: decel voluta cresce da 0 a 'normale' (x^esponente)
    - sopra 15: riporti a 15: normale + k*(v-15), al massimo 'forte'
    L'angolo sale se la bici decelera meno del voluto, scende se di piu'. Banda morta + filtro = niente oscillazioni."""

    def __init__(self, cfg):
        self.v = cfg["velocita"]
        self.d = cfg["decel_obiettivo_ms2"]
        self.f = cfg["freno"]
        self.r = cfg["regolatore"]
        self.v1 = self.v["zona_inizio_kmh"] / 3.6
        self.v2 = self.v["v_max_kmh"] / 3.6
        self.a_des = 0.0
        self.livello = "-"
        self.frena = False
        self.a_f = 0.0

    def passo(self, v, a, angolo, dt):
        d, f, r = self.d, self.f, self.r
        if v is None:
            self.a_des, self.livello, self.frena = 0.0, "cieco", False
            return 0.0
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
        if vp < self.v1 - 0.5:                       # ben sotto la zona (> ~1.8 km/h): il freno non serve, rilascio a rampa veloce
            return 0.0
        pmax = d["forte_picco_max"] if self.livello == "sopra15" else d["normale_picco_max"]
        err = self.a_f - self.a_des
        if abs(err) < r["banda_morta_ms2"]:
            rate = 0.0
        else:
            rate = f["k_anello_deg_s_per_ms2"] * (err - (r["banda_morta_ms2"] if err > 0 else -r["banda_morta_ms2"]))
        if dec > pmax:
            rate = min(rate, -f["k_anello_deg_s_per_ms2"] * (dec - pmax))
        if dec > d["mai_oltre"]:
            return angolo * 0.5
        return max(0.0, angolo + rate * dt)

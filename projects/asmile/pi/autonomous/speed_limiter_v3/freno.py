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


class Regolatore:
    """Regolatore a FASCIA DI CONTATTO (24/11, richiesta di Daniele: loop fine dove il freno sfiora-lavora).
    Il freno vero ha una zona morta (fino a angolo_contatto non frena) e poi ~0.1-0.3 m/s2 per grado. L'accelerazione
    dell'encoder e' rumorosa (std ~0.4 m/s2): inseguirla fa 14-24 inversioni/min. Qui si controlla la VELOCITA' (poco rumorosa):
      - 'libero': sotto la zona, angolo 0.
      - 'avvicinamento_contatto': v >= zona-ingaggio: in fretta fino a contatto - margine (ancora NON frena).
      - 'fine': PI sulla velocita' attorno a v_obiettivo, angolo = (contatto - margine) + u, u = kp*e + I, kp ricavata dalla
        fascia ((lavoro - contatto) gradi alla v_max). Rampe piccole. Se la bici gia' rallenta quanto il profilo chiede (decel
        >= voluta) I cala piano (rilascio dolce) fino a contatto-margine. Non torna a 0 finche' v non e' sotto
        zona - disimpegno (isteresi). Nessun salto: tutto passa dalla Rampa; anti-impuntata e tetti restano a valle.
    a_des/livello (profilo di decel voluta per zona) restano per log e per i picchi massimi."""

    def __init__(self, cfg):
        self.v = cfg["velocita"]
        self.d = cfg["decel_obiettivo_ms2"]
        self.f = cfg["freno"]
        self.r = cfg["regolatore"]
        self.v1 = self.v["zona_inizio_kmh"] / 3.6
        self.v2 = self.v["v_max_kmh"] / 3.6
        self.v_set = self.r["v_obiettivo_kmh"] / 3.6
        self.v_ing = self.v1 - self.r["ingaggio_sotto_zona_kmh"] / 3.6
        self.v_dis = self.v1 - self.r["disimpegno_sotto_zona_kmh"] / 3.6
        self.base = self.f["angolo_contatto_deg"] - self.f["margine_contatto_deg"]
        self.kp = self.r["kp_scala"] * (self.f["angolo_lavoro_deg"] - self.f["angolo_contatto_deg"]) / (self.v2 - self.v_set)
        self.ki = self.kp / self.r["ti_s"]
        self.a_des = 0.0
        self.livello = "-"
        self.fase = "-"
        self.frena = False
        self.a_f = 0.0
        self.ingaggiato = False
        self.I = 0.0
        self.rate_su = None
        self.rate_giu = None

    def passo(self, v, a, angolo, dt):
        d, f, r = self.d, self.f, self.r
        self.rate_su = self.rate_giu = None
        if v is None:
            self.a_des, self.livello, self.fase, self.frena = 0.0, "cieco", "cieco", False
            self.ingaggiato, self.I = False, 0.0
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
        pmax = d["forte_picco_max"] if self.livello == "sopra15" else d["normale_picco_max"]
        if dec > d["mai_oltre"]:
            self.fase = "mai_oltre"
            self.I = max(0.0, min(self.I, angolo * 0.5 - self.base))
            return angolo * 0.5
        # isteresi: ingaggio a zona - ingaggio, disimpegno a zona - disimpegno
        if not self.ingaggiato:
            if vp >= self.v_ing:
                self.ingaggiato = True
                self.I = max(0.0, angolo - self.base)
        elif vp < self.v_dis:
            self.ingaggiato = False
        if not self.ingaggiato:
            self.fase, self.I = "libero", 0.0
            return 0.0                                   # rilascio a rampa (rampa_giu), come prima
        tetto = min(f["tetto_deg"], TETTO_ASSOLUTO)
        umax = max(0.0, tetto - self.base)
        e = vp - self.v_set
        sopra = max(0.0, vp - self.v2) * r["kp_sopra_deg_per_ms"]      # sopra la v_max piu' deciso (solo li')
        u = self.kp * e + sopra + self.I
        gia = dec > 0.1 and dec >= -self.a_des            # sta gia' rallentando quanto il profilo chiede
        if not (e > 0 and u >= umax) and not (gia and e > 0):      # niente windup; se gia' rallenta non spinge di piu'
            self.I += self.ki * e * dt
        if gia:                                          # rilascio dolce
            self.I -= r["rilascio_dolce_deg_s"] * dt
        # I non resta davanti all'angolo reale piu' di 3 gradi (rampe, tetti, anti-impuntata a valle)
        self.I = max(0.0, min(self.I, umax, max(0.0, angolo - self.base) + 3.0))
        u = max(0.0, min(self.kp * e + sopra + self.I, umax))
        target = self.base + u
        if gia:
            target = min(target, max(angolo, self.base))     # mai piu' freno se gia' rallenta abbastanza
        if angolo < self.base - 0.3:
            self.fase = "avvicinamento_contatto"
            self.rate_su = f["rampa_avvicinamento_deg_s"]
            target = min(target, self.base)
        else:
            self.fase = "fine"
            self.rate_su = f["rampa_fine_su_sopra15_deg_s"] if self.livello == "sopra15" else f["rampa_fine_su_deg_s"]
        self.rate_giu = f["rampa_fine_giu_deg_s"]
        if dec > pmax:
            target = min(target, angolo - f["k_anello_deg_s_per_ms2"] * (dec - pmax) * dt)
            self.I = max(0.0, min(self.I, target - self.base))
        return max(0.0, target)

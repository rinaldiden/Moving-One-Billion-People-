#!/usr/bin/env python3
"""Prova contatto/lavoro del freno #001, ruota posteriore SOLLEVATA, bici sul cavalletto.
Protocollo: agents/protocolli/freno_contatto_001_20261124.md   NON VERIFICATO sul Pi (mai girato: serve il "vai" di Daniele).

Cosa fa: gradini di 1 grado (0 -> max 30, tetto assoluto 50), ciascuno PWM 50 Hz per 2 s poi pin in ingresso (pinctrl ip pn),
ruota che decelera da sola. Registra a 50 Hz t, angolo comandato, corrente servo (INA219 0x40 reg 0x01), velocita' ruota
(/tmp/encoder_wheel_cum, stesso Encoder del limiter v3). GPIO12: prende il lock del limiter v3 (se occupato NON tocca il pin).
Stop: Ctrl-C -> 0 gradi con impulso lungo 1,5 s + pin in ingresso. Corrente >1,5 A per >0,3 s -> 0 e stop.
Mai LOW continuo, mai 330 Hz, mai oltre 50 gradi (controllo anche dentro il backend).
v2 (veto 1/3 banco-critico): sfiora dalla corrente CON PWM attivo; riferimento decel(v) a 0 gradi (inizio e fine passata, confronto a pari
velocita'); piu' salite + discesa (isteresi), sfiora = mediana; Ctrl-C al prompt non tocca il pin."""
import argparse
import csv
import os
import signal
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "autonomous"))

ANG_TETTO_ASSOLUTO = 50.0       # mai oltre (#001: a 60 stallo servo >= 3,2 A)
ANG_MAX_PROVA = 30.0            # tetto di questa prova
I_MAX_MA = 1500.0
I_MAX_S = 0.3
INA_MUTO_S = 0.5
STEP_S = 2.0
LIBERO_S = 0.5
RILASCIO_S = 1.5                # da 50 gradi 0,7 s non bastano (lezione 24/11)
DT = 0.02                       # 50 Hz
V_START = 3.3                   # m/s ~ 11,9 km/h (Daniele pedala 10-13)
MAX_PASSI = 80
MIN_PARZIALE_S = 1.2            # gradino interrotto dalla ruota lenta ma con >=1,2 s di dati: vale
V_MIN = 1.0                     # sotto: pausa, si rilancia la ruota
V_CALA = 0.25                   # calo dal picco = ha smesso di pedalare, ruota libera
SCARTO_INIZIO_S = 0.4           # transitorio servo + finestra della parabola dell'Encoder
CAMPI = ["t", "t_enc", "count", "v", "a_enc", "fresco", "ina_ma", "fase", "ang_cmd", "passo", "dir"]
N_SALITE = 2


class Stop(Exception):
    pass


# ---------------- backend veri (import hardware solo qui dentro) ----------------
class ServoVero:
    """Wrapper su speed_limiter_v3.hw.ServoLgpio: aggiunge il tetto 50 gradi e il rilascio lungo."""

    def __init__(self):
        from speed_limiter_v3.hw import ServoLgpio
        self.s = ServoLgpio()

    def pwm(self, angolo):
        if not (0.0 <= angolo <= ANG_TETTO_ASSOLUTO):
            raise ValueError("angolo %r fuori 0..%g" % (angolo, ANG_TETTO_ASSOLUTO))
        self.s.pwm(float(angolo))

    def libera(self):
        self.s.libera()

    def chiudi(self):
        self.s.chiudi()


class SensoriVeri:
    """Solo INA219 ed encoder (non sveglia l'IMU: il bus lo passiamo noi)."""

    def __init__(self):
        import smbus2
        from speed_limiter_v3.hw import LettoreSensori
        self.l = LettoreSensori(bus=smbus2.SMBus(1))

    def enc(self):
        return self.l.enc()

    def ina_ma(self):
        return self.l.ina_ma()


# ---------------- logica ----------------
def fit_decel(punti):
    """Pendenza minimi quadrati di v(t) -> decel (m/s2, positiva = rallenta). punti=[(t,v)]. None se pochi."""
    if len(punti) < 10:
        return None
    t0 = punti[0][0]
    xs = [p[0] - t0 for p in punti]
    ys = [p[1] for p in punti]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-6:
        return None
    return -sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def _segmenti(righe, fasi):
    """Raggruppa righe consecutive con stessa (passo, dir, fase, ang) -> liste (ordinate nel tempo)."""
    seg, ult = [], None
    for r in righe:
        if r["fase"] not in fasi:
            ult = None
            continue
        k = (r["passo"], r.get("dir", ""), r["fase"], r["ang_cmd"] if r["fase"] in ("pwm", "libero") else 0.0)
        if k != ult:
            seg.append((k, []))
            ult = k
        seg[-1][1].append(r)
    return seg


def _dec_v(rr):
    """(decel, v media) sul segmento, scartando dal momento in cui la ruota viene RILANCIATA (v risale >0,3 m/s sopra il minimo)."""
    t0 = rr[0]["t"]
    pt, vmin = [], None
    for r in rr:
        if not r["fresco"] or r["t"] - t0 < SCARTO_INIZIO_S:
            continue
        vmin = r["v"] if vmin is None else min(vmin, r["v"])
        if r["v"] > vmin + 0.3:
            break
        pt.append((r["t"], r["v"]))
    return fit_decel(pt), (statistics.mean(p[1] for p in pt) if pt else None)


def modello_rif(righe):
    """Decel a ruota libera (0 gradi) in funzione della velocita': retta dec = c0 + c1*v sui segmenti rif/rif_fine (inizio e fine
    passata). Con un solo livello di velocita' -> costante. -> (funzione v->dec | None, punti)."""
    pts = []
    for k, rr in _segmenti(righe, ("rif", "rif_fine")):
        d, v = _dec_v(rr)
        if d is not None and v is not None:
            pts.append((v, d))
    if not pts:
        return None, pts
    vs = [p[0] for p in pts]
    if len(pts) >= 3 and max(vs) - min(vs) >= 0.5:
        mv, md = sum(vs) / len(vs), sum(p[1] for p in pts) / len(pts)
        c1 = sum((p[0] - mv) * (p[1] - md) for p in pts) / sum((p[0] - mv) ** 2 for p in pts)
        c0 = md - c1 * mv
        return (lambda v: c0 + c1 * v), pts
    m = statistics.mean(p[1] for p in pts)
    return (lambda v: m), pts


def analizza(righe, soglia_dec=0.2, lavora_dec=(1.0, 2.0), min_ina_ma=30.0):
    """righe: dict del CSV grezzo. Sfiora (per ogni salita) = 1o angolo con delta decel (a pari velocita', vs modello a 0 gradi) > soglia
    per 2 gradini di fila; oppure 1o angolo con corrente CON PWM ATTIVO (mediana dopo 0,5 s) > corrente in aria (mediana gradini 1-3 gradi)
    + max(min_ina_ma, 5 MAD). Riassunto: mediana delle salite; discesa -> angolo di stacco e isteresi. Lavora = 1o angolo con delta >= 1, 2."""
    rif, pts_rif = modello_rif(righe)
    passi = []
    for (passo, dr, fase, ang), rr in _segmenti(righe, ("pwm", "libero")):
        if fase != "pwm":
            continue
        # il gradino = pwm + libero successivo con stesso (passo, dir, ang)
        ext = [r for r in righe if r["passo"] == passo and r.get("dir", "") == dr and r["fase"] in ("pwm", "libero") and r["ang_cmd"] == ang]
        d, v = _dec_v(ext)
        t0 = rr[0]["t"]
        ip = [r["ina_ma"] for r in rr if r["ina_ma"] is not None and r["t"] - t0 >= 0.5]
        il = [r["ina_ma"] for r in ext if r["fase"] == "libero" and r["ina_ma"] is not None and r["t"] - ext[0]["t"] >= STEP_S + 0.15]
        delta = None if (d is None or v is None or rif is None) else d - rif(v)
        passi.append({"passo": passo, "dir": dr, "ang": ang, "dec": d, "v_med": v, "delta": delta,
                      "ina_pwm": statistics.median(ip) if ip else None, "ina_libero": statistics.median(il) if il else None})
    # corrente in aria: gradini 1-3 gradi in salita, con PWM attivo
    aria = [p["ina_pwm"] for p in passi if 1.0 <= p["ang"] <= 3.0 and p["ina_pwm"] is not None and p["dir"].startswith("su")]
    ina_aria = statistics.median(aria) if aria else None
    mad = statistics.median([abs(x - ina_aria) for x in aria]) if aria else 0.0
    soglia_ina = None if ina_aria is None else ina_aria + max(min_ina_ma, 5 * mad)

    def due_di_fila(lst):
        for i in range(len(lst) - 1):
            if lst[i]["delta"] is not None and lst[i]["delta"] > soglia_dec and lst[i + 1]["delta"] is not None \
                    and lst[i + 1]["delta"] > soglia_dec:
                return lst[i]["ang"]
        return None
    su_dirs = sorted({p["dir"] for p in passi if p["dir"].startswith("su")})
    sfiora_dec, sfiora_ina, lavora = [], [], {lv: [] for lv in lavora_dec}
    for dr in su_dirs:
        lst = sorted([p for p in passi if p["dir"] == dr and True], key=lambda p: p["ang"])
        x = due_di_fila(lst)
        if x is not None:
            sfiora_dec.append(x)
        if soglia_ina is not None:
            y = next((p["ang"] for p in lst if p["ang"] > 3.0 and p["ina_pwm"] is not None and p["ina_pwm"] > soglia_ina), None)
            if y is not None:
                sfiora_ina.append(y)
        for lv in lavora_dec:
            z = next((p["ang"] for p in lst if p["delta"] is not None and p["delta"] >= lv), None)
            if z is not None:
                lavora[lv].append(z)
    stacco = []
    for dr in sorted({p["dir"] for p in passi if p["dir"].startswith("giu")}):
        lst = sorted([p for p in passi if p["dir"] == dr], key=lambda p: p["ang"])
        # angolo piu' basso con delta > soglia due gradini consecutivi verso l'alto = il freno smette di lavorare sotto di esso
        for i in range(len(lst) - 1):
            if lst[i]["delta"] is not None and lst[i]["delta"] > soglia_dec and lst[i + 1]["delta"] is not None \
                    and lst[i + 1]["delta"] > soglia_dec:
                stacco.append(lst[i]["ang"])
                break
    med = lambda l: statistics.median(l) if l else None
    return passi, {"corrente_in_aria_ma": ina_aria, "soglia_corrente_ma": soglia_ina,
                   "sfiora_da_decel": sfiora_dec, "sfiora_da_decel_mediana": med(sfiora_dec),
                   "sfiora_da_corrente": sfiora_ina, "sfiora_da_corrente_mediana": med(sfiora_ina),
                   "lavora_gradi_mediana": {lv: med(v) for lv, v in lavora.items()}, "stacco_discesa": stacco,
                   "isteresi_gradi": (None if not stacco or med(sfiora_dec) is None else med(stacco) - med(sfiora_dec)),
                   "rif_punti_v_dec": [(round(v, 2), round(d, 3)) for v, d in pts_rif], "soglia_dec": soglia_dec}


class Prova:
    def __init__(self, servo, sens, enc_cfg, csv_path, ora=time.monotonic, dorme=time.sleep, chiedi=input,
                 dire=print, max_gradi=ANG_MAX_PROVA, passo_gradi=1.0, stop_delta=2.5, salite=N_SALITE, discesa=True):
        from speed_limiter_v3.fonti import Encoder
        if max_gradi > ANG_MAX_PROVA or max_gradi <= 0:
            raise ValueError("max_gradi %r: tetto di questa prova %g (assoluto %g)" % (max_gradi, ANG_MAX_PROVA, ANG_TETTO_ASSOLUTO))
        self.servo, self.sens, self.ora, self.dorme, self.chiedi, self.dire = servo, sens, ora, dorme, chiedi, dire
        self.enc = Encoder(enc_cfg)
        self.max_gradi, self.passo_gradi, self.stop_delta = max_gradi, passo_gradi, stop_delta
        self.salite, self.discesa, self.dir = salite, discesa, ""
        self.f = open(csv_path, "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(CAMPI)
        self.righe = []
        self.run = True
        self.passo = 0
        self.fallimenti = {}
        self.t_over = None
        self.t_ina_ok = None
        self.t_enc = None
        self.count = None
        self.ang_corrente = 0.0     # ultimo angolo comandato (la posizione resta li' a pin libero)

    # --- un ciclo a 50 Hz ---
    def tick(self, fase, ang):
        if not self.run:
            raise Stop("Ctrl-C")
        t = self.ora()
        e = self.sens.enc()
        if e is not None:
            self.t_enc, self.count = e
            self.enc.aggiorna(t, e)
        ina = self.sens.ina_ma()
        if ina is None:
            if self.t_ina_ok is not None and t - self.t_ina_ok > INA_MUTO_S:
                raise Stop("INA219 muto da >%.1f s: senza corrente non si prosegue" % INA_MUTO_S)
        else:
            self.t_ina_ok = t
            if ina > I_MAX_MA:
                self.t_over = self.t_over if self.t_over is not None else t
                if t - self.t_over > I_MAX_S:
                    raise Stop("corrente servo %.0f mA > %.0f per >%.1f s" % (ina, I_MAX_MA, I_MAX_S))
            else:
                self.t_over = None
        r = {"t": round(t, 4), "t_enc": self.t_enc, "count": self.count, "v": round(self.enc.v, 4),
             "a_enc": round(self.enc.a, 3), "fresco": int(self.enc.fresco(t)), "ina_ma": None if ina is None else round(ina, 1),
             "fase": fase, "ang_cmd": ang, "passo": self.passo, "dir": self.dir}
        self.righe.append(r)
        self.w.writerow([r[k] for k in CAMPI])
        self.dorme(DT)
        return r

    def tieni(self, fase, ang, durata, pwm=False, fino_a_vmin=False):
        """Tiene durata secondi (ticks 50 Hz). pwm=True: il segnale PWM e' mantenuto. -> True se completo."""
        if pwm:
            self.servo.pwm(ang)
            self.ang_corrente = ang
        t0 = self.ora()
        n = max(1, int(round(durata / DT)))
        for _ in range(n):
            r = self.tick(fase, ang)
            if fino_a_vmin and r["fresco"] and r["v"] < V_MIN:
                return False
        return True

    def rilascia(self, fase="rilascio"):
        """0 gradi con impulso lungo 1,5 s, poi pin in ingresso. Usato anche in emergenza (senza alzare eccezioni di stop)."""
        self.servo.pwm(0.0)
        self.ang_corrente = 0.0
        t_fine = self.ora() + RILASCIO_S
        while self.ora() < t_fine:
            try:
                self.run, run_prec = True, self.run     # il rilascio NON si ferma col Ctrl-C
                self.tick(fase, 0.0)
                self.run = run_prec
            except Stop:
                self.dorme(DT)
        self.servo.libera()

    def attendi_giro(self):
        """Aspetta che Daniele porti la ruota >= V_START e poi smetta (calo V_CALA dal picco)."""
        self.dire(">>> PEDALA fino a ~%.0f km/h, poi SMETTI e lascia girare la ruota libera." % (V_START * 3.6))
        picco = 0.0
        sali = False
        while True:
            r = self.tick("attesa", 0.0)
            if not r["fresco"]:
                continue
            if r["v"] >= V_START:
                sali = True
            if sali:
                picco = max(picco, r["v"])
                if r["v"] <= picco - V_CALA:
                    self.dire("ruota libera rilevata (picco %.1f m/s = %.1f km/h): parto" % (picco, picco * 3.6))
                    return picco

    def _riferimento(self, fase):
        """Gradino a 0 gradi (pin libero), ruota libera: serve a costruire decel(v) a freno aperto."""
        return self.tieni(fase, 0.0, STEP_S, fino_a_vmin=False)

    def scala(self, angoli, dir_, prec0, sali):
        """Scala di gradini (lista di angoli, nell'ordine di percorrenza) in piu' passate. prec0 = angolo gia' provato a cui riposizionarsi
        alla prima passata (None = parti da 0). Ritorna l'ultimo angolo completato (o None)."""
        i, ultimo, self.dir = 0, None, dir_
        while i < len(angoli):
            self.passo += 1
            if self.passo > MAX_PASSI:
                raise Stop("troppi passi (%d): mi fermo" % MAX_PASSI)
            self.attendi_giro()
            self._riferimento("rif")
            prec = angoli[i - 1] if i > 0 else prec0
            if prec is not None:       # riposizionamento su un angolo GIA' provato (ruota in moto): mai un angolo nuovo di colpo
                self.tieni("ripos", prec, 1.0, pwm=True)
                self.servo.libera()
            fine = False
            while i < len(angoli):
                ang = angoli[i]
                n0 = len(self.righe)
                ok = self.tieni("pwm", ang, STEP_S, pwm=True, fino_a_vmin=True)
                self.servo.libera()          # il pin va libero SOLO a fine gradino (la corrente utile e' quella con PWM attivo)
                if ok:
                    ok = self.tieni("libero", ang, LIBERO_S, fino_a_vmin=True)
                troncato = not ok
                if troncato and (len(self.righe) - n0) * DT < MIN_PARZIALE_S:
                    self.fallimenti[(dir_, ang)] = self.fallimenti.get((dir_, ang), 0) + 1
                    n = self.fallimenti[(dir_, ang)]
                    self.dire("ruota sotto %.1f m/s dopo <%.1f s a %g gradi (tentativo %d): rilascio" % (V_MIN, MIN_PARZIALE_S, ang, n))
                    if n >= 2:
                        if sali:
                            self.dire("la ruota si ferma presto anche rilanciata: freno gia' forte a %g gradi, fine salita" % ang)
                            fine, i = True, len(angoli)
                        else:
                            self.dire("angolo %g saltato in discesa (ruota troppo lenta con freno forte)" % ang)
                            i += 1
                    break
                rr = self.righe[n0:]
                d, v = _dec_v(rr)
                rif, _ = modello_rif(self.righe)
                ina = [r["ina_ma"] for r in rr if r["fase"] == "pwm" and r["ina_ma"] is not None and r["t"] - rr[0]["t"] >= 0.5]
                delta = None if (d is None or v is None or rif is None) else d - rif(v)
                self.dire("%s %4.1f gradi: dec %s m/s2 a %s m/s, delta %s, I_pwm %s mA" % (
                    dir_, ang, "n/d" if d is None else "%.2f" % d, "n/d" if v is None else "%.1f" % v,
                    "n/d" if delta is None else "%+.2f" % delta, "n/d" if not ina else "%.0f" % statistics.median(ina)))
                ultimo = ang
                i += 1
                if sali and delta is not None and delta >= self.stop_delta:
                    self.dire("decelerazione forte (>= %.1f sopra il riferimento): fine salita" % self.stop_delta)
                    fine, i = True, len(angoli)
                    break
                if troncato:
                    self.dire("(gradino troncato: ruota scesa sotto %.1f m/s, dati validi)" % V_MIN)
                    break
            self.rilascia()
            # riferimento di FINE passata: freno a 0, pin libero, ruota che sta rallentando (velocita' bassa del modello decel(v))
            if self.enc.fresco(self.ora()) and self.enc.v > 0.6:
                self.tieni("rif_fine", 0.0, STEP_S)
            if not fine and i < len(angoli):
                self.dire("--- passata %d finita, freno a 0. Prossimo angolo: %g gradi ---" % (self.passo, angoli[i]))
        return ultimo

    def esegui(self):
        self.dire("Rilascio a 0 gradi (impulso 1,5 s) e misura corrente a vuoto 2 s...")
        self.passo = 0
        self.dir = "vuoto"
        self.rilascia()
        self.tieni("vuoto", 0.0, 2.0)
        n = int(round(self.max_gradi / self.passo_gradi))
        salita = [round((k + 1) * self.passo_gradi, 3) for k in range(n)]
        amax_tutte = []
        for k in range(1, self.salite + 1):
            self.dire("=== SALITA %d di %d ===" % (k, self.salite))
            amax = self.scala(salita, "su%d" % k, None, True)
            if amax is not None:
                amax_tutte.append(amax)
        if self.discesa and amax_tutte:
            amax = max(amax_tutte)
            self.dire("=== DISCESA da %g gradi a 1 (isteresi) ===" % amax)
            giu = [a for a in reversed(salita) if a < amax - 1e-9]
            self.scala(giu, "giu1", amax, False)

    def chiudi(self):
        self.f.flush()
        self.f.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-gradi", type=float, default=ANG_MAX_PROVA)
    ap.add_argument("--out", default=None, help="cartella dati (default /data/logging/freno_contatto/<ts>)")
    ap.add_argument("--salite", type=int, default=N_SALITE, help="numero di salite (mediana dello sfiora), default 2")
    ap.add_argument("--senza-discesa", action="store_true")
    ap.add_argument("--analizza", help="rianalizza un CSV grezzo e stampa, senza toccare nulla")
    a = ap.parse_args(argv)
    if a.analizza:
        righe = []
        with open(a.analizza) as f:
            for r in csv.DictReader(f):
                righe.append({"t": float(r["t"]), "v": float(r["v"]), "fresco": int(r["fresco"]),
                              "ina_ma": None if r["ina_ma"] == "" else float(r["ina_ma"]), "fase": r["fase"],
                              "ang_cmd": float(r["ang_cmd"]), "passo": int(r["passo"]), "dir": r.get("dir", "")})
        stampa_analisi(*analizza(righe))
        return 0
    if a.max_gradi > ANG_MAX_PROVA:
        print("max-gradi %g oltre il tetto della prova (%g)" % (a.max_gradi, ANG_MAX_PROVA))
        return 2
    from speed_limiter_v3.controllo import carica_soglie
    from speed_limiter_v3.lock_gpio12 import LockError, acquisisci_lock
    cfg = carica_soglie()
    try:
        lock = acquisisci_lock()
    except LockError as e:
        print("GPIO12 occupato (limiter/master ancora attivi?): %s. NON tocco il pin. Segui il protocollo (fermare il master)." % e)
        return 3
    out = a.out or time.strftime("/data/logging/freno_contatto/%Y%m%d_%H%M%S")
    os.makedirs(out, exist_ok=True)
    sens = SensoriVeri()                       # solo letture: nessun movimento
    i0, e0 = sens.ina_ma(), sens.enc()
    print("Letture iniziali: INA219 %s mA, encoder %s" % ("MUTO" if i0 is None else "%.0f" % i0, e0))
    if i0 is None:
        print("INA219 non risponde: senza corrente non si parte. NON tocco il pin.")
        lock.close()
        return 4
    print("""
PRIMA DEL MOTORE (servo freno, GPIO12):
  Posizione: il servo NON ha feedback di posizione. Atteso: freno a 50 gradi (parcheggio del master) o a 0.
  Direzione: il primo movimento e' un RILASCIO a 0 gradi (impulso 1,5 s). Poi %d salite di gradini da 1 grado verso il freno,
  da 1 a %g gradi, poi %s, mai oltre 50. Ruota posteriore SOLLEVATA, bici sul cavalletto, nessuno vicino alla ruota.
  Stop: Ctrl-C (dopo il 'vai') = 0 gradi + pin libero. Corrente > %.0f mA per > %.1f s = stop automatico.""" % (
        a.salite, a.max_gradi, "nessuna discesa" if a.senza_discesa else "discesa fino a 0", I_MAX_MA, I_MAX_S))
    try:
        risp = input("Scrivi esattamente  vai  per cominciare (altro = esco): ").strip()
    except (KeyboardInterrupt, EOFError):
        risp = ""
    if risp != "vai":
        print("\nniente 'vai': esco senza toccare il freno")
        lock.close()
        return 1
    servo = ServoVero()
    p = Prova(servo, sens, cfg["encoder"], os.path.join(out, "grezzo.csv"), max_gradi=a.max_gradi, salite=a.salite,
              discesa=not a.senza_discesa)
    signal.signal(signal.SIGINT, lambda *_: setattr(p, "run", False))    # handler SOLO dopo il vai
    signal.signal(signal.SIGTERM, lambda *_: setattr(p, "run", False))
    codice = 0
    try:
        p.esegui()
    except Stop as e:
        print("STOP: %s" % e)
        codice = 1
    except Exception as e:                     # qualunque errore: si rilascia
        print("ERRORE: %r" % e)
        codice = 1
    finally:
        try:
            p.rilascia("rilascio_fine")
        finally:
            p.chiudi()
            servo.chiudi()
            lock.close()
    righe = p.righe
    passi, riass = analizza(righe)
    stampa_analisi(passi, riass)
    return codice


def stampa_analisi(passi, riass):
    print("\nCURVA gradi -> decel a pari velocita' (ruota SOLLEVATA: su strada la decel per grado sara' diversa, inerzia diversa)")
    f = lambda x, fm: "n/d" if x is None else fm % x
    for p in sorted(passi, key=lambda p: (p["dir"], p["passo"], p["ang"])):
        print("%-5s passata %d  %4.1f gradi  dec %s  v %s  delta %s  I_pwm %s  I_libero %s" % (
            p["dir"], p["passo"], p["ang"], f(p["dec"], "%.2f"), f(p["v_med"], "%.1f"), f(p["delta"], "%+.2f"),
            f(p["ina_pwm"], "%.0f"), f(p["ina_libero"], "%.0f")))
    print("RIASSUNTO:", riass)


if __name__ == "__main__":
    sys.exit(main())

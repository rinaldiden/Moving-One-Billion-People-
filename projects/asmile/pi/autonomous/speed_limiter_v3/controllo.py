"""Loop UNICO di controllo: leggi encoder -> v,a -> anti-impuntata -> decisione -> comando servo, tutto in passo().
Niente thread separato che comanda il freno. Nessun import hardware (lgpio/smbus/serial sono solo in hw.py)."""
import math
import os

from .fonti import Arbitro, Encoder, Fusione, ImuLong, Campione, sanifica_velocita
from .freno import (TETTO_ASSOLUTO, AntiImpuntata, GuardiaIna, ImpulsoServo, Rampa, Regolatore)
from .validazione import SogliaError, leggi

TETTO_FALLBACK_MAX = 15.0       # gradi: con GPS/BLE come fonte (encoder non usabile) mai oltre
LOOP_LENTO_S = 0.06             # ciclo oltre 60 ms (deve essere 20): niente aumenti del freno
CONFIG_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                              "config", "soglie_speed_limiter_v3.json")


def carica_soglie(path=None):
    """Legge e VALIDA tutto il file soglie (validazione.py). File mancante/corrotto/fuori limiti = SogliaError, mai default."""
    return leggi(path or CONFIG_DEFAULT)


class Controllo:
    def __init__(self, cfg, backend_servo, log_eventi=None):
        self.cfg = cfg
        self.enc = Encoder(cfg["encoder"])
        self.imu = ImuLong(cfg["imu"], cfg["anti_impuntata"], cfg["fallback"]["imu_scala_vs_enc"])
        self.fus = Fusione(cfg["fusione_gps_imu"])
        self.arb = Arbitro(cfg, cfg["imu"], self.enc, self.imu, self.fus)
        self.reg = Regolatore(cfg)
        self.rampa = Rampa(cfg["freno"])
        self.servo = ImpulsoServo(backend_servo, cfg["freno"])
        self.ina = GuardiaIna(cfg["ina219"])
        self.anti = AntiImpuntata(cfg["anti_impuntata"], cfg["freno"]["tetto_deg"])
        self.t_prec = None
        self._t_fermo = None
        self.log_eventi = log_eventi or (lambda *a: None)
        self._n_eventi_arb = 0
        self.imu_ever = False
        self.dati_scartati = {"gps": 0, "ble": 0}
        self.t_inizio = None
        self._t_rilascio_alto = None

    def passo(self, c: Campione):
        t = c.t
        if self.t_inizio is None:
            self.t_inizio = t
        dt_vero = 0.02 if self.t_prec is None else t - self.t_prec
        dt = max(1e-3, min(0.2, dt_vero))
        self.t_prec = t
        cfg = self.cfg

        # 1) encoder
        self.enc.aggiorna(t, c.enc)
        # bici ferma da almeno 1 s -> ricalibra riposo/bias IMU
        if self.enc.fresco(t) and self.enc.v < 0.05:
            self._t_fermo = t if self._t_fermo is None else self._t_fermo
        else:
            self._t_fermo = None
        fermo = self._t_fermo is not None and t - self._t_fermo >= 1.0
        # 2) IMU + fusione GPS/BLE (dati esterni sanificati: finiti e 0-15 m/s, altrimenti ignorati)
        self.imu.aggiorna(t, c.imu, fermo)
        imu_ok = self.imu.viva(t)
        self.fus.predici(t, self.imu.a_avanti if imu_ok else 0.0)
        vmax = cfg["fusione_gps_imu"]["v_max_valida_ms"]
        try:
            if c.gps is not None and bool(c.gps[1]):
                vg = sanifica_velocita(c.gps[0], vmax)
                if vg is None:
                    self.dati_scartati["gps"] += 1
                else:
                    self.fus.misura(t, vg, "gps")
        except (TypeError, IndexError, ValueError):
            self.dati_scartati["gps"] += 1
        if c.ble is not None:
            vb = sanifica_velocita(c.ble, vmax)
            if vb is None:
                self.dati_scartati["ble"] += 1
            else:
                self.fus.misura(t, vb, "ble")
        if imu_ok and self.enc.fresco(t) and not self.arb.enc_implausibile:
            self.fus.suggerisci_bias(t, self.imu.a_avanti, self.enc.a)
        # 3) fonte + v, a
        v, a, fonte = self.arb.stato(t)
        while self._n_eventi_arb < len(self.arb.eventi):
            self.log_eventi(*self.arb.eventi[self._n_eventi_arb])
            self._n_eventi_arb += 1
        dec = -a if a is not None else 0.0
        # 4) anti-impuntata (sopra tutto)
        nuovo, no_aum, su_max, cap_anti = self.anti.passo(t, v, self.imu, self.rampa.angolo)
        rilascia = nuovo is not None
        if rilascia:                       # IMMEDIATO, stesso ciclo: qualche grado, non per forza 0
            self.rampa.angolo = nuovo
        # 5) decisione
        target = self.reg.passo(v, a, self.rampa.angolo, dt)
        if c.emergenza:
            target = TETTO_ASSOLUTO
        # 6) tetti
        fr = cfg["freno"]
        tetto = min(fr["tetto_deg"], TETTO_ASSOLUTO)
        motivi = []
        avvisi = []
        if c.emergenza:
            avvisi.append("emergenza")
        elif fonte in ("GPS_IMU", "BLE_IMU", "IMU_SOLO"):
            # redteam 23/11: una fonte di riserva che mente non deve poter fermare la bici: al massimo 15 gradi
            tetto = min(tetto, cfg["fallback"]["tetto_deg"], TETTO_FALLBACK_MAX)
        if dt_vero > LOOP_LENTO_S:
            # loop lento (CPU piena, I2C bloccato): l'anti-impuntata vede peggio -> niente aumenti, avviso visibile
            tetto = min(tetto, self.rampa.angolo)
            motivi.append("loop_lento")
            avvisi.append("loop lento: %.0f ms" % (dt_vero * 1000))
        if not imu_ok:
            # DECISIONE PER DANIELE: IMU morta = anti-impuntata cieca -> fuori emergenza tetto 0 (rilascio); in emergenza 25
            tetto = min(tetto, fr["tetto_imu_morta_emergenza_deg"] if c.emergenza else fr["tetto_imu_morta_deg"])
            motivi.append("imu_morta")
            avvisi.append("IMU morta/congelata: " + (self.imu.motivo_scarto or "nessun dato"))
        if cap_anti is not None:
            tetto = min(tetto, cap_anti)
        cap_ina = self.ina.passo(t, c.ina_ma, self.servo.fermo_da(t), self.rampa.angolo)
        if cap_ina is not None:
            tetto = min(tetto, cap_ina)
            motivi.append("ina")
        if self.ina.assente:
            avvisi.append("INA219 assente: guardia corrente spenta")
        if self.arb.avviso_failopen:
            avvisi.append("fail-open: velocita' ferma/ignota con bici che vibra e nessun GPS/BLE")
        if self.enc.indietro:
            avvisi.append("retromarcia")
        if self.arb.enc_implausibile:
            avvisi.append("encoder non plausibile")
        if no_aum:
            target = min(target, self.rampa.angolo)
        if rilascia:
            target = min(target, self.rampa.angolo)
            motivi.append("anti_impuntata")
        elif no_aum:
            motivi.append("ripresa_attesa")
        angolo = self.rampa.passo(target, tetto, dt, su_max, self.reg.livello == "sopra15" or c.emergenza)
        # 7) comando servo: stesso ciclo
        self.servo.tick(t, angolo)
        # 8) guardia di rilascio (24/11): comandato 0, impulso finito, ma il servo assorbe ancora > ma_rilascio_max per
        # rilascio_tempo_s -> il freno NON si e' aperto: nuovo impulso lungo a 0 e avviso visibile.
        gi = cfg["ina219"]
        if (self.servo.ultimo == 0.0 and not self.servo.attivo and c.ina_ma is not None and math.isfinite(c.ina_ma)
                and c.ina_ma > gi["ma_rilascio_max"]):
            if self._t_rilascio_alto is None:
                self._t_rilascio_alto = t
            elif t - self._t_rilascio_alto >= gi["rilascio_tempo_s"]:
                self.servo.riprova_zero(t)
                self._t_rilascio_alto = None
                avvisi.append("freno non si apre: %.0f mA a 0 gradi, nuovo impulso lungo a 0 (%d)"
                              % (c.ina_ma, self.servo.n_riprova_zero))
        else:
            self._t_rilascio_alto = None
        if self.servo.n_riprova_zero:
            motivi.append("riprova_zero")
            if self.servo.n_riprova_zero >= 3:
                avvisi.append("FRENO NON SI APRE: %d impulsi di rilascio ripetuti" % self.servo.n_riprova_zero)
        return {
            "t": t, "fonte": fonte, "v": v, "a": a, "dec": dec, "v_enc": self.enc.v, "a_enc": self.enc.a,
            "enc_fresco": self.enc.fresco(t), "v_fus": self.fus.v, "sigma_v": self.fus.sigma_v,
            "dec_imu": self.imu.dec, "d03": self.imu.d03, "imu_ok": imu_ok,
            "frena": self.reg.frena, "livello": self.reg.livello, "a_des": self.reg.a_des,
            "target": target, "angolo": angolo, "tetto": tetto, "rilascia_ora": rilascia, "bloccato": no_aum,
            "motivi": ",".join(motivi), "emergenza": c.emergenza, "avvisi": avvisi, "ina_ma": c.ina_ma,
        }

    def chiudi(self):
        self.servo.chiudi()

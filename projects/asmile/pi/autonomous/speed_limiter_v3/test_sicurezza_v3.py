"""Test dei punti di asmile-sicurezza (BLOCK 1-7 + non bloccanti). Dalla cartella projects/asmile:
python3 -m pytest pi/autonomous/speed_limiter_v3/ -q"""
import copy
import json
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from speed_limiter_v3 import hw, servizio                                   # noqa: E402
from speed_limiter_v3.controllo import carica_soglie                         # noqa: E402
from speed_limiter_v3.fonti import Campione, ImuLong, sanifica_velocita      # noqa: E402
from speed_limiter_v3.freno import GuardiaIna, Rampa                         # noqa: E402
from speed_limiter_v3.scenari import con_guasto, nuovo                       # noqa: E402
from speed_limiter_v3.sim import Guasti, ServoFinto                          # noqa: E402
from speed_limiter_v3.validazione import LIMITI, SogliaError, leggi, valida  # noqa: E402

CFG = carica_soglie()
QUI = os.path.dirname(os.path.abspath(__file__))


def mut(path, valore):
    c = copy.deepcopy(CFG)
    d = c
    parti = path.split(".")
    for p in parti[:-1]:
        d = d[p]
    if valore == "__DEL__":
        del d[parti[-1]]
    else:
        d[parti[-1]] = valore
    return c


# ---------- 1. validazione completa del file soglie ----------
@pytest.mark.parametrize("path,val", [
    ("anti_impuntata.rilascio_gradi", 0), ("anti_impuntata.dec_imu_min_ms2", 99), ("imu.morta_dopo_s", 1e9),
    ("freno.rampa_su_deg_s", 1e6), ("freno.rampa_giu_deg_s", 0.1), ("freno.tetto_deg", 51), ("freno.tetto_deg", -1),
    ("freno.uscita_tieni_s", 0.2), ("anti_impuntata.fermo_s", 1e6), ("encoder.m_per_count", 0.0),
    ("ina219.ma_fermo_max", 1e9), ("anti_impuntata.rilascio_gradi", float("nan")), ("freno.k_anello_deg_s_per_ms2", float("inf")),
    ("anti_impuntata.finestra_s", "0.3"), ("anti_impuntata.finestra_s", True), ("anti_impuntata.finestra_s", None),
    ("anti_impuntata.rilascio_gradi", "__DEL__"), ("imu.vibr_moto_g", "__DEL__"), ("velocita.zona_inizio_kmh", 16.0),
    ("decel_obiettivo_ms2.normale", 1.2), ("encoder.verso_avanti", 0), ("anti_impuntata.tetto_precoce.attivo", 1),
    ("anti_impuntata.nuova_soglia_sconosciuta", 1.0),
])
def test_file_soglie_cattivo_rifiutato(path, val):
    with pytest.raises(SogliaError):
        valida(mut(path, val))


def test_file_soglie_mancante_corrotto_nan(tmp_path):
    with pytest.raises(SogliaError):
        leggi(str(tmp_path / "non_esiste.json"))
    p = tmp_path / "rotto.json"
    p.write_text("{ non json")
    with pytest.raises(SogliaError):
        leggi(str(p))
    testo = open(os.path.join(QUI, "..", "..", "..", "config", "soglie_speed_limiter_v3.json")).read()
    p2 = tmp_path / "nan.json"
    p2.write_text(testo.replace('"rilascio_gradi": 8.0', '"rilascio_gradi": NaN'))
    with pytest.raises(SogliaError):
        leggi(str(p2))
    p3 = tmp_path / "vuoto.json"
    p3.write_text("[]")
    with pytest.raises(SogliaError):
        leggi(str(p3))


def test_ogni_numero_del_file_ha_limiti():
    from speed_limiter_v3.validazione import _foglie
    num = [k for k, v in _foglie(CFG) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert all(k in LIMITI for k in num) and all(k in dict(_foglie(CFG)) for k in LIMITI)


def test_avvio_con_soglie_cattive_non_tocca_il_pin(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ServoLgpio creato: il pin e' stato toccato")
    monkeypatch.setattr(hw, "carica_soglie", lambda: (_ for _ in ()).throw(SogliaError("prova")))
    monkeypatch.setattr(hw, "ServoLgpio", boom)
    monkeypatch.setattr(hw, "scrivi_stato", lambda *a, **k: None)
    assert hw.main() == 2


# ---------- 2. ricalibrazione IMU ----------
def _imu_campione(ay=0.043, az=0.92, gx=-2.64, rum=0.0, rnd=None):
    r = rnd or np.random.default_rng(1)
    return (0.0, ay + rum * r.normal(), az + rum * r.normal(), gx, 0.0, 0.0)


def test_ricalibrazione_non_insegue_una_frenata_con_encoder_bloccato():
    # encoder bloccato a 0 (timestamp vivo) mentre la bici frena e vibra: riposo/bias non devono muoversi
    imu = ImuLong(CFG["imu"], CFG["anti_impuntata"], CFG["fallback"]["imu_scala_vs_enc"])
    r = np.random.default_rng(2)
    t = 0.0
    for i in range(500):
        t += 0.02
        imu.aggiorna(t, (0.0, 0.043 + 0.25 + 0.02 * r.normal(), 0.92 + 0.1 * r.normal(), -2.64 + 4.0, 0.0, 0.0), fermo=True)
    assert abs(imu.ay_riposo - 0.043) < 1e-9 and abs(imu.gx_bias + 2.64) < 1e-9


def test_ricalibrazione_ha_il_clamp():
    cfg = copy.deepcopy(CFG["imu"])
    cfg["recal_max_dev_ay_g"] = 0.01
    imu = ImuLong(cfg, CFG["anti_impuntata"], 1.5)
    t = 0.0
    for i in range(1000):
        t += 0.02
        imu.aggiorna(t, (0.0, 0.043 + 0.04, 0.92, -2.64, 0.0, 0.0), fermo=True)         # fermo vero, ma lontano dal file
    assert imu.ay_riposo <= 0.043 + 0.01 + 1e-9


def test_ricalibrazione_si_fa_da_fermo_vero():
    imu = ImuLong(CFG["imu"], CFG["anti_impuntata"], 1.5)
    t = 0.0
    r = np.random.default_rng(5)
    for i in range(500):
        t += 0.02
        imu.aggiorna(t, (0.0, 0.065 + 0.001 * r.normal(), 0.92 + 0.001 * r.normal(), -2.7, 0.0, 0.0), fermo=True)
    assert 0.06 < imu.ay_riposo <= 0.065 + 1e-9 and imu.riposo_calibrato


def test_anti_impuntata_resta_viva_con_encoder_bloccato():
    r, ctl, s = con_guasto(Guasti(enc_bloccato_zero=(5, 40)), impuntate=(20.0,), durata=30, pend=0.9)
    assert any(x[0] > 19.9 for x in ctl.anti.scatti), "anti-impuntata cieca"
    assert abs(ctl.imu.ay_riposo - 0.043) < 0.01


# ---------- 3. IMU viva solo con dati veri ----------
def _viva_dopo(campioni, durata=2.0):
    imu = ImuLong(CFG["imu"], CFG["anti_impuntata"], 1.5)
    t = 0.0
    for c in campioni:
        t += 0.02
        imu.aggiorna(t, c, fermo=False)
    return imu, imu.viva(t)


def test_imu_congelata_non_e_viva():
    imu, viva = _viva_dopo([(0.0, 0.043, 0.92, -2.64, 0.0, 0.0)] * 100)
    assert not viva and "congelata" in imu.motivo_scarto


def test_imu_a_zero_o_nan_non_e_viva():
    assert not _viva_dopo([(0.0,) * 6] * 100)[1]
    assert not _viva_dopo([(float("nan"),) * 6] * 100)[1]
    assert not _viva_dopo([("x", None, 1, 2, 3, 4)] * 100)[1]
    assert not _viva_dopo([(0.0, 0.0, 0.3, 0, 0, 0)] * 0 + [(0.0, 0.05 + 0.001 * (i % 7), 0.35 + 0.001 * (i % 5), 0, 0, 0) for i in range(200)])[1]


def test_imu_vera_con_rumore_e_viva_e_un_calo_istantaneo_non_la_uccide():
    r = np.random.default_rng(3)
    camp = [(0.0, 0.043 + 0.02 * r.normal(), 0.92 + 0.1 * r.normal(), -2.64 + r.normal(), 0.0, 0.0) for _ in range(200)]
    camp[100] = (0.0, 0.05, 0.5, -2.6, 0.0, 0.0)          # |a| istantaneo 0.5 g: succede nelle impuntate vere (0.50-1.41 g)
    imu, viva = _viva_dopo(camp)
    assert viva


def test_hw_imu_congelata_dopo_5_cicli():
    class Bus:
        def read_i2c_block_data(self, a, r, n):
            return [0] * 14 if a == 0x68 else [0, 0]
    s = hw.LettoreSensori(bus=Bus(), enc_file="/non/esiste", ble_file="/non/esiste", gps_json="/non/esiste", emerg="/non/esiste")
    risultati = [s.imu() for _ in range(8)]
    assert all(x is not None for x in risultati[:4]) and all(x is None for x in risultati[4:])


def test_imu_morta_emergenza_tetto_25():
    cfg, s, ctl, b = nuovo(v0_kmh=8.0, pendenza_ms2=0.0)
    ang = []
    for i in range(2500):
        c = b.campione()
        c.imu = None
        c.emergenza = True
        ang.append(ctl.passo(c)["angolo"])
        b.passo(0.02, s.angolo)
    assert 20.0 < max(ang) <= CFG["freno"]["tetto_imu_morta_emergenza_deg"] + 1e-6


# ---------- 4. GPS / BLE sporchi ----------
@pytest.mark.parametrize("gps", [(float("nan"), True), (float("inf"), True), (None, True), ("x", True), (50.0, True),
                                 (-3.0, True), (1.0,), "garbage", (3.0, None), [], 12])
def test_gps_sporco_non_uccide_il_limiter(gps):
    cfg, s, ctl, b = nuovo(v0_kmh=12.0, pendenza_ms2=0.3)
    for i in range(300):
        c = b.campione()
        c.gps = gps if i % 5 == 0 else c.gps
        r = ctl.passo(c)
        b.passo(0.02, s.angolo)
        assert all(math.isfinite(x) for x in (r["angolo"], r["v_fus"], r["sigma_v"], r["dec_imu"]))
    assert math.isfinite(ctl.fus.v) and math.isfinite(ctl.fus.b)


@pytest.mark.parametrize("ble", [float("nan"), float("inf"), "abc", [1, 2], None, -5.0, 99.0, {}])
def test_ble_sporco_non_uccide_il_limiter(ble):
    cfg, s, ctl, b = nuovo(v0_kmh=12.0, pendenza_ms2=0.3)
    for i in range(300):
        c = b.campione()
        c.ble = ble
        r = ctl.passo(c)
        b.passo(0.02, s.angolo)
        assert math.isfinite(r["angolo"]) and math.isfinite(r["v_fus"])


def test_nan_non_resta_per_sempre_nel_filtro():
    cfg, s, ctl, b = nuovo(v0_kmh=12.0, pendenza_ms2=0.0)
    for i in range(100):
        c = b.campione()
        c.gps = (float("nan"), True)
        ctl.passo(c)
        b.passo(0.02, s.angolo)
    for i in range(200):
        c = b.campione()
        r = ctl.passo(c)
        b.passo(0.02, s.angolo)
    assert abs(r["v_fus"] - b.v) < 1.0


def test_parse_hw_gps_ble():
    assert hw.parse_gps('{"speed_ms": 3.5, "fix": true, "ts": 1}') == (3.5, True)
    for brutto in ('{"speed_ms": NaN}', 'null', '[1]', '{"speed_ms": "abc"}', '{"speed_ms": 99}', '', '{', '{"speed_ms": null}', '{"speed_ms": -1}'):
        assert hw.parse_gps(brutto) is None
    assert hw.parse_ble("4.2 ble") == 4.2
    for brutto in ("nan", "inf", "", "abc", None, "-2", "99"):
        assert hw.parse_ble(brutto) is None
    assert sanifica_velocita(15.0) == 15.0 and sanifica_velocita(15.1) is None


def test_lettore_sensori_con_file_sporchi(tmp_path):
    class Bus:
        def read_i2c_block_data(self, *a):
            raise OSError("i2c giu'")
    g = tmp_path / "gps.json"
    g.write_text('{"speed_ms": "x", "fix": true, "ts": 5}')
    b = tmp_path / "ble"
    b.write_text("nan")
    e = tmp_path / "enc"
    e.write_text("abc def")
    s = hw.LettoreSensori(bus=Bus(), enc_file=str(e), ble_file=str(b), gps_json=str(g), emerg=str(tmp_path / "no"))
    c = s.campione(1.0)
    assert c.gps is None and c.ble is None and c.enc is None and c.imu is None and c.ina_ma is None and not c.emergenza


# ---------- 5. un solo padrone di GPIO12 ----------
def test_flock_esclusivo(tmp_path):
    p = str(tmp_path / "gpio12.lock")
    a = hw.acquisisci_lock(p)
    with pytest.raises(hw.LockError):
        hw.acquisisci_lock(p)
    a.close()
    hw.acquisisci_lock(p).close()


def test_unit_systemd_v3():
    u = open(os.path.join(QUI, "..", "..", "..", "deploy", "speed_limiter_v3.service")).read()
    righe = [r.strip() for r in u.splitlines() if not r.strip().startswith("#")]
    assert "Conflicts=speed_limiter.service servofreno.service" in righe
    assert any(r.startswith("ExecStopPost=") and "porta_a_zero" in r for r in righe)
    assert "Restart=no" in righe and "KillSignal=SIGTERM" in righe


def test_avvio_con_lock_occupato_non_tocca_il_pin(monkeypatch, tmp_path):
    p = str(tmp_path / "l.lock")
    occupato = hw.acquisisci_lock(p)
    monkeypatch.setattr(hw, "acquisisci_lock", lambda path=p: hw.acquisisci_lock.__wrapped__(path)) if False else None
    orig = hw.acquisisci_lock
    monkeypatch.setattr(hw, "acquisisci_lock", lambda: orig(p))
    monkeypatch.setattr(hw, "ServoLgpio", lambda: (_ for _ in ()).throw(AssertionError("pin toccato")))
    monkeypatch.setattr(hw, "scrivi_stato", lambda *a, **k: None)
    assert hw.main() == 3
    occupato.close()


# ---------- 6. uscita e ciclo protetto ----------
class ServoSpia:
    def __init__(self):
        self.ev = []

    def pwm(self, a):
        self.ev.append(("pwm", a))

    def libera(self):
        self.ev.append(("libera",))

    def chiudi(self):
        self.ev.append(("chiudi",))


def test_uscita_tiene_zero_prima_di_liberare():
    sv = ServoSpia()
    trascorso = []
    servizio.chiudi_servo(sv, CFG["freno"]["uscita_tieni_s"], sleep=lambda s: (trascorso.append(s), sv.ev.append(("sleep", s))))
    assert sv.ev[0] == ("pwm", 0.0) and sv.ev[1][0] == "sleep" and sv.ev[1][1] >= 0.6 and sv.ev[2] == ("libera",)


def test_uscita_libera_anche_se_lo_sleep_fallisce():
    sv = ServoSpia()

    def boom(s):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        servizio.chiudi_servo(sv, 0.6, sleep=boom)
    assert ("libera",) in sv.ev


class SensFinto:
    def __init__(self, bici=None, errori=()):
        self.n = 0
        self.errori = set(errori)
        self.bici = bici

    def campione(self, t):
        self.n += 1
        if self.n in self.errori:
            raise RuntimeError("sensore rotto %d" % self.n)
        c = self.bici.campione()
        self.bici.passo(0.02, 0.0)
        return c


def test_ciclo_protetto_errore_isolato_non_ferma_e_avvisa(tmp_path):
    cfg, s, ctl, b = nuovo(v0_kmh=5.0, pendenza_ms2=0.0)
    log = []
    stato = str(tmp_path / "stato.json")
    t = [0.0]
    cod = servizio.esegui(ctl, SensFinto(b, errori=(50,)), s, [True], stato_path=stato, now=lambda: t.__setitem__(0, t[0] + 0.02) or t[0],
                          sleep=lambda x: None, log=log.append, max_cicli=200)
    assert cod == 0 and any("ERRORE nel ciclo" in x for x in log)
    assert json.load(open(stato))["stato"] in ("OK", "ATTENZIONE")


def test_ciclo_protetto_errori_di_fila_esce_a_zero_e_lo_dice(tmp_path):
    cfg, s, ctl, b = nuovo(v0_kmh=14.0, pendenza_ms2=0.5)
    log = []
    stato = str(tmp_path / "stato.json")
    sv = ServoSpia()
    ctl.rampa.angolo = 30.0
    t = [0.0]
    cod = servizio.esegui(ctl, SensFinto(b, errori=range(1, 100)), sv, [True], stato_path=stato,
                          now=lambda: t.__setitem__(0, t[0] + 0.02) or t[0], sleep=lambda x: None, log=log.append, max_cicli=100)
    st = json.load(open(stato))
    assert cod == 1 and st["stato"] == "CADUTO" and "NON ha il limite" in st["avvisi"][0]
    assert ("pwm", 0.0) in sv.ev and ctl.rampa.angolo == 0.0 and any("non riparte" in x for x in log)


def test_ciclo_protetto_eccezione_in_passo(tmp_path, monkeypatch):
    cfg, s, ctl, b = nuovo()
    monkeypatch.setattr(ctl, "passo", lambda c: 1 / 0)
    stato = str(tmp_path / "stato.json")
    t = [0.0]
    cod = servizio.esegui(ctl, SensFinto(b), s, [True], stato_path=stato, now=lambda: t.__setitem__(0, t[0] + 0.02) or t[0],
                          sleep=lambda x: None, log=lambda *a: None, max_cicli=50)
    assert cod == 1 and json.load(open(stato))["stato"] == "CADUTO"


# ---------- non bloccanti ----------
def test_retromarcia_non_conta_come_avanti():
    cfg, s, ctl, b = nuovo(v0_kmh=0.0, pendenza_ms2=0.0)
    k = CFG["encoder"]["m_per_count"]
    cum = 1_000_000.0
    out = []
    for i in range(300):
        cum -= 3.0 / k * 0.02                       # indietro a 3 m/s
        c = b.campione()
        c.enc = (i * 0.02, int(cum))
        out.append(ctl.passo(c))
        b.passo(0.02, 0.0)
    r = out[-1]
    assert r["v_enc"] == 0.0 and ctl.enc.indietro and "retromarcia" in r["avvisi"] and max(x["angolo"] for x in out) == 0.0


def test_encoder_che_inventa_velocita_senza_gps_e_smentito_dall_imu():
    cfg, s, ctl, b = nuovo(v0_kmh=0.0, pendenza_ms2=0.0)
    k = CFG["encoder"]["m_per_count"]
    cum = 0.0
    out = []
    for i in range(600):                              # bici ferma (IMU senza vibrazione), encoder dice 5 m/s, niente GPS
        cum += 5.0 / k * 0.02
        c = b.campione()
        c.enc = (i * 0.02, int(cum))
        c.gps = None
        out.append(ctl.passo(c))
        b.passo(0.02, 0.0)
    assert out[-1]["fonte"] == "FERMO_IMU" and any("IMU non vibra" in e[3] for e in ctl.eventi_log)
    assert max(x["angolo"] for x in out[200:]) < 25.0 and max(x["angolo"] for x in out[450:]) == 0.0   # frenata fantasma di ~1.5 s, poi rilascio


def test_encoder_fermo_con_bici_che_vibra_senza_gps_avvisa_fail_open():
    cfg, s, ctl, b = nuovo(v0_kmh=12.0, pendenza_ms2=0.0, resistenza=0.0)
    out = []
    for i in range(600):
        c = b.campione()
        c.enc = (i * 0.02, 0)                          # encoder bloccato a 0
        c.gps = None
        c.ble = None
        out.append(ctl.passo(c))
        b.passo(0.02, 0.0)
    assert any("AVVISO fail-open" in e[3] for e in ctl.eventi_log)
    assert any("fail-open" in a for a in out[-1]["avvisi"])


def test_tetto_che_scende_e_una_rampa_non_un_salto():
    r = Rampa(CFG["freno"])
    r.angolo = 40.0
    val = [r.passo(40.0, 0.0, 0.02) for _ in range(60)]
    d = np.abs(np.diff([40.0] + val)) / 0.02
    assert d.max() <= CFG["freno"]["rampa_tetto_deg_s"] + 1e-6 and val[-1] == 0.0 and val[0] > 38.0


def test_ina_assente_avviso_visibile():
    g = GuardiaIna(CFG["ina219"])
    for i in range(200):
        g.passo(i * 0.02, None, 10.0, 20.0)
    assert g.assente
    g.passo(5.0, 30.0, 10.0, 20.0)
    assert not g.assente
    cfg, s, ctl, b = nuovo(v0_kmh=5.0, pendenza_ms2=0.0)
    out = []
    for i in range(300):
        c = b.campione()
        c.ina_ma = None
        out.append(ctl.passo(c))
        b.passo(0.02, 0.0)
    assert any("INA219 assente" in a for a in out[-1]["avvisi"])


def test_hw_ina_senza_risposta_e_none_non_zero():
    class Bus:
        def read_i2c_block_data(self, a, r, n):
            if a == 0x40:
                raise OSError
            return [0] * 14
    s = hw.LettoreSensori(bus=Bus(), enc_file="/x", ble_file="/x", gps_json="/x", emerg="/x")
    assert s.ina_ma() is None

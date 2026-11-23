"""pytest: python3 -m pytest pi/autonomous/speed_limiter_v3/test_speed_limiter_v3.py  (dalla cartella projects/asmile)."""
import copy
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from speed_limiter_v3 import fonti, freno                                  # noqa: E402
from speed_limiter_v3.controllo import Controllo, carica_soglie            # noqa: E402
from speed_limiter_v3.fonti import Campione, Encoder                       # noqa: E402
from speed_limiter_v3.scenari import (comando_liscio, con_guasto, discesa_forte, jerk_decel,   # noqa: E402
                                      salto_max_v)
from speed_limiter_v3.sim import Guasti, ServoFinto, SimBici, esegui_sintetico   # noqa: E402

CFG = carica_soglie()
QUI = os.path.dirname(os.path.abspath(__file__))


def test_codice_di_controllo_non_importa_hardware():
    for m in ("controllo", "fonti", "freno", "sim", "scenari"):
        src = open(os.path.join(QUI, m + ".py")).read()
        assert "import lgpio" not in src and "import smbus" not in src and "import serial" not in src, m
    assert "lgpio" not in sys.modules


def test_tetto_50_nel_codice_e_nel_file():
    assert freno.TETTO_ASSOLUTO == 50.0 and freno.SERVO_HZ == 50
    brutto = copy.deepcopy(CFG)
    brutto["freno"]["tetto_deg"] = 60
    p = os.path.join(os.environ.get("TMPDIR", "/tmp"), "soglie_brutte.json")
    import json
    json.dump(brutto, open(p, "w"))
    with pytest.raises(ValueError):
        carica_soglie(p)
    r = freno.Rampa({**CFG["freno"], "tetto_deg": 50.0})
    for _ in range(20000):
        r.passo(80.0, 99.0, 0.02)
    assert r.angolo <= 50.0


def test_encoder_parabola_decel_costante():
    e = Encoder(CFG["encoder"])
    k = CFG["encoder"]["m_per_count"]
    v0, a = 4.0, -1.0
    for i in range(100):
        t = i * 0.02
        s = v0 * t + 0.5 * a * t * t
        e.aggiorna(t, (t, int(round(s / k))))
    assert abs(e.v - (v0 + a * 1.98)) < 0.05 and abs(e.a - a) < 0.1


def test_zona_avvicinamento_continua_senza_on_off():
    from speed_limiter_v3.freno import Regolatore
    r = Regolatore(CFG)
    prec = None
    for kmh in np.arange(10.0, 17.0, 0.1):
        r.passo(kmh / 3.6, 0.0, 10.0, 0.02)
        r.a_f = 0.0
        if prec is not None:
            assert abs(r.a_des - prec) < 0.2          # nessun salto
        prec = r.a_des
    r.passo(11.0 / 3.6, 0.0, 10.0, 0.02)
    assert r.a_des > 0 and r.livello in ("rilascio", "libero")
    r.passo(13.5 / 3.6, 0.0, 10.0, 0.02)
    assert -CFG["decel_obiettivo_ms2"]["normale"] < r.a_des < 0
    r.passo(15.0 / 3.6, 0.0, 10.0, 0.02)
    assert abs(r.a_des + CFG["decel_obiettivo_ms2"]["normale"]) < 0.1


def test_discesa_forte_riporta_a_15_dolce():
    r, ctl = discesa_forte(g=0.05)
    assert max(x["v_vera"] for x in r if x["t"] > 15) * 3.6 <= 15.0
    assert max(x["angolo"] for x in r) <= 50.0
    slew, inv = comando_liscio(r)
    assert slew <= CFG["freno"]["rampa_giu_deg_s"] + 1e-6 and inv == 0
    assert jerk_decel(r) <= 4.0


@pytest.mark.parametrize("g", [0.02, 0.12, 0.25])
def test_stabile_con_guadagni_diversi(g):
    r, _ = discesa_forte(g=g, pend=0.6, v0=11.0, durata=90)
    late = [x["v_vera"] * 3.6 for x in r if x["t"] > 40]
    assert max(late) < 15.0 and min(late) > 10.5
    assert comando_liscio(r)[1] <= 2


def test_impuntata_qualche_grado_poi_zero_poi_ripresa_dolce():
    r, ctl, s = con_guasto(Guasti(), impuntate=(20.0,), durata=40, pend=0.9)
    sc = ctl.anti.scatti
    assert sc, "l'anti-impuntata deve scattare"
    t0, prima, dopo = sc[0][0], sc[0][1], sc[0][2]
    assert prima > 8 and abs((prima - dopo) - CFG["anti_impuntata"]["rilascio_gradi"]) < 1e-9     # primo ciclo: 8 gradi
    ang = {round(x["t"], 2): x["angolo"] for x in r}
    assert ang[round(t0, 2)] == pytest.approx(dopo, abs=1e-6)                     # stesso ciclo
    assert min(ang[round(t0 + 0.02 * i, 2)] for i in range(1, 12)) == 0.0         # se il muso scende, fino a 0
    post = [x for x in r if t0 + 0.6 < x["t"] < t0 + 4.5]
    salita = max((b["angolo"] - a["angolo"]) / 0.02 for a, b in zip(post, post[1:]))
    assert salita <= CFG["anti_impuntata"]["ripresa_rampa_deg_s"] + 0.1           # ripresa lenta
    fermo = [x for x in r if t0 + 0.05 < x["t"] < t0 + CFG["anti_impuntata"]["fermo_s"]]
    assert max(x["angolo"] for x in fermo) <= 0.5                                  # niente salita nel fermo
    assert max(x["angolo"] for x in r if t0 + 1.5 < x["t"] < t0 + 3.9) <= CFG["anti_impuntata"]["ripresa_frazione"] * prima + 0.5


def test_impuntata_con_servo_a_zero_non_fa_danni():
    r, ctl, s = con_guasto(Guasti(), impuntate=(3.0,), durata=8, pend=-0.3, v0=8.0)
    assert max(x["angolo"] for x in r) == 0.0 and ctl.servo.n_impulsi == 0


def test_encoder_si_stacca_a_meta_frenata_senza_salti():
    r, ctl, s = con_guasto(Guasti(enc_stacca=(15, 25)))
    ev = [(round(e[0], 1), e[1], e[2]) for e in ctl.eventi_log]
    assert any(e[1] == "ENC" and e[2] == "GPS_IMU" for e in ev)
    assert any("non fresco" in e[3] for e in ctl.eventi_log)
    assert salto_max_v(r, 14.0, 17.0) < 0.5 and salto_max_v(r, 24.0, 27.0) < 0.5
    assert comando_liscio(r)[0] <= CFG["freno"]["rampa_giu_deg_s"] + 1e-6
    assert max(x["v_vera"] for x in r) * 3.6 < 16.5


def test_gps_senza_fix_passa_a_ble_poi_nessuna_fonte_rilascia():
    r, ctl, s = con_guasto(Guasti(enc_stacca=(10, 30), gps_senza_fix=(10, 30), ble_da_v=(12, 20)))
    fonti_viste = [e[2] for e in ctl.eventi_log]
    assert "BLE_IMU" in fonti_viste and "NESSUNA" in fonti_viste
    tardi = [x for x in r if 24 < x["t"] < 29]
    assert max(x["angolo"] for x in tardi) == 0.0                                   # cieco = nessun freno
    assert all(e[3] for e in ctl.eventi_log)                                         # ogni cambio ha un motivo


def test_imu_morta_tetto_zero_fuori_emergenza():
    r, ctl, s = con_guasto(Guasti(imu_morta=(10, 30)), pend=1.0)
    tardi = [x for x in r if 12 < x["t"] < 30]
    assert max(x["tetto"] for x in tardi) == 0.0
    assert max(x["angolo"] for x in tardi) == 0.0
    assert any("IMU morta" in a for x in tardi for a in x["avvisi"])


def test_ina_stallo_arretra_di_qualche_grado():
    r, ctl, s = con_guasto(Guasti(ina_stallo=(10, 30, 2500.0)), pend=1.0)
    assert ctl.ina.n_arretra >= 1
    a = [x["angolo"] for x in r if 10 < x["t"] < 14]
    assert max(a) - min(a) >= CFG["ina219"]["arretra_deg"] - 0.5


def test_encoder_bloccato_a_zero_riconosciuto_dal_gps():
    r, ctl, s = con_guasto(Guasti(enc_bloccato_zero=(15, 30)))
    assert any(e[1] == "ENC" and e[2] == "GPS_IMU" and "GPS" in e[3] for e in ctl.eventi_log)


def test_emergenza_sale_al_tetto_con_la_rampa():
    from speed_limiter_v3.scenari import nuovo
    cfg, s, ctl, b = nuovo(v0_kmh=8.0, pendenza_ms2=0.0)
    ang = []
    for i in range(1500):
        c = b.campione()
        c.emergenza = True
        r = ctl.passo(c)
        ang.append(r["angolo"])
        b.passo(0.02, s.angolo)
    d = np.diff(ang) / 0.02
    assert max(ang) <= 50.0
    fr = CFG["freno"]
    sotto = np.array(ang[:-1]) < fr["soglia_lenta_deg"]
    assert d[sotto].max() <= fr["rampa_su_sopra_vmax_deg_s"] + 1e-6 and d[~sotto].max() <= fr["rampa_su_oltre_soglia_deg_s"] + 1e-6


def test_servo_impulso_e_pin_libero():
    s = ServoFinto()
    srv = freno.ImpulsoServo(s, CFG["freno"])
    t = 0.0
    for a in list(np.linspace(0, 20, 40)) + [20.0] * 40:
        t += 0.02
        s.t = t
        srv.tick(t, a)
    assert s.pin_libero and s.eventi[-1][1] == "free"
    assert all(e[2] <= 50.0 for e in s.eventi)
    n_prima = len(s.eventi)
    for _ in range(100):
        t += 0.02
        srv.tick(t, 20.0)
    assert len(s.eventi) == n_prima                    # nessun twitch a angolo fermo


def test_replay_vero_le_due_impuntate_del_13_11():
    p = os.path.join(QUI, "..", "..", "..", "asmile-loggers/asmile-001/_sensors/sensors/sensors_20261113_145727.csv")
    if not os.path.exists(p):
        pytest.skip("CSV non presente")
    from speed_limiter_v3.prova_secco import replay
    d_ev = [(4000.9, 1.7), (4301.43, 2.22)]
    R = replay(p, CFG, i0=int(0), i1=None)
    t_sc = [x[0] for x in R["ctl"].anti.scatti]
    for t0, dur in d_ev:
        assert any(t0 - 1.0 <= t <= t0 + dur + 1.5 for t in t_sc), t0
    ep = R["ctl"].anti.episodi
    assert len(ep) <= 4                                       # quasi mai altrove (11 min in moto)


def test_encoder_morto_a_lungo_niente_va_e_vieni():
    r, ctl, s = con_guasto(Guasti(enc_bloccato_zero=(10, 80)), durata=90, pend=0.0, v0=13.0)
    cambi = [e for e in ctl.eventi_log if e[0] > 15 and e[1] in ("ENC", "GPS_IMU") and e[2] in ("ENC", "GPS_IMU")]
    assert len(cambi) <= 4, cambi


def test_gps_rumoroso_a_bici_ferma_non_frena():
    """Parcheggiata: encoder fermo, IMU senza vibrazione, GPS che inventa 8-30 km/h (visto nei log del 9-11/11)."""
    import random
    from speed_limiter_v3.scenari import nuovo
    cfg, s, ctl, b = nuovo(v0_kmh=0.0, pendenza_ms2=0.0)
    rnd = random.Random(3)
    ang = []
    for i in range(3000):
        b.v = 0.0
        c = b.campione()
        c.enc = (b.t, 0)
        c.gps = (rnd.uniform(2.0, 8.0), True) if i % 10 == 0 else None
        ang.append(ctl.passo(c)["angolo"])
        b.passo(0.02, 0.0)
    assert max(ang) == 0.0
    assert any(e[2] == "FERMO_IMU" for e in ctl.eventi_log)

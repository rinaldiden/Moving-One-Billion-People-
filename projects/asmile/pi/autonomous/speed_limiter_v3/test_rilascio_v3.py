"""24/11: il freno di #001 restava chiuso dopo il ritorno a 0 (impulso di 0,15 s, pin lasciato LOW, stallo 3,2 A).
Questi test fissano: ritorno a 0 col PWM acceso >= tieni_zero_s, corsa lunga = impulso lungo, guardia di rilascio su INA."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from speed_limiter_v3.controllo import Controllo, carica_soglie   # noqa: E402
from speed_limiter_v3.fonti import Campione                      # noqa: E402
from speed_limiter_v3.freno import ImpulsoServo                  # noqa: E402
from speed_limiter_v3.sim import ServoFinto                      # noqa: E402

CFG = carica_soglie()
DT = 0.02


def _gira(servo, angoli, t0=0.0):
    t = t0
    for a in angoli:
        servo.b.t = t
        servo.tick(t, a)
        t += DT
    return t


def test_ritorno_a_zero_tiene_il_pwm_almeno_tieni_zero():
    b = ServoFinto()
    s = ImpulsoServo(b, CFG["freno"])
    t = _gira(s, [11.0] * 50)                 # chiuso a 11 gradi, pin gia' libero
    t = _gira(s, [0.0] * 200, t)              # ritorno a 0
    pwm0 = [e for e in b.eventi if e[1] == "pwm" and e[2] == 0.0][0][0]
    free0 = [e for e in b.eventi if e[1] == "free" and e[0] > pwm0][0][0]
    assert free0 - pwm0 >= CFG["freno"]["tieni_zero_s"] - 1e-6


def test_corsa_lunga_impulso_lungo():
    b = ServoFinto()
    s = ImpulsoServo(b, CFG["freno"])
    _gira(s, [40.0] * 200)
    pwm = [e for e in b.eventi if e[1] == "pwm"][0][0]
    free = [e for e in b.eventi if e[1] == "free"][0][0]
    assert free - pwm >= 40.0 * CFG["freno"]["tieni_per_grado_s"] - 1e-6


def test_rampa_a_gradini_non_libera_a_meta_corsa():
    """Rampa 25 gradi/s da 11 a 0: gradini da 1 grado; il pin non si libera prima che sia finita la corsa a 0."""
    b = ServoFinto()
    s = ImpulsoServo(b, CFG["freno"])
    t = _gira(s, [11.0] * 100)
    rampa = [max(0.0, 11.0 - 25.0 * DT * k) for k in range(30)]
    _gira(s, rampa + [0.0] * 200, t)
    pwm0 = [e for e in b.eventi if e[1] == "pwm" and e[2] == 0.0][0][0]
    dopo = [e for e in b.eventi if e[0] >= t and e[1] == "free"]
    assert dopo and dopo[0][0] >= pwm0 + CFG["freno"]["tieni_zero_s"] - 1e-6


def test_guardia_rilascio_ripete_impulso_a_zero_se_la_corrente_resta_alta():
    b = ServoFinto()
    ctl = Controllo(CFG, b)
    t, cont = 100.0, 0
    for k in range(400):                      # bici ferma, comando 0, servo che assorbe 3,2 A (freno chiuso)
        b.t = t
        r = ctl.passo(Campione(t=t, enc=(t, cont), imu=(0.0, 0.0, 1.0, 0.0, 0.0, 0.0), ina_ma=3200.0))
        t += DT
    pwm0 = [e for e in b.eventi if e[1] == "pwm" and e[2] == 0.0]
    assert len(pwm0) >= 2, b.eventi[:10]
    assert ctl.servo.n_riprova_zero >= 1
    assert "riprova_zero" in r["motivi"]
    assert r["ina_ma"] == 3200.0


def test_guardia_rilascio_zitta_col_servo_aperto():
    b = ServoFinto()
    ctl = Controllo(CFG, b)
    t = 100.0
    for k in range(400):
        b.t = t
        ctl.passo(Campione(t=t, enc=(t, 0), imu=(0.0, 0.0, 1.0, 0.0, 0.0, 0.0), ina_ma=27.0))
        t += DT
    assert ctl.servo.n_riprova_zero == 0


def test_guardia_al_massimo_quattro_riprove_poi_avviso():
    b = ServoFinto()
    ctl = Controllo(CFG, b)
    t = 100.0
    for k in range(3000):                     # 60 s di stallo continuo a 0 gradi
        b.t = t
        r = ctl.passo(Campione(t=t, enc=(t, 0), imu=(0.0, 0.0, 1.0, 0.0, 0.0, 0.0), ina_ma=3200.0))
        t += DT
    assert ctl.servo.n_riprova_zero == ctl.servo.RIPROVE_ZERO_MAX
    assert b.pin_libero
    assert any("FRENO NON SI APRE" in a for a in r["avvisi"])


def test_guardia_si_riarma_quando_il_freno_si_apre():
    b = ServoFinto()
    ctl = Controllo(CFG, b)
    t = 100.0
    for ma in [3200.0] * 200 + [27.0] * 200:
        b.t = t
        ctl.passo(Campione(t=t, enc=(t, 0), imu=(0.0, 0.0, 1.0, 0.0, 0.0, 0.0), ina_ma=ma))
        t += DT
    assert ctl.servo.n_riprova_zero == 0


def test_encoder_non_scartato_in_discesa_veloce_ne_dopo_un_buco_di_lettura():
    """24/11: a 35 km/h (9,7 m/s) con letture ogni 21 ms, e con un buco di 112 ms a 15 km/h, l'encoder resta la fonte."""
    from speed_limiter_v3.fonti import Encoder
    k = CFG["encoder"]["m_per_count"]
    for v, dts in ((9.7, [0.021] * 60), (4.2, [0.021] * 20 + [0.112] + [0.021] * 20)):
        e = Encoder(CFG["encoder"])
        t, x = 10.0, 0.0
        e.aggiorna(t, (t, 0))
        for dt in dts:
            t += dt; x += v * dt
            e.aggiorna(t, (t, int(x / k)))
        assert e.glitch == 0, (v, e.glitch)
        assert abs(e.v - v) < 0.3, (v, e.v)


def test_encoder_salto_davvero_irreale_ancora_scartato():
    from speed_limiter_v3.fonti import Encoder
    k = CFG["encoder"]["m_per_count"]
    e = Encoder(CFG["encoder"])
    e.aggiorna(10.0, (10.0, 0)); e.aggiorna(10.021, (10.021, 100))
    e.aggiorna(10.042, (10.042, 100 + int(1.0 / k)))       # 1 m in 21 ms = 171 km/h: impossibile
    assert e.glitch == 1

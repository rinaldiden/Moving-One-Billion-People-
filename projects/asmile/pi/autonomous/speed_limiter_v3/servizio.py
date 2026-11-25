"""Loop di servizio (nessun hardware: sensori e servo arrivano da fuori, quindi si prova sul Mac).
Un try per ciclo: se il limiter cade, il freno va a 0, il log e il file di stato lo dicono, e dopo troppi errori di fila il
servizio esce (con codice 1) tenendo 0 gradi prima di liberare il pin. Il servizio NON riparte da solo (Restart=no)."""
import json
import os
import time
import traceback

STATO_DEFAULT = "/run/speed_limiter_v3.state"
ERRORI_DI_FILA_MAX = 5


def scrivi_stato(path, obj):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(obj, f)
        os.replace(tmp, path)
    except OSError:
        pass


def rampa_servo(servo, da, a, gradi_s, sleep=time.sleep):
    """25/11 Daniele: il servo si porta SEMPRE a rampa (un impulso nuovo ogni 20 ms, come in officina), mai a scatto."""
    n = max(1, int(round(abs(a - da) / gradi_s / 0.02)))
    for i in range(1, n + 1):
        servo.pwm(da + (a - da) * i / n)
        sleep(0.02)


def chiudi_servo(servo, tieni_s, sleep=time.sleep, da=None):
    """Uscita: porta a 0 gradi a rampa (sopra 25 a 16,7 gradi/s, poi 50 gradi/s), TIENE il PWM tieni_s, poi libera il pin."""
    try:
        da = getattr(servo, "ultimo", 0.0) if da is None else da
        if da > 25.0:
            rampa_servo(servo, da, 25.0, 16.7, sleep)
            da = 25.0
        if da > 0.0:
            rampa_servo(servo, da, 0.0, 50.0, sleep)
        servo.pwm(0.0)
        sleep(tieni_s)
    finally:
        try:
            servo.libera()
        finally:
            try:
                servo.chiudi()
            except Exception:
                pass


def esegui(ctl, sens, servo, run, stato_path=STATO_DEFAULT, now=time.monotonic, sleep=time.sleep, log=print,
           max_cicli=None, dt=0.02):
    """run: lista [bool] (messa a False da SIGTERM). Ritorna il codice di uscita (0 ok, 1 limiter caduto)."""
    n_err = 0
    cicli = 0
    ultimo_stato = 0.0
    avvisi_prec = None
    prossimo = now()
    while run[0] and (max_cicli is None or cicli < max_cicli):
        cicli += 1
        try:
            c = sens.campione(now())
            r = ctl.passo(c)
            n_err = 0
            if avvisi_prec != r["avvisi"]:
                if r["avvisi"]:
                    log("[LIMITER] AVVISO: " + "; ".join(r["avvisi"]))
                avvisi_prec = r["avvisi"]
            if now() - ultimo_stato >= 1.0:
                ultimo_stato = now()
                scrivi_stato(stato_path, {"t": time.time(), "stato": "ATTENZIONE" if r["avvisi"] else "OK",
                                          "fonte": r["fonte"], "v_kmh": None if r["v"] is None else round(r["v"] * 3.6, 1),
                                          "angolo": round(r["angolo"], 1), "avvisi": r["avvisi"]})
        except Exception as e:            # qualunque errore: freno a 0, avviso visibile, niente silenzio
            n_err += 1
            log("[LIMITER] ERRORE nel ciclo (%d di fila): %r\n%s" % (n_err, e, traceback.format_exc()))
            try:
                ctl.rampa.azzera()
                servo.pwm(0.0)
            except Exception:
                pass
            scrivi_stato(stato_path, {"t": time.time(), "stato": "CADUTO", "errore": repr(e), "errori_di_fila": n_err,
                                      "avvisi": ["LIMITER CADUTO: la bici NON ha il limite dei 15 km/h"]})
            if n_err >= ERRORI_DI_FILA_MAX:
                log("[LIMITER] troppi errori: esco, freno a 0, il servizio non riparte da solo")
                return 1
        prossimo += dt
        s = prossimo - now()
        if s > 0:
            sleep(s)
        else:
            prossimo = now()
    return 0

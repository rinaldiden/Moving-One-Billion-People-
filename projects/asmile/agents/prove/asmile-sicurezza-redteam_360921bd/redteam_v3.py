"""Red-team speed_limiter_v3 in sim (nessun Pi). Uso: python3 redteam_v3.py  (dalla cartella projects/asmile)."""
import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "pi", "autonomous"))
from speed_limiter_v3.scenari import nuovo
from speed_limiter_v3.fonti import Campione, G
from speed_limiter_v3.sim import esegui_sintetico

def run(b, ctl, s, T, mod=None, dt=0.02, **kw):
    out = []; n = int(T/dt)
    for i in range(n):
        s.t = b.t
        c = b.campione()
        if mod: c = mod(b.t, c, b) or c
        r = ctl.passo(c); r["v_vera"] = b.v; r["ang"] = s.angolo; out.append(r)
        b.passo(dt, s.angolo)
    return out

def A_gps_mente_bici_lenta():
    # bici vera a 4 km/h (vibra), encoder giusto, GPS fix inventa 8 m/s (29 km/h), BLE assente
    cfg, s, ctl, b = nuovo(v0_kmh=4.0, pendenza_ms2=0.0, resistenza=0.0, k_dec_per_grado=0.05)
    def mod(t, c, b):
        if t > 3: c.gps = (8.0, True) if int(t*10) % 1 == 0 and abs((t*10) % 1) < 0.2 else None
        c.ble = None
    o = run(b, ctl, s, 15, mod)
    print("A GPS mente, bici vera 4 km/h: angolo max %.1f, v vera finale %.1f km/h, fonte %s" % (max(x["ang"] for x in o), o[-1]["v_vera"]*3.6, o[-1]["fonte"]))

def B_encoder_inventa_costante():
    # bici vera 11 km/h costante, encoder inventa 20 km/h costante (a=0), nessun GPS/BLE
    cfg, s, ctl, b = nuovo(v0_kmh=11.0, pendenza_ms2=0.0, resistenza=0.0, k_dec_per_grado=0.05)
    k = cfg["encoder"]["m_per_count"]; cum = [0.0]
    def mod(t, c, bb):
        cum[0] += 20/3.6/k*0.02; c.enc = (t, int(cum[0])); c.gps = None; c.ble = None
    o = run(b, ctl, s, 25, mod)
    print("B enc inventa 20 km/h (vera 11, no GPS): angolo max %.1f, v vera min %.1f km/h, fonte finale %s, avvisi %s" % (max(x["ang"] for x in o), min(x["v_vera"] for x in o)*3.6, o[-1]["fonte"], o[-1]["avvisi"]))

def C_loop_lento_impuntata(dt):
    cfg, s, ctl, b = nuovo(v0_kmh=14.0, pendenza_ms2=0.0, resistenza=0.0, k_dec_per_grado=0.05)
    ctl.rampa.angolo = 30.0; ctl.servo.tick(0, 30.0)
    def mod(t, c, bb):
        # impuntata vera: 4.5 m/s2 IMU e 20 dps muso giu' per 0.3 s da t=1
        if 1.0 <= t < 1.3:
            im = list(c.imu); im[1] += 4.5/G; im[3] += 20; c.imu = tuple(im)
    o = run(b, ctl, s, 3, mod, dt=dt)
    sc = [x for x in ctl.anti.scatti]
    print("C loop dt=%.2f: scatti anti-impuntata %d (primo a t=%s)" % (dt, len(sc), "%.2f" % sc[0][0] if sc else "MAI"))

def D_imu_rumorosa():
    # strada brutta: ogni 1.0 s una botta (3 g^-1 ay +0.35g, gx 30 dps per 0.12 s). bici a 20 km/h su discesa
    cfg, s, ctl, b = nuovo(v0_kmh=20.0, pendenza_ms2=0.5, k_dec_per_grado=0.05)
    def mod(t, c, bb):
        if (t % 1.0) < 0.12 and t > 2:
            im = list(c.imu); im[1] += 0.35; im[3] += 30; c.imu = tuple(im)
    o = run(b, ctl, s, 40, mod)
    vm = max(x["v_vera"] for x in o[500:])*3.6
    print("D IMU botte 1/s: scatti %d, v vera max dopo 10 s %.1f km/h, angolo medio %.1f, tempo sopra 15.5 km/h %.1f s" % (len(ctl.anti.scatti), vm, sum(x["ang"] for x in o)/len(o), sum(0.02 for x in o if x["v_vera"]*3.6 > 15.5)))

def E_impuntata_in_fallback():
    cfg, s, ctl, b = nuovo(v0_kmh=17.0, pendenza_ms2=0.3, k_dec_per_grado=0.05)
    def mod(t, c, bb):
        if t > 5: c.enc = None                      # encoder staccato -> GPS+IMU
        if 20 <= t < 20.3:
            im = list(c.imu); im[1] += 4.5/G; im[3] += 20; c.imu = tuple(im)
    o = run(b, ctl, s, 25, mod)
    ant = [x for x in ctl.anti.scatti if x[0] > 19.9]
    pre = [x for x in o if 19.9 < x["t"] < 20.0]
    print("E fallback %s: angolo prima %.1f, scatti anti %d, angolo a +0.1s %.1f" % (o[int(19.9/0.02)]["fonte"], o[int(19.95/0.02)]["ang"], len(ant), o[int(20.1/0.02)]["ang"]))

def F_pump():
    # impuntate ripetute ogni 1.3 s mentre il regolatore vuole frenare (sopra 15)
    cfg, s, ctl, b = nuovo(v0_kmh=18.0, pendenza_ms2=0.8, k_dec_per_grado=0.05)
    def mod(t, c, bb):
        if t > 3 and (t % 1.3) < 0.25:
            im = list(c.imu); im[1] += 4.5/G; im[3] += 20; c.imu = tuple(im)
    o = run(b, ctl, s, 30, mod)
    import numpy as np
    ang = np.array([x["ang"] for x in o]); sl = np.abs(np.diff(ang))/0.02
    print("F impuntate ogni 1.3 s: scatti %d, slew max %.0f gradi/s, angolo max %.1f, v vera max %.1f km/h" % (len(ctl.anti.scatti), sl.max(), ang.max(), max(x["v_vera"] for x in o)*3.6))

def G_hang():
    cfg, s, ctl, b = nuovo(v0_kmh=18.0, pendenza_ms2=0.8)
    o = run(b, ctl, s, 8)
    a = s.angolo; lib = s.pin_libero
    # il loop si blocca qui (I2C appeso / CPU / D-state): nessuno chiama piu' passo()
    print("G loop bloccato a angolo %.1f: pin_libero=%s (PWM gira in thread lgpio finche' non arriva libera())" % (a, lib))

for f in (A_gps_mente_bici_lenta, B_encoder_inventa_costante, D_imu_rumorosa, E_impuntata_in_fallback, F_pump, G_hang):
    f()
for dt in (0.02, 0.1, 0.2):
    C_loop_lento_impuntata(dt)

def C2_impuntata_debole(dt):
    cfg, s, ctl, b = nuovo(v0_kmh=14.0, pendenza_ms2=0.0, resistenza=0.0, k_dec_per_grado=0.05)
    ctl.rampa.angolo = 30.0; ctl.servo.tick(0, 30.0)
    def mod(t, c, bb):
        if 1.0 <= t < 1.3:
            im = list(c.imu); im[1] += 3.0/G; im[3] += 8; c.imu = tuple(im)   # ~d03 2.4 gradi, dec ~3
    o = run(b, ctl, s, 3, mod, dt=dt)
    print("C2 debole dt=%.2f: scatti %d" % (dt, len(ctl.anti.scatti)))
for dt in (0.02, 0.1, 0.2):
    C2_impuntata_debole(dt)

def H_soglie_manomesse():
    import copy
    from speed_limiter_v3.controllo import carica_soglie
    from speed_limiter_v3.validazione import valida
    c = copy.deepcopy(carica_soglie())
    c["velocita"]["v_max_kmh"] = 20.0; c["velocita"]["zona_inizio_kmh"] = 18.0
    c["freno"]["tetto_deg"] = 0.0; c["anti_impuntata"]["dec_imu_min_ms2"] = 3.0
    c["fallback"]["tetto_deg"] = 0.0; c["_x"] = {"qualunque": 1}
    valida(c); print("H file manomesso (v_max 20, tetto 0, fallback 0) ACCETTATO dalla validazione: nessun checksum/firma")
H_soglie_manomesse()

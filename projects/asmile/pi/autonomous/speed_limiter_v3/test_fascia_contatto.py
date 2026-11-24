"""24/11 Regolatore a fascia di contatto: avvicinamento al contatto, rilascio dolce, isteresi, validazione contatto/lavoro,
sim con la zona morta realistica del freno. pytest: python3 -m pytest pi/autonomous/speed_limiter_v3 (da projects/asmile)."""
import copy
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from speed_limiter_v3.controllo import carica_soglie            # noqa: E402
from speed_limiter_v3.freno import Rampa, Regolatore             # noqa: E402
from speed_limiter_v3.scenari import comando_liscio, nuovo      # noqa: E402
from speed_limiter_v3.sim import esegui_sintetico                # noqa: E402
from speed_limiter_v3.validazione import SogliaError, valida     # noqa: E402

CFG = carica_soglie()
F = CFG["freno"]
CONTATTO, LAVORO = F["angolo_contatto_deg"], F["angolo_lavoro_deg"]
BASE = CONTATTO - F["margine_contatto_deg"]


def ciclo(reg, rampa, v, a, dt=0.02):
    """un ciclo come Controllo: decisione + Rampa con le rampe del regolatore."""
    t = reg.passo(v, a, rampa.angolo, dt)
    return rampa.passo(t, F["tetto_deg"], dt, None, reg.livello == "sopra15", reg.rate_su, reg.rate_giu)


def test_validazione_contatto_lavoro():
    def con(**kv):
        c = copy.deepcopy(CFG)
        c["freno"].update(kv)
        return c
    valida(con())
    for kv in ({"angolo_contatto_deg": 20.0, "angolo_lavoro_deg": 18.0}, {"angolo_contatto_deg": 18.0},
               {"angolo_lavoro_deg": 55.0}, {"angolo_lavoro_deg": 49.0, "tetto_deg": 40.0},
               {"angolo_contatto_deg": 3.0, "margine_contatto_deg": 2.0},            # contatto-margine < libera_sotto
               {"angolo_contatto_deg": float("nan")}):
        with pytest.raises(SogliaError):
            valida(con(**kv))
    c = copy.deepcopy(CFG)
    del c["freno"]["angolo_lavoro_deg"]
    with pytest.raises(SogliaError):
        valida(c)


def test_avvicinamento_al_contatto_senza_frenare():
    """v appena sopra l'ingaggio, bici che non accelera: sale in fretta a contatto-margine e li' si ferma (niente frenata)."""
    reg, rampa = Regolatore(CFG), Rampa(F)
    v = (CFG["velocita"]["zona_inizio_kmh"] - 0.3) / 3.6
    angoli = []
    for _ in range(100):                      # 2 s
        angoli.append(ciclo(reg, rampa, v, 0.0))
    assert reg.fase in ("fine", "avvicinamento_contatto")
    assert max(angoli) <= BASE + 0.31 and abs(angoli[-1] - BASE) < 0.5
    assert max(angoli) < CONTATTO                           # non arriva mai a sfiorare
    sal = np.diff([0.0] + angoli) / 0.02
    assert sal.max() <= F["rampa_avvicinamento_deg_s"] + 1e-6 and sal.max() > F["rampa_fine_su_deg_s"]   # in fretta
    # sotto l'ingaggio resta libero
    reg2, ramp2 = Regolatore(CFG), Rampa(F)
    for _ in range(50):
        ciclo(reg2, ramp2, 10.5 / 3.6, 0.0)
    assert ramp2.angolo == 0.0 and reg2.fase == "libero"


def test_fine_rampe_piccole_nella_fascia():
    """bici che accelera a 14.5 km/h: l'angolo sale nella fascia con rampa piccola (mai i 25 gradi/s dell'avvicinamento)."""
    reg, rampa = Regolatore(CFG), Rampa(F)
    for _ in range(60):
        ciclo(reg, rampa, 13.0 / 3.6, 0.0)                  # porta a contatto-margine
    prec, massimo = rampa.angolo, 0.0
    for _ in range(200):
        a = ciclo(reg, rampa, 14.6 / 3.6, 0.3)
        massimo = max(massimo, abs(a - prec) / 0.02)
        prec = a
    assert rampa.angolo > CONTATTO and massimo <= max(F["rampa_fine_su_deg_s"], F["rampa_fine_su_sopra15_deg_s"]) + 1e-6


def test_rilascio_dolce_se_gia_rallenta():
    """in fascia di lavoro, v scende con decel >= voluta: l'angolo non sale mai, cala piano (rampa fine), mai salti, resta >= contatto-margine."""
    reg, rampa = Regolatore(CFG), Rampa(F)
    rampa.angolo = LAVORO
    reg.ingaggiato, reg.I = True, LAVORO - BASE
    reg.a_f = -0.6
    v, prec, passi = 14.5 / 3.6, rampa.angolo, []
    for _ in range(25):                                      # 0.5 s: 14.5 -> 13.6 km/h con decel 0.5 m/s2 (voluta ~0.4 -> 0.1)
        v -= 0.5 * 0.02
        ang = ciclo(reg, rampa, v, -0.5)
        passi.append(ang - prec)
        prec = ang
    passi = np.array(passi) / 0.02
    assert passi.max() <= 1e-6                               # mai in salita
    assert -passi.min() <= F["rampa_fine_giu_deg_s"] + 1e-6  # mai salti
    assert rampa.angolo >= BASE - 1e-6 and rampa.angolo < LAVORO - 0.3     # cala, dentro la fascia, non a 0
    assert reg.ingaggiato


def test_rilascio_dolce_arriva_a_contatto_meno_margine_non_a_zero():
    """bici che gia' rallenta a lungo con v nella zona: l'angolo cala dentro la fascia e non scende mai sotto contatto-margine ne' a 0 (isteresi)."""
    reg, rampa = Regolatore(CFG), Rampa(F)
    rampa.angolo = LAVORO
    reg.ingaggiato, reg.I = True, LAVORO - BASE
    reg.a_f = -0.5
    v = 14.9 / 3.6
    for _ in range(350):                                     # 7 s a decel 0.10 m/s2: 14.9 -> ~12.4 km/h
        v -= 0.10 * 0.02
        ang = ciclo(reg, rampa, v, -0.10)
        assert ang >= BASE - 1e-6
    assert v * 3.6 > CFG["velocita"]["zona_inizio_kmh"] - CFG["regolatore"]["disimpegno_sotto_zona_kmh"]
    assert BASE - 1e-6 <= rampa.angolo < LAVORO - 2.0 and reg.ingaggiato        # cala dentro la fascia, mai a 0


def test_isteresi_non_torna_a_zero_nella_banda():
    zona = CFG["velocita"]["zona_inizio_kmh"]
    ing, dis = CFG["regolatore"]["ingaggio_sotto_zona_kmh"], CFG["regolatore"]["disimpegno_sotto_zona_kmh"]
    reg, rampa = Regolatore(CFG), Rampa(F)
    for _ in range(60):
        ciclo(reg, rampa, (zona + 0.5) / 3.6, 0.0)           # ingaggiato, a contatto-margine
    assert reg.ingaggiato and abs(rampa.angolo - BASE) < 0.5
    for k in range(400):                                     # v oscilla fra disimpegno e ingaggio: angolo fermo, nessun 0/non-0
        v = (zona - 0.5 * (ing + dis) + 0.4 * np.sin(k / 10.0)) / 3.6
        ciclo(reg, rampa, v, 0.0)
        assert reg.ingaggiato and rampa.angolo >= BASE - 0.5
    for _ in range(150):                                     # ben sotto: torna a 0
        ciclo(reg, rampa, (zona - dis - 0.5) / 3.6, 0.0)
    assert not reg.ingaggiato and rampa.angolo == 0.0
    for _ in range(100):                                     # nella banda non si riingaggia
        ciclo(reg, rampa, (zona - 0.5 * (ing + dis)) / 3.6, 0.0)
    assert rampa.angolo == 0.0 and reg.fase == "libero"


def test_v_none_rilascia_e_resetta():
    reg = Regolatore(CFG)
    reg.ingaggiato, reg.I = True, 5.0
    assert reg.passo(None, 0.0, 12.0, 0.02) == 0.0 and not reg.ingaggiato and reg.I == 0.0


def _gira(kd, pend, v0, seed, dur=60):
    rng = np.random.default_rng(seed)
    ph, f = rng.uniform(0, 6.28, 3), rng.uniform(0.8, 2.0, 3)
    fn = lambda t: pend + sum(0.25 * np.sin(6.28 * f[i] * t + ph[i]) for i in range(3))        # noqa: E731 pedalate ~0.4 m/s2
    _, s, ctl, b = nuovo(CFG, k_dec_per_grado=kd, zona_morta_deg=CONTATTO, v0_kmh=v0, seed=seed, a_nat_fn=fn)
    return esegui_sintetico(ctl, s, b, dur), s


@pytest.mark.parametrize("kd", [0.1, 0.2, 0.3])
@pytest.mark.parametrize("pend,v0", [(0.8, 13.0), (0.3, 17.0), (0.15, 14.0)])
def test_sim_zona_morta_nessuna_inversione_e_v_contenuta(kd, pend, v0):
    for seed in range(2):
        r, s = _gira(kd, pend, v0, seed)
        _, inv = comando_liscio(r)
        v = np.array([x["v_vera"] for x in r]) * 3.6
        ang = np.array([x["angolo"] for x in r])
        assert inv == 0
        assert ang.max() <= 50.0
        assert v[500:].max() <= 16.5                         # dopo 10 s (steep non mappato: vedi rapporto)
        assert v[500:].mean() <= 14.8
        assert len([e for e in s.eventi if e[1] == "pwm"]) / 60.0 <= 3.0     # impulsi/s


def test_sim_quasi_piano_v_max_15():
    for kd in (0.1, 0.2, 0.3):
        r, _ = _gira(kd, 0.15, 14.0, 0)
        assert max(x["v_vera"] for x in r[250:]) * 3.6 <= 15.05

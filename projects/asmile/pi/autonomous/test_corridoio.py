#!/usr/bin/env python3
"""Test di corridoio.py: sintetici (dritto, curva costante, sterzo da fermo, segni, larghezza, unita', visione, causalita') + coerenza geometria/YAML/tabella.
Uso: python3 test_corridoio.py"""
import os, sys, re, math, unittest
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from corridoio import Corridoio, VelRuota, _carica_calib
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CAL = {"unit": "asmile-001", "encoder_center_raw": 4112, "deg_per_step": 0.02197, "encoder_pos_increases_to": "DX (destra)", "delta_dx_deg": 45.18, "delta_sx_deg": -45.79}
DEG = 1 / 0.02197

def nuovo(): return Corridoio("asmile-001", calib=CAL)
def corri(c, secs, steer_deg, v, gz, hz=50, **kw):
    for i in range(int(secs * hz)):
        c.update(i / hz if c.t is None else c.t + 1 / hz, 4112 + steer_deg * DEG, v, gz, **kw)
    return c

class T(unittest.TestCase):
    def test_dritto(self):
        c = corri(nuovo(), 5, 0, 3.0, 1.75)
        self.assertAlmostEqual(c.k, 0, places=4); z, x = c.percorso(); self.assertLess(np.abs(x).max(), 1e-3)
    def test_larghezza_tabella(self):
        c = nuovo(); self.assertAlmostEqual(2 * c.hw, 1.10); self.assertAlmostEqual(2 * c.hw, c.sog.p["larghezza_asmile_m"])
        corri(c, 2, 0, 3.0, 1.75)
        self.assertTrue(c.dentro(0.5, 5.0)); self.assertFalse(c.dentro(0.6, 5.0)); self.assertFalse(c.dentro(0.0, c.muso - 0.05)); self.assertFalse(c.dentro(0.0, c.orizzonte + 0.1))
    def test_segni_sterzo_destra(self):
        c = corri(nuovo(), 3, +20, 0.0, 1.75)    # fermo, sterzo a destra (encoder sale verso DX)
        self.assertGreater(c.k, 0.05); z, x = c.percorso(6.0); self.assertGreater(x[-1], 0.1)
        c = corri(nuovo(), 3, -20, 0.0, 1.75); self.assertLess(c.k, -0.05)
    def test_sterzo_da_fermo_senza_imu(self):
        c = corri(nuovo(), 2, 15, 0.0, 1.75); self.assertGreater(c.stato()["pesi"]["sterzo"], 0.99)
        self.assertGreater(abs(c.k), 0.05)
    def test_segno_gz(self):     # gz negativo = destra: bici in moto sterzo dritto ma gz = -10 dps -> k>0
        c = corri(nuovo(), 3, 0, 3.0, 1.75 - 10.0)
        self.assertGreater(c.k_imu, 0); self.assertAlmostEqual(c.k_imu, math.radians(10) / 3.0, delta=0.002)
    def test_curva_costante_coerente(self):     # sterzo e giroscopio concordi: k fusa ~ k_imu
        k_imu = 0.1; v = 3.0; gz = 1.75 - math.degrees(k_imu * v)
        c = corri(nuovo(), 4, 0, v, gz); self.assertAlmostEqual(c.k_imu, k_imu, delta=0.003)
    def test_bias_in_linea(self):
        c = nuovo(); corri(c, 20, 0, 0.0, 3.0)      # fermo con bias vero 3 dps
        self.assertAlmostEqual(c.bias, 3.0, delta=0.15)
    def test_nessuna_rotazione_vera_nel_bias(self):
        c = nuovo(); corri(c, 20, 0, 0.0, 1.75); b = c.bias; corri(c, 5, 0, 0.0, 1.75 + 30); self.assertAlmostEqual(c.bias, b, delta=0.01)
    def test_unita_diversa(self):
        with self.assertRaises(ValueError): Corridoio("asmile-001", calib=dict(CAL, unit="asmile-002"))
        with self.assertRaises(ValueError): _carica_calib("asmile-001", os.path.join(ROOT, "config", "soglie_attuazione_001.json"))
    def test_incertezza_a_parte(self):
        c = corri(nuovo(), 2, 0, 3.0, 1.75); s1 = c.incertezza(np.array([3., 10.])); self.assertTrue(s1[1] > s1[0] > 0); self.assertAlmostEqual(2 * c.hw, 1.10)
    def test_spazio_laterale(self):
        c = corri(nuovo(), 2, 0, 3.0, 1.75)
        sx, dx = c.spazio_laterale(-1.0, 1.3, 5.0); self.assertAlmostEqual(sx, 0.45); self.assertAlmostEqual(dx, 0.75)
        sx, dx = c.spazio_laterale(None, 0.2, 5.0); self.assertTrue(math.isinf(sx)); self.assertLess(dx, 0)
    def test_visione(self):
        c = nuovo(); corri(c, 2, 0, 3.0, 1.75, vis={"k": 0.1, "peso": 0.5}); self.assertAlmostEqual(c.k, 0.05, delta=0.003); self.assertAlmostEqual(c.stato()["pesi"]["visione"], 0.5)
        c = corri(nuovo(), 2, 0, 3.0, 1.75, vis=None); self.assertEqual(c.stato()["pesi"]["visione"], 0.0)
        c = corri(nuovo(), 2, 0, 3.0, 1.75, vis={"k": 0.3, "peso": 1.0}); self.assertLessEqual(c.stato()["pesi"]["visione"], c.par["vis_peso_max"])
    def test_causale(self):     # la risposta a un gradino non anticipa mai il gradino
        c = nuovo(); ks = []
        for i in range(200): c.update(i / 50, 4112 + (0 if i < 100 else 20 * DEG), 3.0, 1.75); ks.append(c.k)
        self.assertLess(abs(ks[99]), 1e-6); self.assertGreater(ks[110], 0.02)
    def test_orizzonte_da_tabella(self):
        c = corri(nuovo(), 2, 0, 2.78, 1.75); self.assertAlmostEqual(c.orizzonte, c.muso + c.sog.a(2.78)["rallenta_entro_m"], delta=0.3)
    def test_poligono(self):
        K = np.array([[1380., 0, 640], [0, 1380., 400], [0, 0, 1]]); c = corri(nuovo(), 2, 0, 3.0, 1.75)
        P = c.poligono_immagine(K, math.radians(7.4)); self.assertGreater(len(P), 10)
        n = len(P) // 2; self.assertLess(P[:n, 0].mean(), 640); self.assertGreater(P[n:, 0].mean(), 640)
        self.assertGreater(len(c.poligono_immagine(K, math.radians(7.4), incertezza=True)), 10)
    def test_geometria_coincide_con_yaml(self):
        txt = open(os.path.join(ROOT, "follow_me", "asmile_config.yaml")).read(); sez = txt.split("stereo:")[0]
        y = {k: float(v) for k, v in re.findall(r"^\s+(\w+_cm):\s*([\d.]+)", sez, re.M)}
        c = nuovo()
        for k in ("larghezza_max_cm", "sporgenza_muso_cm", "cam_offset_laterale_cm", "altezza_cam_da_terra_cm"): self.assertAlmostEqual(c.geo[k], y[k], msg=k)
    def test_velruota(self):
        vr = VelRuota(2.1219e-5); v = 0
        for i in range(100): v = vr.update(i * 0.02, i * 0.02 * 3.0 / 2.1219e-5)
        self.assertAlmostEqual(v, 3.0, delta=0.05)

if __name__ == "__main__":
    unittest.main(verbosity=1)

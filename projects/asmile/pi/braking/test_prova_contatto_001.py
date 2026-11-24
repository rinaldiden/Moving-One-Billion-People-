"""Test a secco di prova_contatto_001 con backend finto (nessun hardware, nessun lock, tempo simulato). Esegui: python3 -m pytest -q  oppure python3 test_prova_contatto_001.py"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_contatto_001 as P
from speed_limiter_v3.controllo import carica_soglie

K = carica_soglie()["encoder"]["m_per_count"]


class Mondo:
    """Clock + ruota + servo + sensori finti. Contatto a CONTATTO gradi: oltre, decel extra 0,4 m/s2 per grado."""
    def __init__(self, contatto=11.0, a0=0.15, i_extra=0, ctrlc_a=None):
        self.t, self.v, self.s, self.pos = 1000.0, 0.0, 0.0, 0.0
        self.contatto, self.a0, self.i_extra, self.pwm_on = contatto, a0, i_extra, False
        self.calls, self.ctrlc_a, self.prova = [], ctrlc_a, None
    def ora(self): return self.t
    def dorme(self, dt):
        a = self.a0 + max(0.0, self.pos - self.contatto) * 0.4 if self.v > 0 else 0.0
        self.v = max(0.0, self.v - a * dt); self.s += self.v * dt; self.t += dt
        if self.v < 0.5:
            self.v = 4.0                     # Daniele rilancia la ruota
        if self.ctrlc_a is not None and self.pos >= self.ctrlc_a and self.prova:
            self.prova.run = False
    # servo
    def pwm(self, a):
        assert 0 <= a <= P.ANG_TETTO_ASSOLUTO; self.pos = a; self.pwm_on = True; self.calls.append(("pwm", a))
    def libera(self): self.pwm_on = False; self.calls.append(("libera", self.pos))
    # sensori
    def enc(self): return (self.t, int(self.s / K))
    def ina_ma(self):
        """Pin libero: 27 mA sempre (log reale 24/11). PWM attivo: ~55 mA in aria, +10 mA per grado oltre il contatto."""
        if not self.pwm_on:
            return 27.0 + self.i_extra
        return 55.0 + 10.0 * max(0.0, self.pos - self.contatto) + self.i_extra


def fai(mondo, **kw):
    out = tempfile.mkdtemp()
    p = P.Prova(mondo, mondo, carica_soglie()["encoder"], os.path.join(out, "g.csv"), ora=mondo.ora, dorme=mondo.dorme,
                chiedi=lambda *_: "vai", dire=lambda *_: None, **kw)
    mondo.prova = p
    return p


class T(unittest.TestCase):
    def test_trova_contatto_e_lavoro(self):
        m = Mondo(); p = fai(m); p.esegui(); p.chiudi()
        passi, r = P.analizza(p.righe)
        self.assertEqual(len(r["sfiora_da_decel"]), 2, r)                       # 2 salite
        self.assertIn(r["sfiora_da_decel_mediana"], (11.0, 12.0), r)
        self.assertTrue(11.0 <= r["sfiora_da_corrente_mediana"] <= 15.0, r)   # corrente CON PWM attivo
        self.assertTrue(r["lavora_gradi_mediana"][1.0] is not None and 12.0 <= r["lavora_gradi_mediana"][1.0] <= 15.0, r)
        self.assertTrue(r["lavora_gradi_mediana"][2.0] is None or r["lavora_gradi_mediana"][2.0] >= 14.0, r)
        self.assertTrue(any(x["dir"] == "giu1" for x in passi))                 # discesa fatta
        self.assertIsNotNone(r["isteresi_gradi"]); self.assertLessEqual(abs(r["isteresi_gradi"]), 2.0, r)
        self.assertLessEqual(max(a for k, a in m.calls if k == "pwm"), 30.0)
        self.assertEqual(m.calls[-1][0], "libera")

    def test_senza_contatto_non_sfiora(self):
        m = Mondo(contatto=99.0); p = fai(m); p.esegui(); p.chiudi()
        _, r = P.analizza(p.righe)
        self.assertEqual(r["sfiora_da_decel"], []); self.assertIsNone(r["lavora_gradi_mediana"][1.0])
        self.assertEqual(max(a for k, a in m.calls if k == "pwm"), 30.0)    # arriva al tetto e si ferma

    def test_riferimento_dipende_da_v(self):
        """decel a freno aperto = 0,10 + 0,1*v: il confronto a pari velocita' evita il falso 'sfiora' ai bassi v."""
        class M2(Mondo):
            def dorme(self, dt):
                self.a0 = 0.10 + 0.1 * self.v
                Mondo.dorme(self, dt)
        m = M2(contatto=99.0); p = fai(m); p.esegui(); p.chiudi()
        _, r = P.analizza(p.righe)
        self.assertEqual(r["sfiora_da_decel"], [], r)
        self.assertGreater(len(r["rif_punti_v_dec"]), 4)                        # riferimento anche a fine passata

    def test_ctrl_c_al_prompt_non_tocca_il_pin(self):
        """main(): Ctrl-C su input() prima del 'vai' -> esce, nessun backend servo creato."""
        import unittest.mock as um
        with um.patch.object(P, "SensoriVeri") as SV, um.patch.object(P, "ServoVero", side_effect=RuntimeError) as SR, \
                um.patch("builtins.input", side_effect=KeyboardInterrupt), \
                um.patch("speed_limiter_v3.lock_gpio12.acquisisci_lock", return_value=um.MagicMock()):
            SV.return_value.ina_ma.return_value = 80.0; SV.return_value.enc.return_value = (1.0, 1)
            rc = P.main(["--out", tempfile.mkdtemp()])
        self.assertEqual(rc, 1); SR.assert_not_called()

    def test_corrente_alta_ferma_e_rilascia(self):
        m = Mondo(i_extra=1600); p = fai(m)
        with self.assertRaises(P.Stop): p.esegui()
        p.rilascia("fine"); p.chiudi()
        self.assertEqual(m.calls[-2:], [("pwm", 0.0), ("libera", 0.0)])

    def test_ctrl_c_rilascia_a_zero_lungo(self):
        m = Mondo(ctrlc_a=5.0); p = fai(m); m.prova = p
        t_prima = None
        with self.assertRaises(P.Stop): p.esegui()
        t0 = m.t; p.rilascia("fine"); p.chiudi()
        self.assertGreaterEqual(m.t - t0, P.RILASCIO_S - 0.05)
        self.assertEqual(m.calls[-2:], [("pwm", 0.0), ("libera", 0.0)])

    def test_tetti(self):
        with self.assertRaises(ValueError): fai(Mondo(), max_gradi=31)
        with self.assertRaises(ValueError): P.ServoVero.pwm(type("X", (), {"s": None})(), 51)

    def test_ina_muto(self):
        m = Mondo(); p = fai(m); m.ina_ma = lambda: None
        p.t_ina_ok = m.t - 1.0
        with self.assertRaises(P.Stop): p.tick("vuoto", 0.0)

    def test_fit(self):
        self.assertAlmostEqual(P.fit_decel([(i * .02, 3 - .5 * i * .02) for i in range(50)]), 0.5, 5)

if __name__ == "__main__":
    unittest.main()

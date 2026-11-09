"""Test locali (nessun hardware): i rifiuti di vesc_return_centro_001 e vesc_mcconf_limiti_001 con seriale finta."""
import json, os, sys, tempfile, unittest, struct
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vesc_return_centro_001 as rc
import vesc_mcconf_limiti_001 as mc
import safety_001 as sf
_WHEEL_REALE = rc._wheel

CAL = {"unit": "asmile-001", "encoder_bits": 14, "encoder_steps_per_rev": 16384, "encoder_center_raw": 8000,
       "delta_sx_steps": -1500, "delta_dx_steps": 1500, "center_repeatability_deg": 0.3}


class FakeSer:
    def __init__(self): self.w = []
    def write(self, b): self.w.append(b)
    def close(self): pass


class RC(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); rc.DATA_DIR = self.d
        self.cal = dict(CAL)
        self._wr()
        self.pt = [mock.patch.object(rc, "unit", lambda: "asmile-001"),
                   mock.patch.object(rc, "uart_libera", lambda u: (True, "")),
                   mock.patch.object(rc, "ferma_bici", lambda ref=None: True),
                   mock.patch.object(rc, "_wheel", lambda: ("5", True)),
                   mock.patch.object(rc.serial, "Serial", lambda *a, **k: FakeSer()),
                   mock.patch.object(rc, "send_duty", lambda s, d: s.write(("d", d))),
                   mock.patch.object(rc, "send_current", lambda s, d: s.write(("c", d))),
                   mock.patch.object(rc, "rd", lambda: 8600),
                   mock.patch.object(rc, "lcur_max", lambda s: 5.0),
                   mock.patch.object(rc, "vai_interattivo", lambda t: False)]
        for p in self.pt: p.start()
    def tearDown(self):
        for p in self.pt: p.stop()
    def _wr(self): json.dump(self.cal, open(os.path.join(self.d, "steering_limits_asmile-001.json"), "w"))
    def refuse(self, argv=(), msg=""):
        with self.assertRaises(SystemExit) as c: rc.main(list(argv))
        self.assertIn(msg, str(c.exception.code))

    def test_tetti(self):
        self.refuse(["--imax", "6"], "--imax")
        self.refuse(["--duty", "0.04"], "--duty")
        self.refuse(["--step-ms", "150"], "--step-ms")
    def test_manca_calib(self):
        os.remove(os.path.join(self.d, "steering_limits_asmile-001.json")); self.refuse(msg="manca")
    def test_calib_invalide(self):
        for k, v, m in (("unit", "asmile2", "altra unita"), ("encoder_bits", 12, "14 bit"), ("center_repeatability_deg", 1.5, "> 1")):
            self.cal = dict(CAL); self.cal[k] = v; self._wr(); self.refuse(msg=m)
    def test_uart_occupata(self):
        with mock.patch.object(rc, "uart_libera", lambda u: (False, "servizio power_steering attivo")): self.refuse(msg="non libera")
    def test_bici_in_moto(self):
        with mock.patch.object(rc, "ferma_bici", lambda ref=None: False): self.refuse(msg="NON ferma")
    def test_fuori_range(self):
        with mock.patch.object(rc, "rd", lambda: 8000 + 1490): self.refuse(msg="fuori da")
    def test_lcur_alta(self):
        with mock.patch.object(rc, "lcur_max", lambda s: 15.0): self.refuse(msg="passo A")
    def test_vai_negato_nessun_comando(self):
        sers = []
        with mock.patch.object(rc.serial, "Serial", lambda *a, **k: sers.append(FakeSer()) or sers[-1]):
            rc.main([])
        # solo zeri (stop nel finally), mai duty != 0
        self.assertTrue(all(w[1] == 0 for w in sers[0].w))
    def test_movimento_piccolo(self):
        it = iter([8600, 8602, 8602])  # p, p1 dopo stadio 1
        with mock.patch.object(rc, "vai_interattivo", lambda t: True), mock.patch.object(rc, "rd", lambda: next(it)), \
             mock.patch.object(rc, "pulse", lambda *a, **k: None), mock.patch.object(rc.time, "sleep", lambda x: None):
            import io, contextlib
            b = io.StringIO()
            with contextlib.redirect_stdout(b): rc.main([])
            self.assertIn("< 5", b.getvalue())
    def test_corrente_alta_ferma(self):
        with mock.patch.object(rc, "vai_interattivo", lambda t: True), mock.patch.object(rc, "query_tach", lambda s: {"i_motor": 9.0}), \
             mock.patch.object(rc.time, "sleep", lambda x: None):
            import io, contextlib
            b = io.StringIO()
            with contextlib.redirect_stdout(b): rc.main([])
            self.assertIn("corrente", b.getvalue())
    def test_pulse_fuori_range(self):
        with mock.patch.object(rc, "query_tach", lambda s: {"i_motor": 1.0}), mock.patch.object(rc, "rd", lambda: 9480), mock.patch.object(rc.time, "sleep", lambda x: None):
            r = rc.pulse(FakeSer(), 0.02, 50, 5, 9400, 8000, 6500, 9500, 40)
            self.assertIn("fuori range", r)
    def test_ferma_bici_vecchio(self):
        p = os.path.join(self.d, "w"); open(p, "w").write("1"); os.utime(p, (1, 1))
        self.pt[2].stop()  # ferma_bici reale
        with mock.patch.object(rc, "WHEEL", p), mock.patch.object(rc, "_wheel", _WHEEL_REALE):
            self.assertFalse(rc.ferma_bici())
            self.assertFalse(rc.ferma_bici("1"))
            os.utime(p, None); self.assertTrue(rc.ferma_bici("1")); self.assertFalse(rc.ferma_bici("2"))
        self.pt[2].start()


class SF(unittest.TestCase):
    def test_no_tty(self):
        with mock.patch.object(sys, "stdin", mock.Mock(isatty=lambda: False)):
            with self.assertRaises(SystemExit): sf.vai_interattivo("x")
    def test_uart_fuser(self):
        r = mock.Mock(stdout="123 456", returncode=0)
        with mock.patch.object(sf, "_run", lambda c: r): self.assertFalse(sf.uart_libera("/dev/x")[0])
    def test_servizio_attivo(self):
        def run(c):
            return mock.Mock(stdout="" if c[0] in ("fuser", "pgrep") else "active")
        with mock.patch.object(sf, "_run", run): self.assertIn("servizio", sf.uart_libera("/dev/x")[1])
    def test_pgrep(self):
        def run(c):
            return mock.Mock(stdout="999" if c[0] == "pgrep" else ("inactive" if c[0] == "systemctl" else ""))
        with mock.patch.object(sf, "_run", run): self.assertIn("power_steering", sf.uart_libera("/dev/x")[1])
    def test_tutto_libero(self):
        def run(c): return mock.Mock(stdout="inactive" if c[0] == "systemctl" else "")
        with mock.patch.object(sf, "_run", run): self.assertTrue(sf.uart_libera("/dev/x")[0])


def blob(vals):
    b = bytearray(b"\x00\x01\x02\x03" + b"\x00" * 4)
    for v in vals: b += mc.enc(v)
    return b


class MC(unittest.TestCase):
    def test_plausibile_segni(self):
        self.assertTrue(mc.plausibile(blob([20, -20, 10, -5, 30])))
        self.assertFalse(mc.plausibile(blob([-20, -20, 10, -5, 30])))   # max negativo
        self.assertFalse(mc.plausibile(blob([20, 20, 10, -5, 30])))     # min positivo
        self.assertFalse(mc.plausibile(blob([20, 0, 10, -5, 30])))      # zero
        self.assertFalse(mc.plausibile(blob([20, -20, 0, -5, 30])))
    def _run_scrivi(self, extra, uart=(True, ""), vai=True, validato=True):
        b = blob([20, -20, 10, -5, 30])
        with mock.patch.object(mc.serial, "Serial", lambda *a, **k: FakeSer()), mock.patch.object(mc, "fw", lambda s: (5, 2)), \
             mock.patch.object(mc, "get", lambda s: b), mock.patch.object(mc, "uart_libera", lambda p: uart), \
             mock.patch.object(mc, "vai_interattivo", lambda t: vai), mock.patch.object(mc.os.path, "exists", lambda p: validato), \
             mock.patch.object(mc, "pack", lambda x: x), mock.patch.object(mc.time, "sleep", lambda x: None), \
             mock.patch.object(mc.os, "makedirs", lambda *a, **k: None), mock.patch("builtins.open", mock.mock_open()), \
             mock.patch.object(sys, "argv", ["x", "scrivi"] + extra):
            mc.main()
    def test_alza_rifiutato(self):
        with self.assertRaises(SystemExit) as c: self._run_scrivi(["--apply", "--l-current-max", "25"])
        self.assertIn("ALZEREBBE", str(c.exception.code))
    def test_segno_sbagliato(self):
        with self.assertRaises(SystemExit) as c: self._run_scrivi(["--apply", "--l-current-min", "8"])
        self.assertIn("plausibili", str(c.exception.code))
    def test_zero(self):
        with self.assertRaises(SystemExit) as c: self._run_scrivi(["--apply", "--l-current-max", "0"])
        self.assertIn("plausibili", str(c.exception.code))
    def test_uart_occupata(self):
        with self.assertRaises(SystemExit) as c: self._run_scrivi(["--apply"], uart=(False, "pid 1"))
        self.assertIn("non libera", str(c.exception.code))
    def test_vai_negato(self):
        with self.assertRaises(SystemExit) as c: self._run_scrivi(["--apply"], vai=False)
        self.assertIn("annullato", str(c.exception.code))
    def test_dry_run_non_scrive(self):
        self._run_scrivi([])
    def test_vai_flag_non_esiste(self):
        with self.assertRaises(SystemExit): self._run_scrivi(["--apply", "--vai"])


if __name__ == "__main__":
    unittest.main(verbosity=1)

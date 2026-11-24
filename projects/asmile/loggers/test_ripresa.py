"""Test a secco di scarica_con_ripresa contro un server finto (Range, cadute a meta', server vecchio senza Range, 503)."""
import http.server, threading, tempfile, os, hashlib, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pull_from_loggers as p

DATI = os.urandom(3_000_000)
MODO = {"senza_cr": False, "corto": False, "cadi_dopo": 0, "range": True, "n503": 0, "richieste": []}

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_GET(self):
        MODO["richieste"].append(self.headers.get("Range"))
        if MODO["n503"] > 0:
            MODO["n503"] -= 1
            self.send_response(503); self.send_header("Content-Length", "0"); self.end_headers(); return
        rng = self.headers.get("Range")
        a = 0
        if rng and MODO["range"]:
            a = int(rng.split("=")[1].split("-")[0])
            if a >= len(DATI):
                self.send_response(416); self.send_header("Content-Length", "0"); self.end_headers(); return
            self.send_response(206)
            if not MODO["senza_cr"]: self.send_header("Content-Range", f"bytes {a}-{len(DATI)-1}/{len(DATI)}")
        else:
            self.send_response(200)
        corpo = DATI[a:]
        if MODO["corto"]: corpo = corpo[:-1000]
        self.send_header("Content-Length", str(len(corpo))); self.end_headers()
        if MODO["cadi_dopo"]:
            self.wfile.write(corpo[:MODO["cadi_dopo"]]); self.wfile.flush(); self.close_connection = True
            self.connection.shutdown(2); return
        self.wfile.write(corpo)

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_port}/dl?f=x"
d = tempfile.mkdtemp()
sha = hashlib.sha256(DATI).hexdigest()
def prova(nome, ok_atteso=True, **kw):
    part = os.path.join(d, nome)
    r = p.scarica_con_ripresa(url, part, len(DATI), pausa=0.05, log=lambda m: None, **kw)
    esatto = os.path.exists(part) and hashlib.sha256(open(part, "rb").read()).hexdigest() == sha
    assert r == ok_atteso, (nome, r)
    if ok_atteso: assert esatto, nome + ": contenuto diverso"
    print("OK", nome, "richieste Range:", MODO["richieste"]); MODO["richieste"].clear()

prova("a_liscio")
MODO["cadi_dopo"] = 700_000; prova("cade_ogni_700k"); MODO["cadi_dopo"] = 0
# .part parziale da un giro precedente: deve riprendere, non ricominciare
part = os.path.join(d, "b_preesistente"); open(part, "wb").write(DATI[:1_000_000])
assert p.scarica_con_ripresa(url, part, len(DATI), log=lambda m: None) and open(part, "rb").read() == DATI
assert MODO["richieste"] == ["bytes=1000000-"], MODO["richieste"]; MODO["richieste"].clear(); print("OK riprende da 1000000")
MODO["range"] = False; MODO["cadi_dopo"] = 0
part = os.path.join(d, "c_vecchio"); open(part, "wb").write(DATI[:500_000])
assert p.scarica_con_ripresa(url, part, len(DATI), log=lambda m: None) and open(part, "rb").read() == DATI; MODO["richieste"].clear(); print("OK server senza Range: riparte da 0, contenuto esatto")
MODO["range"] = True
part = os.path.join(d, "d_troppo_lungo"); open(part, "wb").write(DATI + b"x")
assert p.scarica_con_ripresa(url, part, len(DATI), log=lambda m: None) and open(part, "rb").read() == DATI; MODO["richieste"].clear(); print("OK part piu' lungo: da capo")
MODO["n503"] = 2; prova("e_503_poi_ok")
MODO["n503"] = 99; prova("f_sempre_503", ok_atteso=False, tentativi=6)
print("tentativi su 503 permanente:", len(MODO["richieste"]), "(max 3 poi stop)")
assert len(MODO["richieste"]) <= 3
MODO["n503"] = 0; MODO["richieste"].clear()
# 206 SENZA Content-Range (proxy /b): col codice vecchio falliva ("Content-Range inatteso"), ora riprende con verifica lunghezza
MODO["senza_cr"] = True
part = os.path.join(d, "g_senza_cr"); open(part, "wb").write(DATI[:1_200_000])
assert p.scarica_con_ripresa(url, part, len(DATI), log=lambda m: None) and open(part, "rb").read() == DATI
assert MODO["richieste"] == ["bytes=1200000-"], MODO["richieste"]; MODO["richieste"].clear(); print("OK 206 senza Content-Range, lunghezza giusta: accodato")
MODO["corto"] = True
part = os.path.join(d, "h_senza_cr_corto"); open(part, "wb").write(DATI[:1_200_000])
assert not p.scarica_con_ripresa(url, part, len(DATI), tentativi=1, log=lambda m: None)
assert os.path.getsize(part) == 1_200_000, "non deve accodare byte di lunghezza sbagliata"; print("OK 206 senza CR e corto: rifiutato, .part intatto")
MODO["corto"] = MODO["senza_cr"] = False
print("TUTTI OK")

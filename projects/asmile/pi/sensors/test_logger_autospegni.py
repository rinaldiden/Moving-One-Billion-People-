#!/usr/bin/env python3
"""Test a secco (Mac, nessun hardware) di logger_autospegni: file da scaricare + Mac visto + tetti."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logger_autospegni as L

def t(nome, got, want):
    print(("ok  " if got == want else "KO  ") + nome, "" if got == want else f"(got {got!r})")
    return got == want

ok = True
d = tempfile.mkdtemp()
ok &= t("cartella vuota: 0 pezzi", L.pezzi_da_scaricare(d), 0)
for i in range(3):
    f = os.path.join(d, f"clip_{i}.h264"); open(f, "w").close(); os.utime(f, (time.time() - 100 + i,) * 2)
ok &= t("3 clip: il piu' recente e' in scrittura -> 2", L.pezzi_da_scaricare(d), 2)
open(os.path.join(d, "clip_%05d.h264"), "w").close()
ok &= t("artefatto %05d ignorato", L.pezzi_da_scaricare(d), 2)
A = L.aspetta_scarico
ok &= t("niente pezzi -> spegne", A(0, 30, 6, 12.0), None)
ok &= t("pezzi + Mac 30 s fa -> sveglio", bool(A(2, 30, 6, 12.0)), True)
ok &= t("pezzi + Mac 9 min fa -> sveglio", bool(A(2, 540, 6, 12.0)), True)
ok &= t("pezzi + Mac 11 min fa -> spegne", A(2, 660, 6, 12.0), None)
ok &= t("pezzi + Mac mai visto (lontano da casa) -> spegne", A(2, None, 6, 12.0), None)
ok &= t("pezzi + Mac presente + batteria 9,8 V -> spegne", A(2, 30, 6, 9.8), None)
ok &= t("batteria illeggibile -> non spegne per questo", bool(A(2, 30, 6, None)), True)
ok &= t("tetto 3 h dopo il fermo -> spegne", A(2, 30, 5 + 181, 12.0), None)
ok &= t("poco prima del tetto -> sveglio", bool(A(2, 30, 5 + 170, 12.0)), True)
# file sparito fra glob e stat (il Mac cancella): niente eccezione
real = os.path.getmtime
def finto(x):
    if x.endswith("clip_0.h264"): raise FileNotFoundError(x)
    return real(x)
os.path.getmtime = finto
try:
    ok &= t("file sparito fra glob e stat: nessuna eccezione, 1 pezzo", L.pezzi_da_scaricare(d), 1)
finally:
    os.path.getmtime = real
# journalctl/ss mancanti (PATH vuoto): nessuna eccezione, None
oldp = os.environ.get("PATH", ""); os.environ["PATH"] = "/nonexistent"
try:
    ok &= t("journalctl/ss mancanti: None senza eccezione", L.mac_visto_s_fa(), None)
finally:
    os.environ["PATH"] = oldp
print("TUTTO OK" if ok else "FALLITI"); sys.exit(0 if ok else 1)

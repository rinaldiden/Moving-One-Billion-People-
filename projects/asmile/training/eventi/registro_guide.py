#!/usr/bin/env python3
"""
registro_guide.py — REGISTRO CUMULATIVO del comportamento del pilota, per unità e sessione.

Ogni uscita (asmile #001, asmile-logger001, altre Asmile) aggiunge i suoi eventi di guida allo stesso registro:
così si confronta come ha guidato il pilota in situazioni che #001 non ha incontrato (Daniele 2026-11-13).
#001 è l'insegnante (sensori completi); il logger misura con quello che ha (IMU+video o ruota BLE, niente sterzo):
la colonna `fonte_v` e `qualita` dicono quanto fidarsi.

  agents/registro_guide/frenate.csv   un evento di frenata per riga
  agents/registro_guide/sterzate.csv  una sterzata per riga
  agents/registro_guide/sessioni.csv  una riga per sessione importata (unità, data, metri, fonte velocità, note)

Uso:  python3 registro_guide.py aggiungi --unita asmile-001 --dir training/eventi/out_guide_20261112_c0.3477 \
          --fonte-v encoder_ruota --qualita alta [--nota "..."]
      python3 registro_guide.py riepilogo
Idempotente: rimportare la stessa sessione sostituisce le sue righe (chiave unita+sess).
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "..", "..", "agents", "registro_guide")
TIPI = ("frenate", "sterzate")


def leggi(path):
    if not os.path.exists(path):
        return [], []
    with open(path) as f:
        r = csv.DictReader(f)
        return r.fieldnames or [], list(r)


def scrivi(path, campi, righe):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campi, extrasaction="ignore")
        w.writeheader()
        w.writerows(righe)


def aggiungi(a):
    os.makedirs(REG, exist_ok=True)
    importate = defaultdict(int)
    for tipo in TIPI:
        src = os.path.join(a.dir, f"{tipo}.csv")
        if not os.path.exists(src):
            continue
        _, nuove = leggi(src)
        for r in nuove:
            r.update(unita=a.unita, fonte_v=a.fonte_v, qualita=a.qualita, origine=os.path.relpath(src, os.path.join(HERE, "..", "..")))
        chiavi = {(a.unita, r["sess"]) for r in nuove}
        dst = os.path.join(REG, f"{tipo}.csv")
        campi_old, vecchie = leggi(dst)
        tenute = [r for r in vecchie if (r.get("unita"), r.get("sess")) not in chiavi]
        campi = ["unita", "sess"] + [c for c in dict.fromkeys(campi_old + list(nuove[0].keys() if nuove else []))
                                     if c not in ("unita", "sess")]
        scrivi(dst, campi, tenute + nuove)
        for r in nuove:
            importate[r["sess"]] += 1
    # sessioni
    dst = os.path.join(REG, "sessioni.csv")
    _, vecchie = leggi(dst)
    metri = {}
    seg = os.path.join(a.dir, "segmenti.json")
    if os.path.exists(seg):
        try:
            for s in json.load(open(seg)):
                k = s.get("sess")
                if k and s.get("usato", True):
                    metri[k] = metri.get(k, 0) + float(s.get("dist_m", 0) or 0)
        except (ValueError, TypeError, AttributeError):
            pass
    nuove = [dict(unita=a.unita, sess=s, eventi=n, metri=round(metri.get(s, 0), 1), fonte_v=a.fonte_v,
                  qualita=a.qualita, importato=datetime.now().isoformat(timespec="seconds"), nota=a.nota)
             for s, n in sorted(importate.items())]
    chiavi = {(r["unita"], r["sess"]) for r in nuove}
    tenute = [r for r in vecchie if (r.get("unita"), r.get("sess")) not in chiavi]
    scrivi(dst, ["unita", "sess", "eventi", "metri", "fonte_v", "qualita", "importato", "nota"], tenute + nuove)
    print(f"importate {len(nuove)} sessioni di {a.unita}: " + ", ".join(f"{r['sess']} ({r['eventi']})" for r in nuove))


def usabile_per_soglie(r):
    """Riga usabile per ricavare soglie (Daniele/scettico 2026-11-13): classe stop_umano/umano E qualita != bassa E
    segno_imu vuoto o verificato_ble (mapping_0911/non_verificato esclusi; vuoto = unita' con velocita da encoder, nessun segno IMU da verificare).
    Le righe candidata_imu / qualita bassa NON entrano mai in soglie."""
    return (r.get("classe") in ("stop_umano", "umano") and r.get("qualita") != "bassa"
            and r.get("segno_imu", "") in ("", "verificato_ble"))


def righe_usabili(tipo="frenate"):
    """Solo le righe del registro usabili per soglie: e' l'unico punto da cui un fit di soglie deve leggere il registro."""
    return [r for r in leggi(os.path.join(REG, f"{tipo}.csv"))[1] if usabile_per_soglie(r)]


def riepilogo(_):
    for tipo in TIPI:
        _, righe = leggi(os.path.join(REG, f"{tipo}.csv"))
        c = Counter((r["unita"], r.get("classe", "-")) for r in righe)
        print(f"{tipo}: {len(righe)} eventi")
        for (u, cl), n in sorted(c.items()):
            print(f"   {u:18s} {cl:14s} {n}")
        if tipo == "frenate":
            cu = Counter(r["unita"] for r in righe if usabile_per_soglie(r))
            print("   usabili per soglie: %d  (%s)" % (sum(cu.values()), ", ".join(f"{u} {n}" for u, n in sorted(cu.items())) or "nessuna"))
    _, s = leggi(os.path.join(REG, "sessioni.csv"))
    print(f"sessioni: {len(s)}")
    for r in s:
        print(f"   {r['unita']:18s} {r['sess']}  {r['eventi']} eventi  {r['metri']} m  v da {r['fonte_v']} ({r['qualita']})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("aggiungi")
    p.add_argument("--unita", required=True)
    p.add_argument("--dir", required=True, help="cartella con frenate.csv / sterzate.csv (soglie_dalle_guide.py)")
    p.add_argument("--fonte-v", required=True, help="encoder_ruota | ruota_ble | imu_video | gps")
    p.add_argument("--qualita", required=True, choices=("alta", "media", "bassa"))
    p.add_argument("--nota", default="")
    sp.add_parser("riepilogo")
    a = ap.parse_args()
    {"aggiungi": aggiungi, "riepilogo": riepilogo}[a.cmd](a)

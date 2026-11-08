#!/usr/bin/env python3
"""
palla.py — registro dei passaggi di palla agente → contro-agente (schema Groma, 2026-11-08).

Ogni deliverable passa da un contro-agente che lo guarda con una LENTE diversa. Nessun gate si chiude senza
il suo PASSA. Dopo 3 VETO sullo stesso artefatto il capo smette di girare in tondo e chiede a Daniele.

  passa    --verticale V --da PRODUTTORE --a CRITICO --artefatto PATH [--gate G] [--nota ...]
  verdetto --verticale V --critico CRITICO --artefatto PATH --esito PASSA|VETO [--gate G] [--nota ...]
  stato    [--verticale V]          palle aperte, giri, escalation

Un PASSA con --gate scrive la prova in agents/prove/<gate>.json (la legge stato.py per la lavagna).
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = HERE / "palla" / "registro.jsonl"
PROVE = HERE / "prove"
MAX_GIRI = 3


def leggi():
    if not REG.exists():
        return []
    return [json.loads(l) for l in REG.read_text().splitlines() if l.strip()]


def scrivi(ev):
    REG.parent.mkdir(exist_ok=True)
    ev["quando"] = datetime.now().isoformat(timespec="seconds")
    with open(REG, "a") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def stato(vert=None):
    palle = defaultdict(lambda: {"veto": 0, "ultimo": None})
    for ev in leggi():
        k = (ev["verticale"], ev["artefatto"])
        if ev["tipo"] == "verdetto" and ev["esito"] == "VETO":
            palle[k]["veto"] += 1
        palle[k]["ultimo"] = ev
    out = []
    for (v, art), p in palle.items():
        if vert and v != vert:
            continue
        u = p["ultimo"]
        if u["tipo"] == "verdetto" and u["esito"] == "PASSA":
            continue
        dove = f"da {u['critico']}" if u["tipo"] == "verdetto" else f"in mano a {u['a']}"
        esc = "  ⚠ ESCALATION A DANIELE" if p["veto"] >= MAX_GIRI else ""
        out.append(f"[{v}] {art} — {dove}, veto {p['veto']}/{MAX_GIRI}{esc}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["passa", "verdetto", "stato"])
    ap.add_argument("--verticale")
    ap.add_argument("--da"); ap.add_argument("--a"); ap.add_argument("--critico")
    ap.add_argument("--artefatto")
    ap.add_argument("--esito", choices=["PASSA", "VETO"])
    ap.add_argument("--gate")
    ap.add_argument("--nota", default="")
    a = ap.parse_args()

    if a.cmd == "stato":
        righe = stato(a.verticale)
        print("\n".join(righe) if righe else "nessuna palla aperta")
        return
    if a.cmd == "passa":
        assert a.verticale and a.da and a.a and a.artefatto, "servono --verticale --da --a --artefatto"
        scrivi({"tipo": "passa", "verticale": a.verticale, "da": a.da, "a": a.a,
                "artefatto": a.artefatto, "gate": a.gate, "nota": a.nota})
        print(f"palla da {a.da} a {a.a}: {a.artefatto}")
        return
    assert a.verticale and a.critico and a.artefatto and a.esito, "servono --verticale --critico --artefatto --esito"
    scrivi({"tipo": "verdetto", "verticale": a.verticale, "critico": a.critico, "artefatto": a.artefatto,
            "esito": a.esito, "gate": a.gate, "nota": a.nota})
    if a.esito == "PASSA" and a.gate:
        PROVE.mkdir(exist_ok=True)
        (PROVE / f"{a.gate}.json").write_text(json.dumps(
            {"gate": a.gate, "artefatto": a.artefatto, "visto_critico": a.critico, "nota": a.nota,
             "quando": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=1))
        print(f"PASSA — prova scritta per il gate {a.gate}")
    else:
        veti = sum(1 for e in leggi() if e["tipo"] == "verdetto" and e["artefatto"] == a.artefatto
                   and e["esito"] == "VETO")
        print(f"{a.esito} ({veti}/{MAX_GIRI} veto su questo artefatto)"
              + ("  ⚠ ESCALATION: il capo chiede a Daniele" if veti >= MAX_GIRI else ""))


if __name__ == "__main__":
    main()

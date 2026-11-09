#!/usr/bin/env python3
"""
palla.py — registro dei passaggi di palla agente → contro-agente (schema Groma, 2026-11-08).

Ogni deliverable passa da un contro-agente che lo guarda con una LENTE diversa. Nessun gate si chiude senza
il suo PASSA. Dopo 3 VETO sullo stesso artefatto il capo smette di girare in tondo e chiede a Daniele.

  passa    --verticale V --da PRODUTTORE --a CRITICO --artefatto PATH [--gate G] [--nota ...]
  verdetto --verticale V --critico CRITICO --artefatto PATH --esito PASSA|VETO [--gate G] [--nota ...]
  stato    [--verticale V]          palle aperte, giri, escalation
  lezioni  --da AGENTE              lezioni da mettere nel brief di AGENTE (sue + di Daniele)

Apprendimento (2026-11-09): ogni VETO scrive da solo la nota del critico in agents/lezioni/<produttore>.md;
il PASSA che segue la chiude come "risolto". Il capo apre ogni brief con `palla.py lezioni --da <agente>`,
così l'errore di ieri non si ripete. Le decisioni di Daniele vanno in agents/lezioni/daniele.md (le legge tutti).

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
LEZIONI = HERE / "lezioni"
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


def produttore(artefatto):
    """Chi ha fatto l'artefatto: l'ultimo `passa` registrato su quel path."""
    passi = [e for e in leggi() if e["tipo"] == "passa" and e["artefatto"] == artefatto]
    return passi[-1]["da"] if passi else None


def impara(a):
    """VETO → lezione per il produttore; PASSA dopo almeno un VETO → la lezione risulta risolta."""
    chi = produttore(a.artefatto)
    if not chi:
        return
    veti = [e for e in leggi() if e["tipo"] == "verdetto" and e["artefatto"] == a.artefatto and e["esito"] == "VETO"]
    if a.esito == "PASSA" and not veti:
        return
    LEZIONI.mkdir(exist_ok=True)
    f = LEZIONI / f"{chi}.md"
    if not f.exists():
        f.write_text(f"# Lezioni di {chi}\n\nScritte da palla.py dai VETO dei contro-agenti. Leggile prima di ogni lavoro.\n\n")
    oggi = datetime.now().strftime("%Y-%m-%d")
    riga = (f"- {oggi} **VETO** di {a.critico} su `{a.artefatto}`" + (f" (gate {a.gate})" if a.gate else "")
            + f": {a.nota}\n") if a.esito == "VETO" else \
           f"  - {oggi} risolto: PASSA di {a.critico} dopo {len(veti)} veto. {a.nota[:200]}\n"
    with open(f, "a") as fh:
        fh.write(riga)


def lezioni(chi):
    out = []
    for nome in (chi, "daniele"):
        f = LEZIONI / f"{nome}.md"
        if f.exists():
            out.append(f.read_text().strip())
    return "\n\n".join(out) if out else f"nessuna lezione per {chi}"


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
    ap.add_argument("cmd", choices=["passa", "verdetto", "stato", "lezioni"])
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
    if a.cmd == "lezioni":
        assert a.da, "serve --da AGENTE"
        print(lezioni(a.da))
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
    impara(a)
    parziale = "PARZIALE" in a.nota.upper() or "NON CHIUSO" in a.nota.upper()
    if a.esito == "PASSA" and a.gate and parziale:
        print(f"PASSA sul rapporto PARZIALE — il gate {a.gate} resta aperto (nessuna prova scritta)")
    elif a.esito == "PASSA" and a.gate:
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

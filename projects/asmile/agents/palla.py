#!/usr/bin/env python3
"""
palla.py — registro dei passaggi di palla agente → contro-agente (schema Groma, 2026-11-08).

Ogni deliverable passa da un contro-agente che lo guarda con una LENTE diversa. Nessun gate si chiude senza
il suo PASSA. Dopo 3 VETO sullo stesso artefatto il capo smette di girare in tondo e chiede a Daniele.

  passa    --verticale V --da PRODUTTORE --a CRITICO --artefatto PATH [--gate G] [--nota ...]
  verdetto --verticale V --critico CRITICO --artefatto PATH --esito PASSA|VETO [--gate G] [--parziale] [--nota ...]
  stato    [--verticale V]          palle aperte, giri, escalation
  lezioni  --da AGENTE              lezioni da mettere nel brief di AGENTE (sue + di Daniele + sue ultime decisioni)
  decido   --da AGENTE --cosa ... --scelta ... --perche ... [--scartato ...] [--evidenza PATH] [--verticale V]
                                    registro delle DECISIONI (scelte prese e perché, alternative scartate)
  bilancio --da AGENTE --giusto "..." --sbagliato "..." (ripetibili) [--artefatto PATH]
                                    autoapprendimento: cosa è andato bene e cosa male, in agents/lezioni/<agente>.md

Decisioni (2026-11-10, Daniele): ogni agente registra OGNI scelta non ovvia mentre lavora (non a fine lavoro):
agents/decisioni/<agente>.md + riga tipo "decisione" nel registro. Si committa su git: serve a imparare e a non
rifare gli stessi errori. Il brief (`lezioni`) riporta le ultime decisioni dell'agente.

Apprendimento (2026-11-09): ogni VETO scrive da solo la nota del critico in agents/lezioni/<produttore>.md;
il PASSA che segue la chiude come "risolto". Il capo apre ogni brief con `palla.py lezioni --da <agente>`,
così l'errore di ieri non si ripete. Le decisioni di Daniele vanno in agents/lezioni/daniele.md (le legge tutti).

Autoapprendimento (2026-11-11, Daniele): ogni lavoro si chiude con un BILANCIO (giusto/sbagliato) scritto in
agents/lezioni/<agente>.md. `passa` lo pretende: rifiuta se il produttore non ha fatto un bilancio dopo la sua palla
precedente (o non passa --giusto/--sbagliato in linea). Così le lezioni si scrivono da sole a ogni giro, non a richiesta.

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
DECISIONI = HERE / "decisioni"
N_DECISIONI_BRIEF = 15
MAX_GIRI = 3


def leggi():
    if not REG.exists():
        return []
    evs = [json.loads(l) for l in REG.read_text().splitlines() if l.strip()]
    for ev in evs:  # stesso artefatto scritto con o senza prefisso projects/asmile/
        if isinstance(ev.get("artefatto"), str) and ev["artefatto"].startswith("projects/asmile/"):
            ev["artefatto"] = ev["artefatto"][len("projects/asmile/"):]
    return evs


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


def decido(a):
    DECISIONI.mkdir(exist_ok=True)
    f = DECISIONI / f"{a.da}.md"
    if not f.exists():
        f.write_text(f"# Decisioni di {a.da}\n\nScritte con `palla.py decido` mentre lavora. Append-only: "
                     "una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.\n\n")
    ora = datetime.now().strftime("%Y-%m-%d %H:%M")
    riga = f"- {ora} **{a.cosa}** → {a.scelta}. Perché: {a.perche}."
    if a.scartato:
        riga += f" Scartato: {a.scartato}."
    if a.evidenza:
        riga += f" Evidenza: `{a.evidenza}`."
    with open(f, "a") as fh:
        fh.write(riga + "\n")
    scrivi({"tipo": "decisione", "verticale": a.verticale or "", "da": a.da, "artefatto": a.evidenza or "",
            "cosa": a.cosa, "scelta": a.scelta, "perche": a.perche, "scartato": a.scartato or ""})


def bilancio(chi, giusti, sbagliati, artefatto=None):
    LEZIONI.mkdir(exist_ok=True)
    f = LEZIONI / f"{chi}.md"
    if not f.exists():
        f.write_text(f"# Lezioni di {chi}\n\nScritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.\n\n")
    oggi = datetime.now().strftime("%Y-%m-%d")
    dove = f" (`{artefatto}`)" if artefatto else ""
    with open(f, "a") as fh:
        for g in giusti:
            fh.write(f"- {oggi} GIUSTO{dove}: {g}\n")
        for b in sbagliati:
            fh.write(f"- {oggi} SBAGLIATO{dove}: {b}\n")
    scrivi({"tipo": "bilancio", "verticale": "", "da": chi, "artefatto": artefatto or "",
            "giusto": giusti, "sbagliato": sbagliati})


def ha_bilancio(chi):
    """True se `chi` ha scritto un bilancio dopo la sua ultima palla passata (o non ha mai passato palle)."""
    evs = [e for e in leggi() if e.get("da") == chi and e.get("tipo") in ("passa", "bilancio")]
    passi = [i for i, e in enumerate(evs) if e["tipo"] == "passa"]
    ultimo = passi[-1] if passi else -1
    return any(e["tipo"] == "bilancio" for e in evs[ultimo + 1:])


def lezioni(chi):
    out = []
    for nome in (chi, "daniele"):
        f = LEZIONI / f"{nome}.md"
        if f.exists():
            out.append(f.read_text().strip())
    f = DECISIONI / f"{chi}.md"
    if f.exists():
        righe = [l for l in f.read_text().splitlines() if l.startswith("- ")]
        out.append(f"# Ultime decisioni di {chi}\n" + "\n".join(righe[-N_DECISIONI_BRIEF:]))
    return "\n\n".join(out) if out else f"nessuna lezione per {chi}"


def stato(vert=None):
    palle = defaultdict(lambda: {"veto": 0, "ultimo": None})
    for ev in leggi():
        if ev.get("tipo") not in ("passa", "verdetto"):
            continue  # le decisioni (palla.py decido) non sono palle
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
    ap.add_argument("cmd", choices=["passa", "verdetto", "stato", "lezioni", "decido", "bilancio"])
    ap.add_argument("--verticale")
    ap.add_argument("--da"); ap.add_argument("--a"); ap.add_argument("--critico")
    ap.add_argument("--artefatto")
    ap.add_argument("--esito", choices=["PASSA", "VETO"])
    ap.add_argument("--gate")
    ap.add_argument("--nota", default="")
    ap.add_argument("--cosa"); ap.add_argument("--scelta"); ap.add_argument("--perche")
    ap.add_argument("--scartato"); ap.add_argument("--evidenza")
    ap.add_argument("--giusto", action="append", default=[], help="bilancio: cosa è andato bene (ripetibile)")
    ap.add_argument("--sbagliato", action="append", default=[], help="bilancio: cosa è andato male (ripetibile)")
    ap.add_argument("--parziale", action="store_true",
                    help="PASSA sul rapporto ma il gate resta aperto (nessuna prova scritta)")
    a = ap.parse_args()

    if a.cmd == "stato":
        righe = stato(a.verticale)
        print("\n".join(righe) if righe else "nessuna palla aperta")
        return
    if a.cmd == "lezioni":
        assert a.da, "serve --da AGENTE"
        print(lezioni(a.da))
        return
    if a.cmd == "decido":
        assert a.da and a.cosa and a.scelta and a.perche, "servono --da --cosa --scelta --perche"
        decido(a)
        print(f"decisione registrata: agents/decisioni/{a.da}.md")
        return
    if a.cmd == "bilancio":
        assert a.da and (a.giusto or a.sbagliato), "servono --da e almeno un --giusto o --sbagliato"
        bilancio(a.da, a.giusto, a.sbagliato, a.artefatto)
        print(f"bilancio registrato: agents/lezioni/{a.da}.md")
        return
    if a.cmd == "passa":
        assert a.verticale and a.da and a.a and a.artefatto, "servono --verticale --da --a --artefatto"
        if a.giusto or a.sbagliato:
            bilancio(a.da, a.giusto, a.sbagliato, a.artefatto)
        elif not ha_bilancio(a.da):
            raise SystemExit(f"RIFIUTO: {a.da} non ha scritto il bilancio di questo lavoro. Prima:\n"
                             f"  palla.py bilancio --da {a.da} --giusto \"...\" --sbagliato \"...\" --artefatto {a.artefatto}\n"
                             "oppure aggiungi --giusto/--sbagliato a questo passa (anche 'niente di sbagliato' va scritto).")
        scrivi({"tipo": "passa", "verticale": a.verticale, "da": a.da, "a": a.a,
                "artefatto": a.artefatto, "gate": a.gate, "nota": a.nota})
        print(f"palla da {a.da} a {a.a}: {a.artefatto}")
        return
    assert a.verticale and a.critico and a.artefatto and a.esito, "servono --verticale --critico --artefatto --esito"
    scrivi({"tipo": "verdetto", "verticale": a.verticale, "critico": a.critico, "artefatto": a.artefatto,
            "esito": a.esito, "gate": a.gate, "nota": a.nota})
    impara(a)
    parziale = a.parziale
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

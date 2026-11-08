#!/usr/bin/env python3
"""
avvisa.py — l'orchestratore (asmile-capo) parla a Daniele in modo semplice (2026-11-08).

  info  "testo"                         apre un Terminale sul Mac col messaggio (niente attesa)
  chiedi "domanda" [--opzioni "a|b"]    apre un Terminale, aspetta la risposta; se non arriva entro --attesa
                                        minuti scrive a Daniele su Telegram (Doppio) e stampa NESSUNA
  fai   "accendi asmile #001" --perche "..."   come chiedi, ma è un'azione FISICA (risposta: fatto / non ora / ...)
  leggi ID                              stampa la risposta arrivata dopo (o NESSUNA)

Ogni messaggio finisce in agents/registro_avvisi.md. Le domande vivono in agents/inbox/ (fuori da git).
Telegram passa da ~/progetti/doppio/telegram-brain/scrivi_a_daniele.py (solo verso Daniele, protocollo
~/progetti/CONTATTI-ESTERNI.md). Uso interno: --rispondi ID gira dentro il Terminale aperto.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
INBOX = HERE / "inbox"
REGISTRO = HERE / "registro_avvisi.md"
DOPPIO = Path.home() / "progetti/doppio/telegram-brain"
DOPPIO_PY = Path.home() / "progetti/council/doppio/telegram-brain/.venv/bin/python"


def registra(tipo, testo, extra=""):
    nuovo = not REGISTRO.exists()
    with open(REGISTRO, "a", encoding="utf-8") as f:
        if nuovo:
            f.write("# Registro avvisi a Daniele (asmile-capo)\n\n")
        f.write(f"- {datetime.now():%Y-%m-%d %H:%M} **{tipo}** — {testo}{' · ' + extra if extra else ''}\n")


def apri_terminale(cmd):
    """Apre una finestra del Terminale del Mac che esegue cmd (e la porta in primo piano)."""
    esc = cmd.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e", f'tell application "Terminal" to do script "{esc}"',
                    "-e", 'tell application "Terminal" to activate'], capture_output=True)


def telegram(motivo, chiedi):
    py = DOPPIO_PY if DOPPIO_PY.exists() else Path(sys.executable)
    r = subprocess.run([str(py), str(DOPPIO / "scrivi_a_daniele.py"), "--agente", "Asmile capo",
                        "--progetto", "asmile", "--motivo", motivo, "--chiedi", chiedi],
                       capture_output=True, text=True, cwd=DOPPIO)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def nuova_domanda(tipo, testo, opzioni, perche):
    INBOX.mkdir(exist_ok=True)
    qid = datetime.now().strftime("%Y%m%d_%H%M%S")
    q = {"id": qid, "tipo": tipo, "testo": testo, "opzioni": opzioni, "perche": perche,
         "creata": datetime.now().isoformat(timespec="seconds")}
    (INBOX / f"{qid}.json").write_text(json.dumps(q, ensure_ascii=False, indent=1))
    return qid


def risposta(qid):
    p = INBOX / f"{qid}.risposta"
    return p.read_text().strip() if p.exists() else None


def aspetta(qid, minuti):
    fine = time.time() + minuti * 60
    while time.time() < fine:
        r = risposta(qid)
        if r is not None:
            return r
        time.sleep(5)
    return None


def rispondi(qid):
    """Gira DENTRO il Terminale aperto: mostra il messaggio e raccoglie la risposta di Daniele."""
    q = json.loads((INBOX / f"{qid}.json").read_text())
    print("\n" + "=" * 64)
    print("  ASMILE — il capo ti scrive" + ("  (azione fisica)" if q["tipo"] == "fai" else ""))
    print("=" * 64 + "\n")
    print("  " + q["testo"].replace("\n", "\n  "))
    if q.get("perche"):
        print("\n  Perché: " + q["perche"])
    if q["tipo"] == "info":
        input("\n  (premi Invio per chiudere) ")
        return
    ops = q.get("opzioni") or (["fatto", "non ora"] if q["tipo"] == "fai" else [])
    if ops:
        print()
        for i, o in enumerate(ops, 1):
            print(f"   {i}) {o}")
        print("   oppure scrivi quello che vuoi")
    r = input("\n  La tua risposta: ").strip()
    if r.isdigit() and ops and 1 <= int(r) <= len(ops):
        r = ops[int(r) - 1]
    (INBOX / f"{qid}.risposta").write_text(r or "(vuota)")
    registra("risposta", f"[{qid}] {r or '(vuota)'}")
    print("\n  Grazie 🙏 — ricevuto. Puoi chiudere questa finestra.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["info", "chiedi", "fai", "leggi"])
    ap.add_argument("testo", nargs="?")
    ap.add_argument("--opzioni", default="", help="opzioni separate da |")
    ap.add_argument("--perche", default="")
    ap.add_argument("--attesa", type=float, default=10, help="minuti di attesa prima di Telegram")
    ap.add_argument("--rispondi", metavar="ID")
    a = ap.parse_args()

    if a.rispondi:
        return rispondi(a.rispondi)
    if a.cmd == "leggi":
        print(risposta(a.testo) or "NESSUNA")
        return
    if not a.cmd or not a.testo:
        ap.error("serve un comando e un testo")

    ops = [o.strip() for o in a.opzioni.split("|") if o.strip()]
    qid = nuova_domanda(a.cmd, a.testo, ops, a.perche)
    registra(a.cmd, a.testo, a.perche)
    apri_terminale(f"python3 '{Path(__file__).resolve()}' --rispondi {qid}; exit")
    if a.cmd == "info":
        print(f"avviso mostrato [{qid}]")
        return
    r = aspetta(qid, a.attesa)
    if r is not None:
        print(f"RISPOSTA [{qid}]: {r}")
        return
    cosa = ("Azione fisica: " if a.cmd == "fai" else "") + a.testo
    ok, out = telegram(a.perche or "ti ho scritto nel Terminale del Mac ma non hai risposto",
                       cosa + (f" (opzioni: {' / '.join(ops)})" if ops else "")
                       + " — rispondi nel Terminale aperto sul Mac.")
    registra("telegram", f"[{qid}] {'inviato' if ok else 'NON inviato: ' + out[:120]}")
    print(f"NESSUNA [{qid}] — {'avvisato su Telegram' if ok else 'Telegram fallito: ' + out[:200]}")
    print(f"rileggi dopo con: python3 {Path(__file__).name} leggi {qid}")


if __name__ == "__main__":
    main()

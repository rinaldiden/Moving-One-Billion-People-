#!/usr/bin/env python3
"""
stato.py — la LAVAGNA di asmile #001: a che livello siamo, cosa manca, chi ci lavora, cosa deve fare Daniele
(2026-11-08). Deterministico: niente LLM. Lo lancia asmile-capo all'inizio di ogni giro.

Scala di autonomia (ogni livello si sblocca solo con TUTTI i gate del precedente + firma di Daniele):
  L0 registra · L1 ombra · L2 freno di sicurezza · L3 sterzo assistito · L4 autonomia su percorso

Un gate è FATTO solo se:
  - c'è una prova in agents/prove/<gate>.json scritta da palla.py con il PASSA del contro-agente, e
    l'artefatto a cui punta esiste ancora; oppure
  - un controllo automatico qui sotto lo verifica sui file veri.
Altrimenti è MANCA (o DA VERIFICARE se serve un controllo che da qui non si può fare).

Scrive: ../.collegio/001_LAVAGNA.md (per Daniele, linguaggio semplice) + agents/stato.json (per il capo).
NON scrive mai nel DECISION_LOG: le firme sono solo di Daniele.
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASMILE = HERE.parent
PROVE = HERE / "prove"
LAVAGNA = ASMILE / ".collegio" / "001_LAVAGNA.md"
STATO = HERE / "stato.json"
DLOG = ASMILE / ".collegio" / "DECISION_LOG.md"
LOGGERS = ASMILE / "asmile-loggers"

# gate: (id, livello, cosa, verticale, agente, contro-agente, azione fisica per Daniele o None)
GATES = [
    ("L0.sync_001", 0, "Camere di #001 sincronizzate anche nei video in movimento", "veicolo",
     "asmile-pi-001", "asmile-pi-001-verifica", "accendi asmile #001 e fai un giro di 5 minuti"),
    ("L0.sensori_001", 0, "sensor_hub a 50 Hz attivo su #001 (camere+sensori stesso ms)", "veicolo",
     "asmile-pi-001", "asmile-pi-001-verifica", "accendi asmile #001 (interruttore OFF, solo Pi)"),
    ("L0.encoder_ruota", 0, "Encoder ruota tarato (velocità e accelerazione giuste)", "veicolo",
     "asmile-pi-001", "asmile-pi-001-verifica", None),
    ("L0.calib_logger", 0, "Calibrazione stereo del logger col metro (±2% da fermi)", "percezione",
     "asmile-calib", "asmile-calib-critico", None),
    ("L0.calib_001", 0, "Calibrazione stereo di #001 col metro (±2% da fermi, 1-15 m)", "percezione",
     "asmile-calib", "asmile-calib-critico", "video col metro con #001: soste a 1-2-3-5-7-10-15 m"),
    ("L0.dati", 0, "Video nuovi scaricati, controllati e indicizzati", "dati",
     "asmile-logger-ingest", "asmile-ingest-critico", None),
    ("L1.banco_fisso", 1, "Banco di misura fisso: punti col metro MAI usati nel fit (4-6-8-12 m) + oggetti reali",
     "percezione", "asmile-calib", "asmile-calib-critico", "video col metro a 4, 6, 8, 12 m (logger e #001)"),
    ("L1.rettifica", 1, "Rettifica vera: scarto verticale L-R < 1 px su tutta l'immagine, anche in movimento",
     "percezione", "asmile-calib", "asmile-calib-critico", None),
    ("L1.depth_moto", 1, "Depth in movimento: ±2% <5 m, ±5% 5-10 m, ±10% 10-20 m sul banco fisso",
     "percezione", "asmile-depth", "asmile-occhio", None),
    ("L1.ostacoli", 1, "Ostacoli SENZA nome nel corridoio davanti (depth densa / occupazione)",
     "percezione", "asmile-depth", "asmile-occhio", None),
    ("L1.ttc", 1, "Tracking + filtro: distanza, velocità di avvicinamento e tempo-al-contatto stabili",
     "percezione", "asmile-depth", "asmile-occhio", None),
    ("L1.classi", 1, "SAM 3 vede cancelli, griglie, catene, dossi (test: rientro logger frame ~1500)",
     "percezione", "asmile-seg-segmenter", "asmile-seg-verifier", None),
    ("L1.ombra_5", 1, "5 sessioni in OMBRA su #001: percezione+decisione calcolate, non agite, confrontate con Daniele",
     "guida", "asmile-sim-validator", "asmile-regressione", "5 giri normali con #001 (ombra attiva)"),
    ("L2.freno_bam", 2, "Modello del freno (BAM): gradini ≤60° a 10-15 km/h, decelerazione da encoder",
     "attuazione", "asmile-actuator-modeler", "asmile-attuatori-avversario",
     "test freno in strada chiusa: gradini di freno a 10-15 km/h (protocollo del banco-hw)"),
    ("L2.freno_limite", 2, "Freno mai oltre 60° garantito nel codice (speed_limiter unico padrone GPIO12)",
     "governo", "asmile-sicurezza", "asmile-sicurezza-redteam", None),
    ("L2.watchdog", 2, "Watchdog indipendente + disco in sola lettura su #001 (ferma e torna al noto-buono)",
     "veicolo", "asmile-deploy", "asmile-rollback-guardian", None),
    ("L2.redteam", 2, "Red team di sicurezza superato sul freno automatico", "governo",
     "asmile-sicurezza", "asmile-sicurezza-redteam", None),
    ("L3.sterzo_limiti", 3, "Centro e finecorsa sterzo di #001 misurati", "attuazione",
     "asmile-banco-hw", "asmile-banco-critico", "su #001: sterzo a mano tutto sx/dx con calibrate_steering_limits.py"),
    ("L3.sterzo_bam", 3, "Modello dello sterzo (BAM) VESC + Speed PID configurato", "attuazione",
     "asmile-actuator-modeler", "asmile-attuatori-avversario", "porta il laptop: VESC Tool per lo Speed PID"),
    ("L3.ombra_sterzo", 3, "5 sessioni in ombra dello sterzo", "guida",
     "asmile-sim-validator", "asmile-regressione", "5 giri con #001 (ombra sterzo attiva)"),
    ("L4.sim2real", 4, "Policy validata in sim + banco virtuale senza regressioni", "guida",
     "asmile-sim-validator", "asmile-regressione", None),
]
FIRME_LIVELLO = {1: "L1", 2: "L2", 3: "L3", 4: "L4"}   # firma di Daniele per entrare nel livello (DECISION_LOG)


def sh(cmd, cwd=ASMILE):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return ""


def prova(gid):
    p = PROVE / f"{gid}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    art = d.get("artefatto", "")
    if art and not (ASMILE / art).exists() and not Path(art).exists():
        return None                                     # l'artefatto è sparito: la prova non vale più
    return d


def auto(gid):
    """Controlli automatici sui file veri. Ritorna (stato, prova) o None se non c'è un controllo."""
    if gid == "L0.calib_logger":
        p = ASMILE / "logger/depth/calib_asmile-logger_metro.json"
        if p.exists():
            pts = json.loads(p.read_text()).get("tape_points", [])
            errs = [abs(t["Z_stereo_m"] - t["Z_m"]) / t["Z_m"] for t in pts if t.get("Z_stereo_m")]
            if errs and max(errs) <= 0.025:
                return "FATTO", f"{p.name}: errore max {100 * max(errs):.1f}% su {len(errs)} soste (fermo)"
            return "MANCA", f"{p.name}: errore max {100 * max(errs):.1f}%" if errs else "nessuna sosta col metro"
    if gid == "L0.calib_001":
        p = ASMILE / "logger/depth/calib_asmile-001.json"
        if p.exists() and json.loads(p.read_text()).get("tape_points"):
            return "DA VERIFICARE", f"{p.name} ha soste col metro: serve il visto di asmile-calib-critico"
        return "MANCA", "calib di #001 senza soste col metro (d0 provvisorio)"
    if gid == "L0.dati":
        nuovi = video_non_lavorati()
        return ("FATTO", "nessun video in attesa") if not nuovi else ("MANCA", f"{len(nuovi)} sessioni da lavorare")
    return None


def video_non_lavorati():
    fatti = {p.name for d in ("_seg_sam3", "_seg") if (LOGGERS / d).exists() for p in (LOGGERS / d).iterdir()}
    out = []
    for unit in ("asmile-001", "asmile-logger"):
        d = LOGGERS / unit
        if d.exists():
            for s in d.iterdir():
                if s.is_dir() and s.name.startswith(("session_", "calib_")) and s.name not in fatti:
                    out.append(f"{unit}/{s.name}")
    return sorted(out)


def firme():
    txt = DLOG.read_text() if DLOG.exists() else ""
    blocchi = re.split(r"\n## ", txt)
    da_firmare = [b.split("\n")[0][:70] for b in blocchi[1:] if re.search(r"\*\*Firma:\*\*\s*_{3,}", b)]
    return da_firmare


def pi_raggiungibile():
    out = sh(["tailscale", "status"])
    return {n: (n in out and "offline" not in next((l for l in out.splitlines() if n in l), ""))
            for n in ("asmile-001", "asmile-logger")} if out else {}


def main():
    righe, gates = [], []
    for gid, liv, cosa, vert, ag, crit, fisico in GATES:
        st, pr = "MANCA", ""
        d = prova(gid)
        if d:
            st, pr = "FATTO", f"{d['artefatto']} (visto {d['visto_critico']}, {d['quando'][:10]})"
        else:
            r = auto(gid)
            if r:
                st, pr = r
        gates.append({"id": gid, "livello": liv, "cosa": cosa, "verticale": vert, "agente": ag,
                      "contro_agente": crit, "fisico": fisico, "stato": st, "prova": pr})

    livello = -1
    for L in range(5):
        if all(g["stato"] == "FATTO" for g in gates if g["livello"] == L):
            livello = L
        else:
            break
    prossimo = livello + 1
    aperti = [g for g in gates if g["livello"] == prossimo and g["stato"] != "FATTO"]
    fisiche = [g for g in aperti if g["fisico"]]
    stato = {"quando": datetime.now().isoformat(timespec="seconds"), "livello": livello, "prossimo": prossimo,
             "gates": gates, "aperti": [g["id"] for g in aperti], "azioni_fisiche": [g["fisico"] for g in fisiche],
             "video_non_lavorati": video_non_lavorati(), "da_firmare": firme(), "pi": pi_raggiungibile(),
             "git_sporco": bool(sh(["git", "status", "--porcelain", "."]).strip())}
    STATO.write_text(json.dumps(stato, ensure_ascii=False, indent=1))

    nomi = ["registra", "ombra", "freno di sicurezza", "sterzo assistito", "autonomia su percorso"]
    L = [f"# Lavagna asmile #001 — {datetime.now():%Y-%m-%d %H:%M}", "",
         f"**Livello raggiunto:** {'nessuno' if livello < 0 else f'L{livello} ({nomi[livello]})'}  ·  "
         f"**Stiamo lavorando per:** L{prossimo} ({nomi[min(prossimo, 4)]})", ""]
    if fisiche:
        L += ["## Cosa serve da te (parte fisica)"] + [f"- {g['fisico']}  ← per: {g['cosa']}" for g in fisiche] + [""]
    L += ["## Gate", "", "| | gate | cosa | chi → contro-agente | prova |", "|---|---|---|---|---|"]
    icona = {"FATTO": "✅", "MANCA": "⬜", "DA VERIFICARE": "🟡"}
    for g in gates:
        L.append(f"| {icona[g['stato']]} | {g['id']} | {g['cosa']} | {g['agente']} → {g['contro_agente']} | {g['prova']} |")
    L += ["", f"**Video da lavorare:** {len(stato['video_non_lavorati'])}  ·  "
          f"**Decisioni da firmare:** {len(stato['da_firmare'])}  ·  "
          f"**Pi online:** {', '.join(k for k, v in stato['pi'].items() if v) or 'nessuno'}", "",
          "_Generata da projects/asmile/agents/stato.py — non modificarla a mano._"]
    LAVAGNA.write_text("\n".join(L) + "\n")
    print(f"livello L{livello} → lavoro per L{prossimo}; aperti {len(aperti)}; azioni fisiche {len(fisiche)}")
    for g in aperti:
        print(f"  {icona[g['stato']]} {g['id']:<18s} {g['agente']} → {g['contro_agente']}")
    if fisiche:
        print("DA DANIELE: " + " | ".join(g["fisico"] for g in fisiche))


if __name__ == "__main__":
    main()

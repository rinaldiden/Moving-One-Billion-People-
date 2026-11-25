#!/usr/bin/env python3
"""Regola la sensibilita' del freno di #001 cambiando le variabili del loop decel-velocita' (Daniele 25/11).

Senza argomenti: mostra i valori in uso sul Pi.
Con argomenti nome=valore: li scrive nel file soglie del repo E sul Pi (live + /media/root-ro), controlla che il limiter
accetti il file (validazione sul Pi) e registra in deploy/freno_regola.log. Vale al prossimo interruttore OFF->ON.

  python3 deploy/freno_regola.py                         # cosa c'e' adesso
  python3 deploy/freno_regola.py chiude=8 apre=50        # piu' pronto a chiudere e ad aprire
  python3 deploy/freno_regola.py vmax=12 zona=10 obiettivo=11

Variabili (nome corto -> chiave):
  vmax       velocita' oltre cui frena piu' deciso (km/h)
  zona       velocita' da cui comincia a frenare (km/h)
  obiettivo  velocita' attorno a cui lavora (km/h), fra zona e vmax
  attesa_da  quanti km/h sotto la zona si mette in attesa vicino al morso
  attesa     angolo di attesa (gradi) = contatto_min - margine: si cambia con attesa=<gradi>
  chiude     gradi/s di chiusura per ogni km/h sopra l'obiettivo          (piu' alto = risponde prima alla velocita')
  chiude_max gradi/s massimi di chiusura                                   (piu' alto = piu' brusco)
  apre       gradi/s di rilascio per ogni m/s2 di decel oltre dec_ok      (piu' alto = molla prima)
  dec_ok     decel oltre cui comincia a rilasciare (m/s2)
  filtro_v   secondi di media della velocita' (una pedalata)
  apre_max   gradi/s massimi di apertura
  ritardo    secondi di anticipo sulla velocita' (rilascia prima di scendere sotto la zona)
  normale    decel voluta in zona (m/s2)
  forte      decel voluta sopra vmax (m/s2)
"""
import json, os, subprocess, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(QUI, "..", "config", "soglie_speed_limiter_v3.json")
LOG = os.path.join(QUI, "freno_regola.log")
H = "asmile@100.75.198.118"
R = "/home/asmile/wip/Moving-One-Billion-People-/projects/asmile"
F = "config/soglie_speed_limiter_v3.json"

MAPPA = {
    "vmax": ("velocita", "v_max_kmh"), "zona": ("velocita", "zona_inizio_kmh"),
    "obiettivo": ("regolatore", "v_obiettivo_kmh"), "attesa_da": ("regolatore", "ingaggio_sotto_zona_kmh"),
    "chiude": ("regolatore", "incrementale", "k_v_deg_s_per_kmh"), "riapre": ("regolatore", "incrementale", "k_v_giu_deg_s_per_kmh"), "chiude_max": ("regolatore", "incrementale", "su_max_deg_s"), "avvicina": ("regolatore", "incrementale", "avvicinamento_deg_s"),
    "apre": ("regolatore", "incrementale", "k_dec_deg_s_per_ms2"), "apre_max": ("regolatore", "incrementale", "giu_max_deg_s"),
    "filtro_v": ("regolatore", "incrementale", "v_filtro_s"), "dec_ok": ("regolatore", "incrementale", "dec_ok_ms2"),
    "ritardo": ("freno", "ritardo_comando_decel_s"),
    "normale": ("decel_obiettivo_ms2", "normale"), "forte": ("decel_obiettivo_ms2", "forte"),
}


def leggi(c, k):
    for p in k:
        c = c[p]
    return c


def scrivi(c, k, v):
    for p in k[:-1]:
        c = c[p]
    c[k[-1]] = v


def mostra(c):
    for n, k in MAPPA.items():
        print(f"  {n:11s} = {leggi(c, k)}")
    f = c["freno"]
    print(f"  {'attesa':11s} = {f['contatto_min_deg'] - f['margine_contatto_deg']}  (gradi, da {c['velocita']['zona_inizio_kmh'] - c['regolatore']['ingaggio_sotto_zona_kmh']} km/h)")


def main():
    args = sys.argv[1:]
    if not args:
        out = subprocess.run(["ssh", "-o", "BatchMode=yes", H, f"cat {R}/{F}"], capture_output=True, text=True, timeout=20)
        print("Sul Pi adesso:")
        mostra(json.loads(out.stdout))
        return
    c = json.load(open(CFG))
    cambi = []
    for a in args:
        n, v = a.split("=", 1)
        v = float(v)
        if n == "attesa":                        # attesa = contatto_min - margine: sposto contatto_min, margine invariato
            f = c["freno"]
            vecchio = f["contatto_min_deg"] - f["margine_contatto_deg"]
            f["contatto_min_deg"] = v + f["margine_contatto_deg"]
            f["contatto_default_deg"] = max(f["contatto_default_deg"], f["contatto_min_deg"])
        elif n in MAPPA:
            vecchio = leggi(c, MAPPA[n])
            scrivi(c, MAPPA[n], v)
        else:
            sys.exit(f"variabile sconosciuta: {n} (vedi --help in testa al file)")
        cambi.append(f"{n} {vecchio} -> {v}")
    json.dump(c, open(CFG, "w"), indent=1, ensure_ascii=False)
    open(CFG, "a").write("\n")
    # controllo sul Mac che il limiter accetterebbe il file (se no sul Pi non parte)
    chk = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0,'.'); from speed_limiter_v3.controllo import carica_soglie; carica_soglie()"],
                         cwd=os.path.join(QUI, "..", "pi", "autonomous"), capture_output=True, text=True)
    if chk.returncode:
        subprocess.run(["git", "checkout", "--", CFG], cwd=QUI)
        sys.exit("RIFIUTATO dalla validazione, niente caricato:\n" + chk.stderr.strip().splitlines()[-1])
    subprocess.run(["scp", "-q", CFG, f"{H}:/tmp/soglie_regola.json"], check=True, timeout=30)
    sh = (f"set -e; mount -o remount,rw /media/root-ro; for b in {R} /media/root-ro{R}; do cp /tmp/soglie_regola.json $b/{F}; done; "
          f"sync; mount -o remount,ro /media/root-ro; cd {R}/pi/autonomous && python3 -c \"import sys; sys.path.insert(0,'.'); "
          f"from speed_limiter_v3.controllo import carica_soglie; carica_soglie(); print('VALIDA sul Pi')\"")
    tmp = "/tmp/freno_regola_run.sh"
    open(tmp, "w").write(sh + "\n")
    subprocess.run(["scp", "-q", tmp, f"{H}:/tmp/freno_regola_run.sh"], check=True, timeout=30)
    subprocess.run(["ssh", "-o", "BatchMode=yes", H, "echo asmile | sudo -S -p '' bash /tmp/freno_regola_run.sh"], check=True, timeout=40)
    riga = time.strftime("%Y-%m-%d %H:%M:%S ") + "; ".join(cambi)
    open(LOG, "a").write(riga + "\n")
    print(riga)
    print("Caricato. Vale all'interruttore OFF -> ON.")


if __name__ == "__main__":
    main()

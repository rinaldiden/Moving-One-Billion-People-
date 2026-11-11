#!/usr/bin/env python3
"""Genera il PDF del protocollo di calibrazione di asmile-logger001 (un solo set di video), dalle lezioni di #001 (2026-11-11).
Geometria logger: Camarray SBS 2x1280x800, f ~935 px, baseline 200 mm, camere a 0.77 m (DA RIMISURARE), pitch da misurare."""
import math, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

F, W, H, B, HC = 935.0, 1280, 800, 0.20, 0.77
OUT = __file__.replace("genera_pdf_calib_logger001.py", "protocollo_calib_logger001.pdf")

def zona(Z):
    """Centri delle 9 zone (lato dal centro fra le lenti, altezza del centro tabellone) con il tabellone visto da ENTRAMBE le camere."""
    hw, hh = Z * (W / 2) / F, Z * (H / 2) / F
    t = hw / 3                                     # confine dei terzi attorno all'asse di ogni camera
    # zona sinistra comune: [-(hw - B/2), -(t + B/2)] ; destra simmetrica
    lat = ((hw - B / 2) + (t + B / 2)) / 2
    ty = hh / 3; alt = (hh + ty) / 2
    return round(lat, 2), [max(0.20, round(HC - alt, 2)), HC, round(HC + alt, 2)]

def pagina(pdf, titolo, righe, size=10.5):
    fig = plt.figure(figsize=(8.27, 11.69)); fig.text(0.07, 0.95, titolo, fontsize=16, weight="bold")
    y = 0.91
    for r in righe:
        if r.startswith("##"):
            y -= 0.012; fig.text(0.07, y, r[2:].strip(), fontsize=12.5, weight="bold"); y -= 0.028; continue
        for k, chunk in enumerate([r[i:i + 95] for i in range(0, max(len(r), 1), 95)] or [""]):
            fig.text(0.07 if k == 0 else 0.09, y, chunk, fontsize=size, family="DejaVu Sans"); y -= 0.022
    pdf.savefig(fig); plt.close(fig)

with PdfPages(OUT) as pdf:
    l12, h12 = zona(1.5); l20, h20 = zona(2.0); l25, h25 = zona(2.5)
    pagina(pdf, "Calibrazione asmile-logger001 — un solo set di video", [
        "Versione 2026-11-11. Fatta con le lezioni della calibrazione di asmile #001 (3 riprese, 11/11).",
        "Obiettivo: una sola uscita (~25 minuti) che basta per calibrare e verificare il logger.",
        "## Prima di uscire (5 minuti)",
        "1. Accendi il logger e scrivimi: attivo io la REGISTRAZIONE DI CALIBRAZIONE (12 Mbps).",
        "   (Lezione #001: a 0,5 Mbps la compressione sporca gli angoli e la precisione non passa mai.)",
        "2. Misura e scrivimi: altezza da terra del CENTRO fra le due lenti (oggi in archivio 0,77 m).",
        "3. Misura e scrivimi: quanto guardano in giù le camere (app livella del telefono sul corpo camera).",
        "4. Misura col metro la distanza centro-centro fra le due lenti (attesa ~200 mm).",
        "5. Tabellone: lo stesso ChArUco A3 da 50 mm, INCOLLATO su pannello rigido, opaco, niente sole diretto.",
        "6. Filo a piombo (anche un peso su uno spago) + metro a nastro + nastro adesivo per i segni a terra.",
        "## Come si misurano le distanze (lezione #001: errore di 11 cm per lo zero sbagliato)",
        "- ZERO del metro: filo a piombo calato dal CENTRO fra le due lenti -> segno a terra.",
        "- ARRIVO: filo a piombo dalla FACCIA del tabellone -> punto a terra. Mai il piede della sedia.",
        "- LATO: dal segno zero, perpendicolare alla direzione delle camere.",
        "- ALTEZZA: del CENTRO del tabellone, da terra.",
        "## Ordine della ripresa (tutto in UNA sessione, logger fermo)",
        "A. Pose vicine a 1,5 m (tabella pag. 2)            ~8 min",
        "B. Pose a 2,0 m (tabella pag. 2)                     ~8 min",
        "C. Pose a 2,5 m solo ai LATI e in ALTO (pag. 2)       ~4 min",
        "   (Lezione #001: il lato sinistro si copre solo da più lontano: vicino esce dal campo di una camera.)",
        "D. Soste ferme per verificare le distanze (pag. 3)    ~5 min",
        "## Ogni posa",
        "- In ogni punto 3 pose ferme 2 secondi: dritto, girato ~30° (come una porta), inclinato ~30° (alto verso di te).",
        "- In ogni zona almeno 6-8 pose. Il tabellone deve stare TUTTO dentro l'immagine di ENTRAMBE le camere.",
        "- Fra una posa e l'altra muoviti piano: le pose mosse vengono scartate.",
        "## Dopo",
        "Scarico i video, gira lo strumento (stesse soglie di #001), il critico controlla, ti mando immagine con",
        "le distanze etichettate da confermare (come oggi: muro, borsa, manubrio).",
    ])
    rows = ["Posizioni calcolate per camere a 0,77 m che guardano DRITTE. Se guardano in giù di P gradi,",
            "abbassa le altezze ALTA e BASSA di Z*tan(P): a 1,5 m 13 cm ogni 5°, a 2 m 17 cm, a 2,5 m 22 cm.",
            "(Te le ricalcolo io appena mi mandi altezza e inclinazione misurate.)", "",
            "## A. 1,5 m dalle lenti",
            f"   Lati: {l12:.2f} m a sinistra  |  centro  |  {l12:.2f} m a destra",
            f"   Altezze del centro tabellone: bassa {h12[0]:.2f} m  |  media {h12[1]:.2f} m  |  alta {h12[2]:.2f} m",
            "   9 punti (3 lati x 3 altezze) x 3 pose = 27 pose minimo.",
            "## B. 2,0 m dalle lenti",
            f"   Lati: {l20:.2f} m a sinistra  |  centro  |  {l20:.2f} m a destra",
            f"   Altezze: bassa {h20[0]:.2f} m (appoggiato a terra, inclinato verso l'alto)  |  media {h20[1]:.2f} m  |  alta {h20[2]:.2f} m",
            "   9 punti x 3 pose = 27 pose minimo.",
            "## C. 2,5 m dalle lenti (solo dove #001 è rimasta scoperta)",
            f"   Sinistra {l25:.2f} m: bassa {h25[0]:.2f} / media {h25[1]:.2f} / alta {h25[2]:.2f} m",
            f"   Destra {l25:.2f} m: alta {h25[2]:.2f} m   |   Centro: alta {h25[2]:.2f} m",
            "   6-8 pose per punto (il tabellone qui è piccolo nell'immagine: più pose).",
            "## Perché così",
            "- Zone contate su ENTRAMBE le camere: lato calcolato perché il tabellone stia intero nel campo comune.",
            "- Lente del logger più larga di #001 (~69° x 46°): i lati sono più lontani dal centro che su #001.",
            "- Altezza bassa a 0,20 m minimo: sotto il tabellone tocca terra e si ombreggia."]
    pagina(pdf, "Dove mettere il tabellone", rows)
    hw5 = 5 * (W / 2) / F
    lat5 = round(hw5 - B / 2 - 0.45, 1)
    pagina(pdf, "Soste per verificare le distanze", [
        "Tabellone DRITTO su supporto fisso (sedia o cavalletto), mai in mano. 5 secondi fermi ciascuna.",
        "Distanza: filo a piombo sotto il centro fra le lenti -> filo a piombo sotto la faccia del tabellone.",
        "## Al centro",
        "   1 m   |   2 m   |   5 m   |   10 m",
        "## Ai lati",
        f"   2 m:  {l20:.2f} m a sinistra  e  {l20:.2f} m a destra",
        f"   5 m:  {lat5:.1f} m a sinistra  e  {lat5:.1f} m a destra",
        "## Ordine",
        "   centro 1 -> 2 -> 5 -> 10, poi 2 m sx -> 2 m dx -> 5 m dx -> 5 m sx.",
        "   Tra una sosta e l'altra copri le camere con la mano 1 secondo: segna il cambio nel video.",
        "## Scena di controllo finale (1 minuto)",
        "   Inquadra un muro a ~5 m e un oggetto a ~1 m e a ~2 m: misurali col metro e scrivimeli.",
        "   È la prova 'muro / borsa / manubrio' fatta oggi su #001.",
        "## Soglie (le stesse firmate per #001, D012)",
        "   Precisione camera < 0,5 px · coppia < 1 px · scarto verticale < 0,5 / 1 px in tutte le 9 zone",
        "   Distanza centro <= 2% fino a 5 m, <= 3% a 10 m · lati <= 3% a 2-5 m · baseline 200 mm ±3%",
        "## Cosa abbiamo imparato su #001 (non ripetere)",
        "   - registrare a bitrate alto (fatto in automatico da me)",
        "   - zero del metro col filo a piombo, scritto prima di partire",
        "   - zone basse/laterali pensate per tutte e due le camere, non per il centro del tabellone",
        "   - una sola sessione ben fatta vale più di tre riprese di recupero",
    ])
print(OUT)

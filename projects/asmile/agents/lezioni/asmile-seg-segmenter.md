# Lezioni di asmile-seg-segmenter

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-12 GIUSTO (`agents/rapporti/seg_sam3_094146_20261112.md`): 393/393 frame identici alla depth, stessa rettifica, 1 processo SAM 3, ripresa dopo kill, mosaico a passo regolare senza scelte a mano
- 2026-11-12 SBAGLIATO (`agents/rapporti/seg_sam3_094146_20261112.md`): primo lancio ha salvato immagini in runs/ (save=True ultralytics): cancellata e disattivato; 55% detection unknown e molti pole sospetti: classi non verificate
- 2026-11-12 GIUSTO (`agents/rapporti/seg_sam3_094146_20261112_v2.md`): Parametri dichiarati prima; corretto da solo il filtro che gonfiava la consistenza veicoli (100%->94%); regola gate testata sul set certificato prima di adottarla e scartata; non dichiarato come miglioramento della fusione cio' che e' merito della famiglia
- 2026-11-12 SBAGLIATO (`agents/rapporti/seg_sam3_094146_20261112_v2.md`): Il 21% del verifier non e' riproducibile: la mia definizione da' 37%; 159 conflitti di famiglia non risolti; frame_ref dei casi puntavano a /tmp (corretto ora)

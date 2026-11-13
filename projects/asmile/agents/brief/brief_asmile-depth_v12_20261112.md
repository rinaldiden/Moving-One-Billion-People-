# Brief dato dal capo ad asmile-depth — giro v12 (2026-11-12 sera)

Testo esatto inviato all'agente. L'errore del capo è al **punto 4**: "STERZA se c'è spazio libero dall'altro lato"
senza imporre che lo spazio sia MISURATO. L'agente ha implementato "lato non misurato = libero" (43 sterzate su 53
verso un lato mai misurato; f2060 verso muro e furgone). La stessa frase ambigua è anche nella tabella
config/soglie_attuazione_001.json → "azioni" → "ostacolo_davanti_entro_frena": "FRENA (o sterza se c'è spazio libero dall'altro lato)".

---

Giro v12 su L1.depth_video (asmile #001), dopo PASSA parziale di asmile-occhio su v11. Repo /Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile. Mac: CPU max 3, MPS 1. Prima: `python3 agents/palla.py lezioni --da asmile-depth` (regole di Daniele: 0-2 m anche sospesi, sbarra nominata esplicitamente; muri/cordoli = bordi; soglie solo da config/soglie_attuazione_001.json).
Partenza: agents/rapporti/depth_video_001_20261112_v11.md (commit 2479e1ff); prove critico agents/prove/occhio_depth_video_v11_2479e1ff/ (casi_fissi_v11.json SOLO regressione; stadioA_occhio_barra.py = sua prova del fix sbarra).
Correggi:
1. SBARRA (bloccante): training/depth/depth_fluido_a_001.py riga ~127 scarta hh<0.30*f/Z → esenta gli oggetti larghi e bassi (proposta critico: w≥0.60*f/Z e hh≥0.08*f/Z), così una sbarra 0.15 m è vista. Misura i falsi nuovi su TUTTI i 1350 fotogrammi (prima/dopo, guarda a occhio tutti i nuovi primi ostacoli <5 m), e la catena completa fino a FRENA entro 0.3 s col test sintetico a spessore 0.15 m a 1.0 e 1.7 m da terra.
2. FRENA su muri "altro" grandi e laterali (2711-15, 2903-10, 1931-32: ≥15 fotogrammi su 99): niente FRENA per "altro"/blob grandi laterali (box >40% immagine o parte di edificio dallo sfondo, |X|>0.8 m) → al più bordo. Misura i FRENA prima/dopo e campionane 15.
3. Regressione: vaso 3163-64 e 3173 perso in v11 (caso fisso v8): deve tornare primo ostacolo; pilastro d'angolo 2766 perso.
4. 2748/2760: oggetto vero ma la strada gira e l'umano sterza: azione corretta = **STERZA se c'è spazio libero dall'altro lato entro il percorso, altrimenti FRENA** (regola già in tabella: "FRENA o sterza se c'è spazio"). Implementala in modo semplice e dichiarala.
Rigenera i due video in training/depth/out_20261112_v12/. Uscita: agents/rapporti/depth_video_001_20261112_v12.md, commit (mai video), bilancio, `palla.py passa --verticale percezione --da asmile-depth --a asmile-occhio --artefatto agents/rapporti/depth_video_001_20261112_v12.md --gate L1.depth_video`. Riassunto in 8 righe con percorsi assoluti.

---

**Come andava scritto:** "STERZA solo se il lato opposto è MISURATO libero (bordo/ostacoli misurati oltre bordo_margine per tutto lo spazio di frenata); se il lato non è misurato o è incerto → FRENA/RALLENTA (lato sicuro)."

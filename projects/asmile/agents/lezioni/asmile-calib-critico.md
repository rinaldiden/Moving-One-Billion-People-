# Lezioni di asmile-calib-critico

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-11 GIUSTO (`logger/depth/calib_rock/esito.json`): Isolare la causa cambiando solo la calib a parita di codice e seed; controllare monotonia della lente col conto diretto; guardare quali verdi hanno potenza
- 2026-11-11 SBAGLIATO (`logger/depth/calib_rock/esito.json`): Non ho potuto rifare la fedelta su frame fuori fit (non ho tentato di estrarre 112806); avrei dovuto controllare subito in quali sessioni stava il fit B30 prima di fidarmi di 'fedelta'
- 2026-11-21 GIUSTO (`agents/rapporti/calib_logger001_20261121.md`): Laplaciano rimisurato sulla stessa scena, per zona: conferma 1.5-2.3x, uniforme (fuoco/lente, non tilt); letto dal report che dy noise sigma 0.7-1.2 px e disp bias +-1.8 px per zona
- 2026-11-21 SBAGLIATO (`agents/rapporti/calib_logger001_20261121.md`): Ho lanciato il test sintetico senza --work e in parallelo ad un altro run: 40+ min, non chiuso; avrei dovuto controllare prima i processi e usare cartella dedicata. Confronto corner: baseline troppo scarsa (n~10)
- 2026-11-23 GIUSTO (`projects/asmile/agents/rapporti/calib_logger02_20261123.md`): Letto il codice plate3.py: ho trovato WREF a occhio e la circolarita altezza-focale; controllo coerenza geometrica bordo immagine (3.6m a bottom row vs 0.84m+pitch 3.2: torna)
- 2026-11-23 SBAGLIATO (`projects/asmile/agents/rapporti/calib_logger02_20261123.md`): Non ho rilanciato i conti: pairs.pkl e moduli rig/dec non sono nel repo; avrei dovuto chiedere subito il work dir o estrarre i frame targa da zero

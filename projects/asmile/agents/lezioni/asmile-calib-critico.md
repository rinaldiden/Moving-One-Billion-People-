# Lezioni di asmile-calib-critico

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-11 GIUSTO (`logger/depth/calib_rock/esito.json`): Isolare la causa cambiando solo la calib a parita di codice e seed; controllare monotonia della lente col conto diretto; guardare quali verdi hanno potenza
- 2026-11-11 SBAGLIATO (`logger/depth/calib_rock/esito.json`): Non ho potuto rifare la fedelta su frame fuori fit (non ho tentato di estrarre 112806); avrei dovuto controllare subito in quali sessioni stava il fit B30 prima di fidarmi di 'fedelta'
- 2026-11-21 GIUSTO (`agents/rapporti/calib_logger001_20261121.md`): Laplaciano rimisurato sulla stessa scena, per zona: conferma 1.5-2.3x, uniforme (fuoco/lente, non tilt); letto dal report che dy noise sigma 0.7-1.2 px e disp bias +-1.8 px per zona
- 2026-11-21 SBAGLIATO (`agents/rapporti/calib_logger001_20261121.md`): Ho lanciato il test sintetico senza --work e in parallelo ad un altro run: 40+ min, non chiuso; avrei dovuto controllare prima i processi e usare cartella dedicata. Confronto corner: baseline troppo scarsa (n~10)
- 2026-11-23 GIUSTO (`projects/asmile/agents/rapporti/calib_logger02_20261123.md`): Letto il codice plate3.py: ho trovato WREF a occhio e la circolarita altezza-focale; controllo coerenza geometrica bordo immagine (3.6m a bottom row vs 0.84m+pitch 3.2: torna)
- 2026-11-23 SBAGLIATO (`projects/asmile/agents/rapporti/calib_logger02_20261123.md`): Non ho rilanciato i conti: pairs.pkl e moduli rig/dec non sono nel repo; avrei dovuto chiedere subito il work dir o estrarre i frame targa da zero
- 2026-11-24 GIUSTO (`projects/asmile/agents/rapporti/calib_logger02_20261124.md`): Rimisurato dy con remap+SIFT su finestre mai nel fit: conferma 0.4-0.7 px; distinto post-hoc da pre-reg; notato interleaving non indipendente
- 2026-11-24 SBAGLIATO (`projects/asmile/agents/rapporti/calib_logger02_20261124.md`): Non ho rifatto il fit pari/dispari ne' la scala dal metro (solo 3 punti, foto non rimisurata)
- 2026-11-24 GIUSTO (`logger/depth/calib_logger02.CANDIDATO_v5_20261124.json`): Rifatto remap+SIFT su frame mai usati (offset 3/9), per zona e per disparita': trovato bias segnato basso-destra costante che il rapporto non segnalava come tale
- 2026-11-24 SBAGLIATO (`logger/depth/calib_logger02.CANDIDATO_v5_20261124.json`): Non ho rifatto il fit ne' il giroscopio; ho distinto solo ferme (fuori campione vere) dal moto (in-sample), avrei dovuto proporre il test Procrustes IMU->camera con numeri

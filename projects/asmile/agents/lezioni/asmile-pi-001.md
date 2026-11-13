# Lezioni di asmile-pi-001

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-12 GIUSTO (`agents/rapporti/L0.encoder_ruota_20261112.md`): Confermata la rotolata coi 3 candidati: gli altri due sono marcia (GPS 2.7-3.7 m/s), la spinta e' a 1 m/s con fermo prima e dopo
- 2026-11-12 GIUSTO (`agents/rapporti/L0.encoder_ruota_20261112.md`): Accel valutata con Delta-v per evento (1.012) invece del rapporto selezionato sul GPS, che e' distorto dal rumore
- 2026-11-12 GIUSTO (`agents/rapporti/L0.encoder_ruota_20261112.md`): Capito che il lag 0.0 dello script e' il fit causale 0.3 s che compensa il ritardo GPS
- 2026-11-12 SBAGLIATO (`agents/rapporti/L0.encoder_ruota_20261112.md`): Primo tentativo flusso ottico: ffmpeg senza -f h264/passthrough decodificava 3 frame su 10066; poi il flusso ottico non ha risolto il lag (NON VERIFICATO sotto 0.5 s)
- 2026-11-12 SBAGLIATO (`agents/rapporti/L0.encoder_ruota_20261112.md`): Segno del lag in b_accel_imu.py inizialmente ambiguo, corretto leggendo roll e rifacendo la prova con la convenzione dello script ufficiale

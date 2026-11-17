# Lezioni di asmile-event-scettico

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-12 GIUSTO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Rifatti gli eventi con codice mio e separazione servo/lim_zone: ha scovato 7 stop contaminati dal limiter
- 2026-11-12 SBAGLIATO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Avrei dovuto controllare subito brake_out per ogni classe 'umano' e non fidarmi della regola v finale<2
- 2026-11-12 GIUSTO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Rimisurato gli stop da ev.csv e dal CSV sensori (encoder/GPS al tratto 5617 s), controllato monotonia e segnaposto sul JSON
- 2026-11-12 SBAGLIATO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Nel giro 1 non avevo escluso gli stop con v1 negativo (inversione encoder): lo stop 5625 era nel mio ev.csv; filtro da aggiungere v1>=-0.1
- 2026-11-12 GIUSTO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Rifatto il fit da ev.csv indipendente: coincide al centesimo; controllato monotonia e segnaposto
- 2026-11-12 SBAGLIATO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Non ho verificato il fit degli 8 stop GPS (4.56 a 5 km/h) con dati miei, solo plausibilita
- 2026-11-13 GIUSTO (`agents/rapporti/registro_guide_logger_20261113.md`): rifatto gate moto/fermo con codice mio (flusso Farneback) invece di fidarmi di v_raw; test segno su transizioni
- 2026-11-13 SBAGLIATO (`agents/rapporti/registro_guide_logger_20261113.md`): avrei dovuto controllare subito il mapping wall hub-vs-mtime (offset ~1-2 s lascia ambiguita sui singoli eventi) e usare frame di conferma
- 2026-11-13 GIUSTO (`agents/rapporti/registro_guide_logger_20261113.md`): Tasso base del gate su finestre casuali in moto: misura che smaschera un gate non discriminante
- 2026-11-13 SBAGLIATO (`agents/rapporti/registro_guide_logger_20261113.md`): Nel VETO 1 avrei dovuto chiedere subito il tasso base del flusso in moto e non solo gli arresti singoli
- 2026-11-13 GIUSTO (`agents/rapporti/eventi_guida_20261113.md`): Segno rifatto da video con test sintetico; rifatte le regole con codice indipendente e provate su un secondo giro (09/11) dove il doppio dei falsi non si vedeva in-sample
- 2026-11-13 SBAGLIATO (`agents/rapporti/eventi_guida_20261113.md`): Non ho potuto etichettare gli scatti 09/11 (nessuna verita): avrei dovuto guardare i fotogrammi di quei 8 scatti; ay vs az confusi nel mio primo dump

# Lezioni di asmile-event-scettico

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-12 GIUSTO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Rifatti gli eventi con codice mio e separazione servo/lim_zone: ha scovato 7 stop contaminati dal limiter
- 2026-11-12 SBAGLIATO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Avrei dovuto controllare subito brake_out per ogni classe 'umano' e non fidarmi della regola v finale<2
- 2026-11-12 GIUSTO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Rimisurato gli stop da ev.csv e dal CSV sensori (encoder/GPS al tratto 5617 s), controllato monotonia e segnaposto sul JSON
- 2026-11-12 SBAGLIATO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Nel giro 1 non avevo escluso gli stop con v1 negativo (inversione encoder): lo stop 5625 era nel mio ev.csv; filtro da aggiungere v1>=-0.1
- 2026-11-12 GIUSTO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Rifatto il fit da ev.csv indipendente: coincide al centesimo; controllato monotonia e segnaposto
- 2026-11-12 SBAGLIATO (`agents/rapporti/soglie_dalle_guide_001_20261112.md`): Non ho verificato il fit degli 8 stop GPS (4.56 a 5 km/h) con dati miei, solo plausibilita

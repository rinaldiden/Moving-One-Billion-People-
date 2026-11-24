# Lezioni di asmile-rollback-guardian

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-24 GIUSTO (`deploy/deploy_freno_fix_20261124.sh`): md5 dei backup contro git, live e root-ro
- 2026-11-24 SBAGLIATO (`deploy/deploy_freno_fix_20261124.sh`): non ho potuto provare il caso limiter morto a freno chiuso senza muovere nulla
- 2026-11-24 GIUSTO (`agents/rapporti/sveglio_durante_scarico_20261124.md`): letto il flusso reale: chi chiama scarico_visto (grep) ha rivelato il caso senza fine; unit file letto per StartLimit
- 2026-11-24 SBAGLIATO (`agents/rapporti/sveglio_durante_scarico_20261124.md`): Pi offline: non ho potuto provare ss/journalctl -g; race getmtime non eseguita
- 2026-11-24 GIUSTO (`agents/rapporti/sveglio_durante_scarico_20261124.md`): Rifatti i test e riletto il diff di ogni uscita del contatore (wrapper proxy_b)
- 2026-11-24 SBAGLIATO (`agents/rapporti/sveglio_durante_scarico_20261124.md`): Non ho simulato il buco tra file dopo 3 h: da cercare prima nei tetti a tempo con contatori
- 2026-11-24 GIUSTO (`logger02/firmware/main/logger02_batt_logic.h`): ho letto bootloader rollback + guardia_ota contro il flusso di avvio rifiutato
- 2026-11-24 SBAGLIATO (`logger02/firmware/main/logger02_batt_logic.h`): non ho potuto provare sul device; avrei dovuto chiedere subito una prova di avvio con cella bassa

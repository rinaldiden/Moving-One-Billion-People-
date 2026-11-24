# Lezioni di asmile-sicurezza

Scritte da palla.py (VETO dei critici + bilanci giusto/sbagliato). Leggile prima di ogni lavoro.

- 2026-11-23 GIUSTO (`projects/asmile/agents/rapporti/speed_limiter_v3_sicurezza.md`): Letto ogni percorso verso b.pwm, provato in Python che NaN non alza il tetto, trovato che la ricalibrazione IMU dipende dall'encoder (anti cieca con encoder bloccato)
- 2026-11-23 SBAGLIATO (`projects/asmile/agents/rapporti/speed_limiter_v3_sicurezza.md`): Niente di sbagliato; non ho eseguito i test ne' simulato i guasti, solo lettura statica
- 2026-11-23 GIUSTO (`projects/asmile/agents/rapporti/speed_limiter_v3_sicurezza.md`): Stavolta ho eseguito: pytest 91 verdi e 2 scenari miei (encoder bloccato con IMU che vibra; ruota sollevata girata a mano: servo a 31 gradi per 1.5 s poi 0). Ho trovato fuori dal diff che gps_state.json lo scrive solo v2 e che il master lancia v2 con Popen, non da servizio
- 2026-11-23 SBAGLIATO (`projects/asmile/agents/rapporti/speed_limiter_v3_sicurezza.md`): Nel primo giro avevo chiesto il filtro |a| istantaneo 0.7-1.3 g: avrebbe cancellato le impuntate vere (0.50-1.41 g); il produttore aveva ragione a cambiarlo. Prima di proporre un filtro devo confrontarlo coi dati veri
- 2026-11-24 GIUSTO (`agents/rapporti/regolatore_fascia_contatto_20261124.md`): provato il glitch con salti sintetici, letto controllo.py per l'ordine anti-impuntata
- 2026-11-24 SBAGLIATO (`agents/rapporti/regolatore_fascia_contatto_20261124.md`): niente di sbagliato; non ho girato la sim 36 celle del ramo, mi fido dei numeri del report

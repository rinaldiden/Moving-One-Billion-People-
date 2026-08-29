# LJ8A3-2-Z/BX → Raspberry Pi 5 — cablaggio wheel speed / odometry

Sensore di prossimità induttivo M8, **NPN NO**, portata nominale 2mm, alim **12-24VDC**, 3 fili.
Uso: rileva il metallo che passa (bulloni disco / raggi) → un impulso a giro → conta impulsi = velocità ruota.

## I 3 fili
- **Marrone** = V+ (12-24V)
- **Blu** = 0V / GND
- **Nero** = segnale (uscita **NPN open-collector**: quando vede metallo tira il nero a 0V; a vuoto il nero "galleggia")

## Regola d'oro (memoria VESC bruciato)
Il Pi è a **3.3V**, il sensore è alimentato a **12V**. Il filo nero **non va MAI diretto sul GPIO**.

## Cablaggio corretto
1. **Marrone → +12V** (buck converter dalla batteria bici; non c'è un rail 12V pronto sul Pi).
2. **Blu → GND in COMUNE col Pi** (massa condivisa: senza questo il segnale non ha riferimento).
3. **Nero → GPIO** solo con protezione, in ordine di sicurezza:
   - Minimo: pull-up **a 3.3V** (10k verso 3.3V del Pi) + **resistenza serie 1-4.7k** + **zener 3.3V** verso GND come clamp. Così il nero oscilla solo 0-3.3V.
   - Meglio / zero rischio: **optoisolatore** (isolamento galvanico completo tra i 12V del sensore e il 3.3V del Pi).

## Logica software
- Metallo presente → GPIO **LOW** (0V)
- Niente metallo → GPIO **HIGH** (3.3V, dal pull-up)
- Conta i fronti di discesa; impulsi/tempo × circonferenza ruota / n. target = velocità.

## Montaggio meccanico
- Gap dal target **≤ 2mm** (stai ~1-1.5mm), fisso e rigido.
- Target metallici regolari (bulloni disco freno o testine raggi): più target = più risoluzione a bassa velocità.

<!-- creato 2026-08-29: cablaggio distillato per rispondere a Paolo -->

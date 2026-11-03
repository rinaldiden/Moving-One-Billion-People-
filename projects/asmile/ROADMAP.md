# Asmile — Roadmap

## Dopo il software: hardware dedicato

> Da nota "inbox-zio" del 2026-11-03 (Claude voce, su richiesta di Daniele).

**Quando lo sviluppo software di Asmile è completato: progettare hardware dedicato.**

Oggi Asmile gira su componenti general purpose (Raspberry Pi 5, ESP32, sensori off-the-shelf).
Il passo successivo, a software maturo e stabile, è un hardware disegnato su misura per il suo compito.

### Riferimenti

- **RISC-V** — set di istruzioni aperto, senza licenze (RISC-V International, <https://riscv.org>).
  Base candidata per il chip dedicato.
- **TSMC** — principale produttore (foundry) di chip, Taiwan.
- **ASML** — produttore olandese delle macchine litografiche per i chip avanzati.

### Da chiarire quando si arriva qui

- Cosa conviene integrare (inferenza visione, controllo attuatori sterzo/freno, power management, safe shutdown).
- Strada intermedia prima del chip custom: SoC RISC-V esistenti / FPGA / board custom.
- Volumi, costi NRE, certificazioni.

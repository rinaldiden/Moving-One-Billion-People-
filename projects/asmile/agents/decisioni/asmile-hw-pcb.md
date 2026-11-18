# Decisioni di asmile-hw-pcb

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-18 15:04 **compute del logger HW4** → 2 moduli Waveshare ESP32-P4-Module (gli stessi di HW3) su una scheda unica, stessi GPIO di HW3. Perché: chip P4 nudo stock 0 ovunque (Espressif MOQ 2000, DigiKey apr-2027); il modulo include P4+PSRAM+flash+C6 a ~10 $, firmware hw3-def gira senza cambiare una riga, compute doppio (largo come chiede Daniele). Scartato: 1 P4 + DVP: modulo OV9281 DVP non a catalogo, driver DVP da scrivere, un solo ISP (piano B per HW4-v2 dopo la prova); chip nudo: non comprabile oggi, +rischio RF/alimentazione. Evidenza: `projects/asmile/hw/pcb/REGISTRO.md`.

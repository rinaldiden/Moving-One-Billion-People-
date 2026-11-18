# Report al capo — logger HW4 (asmile-hw-pcb, 18/11/2026 notte, dopo il VETO 2) · maturità L0 → L1

**Scelta (invariata).** Scheda unica 250 × 50 mm, 4 strati, 2 moduli Waveshare ESP32-P4-Module + 2 OV9281 mono global
shutter su FFC 15 pin + trigger, baseline 200 mm. VETO 1 chiuso e rifatto dal critico. Cosa ho cambiato per il VETO 2
(una riga per voce in `../REGISTRO.md`, 23:00-23:20):
1. **Partitore batteria 100k/33k come HW3, C4 non montato.** `kicad/modello_partitore.py` simula la sequenza di
   `logger02_imu.c:77-84`: errore della RC **0,000 %** fra 3,0 e 4,2 V (riprodotto anche il −31,9 % del giro prima).
   Non dipendono dalla RC: resistenze 1 % (±1,36 %) e ADC P4 a 12 dB (±15 mV, Tab. 5-6 pag. 90). Per stare sotto l'1 %
   complessivo c'è la calibrazione a un punto in collaudo (passo 8b).
2. **R35 a 10k, e non basta da sola** (`kicad/modello_power_path.py`): con il gate su VBUS (10 µF) la scheda resta 60-80 ms
   sul diodo di body, con la 3V3 a 2,5-3,0 V. Ho alimentato il gate da VBUS tramite **D8 (SS14, stesso codice di D5)**:
   τ del gate ≈ 7 µs contro 35-48 µs di discesa di VBUS/VSYS → nessun buco. Prova sonda su 3V3_A al passo 4 di COLLAUDO.
3. **VBUS:** R36 in serie dopo J1 (0805 0 Ω montato, posto per PTC o perla; 0805 e non 0603 perché passano 2 A) + TVS +
   **OVP AW32901** (5,83-6,07 V, 50 ns, 120 V di surge, 0,24 $; datasheet pag. 4 e 7) davanti a TP4056 (6,5 V max) e
   TLV62569 (6 V max). Prova hot-plug e 9 V al passo 5b. Rischio: CSP passo 0,4 mm da sbrogliare.
4. Documentati: GPIO36 alto grazie a R46 dentro il modulo; console UART0 della A solo su J12 (adattatore al bring-up);
   NVS "ident" scritta su A (USB-C) e B (J22); passo 3 con limite 1 A; finestra NTC reale 39-42 °C / 0-4 °C.
5. **ERC 0 (23:02:09), netlist KiCad = netlist voluta su 526 pin, DRC 0 errori rame (23:02:18)**, tabella pin 0 conflitti.

**Costo scheda K1 senza camere** (`kicad/costi.py`, JLC unico fornitore): 48,5 € a 10 pz · **30,7 € a 100** · 27,3 € a 1000
(netto IVA; caso peggiore con dazio e IVA: 60,4 / 38,0 / 33,8 €). OVP + D8 + R36 aggiungono ~0,3 € a scheda.

**NON verificato:** tutto ciò che è transitorio (stacco USB, hot-plug) è calcolo, non misura · pin 1 del modulo (P1) · flat
(P3) · flash della B (P7) · montaggio vero (servono i gerber) · portata dello 0 Ω 0805 (2 A tipico).

**Decisioni per Daniele (le ha sollevate il critico, non le decido io):**
1. **Corrente di carica (R5):** oggi 1,2 kΩ = 1 A. Il TP4056 dissipa fino a ~1,75 W (sopra 1,5 W va in foldback termico)
   e 1 A più la scheda accesa sono troppi per una porta USB "normale" (500-900 mA). **R5 = 2 kΩ (~600 mA) o 2,4 kΩ (~500 mA)**:
   più fresco e compatibile con ogni porta, ma 2 × 18650 (5-6 Ah) si caricano in **8-10 h** invece di ~6.
2. **Cella inserita al contrario:** nessuna protezione (FS8205A e P-MOS conducono dai diodi di body). Basta serigrafia "+"
   su J2 e colori fissi nei fili + tester sul pacco prima della prima spina (già nel passo 4)? Oppure si aggiunge un
   P-MOS di protezione (~0,05 $, un po' di caduta in più → soglia di cella più alta)?
3. (dalle volte prima) scheda con 2 moduli a ~31 € o piano B a ~19 €; lente uguale a #001; una o due SD; bozze ai fornitori.

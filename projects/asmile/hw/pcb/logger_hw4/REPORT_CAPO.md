# Report al capo — logger HW4 (asmile-hw-pcb, 18/11/2026 sera, dopo il VETO 1) · maturità L0 → L1

**Scelta (invariata).** Scheda unica 250 × 50 mm, 4 strati, **2 moduli Waveshare ESP32-P4-Module** + **2 OV9281 mono
global shutter** su FFC 15 pin + trigger, baseline 200 mm rigida. Chip P4 nudo e sensori nudi: stock 0.

**VETO 1 — cosa ho corretto (ogni punto riga per riga in `../REGISTRO.md` 17:10-17:42):**
1. GPIO: `PIN_HW4.md` generato da `kicad/controlla_pin_fw.py`, che cerca ogni GPIO in tutto il firmware hw3-def:
   **0 conflitti**. CAM_EN 12→11, LED 9/10→50/52, buzzer 53→27. I pad del saluto I2S (9/10/12/13), del PA e di ETH restano
   liberi. Saluto→bip con il flag `CONFIG_LOGGER02_HW4` (`PROPOSTA_FIRMWARE_HW4.md`). logger02 non toccato.
2. Flash della B: pad PROG J22 (UART0 37/38 + EN + BOOT, pogo/header) + TP USB-JTAG; in campo OTA wifi. COLLAUDO §7 riscritto.
3. NTC sul TP4056 (~3-42 °C), TVS SMF5.0A su VBUS, J2 a 3 poli e J3 a 2 poli (non si scambiano), **power-path**
   (P-MOS + Schottky, interruttore dopo l'OR), partitore batteria sulla cella con lo stesso rapporto di HW3.
4. KiCad 10.0.8 **installato in /Applications/KiCad** (nessuna password; senza modelli 3D: disco al 98 %).
   **ERC 0 (17:06:38), netlist 507 pin = 0 differenze, DRC 0 errori rame (17:06:40)**; 375 collegamenti ancora da sbrogliare.
5. TLV62569 sul datasheet vero SLVSDG1C (§6.5 p.5, §7.3.2 p.6): 3,30 V pieni con la cella sopra ~3,7 V; ≥ 3,0 V fino a ~3,4 V;
   il firmware si spegne a 3,45 V.
6. Costi: PCB e montaggio **dallo stesso fornitore (JLCPCB)**, con il preventivo vero del PCB (10 pz 60 $, 100 pz 297 $).
   Nel conto ora ci sono saldatura a mano dei moduli, 23 Extended, IVA e dazio, e lo stock a 1000 pz.

**Costo scheda K1 senza camere (`kicad/costi.py`, 1 € = 1,10 $):**
| | 10 pz | 100 pz | 1000 pz |
|---|---|---|---|
| netto IVA | 48,2 € | **30,4 €** | 27,1 € |
| caso peggiore (dazio 3,5 % + IVA 22 % non recuperata) | 60,0 € | 37,6 € | 33,5 € |
| piano B K2 (1 modulo + DVP), netto | — | 19,2 € | 16,1 € |
Con 2 camere OV9281 a modulo: 63 € a 100 pz, 53 € a 1000 pz. "25 € tutto compreso": non raggiungibile. "25 € scheda": K1 sta
5 € sopra a 100 pz (i moduli valgono 19 €).

**Ancora NON verificato:** pin 1 del modulo sul pezzo vero (P1) · lato contatti del flat (P3) · flash della B da J22 (P7) ·
3V3 a cella bassa (P8) · montaggio vero (servono gerber dopo lo sbroglio) · paese della spedizione DDP · stock FFC a 1000
pz (serve footprint combinato) · valori dei registri LSM6 nella proposta firmware.

**Decisioni per Daniele:** 1) K1 a ~30 € o K2 a ~19 €? 2) lente uguale a #001? una SD o due? 3) mandare le 4 bozze ai fornitori?
4) va bene KiCad in /Applications senza modelli 3D (disco al 98 %)?

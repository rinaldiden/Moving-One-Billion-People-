# Report al capo — logger HW4 (asmile-hw-pcb, 19/11/2026 notte, dopo il PASSA del giro 3) · maturità L0 → L1

**Fatto (un commit per passo):** 7e36f248 condizioni del critico · bd64a179 sbroglio · 7882f052 produzione · 8ad02238 preventivi.
1. **4 condizioni:** AW32901 col land pattern del datasheet (pad 0,23 NSMD, maschera 0,33, nome FCQFN-12); D5 → SS34 C8678
   (Basic, 3 A); COLLAUDO 5b a 9 V con banco a 0,1 A (il TVS conduce e scalda); 24 Extended nel BOM = 23 montati + u.FL DNP.
2. **PCB 4 strati sbrogliato: DRC 0 errori, 0 collegamenti aperti** (solo 41 avvisi di serigrafia), **ERC 0**; schema e PCB =
   netlist voluta su 526 pin/pad. Si rifà con `bash kicad/costruisci_pcb.sh freerouting.jar`. Stack-up F/B segnali+GND,
   In1 GND, In2 3V3_A | 3V3_B (JLC04161H-3313: pista 0,15 ≈ 50 Ω). Coppie MIPI instradate dal nostro router A*:
   11-17 mm, **differenza P/N ≤ 1,6 mm**. Nodo SW dei buck 5,4 / 6,7 mm. Dettaglio e rischi in DESIGN §8.
3. **Produzione** in `produzione/`: gerber + fori (zip), BOM_JLC (52 righe, 125 pezzi), CPL (125, tutti top, rotazioni 0
   controllate sui LED e su D5), moduli Waveshare elencati a parte.
4. **Preventivi coi gerber veri** (letti senza errori da entrambi): **JLCPCB 60,00 $ (10 pz) · 279,05 $ (100 pz)**,
   PCBWay 130,89 $ · 350,89 $. Costo scheda K1 senza camere: **30,7 € a 100 pz** (netto IVA), 27,4 € a 1000.

**BLOCCO (fermo, come da istruzioni):** il preventivo di **assemblaggio** coi file (BOM + CPL → montaggio e DFM del CSP)
chiede l'account. Registrazione JLCPCB compilata (password generata nel Portachiavi `claude-jlcpcb.com`, email
daniele@movingonebillionpeople.org, Personal, Italia, solo i termini) → **reCAPTCHA «I'm not a robot»**: non lo aggiro.
PCBWay ha due captcha nella registrazione. **Serve Daniele per 2 minuti**: risolvere il captcha su jlcpcb.com (o entrare con
Google) con quella email; poi faccio io upload BOM/CPL, montaggio e DFM, senza ordinare né pagare.

**NON verificato:** prezzo di montaggio (stima: 4,64 $/scheda a 100 pz) e DFM del CSP 0,4 mm (sulle capacità pubblicate
JLC è accettabile: pad ≥ 0,2 mm con ENIG) · VBUS a 0,3 mm per 39 mm (fino a ~2,2 A: +20-30 °C) · impedenza dello stack-up
(col calcolatore del fornitore) · pin 1 del modulo (P1), flat (P3), flash della B (P7), stacco USB (P10): tutto a banco.

**Note di strumenti:** OpenJDK 27 via brew (nessuna password) + Freerouting 2.5.0 in /tmp; profilo browser dedicato
`~/.claude_pw_pcb`. Errore mio corretto subito: un `git stash pop` ha ripescato un vecchio stash di altri (pi/braking):
file ripristinati, stash lasciato intatto, niente committato (antipattern A15).

**Decisioni per Daniele:** 1) **captcha JLCPCB** (sblocca il preventivo di montaggio); 2) R5 2 kΩ / 2,4 kΩ (carica più fresca,
aiuta anche il punto VBUS); 3) cella invertita; 4) K1 ~31 € o K2 ~19 €; lente; SD; bozze fornitori (aperte da prima).

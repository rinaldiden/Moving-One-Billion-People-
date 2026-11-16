# Carrello proposto — Logger v2 MOSFET e diodi

Generato da `cerca_prezzi.py` il 2026-11-16. Prezzi letti dal web oggi: **il carrello reale fa fede**.
Amazon: NON Prime (soglia gratis 39 €). AliExpress Choice: gratis da 10 € accorpati.

## Scenario `base` — totale stimato **16.68 €** (merce + spedizioni)

### Ordine aliexpress:choice — spedizione 1.99 €
| voce | qty | offerta | conf. | € merce | link |
|---|---|---|---|---|---|
| pmos | 2 | 5 pz IRF3703 IRF3708 IRF3709 IRF3710 IRF3713 IRF3808 IRF4905 IRF6218 i | 1×5pz | 2.27 | [apri](https://it.aliexpress.com/item/1005006771928211.html) |
| diodi | 10 | 100PCS 1N5817 1N5819 1N5399 1N4937 1N4004 Schottky Diodo di Raddrizzat | 1×100pz | 3.08 | [apri](https://it.aliexpress.com/item/32894528894.html) |

### Ordine web:conrad.it — spedizione 6.90 €
| voce | qty | offerta | conf. | € merce | link |
|---|---|---|---|---|---|
| nmos | 2 | Infineon Technologies IRL540NPBF MOSFET 1 Canale N 140 W TO-220 | 2×1pz | 2.44 | [apri](https://www.conrad.it/it/p/infineon-technologies-irl540npbf-mosfet-1-canale-n-140-w-to-220-162798.html) |

## Alternative per voce (le 3 migliori dopo i filtri)

**pmos** (base, qty 2) — `IRF4905 mosfet TO-220`
- aliexpress 1.08 € (0.108 €/pz) sped:None ★4.9 · 184 venduti — [10 pz muslimatirf3205 TO-220 MOSFET di potenza IRF3710 IRF38](https://it.aliexpress.com/item/1005003194898684.html)
- aliexpress 2.27 € (0.454 €/pz) sped:choice_10 ★4.8 · 162 venduti — [5 pz IRF3703 IRF3708 IRF3709 IRF3710 IRF3713 IRF3808 IRF4905](https://it.aliexpress.com/item/1005006771928211.html)
- aliexpress 2.89 € (0.289 €/pz) sped:None ★4.5 · 1000 venduti — [10PCS IRF3205PBF IRF3205 TO-220 IRF3710 IRF3808 IRF4905 IRF5](https://it.aliexpress.com/item/1005005109420191.html)

**nmos** (base, qty 2) — `IRL540N mosfet TO-220 logic level`
- web 2.44 € (1.22 €/pz) sped:None  — [Infineon Technologies IRL540NPBF MOSFET 1 Canale N 140 W TO-](https://www.conrad.it/it/p/infineon-technologies-irl540npbf-mosfet-1-canale-n-140-w-to-220-162798.html)
- web 4.98 € (2.49 €/pz) sped:None  — [IRL540N MOSFET TO-220](https://www.otronic.it/it/irl540n-mosfet-to-220)
- amazon 9.99 € (0.999 €/pz) sped:gratis_amazon ★4.6 · 465 rec. · vende WUMINGPS · 100% pos. — [10 Pezzi IRLZ44N Transistor MOSFET Canale N 47A 55V – Interr](https://www.amazon.it/dp/B0H1M7T9GN)

**diodi** (base, qty 10) — `1N5817 diodo schottky`
- aliexpress 1.92 € (0.038 €/pz) sped:None ★4.9 · 5000 venduti — [50PCS HER107 FR207 FR157 FR107 RL207 DO-41 Diodo raddrizzato](https://it.aliexpress.com/item/1005009508821696.html)
- aliexpress 1.99 € (0.04 €/pz) sped:None ★4.9 · 5000 venduti — [50PCS 1N5817 1N5819 1N5399 1N4937 1N4004 Diodo raddrizzatore](https://it.aliexpress.com/item/1005001552094086.html)
- aliexpress 3.08 € (0.031 €/pz) sped:choice_10 ★4.8 · 79 venduti — [100PCS 1N5817 1N5819 1N5399 1N4937 1N4004 Schottky Diodo di ](https://it.aliexpress.com/item/32894528894.html)

## Aggiornamento 2026-11-16 (Daniele): IRL540N già in casa, SB580 va bene, + condensatore d'uscita del 1117 (obbligatorio; ingresso non serve)
**Ordine consigliato VELOCE (Amazon, 1-2 giorni):**
| voce | offerta | € |
|---|---|---|
| IRF4905 (indispensabile) | 10 pz, voto 4.7 — https://www.amazon.it/dp/B08L3NPPTF | 8.78 |
| condensatori elettrolitici | kit 240 pz 24 valori (contiene 22/47/100 µF), voto 4.5 — https://www.amazon.it/dp/B07KC99W2K | 10.99 |
| 1N5817 (facoltativo: SB580 va bene) | 10 pz, voto 4.6 — https://www.amazon.it/dp/B089P1TKNV | 7.49 |
Totale 19.77 € senza diodi / 27.26 € con diodi (+4.99 € spedizione se non Prime: sotto 39 €).
**Ordine ECONOMICO (AliExpress, 1-2 settimane):** IRF4905 5 pz 2.27 € (variante da scegliere) + 22 µF 25 V Nichicon 10 pz 2.93 € + 1N5817 100 pz 3.08 € ≈ 8.3 € + spedizione Choice (gratis da 10 €, altrimenti ~2 €).

# Encoder SameSky (AMT222A-V) sterzo — verifica cablaggio + alimentazione

> SameSky (ex CUI Devices) = AMT22. Modello sterzo: **AMT222A-V**, assoluto 12-bit, SPI Mode 0.
> Sostituisce il vecchio Briter BRT38 SSI (che girava via 2× RS-485 + level shifter).
> Reader: `pi/steering/amt22_reader.py` (commit 81167d1, 2026-05-13). Datasheet: `docs/datasheets/AMT222A-V_notes.md`.

## Alimentazione — VERIFICATA contro datasheet
- Vdd: **min 3.8 / typ 5 / max 5.5 V → si alimenta a 5V, NON a 3.3V.** Pin 1 (Vdd) → Pi **Pin 2 (5V)**.
- Assorbimento ~16 mA → rail 5V del Pi lo regge senza problemi.
- Uscite HIGH = 3.3V tipico → **compatibili diretto coi GPIO del Pi: NIENTE level shifter, NIENTE RS-485** (al contrario del Briter).

## Cablaggio — 6 fili su SPI1 (/dev/spidev1.0)
| AMT222 | Funzione | Pi (pin fisico / GPIO) |
|---|---|---|
| Pin 1 Vdd | +5V | Pin 2 (5V) |
| Pin 2 SCLK | clock | Pin 40 / GPIO 21 (SPI1_SCLK) |
| Pin 3 MOSI | dati Pi→enc | Pin 38 / GPIO 20 (SPI1_MOSI) |
| Pin 4 GND | massa | Pin 39 (GND) |
| Pin 5 MISO | dati enc→Pi | Pin 35 / GPIO 19 (SPI1_MISO) |
| Pin 6 CS | chip select | Pin 12 / GPIO 18 (SPI1_CE0) |

Overlay attivo (`config/boot_config_asmile.txt`): `dtoverlay=spi1-1cs` ✓ → espone GPIO 18/19/20/21 = /dev/spidev1.0. Reader: SPI Mode 0, 500kHz, 8-bit.

## PUNTI DI ATTENZIONE (differenze dal Briter — controllare in fisico)
1. **Filo MOSI nuovo.** Col Briter il Pin 38/GPIO20 era libero (SSI = solo clock+dato). L'AMT22 è SPI vero: serve il filo MOSI (Pin3→Pin38). Per la sola lettura posizione è di fatto ignorato, ma è **obbligatorio per i comandi reset (0x60) e set-zero (0x70)** → collegarlo.
2. **Switch RUN MODE.** Lo switch sotto l'encoder va a destra (Run) PRIMA di alimentare. A sinistra (Program) = niente SPI, letture nulle/garbage.
3. **Conflitto storico SPI1 ↔ ov9281.** Col Briter l'encoder leggeva 4095 con le cam accese, 0 senza → conflitto overlay camera su SPI1. Da riprovare con l'AMT22: **accendere le cam stereo e leggere l'encoder insieme**, non solo da solo.

## Esito lettura
Nel repo ci sono reader + note datasheet + cablaggio, ma **non c'è un log registrato dell'esito della prova** (nessun CSV/txt con le letture). Appena rifatta la prova, annotare qui sotto: posizione 0-4095 stabile? checkbit OK? valori cambiano ruotando? tiene con cam accese?

Comando di prova: `python3 pi/steering/amt22_reader.py --test` → ruotare l'encoder, i valori devono variare 0-4095 e checkbit = OK.

_Verifica cablaggio/alimentazione fatta dal doppio contro datasheet il 2026-10-19 — esito lettura da compilare da Daniele._

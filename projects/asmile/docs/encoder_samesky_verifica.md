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

---

## DUE encoder (sterzo + ruota) — mappa GPIO (2026-10-26)

Approccio attuale: `pi/steering/amt22_bitbang_dual.py` = bit-bang, bus CONDIVISO + 2 CS = **5 GPIO** (SCLK21/MISO19/MOSI20 condivisi, CS sterzo 18, CS ruota 16). Letture 0-drop come l'Arduino.

### GPIO già occupati (ultimo wiring)
`2,3` I2C (MPU6050+INA219) · `4` buzzer · `8,9` GPS UART · `12` servo freno PWM · `14,15` VESC UART · `17` master_switch · `26` power-sense. (`5` = buzzer proximity, non cablato/claimed.)

### GPIO LIBERI
`6,7,10,11,13,16,18,19,20,21,22,23,24,25,27` → **15 liberi**. Spazio abbondante.

### Opzione A — split COMPLETO 4+4 = 8 GPIO (come chiesto)
| Segnale | STERZO (invariato) | RUOTA (nuovo) |
|---|---|---|
| SCLK | GPIO21 / Pin40 | GPIO25 / Pin22 |
| MISO | GPIO19 / Pin35 | GPIO24 / Pin18 |
| MOSI | GPIO20 / Pin38 | GPIO23 / Pin16 |
| CS   | GPIO18 / Pin12 | GPIO22 / Pin15 |

Blocco 22-25 tutto libero e contiguo. +5V da Pin2/4, GND da Pin6/9/… (2×16mA = nulla sul rail). Richiede patch a `amt22_bitbang_dual.py` (SCLK/MISO/MOSI separati per encoder).

### Opzione B — bus condiviso + 2 CS = 5 GPIO (già implementata, Regola n.1)
Nessun filo nuovo oltre il 2° CS. Funziona già a 0-drop. Per l'AMT22 lo split completo non dà vantaggi funzionali (lettura alternata CS). Lo split serve solo se vuoi leggere i due encoder DAVVERO in parallelo/simultaneo o se gli harness corrono separati.

---

## PROVA DA FARE — scambia CS↔MOSI sul lato Pi (2026-10-27)

Encoder AMT22 — pin Pi (prova questa):
Pin 1 Vdd → 5V (Pin 2)
Pin 2 SCLK → Pin 40
Pin 3 MOSI → Pin 12 (quello che pensavi fosse CS)
Pin 4 GND → GND
Pin 5 MISO → Pin 35
Pin 6 CS → Pin 38 (quello che pensavi fosse MOSI)

Oppure semplicemente scambia i due fili CS e MOSI sul lato Pi e lascia tutto il resto com'è.

Overlay corretto (dal dual_daemon):
dtoverlay=spi1-2cs,cs1_pin=16

Dopo aver scambiato i fili, lancia:
python3 pi/steering/amt22_reader.py --test
o direttamente il dual daemon.

Questa prova l'abbiamo fatta ieri provando a leggere l'encoder via raspi dopo averlo letto da Arduino?

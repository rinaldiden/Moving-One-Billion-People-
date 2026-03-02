# Firmware Sterzo — Arduino + VESC + Encoder SSI

Sketch Arduino originale per il controllo dello sterzo via VESC.

## Componenti

- **VESC** — Controller motore BLDC in modalità FOC (Field Oriented Control)
- **Encoder SSI 12-bit** — Posizione assoluta dello sterzo (0–4095)
- **Arduino** — Lettura encoder → calcolo duty → invio a VESC via UART

## Come funziona

1. L'encoder SSI viene letto con median filter (5 campioni) per stabilità
2. Il delta tra posizione attuale e precedente determina direzione e velocità
3. Il duty cycle viene calcolato proporzionalmente al delta e inviato al VESC
4. Gestione wrap-around a 0/4095 per continuità

## Parametri chiave

| Parametro | Valore | Note |
|-----------|--------|------|
| Risoluzione encoder | 12 bit (4096 posizioni) | ~0.088° per step |
| MIN_CHANGE | 5 | Soglia minima per inviare comando |
| MAX_DUTY | 0.8 | Limite velocità motore (sicurezza) |
| Loop delay | 20ms | ~50Hz |

## Pin Arduino

| Pin | Funzione |
|-----|----------|
| 10 (RX) | VESC UART RX |
| 11 (TX) | VESC UART TX |
| 4 | Encoder CLOCK |
| 3 | Encoder DATA |
| 5 | CLOCK_ENABLE (HIGH) |
| 6 | DATA_ENABLE (LOW) |

## Stato

✅ Funzionante su Arduino — da convertire in Python per Raspberry Pi 5.

# Firmware Freno — Arduino + Servomotore

Sketch Arduino per il controllo del freno idraulico a disco via servomotore.

## Componenti

- **Servomotore** — Aziona il pompante del freno idraulico a disco
- **Arduino** — Controlla il servo con profilo di frenata realistico

## Come funziona

Il sistema simula una frenata realistica in due fasi:

1. **Scatto rapido** — Primi gradi a velocità massima (recupero gioco meccanico)
2. **Progressiva** — Ultimi gradi con ritardo crescente (frenata progressiva)

Il rilascio è sempre rapido (1ms/grado).

## Parametri chiave

| Parametro | Valore | Note |
|-----------|--------|------|
| CENTRO | 0° | Posizione di riposo (leva rilasciata) |
| ESCURSIONE_MEDIA | 85° | Corsa per frenata media |
| GRADI_VELOCI | 56° | Fase rapida iniziale |
| RITARDO_FRENO_DOLCE | 60 ms/° | Velocità fase progressiva |
| RITARDO_SUPER_RAPIDO | 1 ms/° | Velocità scatto e rilascio |
| Pin servo | 9 | PWM (500–2500 µs) |

## Test

Lo sketch `brake_servo_test.ino` esegue 500 cicli di frenata media per stress test del sistema meccanico.

## Stato

✅ Testato (500 cicli) su Arduino — da convertire in Python per Raspberry Pi 5.

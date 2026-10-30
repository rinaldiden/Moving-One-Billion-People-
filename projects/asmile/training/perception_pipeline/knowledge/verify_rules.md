# Regole di verifica della segmentazione — Asmile (stadio 2: `asmile-seg-verifier`)

> Controlli che decidono se un frame segmentato è `ok` / `review` / `reject`, e se è `novel`.
> Tutti operano sull'output dello stadio 1 (quasi gratis, niente ri-segmentazione). Soglie
> **dichiarate**, da calibrare sui primi video freschi (nessuna è legge finché non misurata).

## Verdetti
- **ok** — passa a `asmile-seg-situation`.
- **review** — dubbio: non si usa per il training finché non chiarito; candidato caso dubbio.
- **reject** — palesemente sbagliato/incoerente: scartato dal training, **marcato** (non cancellato).
- **novel** (ortogonale) — scena/oggetto mai visto (OOD): **non scartare**, flagga → caso dubbio.

## Controlli
1. **Consistenza temporale.** IoU della maschera di una classe tra frame adiacenti < soglia (es.
   0.3 su oggetti grandi) → flicker → `review`. Comparsa/sparizione istantanea di classe grande → `review`.
2. **Confidenza.**
   - Classe non critica sotto soglia (es. 0.4) → `review`.
   - Classe **critica** (`person`/`vehicle`/`bicycle`/`obstacle`/`animal`) sotto soglia →
     **NON reject**: `review` + tieni (umiltà sul pericolo; vedi linea rossa verifier).
3. **Coerenza fisica (da `categories.yaml`).** Incoerenze → `reject`/`review` con motivazione:
   - `sky` sotto `road`; `road` sopra `building`; `person` < pochi px; drivable=0 su tutto il
     frame mentre la bici si muoveva; `vehicle` che occupa >90% frame all'improvviso.
4. **Novità / OOD.** Energy-score dai logit (`segment_gate_jev_approach.md` §3). Oltre soglia →
   `novel`. OOD = **non scartare mai**: è esattamente il pericolo nuovo da non perdere.
5. **Copertura.** Frame senza drivable né ostacoli ma con velocità > 0 → sospetto → `review`.

## Output per frame
`{frame_id, status: ok|review|reject, reasons: [...], novel: bool, novel_score: float}`.
I `review`/`novel` con peso alto (classe critica, molti frame contigui) → l'orchestratore li
impacchetta come caso dubbio.

## Regola d'oro
Nel dubbio su una classe critica: **tieni e flagga**, mai scartare. Un falso `reject` su un pedone
è l'errore che non ci si può permettere. Over-review è sicuro; under-review è il rischio.

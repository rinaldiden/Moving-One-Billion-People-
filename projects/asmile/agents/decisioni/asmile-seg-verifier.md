# Decisioni di asmile-seg-verifier

Scritte con `palla.py decido` mentre lavora. Append-only: una decisione sbagliata non si cancella, se ne scrive una nuova che la corregge.

- 2026-11-10 12:44 **L1.classi ricontrollo numeri** → Nessuna rigirata SAM 3: ricontrollo da res_ctrl.jsonl/metriche. Numeri tornano: 001 22/113 (19.5%) e logger 6/107 (5.6%) @0.70, cancello 55/55, delta classi vecchie 0%. Perché: CPU occupata da calib_charuco_dual, nessuna GPU necessaria: i jsonl bastano per ricalcolare.
- 2026-11-10 12:44 **Falsi veri per unita (ispezione fogli falsi_*)** → 001: ~13 falsi veri (portoni/porte/impalcature/muretti/arcate) su 113 = ~11.5%, 8-9 ringhiere/paletti plausibilmente reali, 1 cancellata vera; logger: 4/107=3.7% (2 ambigue). Entrambi >2%. Perché: Fogli a bassa risoluzione: stima per ispezione; tolti i reali il criterio resta fallito, il VETO non dipende dall'ambiguita.
- 2026-11-10 12:44 **Verdetto L1.classi in ombra** → PASSA --parziale solo su cancello (55/55, 1 passaggio, frame correlati) e classi vecchie delta 0%; falsi FALLITI; griglie/catene/dossi NON VERIFICATO. Perché: Eccezione ombra solo-Mac; PASSA pieno impossibile con falsi >2% su entrambe le unita.

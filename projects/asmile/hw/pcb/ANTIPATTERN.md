# Antipattern — errori fatti e regola che li evita (estratto da REGISTRO.md)

- **A1 — generatore che sovrascrive modifiche a mano.** Rigenerare file "GENERATO" cancella quello che qualcuno ha
  aggiunto a mano dopo. Regola: dopo ogni rigenerazione `git diff` riga per riga; le regole nuove si scrivono nel
  generatore, mai solo nel file generato. (Registro 2026-11-18 14:40)

# Censimento strutture Italia — disabilità & anziani (outreach)

> **Stato: BOZZA / SEED — DA FIRMARE Daniele prima di qualsiasi invio.**
> Due liste di recapiti da usare per raggiungere le realtà che il Movimento serve:
> centri/associazioni per persone con disabilità, e RSA/case di riposo/centri per anziani.

Non è una lista fredda: sono i luoghi dove vivono le Persone al centro (la nonna nella
casa di riposo, la Persona al centro disabili — quelle che tengono il volante del
desiderio). L'inclusione è il punto da cui nasce l'innovazione, non il punto d'arrivo.

## I due file
- `disabilita_centri_italia.csv` — centri e associazioni per persone con disabilità.
- `rsa_anziani_italia.csv` — RSA, case di riposo, centri per anziani.

Formato: CSV UTF-8, separatore virgola → si apre in Excel / Google Sheets con doppio clic.
Colonne:
`nome, tipo, categoria, regione, provincia, citta, indirizzo, telefono, email, pec, sito_web, facebook, instagram, fonte, verificato, note`

Regola dura del dato: **cella vuota se non trovata, mai riempita a intuito**; `fonte`
sempre valorizzata; `verificato = web AAAA-MM-GG` solo se il recapito è stato letto su
fonte affidabile, altrimenti `da_verificare`.

## Come si espande (l'agente)
Il censimento lo fa l'agente **`censimento-strutture-italia`** (`.claude/agents/`), guidato
dalla skill **`censimento-italia`** (`.claude/skills/`). Lavora a strati — nazionale →
regionale → provinciale — e **appende** righe nuove deduplicando. Non riscrive i file.

Lancialo dicendo la fetta: es. *"censisci le RSA della Lombardia"* o *"scendi dai soci
Anffas del Veneto"*. Coprire tutta l'Italia è un lavoro a ondate: questo README tiene il
conto di cosa è già mappato.

## Fonti autorevoli da cui pescare (mappa del territorio)

**Disabilità**
- **RUNTS** — Registro Unico Nazionale del Terzo Settore (ricerca pubblica): la fonte
  ufficiale degli enti, filtrabile per regione/attività.
- **Federazioni ombrello** → scendere ai soci/sezioni locali: Anffas
  (`anffas.net/it/strutture`), FISH ETS + delegazioni regionali, FAND, UICI, ENS, UILDM,
  AISM, ANMIC, UNMS, LEDHA (Lombardia).

**Anziani / RSA**
- **Registri regionali di accreditamento socio-sanitario** — le RSA sono autorizzate a
  livello di Regione/ATS/ASL: ogni Regione pubblica l'elenco degli enti accreditati (è la
  fonte più completa e affidabile per struttura+indirizzo). 20 Regioni: coprirle a una a una.
- **UNEBA** (nazionale + comitati regionali, `uneba.org/regioni`), **Auser** e reti locali.

## Copertura — log delle ondate (append)
| Data | Ondata | Righe disabilità | Righe RSA | Cosa manca |
|------|--------|------------------|-----------|------------|
| 2026-08-30 | Seed anchor nazionali (federazioni ombrello) | 4 | 5 | Tutto il livello regionale/provinciale: 20 Regioni × entrambi i mondi. Facebook/Instagram non ancora raccolti (celle vuote) |

## DA FIRMARE / decidere (Daniele)
1. **Priorità geografica**: partire da Lombardia/Valtellina + Poschiavo (dove il Movimento
   è già radicato, Olympink) o coprire a tappeto per regione?
2. **Profondità**: fermarsi alle federazioni/enti capofila, o scendere a ogni singola
   struttura (migliaia di righe → serve decidere quanto a fondo).
3. **Uso**: la lista serve a preparare un contatto — il testo e l'invio seguono la voce
   email in `shared/email-voce-daniele.md` e **non partono in autonomia** (tocca persone e
   nuove relazioni: bozza + conferma). Questa cartella prepara, non spedisce.

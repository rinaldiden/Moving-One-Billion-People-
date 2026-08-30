---
name: censimento-italia
description: Runbook per censire dal web tutte le strutture italiane per persone con disabilità e tutte le RSA/case di riposo/centri per anziani, e raccoglierne i recapiti (telefono, email, PEC, sito, Facebook, Instagram) in due CSV pronti per l'outreach. Usa quando servono liste di contatti verificati per scrivere a queste realtà. Orchestra l'agente censimento-strutture-italia. NON invia nulla: prepara la lista, l'invio lo decide Daniele.
---

# Runbook — censimento strutture Italia (disabilità & anziani)

Trasforma "il web" in **due liste di recapiti usabili**: centri/associazioni per persone
con disabilità, e RSA/case di riposo/centri per anziani. Serve a preparare l'outreach del
Movimento verso i luoghi dove vivono le Persone al centro — non è una lista fredda.

Deliverable in `outreach/censimento-italia/`:
- `disabilita_centri_italia.csv`
- `rsa_anziani_italia.csv`
- `README.md` — schema, fonti autorevoli, log di copertura, cose da firmare.

## Cosa NON è
- **Non spedisce email.** Prepara la lista; il testo e l'invio seguono
  `shared/email-voce-daniele.md` e non partono in autonomia (tocca persone/nuove relazioni).
- Non riscrive i file: ogni ondata **appende** righe nuove e deduplica.
- Non inventa recapiti: cella vuota + `da_verificare` nel dubbio.

## Come si lancia
L'agente è **`censimento-strutture-italia`** (`.claude/agents/`). Diglielo a fette:
- *"censisci le RSA accreditate della Lombardia"*
- *"scendi dai soci Anffas del Veneto e prendine i recapiti"*
- *"arricchisci le righe esistenti con Facebook/Instagram dai loro siti"*

Coprire tutta l'Italia è un lavoro a **ondate**: una Regione o una federazione per volta.

## Il metodo in 4 passi (dal macro al micro)
```
1 ombrello nazionale ─▶ 2 registro regionale ─▶ 3 struttura singola ─▶ 4 social/email
```
1. **Nazionale.** Parti dai contenitori: RUNTS + federazioni (Anffas, FISH, FAND, UICI,
   ENS, UILDM, AISM, ANMIC, UNMS, LEDHA) per la disabilità; UNEBA + Auser per gli anziani.
2. **Regionale.** Per gli anziani è lì la miniera: i **registri regionali di accreditamento
   socio-sanitario** (Regione/ATS/ASL) elencano le RSA con indirizzo. 20 Regioni, tutte.
3. **Struttura singola.** Sito ufficiale, Pagine Gialle/Bianche, sito comunale → indirizzo,
   telefono, email, PEC.
4. **Social/email.** Dal sito della struttura pesca i link Facebook/Instagram e l'email reale.

## Schema CSV (Excel/Sheets, UTF-8, virgola)
`nome, tipo, categoria, regione, provincia, citta, indirizzo, telefono, email, pec, sito_web, facebook, instagram, fonte, verificato, note`
- `fonte` sempre valorizzata (URL/registro): dato senza fonte non è un dato.
- `verificato`: `web AAAA-MM-GG` se letto su fonte affidabile, altrimenti `da_verificare`.
- Campo non trovato → cella vuota, **mai a intuito**.

## Al termine di ogni ondata
Aggiorna la tabella "Copertura" nel `README.md` (Regioni/federazioni coperte, righe nuove,
cosa manca). È lì che si legge quanto del territorio è già mappato.

## Linea rossa
Una email o un numero sbagliato in una lista "pronta da mandare" è peggio del vuoto: si
scrive alla Persona sbagliata. Umiltà e rispetto: nel dubbio, non riempire. E niente invio
autonomo — la lista prepara, Daniele decide.

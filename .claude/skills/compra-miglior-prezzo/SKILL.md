---
name: compra-miglior-prezzo
description: Cercare dove comprare un pezzo (o una lista/BOM intera) al prezzo più basso SPEDIZIONE COMPRESA — Amazon.it, AliExpress e altri negozi trovati dal motore di ricerca — verificando i fornitori (non il primo della lista) e accorpando gli ordini per stare sopra le soglie di spedizione gratuita. Usa quando Daniele dice "cerca dove comprare", "miglior prezzo", "lista acquisti", "BOM da ordinare", da qualsiasi progetto di ~/progetti. NON compra: prepara il carrello, l'acquisto parte solo con l'ok di Daniele.
---

# Comprare al miglior prezzo — runbook del doppio

Lo stesso pezzo costa 1,26 € su AliExpress, 6,99 € su Amazon e 11 € in un negozio italiano. La differenza vera però
la fanno tre cose che il "primo risultato" nasconde: **la confezione** (3 pezzi o 1?), **la spedizione** (gratis solo
sopra soglia, o "sul tuo primo ordine") e **chi vende** (venditore con 100% feedback o uno senza storia). Questa skill
le mette in fila, per ogni voce, e poi sceglie la combinazione di negozi col **totale più basso**.

## Strumento
`cerca_prezzi.py` (in questa cartella). Python con Playwright: `~/.asmile_depth_venv/bin/python`.
Chrome vero, **headless** (non ruba lo schermo), profilo dedicato `~/.claude_pw_shop` (CAP Amazon già impostato:
23037 Tirano; per cambiarlo `cerca_prezzi.py cap <CAP>`).

```bash
PY=~/.asmile_depth_venv/bin/python; S=~/.claude/skills/compra-miglior-prezzo/cerca_prezzi.py
$PY $S cerca "ADS1115 modulo" --deve ADS1115 --escludi IDGSR,MSOP,chip     # una voce, JSON
$PY $S bom lista_acquisti.csv --out <cartella> --titolo "..."              # lista intera → offerte.json + carrello.md
$PY $S carrello <cartella>/offerte.json [--prime]                            # ricalcola solo l'accorpamento
```

`lista_acquisti.csv`: `id,gruppo,qty,query,deve,escludi,note`
- `deve` = token che il titolo DEVE contenere (separati da `|`; alternative con `/`, es. `RTC/Raspberry`). È il
  controllo "stesso prodotto": si confronta **il meccanismo** (sigla del chip, specifica), non il nome commerciale.
- `escludi` = token che lo scartano (es. il chip nudo `IDGSR/MSOP` quando serve il modulo).
- `gruppo` = `base` / `revisione` / `opzionale` → il carrello fa un totale per scenario.

## Il metodo (dal macro al micro)
1. **Lista prima.** Parti dall'ultimo BOM del progetto; togli ciò che "già c'è"; per ogni voce scrivi la specifica
   che conta (tensione, Vgs, corrente, interfaccia). Se il BOM ha una revisione non firmata, metti quei pezzi in un
   gruppo a parte: non decidere al posto di Daniele.
2. **Cerca su tutte le fonti** — Amazon.it (16 risultati), AliExpress (20), web via DuckDuckGo (pagine prodotto con
   prezzo in JSON-LD: negozi italiani/UE, distributori).
3. **Filtra i fornitori, non fermarti al primo:**
   - titolo coerente con `deve`/`escludi`;
   - Amazon: voto ≥ 4.0 e ≥ 10 recensioni; sulle 2 migliori apre la scheda → *spedito da*, *venduto da*, consegna
     reale, % feedback positivo del venditore (scarta < 85%);
   - AliExpress: voto ≥ 4.5 e ≥ 50 venduti; "Choice" riconosciuto (gratis da 10 € accorpati).
4. **Normalizza la confezione:** "3 moduli", "5PCS" → €/pezzo e numero di confezioni per la qty richiesta.
5. **Accorpa:** prova le combinazioni delle 3 migliori offerte per voce e calcola merce + spedizione per negozio
   (Amazon sopra 39 € non-Prime, AliExpress Choice sopra 10 €, negozio web con la sua soglia se scritta in pagina).
6. **Scrivi il carrello** (`carrello.md`): ordini per negozio, totale per scenario, alternative per voce con link.

## Limiti onesti (dichiarali sempre nel report)
- **AliExpress scheda prodotto = captcha** in headless: negozio e spedizione esatta non si leggono da script. Si usa
  la card della ricerca (prezzo, voto, venduti, "Spedizione gratuita"/"da 10€"); card senza info → stima 2,50 €
  marcata. Verifica finale del negozio nel carrello reale.
- **eBay** blocca il browser headless: entra solo se il motore di ricerca porta a una sua pagina leggibile.
- **Amazon "Consegna GRATUITA sul tuo primo ordine"**: vale per un account nuovo; per Daniele conta Prime sì/no
  (`--prime`). Le spedizioni a stima (4,99 € Amazon sotto soglia, 6,90 € negozio web) sono marcate.
- Prezzi del giorno: **il carrello reale fa fede**. Rilancia prima di comprare.

## Confine (non negoziabile)
Prepara, non compra. Quando Daniele darà la carta, l'acquisto resta un'azione che tocca **denaro**: carrello
proposto → ok esplicito di Daniele per quell'ordine → solo allora checkout (`amazon.py compra`, vedi sotto:
tutto il resto — account, password, carrello, indirizzo, carta — lo faccio da solo). Mai salvare i dati della carta in chiaro
(Portachiavi macOS, come in `~/progetti/ACCESSI.md`).

## Dove scrivere il risultato
Nella casa del progetto, accanto al BOM: es. `projects/asmile/logger/hw_v2/acquisti/` (lista CSV + offerte.json +
carrello.md + README con le scelte da firmare). Le decisioni d'acquisto aperte vanno nel registro del progetto
(`.collegio/QUESTIONI_APERTE.md` per Asmile).

## Autonomia: account, password, Amazon (voce di Daniele 2026-11-14 — regola d'acquisto D014 DA FIRMARE)
Daniele: *"devi essere in grado di farla da solo: salvare le password nel Portachiavi, creare gli account dove
serve, oppure andare avanti come ospite… dopo devi essere in grado di fare tutto da solo."*

**Ordine di preferenza in un negozio nuovo:** 1) **ospite** se il checkout lo permette (meno account = meno
superficie); 2) se l'account è obbligatorio → lo creo io con `account.py nuovo <sito>` (password forte generata e
salvata nel Portachiavi `claude-<sito>`, mai stampata) e email `daniele@movingonebillionpeople.org`; 3) codice di
verifica via email → lo leggo dalla casella collegata (Gmail MCP `search_threads`); se arriva su una casella che non
leggo o via SMS → una riga a Daniele (`scrivi_a_daniele.py`), non tento altro.

```bash
PY=~/.asmile_depth_venv/bin/python; D=~/.claude/skills/compra-miglior-prezzo
$PY $D/account.py nuovo robotics.it            # crea password + registro (senza password) in ~/.config/doppio/
$PY $D/account.py dati                          # nome, indirizzo di spedizione, email per form e ospite
$PY $D/account.py elenco                        # dove ho già un account
# nei form:  from account import password, dati ;  pg.fill("#pw", password("robotics.it"))
```

**Amazon (account di Daniele, più carte e più indirizzi sullo stesso account):** `amazon.py`, profilo Chrome
`~/.claude_pw_shop` (headless; un processo alla volta, è lo stesso profilo di `cerca_prezzi.py`).
- `login` — **una volta, lo fa Daniele**: Chrome visibile, entra con password + codice, "Resta connesso".
- `stato --dettagli` — loggato? indirizzi (→ quello giusto) e carte per ultime 4 cifre.
- `aggiungi ASIN:qty …` · `carrello` · `svuota` (sempre carrello pulito prima di un ordine: è condiviso con Daniele).
- `prepara` — checkout: **impone indirizzo "Rinaldi Daniele, via San Carlo 25" e la carta con le ultime 4 cifre
  di `acquisti.json`**, rilegge il riepilogo, legge il totale, fa screenshot e **si ferma**. Se indirizzo o carta
  non tornano, o il totale non si legge → si ferma con il problema scritto. Non indovina mai una carta.
- `compra --totale X --ok "Daniele, <canale>, <ora>"` — rifà `prepara` e clicca "Acquista ora" **solo** se totale
  (al centesimo), indirizzo e carta coincidono con l'approvato. Registro + screenshot in `~/.config/doppio/amazon_checkout/`.

**Sessione scaduta:** se Amazon chiede di nuovo la password, la leggo dal Portachiavi (`claude-amazon.it`, la
salva Daniele con `account.py salva amazon.it --utente <email>`: la digita lui, non passa in chat). Se chiede il
codice OTP (SMS/app) → Daniele, con `scrivi_a_daniele.py`; riapro `login` visibile solo se lui è al Mac.

**Provato il 2026-11-14 (da ospite, profilo clonato):** stato (vede "non loggato"), aggiungi da scheda prodotto
(il link `/gp/aws/cart/add` ora rimanda al login), carrello con righe e subtotale, svuota. **Non ancora provati:**
`prepara`/`compra` sul checkout vero — servono login di Daniele e le ultime 4 cifre della carta. Il primo `prepara`
reale va guardato a mano sullo screenshot: i selettori del checkout Amazon cambiano spesso.

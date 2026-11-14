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
proposto → ok esplicito di Daniele per quell'ordine → solo allora checkout. Mai salvare i dati della carta in chiaro
(Portachiavi macOS, come in `~/progetti/ACCESSI.md`).

## Dove scrivere il risultato
Nella casa del progetto, accanto al BOM: es. `projects/asmile/logger/hw_v2/acquisti/` (lista CSV + offerte.json +
carrello.md + README con le scelte da firmare). Le decisioni d'acquisto aperte vanno nel registro del progetto
(`.collegio/QUESTIONI_APERTE.md` per Asmile).

# CapomastroBridge — il ponte tra zio code e Fusion 360

Permette a Claude Code di **leggere e modificare il modello CAD** di Fusion 360
mandando comandi via HTTP a un add-in che gira dentro Fusion.

```
  Tu (chat)  ──►  zio code  ──►  client.py ──HTTP──►  add-in dentro Fusion  ──►  modello .f3d
                                (curl/python)         (localhost:8765)
```

## Perché serve un ponte

Le API di Fusion (`adsk.core`, `adsk.fusion`) **girano solo dentro Fusion**.
Un processo esterno (il terminale) non può chiamarle. L'add-in
`CapomastroBridge` apre un piccolo server HTTP **dentro** Fusion e traduce le
richieste in chiamate API, eseguite in sicurezza sul main thread.

## Installazione (una volta sola)

1. **Copia l'add-in** nella cartella AddIns di Fusion:

   ```bash
   cp -R "fusion-bridge/CapomastroBridge" \
     "$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/"
   ```

2. **Avvia Fusion 360** e apri il modello di Ca' del Papa (`.f3d`).

3. In Fusion: menu **Utilities → Scripts and Add-Ins** (o `Shift+S`) →
   scheda **Add-Ins** → seleziona **CapomastroBridge** → **Run**.
   (Spunta *Run on Startup* se lo vuoi sempre attivo.)

4. Appare il messaggio **"CapomastroBridge ATTIVO — in ascolto su
   http://127.0.0.1:8765"**. Il ponte è aperto.

## Verifica (dal terminale)

```bash
curl http://127.0.0.1:8765                       # -> {"ok": true, "pong": true, ...}
python3 fusion-bridge/client.py info             # documento, unità, n. corpi/parametri
python3 fusion-bridge/client.py params           # tutti i parametri utente
```

## Comandi disponibili

| Comando client                              | Cosa fa                                   |
|---------------------------------------------|-------------------------------------------|
| `client.py ping`                            | verifica che il ponte risponda            |
| `client.py info`                            | documento, unità, conteggi                |
| `client.py params`                          | legge tutti i parametri utente            |
| `client.py set <nome> "<espr>"`             | cambia un parametro (es. `set colmo "3050 mm"`) |
| `client.py bodies`                          | corpi: volume, area, bounding box         |
| `client.py save ["msg"]`                    | salva il documento                        |
| `client.py export <step\|stl\|f3d\|iges> <path>` | esporta                              |
| `client.py shot <path.png>`                 | screenshot del viewport                   |
| `client.py exec <file.py \| ->`             | esegue codice API arbitrario (vedi sotto) |

## Il comando `exec` — la chiave che apre la strada

`exec` esegue codice Python nel contesto Fusion, con già disponibili:
`adsk`, `app`, `ui`, `design`, `root`. Imposta una variabile `result`
(serializzabile) per riavere dati indietro. Esempio:

```python
# conta le facce del primo corpo
body = root.bRepBodies.item(0)
result = {"name": body.name, "faces": body.faces.count}
```

```bash
python3 fusion-bridge/client.py exec quel_file.py
```

Così qualsiasi operazione nuova (sketch, estrusioni, giunti…) non richiede di
toccare l'add-in: io scrivo il codice API e lo mando via `exec`.

## Sicurezza

- Ascolta **solo su 127.0.0.1** — nessun accesso dalla rete.
- `exec` esegue codice arbitrario: accettabile perché gira **solo in locale**
  sulla macchina di Daniele ed è esattamente ciò che serve per "fare".
- Il ponte tocca il modello solo quando arriva un comando: nessuna azione
  automatica, nessun salvataggio non richiesto.

## Se qualcosa non va

- **"Ponte non raggiungibile"** → l'add-in non è in Run in Fusion (rifai punto 3).
- **"Nessun design attivo"** → apri un file `.f3d` in Fusion.
- **Fusion si blocca** → l'add-in esegue sempre sul main thread con timeout
  120s; se un `exec` è troppo pesante, arriva un errore di timeout invece del
  freeze. Ferma e riavvia l'add-in da Scripts and Add-Ins.

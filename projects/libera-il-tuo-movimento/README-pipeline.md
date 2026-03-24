# 🚴 LIBERA IL TUO MOVIMENTO

> Pipeline multi-agente per la generazione autonoma di giunti organici per telai — dal linguaggio naturale al G-code.

Niente più Fusion 360 per disegnare ogni giunto. Descrivi il telaio, la pipeline pensa, progetta e genera il codice macchina pronto per la tua Bambu Lab X1C o Qidi con Klipper.

---

## Il problema che risolve

Ogni giunto di un telaio organico richiede ore di modellazione in Fusion 360. Questa pipeline sostituisce quel processo con una catena di agenti AI specializzati che ragionano come un team di progettazione reale: l'architetto, il meccanico da campo, il pilota, il dimensionatore, e infine chi traduce tutto in movimenti macchina.

---

## Architettura della Pipeline

```
TU (linguaggio naturale)
         │
         ▼
[Agente 1 — Architetto del Telaio]
  Legge la descrizione → produce wireframe 3D strutturato (JSON)
         │
         ▼
[Agente 2 — Strutturista da Campo]
  Analisi macro degli sforzi per nodo
  Principio guida: "una vite M4 può reggere ma se non ci passano
  le dita con i guanti in salita, è sbagliata"
         │
         ▼
[Agente 3 — Il Pilota]
  Traduce geometria in sensazioni di guida previste
  Suggerisce aggiustamenti basati sul feeling reale, non sui numeri FEM
         │
         ▼
[Agente 4 — Dimensionatore Sezioni]
  Sceglie diametri e spessori tubi per ogni segmento
  Database: bambù, Al6061, CrMo, carbonio
         │
         ▼
[Agente 4B — Geometra dei Componenti]
  Mappa ingombri reali (movimento centrale, freni, cavi)
  Definisce zone proibite e clearance minime per i giunti
         │
         ▼
[Agente 5 — Generatore Giunti]
  Geometria 3D organica per ogni nodo
  Orientamento ottimale sul piatto di stampa
  Parametri slicing suggeriti
         │
         ▼
[Agente 6 — Revisore Visivo]
  Approva o rigetta forma estetica e stampabilità
         │
         ▼
[Agente 7 — Traduttore G-code]
  G-code nativo per Bambu X1C o Qidi/Klipper
  Con start/end script e parametri materiale
         │
         ▼
output/joint_output.gcode → OrcaSlicer per verifica visiva
```

---

## Setup

### 1. Clona il repo

```bash
git clone https://github.com/rinaldiden/libera-il-tuo-movimento.git
cd libera-il-tuo-movimento
```

### 2. Ambiente Python

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# oppure: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 3. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Apri `.env` e imposta:

```
ANTHROPIC_API_KEY=sk-ant-...       # La tua chiave API Anthropic
ORCA_SLICER_PATH=/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer
```

---

## Uso — Pipeline completa

```bash
python main.py "Nodo del movimento centrale per cargo bike, tre tubi in entrata: 
tubo orizzontale 32mm, carro posteriore 28mm chainstay, piantone sella 31.6mm. 
Bambù per il telaio principale, giunti in PETG-CF."
```

L'output G-code viene salvato in `output/joint_output.gcode`.

---

## Verifica visiva con OrcaSlicer (Blocco 2)

OrcaSlicer è il tuo strumento di verifica. Permette di vedere la stampa layer per layer prima di mandare in macchina — una simulazione inversa: parti dal G-code e vedi come il pezzo si costruisce sul piatto.

### Come aprire il G-code in OrcaSlicer

**Metodo 1 — Automatico (se OrcaSlicer è configurato in .env):**
```bash
python tools/orca_bridge.py output/joint_output.gcode
```

**Metodo 2 — Manuale:**
1. Apri OrcaSlicer
2. `File` → `Import` → `Import G-code`
3. Seleziona `output/joint_output.gcode`
4. Usa il **slider layer** in basso a sinistra per scorrere la stampa layer per layer
5. Attiva la vista **"Travel"** per vedere anche i movimenti a vuoto
6. Attiva **"Overhang"** per evidenziare le zone critiche

### Cosa controllare

- **Layer 1-3**: adesione al piatto, brim se presente
- **Zone socket**: i fori dove entrano i tubi devono avere pareti continue, niente gaps
- **Transizioni organiche**: le nervature devono crescere gradualmente, non a scalini bruschi
- **Overhang**: zone rosse = problemi → torna all'Agente 5 e cambia orientamento

### Statistiche rapide senza aprire OrcaSlicer

```bash
python tools/orca_bridge.py output/joint_output.gcode --stats-only
```

Output:
```
layer_count: 245
max_z_mm: 49.0
filament_used_mm: 8420
estimated_time_min: 187
```

---

## Blocco 3 — Training automatico

### Da OrcaSlicer (profili materiale e macchina)

Estrae automaticamente tutti i tuoi profili di stampa:

```bash
python training/orca_extractor.py
```

Trova da solo la directory profili OrcaSlicer (`~/Library/Application Support/OrcaSlicer/user/` su macOS).
Salva tutto in `training/data/orca_profiles/orca_profiles.json`.

Questi dati vengono usati dall'Agente 7 per generare G-code calibrato sui tuoi materiali reali.

### Da Fusion 360 (libreria giunti)

Richiede il **Fusion 360 MCP server**: https://github.com/mycelia1/fusion360-mcp-server

```bash
# 1. Installa e avvia il MCP server dentro Fusion 360
# 2. Poi:
python training/fusion360_extractor.py
```

Estrae geometria e parametri dai tuoi f3d esistenti e li aggiunge al dataset di training.
Ogni giunto esistente diventa un esempio: input (parametri geometrici) → output (G-code corrispondente).

---

## Struttura del repo

```
libera-il-tuo-movimento/
├── main.py                    # Entry point
├── agents/
│   ├── orchestrator.py        # Coordina la pipeline
│   ├── agent1_architect.py    # Wireframe dal linguaggio naturale
│   ├── agent2_structural.py   # Analisi strutturale da campo
│   ├── agent3_pilot.py        # Sensazioni di guida
│   ├── agent4_dimensioner.py  # Dimensionamento sezioni tubi
│   ├── agent4b_components.py  # Ingombri componenti standard
│   ├── agent5_joint_generator.py  # Geometria giunti organici
│   ├── agent6_visual_reviewer.py  # Revisione estetica
│   └── agent7_gcode.py        # Traduzione G-code
├── training/
│   ├── fusion360_extractor.py # Estrae dati da Fusion 360
│   ├── orca_extractor.py      # Estrae profili da OrcaSlicer
│   ├── bambu_extractor.py     # Estrae profili da Bambu Studio
│   └── dataset_builder.py     # Costruisce il dataset di training
├── tools/
│   ├── orca_bridge.py         # Bridge per verifica in OrcaSlicer
│   ├── gcode_simulator.py     # Statistiche G-code
│   └── wireframe_parser.py    # Parser wireframe JSON
├── config/
│   ├── agents_config.yaml     # System prompt di tutti gli agenti
│   ├── print_profiles.yaml    # Profili stampa di riferimento
│   └── components_db.yaml     # Database componenti standard
└── output/                    # G-code generato
```

---

## Filosofia

Questo sistema ragiona come un team reale. Ogni agente ha un punto di vista diverso — e i punti di vista contrastano in modo produttivo prima di convergere sul giunto finale.

L'Agente 2 non è un ingegnere da ufficio. Sa che i calcoli puliti non sopravvivono sempre alla strada.
L'Agente 3 non ha sensori — ma ha memoria di cosa si sente e perché.

Il risultato non è il giunto perfetto sulla carta. È il giunto giusto per quel telaio, in quel contesto, per quel pilota.

---

## Roadmap

- [ ] Agente 3 approfondito con sessione di estrazione sensazioni (in sviluppo)
- [ ] Integrazione MCP Fusion 360 per import/export bidirezionale
- [ ] Loop di feedback automatico: stampa → test → correzione agente
- [ ] UI web minimale per interagire con l'Agente 1
- [ ] Supporto multi-nodo: genera tutti i giunti di un telaio completo in un run

---

*Libera il tuo movimento. Un miliardo di persone senza impatto ambientale.*

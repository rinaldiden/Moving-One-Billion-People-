# Sim2real — cosa rubare a Microduck (Pollen Robotics) per Asmile

> Fonte: `pollen-robotics/microduck` (firmware, Apache-2.0) + `microduck_rl` (training).
> Nota: la meccanica del duck è CC-BY-SA-**NC** (non commerciale) e non c'è STL/BOM pubblico: si compra come kit ($399). Il valore per noi è **software + ricetta RL**, non la scocca. Il cugino *Open Duck Mini v2* è invece full-open (STL + BOM <$400, stampabile).

## Perché ci riguarda
Asmile ha già in memoria il piano sim-to-real ([project_simulator_approach], trigger ~10h di dati). Microduck_rl è una ricetta sim2real **completa e leggibile** che possiamo trapiantare senza reinventare.

## La ricetta RL (microduck_rl → Asmile)
- **Sim**: MuJoCo Warp (mjlab) + **PPO**, control loop 50 Hz — stesso rate a cui girano le policy sul robot.
- **BAM (Better Actuator Models)**: modella l'attuatore con legge in tensione + attrito. → Per noi = modellare **VESC sterzo** e **servofreno idraulico** (attrito, stallo, carico idraulico dopo contatto pad-disco) invece di trattarli come attuatori ideali. È il pezzo che fa reggere il transfer.
- **Domain randomization** per-env su: tensione batteria, ritardi comando, attrito. → Per noi: 48V che cala, latenza BLE/GPS, aderenza gomma. Randomizzare questi = policy robusta al mondo vero.
- **Export ONNX**: policy addestrata → ONNX → gira on-edge. → Stesso pattern che ci serve sul Pi 5.
- **AGENTS.md** del repo = "playbook distillato" su reward design e costruzione env. Da leggere prima di scrivere reward per la guida.

## L'architettura software (microduck firmware, Rust)
Anche se non facciamo un biped, il pattern è oro per Asmile:
- Tanti **daemon piccoli** invece di un monolite: `robotd` (loop 50Hz + bus motori), `tofd` (depth), `mediad` (camera WebRTC), `btd`, `configd`, `updaterd` (update firmati + rollback).
- Comunicazione via **JSON-RPC su Unix socket**. → Risolve il nostro problema ricorrente di **owner unico del GPIO**: invece di processi che litigano sul GPIO12 (speed_limiter vs servofreno), un daemon possiede l'attuatore e gli altri gli parlano via socket. Vedi [brake owner].
- **updaterd** con release firmate + rollback + health gate → deploy sicuro sulla fleet senza brickare un Pi in campo.

## Prossimi passi concreti (se si vuole)
1. Clonare `microduck_rl`, leggere `AGENTS.md` + il modulo BAM.
2. PoC: modellare in MuJoCo il solo **sterzo VESC** (1 DOF) con BAM, addestrare una policy "torna al centro / segui angolo target", export ONNX, confronto con gli script attuali (`vesc_return_to_center_*`).
3. Valutare refactor GPIO su socket-owner ispirato ai daemon Rust (senza riscrivere in Rust: stesso pattern in Python).

## Link
- pollen-robotics.com/microduck · github.com/pollen-robotics/microduck · github.com/pollen-robotics/microduck_rl
- Full-open stampabile: Open Duck Mini v2 (orobot.io)

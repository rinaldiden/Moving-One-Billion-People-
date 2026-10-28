# BOM — Logger video standalone (Li-ion + overlay FS)

Unità **staccata dalla bici**, autonoma, per raccogliere ore di video stereo da
elaborare poi sul Mac (dataset sim2real / vtest / segmentazione / cattura di
situazioni nuove).

## Scopo e carico

Solo **video logging**: niente UART/VESC, IMU, encoder, timestamp logging.
Carico reale sul rail 5V = **solo Pi + Camarray** ≈ **5–9 W** (Pi4 ~5–6W,
Pi5 ~7–9W). ⚠️ Da misurare con wattmetro USB. Autonomia = scelta batteria di
Daniele (Li-ion sua).

## SBC — scelto: Raspberry Pi 5 2GB

Deciso (2026-10-28): **Pi 5 2GB**, il Pi5 più economico sufficiente allo scopo.
- Logging video = cattura Camarray + encode **software** (Pi5 non ha H264 HW ma
  regge 2560×800@15fps) + invio WiFi → RAM usata **<1GB**. L'overlay FS tiene in
  RAM pochi MB (i video vanno sulla partizione dati della SD). Il collo è la
  **CPU dell'encode, non la RAM** → 4/8/16GB non darebbero alcun vantaggio.
- Prezzo ~€70–80 da rivenditore ufficiale IT (Melopero/Robotstore), stock variabile.

*(Pi4 scartato: 1 sola CSI e H264 HW limitato a 1920 px larghi → il 2560 stereo
andrebbe downscalato o messo in MJPEG. Il Pi5 lo gestisce nativo in SW.)*

## BOM

| # | Componente | Modello | Qty | Note |
|---|---|---|---|---|
| 1 | SBC | **Raspberry Pi 5 2GB** | 1 | Scelto: capture+encode SW+WiFi usa <1GB; encode 2560 è CPU-bound non RAM-bound → 4/8/16GB inutili. ~€70–80 da rivenditore ufficiale IT (Melopero/Robotstore), verificare stock |
| 2 | Camera stereo | Arducam Camarray HAT (2× OV9281 mono) | 1 | 2560×800, 1 porta CSI, `rpicam-vid` + `arducam_fix.so` |
| 3 | Storage | **SD 128GB già in possesso di Daniele** | 1 | Abbondante: ~540h in H264 500kbit, ~25–28h in MJPEG. Riusata, non si compra |
| 4 | Batteria | **Li-ion — la fa Daniele** | 1 | Nessun acquisto qui. Determina il buck (#5) |
| 5 | Step-down 5V | Pololu D24V50F5 / D24V22F5 (buck) se pacco 2S+; boost se 1S | 1 | Dimensionare sul n° celle in serie del pacco di Daniele |
| 6 | Protezioni pacco | Fusibile 5A + kill switch | 1 | Sul positivo del pacco |
| 7 | *(opz.)* Monitor V | ADS1115 + partitore | 1 | **Solo** per avviso batteria bassa (niente shutdown) |
| 8 | *(opz.)* Buzzer avviso | **Sirena piezo 5V ~100–110 dB** (non il KY-006, troppo debole) | 1 | ~0.3A → pilotata via driver, non da GPIO diretto |
| 9 | *(opz.)* Driver buzzer | 2N2222 (TO-92) + 1kΩ (470Ω se serve più volume) | 1 | GPIO Pi → base via R, sirena sul collettore |

## Niente safe-shutdown: Overlay File System

Verificato (2026-10-28) — **si elimina tutto l'hardware di hold-up/safe-shutdown**
(2× LM74700, supercap 10F, R pre-charge, MOSFET drain + 2N2222, bleed, sense GPIO):

- **`raspi-config → Performance → Overlay File System`**: root in sola lettura,
  scritture in RAM → **stacchi corrente quando vuoi, zero corruzione SD. Costo zero.**
- **Caveat:** l'overlay protegge il **sistema**, non la **partizione dati** su cui
  scrivi i video. Se stacchi mentre registra, al massimo perdi **il file in corso**.
- **Mitigazione:** registra a **segmenti** (`rpicam-vid --segment`, es. 1 file ogni
  15–30s) → perdi solo l'ultimo spezzone. Per un logger è accettabile.
- Partiziona la SD: rootfs piccola (overlay) + partizione dati grande per i video.
- Per cambiare config: disabilita overlay → modifica → riabilita.

Alternative valutate e **scartate** perché l'overlay le rende inutili: supercap
2×25F/2,7V (12,5F@5,4V ≈ 126J ≈ ~27–31s a 4W — matematica corretta, ma hardware in
più); 18650+boost / UPS HAT (più componenti, cella invecchia).

## Avviso batteria bassa (opzionale)

Se Daniele vuole sapere quando la Li-ion è quasi scarica (per ricaricare/non
perdere ore di logging): **ADS1115** legge V_pacco e a soglia bassa fa suonare la
**sirena piezo** (#8). Nessuno shutdown: alla fine la BMS Li-ion stacca, il Pi
muore, e grazie all'overlay non si corrompe nulla. Soglia da fissare sul pacco
di Daniele (regola Li-ion: non scaricare sotto ~3.0V/cella).

## Trasmissione dati — Pi remoto → Mac (reti diverse)

Il logger starà "chissà dove", NON sulla stessa rete del Mac. Servono tre pezzi:

1. **Uplink del Pi:** chiavetta USB 4G/LTE + SIM dati (es. Huawei E3372) o MiFi.
   ⚠️ **Consumo dati:** H264 500kbit ~225 MB/h → ~1,3 GB/sessione 6h; **MJPEG ~30 GB**
   → su SIM **usare H264** (eventualmente downscalato), mai MJPEG.
2. **Canale sicuro Pi↔Mac attraverso Internet** (entrambi dietro NAT).
3. **Push automatico** a fine sessione (su marker `metadata.json`) con **retry** finché
   arriva e marcatura "già inviato"; `rsync --partial` riprende i trasferimenti
   interrotti (vitale su 4G ballerino).

**Baseline consigliata = Tailscale** (già in uso: Mac `macbook-pro-di-daniele`
`100.87.2.77` nel tailnet). Connessione outbound dal Pi, WireGuard E2E, spesso P2P
diretta, `rsync`-over-SSH liscio. Gotcha overlay FS: lo stato `/var/lib/tailscale`
deve persistere (bind-mount su partizione dati scrivibile, o auth key riusabile).

### Due ipotesi Cloudflare (da valutare, SALVATE 2026-10-28)

Alternative/compl. a Tailscale, da scegliere in base al problema reale:

- **Ipotesi A — Cloudflare Tunnel + Access (esporre SSH del Mac).**
  `cloudflared` sul Mac in uscita (no porte aperte sul router) pubblica l'SSH del
  Mac dietro hostname Cloudflare + Access (service token/mTLS: solo il Pi entra).
  Il Pi fa `rsync`-over-SSH via `cloudflared access`.
  → Conviene **se il 4G blocca WireGuard/UDP**: è outbound-only su 443.
  Contro: serve **dominio su Cloudflare** + `cloudflared` su entrambi + token Access;
  **il Mac deve essere acceso**; traffico con hop sull'edge Cloudflare (non P2P).

- **Ipotesi B — Cloudflare R2 come punto di scarico (la migliore in Cloudflare).**
  Il Pi carica le sessioni completate in un bucket **R2** via HTTPS (outbound puro,
  nessun tunnel/porta, es. `rclone`); il Mac le scarica da R2 quando vuole.
  → Conviene **se vuoi che arrivi SEMPRE, anche a Mac spento**: R2 è il relay
  sempre-acceso. Sicuro (HTTPS + token scoped), **niente egress fee** su R2,
  nessun `cloudflared` sul Pi.
  Contro: i dati stazionano nel cloud (privacy/retention da decidere); serve account
  R2 + API token.

**Regola di scelta:** "arriva sempre anche a Mac spento" → **R2**; "4G blocca
Tailscale" → **Tunnel**; nessuno dei due problemi → **resta su Tailscale**.
Per implementare A o B: skill Cloudflare + servono dominio Cloudflare (A) o
bucket R2 + API token (B). Serve confermare la cartella sessioni del recorder.

## Aperto

- se tenere l'avviso batteria (ADS1115 + sirena) o no
- link d'acquisto + prezzi dei pochi pezzi residui (buck + eventuale sirena/ADS1115)

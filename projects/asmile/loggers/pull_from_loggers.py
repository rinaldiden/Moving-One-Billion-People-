#!/usr/bin/env python3
"""
pull_from_loggers.py — scarica i video dai logger asmile sul Mac (PULL Mac<-Pi
via Tailscale/SSH), verifica il checksum, poi CANCELLA la clip dal Pi.

I video vanno in  projects/asmile/asmile-loggers/<logger>/  (LOCALE, mai su git).
Scarica solo i segmenti COMPLETI (esclude l'ultimo in scrittura). L'ultimo si
prende al giro successivo, quando il recorder l'ha chiuso.

"Si attiva quando ci sono video": lanciato periodicamente (launchd/cron) o a mano.
E' il pezzo di DOWNLOAD dell'agente asmile-logger-ingest; l'elaborazione (pipeline
sim2real per migliorare il modello) la fa l'agente / lo skill asmile-sim2real-pipeline.

Uso:  python3 pull_from_loggers.py          # un giro su tutti i logger
"""
import os, subprocess, hashlib, shlex, json, shutil, time

HERE = os.path.dirname(os.path.abspath(__file__))              # .../projects/asmile/loggers
DEST_BASE = os.path.abspath(os.path.join(HERE, "..", "asmile-loggers"))

# --- Scoperta flotta via TAILSCALE: prende TUTTI i logger ONLINE, anche fuori EOLO ---
TAILSCALE_BIN = shutil.which("tailscale") or "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
NAME_PATTERN = "logger"          # sottostringa (case-insens.) che identifica i logger della flotta
DEFAULT_USER = "asmile-logger"
SRC = "/data/recordings"
USER_MAP = {}                    # override utente per-host se serve: {"nomehost": "utente"}

# Bici della flotta con layout "sessions" (dual_cam_recorder: una cartella per sessione con
# video_left.h264 + video_right.h264 + metadata.json). Su #001 /data è la partizione
# persistente fuori dall'overlay. I CSV sensori si COPIANO (restano anche sul Pi).
FLEET = {
    "asmile-001": {"host": "100.75.198.118",          # IP Tailscale (fisso per nodo)
                   "user": "asmile", "layout": "sessions", "src": "/data/training_sessions",
                   "sensors": ["/data/logging/sensors",          # CSV unico sensor_hub 50 Hz (2026-11-07)
                               "/data/logging/speed_limiter", "/data/logging/training_data_pi",   # formato vecchio
                               "/data/logging/limiter_v3"]},   # registro del limiter v3 (ombra/attivo, 24/11)
}

# Fallback statico se Tailscale non è disponibile (host = alias ssh o IP).
LOGGERS = [
    {"name": "asmile-logger", "host": "100.83.200.55",      # IP Tailscale
     "user": "asmile-logger", "src": SRC,
     "sensors": ["/data/logging/sensors"],               # sensor_hub (stesso formato della flotta)
     "frames_glob": "clip_*_frames.csv"},                # istanti dei frame (recorder.sh)
]

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=accept-new"]


def ssh(lg, cmd):
    return subprocess.run(["ssh"] + SSH_OPTS + [f"{lg['user']}@{lg['host']}", cmd],
                          capture_output=True, text=True)


def reachable(lg):
    return ssh(lg, "true").returncode == 0


def discover_loggers():
    """Logger ONLINE sulla tailnet che matchano NAME_PATTERN (li prende anche fuori EOLO)."""
    try:
        r = subprocess.run([TAILSCALE_BIN, "status", "--json"],
                           capture_output=True, text=True, timeout=15)
        data = json.loads(r.stdout)
    except Exception:
        return []
    found = []
    for p in (data.get("Peer") or {}).values():
        host = p.get("HostName") or ""
        ips = p.get("TailscaleIPs") or []
        if not (p.get("Online") and ips):
            continue
        if host in FLEET:
            found.append(dict(FLEET[host], name=host, host=ips[0]))
        elif NAME_PATTERN.lower() in host.lower():
            found.append({"name": host, "host": ips[0],
                          "user": USER_MAP.get(host, DEFAULT_USER), "src": SRC})
    return found


def complete_clips(lg):
    # tutti i .h264 tranne il piu' recente (in scrittura) e l'artefatto %05d
    r = ssh(lg, f"ls -t {lg['src']}/*.h264 2>/dev/null")
    files = [f.strip() for f in r.stdout.splitlines() if f.strip() and "%" not in f]
    return files[1:] if len(files) > 1 else []   # [0] = il piu' recente = in scrittura


def sha256_local(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha256_remote(lg, path):
    return ssh(lg, f"sha256sum {shlex.quote(path)} | cut -d' ' -f1").stdout.strip()


def pull_logger(lg):
    dest = os.path.join(DEST_BASE, lg["name"])
    os.makedirs(dest, exist_ok=True)
    done = 0
    for remote in complete_clips(lg):
        name = os.path.basename(remote)
        local = os.path.join(dest, name)
        # Overlay senza RTC: a ogni boot il recorder riparte dallo STESSO nome (ora finta, es. clip_20261029_163306).
        # Se esiste già un file con quel nome e contenuto diverso è di un altro boot: mai sovrascrivere,
        # lo salvo con l'impronta del contenuto prima dell'indice (clip_..._163306_<sha8>_00031.h264).
        if os.path.exists(local) and sha256_local(local) != sha256_remote(lg, remote):
            stem, idx = name.rsplit("_", 1)
            local = os.path.join(dest, f"{stem}_{sha256_remote(lg, remote)[:8]}_{idx}")
            print(f"  {name}: nome già usato da un altro boot -> {os.path.basename(local)}")
        rc = subprocess.run(
            ["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
             f"{lg['user']}@{lg['host']}:{remote}", local]).returncode
        if rc != 0:
            print(f"  {name}: rsync fallito"); continue
        if sha256_local(local) == sha256_remote(lg, remote):
            ssh(lg, f"rm -f {shlex.quote(remote)}")     # libera il Pi dopo conferma
            done += 1
            print(f"  {name}: OK (checksum confermato) -> cancellato dal Pi")
        else:
            os.remove(local)
            print(f"  {name}: checksum DIVERSO -> ritento al prossimo giro")
    sync_sensors(lg, dest)
    return done


def complete_sessions(lg):
    # sessioni CHIUSE: se il recorder non gira sono tutte chiuse (anche quelle troncate da
    # uno spegnimento, senza end_time); se gira, escludo la più recente (in scrittura).
    r = ssh(lg, f"ls -dt {lg['src']}/session_* 2>/dev/null")
    sess = [f.strip() for f in r.stdout.splitlines() if f.strip()]
    if ssh(lg, "pgrep -f [d]ual_cam_recorder.py >/dev/null").returncode == 0:
        sess = sess[1:]
    return sess


def pull_sessions(lg):
    """Layout #001: video piatti <sessione>_<cam>.h264 (per on_new_videos.sh) + sidecar in <sessione>/."""
    dest = os.path.join(DEST_BASE, lg["name"])
    os.makedirs(dest, exist_ok=True)
    done = 0
    for remote in complete_sessions(lg):
        sess = os.path.basename(remote)
        # Con l'overlay l'orologio riparte da un'ora finta a ogni boot (prima di NTP): lo
        # stesso nome può tornare in boot diversi -> se esiste già con contenuto diverso,
        # suffisso col checksum del video, mai sovrascrivere.
        loc = os.path.join(dest, f"{sess}_left.h264")
        if os.path.exists(loc) and sha256_local(loc) != sha256_remote(lg, f"{remote}/video_left.h264"):
            sess = f"{sess}_{sha256_remote(lg, remote + '/video_left.h264')[:8]}"
        side = os.path.join(dest, sess)
        os.makedirs(side, exist_ok=True)
        files = [f.strip() for f in ssh(lg, f"ls {shlex.quote(remote)}").stdout.splitlines() if f.strip()]
        ok = True
        for name in files:
            rem = f"{remote}/{name}"
            local = (os.path.join(dest, f"{sess}_{name[len('video_'):]}")
                     if name.startswith("video_") and name.endswith(".h264")
                     else os.path.join(side, name))
            rc = subprocess.run(["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
                                 f"{lg['user']}@{lg['host']}:{rem}", local]).returncode
            if rc != 0 or sha256_local(local) != sha256_remote(lg, rem):
                ok = False
                print(f"  {sess}/{name}: rsync/checksum KO -> ritento al prossimo giro")
        if ok:
            ssh(lg, f"rm -rf {shlex.quote(remote)}")       # libera il Pi dopo conferma di TUTTI i file
            done += 1
            print(f"  {sess}: OK ({len(files)} file, checksum confermato) -> cancellata dal Pi")
    sync_sensors(lg, dest)
    return done


def sync_sensors(lg, dest):
    """CSV sensori e istanti dei frame: si COPIANO (restano sul Pi), cartelle assenti = nulla."""
    sens = os.path.join(dest, "_sensors")
    for src in lg.get("sensors", []):
        os.makedirs(os.path.join(sens, os.path.basename(src)), exist_ok=True)
        subprocess.run(["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
                        f"{lg['user']}@{lg['host']}:{src}/", os.path.join(sens, os.path.basename(src)) + "/"],
                       stderr=subprocess.DEVNULL)
    if lg.get("frames_glob"):
        os.makedirs(os.path.join(sens, "frames"), exist_ok=True)
        subprocess.run(["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
                        f"{lg['user']}@{lg['host']}:{lg['src']}/{lg['frames_glob']}", os.path.join(sens, "frames") + "/"],
                       stderr=subprocess.DEVNULL)
        # stesso nome riusato a ogni boot (ora finta): copia anche per boot, così un boot non cancella l'altro
        boot = ssh(lg, "cat /proc/sys/kernel/random/boot_id").stdout.strip()[:8]
        if boot:
            per = os.path.join(sens, "frames", "per_boot", boot)
            os.makedirs(per, exist_ok=True)
            subprocess.run(["rsync", "-a", "-e", "ssh " + " ".join(SSH_OPTS),
                            f"{lg['user']}@{lg['host']}:{lg['src']}/{lg['frames_glob']}", per + "/"],
                           stderr=subprocess.DEVNULL)


# --- Batteria del SOLO logger001 (hostname ancora "asmile-logger"): ADS1115 0x48, A0 = VSW dopo il MOSFET,
# partitore 100k/33k. Sotto 10 V avviso Daniele su Telegram (Daniele 2026-11-17). Ai prossimi logger: LED di stato.
BATT_HOST = "asmile-logger"
BATT_MIN_V, BATT_OK_V = 10.0, 10.3          # isteresi: torna a "carica" sopra 10.3 V
BATT_RIPETI_S = 6 * 3600                    # se resta bassa, riavvisa ogni 6 ore
BATT_STATO = os.path.join(DEST_BASE, ".batteria_logger001.json")
TG_ENV = os.path.expanduser("~/progetti/doppio/telegram-brain/.env")
ADS_PY = (
    "import smbus2,time\n"
    "b=smbus2.SMBus(1);v=[]\n"
    "for _ in range(8):\n"
    " b.write_i2c_block_data(0x48,1,[0xC3,0x83]);time.sleep(0.01)\n"   # AIN0-GND, ±4.096 V, single-shot
    " r=b.read_i2c_block_data(0x48,0,2);x=r[0]<<8|r[1];x-=65536 if x&0x8000 else 0;v.append(x*4.096/32768)\n"
    "print(sum(v)/len(v)*133/33)\n")


def telegram(testo):
    import urllib.request
    env = dict(l.strip().split("=", 1) for l in open(TG_ENV) if "=" in l and not l.startswith("#"))
    env = {k: v.strip().strip('"\'') for k, v in env.items()}
    req = urllib.request.Request(f"https://api.telegram.org/bot{env['TELEGRAM_TOKEN']}/sendMessage",
                                 data=json.dumps({"chat_id": int(env["ALLOWED_USER_ID"]), "text": testo}).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15).read()


def check_batteria(lg):
    import time
    r = ssh(lg, "python3 -c " + shlex.quote(ADS_PY))
    try:
        v = float(r.stdout.strip())
    except ValueError:
        print(f"[{lg['name']}] batteria: lettura fallita ({r.stderr.strip()[:80]})")
        return
    print(f"[{lg['name']}] batteria {v:.2f} V")
    try:
        st = json.load(open(BATT_STATO))
    except Exception:
        st = {}
    now = time.time()
    if v < BATT_MIN_V:
        if now - st.get("avvisato", 0) >= BATT_RIPETI_S:
            telegram(f"🔋 Logger 001: batteria a {v:.1f} V (sotto {BATT_MIN_V:.0f} V). Attaccalo alla corrente.")
            st["avvisato"] = now
            print(f"[{lg['name']}] avviso Telegram inviato")
    elif v >= BATT_OK_V:
        st["avvisato"] = 0
    st.update(ultimo_v=round(v, 2), ultimo_t=now)
    json.dump(st, open(BATT_STATO, "w"))


# --- logger ESP32 (HW3: logger02 e successivi, 2 × ESP32-P4): niente ssh, API HTTP sulla A (la B dietro /b/).
# Indirizzi di riserva per nome (LAN di casa): Tailscale non sempre c'è.
HTTP_HOSTS_EXTRA = {"logger02": ["100.117.207.99", "192.168.1.122"]}


def http_risponde(host, t=4):
    import urllib.request
    try:
        urllib.request.urlopen(f"http://{host}/api/stato", timeout=t).read()
        return True
    except Exception:
        return False


def scarica_con_ripresa(url, part, size, tentativi=6, pausa=3.0, timeout=30, aprire=None, log=print):
    """Scarica url in `part` RIPRENDENDO da dove era arrivato (Range: bytes=N-). 24/11: i clip da 8-10 MB/min andavano in
    timeout a meta' e il .part ripartiva da 0 per sempre. Ritorna True solo se part ha ESATTAMENTE `size` byte.
    Server vecchio che ignora Range (risponde 200): si riparte da 0 (troncato), mai si accoda a meta'.
    Il .part resta sul disco tra un giro e l'altro (si riprende anche al prossimo launchd)."""
    import urllib.request, urllib.error, time, re
    aprire = aprire or (lambda rq: urllib.request.urlopen(rq, timeout=timeout))
    senza_progresso = 0
    for t in range(tentativi):
        off = os.path.getsize(part) if os.path.exists(part) else 0
        if off == size:
            return True
        if off > size:                                   # part piu' lungo del file: non fidarsi, da capo
            os.remove(part)
            off = 0
        rq = urllib.request.Request(url, headers={"Range": f"bytes={off}-"} if off else {})
        try:
            with aprire(rq) as r:
                st = getattr(r, "status", None) or r.getcode()
                cr = r.headers.get("Content-Range", "")
                if off and st == 206:
                    m = re.match(r"bytes (\d+)-", cr)
                    if m and int(m.group(1)) == off:
                        with open(part, "ab") as out:
                            shutil.copyfileobj(r, out, 1 << 16)
                    elif m:
                        raise IOError("Content-Range inatteso")
                    else:
                        # 206 senza Content-Range (proxy /b della A, 24/11): accetto SOLO se i byte ricevuti sono
                        # esattamente size-off; li metto da parte e li accodo a verifica fatta
                        tmp = part + ".r"
                        with open(tmp, "wb") as out:
                            shutil.copyfileobj(r, out, 1 << 16)
                        if os.path.getsize(tmp) == size - off:
                            with open(part, "ab") as out, open(tmp, "rb") as src:
                                shutil.copyfileobj(src, out, 1 << 16)
                            os.remove(tmp)
                        else:
                            os.remove(tmp)
                            raise IOError("206 senza Content-Range e lunghezza diversa da size-offset")
                else:
                    off = 0                              # 200: il server manda tutto dall'inizio
                    with open(part, "wb") as out:
                        shutil.copyfileobj(r, out, 1 << 16)
        except urllib.error.HTTPError as e:
            if e.code == 416:                            # Range oltre la fine: part sbagliato, da capo
                if os.path.exists(part):
                    os.remove(part)
            elif e.code == 503:                          # la scheda ha gia' un trasferimento: aspetto
                log("    scheda occupata (503), aspetto")
            else:
                log(f"    HTTP {e.code}")
        except Exception as e:                           # timeout, reset, IncompleteRead: il .part resta
            log(f"    interrotto a {os.path.getsize(part) if os.path.exists(part) else 0}/{size}: {e}")
        nuovo = os.path.getsize(part) if os.path.exists(part) else 0
        if nuovo == size:
            return True
        senza_progresso = 0 if nuovo > off else senza_progresso + 1
        if senza_progresso >= 3:                         # niente avanza: non martellare la scheda, riprova al prossimo giro
            return False
        time.sleep(pausa)
    return False


def pull_logger02(name="logger02", hosts=None):
    """Scarica un logger ESP32 (A + B dietro /b) in asmile-loggers/<name>/: verifica dimensione, poi cancella."""
    import urllib.request
    def get(url, t=10):
        return urllib.request.urlopen(url, timeout=t)
    if os.path.exists(os.path.join(DEST_BASE, f".pausa_{name}")):     # 24/11: Daniele "smetti di scaricare" (togli il file per riprendere)
        print(f"[{name}] scarico in pausa (file .pausa_{name})")
        return 0
    host = None
    for h in (hosts or HTTP_HOSTS_EXTRA.get(name, [])):
        try:
            get(f"http://{h}/api/stato", 5).read()
            host = h
            break
        except Exception:
            pass
    if not host:
        print(f"[{name}] non raggiungibile - skip")
        return 0
    # 24/11 (giro di Daniele rovinato): scaricare MENTRE registra manda in crisi A e B (la B si e' fermata alle 16:12
    # proprio quando il Mac ha iniziato a scaricare). Regola Daniele 18/11: si scarica solo a bici ferma = logger in pausa.
    try:
        st = json.loads(get(f"http://{host}/api/stato", 5).read())
        if st.get("rec", {}).get("registra") is not False:      # solo se dice chiaramente "non registro" (pausa)
            print(f"[{name}] sta registrando o stato senza 'registra': non scarico, aspetto la pausa")
            return 0
    except Exception as e:
        print(f"[{name}] stato non leggibile ({e}): non scarico")
        return 0
    dest = os.path.join(DEST_BASE, name)
    os.makedirs(dest, exist_ok=True)
    n = 0
    for pref in ("", "/b"):
        try:
            stato = json.loads(get(f"http://{host}{pref}/api/stato").read())
            files = json.loads(get(f"http://{host}{pref}/api/files").read())
        except Exception as e:
            print(f"[{name}{pref or '/a'}] errore elenco: {e}")
            continue
        in_corso = stato.get("rec", {}).get("file", "")
        base_corso = in_corso.replace(".h264", "")
        sess = stato.get("rec", {}).get("sessione", "")
        sens_corso = max([f["nome"] for f in files if f["nome"].startswith("sensors_") and sess and sess in f["nome"]],
                         default="")                     # CSV IMU del minuto in corso (uno al minuto)
        # salute/errori (firmware dal 20/11): il più recente di ogni tipo è ancora aperto
        aperti = {max([f["nome"] for f in files if f["nome"].startswith(pr)], default="") for pr in ("salute_", "errori_")}
        # 23/11: prima la sessione più recente (il giro appena fatto), dentro la sessione in ordine
        import re
        sess_di = lambda n: (re.search(r"(\d{8}_\d{6})", n) or re.search(r"(boot\d+)", n) or [None, ""])[1]
        files = sorted(sorted(files, key=lambda x: x["nome"]), key=lambda x: sess_di(x["nome"]), reverse=True)
        guasti = 0
        for f in files:
            nome, size = f["nome"], f["byte"]
            if base_corso and nome.startswith(base_corso):
                continue                                  # pezzo ancora in scrittura (video + frames)
            if nome == sens_corso:
                continue                                  # CSV IMU ancora aperto
            if nome in aperti:
                continue                                  # salute/errori del minuto in corso
            locale = os.path.join(dest, nome)
            try:
                if not scarica_con_ripresa(f"http://{host}{pref}/dl?f={nome}", locale + ".part", size):
                    guasti += 1
                    print(f"  {nome}: incompleto, il .part resta e si riprende al prossimo giro")
                    if guasti >= 2:
                        print(f"  [{name}{pref or '/a'}] 2 file di fila falliti: smetto per questo giro (non martello la scheda)")
                        break
                    continue
                guasti = 0
                os.replace(locale + ".part", locale)
                urllib.request.urlopen(urllib.request.Request(f"http://{host}{pref}/del?f={nome}", method="POST"),
                                       timeout=10).read()
                print(f"  {nome}: OK ({size} byte) -> cancellato dalla scheda {'B' if pref else 'A'}")
                n += 1
                time.sleep(1.0)                            # pausa fra file: la A respira
            except Exception as e:
                print(f"  {nome}: errore {e}")
    return n


# 24/11 (Daniele: "da tutti gli asmile che si collegano a Tailscale, in automatico"): da launchd la CLI di Tailscale.app
# fallisce SEMPRE (CLIError 3), quindi la scoperta non trovava le unita' nuove. MagicDNS (100.100.100.100) invece risponde
# anche da launchd e solo per i nodi che esistono: provo i nomi della flotta per convenzione.
NOMI_FLOTTA = (["asmile-%03d" % i for i in range(1, 21)] + ["logger%02d" % i for i in range(1, 21)]
               + ["asmile-logger"] + ["asmile-logger%03d" % i for i in range(1, 21)])
REGISTRO = os.path.join(HERE, "flotta_tailscale.json")      # ultimi nodi visti (diagnostica)


def risolvi(nome):
    import socket
    try:
        return socket.gethostbyname(nome)
    except OSError:
        return None


def scopri_magicdns():
    """-> (unita' ssh [Pi], logger HTTP [ESP32]) per i nomi della flotta che MagicDNS risolve."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(16) as ex:
        ips = dict(zip(NOMI_FLOTTA, ex.map(risolvi, NOMI_FLOTTA)))
    pi, esp = [], []
    for nome, ip in ips.items():
        if not ip or not ip.startswith("100."):
            continue
        if nome in FLEET:
            pi.append(dict(FLEET[nome], name=nome, host=ip))
        elif nome.startswith("asmile-") and nome[7:].isdigit():      # Asmile nuova: stesso layout di #001
            pi.append(dict(FLEET["asmile-001"], name=nome, host=ip))
        elif nome.startswith("logger") and nome[6:].isdigit():       # logger ESP32 (HW3 e successivi)
            esp.append((nome, [ip] + [h for h in HTTP_HOSTS_EXTRA.get(nome, []) if h != ip]))
        else:                                                         # logger su Raspberry (asmile-logger...)
            pi.append({"name": nome, "host": ip, "user": USER_MAP.get(nome, DEFAULT_USER), "src": SRC,
                       "sensors": ["/data/logging/sensors"], "frames_glob": "clip_*_frames.csv"})
    try:
        with open(REGISTRO, "w") as f:
            json.dump({k: v for k, v in ips.items() if v}, f, indent=1)
    except OSError:
        pass
    return pi, esp


def main():
    os.makedirs(DEST_BASE, exist_ok=True)
    loggers, esp32 = scopri_magicdns()
    if loggers or esp32:
        print("MagicDNS: " + ", ".join([l["name"] for l in loggers] + [n for n, _ in esp32]))
    else:
        loggers = discover_loggers()
        if loggers:
            print(f"Tailscale: {len(loggers)} logger online -> {', '.join(l['name'] for l in loggers)}")
    if not loggers:
        # da launchd la CLI di Tailscale.app prova ad aprire la GUI e fallisce ("CLIError 3"):
        # allora provo direttamente gli IP Tailscale noti (reachable() scarta chi è offline)
        loggers = LOGGERS + [dict(cfg, name=n) for n, cfg in FLEET.items()]
        print("Tailscale CLI non disponibile -> provo la lista statica: "
              + ", ".join(l["name"] for l in loggers))
    tot = 0
    for lg in loggers:
        if not reachable(lg):
            print(f"[{lg['name']}] non raggiungibile (Tailscale off?) - skip")
            continue
        if lg["name"] == BATT_HOST:
            check_batteria(lg)
        n = pull_sessions(lg) if lg.get("layout") == "sessions" else pull_logger(lg)
        print(f"[{lg['name']}] scaricati+cancellati {n} segmenti")
        tot += n
    if not any(n == "logger02" for n, _ in esp32):
        esp32.append(("logger02", HTTP_HOSTS_EXTRA["logger02"]))     # LAN di casa anche senza Tailscale
    for nome, hosts in esp32:
        n02 = pull_logger02(nome, hosts)
        if n02:
            print(f"[{nome}] scaricati+cancellati {n02} file")
        tot += n02
    if tot:
        print(f"TOTALE {tot} nuovi segmenti in {DEST_BASE}")
        # Hook elaborazione: se esiste on_new_videos.sh, lancialo sui nuovi video
        hook = os.path.join(HERE, "on_new_videos.sh")
        # staccato: l'elaborazione dura ore e NON deve bloccare i download successivi (launchd ogni 5 min
        # non rilancia finché questo processo vive). Un solo hook alla volta (lock).
        lock = os.path.join(DEST_BASE, ".on_new_videos.lock")
        if os.path.isfile(hook) and os.access(hook, os.X_OK):
            subprocess.Popen(["/usr/bin/lockf", "-t", "0", lock, hook, DEST_BASE], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("nessun nuovo video da scaricare")


if __name__ == "__main__":
    main()

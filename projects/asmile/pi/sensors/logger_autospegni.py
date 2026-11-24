#!/usr/bin/env python3
"""Logger HW v2: spegne il Pi quando la bici è ferma da FERMO_MIN minuti.

Movimento = giroscopio sopra GYRO_DPS oppure variazione dell'accelerometro sopra ACC_MG fra due letture.
Allo spegnimento systemd ferma il recorder (chiude i file), imu_wake.service arma l'IMU e gpio-poweroff
porta HOLD a 0 V: l'IRF4905 stacca tutto. Il prossimo movimento riaccende il Pi dall'INT dell'IMU.
Non spegne se c'è uno scaricamento in corso (rsync/scp/sftp).
24/11 (regola Daniele: «mentre si scarica, l'apparecchio resta sveglio»): non spegne nemmeno se in SRC ci sono
ancora registrazioni che il Mac scarica e cancella (pull_from_loggers.py: tutti i .h264 tranne il più recente)
e il Mac è passato (login ssh) negli ultimi MAC_VISTO_MIN minuti. Tetti: MAX_ATTESA_MIN dopo il fermo, e batteria
sotto BATT_MIN_V (ADS1115, come l'avviso del Mac) = spegne comunque e pulito. Lontano da casa (Mac mai visto) = come prima.
"""
import glob, os, subprocess, time

BUS, ADDR = 1, 0x68
FERMO_MIN = float(os.environ.get("FERMO_MIN", "5"))
MIN_ACCESO_MIN = float(os.environ.get("MIN_ACCESO_MIN", "3"))   # dopo l'accensione resta su almeno così
SRC = os.environ.get("SRC", "/data/recordings")
MAC_VISTO_MIN = float(os.environ.get("MAC_VISTO_MIN", "10"))    # il Mac passa ogni 2-5 min
MAX_ATTESA_MIN = float(os.environ.get("MAX_ATTESA_MIN", "180")) # oltre, con file ancora lì e Mac presente, spegne (il pull non riesce)
BATT_MIN_V = float(os.environ.get("BATT_MIN_V", "10.0"))        # stessa soglia dell'avviso Telegram del Mac
GYRO_DPS, ACC_MG = 3.0, 30.0
PASSO_S = 0.2


def s16(h, l):
    return ((h << 8 | l) ^ 0x8000) - 0x8000


def leggi(b):
    r = b.read_i2c_block_data(ADDR, 0x3B, 14)
    acc = [s16(r[i], r[i + 1]) / 16.384 for i in (0, 2, 4)]          # mg a ±2 g
    gyr = [s16(r[i], r[i + 1]) / 131.0 for i in (8, 10, 12)]         # °/s a ±250
    return acc, gyr


def occupato():
    for nome in ("rsync", "scp", "sftp-server"):
        if subprocess.run(["pgrep", "-x", nome], capture_output=True).returncode == 0:
            return nome
    return None   # niente `who`: sul logger c'è sempre la sessione automatica di tty1/seat0


def pezzi_da_scaricare(src=SRC):
    """Come complete_clips() del Mac: tutti i .h264 tranne il più recente (in scrittura)."""
    def mt(x):
        try:
            return os.path.getmtime(x)
        except OSError:
            return None          # sparito fra glob e stat (il Mac cancella): non conta
    f = [(mt(x), x) for x in glob.glob(os.path.join(src, "*.h264")) if "%" not in x]
    f = [x for x in f if x[0] is not None]
    return max(0, len(f) - 1)


def mac_visto_s_fa():
    """Secondi dall'ultimo login ssh (il Mac passa con ssh/rsync); None se non si sa. Anche connessione ssh aperta = 0."""
    try:
        if subprocess.run(["ss", "-Htn", "state", "established", "( sport = :22 )"], capture_output=True, text=True).stdout.strip():
            return 0.0
    except OSError:
        pass
    for unit in ("ssh", "sshd"):
        try:
          r = subprocess.run(["journalctl", "-u", unit, "--no-pager", "-o", "short-unix", "-n", "200", "-g", "Accepted"],
                           capture_output=True, text=True)
        except OSError:
            continue
        tt = [float(l.split()[0]) for l in r.stdout.splitlines() if l[:1].isdigit() and "Accepted" in l]
        if tt:
            return max(0.0, time.time() - max(tt))
    return None


def batteria_v():
    try:
        import smbus2
        b = smbus2.SMBus(BUS); v = []
        for _ in range(8):
            b.write_i2c_block_data(0x48, 1, [0xC3, 0x83]); time.sleep(0.01)       # AIN0-GND, ±4.096 V
            r = b.read_i2c_block_data(0x48, 0, 2); x = r[0] << 8 | r[1]; x -= 65536 if x & 0x8000 else 0
            v.append(x * 4.096 / 32768)
        return sum(v) / len(v) * 133 / 33
    except Exception:
        return None


def aspetta_scarico(pezzi, mac_s, fermo_min, batt_v):
    """Pura. Motivo per NON spegnere (stringa) o None. Il Mac scarica e cancella: con pezzi ancora lì e il Mac
    passato da poco resto sveglio; batteria bassa e tetto di tempo vincono (spegnimento pulito)."""
    if pezzi <= 0:
        return None
    if batt_v is not None and 2.0 < batt_v < BATT_MIN_V:
        return None
    if mac_s is None or mac_s > MAC_VISTO_MIN * 60:
        return None                                   # Mac lontano: comportamento di prima
    if fermo_min - FERMO_MIN > MAX_ATTESA_MIN:
        return None
    return f"{pezzi} file da scaricare, Mac visto {mac_s/60:.1f} min fa"


def main():
    import smbus2
    t_avvio = ultimo_mov = time.monotonic()
    prev, ultimo_log = None, 0.0
    b = smbus2.SMBus(BUS)
    while True:
        ora = time.monotonic()
        try:
            acc, gyr = leggi(b)
            mosso = max(abs(g) for g in gyr) > GYRO_DPS or (
                prev is not None and max(abs(a - p) for a, p in zip(acc, prev)) > ACC_MG)
            prev = acc
        except OSError:
            mosso = True            # IMU muta: nel dubbio resta acceso
            prev = None
        if mosso:
            ultimo_mov = ora
        fermo_min = (ora - ultimo_mov) / 60
        if ora - ultimo_log > 60:
            print(f"fermo da {fermo_min:.1f} min", flush=True)
            ultimo_log = ora
        if fermo_min >= FERMO_MIN and (ora - t_avvio) / 60 >= MIN_ACCESO_MIN:
            chi = occupato()
            if not chi:
                try:       # 24/11: tutta la parte nuova protetta; in errore = comportamento di prima (spegne)
                    p = pezzi_da_scaricare()
                    chi = aspetta_scarico(p, mac_visto_s_fa(), fermo_min, batteria_v()) if p else None
                except Exception as e:
                    print(f"controllo scarico fallito ({e!r}): comportamento di prima, spengo", flush=True)
                    chi = None
            if chi:
                if ora - ultimo_log > 55:
                    print(f"fermo ma occupato ({chi}): non spengo", flush=True)
            else:
                print(f"fermo da {fermo_min:.1f} min: spengo", flush=True)
                subprocess.run(["sync"])
                subprocess.run(["systemctl", "poweroff"])
                return
        time.sleep(PASSO_S)


if __name__ == "__main__":
    main()

"""Hardware VERO (lgpio, smbus2, file di /tmp). L'UNICO file che importa lgpio/smbus2 (dentro le funzioni, mai a livello di modulo).
NON VERIFICATO: mai girato sul Pi (vietato da Daniele per questa fase). Avvio: soglie validate -> flock su GPIO12 -> servo -> loop."""
import json
import os
import signal
import struct
import sys
import time

from .controllo import Controllo, carica_soglie
from .fonti import Campione, sanifica_velocita
from .freno import SERVO_HZ, angle_to_duty
from .lock_gpio12 import LOCK_GPIO12, LockError, acquisisci_lock, acquisisci_lock_attendi   # noqa: F401
from .servizio import STATO_DEFAULT, chiudi_servo, esegui, scrivi_stato
from .validazione import SogliaError

ENC_CUM_FILE = "/tmp/encoder_wheel_cum"        # "<count srotolati> <t_monotonic>" ~880 Hz dal bridge
BLE_FILE = "/tmp/bike_speed"
EMERGENCY_FLAG = "/tmp/emergency_brake"
GPS_JSON = "/tmp/gps_state.json"
GPIO_CHIP, SERVO_PIN = 0, 12
IMU_ADDR, INA_ADDR = 0x68, 0x40
VMAX_VALIDA = 15.0


def parse_gps(testo_json, vmax=VMAX_VALIDA):
    """-> (v, fix) oppure None. Mai eccezioni: dato sporco = nessun dato."""
    try:
        j = json.loads(testo_json)
        v = sanifica_velocita(j.get("speed_ms"), vmax)
        if v is None:
            return None
        return (v, bool(j.get("fix")))
    except (ValueError, AttributeError, TypeError):
        return None


def parse_ble(testo, vmax=VMAX_VALIDA):
    try:
        return sanifica_velocita(testo.split()[0], vmax)
    except (IndexError, AttributeError):
        return None


class ServoLgpio:
    """Backend servo: impulso 50 Hz poi pin libero (hi-Z). Mai 330 Hz, mai LOW continuo."""

    def __init__(self):
        import lgpio
        self.lg = lgpio
        self.h = lgpio.gpiochip_open(GPIO_CHIP)
        self.claimed = False

    def pwm(self, angolo):
        lg = self.lg
        if not self.claimed:
            try:
                lg.gpio_free(self.h, SERVO_PIN)
            except Exception:
                pass
            lg.gpio_claim_output(self.h, SERVO_PIN)
            self.claimed = True
        lg.tx_pwm(self.h, SERVO_PIN, SERVO_HZ, angle_to_duty(angolo))

    def libera(self):
        lg = self.lg
        if self.claimed:
            lg.tx_pwm(self.h, SERVO_PIN, SERVO_HZ, 0.0)
            lg.gpio_free(self.h, SERVO_PIN)
            self.claimed = False

    def chiudi(self):
        try:
            self.lg.gpiochip_close(self.h)
        except Exception:
            pass


class ServoOmbra:
    """SHADOW MODE (Daniele 23/11): stesso controllo, sensori veri, ma il servo NON viene mai toccato. Ricorda solo l'angolo
    che avrebbe comandato: GPIO12 resta libero (nessun lock, nessun claim)."""

    def __init__(self):
        self.angolo = 0.0

    def pwm(self, angolo):
        self.angolo = float(angolo)

    def libera(self):
        pass

    def chiudi(self):
        pass


class RegistroOmbra:
    """Una riga per ciclo con quello che il limiter avrebbe fatto, per confrontarlo con le frenate di Daniele (persistente in /data)."""
    CAMPI = ["t_wall", "t", "fonte", "v", "a", "dec", "v_enc", "a_enc", "enc_fresco", "v_fus", "dec_imu", "d03", "imu_ok",
             "frena", "livello", "a_des", "target", "angolo", "tetto", "rilascia_ora", "bloccato", "motivi", "emergenza"]

    def __init__(self, cartella="/data/logging/limiter_v3"):
        import csv
        os.makedirs(cartella, exist_ok=True)
        self.f = open(os.path.join(cartella, time.strftime("ombra_%Y%m%d_%H%M%S.csv")), "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(self.CAMPI)
        self.n = 0

    def scrivi(self, r):
        self.w.writerow([round(time.time(), 3)] + [r.get(k) if not isinstance(r.get(k), float) else round(r.get(k), 4)
                                                     for k in self.CAMPI[1:]])
        self.n += 1
        if self.n % 50 == 0:
            self.f.flush()


class LettoreSensori:
    """Tutte le letture in try: un sensore che sbaglia = None, mai un'eccezione nel loop. Percorsi e bus iniettabili (test)."""

    def __init__(self, bus=None, enc_file=ENC_CUM_FILE, ble_file=BLE_FILE, gps_json=GPS_JSON, emerg=EMERGENCY_FLAG):
        if bus is None:
            import smbus2
            bus = smbus2.SMBus(1)
            bus.write_byte_data(IMU_ADDR, 0x6B, 0x00)
        self.bus = bus
        self.enc_file, self.ble_file, self.gps_json, self.emerg = enc_file, ble_file, gps_json, emerg
        self._ult_enc_t = None
        self._ult_gps_t = None
        self._ult_ble_m = None
        self._raw_prec = None
        self._raw_uguali = 0

    def imu(self):
        try:
            b = bytes(self.bus.read_i2c_block_data(IMU_ADDR, 0x3B, 14))
        except Exception:
            return None
        if len(b) != 14:
            return None
        self._raw_uguali = self._raw_uguali + 1 if b == self._raw_prec else 0
        self._raw_prec = b
        if self._raw_uguali + 1 >= 5:                     # 14 byte identici da 5 cicli: sensore congelato/sleep -> nessun dato
            return None
        ax, ay, az, _, gx, gy, gz = struct.unpack(">hhhhhhh", b)
        return (ax / 16384.0, ay / 16384.0, az / 16384.0, gx / 131.0, gy / 131.0, gz / 131.0)

    def ina_ma(self):
        """Corrente servo da tensione di shunt (reg 0x01, 10 uV/LSB, shunt 0.1 ohm): non serve calibrazione. None se non risponde."""
        try:
            r = self.bus.read_i2c_block_data(INA_ADDR, 0x01, 2)
            return struct.unpack(">h", bytes(r))[0] * 0.01 / 0.1
        except Exception:
            return None

    def enc(self):
        try:
            with open(self.enc_file) as f:
                c, tb = f.readline().split()[:2]
            c, tb = int(c), float(tb)
        except (OSError, ValueError):
            return None
        if tb == self._ult_enc_t:
            return None
        self._ult_enc_t = tb
        return (tb, c)

    def gps(self):
        try:
            with open(self.gps_json) as f:
                txt = f.read()
            j = json.loads(txt)
            ts = j.get("ts")
        except (OSError, ValueError, AttributeError):
            return None
        if ts == self._ult_gps_t:
            return None
        self._ult_gps_t = ts
        return parse_gps(txt)

    def ble(self):
        try:
            st = os.stat(self.ble_file)
            if st.st_mtime == self._ult_ble_m or time.time() - st.st_mtime > 3.0:
                return None
            self._ult_ble_m = st.st_mtime
            with open(self.ble_file) as f:
                return parse_ble(f.readline())
        except OSError:
            return None

    def campione(self, t):
        return Campione(t=t, enc=self.enc(), imu=self.imu(), gps=self.gps(), ble=self.ble(), ina_ma=self.ina_ma(),
                        emergenza=os.path.exists(self.emerg))


def main():
    ombra = "--ombra" in sys.argv
    try:
        cfg = carica_soglie()                       # validazione completa: se sbaglia si esce SENZA toccare il pin
    except SogliaError as e:
        print("[LIMITER] soglie non valide, non parto: %s" % e, flush=True)
        scrivi_stato(STATO_DEFAULT, {"t": time.time(), "stato": "NON_PARTITO", "errore": str(e)})
        return 2
    lock = None
    if ombra:
        servo = ServoOmbra()                        # ombra: il freno NON si tocca, niente lock su GPIO12
        print("[LIMITER] SHADOW MODE: calcolo e registro, il freno non viene comandato", flush=True)
    else:
        try:
            lock = acquisisci_lock()
        except LockError as e:
            print("[LIMITER] non parto: %s" % e, flush=True)
            scrivi_stato(STATO_DEFAULT, {"t": time.time(), "stato": "NON_PARTITO", "errore": str(e)})
            return 3
        servo = ServoLgpio()
    ctl = Controllo(cfg, servo, log_eventi=lambda t, da, a, m: print(f"[FONTE] {da} -> {a}: {m}", flush=True))
    if ombra:
        reg = RegistroOmbra()
        passo0 = ctl.passo
        ctl.passo = lambda c: (lambda r: (reg.scrivi(r), r)[1])(passo0(c))
    sens = LettoreSensori()
    run = [True]
    signal.signal(signal.SIGTERM, lambda *_: run.__setitem__(0, False))
    signal.signal(signal.SIGINT, lambda *_: run.__setitem__(0, False))
    codice = 1
    try:
        codice = esegui(ctl, sens, servo, run)
    finally:
        ctl.rampa.azzera()
        chiudi_servo(servo, cfg["freno"]["uscita_tieni_s"])      # 0 gradi tenuto >= 0.6 s, poi pin libero
        scrivi_stato(STATO_DEFAULT, {"t": time.time(), "stato": "FERMATO", "codice": codice})
        if lock is not None:
            lock.close()
        if ombra:
            reg.f.close()
    return codice


if __name__ == "__main__":
    sys.exit(main())

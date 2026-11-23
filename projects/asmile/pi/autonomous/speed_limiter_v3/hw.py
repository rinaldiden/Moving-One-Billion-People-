"""Hardware VERO (lgpio, smbus2, file di /tmp). L'UNICO file che importa lgpio. NON VERIFICATO: mai girato sul Pi
(vietato da Daniele per questa fase). Il loop e' unico: leggi -> Controllo.passo() -> (il servo e' comandato li' dentro)."""
import json
import os
import signal
import struct
import sys
import time

from .controllo import Controllo, carica_soglie
from .fonti import Campione
from .freno import SERVO_HZ, angle_to_duty

ENC_CUM_FILE = "/tmp/encoder_wheel_cum"        # "<count srotolati> <t_monotonic>" ~880 Hz dal bridge
BLE_FILE = "/tmp/bike_speed"
EMERGENCY_FLAG = "/tmp/emergency_brake"
GPS_JSON = "/tmp/gps_state.json"
GPIO_CHIP, SERVO_PIN = 0, 12
IMU_ADDR, INA_ADDR = 0x68, 0x40


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
            self.libera()
            self.lg.gpiochip_close(self.h)
        except Exception:
            pass


class LettoreSensori:
    def __init__(self):
        import smbus2
        self.bus = smbus2.SMBus(1)
        self.bus.write_byte_data(IMU_ADDR, 0x6B, 0x00)
        self._ult_enc_t = None
        self._ult_gps_t = None
        self._ult_ble_m = None

    def imu(self):
        try:
            b = self.bus.read_i2c_block_data(IMU_ADDR, 0x3B, 14)
        except OSError:
            return None
        ax, ay, az, _, gx, gy, gz = struct.unpack(">hhhhhhh", bytes(b))
        return (ax / 16384.0, ay / 16384.0, az / 16384.0, gx / 131.0, gy / 131.0, gz / 131.0)

    def ina_ma(self):
        try:
            r = self.bus.read_i2c_block_data(INA_ADDR, 0x04, 2)
            return struct.unpack(">h", bytes(r))[0] * 0.1
        except OSError:
            return None

    def enc(self):
        try:
            with open(ENC_CUM_FILE) as f:
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
            with open(GPS_JSON) as f:
                j = json.load(f)
        except (OSError, ValueError):
            return None
        if j.get("ts") == self._ult_gps_t:
            return None
        self._ult_gps_t = j.get("ts")
        return (float(j.get("speed_ms", 0.0)), bool(j.get("fix")))

    def ble(self):
        try:
            st = os.stat(BLE_FILE)
            if st.st_mtime == self._ult_ble_m or time.time() - st.st_mtime > 3.0:
                return None
            self._ult_ble_m = st.st_mtime
            with open(BLE_FILE) as f:
                return float(f.readline().split()[0])
        except (OSError, ValueError, IndexError):
            return None


def main():
    cfg = carica_soglie()
    servo = ServoLgpio()
    ctl = Controllo(cfg, servo, log_eventi=lambda t, da, a, m: print(f"[FONTE] {da} -> {a}: {m}", flush=True))
    sens = LettoreSensori()
    run = [True]
    signal.signal(signal.SIGTERM, lambda *_: run.__setitem__(0, False))
    signal.signal(signal.SIGINT, lambda *_: run.__setitem__(0, False))
    dt = 1.0 / 50
    prossimo = time.monotonic()
    try:
        while run[0]:
            t = time.monotonic()
            c = Campione(t=t, enc=sens.enc(), imu=sens.imu(), gps=sens.gps(), ble=sens.ble(), ina_ma=sens.ina_ma(),
                         emergenza=os.path.exists(EMERGENCY_FLAG))
            ctl.passo(c)          # il comando servo avviene QUI DENTRO, nello stesso ciclo
            prossimo += dt
            s = prossimo - time.monotonic()
            if s > 0:
                time.sleep(s)
            else:
                prossimo = time.monotonic()
    finally:
        ctl.rampa.azzera()
        try:
            servo.pwm(0.0)
            time.sleep(0.2)
        except Exception:
            pass
        servo.chiudi()


if __name__ == "__main__":
    main()

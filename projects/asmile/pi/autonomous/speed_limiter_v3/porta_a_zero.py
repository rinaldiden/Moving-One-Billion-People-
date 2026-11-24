"""ExecStopPost: dopo QUALSIASI fine del servizio (anche SIGKILL/OOM) manda il servo a 0 gradi, tiene >= 0.6 s, libera il pin.
Prende lo stesso flock di GPIO12 (aspetta fino a 3 s che il limiter lo lasci). NON VERIFICATO (mai girato sul Pi)."""
import sys
import time

from .lock_gpio12 import LockError, acquisisci_lock_attendi


def main():
    lock = None
    t0 = time.monotonic()
    while lock is None and time.monotonic() - t0 < 3.0:
        try:
            lock = acquisisci_lock()
        except LockError:
            time.sleep(0.1)
    if lock is None:
        print("[porta_a_zero] lock GPIO12 non ottenuto: non tocco il pin", flush=True)
        return 1
    servo = ServoLgpio()
    try:
        servo.pwm(0.0)
        time.sleep(1.5)   # 24/11: da 50 gradi 0,7 s non bastano (come tieni_zero_s)
    finally:
        servo.libera()
        servo.chiudi()
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

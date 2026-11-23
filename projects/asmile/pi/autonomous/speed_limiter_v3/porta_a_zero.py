"""ExecStopPost: dopo QUALSIASI fine del servizio (anche SIGKILL/OOM) manda il servo a 0 gradi, tiene >= 0.6 s, libera il pin.
Prende lo stesso flock di GPIO12 (aspetta fino a 3 s che il limiter lo lasci). NON VERIFICATO (mai girato sul Pi)."""
import sys
import time

from .hw import LockError, ServoLgpio, acquisisci_lock


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
        time.sleep(0.7)
    finally:
        servo.libera()
        servo.chiudi()
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

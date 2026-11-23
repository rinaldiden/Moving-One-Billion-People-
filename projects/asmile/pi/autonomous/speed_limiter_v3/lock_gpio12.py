"""UN solo padrone di GPIO12: flock esclusivo su /run/brake_gpio12.lock. Solo fcntl (niente hardware): lo usano v3 e master_switch."""
import fcntl
import time

LOCK_GPIO12 = "/run/brake_gpio12.lock"


class LockError(Exception):
    pass


def acquisisci_lock(path=LOCK_GPIO12):
    """Non bloccante: se il pin ha gia' un padrone -> LockError."""
    f = open(path, "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise LockError("GPIO12 ha gia' un padrone (lock %s occupato)" % path)
    return f


def acquisisci_lock_attendi(path=LOCK_GPIO12, timeout_s=3.0, sleep=time.sleep, now=time.monotonic):
    """Aspetta fino a timeout_s che il padrone lasci il pin; poi LockError (chi chiama NON deve toccare il pin)."""
    t0 = now()
    while True:
        try:
            return acquisisci_lock(path)
        except LockError:
            if now() - t0 >= timeout_s:
                raise
            sleep(0.05)

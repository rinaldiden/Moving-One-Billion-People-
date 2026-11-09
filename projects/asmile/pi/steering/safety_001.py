"""safety_001.py — controlli comuni per gli script VESC di #001 (UART libera, vai interattivo)."""
import os, subprocess, sys

SERVIZI = ["power_steering", "speed_limiter"]


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None


def uart_libera(uart):
    """Ritorna (True, '') se nessuno tiene la UART; altrimenti (False, motivo). Se non si puo' verificare = occupata."""
    r = _run(["fuser", uart])
    if r is None: return False, "fuser non eseguibile: non verificabile"
    mine = str(os.getpid())
    pids = [x for x in r.stdout.split() if x != mine]
    if pids: return False, f"{uart} tenuta da pid {pids}"
    for s in SERVIZI:
        r = _run(["systemctl", "is-active", s])
        if r is None: return False, f"systemctl is-active {s} non verificabile"
        if r.stdout.strip() in ("active", "activating", "reloading"): return False, f"servizio {s} attivo"
    r = _run(["pgrep", "-f", "power_steering"])
    if r is None: return False, "pgrep non eseguibile"
    pids = [x for x in r.stdout.split() if x != mine]
    if pids: return False, f"processo power_steering in esecuzione {pids}"
    return True, ""


def vai_interattivo(txt):
    """Il 'vai' deve essere scritto a mano da Daniele su un terminale vero. Niente flag, niente pipe."""
    if not sys.stdin.isatty():
        sys.exit("stdin non e' un terminale: il 'vai' va scritto a mano da Daniele, rifiuto")
    return input(f"\n>>> {txt}\n    scrivi 'vai' per procedere (altro = stop): ").strip().lower() == "vai"

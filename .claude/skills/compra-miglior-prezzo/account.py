#!/usr/bin/env python3
"""
account.py — gli account dei negozi del doppio: password nel Portachiavi del Mac, mai in chiaro.

Ogni sito ha una voce nel Portachiavi `claude-<sito>` (stessa convenzione di ~/progetti/ACCESSI.md).
Il registro dei siti (SENZA password) sta in ~/.config/doppio/account_negozi.json, fuori da git.
I dati di consegna (nome, indirizzo, carta per ultime 4 cifre) stanno in ~/.config/doppio/acquisti.json.

Uso:
  account.py nuovo robotics.it --utente daniele@movingonebillionpeople.org   # genera password forte + salva
  account.py salva amazon.it --utente <email>      # la password la digita Daniele (non passa in chat né nei log)
  account.py c'è amazon.it                          # sì/no, senza mostrarla
  account.py elenco                                 # siti registrati (niente password)
  account.py dati                                   # dati di consegna/fatturazione per registrazioni e ospite
  account.py imposta amazon.carta_ultime4 1234      # aggiorna un dato (chiave puntata)

Da Python (per compilare un form senza stampare nulla):
  from account import password, dati
  pg.fill("#password", password("robotics.it"))
"""
import getpass, json, os, secrets, string, subprocess, sys
from datetime import date

CONF = os.path.expanduser("~/.config/doppio")
REGISTRO = os.path.join(CONF, "account_negozi.json")
DATI = os.path.join(CONF, "acquisti.json")
UTENTE_DEFAULT = "daniele@movingonebillionpeople.org"

# Dati di consegna. Vengono SOLO da Daniele (voce 2026-11-14): Rinaldi Daniele, via San Carlo 25.
# CAP/città non detti: su Amazon il CAP impostato è 23037 Tirano, ma va confermato. Mai inventare.
DATI_DEFAULT = {
    "nome": "Daniele", "cognome": "Rinaldi",
    "email": UTENTE_DEFAULT,
    "spedizione": {"intestatario": "Rinaldi Daniele", "via": "via San Carlo 25",
                   "cap": None, "citta": None, "provincia": None, "nazione": "Italia",
                   "nota": "CAP/città da confermare con Daniele (CAP Amazon impostato: 23037 Tirano)"},
    "telefono": None,
    "amazon": {"indirizzo_cerca": ["san carlo 25", "rinaldi"],   # tutte devono esserci nel testo dell'indirizzo
               "carta_ultime4": None,                             # la dà Daniele: senza, il checkout si ferma
               "prime": None},
}


def _carica(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return json.loads(json.dumps(default))


def _scrivi(path, obj):
    os.makedirs(CONF, mode=0o700, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.chmod(path, 0o600)


def _servizio(sito):
    return f"claude-{sito.lower().removeprefix('www.')}"


def genera(n=20):
    """Password forte che i form accettano quasi sempre: lettere, cifre e un set di simboli 'sicuri'."""
    alfa = string.ascii_letters + string.digits + "-_.!@#"
    while True:
        p = "".join(secrets.choice(alfa) for _ in range(n))
        if (any(c.islower() for c in p) and any(c.isupper() for c in p)
                and any(c.isdigit() for c in p) and any(c in "-_.!@#" for c in p)):
            return p


def salva_keychain(sito, utente, pw):
    # -U aggiorna se esiste. La password passa come argomento a `security` (non in shell, non nei log).
    subprocess.run(["security", "add-generic-password", "-U", "-s", _servizio(sito), "-a", utente, "-w", pw],
                   check=True, capture_output=True)


def password(sito, utente=None):
    """Legge la password dal Portachiavi. None se non c'è. Non stamparla mai."""
    cmd = ["security", "find-generic-password", "-s", _servizio(sito), "-w"]
    if utente:
        cmd[3:3] = ["-a", utente]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def registra(sito, utente, modo, nota=""):
    reg = _carica(REGISTRO, {})
    reg[sito] = {"utente": utente, "portachiavi": _servizio(sito), "modo": modo,
                 "data": date.today().isoformat(), "nota": nota}
    _scrivi(REGISTRO, reg)


def dati():
    return _carica(DATI, DATI_DEFAULT)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    cmd = a[0]
    utente = a[a.index("--utente") + 1] if "--utente" in a else UTENTE_DEFAULT
    if cmd == "nuovo":
        sito = a[1]
        if password(sito):
            sys.exit(f"{sito}: c'è già una password nel Portachiavi ({_servizio(sito)}). Non la sovrascrivo.")
        salva_keychain(sito, utente, genera())
        registra(sito, utente, "creato dal doppio")
        print(f"ok: password generata e salvata nel Portachiavi come {_servizio(sito)} (utente {utente})")
    elif cmd == "salva":
        sito = a[1]
        pw = getpass.getpass(f"Password di {sito} per {utente} (non viene mostrata): ")
        if not pw:
            sys.exit("vuota: niente salvato")
        salva_keychain(sito, utente, pw)
        registra(sito, utente, "data da Daniele")
        print(f"ok: salvata nel Portachiavi come {_servizio(sito)}")
    elif cmd in ("c'è", "ce", "esiste"):
        print("sì" if password(a[1]) else "no")
    elif cmd == "elenco":
        for s, r in sorted(_carica(REGISTRO, {}).items()):
            print(f"{s:28} {r['utente']:40} {r['modo']:18} {r['data']}")
    elif cmd == "dati":
        d = dati()
        if not os.path.exists(DATI):
            _scrivi(DATI, d)
        print(json.dumps(d, ensure_ascii=False, indent=2))
    elif cmd == "imposta":
        chiave, valore = a[1], a[2]
        d = dati(); nodo = d
        *testa, coda = chiave.split(".")
        for k in testa:
            nodo = nodo.setdefault(k, {})
        nodo[coda] = None if valore.lower() in ("null", "none") else valore
        _scrivi(DATI, d)
        print(f"ok: {chiave} = {nodo[coda]}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

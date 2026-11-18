#!/usr/bin/env python3
"""Tabella pin hw ↔ fw (antipattern A6): per ogni GPIO dei due moduli confronta la net di HW4 con TUTTI gli usi nel
firmware HW3 (macro L02_PIN_*, numeri scritti nel codice: I2S, SD, PA, e i CONFIG_*PIN/GPIO di sdkconfig).
Uso: python3 controlla_pin_fw.py ../../../../logger02/firmware > ../PIN_HW4.md   (esce 1 se trova conflitti)
Conflitto = il firmware pilota (uscita/periferica) un GPIO che su HW4 ha una funzione diversa da quella di HW3.
"""
import os, re, sys
import netlist_hw4 as NL
from costruisci_lib import ws_pins

FW = sys.argv[1]
fw = {}          # gpio -> [(file:riga, testo)]
# macro usate da UN solo ruolo (prova nel codice): non contano sull'altro modulo
SOLO = {"L02_PIN_SYNC_B": "B",      # logger02_link.c:216-225, ramo else di `if (logger02_ruolo()->is_a)`
        "L02_PIN_SYNC_A": "A",      # logger02_link.c:210-214, ramo is_a
        "L02_PIN_IMU_INT": "A", "L02_PIN_BATT_ADC": "A"}   # logger02_main.c: logger02_imu_start() solo se ru->is_a


def add(g, dove, testo):
    fw.setdefault(int(g), []).append((dove, testo.strip()[:90]))


src = []
for d in ("main",):
    for f in sorted(os.listdir(os.path.join(FW, d))):
        if f.endswith((".c", ".h")):
            src.append(os.path.join(d, f))
macro = {}
for f in src:
    for m in re.finditer(r"#define\s+(L02_PIN_\w+)\s+(\d+)", open(os.path.join(FW, f)).read()):
        macro[m.group(1)] = int(m.group(2))
for f in src:
    for i, riga in enumerate(open(os.path.join(FW, f)), 1):
        for name, g in macro.items():
            if re.search(r"\b%s\b" % name, riga):
                add(g, "%s:%d" % (f, i), ("[solo %s] " % SOLO[name] if name in SOLO else "") + riga)
        # numeri di pin scritti a mano: .mclk = 13, slot.clk = 43, .pa_pin = 53 ...
        for m in re.finditer(r"\.(mclk|bclk|ws|dout|din|clk|cmd|d[0-7]|pa_pin|sda_io_num|scl_io_num|gpio_\w+)\s*=\s*(\d+)", riga):
            add(m.group(2), "%s:%d" % (f, i), riga)
for i, riga in enumerate(open(os.path.join(FW, "sdkconfig")), 1):
    m = re.match(r"(CONFIG_\w*(?:_PIN|_GPIO)\w*)=(\d+)$", riga.strip())
    if m and "RANGE" not in m.group(1) and not m.group(1).startswith("CONFIG_SOC"):
        add(m.group(2), "sdkconfig:%d" % i, riga)

PAD2GPIO = {n: int(name[4:]) for n, name in ws_pins() if name.startswith("GPIO")}
mod = {p["ref"]: p for p in NL.PARTS if p["sym"] == "WS_ESP32-P4-Module"}
hw = {"A": {}, "B": {}}
for ref, s in (("U10", "A"), ("U20", "B")):
    for pad, net in mod[ref]["pins"].items():
        if int(pad) in PAD2GPIO:
            hw[s][PAD2GPIO[int(pad)]] = net
# funzione di HW3 per ogni GPIO (dai fili e dalla dev-kit): se HW4 la conserva non è un conflitto
UGUALE = {3: "SYNC", 4: "IMU_INT", 5: "WAKE", 7: "I2C_SDA", 8: "I2C_SCL", 20: "BATT_ADC", 21: "SYNC",
          22: "UART", 23: "UART", 24: "USB_DM", 25: "USB_DP", 37: "U0TXD", 38: "U0RXD", 35: "BOOT",
          39: "SD_D0", 40: "SD_D1", 41: "SD_D2", 42: "SD_D3", 43: "SD_CLK", 44: "SD_CMD", 45: "SD_PWR"}
INTERNI = {14, 15, 16, 17, 18, 19, 54}   # SDIO e reset della C6, dentro il modulo


print("# Tabella pin HW4 ↔ firmware hw3-def (generata da kicad/controlla_pin_fw.py, non a mano)\n")
print("Conflitto = il firmware usa il GPIO e HW4 lo collega a una funzione diversa da HW3. Fonte firmware: `logger02/firmware` (main/*.c|h, sdkconfig).\n")
print("| GPIO | net A | net B | usi nel firmware (file:riga) | esito |")
print("|---|---|---|---|---|")
conflitti = 0
for g in range(0, 55):
    a, b = hw["A"].get(g, "—"), hw["B"].get(g, "—")
    usi = fw.get(g, [])
    if a == "—" and b == "—" and not usi:
        continue
    esito = "ok"
    if g in INTERNI:
        esito = "interno al modulo (C6)" if a == b == "—" else "CONFLITTO: pin interno usato"
    elif usi:
        stessa = g in UGUALE and all(n == "—" or UGUALE[g].split("_")[0] in n for n in (a, b))
        libero = a == "—" and b == "—"
        ruoli = {t[6] for _, t in usi if t.startswith("[solo ")}
        if ruoli and len(ruoli) == 1 and all(t.startswith("[solo ") for _, t in usi):
            r = ruoli.pop()
            altra = b if r == "A" else a
            propria = a if r == "A" else b
            ruolo_ok = propria == "—" or (g in UGUALE and UGUALE[g].split("_")[0] in propria)
        else:
            ruolo_ok = False
        if ruolo_ok and not stessa:
            esito = "ok: il firmware lo usa solo sul modulo %s (stessa funzione o pad libero); sull'altro è %s" % (r, altra)
        elif libero:
            esito = "ok: su HW4 il pad è libero (il firmware può pilotarlo senza danni)"
        elif stessa:
            esito = "ok: stessa funzione di HW3"
        else:
            esito = "**CONFLITTO**"
            conflitti += 1
    elif a != "—" or b != "—":
        esito = "ok: il firmware hw3-def non lo usa (funzione nuova HW4)"
    u = "<br>".join("%s `%s`" % (d, t.replace("|", "/")) for d, t in usi[:3]) or "—"
    print("| %d | %s | %s | %s | %s |" % (g, a, b, u, esito))
print("\n**Conflitti: %d**" % conflitti)
sys.exit(1 if conflitti else 0)

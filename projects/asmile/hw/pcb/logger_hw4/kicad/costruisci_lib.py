#!/usr/bin/env python3
"""Costruisce la libreria locale del progetto logger HW4 (lib/hw4.kicad_sym + lib/hw4.pretty).

Fonti (tutte primarie, nessun footprint disegnato "a occhio"):
  - simboli/footprint standard KiCad 10.0.8 (R, C, LED, header, test point, fori)
  - pezzi LCSC: easyeda2kicad (stesso disegno che usa JLCPCB per montare quel codice C…)
  - modulo Waveshare ESP32-P4-Module: footprint generato dal land pattern DXF ufficiale Waveshare
    (88 pad 1,5×0,7 mm, passo 1 mm, 25×25 mm) e simbolo generato dalla tabella pin del wiki Waveshare.

Uso: python3 costruisci_lib.py --kicad /tmp/kicad_dmg/KiCad/KiCad.app --easyeda /tmp/hw4work/eelib --wspads /tmp/hw4work/wspads.json
Il risultato (lib/) è committato: per aprire il progetto NON serve rilanciarlo.
"""
import argparse, json, os, re, shutil, subprocess

QUI = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(QUI, "lib")

STD_SYM = [("Device", "R"), ("Device", "C"), ("Device", "LED"),
           ("Connector_Generic", "Conn_01x04"), ("Connector_Generic", "Conn_01x06"),
           ("Connector_Generic", "Conn_01x08"), ("Connector", "TestPoint"),
           ("Mechanical", "MountingHole"), ("power", "PWR_FLAG")]
STD_FP = [("Resistor_SMD", "R_0402_1005Metric"), ("Capacitor_SMD", "C_0402_1005Metric"),
          ("Capacitor_SMD", "C_0603_1608Metric"), ("Capacitor_SMD", "C_0805_2012Metric"),
          ("LED_SMD", "LED_0603_1608Metric"),
          ("Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical"),
          ("Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical"),
          ("Connector_PinHeader_2.54mm", "PinHeader_1x08_P2.54mm_Vertical"),
          ("TestPoint", "TestPoint_Pad_D1.5mm"),
          ("MountingHole", "MountingHole_2.2mm_M2"), ("MountingHole", "MountingHole_2.7mm_M2.5")]

# Pinout del modulo (wiki Waveshare ESP32-P4-Module, 18/11/2026). Pin 1 = lato sinistro in alto, antiorario.
WS_PINS = """1 GND|2 LNA_OUT|3 GND|4 C6_U0RXD|5 C6_U0TXD|6 C6_IO15|7 C6_IO14|8 C6_IO13|9 C6_IO9|10 C6_IO8|11 C6_IO7|
12 C6_IO6|13 C6_IO5|14 C6_IO4|15 GND|16 GPIO1|17 GPIO2|18 GPIO3|19 GPIO4|20 GPIO5|21 GPIO6|22 GPIO7|23 GPIO8|
24 GPIO9|25 GPIO10|26 GPIO11|27 GPIO12|28 GPIO13|29 GPIO20|30 GPIO21|31 GPIO22|32 GPIO23|33 GND|34 DSI_DATAP1|
35 DSI_DATAN1|36 DSI_CLKN|37 DSI_CLKP|38 DSI_DATAP0|39 DSI_DATAN0|40 GND|41 CSI_DATAN0|42 CSI_DATAP0|43 CSI_CLKP|
44 CSI_CLKN|45 CSI_DATAN1|46 CSI_DATAP1|47 GND|48 USB_DM|49 USB_DP|50 GPIO24|51 GPIO25|52 GND|53 GPIO26|54 GPIO27|
55 GPIO28|56 GPIO29|57 GPIO30|58 GPIO31|59 GPIO32|60 GPIO33|61 GPIO34|62 GPIO35|63 GPIO36|64 GPIO37|65 GPIO38|
66 ESP_LDO_VO4|67 GPIO39|68 GPIO40|69 GPIO41|70 GPIO42|71 GPIO43|72 GPIO44|73 GPIO45|74 GPIO46|75 GPIO47|76 GPIO48|
77 GPIO49|78 GPIO50|79 GPIO51|80 GPIO52|81 GPIO53|82 GPIO54|83 GND|84 VBAT|85 ESP_3V3|86 ESP_3V3|87 ESP_EN|88 GPIO0"""


def ws_pins():
    out = []
    for tok in WS_PINS.replace("\n", "").split("|"):
        n, name = tok.strip().split(" ", 1)
        out.append((int(n), name))
    return out


def blocco(s, start):
    d = 0
    for j in range(start, len(s)):
        if s[j] == "(":
            d += 1
        elif s[j] == ")":
            d -= 1
            if d == 0:
                return s[start:j + 1]
    raise ValueError("parentesi")


def simbolo(libfile, name):
    s = open(libfile, encoding="utf-8").read()
    m = re.search(r'\(symbol "%s"' % re.escape(name), s)
    if not m:
        raise KeyError(name)
    return blocco(s, m.start())


def tipo_pin(name):
    if name == "GND":
        return "power_in"
    if name in ("ESP_3V3", "VBAT"):
        return "power_in"
    if name == "ESP_LDO_VO4":
        return "power_out"
    if name == "ESP_EN":
        return "input"
    return "bidirectional"


def simbolo_modulo():
    """Simbolo del modulo: pin 1-44 a sinistra, 45-88 a destra (dall'alto), passo 2,54 mm."""
    pins = ws_pins()
    righe = 44
    h = (righe + 1) * 2.54
    top = h / 2
    out = ['(symbol "WS_ESP32-P4-Module" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)',
           '(property "Reference" "U" (at 0 %.2f 0) (effects (font (size 1.27 1.27))))' % (top + 2.54),
           '(property "Value" "Waveshare ESP32-P4-Module" (at 0 %.2f 0) (effects (font (size 1.27 1.27))))' % (-top - 2.54),
           '(property "Footprint" "hw4:Waveshare_ESP32-P4-Module" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
           '(property "Datasheet" "https://www.waveshare.com/wiki/ESP32-P4-Module" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
           '(property "Description" "ESP32-P4 + PSRAM 32MB + flash 16MB + ESP32-C6 (wifi/BLE), 88 pad a castello passo 1 mm" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
           '(symbol "WS_ESP32-P4-Module_0_1" (rectangle (start -17.78 %.2f) (end 17.78 %.2f) (stroke (width 0.254) (type default)) (fill (type background))))' % (top, -top),
           '(symbol "WS_ESP32-P4-Module_1_1"']
    for n, name in pins:
        if n <= 44:
            x, y, a = -22.86, top - 2.54 * n, 0
        else:
            x, y, a = 22.86, top - 2.54 * (n - 44), 180
        hide = ""
        out.append('(pin %s line (at %.2f %.2f %d) (length 5.08)%s (name "%s" (effects (font (size 1.27 1.27)))) (number "%d" (effects (font (size 1.27 1.27)))))'
                   % (tipo_pin(name), x, y, a, hide, name, n))
    out.append("))")
    return "\n".join(out)


def footprint_modulo(wspads):
    """Footprint dal DXF Waveshare. DXF: Y verso l'alto; KiCad: Y verso il basso → y_kicad = -y_dxf."""
    pins = dict(ws_pins())
    pads = json.load(open(wspads))
    # numerazione: lato sinistro (x=-12.5) dall'alto in basso 1-22, sotto (y_k=+12.5) da sinistra 23-44,
    # destra (x=+12.5) dal basso in alto 45-66, sopra (y_k=-12.5) da destra 67-88
    num = {}
    for (x, y, w, h) in pads:
        yk = -y
        if abs(x + 12.5) < 0.01:
            n = 1 + round(yk + 10.5)
        elif abs(yk - 12.5) < 0.01:
            n = 23 + round(x + 10.5)
        elif abs(x - 12.5) < 0.01:
            n = 45 + round(10.5 - yk)
        elif abs(yk + 12.5) < 0.01:
            n = 67 + round(10.5 - x)
        else:
            raise ValueError((x, y))
        num[n] = (x, yk, w, h)
    assert sorted(num) == list(range(1, 89)), "numerazione pad incompleta"
    L = ['(footprint "Waveshare_ESP32-P4-Module" (version 20240108) (generator "costruisci_lib.py") (layer "F.Cu")',
         '(descr "Waveshare ESP32-P4-Module, 25x25 mm, 88 pad a castello passo 1 mm, dal land pattern DXF ufficiale Waveshare. PIN 1 DA VERIFICARE sul modulo vero.")',
         '(attr smd)',
         '(property "Reference" "REF**" (at 0 -14.5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
         '(property "Value" "Waveshare_ESP32-P4-Module" (at 0 14.5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))']
    for (a, b) in [((-12.5, -12.5), (12.5, -12.5)), ((12.5, -12.5), (12.5, 12.5)),
                   ((12.5, 12.5), (-12.5, 12.5)), ((-12.5, 12.5), (-12.5, -12.5))]:
        L.append('(fp_line (start %.2f %.2f) (end %.2f %.2f) (stroke (width 0.1) (type solid)) (layer "F.Fab"))' % (a + b))
        L.append('(fp_line (start %.2f %.2f) (end %.2f %.2f) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))'
                 % tuple(v * 13.5 / 12.5 for v in a + b))
    L.append('(fp_circle (center -13.97 -10.5) (end -13.82 -10.5) (stroke (width 0.3) (type solid)) (fill solid) (layer "F.SilkS"))')
    L.append('(fp_text user "1" (at -14.6 -11.6 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    # zona sotto il modulo: niente rame sul top (il modulo ha pad e vie sul fondo)
    L.append('(zone (net 0) (net_name "") (layers "F.Cu") (hatch edge 0.5) (connect_pads (clearance 0)) (min_thickness 0.25) '
             '(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) '
             '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) (polygon (pts (xy -10.9 -10.9) (xy 10.9 -10.9) (xy 10.9 10.9) (xy -10.9 10.9))))')
    for n in range(1, 89):
        x, y, w, h = num[n]
        L.append('(pad "%d" smd rect (at %.3f %.3f) (size %.2f %.2f) (layers "F.Cu" "F.Paste" "F.Mask"))' % (n, x, y, w, h))
    L.append(")")
    return "\n".join(L), num, pins


IC_EASYEDA = ("TP4056", "DW01A", "TLV62569", "LSM6DS3", "USBLC6")


def tipi_pin_easyeda(b):
    """easyeda2kicad mette tutti i pin 'unspecified' (ERC pieno di avvisi finti). Regola: pin di alimentazione degli
    IC = power_in (così l'ERC controlla che la rail sia pilotata), tutto il resto passive (connettori, discreti, I/O)."""
    nome = re.search(r'\(symbol "([^"]+)"', b).group(1)
    ic = any(k in nome for k in IC_EASYEDA)

    def tipo(m):
        pb = m.group(0)
        pname = re.search(r'\(name "([^"]*)"', pb).group(1).upper()
        t = "passive"
        if ic and re.fullmatch(r"(GND|VSS|EP|VCC|VDD|VDDIO|VIN|VBUS)", pname):
            t = "power_in"
        return pb.replace("(pin unspecified", "(pin " + t, 1)
    return re.sub(r'\(pin unspecified .*?\(number "[^"]*"[^)]*\)\s*\)', tipo, b, flags=re.S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kicad", required=True)
    ap.add_argument("--easyeda", required=True)
    ap.add_argument("--wspads", required=True)
    a = ap.parse_args()
    shared = os.path.join(a.kicad, "Contents/SharedSupport")
    cli = os.path.join(a.kicad, "Contents/MacOS/kicad-cli")
    os.makedirs(os.path.join(LIB, "hw4.pretty"), exist_ok=True)

    # --- simboli: standard (formato 10) + easyeda (formato vecchio, ripulito) + modulo
    blocchi = []
    for lib, name in STD_SYM:
        blocchi.append(simbolo(os.path.join(shared, "symbols", lib + ".kicad_sym"), name))
    ee = open(os.path.join(a.easyeda, "lcsc.kicad_sym"), encoding="utf-8").read()
    for m in re.finditer(r'\n  \(symbol "([^"]+)"', ee):
        b = blocco(ee, m.start() + 3)
        b = re.sub(r'\(id \d+\)', '', b)
        b = re.sub(r'\)\s*hide\)', ') (hide yes))', b)
        b = b.replace('"lcsc:', '"hw4:')
        blocchi.append(tipi_pin_easyeda(b))
    blocchi.append(simbolo_modulo())
    tmp = os.path.join(LIB, "_hw4_tmp.kicad_sym")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write('(kicad_symbol_lib (version 20231120) (generator "costruisci_lib.py")\n')
        f.write("\n".join(blocchi))
        f.write("\n)\n")
    dst = os.path.join(LIB, "hw4.kicad_sym")
    if os.path.exists(dst):
        os.remove(dst)
    subprocess.run([cli, "sym", "upgrade", "--force", tmp, "-o", dst], check=True)
    os.remove(tmp)

    # --- footprint
    fpdir = os.path.join(LIB, "hw4.pretty")
    for lib, name in STD_FP:
        shutil.copy(os.path.join(shared, "footprints", lib + ".pretty", name + ".kicad_mod"), fpdir)
    for f in os.listdir(os.path.join(a.easyeda, "lcsc.pretty")):
        t = open(os.path.join(a.easyeda, "lcsc.pretty", f), encoding="utf-8").read()
        # modello 3D: il blocco (model ...) punta a /tmp e gli .step pesano 40 MB → tolto (render non serve qui)
        m = re.search(r'\(model "', t)
        if m:
            t = t.replace(blocco(t, m.start()), "")
        open(os.path.join(fpdir, f), "w", encoding="utf-8").write(t)
    fp, num, pins = footprint_modulo(a.wspads)
    open(os.path.join(fpdir, "Waveshare_ESP32-P4-Module.kicad_mod"), "w").write(fp)
    subprocess.run([cli, "fp", "upgrade", "--force", fpdir, "-o", fpdir + "_up"], check=True)
    shutil.rmtree(fpdir)
    os.rename(fpdir + "_up", fpdir)
    print("ok:", dst, len(os.listdir(fpdir)), "footprint")


if __name__ == "__main__":
    main()

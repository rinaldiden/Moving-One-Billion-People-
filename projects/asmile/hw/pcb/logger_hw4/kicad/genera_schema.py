#!/usr/bin/env python3
"""Genera logger_hw4.kicad_sch (+ .kicad_pro, sym/fp-lib-table) da netlist_hw4.py.

Stile: ogni pin ha un moncherino di filo e un'etichetta col nome della net (niente fili lunghi: lo schema si legge per
nome, come la net-list per piedino che piace a Daniele). Pin non usati → croce "non connesso".
Simboli incorporati da lib/hw4.kicad_sym (costruita da costruisci_lib.py). Ri-generare SOVRASCRIVE lo schema:
le modifiche si fanno in netlist_hw4.py, mai a mano nel .kicad_sch (antipattern A1).
"""
import json, os, re, uuid
import netlist_hw4 as NL

QUI = os.path.dirname(os.path.abspath(__file__))
NOME = "logger_hw4"
NS = uuid.UUID("6f1f3c52-0c1e-4d0e-9a51-48a3c0d0b404")      # uuid deterministici: diff puliti fra una generazione e l'altra


def U(*k):
    return str(uuid.uuid5(NS, "/".join(map(str, k))))


ROOT = U("root")


def blocco(s, start):
    d = 0
    for j in range(start, len(s)):
        if s[j] == "(":
            d += 1
        elif s[j] == ")":
            d -= 1
            if d == 0:
                return s[start:j + 1]
    raise ValueError


LIBTXT = open(os.path.join(QUI, "lib", "hw4.kicad_sym"), encoding="utf-8").read()


def sym_def(name):
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(name), LIBTXT)
    b = blocco(LIBTXT, m.start() + 2)
    return b


def pins_of(name):
    """numero → (x, y, angolo) nel sistema del simbolo (Y in su)."""
    b = sym_def(name)
    out = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', b):
        pb = blocco(b, m.start())
        num = re.search(r'\(number "([^"]*)"', pb).group(1)
        out[num] = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    return out


def bbox(name):
    b = sym_def(name)
    xs, ys = [0.0], [0.0]
    for m in re.finditer(r'\((?:start|end|at|xy|center) ([-\d.]+) ([-\d.]+)', b):
        xs.append(float(m.group(1)))
        ys.append(float(m.group(2)))
    return min(xs), max(xs), min(ys), max(ys)


def fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


def main():
    parts = NL.PARTS
    usati = sorted({p["sym"] for p in parts} | {"PWR_FLAG"})
    lib_syms = []
    for n in usati:
        b = sym_def(n).replace('(symbol "%s"' % n, '(symbol "hw4:%s"' % n, 1)
        lib_syms.append(b)

    out = []
    # disposizione: per blocco, in colonne; ogni simbolo occupa la sua scatola + spazio per le etichette
    blocchi = []
    for p in parts:
        if p["blocco"] not in blocchi:
            blocchi.append(p["blocco"])
    x0, y0 = 30.0, 40.0
    x, y, riga_h = x0, y0, 0.0
    LARGH = 1150.0
    testi = []
    for bl in blocchi:
        membri = [p for p in parts if p["blocco"] == bl]
        if x > x0:
            x, y = x0, y + riga_h + 25
            riga_h = 0
        testi.append((bl.upper(), x, y - 12))
        for p in membri:
            xmin, xmax, ymin, ymax = bbox(p["sym"])
            w = (xmax - xmin) + 2 * 38
            h = (ymax - ymin) + 20
            if x + w > LARGH:
                x, y = x0, y + riga_h + 10
                riga_h = 0
            sx = round((x + 38 - xmin) / 1.27) * 1.27
            sy = round((y + ymax + 8) / 1.27) * 1.27
            p["_at"] = (sx, sy)
            x += w
            riga_h = max(riga_h, h)
    # PWR_FLAG in fondo
    y += riga_h + 30
    flags = []
    for i, net in enumerate(NL.PWR_FLAGS):
        fx = round((x0 + 30 + i * 45) / 1.27) * 1.27
        fy = round(y / 1.27) * 1.27
        flags.append(dict(ref="#FLG%02d" % (i + 1), sym="PWR_FLAG", value="PWR_FLAG", fp="", lcsc="", dnp=False,
                          pins={"1": net}, blocco="flag", nota="", _at=(fx, fy)))
    alt_foglio = y + 40

    for p in parts + flags:
        sx, sy = p["_at"]
        pins = pins_of(p["sym"])
        uid = U("sym", p["ref"])
        prop = []
        fp = ("hw4:" + p["fp"]) if p["fp"] else ""
        hidden_ref = p["ref"].startswith("#")
        props = [("Reference", p["ref"], 0, -4, hidden_ref), ("Value", p["value"], 0, 4, False),
                 ("Footprint", fp, 0, 0, True), ("Datasheet", "", 0, 0, True), ("LCSC", p.get("lcsc", ""), 0, 0, True)]
        if p.get("nota"):
            props.append(("Nota", p["nota"], 0, 0, True))
        xmin, xmax, ymin, ymax = bbox(p["sym"])
        for k, v, dx, dy, hid in props:
            py = sy - ymax - 2.54 if k == "Reference" else (sy - ymin + 2.54 if k == "Value" else sy)
            prop.append('(property "%s" "%s" (at %s %s 0) (effects (font (size 1.27 1.27))%s))'
                        % (k, v.replace('"', "'"), fmt(sx), fmt(py), " (hide yes)" if hid else ""))
        pinlines = " ".join('(pin "%s" (uuid "%s"))' % (n, U("pin", p["ref"], n)) for n in pins)
        out.append('(symbol (lib_id "hw4:%s") (at %s %s 0) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board %s) '
                   '(dnp %s) (uuid "%s") %s %s (instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))'
                   % (p["sym"], fmt(sx), fmt(sy), "no" if hidden_ref else "yes", "no" if hidden_ref else "yes",
                      "yes" if p["dnp"] else "no", uid, " ".join(prop), pinlines, NOME, ROOT, p["ref"]))
        for num, (px, py, ang) in pins.items():
            ax, ay = sx + px, sy - py                       # punto di connessione nel foglio (Y in giù)
            import math
            dx, dy = -math.cos(math.radians(ang)), math.sin(math.radians(ang))   # verso fuori dal corpo
            dx, dy = round(dx), round(dy)
            net = p["pins"].get(num)
            if net is None:
                out.append('(no_connect (at %s %s) (uuid "%s"))' % (fmt(ax), fmt(ay), U("nc", p["ref"], num)))
                continue
            bx, by = ax + dx * 2.54, ay + dy * 2.54
            out.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))'
                       % (fmt(ax), fmt(ay), fmt(bx), fmt(by), U("w", p["ref"], num)))
            angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
            just = "left" if angle in (0, 90) else "right"
            out.append('(label "%s" (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid "%s"))'
                       % (net, fmt(bx), fmt(by), angle, just, U("l", p["ref"], num)))
    for t, tx, ty in testi:
        out.append('(text "%s" (exclude_from_sim no) (at %s %s 0) (effects (font (size 3 3) (thickness 0.6) (bold yes)) (justify left bottom)) (uuid "%s"))'
                   % (t, fmt(tx), fmt(ty), U("t", t)))
    note = ("LOGGER HW4 — schema generato da netlist_hw4.py (genera_schema.py). NON modificare a mano: si rigenera. "
            "Stessi GPIO di HW3 = firmware hw3-def invariato. Vedi DESIGN.md.")
    out.append('(text "%s" (exclude_from_sim no) (at 30 22 0) (effects (font (size 2.5 2.5)) (justify left bottom)) (uuid "%s"))'
               % (note, U("nota")))

    w_mm = 1189 if alt_foglio <= 841 else 1189
    sch = ['(kicad_sch (version 20250114) (generator "genera_schema.py") (generator_version "10.0") (uuid "%s")' % ROOT,
           '(paper "User" %d %d)' % (1200, max(841, int(alt_foglio) + 20)),
           '(title_block (title "Logger HW4 — scheda dedicata (2 x ESP32-P4-Module)") (date "2026-11-18") (rev "0.1") '
           '(company "Asmile — Moving One Billion People") (comment 1 "asmile-hw-pcb (STAGNO)"))',
           "(lib_symbols", "\n".join(lib_syms), ")", "\n".join(out),
           '(sheet_instances (path "/" (page "1")))', "(embedded_fonts no))"]
    open(os.path.join(QUI, NOME + ".kicad_sch"), "w", encoding="utf-8").write("\n".join(sch) + "\n")

    open(os.path.join(QUI, "sym-lib-table"), "w").write(
        '(sym_lib_table (version 7)\n  (lib (name "hw4")(type "KiCad")(uri "${KIPRJMOD}/lib/hw4.kicad_sym")(options "")(descr "logger HW4"))\n)\n')
    open(os.path.join(QUI, "fp-lib-table"), "w").write(
        '(fp_lib_table (version 7)\n  (lib (name "hw4")(type "KiCad")(uri "${KIPRJMOD}/lib/hw4.pretty")(options "")(descr "logger HW4"))\n)\n')
    pro = os.path.join(QUI, NOME + ".kicad_pro")
    if not os.path.exists(pro):
        json.dump({"meta": {"filename": NOME + ".kicad_pro", "version": 3}, "schematic": {}, "board": {},
                   "sheets": [[ROOT, "Root"]]}, open(pro, "w"), indent=2)
    # netlist "piatta" per il PCB (letta da genera_pcb.py col Python di KiCad)
    json.dump([{k: v for k, v in p.items() if not k.startswith("_")} | {"uuid": U("sym", p["ref"])} for p in parts],
              open(os.path.join(QUI, "netlist_hw4.json"), "w"), indent=1, ensure_ascii=False)
    print("schema:", len(parts), "parti,", len({n for p in parts for n in p["pins"].values()}), "net")


if __name__ == "__main__":
    main()

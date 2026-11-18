"""Netlist del logger HW4 — UNICA fonte di verità (schema e PCB si generano da qui, mai a mano).

Regola: stessi GPIO di HW3 (projects/asmile/logger02/firmware/main/logger02.h) → firmware hw3-def invariato.
Ogni parte: ref, simbolo (lib hw4), valore, footprint (lib hw4), LCSC, dnp, {numero pin: net}.
I pin non elencati diventano "non connesso" (X nello schema). Nomi net parlanti, suffisso _A / _B per modulo.
"""

R0805_NTC = "R0805"
R0402, C0402, C0603, C0805, LED0603 = ("R_0402_1005Metric", "C_0402_1005Metric", "C_0603_1608Metric",
                                       "C_0805_2012Metric", "LED_0603_1608Metric")
PARTS = []


def P(ref, sym, val, fp, lcsc, pins, dnp=False, blocco="", nota=""):
    PARTS.append(dict(ref=ref, sym=sym, value=val, fp=fp, lcsc=lcsc, pins=pins, dnp=dnp, blocco=blocco, nota=nota))


def R(ref, val, a, b, lcsc, dnp=False, blocco="", nota=""):
    P(ref, "R", val, R0402, lcsc, {"1": a, "2": b}, dnp, blocco, nota)


def C(ref, val, a, b="GND", fp=C0402, lcsc="C1525", blocco="", dnp=False, nota=""):
    P(ref, "C", val, fp, lcsc, {"1": a, "2": b}, dnp=dnp, blocco=blocco, nota=nota)


RES = {"0": "C17168", "22": "C25092", "33": "C25105", "100": "C25076", "1k": "C11702", "1.2k": "C25862",
       "2.2k": "C25879", "4.7k": "C25900", "5.1k": "C25905", "10k": "C25744", "22k": "C25768", "33k": "C25779",
       "100k": "C25741"}


# ---------------------------------------------------------------- alimentazione
B = "alimentazione"
P("J1", "TYPE-C-31-M-12", "USB-C (carica + flash A)", "USB-C_SMD-TYPE-C-31-M-12_1", "C165948",
  {"A1B12": "GND", "B1A12": "GND", "A4B9": "VBUS_C", "B4A9": "VBUS_C", "A5": "CC1", "B5": "CC2",
   "A6": "USB_DP_C", "B6": "USB_DP_C", "A7": "USB_DM_C", "B7": "USB_DM_C",
   "1": "GND", "2": "GND", "3": "GND", "4": "GND"}, blocco=B)
R("R1", "5.1k", "CC1", "GND", RES["5.1k"], blocco=B, nota="CC pull-down: sink 5 V/USB default")
R("R2", "5.1k", "CC2", "GND", RES["5.1k"], blocco=B)
P("U1", "USBLC6-2SC6_C2827654", "USBLC6-2SC6", "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL", "C2827654",
  {"1": "USB_DM_C", "6": "USB_DM_C", "3": "USB_DP_C", "4": "USB_DP_C", "2": "GND", "5": "VBUS_RAW"}, blocco=B)
# VBUS: J1 → R36 (serie, 0 Ω montato; posto per PTC o perla) → TVS → OVP AW32901 (5,83-6,07 V, 50 ns, 120 V surge,
# datasheet Awinic V1.0 pag. 4 e 7) → VBUS interna. Proteggono TP4056 (VCC max 6,5 V) e TLV62569 (VIN max 6 V via D5).
P("R36", "R", "0 (PTC/perla)", "R_0805_2012Metric", "C17477", {"1": "VBUS_C", "2": "VBUS_RAW"}, blocco=B,
  nota="serie su VBUS dopo J1: 0 Ω montato; 0805 e non 0603 perché passa fino a 2 A (carica 1 A + scheda) e lo 0 Ω 0603 è da 1 A")
P("U7", "AW32901FCR", "AW32901 OVP 5,95 V", "BGA-12_L1.8-W1.3-R3-C4-P0.40-TL", "C407920",
  {"B3": "VBUS_RAW", "C2": "VBUS_RAW", "C3": "VBUS_RAW", "A2": "VBUS", "A3": "VBUS", "B2": "VBUS",
   "A1": "GND", "C1": "GND", "A4": "GND", "B4": "GND", "C4": "GND"}, blocco=B,
  nota="EN attivo basso a GND, OVLO a GND = soglia di default 5,95 V; ACOK non usato (datasheet: può restare libero)")
C("C36", "100n 50V", "VBUS_RAW", fp=C0603, lcsc="C14663", blocco=B)
C("C37", "1u", "VBUS", fp=C0603, lcsc="C1592", blocco=B)
R("R3", "22", "USB_DM_C", "USB_DM_A", RES["22"], blocco=B, nota="serie FS USB (checklist P4 §USB)")
R("R4", "22", "USB_DP_C", "USB_DP_A", RES["22"], blocco=B)
C("C1", "10u", "VBUS", fp=C0805, lcsc="C15850", blocco=B)
# caricatore TP4056 1 A
P("U2", "TP4056_C725790", "TP4056", "ESOP-8_L4.9-W3.9-P1.27-LS6.0-BL-EP", "C725790",
  {"1": "TEMP", "2": "PROG", "3": "GND", "4": "VBUS", "5": "BATP", "7": "CHRG_N", "8": "VBUS",
   "9": "GND"}, blocco=B)
R("R5", "1.2k", "PROG", "GND", RES["1.2k"], blocco=B, nota="R_PROG 1,2 kΩ = 1000 mA (tabella TP4056)")
R("R6", "10k", "CHRG_N", "3V3_A", RES["10k"], blocco=B)
# NTC: TEMP carica solo fra 45 % e 80 % di VCC (datasheet TP4056). 6,8k da VBUS + NTC 10k B3950 a GND
# → carica permessa fra ~3 °C e ~42 °C. NTC sulla scheda vicino a J2; piano B: NTC del pacco su J2 pin 2.
R("R7", "6.8k", "VBUS", "TEMP", "C25917", blocco=B, nota="TEMP alto: 6,8k → finestra ~3-42 °C con NTC 10k B3950")
P("RT1", "CMFB103F3950FANT", "NTC 10k B3950", "R0805", "C51597", {"1": "TEMP_NTC", "2": "GND"}, blocco=B,
  nota="NTC sulla scheda accanto al portabatteria (temperatura cella/case)")
R("R33", "0", "TEMP", "TEMP_NTC", RES["0"], blocco=B, nota="montata: NTC sulla scheda")
R("R34", "0", "TEMP", "NTC_EXT", RES["0"], dnp=True, blocco=B, nota="piano B: NTC del pacco su J2 pin 2 (togliere R33)")
# TVS su VBUS (oltre all'USBLC6): SMF5.0A 200 W
P("D6", "SMF5.0A_C193402", "SMF5.0A", "SOD-123FL_L2.7-W1.8-LS3.8-RD", "C193402", {"1": "VBUS_RAW", "2": "GND"}, blocco=B,
  nota="TVS 5 V su VBUS: picchi da caricatori/cavi lunghi")
C("C2", "10u", "BATP", fp=C0805, lcsc="C15850", blocco=B)
P("J2", "S3B-PH-SM4-TB", "BATT 1S 3 poli (+, NTC, -)", "CONN-SMD_S3B-PH-SM4-TB-LF-SN", "C265101",
  {"1": "BATP", "2": "NTC_EXT", "3": "BAT_N"}, blocco=B,
  nota="3 poli: NON si inserisce nel J3 (2 poli). JST originale (stock 21k)")
# protezione cella DW01A + FS8205A (schema tipico datasheet DW01A)
P("U3", "DW01A_C351410", "DW01A", "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BR", "C351410",
  {"1": "PROT_OD", "2": "PROT_VM", "3": "PROT_OC", "5": "PROT_VCC", "6": "BAT_N"}, blocco=B)
R("R8", "100", "BATP", "PROT_VCC", RES["100"], blocco=B)
C("C3", "100n", "PROT_VCC", "BAT_N", blocco=B)
R("R9", "1k", "PROT_VM", "GND", RES["1k"], blocco=B, nota="VM verso P- (= GND della scheda)")
P("Q1", "FS8205A_C2830320", "FS8205A", "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL", "C2830320",
  {"1": "BAT_N", "2": "PROT_D", "5": "PROT_D", "3": "GND", "6": "PROT_OD", "4": "PROT_OC"}, blocco=B)
# interruttore esterno (quello di HW3) sul cavo: JST 2 pin, BATP → VSYS
# power-path (carico e carica separati): con USB la scheda va da VBUS via D5, la cella si carica da sola e il TP4056
# termina davvero a C/10; senza USB Q3 (P-MOS) conduce dalla cella. Interruttore DOPO l'OR: spento = spento anche in carica.
P("Q3", "AO3401A", "AO3401A", "SOT-23-3_L3.0-W1.7-P0.95-LS2.9-BR", "C15127",
  {"1": "GATE_Q3", "3": "BATP", "2": "VSYS_IN"}, blocco=B, nota="power-path: G da VBUS via D8, D=cella, S=VSYS_IN")
# gate di Q3 alimentato da VBUS attraverso D8: allo stacco USB il gate non vede i 10 µF di VBUS e si scarica su R35
# in ~7 µs (Ciss 645 pF) → Q3 prende il carico prima che VSYS cada sul diodo di body (modello_power_path.py)
P("D8", "SS14", "SS14", "SMA_L4.2-W2.6-LS5.0-RD_1", "C2480", {"2": "VBUS", "1": "GATE_Q3"}, blocco=B,
  nota="isola il gate di Q3 dalla capacità di VBUS (stesso pezzo di D5)")
R("R35", "10k", "GATE_Q3", "GND", RES["10k"], blocco=B, nota="scarica il gate di Q3: τ = 10k × ~0,7 nF ≈ 7 µs")
P("D5", "SS14", "SS14", "SMA_L4.2-W2.6-LS5.0-RD_1", "C2480", {"2": "VBUS", "1": "VSYS_IN"}, blocco=B,
  nota="power-path: VBUS → VSYS_IN (0,55 V a 1 A)")
P("J3", "PH-2AWT", "INTERRUTTORE est. (2 poli)", "CONN-SMD_PH-2AWT", "C2763693",
  {"1": "VSYS_IN", "2": "VSYS", "3": "GND", "4": "GND"}, blocco=B,
  nota="2 poli ≠ J2 (3 poli): non invertibili. Senza interruttore: ponticello sul connettore")
# partitore batteria (HW3: 100k/33k su GPIO20)
R("R10", "100k", "BATP", "BATT_ADC", RES["100k"], blocco=B, nota="100k/33k come HW3: la sequenza di leggi_batteria() (pull-down 2 ms + 2 ms) è tarata su questa impedenza (modello_partitore.py)")
R("R11", "33k", "BATT_ADC", "GND", RES["33k"], blocco=B)
C("C4", "100n", "BATT_ADC", blocco=B, dnp=True, nota="NON montare con il firmware hw3-def: con 100 nF la lettura sbaglia (VETO 2, A11)")
R("R12", "68k", "VBUS", "VBUS_SENSE", "C36871", blocco=B, nota="5 V → 2,98 V: leggibile come ADC e come livello alto (VIH 0,75×3,3 = 2,48 V)")
R("R13", "100k", "VBUS_SENSE", "GND", RES["100k"], blocco=B)
# due buck TLV62569 (uno per modulo), 3,3 V: Vout = 0,6 × (1 + 100k/22k) = 3,33 V
for s, en in (("A", "VSYS"), ("B", "EN_BUCK_B")):
    n = 4 if s == "A" else 5
    P("U%d" % n, "TLV62569DBVR", "TLV62569DBVR", "SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR", "C141836",
      {"1": en, "2": "GND", "3": "SW_" + s, "4": "VSYS", "5": "FB_" + s}, blocco=B)
    P("L%d" % (n - 3), "MWSA0402S-2R2MT", "2.2u 4.5A", "IND-SMD_L4.4-W4.2", "C408335",
      {"1": "SW_" + s, "2": "3V3_" + s}, blocco=B)
    R("R%d" % (10 + 2 * n), "100k", "3V3_" + s, "FB_" + s, RES["100k"], blocco=B)
    R("R%d" % (11 + 2 * n), "22k", "FB_" + s, "GND", RES["22k"], blocco=B)
    ca, cb, cc = (5, 6, 7) if s == "A" else (8, 9, 13)
    C("C%d" % ca, "10u", "VSYS", fp=C0805, lcsc="C15850", blocco=B)
    C("C%d" % cb, "22u", "3V3_" + s, fp=C0805, lcsc="C45783", blocco=B)
    C("C%d" % cc, "22u", "3V3_" + s, fp=C0805, lcsc="C45783", blocco=B)
# EN del buck B: di serie da VSYS (B sempre accesa come HW3); piano B: da A GPIO6 (spegne B a zero consumo)
R("R30", "0", "VSYS", "EN_BUCK_B", RES["0"], blocco=B, nota="montata: B accesa con A")
R("R31", "0", "B_PWR_EN", "EN_BUCK_B", RES["0"], dnp=True, blocco=B, nota="piano B: A comanda l'alimentazione di B")
R("R32", "100k", "EN_BUCK_B", "GND", RES["100k"], blocco=B)

# ---------------------------------------------------------------- moduli P4
COMUNE = {"1": "GND", "3": "GND", "15": "GND", "33": "GND", "40": "GND", "47": "GND", "52": "GND", "83": "GND"}


def modulo(ref, s):
    p = dict(COMUNE)
    p.update({"84": "3V3_" + s, "85": "3V3_" + s, "86": "3V3_" + s, "87": "EN_" + s, "62": "BOOT_" + s,
              "2": "ANT_" + s, "4": "C6_RXD_" + s, "5": "C6_TXD_" + s, "9": "C6_BOOT_" + s,
              "22": "I2C_SDA_" + s, "23": "I2C_SCL_" + s, "26": "CAM_EN_" + s,
              "41": "CSI_D0N_" + s, "42": "CSI_D0P_" + s, "43": "CSI_CKP_" + s, "44": "CSI_CKN_" + s,
              "45": "CSI_D1N_" + s, "46": "CSI_D1P_" + s,
              "64": "U0TXD_" + s, "65": "U0RXD_" + s, "66": "VDD_SDIO_" + s,
              "67": "SD_D0_" + s, "68": "SD_D1_" + s, "69": "SD_D2_" + s, "70": "SD_D3_" + s,
              "71": "SD_CLK_M_" + s, "72": "SD_CMD_" + s, "73": "SD_PWR_N_" + s,
              "55": "SPI_SCLK_" + s, "56": "SPI_MOSI_" + s, "57": "SPI_MISO_" + s, "58": "SPI_CS_" + s,
              "59": "SPI_HS_" + s})
    if s == "A":
        p.update({"17": "TRIG_M", "18": "SYNC_M", "19": "IMU_INT", "20": "WAKE_M", "21": "B_PWR_EN",
                  "78": "LED_R", "80": "LED_G", "29": "BATT_ADC", "30": "VBUS_SENSE",
                  "31": "UART_AB", "32": "UART_BA", "50": "USB_DM_A", "51": "USB_DP_A", "53": "CHRG_N",
                  "60": "B_EN_CTL", "77": "B_BOOT_CTL", "54": "BUZZER",
                  "16": "EXP_IO1", "75": "EXP_IO47", "76": "EXP_IO48"})
    else:
        p.update({"30": "SYNC_B", "20": "WAKE_B", "31": "UART_BA_B", "32": "UART_AB_B",
                  "78": "LED_B", "50": "USB_DM_B", "51": "USB_DP_B"})
    P(ref, "WS_ESP32-P4-Module", "Waveshare ESP32-P4-Module (IPEX)", "Waveshare_ESP32-P4-Module", "",
      p, blocco="modulo " + s, nota="fornito a parte (non in libreria JLC); versione con connettore IPEX")


modulo("U10", "A")
modulo("U20", "B")
for s, n in (("A", 10), ("B", 20)):
    b = "modulo " + s
    r0 = 40 if s == "A" else 43
    C("C%d" % n, "22u", "3V3_" + s, fp=C0805, lcsc="C45783", blocco=b)
    C("C%d" % (n + 1), "100n", "3V3_" + s, blocco=b)
    C("C%d" % (n + 2), "1u", "EN_" + s, fp=C0603, lcsc="C1592", blocco=b)
    R("R%d" % r0, "10k", "3V3_" + s, "EN_" + s, RES["10k"], blocco=b, nota="CHIP_PU RC 10k/1u (checklist P4 §Reset)")
    R("R%d" % (r0 + 1), "10k", "3V3_" + s, "BOOT_" + s, RES["10k"], blocco=b, nota="GPIO35 pull-up (strapping)")
    # antenna: versione IPEX del modulo → niente; piano B u.FL sulla scheda (non montato)
    R("R%d" % (r0 + 2), "0", "ANT_" + s, "ANT_UFL_" + s, RES["0"], dnp=True, blocco=b)
    P("J%d" % (n + 1), "U.FL-R-SMT-1", "u.FL (piano B)", "RF-SMD_FRF05002-JSS103M", "C88374",
      {"1": "ANT_UFL_" + s, "2": "GND", "3": "GND"}, dnp=True, blocco=b)
    # header di debug/collaudo (non montato: pogo o saldato al bisogno)
    P("J%d" % (n + 2), "Conn_01x06", ("DEBUG " if s == "A" else "PROG ") + s + " (UART0 37/38 + EN + BOOT, pogo)",
      "PinHeader_1x06_P2.54mm_Vertical", "",
      {"1": "GND", "2": "U0TXD_" + s, "3": "U0RXD_" + s, "4": "EN_" + s, "5": "BOOT_" + s, "6": "3V3_" + s},
      dnp=True, blocco=b, nota="non montato: pad a 2,54 mm per pogo (collaudo) o header saldato al banco. Il ROM del P4 scarica solo da UART0 37/38 o USB-Serial/JTAG")
    # test point C6 (flash della C6 in fabbrica se servisse)
    P("TP%d" % (n + 1), "TestPoint", "C6_RXD_" + s, "TestPoint_Pad_D1.5mm", "", {"1": "C6_RXD_" + s}, blocco=b)
    P("TP%d" % (n + 2), "TestPoint", "C6_TXD_" + s, "TestPoint_Pad_D1.5mm", "", {"1": "C6_TXD_" + s}, blocco=b)
    P("TP%d" % (n + 3), "TestPoint", "C6_BOOT_" + s, "TestPoint_Pad_D1.5mm", "", {"1": "C6_BOOT_" + s}, blocco=b)
P("SW1", "TS-1187A-B-A-B", "BOOT A", "SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5", "C318884",
  {"1": "BOOT_A", "2": "BOOT_A", "3": "GND", "4": "GND"}, blocco="modulo A")
P("SW2", "TS-1187A-B-A-B", "RESET A", "SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5", "C318884",
  {"1": "EN_A", "2": "EN_A", "3": "GND", "4": "GND"}, blocco="modulo A")
P("TP30", "TestPoint", "USB_DM_B", "TestPoint_Pad_D1.5mm", "", {"1": "USB_DM_B"}, blocco="modulo B")
P("TP31", "TestPoint", "USB_DP_B", "TestPoint_Pad_D1.5mm", "", {"1": "USB_DP_B"}, blocco="modulo B")

# ---------------------------------------------------------------- collegamenti A ↔ B (piste, non più fili)
B = "A-B"
R("R50", "1k", "SYNC_M", "SYNC_B", RES["1k"], blocco=B, nota="SYNC 1 Hz A GPIO3 → B GPIO21 (HW3)")
R("R51", "1k", "WAKE_M", "WAKE_B", RES["1k"], blocco=B, nota="WAKE A GPIO5 → B GPIO5 (HW3)")
R("R52", "1k", "UART_AB", "UART_AB_B", RES["1k"], blocco=B, nota="A GPIO22 TX → B GPIO23 RX")
R("R53", "1k", "UART_BA_B", "UART_BA", RES["1k"], blocco=B, nota="B GPIO22 TX → A GPIO23 RX")
R("R54", "1k", "B_EN_CTL", "EN_B", RES["1k"], blocco=B, nota="A GPIO33 (open-drain) resetta B")
R("R55", "1k", "B_BOOT_CTL", "BOOT_B", RES["1k"], blocco=B, nota="A GPIO49 (open-drain) mette B in download")
for i, sig in enumerate(("SCLK", "MOSI", "MISO", "CS", "HS")):
    R("R%d" % (110 + i), "33", "SPI_%s_A" % sig, "SPI_%s_B" % sig, RES["33"], blocco=B,
      nota="SPI A↔B per il video della B verso la SD della A (firmware futuro)")
P("TP40", "TestPoint", "SYNC", "TestPoint_Pad_D1.5mm", "", {"1": "SYNC_M"}, blocco=B)
P("TP41", "TestPoint", "TRIG", "TestPoint_Pad_D1.5mm", "", {"1": "TRIG_M"}, blocco=B)

# ---------------------------------------------------------------- camere (FFC 15 pin standard Raspberry Pi)
for s, n in (("A", 60), ("B", 70)):
    b = "camera " + s
    P("J%d" % n, "1.0MM-15PLT", "CAM " + ("SX" if s == "A" else "DX") + " FFC 15p 1mm", "CONN-SMD_15P-P1.00_SHOU-HAN_1.0MM-15P-LT",
      "C7529394", {"1": "GND", "2": "CSI_D0N_" + s, "3": "CSI_D0P_" + s, "4": "GND", "5": "CSI_D1N_" + s,
                   "6": "CSI_D1P_" + s, "7": "GND", "8": "CSI_CKN_" + s, "9": "CSI_CKP_" + s, "10": "GND",
                   "11": "CAM_EN_" + s, "13": "I2C_SCL_" + s, "14": "I2C_SDA_" + s, "15": "3V3_" + s,
                   "16": "GND", "17": "GND"}, blocco=b, nota="pinout camera Raspberry Pi 15 pin; pin 12 (CAM_IO1) libero")
    P("J%d" % (n + 1), "SM02B-SRSS-TB", "TRIG " + s, "CONN-SMD_2P-P1.00_SM02B-SRSS-TB-LF-SN", "C160402",
      {"1": "TRIG_" + s, "2": "GND", "3": "GND", "4": "GND"}, blocco=b, nota="trigger/FSIN della camera (Inno-Maker J3)")
    R("R%d" % n, "100", "TRIG_M", "TRIG_" + s, RES["100"], blocco=b)
    R("R%d" % (n + 1), "4.7k", "I2C_SDA_" + s, "3V3_" + s, RES["4.7k"], blocco=b)
    R("R%d" % (n + 2), "4.7k", "I2C_SCL_" + s, "3V3_" + s, RES["4.7k"], blocco=b)
    R("R%d" % (n + 3), "10k", "CAM_EN_" + s, "3V3_" + s, RES["10k"], blocco=b,
      nota="camera accesa di default: il firmware HW3 non pilota GPIO12 (può tirarlo basso per spegnerla)")
    C("C%d" % n, "10u", "3V3_" + s, fp=C0603, lcsc="C19702", blocco=b)

# ---------------------------------------------------------------- SD (una per modulo, come HW3)
for s, n in (("A", 80), ("B", 90)):
    b = "SD " + s
    P("J%d" % n, "TF-015", "microSD " + s, "TF-SMD_TF-015", "C113206",
      {"1": "SD_D2_" + s, "2": "SD_D3_" + s, "3": "SD_CMD_" + s, "4": "SD_VCC_" + s, "5": "SD_CLK_" + s,
       "6": "GND", "7": "SD_D0_" + s, "8": "SD_D1_" + s, "10": "GND", "11": "GND", "12": "GND", "13": "GND"},
      blocco=b)
    P("Q%d" % (n // 10), "AO3401A", "AO3401A", "SOT-23-3_L3.0-W1.7-P0.95-LS2.9-BR", "C15127",
      {"1": "SD_PWR_N_" + s, "2": "3V3_" + s, "3": "SD_VCC_" + s}, blocco=b, nota="GPIO45 basso = SD accesa (come la dev-kit)")
    R("R%d" % n, "10k", "SD_PWR_N_" + s, "3V3_" + s, RES["10k"], blocco=b)
    R("R%d" % (n + 1), "22", "SD_CLK_M_" + s, "SD_CLK_" + s, RES["22"], blocco=b)
    for i, sig in enumerate(("D0", "D1", "D2", "D3", "CMD")):
        R("R%d" % (n + 2 + i), "10k", "SD_%s_%s" % (sig, s), "VDD_SDIO_" + s, RES["10k"], blocco=b,
          nota="pull-up al dominio IO della SD (ESP_LDO_VO4, checklist P4 §SD)")
    C("C%d" % n, "4.7u", "SD_VCC_" + s, fp="C_0402_1005Metric", lcsc="C23733", blocco=b)
    C("C%d" % (n + 1), "100n", "SD_VCC_" + s, blocco=b)
    C("C%d" % (n + 2), "1u", "VDD_SDIO_" + s, fp=C0603, lcsc="C1592", blocco=b)

# ---------------------------------------------------------------- IMU, buzzer, LED, espansione
B = "sensori e segnali"
P("U6", "LSM6DS3TR-C", "LSM6DS3TR-C", "LGA-14_L3.0-W2.5-P0.50-TL", "C967633",
  {"1": "GND", "2": "GND", "3": "GND", "4": "IMU_INT", "5": "3V3_A", "6": "GND", "7": "GND", "8": "3V3_A",
   "12": "3V3_A", "13": "I2C_SCL_A", "14": "I2C_SDA_A"}, blocco=B,
  nota="I2C 0x6A (SA0 a GND), CS alto = I2C; SDx/SCx a GND (aux non usato), INT1 → GPIO4 risveglio. NON è un MPU6050: il driver IMU del firmware va portato (unico cambio sw)")
C("C100", "100n", "3V3_A", blocco=B)
C("C101", "100n", "3V3_A", blocco=B)
P("BZ1", "HND-9650B", "buzzer attivo 3-7V", "BUZ-SMD_L9.6-W9.6-LS10.0-R", "C96127",
  {"1": "VSYS", "2": "BUZ_K"}, blocco=B, nota="sul pin del PA di HW3 (GPIO53): il saluto diventa un bip")
P("Q2", "S8050_C2146", "S8050", "SOT-23_L2.9-W1.3-P1.90-LS2.4-BR", "C2146",
  {"1": "BUZ_BASE", "2": "GND", "3": "BUZ_K"}, blocco=B)
R("R100", "1k", "BUZZER", "BUZ_BASE", RES["1k"], blocco=B)
R("R101", "100k", "BUZ_BASE", "GND", RES["100k"], blocco=B)
P("D1", "1N4148W_C81598", "1N4148W", "SOD-123F_L2.7-W1.6-LS3.8-RD", "C81598", {"1": "VSYS", "2": "BUZ_K"}, blocco=B)
for i, (net, col, lc, ref3v) in enumerate((("LED_R", "rosso", "C2286", "A"), ("LED_G", "verde", "C12624", "A"),
                                          ("LED_B", "blu (B)", "C2288", "B"))):
    P("D%d" % (2 + i), "LED", col, LED0603, lc, {"2": net + "_R", "1": "GND"}, blocco=B)
    R("R%d" % (102 + i), "1k", net, net + "_R", RES["1k"], blocco=B)
P("J100", "Conn_01x06", "ESPANSIONE A", "PinHeader_1x06_P2.54mm_Vertical", "",
  {"1": "3V3_A", "2": "EXP_IO1", "3": "EXP_IO47", "4": "EXP_IO48", "5": "VSYS", "6": "GND"}, dnp=True, blocco=B,
  nota="GPIO liberi della A. GPIO1 = XTAL_32K_P, GPIO47/48 nel dominio VDD_IO_5 (tensione della SD): verificare prima di usarli")
for i, net in enumerate(("VBUS", "BATP", "VSYS", "3V3_A", "3V3_B", "GND", "VSYS_IN")):
    P("TP%d" % (1 + i), "TestPoint", net, "TestPoint_Pad_D1.5mm", "", {"1": net}, blocco=B)
for i in range(4):
    P("H%d" % (1 + i), "MountingHole", "M2.5", "MountingHole_2.7mm_M2.5", "", {}, blocco="meccanica")
for i in range(8):
    P("H%d" % (11 + i), "MountingHole", "M2 camera", "MountingHole_2.2mm_M2", "", {}, blocco="meccanica",
      nota="fori camera: posizione DA VERIFICARE sul modulo camera scelto")

# net di alimentazione su cui serve PWR_FLAG (pin power_in senza un power_out che le pilota)
PWR_FLAGS = ["VBUS", "VBUS_RAW", "BATP", "BAT_N", "VSYS", "GND", "3V3_A", "3V3_B", "PROT_VCC", "VSYS_IN"]

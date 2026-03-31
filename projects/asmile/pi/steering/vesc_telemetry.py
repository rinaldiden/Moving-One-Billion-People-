#!/usr/bin/env python3
"""
Legge telemetria VESC in tempo reale: corrente, tensione, RPM, temperatura.
"""

import serial
import struct
import time

UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
COMM_GET_VALUES = 4


def crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def vesc_packet(payload: bytes) -> bytes:
    c = crc16(payload)
    return bytes([0x02, len(payload)]) + payload + struct.pack(">H", c) + bytes([0x03])


def parse_values(data: bytes):
    """Parse COMM_GET_VALUES response (FW 5.x)."""
    if len(data) < 56:
        return None

    # Skip packet framing, find payload
    # Packet: 0x02 len payload crc16 0x03
    # Or: 0x03 len_hi len_lo payload crc16 0x03
    idx = 0
    if data[0] == 0x02:
        plen = data[1]
        payload = data[2:2+plen]
    elif data[0] == 0x03:
        plen = (data[1] << 8) | data[2]
        payload = data[3:3+plen]
    else:
        return None

    if len(payload) < 56 or payload[0] != COMM_GET_VALUES:
        return None

    p = payload[1:]  # skip command byte

    try:
        temp_fet = struct.unpack(">h", p[0:2])[0] / 10.0
        temp_motor = struct.unpack(">h", p[2:4])[0] / 10.0
        current_motor = struct.unpack(">i", p[4:8])[0] / 100.0
        current_input = struct.unpack(">i", p[8:12])[0] / 100.0
        # p[12:16] = id, p[16:20] = iq
        duty = struct.unpack(">h", p[20:22])[0] / 1000.0
        rpm = struct.unpack(">i", p[22:26])[0]
        v_in = struct.unpack(">h", p[26:28])[0] / 10.0
        amp_hours = struct.unpack(">i", p[28:32])[0] / 10000.0
        amp_hours_charged = struct.unpack(">i", p[32:36])[0] / 10000.0
        watt_hours = struct.unpack(">i", p[36:40])[0] / 10000.0
        watt_hours_charged = struct.unpack(">i", p[40:44])[0] / 10000.0
        tachometer = struct.unpack(">i", p[44:48])[0]
        tachometer_abs = struct.unpack(">i", p[48:52])[0]
        fault = p[52]

        return {
            'temp_fet': temp_fet,
            'temp_motor': temp_motor,
            'i_motor': current_motor,
            'i_input': current_input,
            'duty': duty,
            'rpm': rpm,
            'v_in': v_in,
            'ah': amp_hours,
            'ah_charged': amp_hours_charged,
            'wh': watt_hours,
            'wh_charged': watt_hours_charged,
            'tach': tachometer,
            'tach_abs': tachometer_abs,
            'fault': fault,
        }
    except (struct.error, IndexError):
        return None


FAULT_NAMES = {
    0: "NONE",
    1: "OVER_VOLTAGE",
    2: "UNDER_VOLTAGE",
    3: "DRV",
    4: "ABS_OVER_CURRENT",
    5: "OVER_TEMP_FET",
    6: "OVER_TEMP_MOTOR",
    7: "GATE_DRIVER_OVER_VOLTAGE",
    8: "GATE_DRIVER_UNDER_VOLTAGE",
}


def main():
    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.2)
    ser.reset_input_buffer()

    print("=== VESC Telemetria ===")
    print("Ctrl+C per fermare\n")

    peak_motor = 0.0
    peak_input = 0.0

    try:
        while True:
            ser.reset_input_buffer()
            ser.write(vesc_packet(bytes([COMM_GET_VALUES])))
            time.sleep(0.05)

            resp = ser.read(ser.in_waiting or 128)
            if not resp:
                print("  Nessuna risposta...")
                time.sleep(0.5)
                continue

            vals = parse_values(resp)
            if not vals:
                # Riprova con più dati
                time.sleep(0.05)
                resp += ser.read(ser.in_waiting or 128)
                vals = parse_values(resp)

            if vals:
                peak_motor = max(peak_motor, abs(vals['i_motor']))
                peak_input = max(peak_input, abs(vals['i_input']))
                fault_name = FAULT_NAMES.get(vals['fault'], f"UNKNOWN({vals['fault']})")

                print(
                    f"\r\033[K"
                    f"I_mot={vals['i_motor']:+6.1f}A "
                    f"I_bat={vals['i_input']:+5.1f}A "
                    f"V={vals['v_in']:4.1f}V "
                    f"RPM={vals['rpm']:+6d} "
                    f"duty={vals['duty']:+.2f} "
                    f"T_fet={vals['temp_fet']:.0f}° "
                    f"T_mot={vals['temp_motor']:.0f}° "
                    f"fault={fault_name} "
                    f"| PEAK: mot={peak_motor:.1f}A bat={peak_input:.1f}A",
                    end='', flush=True
                )
            else:
                print(f"\r\033[KParsing fallito ({len(resp)} bytes)", end='', flush=True)

            time.sleep(0.2)

    except KeyboardInterrupt:
        print(f"\n\n=== Picco corrente motore: {peak_motor:.1f}A ===")
        print(f"=== Picco corrente batteria: {peak_input:.1f}A ===")
    finally:
        ser.close()


if __name__ == "__main__":
    main()

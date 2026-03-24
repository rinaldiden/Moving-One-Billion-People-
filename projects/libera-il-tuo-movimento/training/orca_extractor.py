"""
BLOCCO 3 — Training Extractor: OrcaSlicer
Legge i profili di stampa .json da OrcaSlicer e costruisce
il database dei parametri di slicing per i materiali usati.

SETUP:
  OrcaSlicer salva i profili in:
  - macOS: ~/Library/Application Support/OrcaSlicer/user/
  - Windows: %APPDATA%/OrcaSlicer/user/
  - Linux: ~/.config/OrcaSlicer/user/
"""

import json
import os
import platform
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "data" / "orca_profiles"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_orca_profile_dir() -> Path:
    """Trova la directory profili OrcaSlicer in base al sistema operativo."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "OrcaSlicer" / "user"
    elif system == "Windows":
        return Path(os.environ["APPDATA"]) / "OrcaSlicer" / "user"
    else:
        return Path.home() / ".config" / "OrcaSlicer" / "user"


def extract_filament_profile(profile_path: Path) -> dict:
    """Estrae i parametri chiave da un profilo filamento OrcaSlicer."""
    with open(profile_path) as f:
        profile = json.load(f)
    
    return {
        "name": profile.get("name", profile_path.stem),
        "filament_type": profile.get("filament_type", "unknown"),
        "nozzle_temp": profile.get("nozzle_temperature", [230])[0],
        "bed_temp": profile.get("bed_temperature", [60])[0],
        "fan_speed": profile.get("fan_speed", [100])[0],
        "retraction_length": profile.get("retraction_length", [0.5])[0],
        "print_speed": profile.get("outer_wall_speed", 60),
        "layer_height": profile.get("layer_height", 0.2),
        "infill_pattern": profile.get("infill_pattern", "gyroid"),
        "source_file": str(profile_path)
    }


def extract_printer_profile(profile_path: Path) -> dict:
    """Estrae i parametri macchina da un profilo stampante OrcaSlicer."""
    with open(profile_path) as f:
        profile = json.load(f)
    
    return {
        "name": profile.get("name", profile_path.stem),
        "machine_name": profile.get("machine_name", "unknown"),
        "bed_x": profile.get("printable_area", [[0, 0], [256, 256]])[1][0],
        "bed_y": profile.get("printable_area", [[0, 0], [256, 256]])[1][1],
        "max_speed": profile.get("machine_max_speed_x", [500])[0],
        "start_gcode": profile.get("machine_start_gcode", ""),
        "end_gcode": profile.get("machine_end_gcode", ""),
        "source_file": str(profile_path)
    }


def scan_and_export(output_file: str = "orca_profiles.json"):
    """Scansiona tutti i profili OrcaSlicer e li esporta."""
    profile_dir = get_orca_profile_dir()
    
    if not profile_dir.exists():
        print(f"Directory profili non trovata: {profile_dir}")
        print("Specifica manualmente con: ORCA_PROFILE_DIR=/path/to/profiles")
        return
    
    results = {"filaments": [], "printers": [], "processes": []}
    
    for json_file in profile_dir.rglob("*.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            if "filament_type" in data:
                results["filaments"].append(extract_filament_profile(json_file))
            elif "machine_name" in data or "printable_area" in data:
                results["printers"].append(extract_printer_profile(json_file))
            
        except Exception as e:
            print(f"Errore leggendo {json_file}: {e}")
    
    output_path = OUTPUT_DIR / output_file
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Estratti {len(results['filaments'])} profili filamento")
    print(f"Estratti {len(results['printers'])} profili stampante")
    print(f"Salvato in: {output_path}")
    return results


if __name__ == "__main__":
    print("OrcaSlicer Extractor — LIBERA IL TUO MOVIMENTO")
    scan_and_export()

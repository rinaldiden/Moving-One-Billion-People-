"""
OrcaSlicer Bridge — verifica visiva del G-code generato
Apre OrcaSlicer con il G-code per la preview layer-by-layer.

In OrcaSlicer: File → Import → Import G-code
oppure da CLI: OrcaSlicer --slice /path/to/file.gcode
"""

import subprocess
import platform
import os
from pathlib import Path


def get_orca_executable() -> str:
    """Trova l'eseguibile OrcaSlicer."""
    custom = os.getenv("ORCA_SLICER_PATH")
    if custom and Path(custom).exists():
        return custom
    
    system = platform.system()
    defaults = {
        "Darwin": "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
        "Windows": r"C:\Program Files\OrcaSlicer\OrcaSlicer.exe",
        "Linux": "/usr/bin/orca-slicer"
    }
    return defaults.get(system, "orca-slicer")


def open_gcode_for_preview(gcode_path: str):
    """
    Apre il G-code in OrcaSlicer per verifica visiva.
    OrcaSlicer mostra automaticamente il preview layer-by-layer.
    """
    orca = get_orca_executable()
    gcode = Path(gcode_path).resolve()
    
    if not gcode.exists():
        print(f"G-code non trovato: {gcode}")
        return False
    
    print(f"Apertura in OrcaSlicer: {gcode}")
    print("Usa il slider layer nell'anteprima per verificare la stampa.")
    
    try:
        subprocess.Popen([orca, str(gcode)])
        return True
    except FileNotFoundError:
        print(f"OrcaSlicer non trovato in: {orca}")
        print("Imposta ORCA_SLICER_PATH in .env oppure apri manualmente:")
        print(f"  File → Import → Import G-code → {gcode}")
        return False


def simulate_gcode_stats(gcode_path: str) -> dict:
    """
    Analisi statica del G-code senza aprire OrcaSlicer.
    Estrae statistiche: layer count, tempo stimato, materiale usato.
    """
    stats = {
        "layer_count": 0,
        "total_lines": 0,
        "estimated_time_min": 0,
        "filament_used_mm": 0,
        "max_z_mm": 0,
        "move_commands": 0
    }
    
    with open(gcode_path) as f:
        for line in f:
            stats["total_lines"] += 1
            line = line.strip()
            
            if line.startswith(";LAYER_CHANGE") or line.startswith(";LAYER:"):
                stats["layer_count"] += 1
            
            if line.startswith("G1") or line.startswith("G0"):
                stats["move_commands"] += 1
                if "Z" in line:
                    try:
                        z = float([p for p in line.split() if p.startswith("Z")][0][1:])
                        stats["max_z_mm"] = max(stats["max_z_mm"], z)
                    except (IndexError, ValueError):
                        pass
                if "E" in line:
                    try:
                        e = float([p for p in line.split() if p.startswith("E")][0][1:])
                        stats["filament_used_mm"] = max(stats["filament_used_mm"], e)
                    except (IndexError, ValueError):
                        pass
    
    # Stima grezza: ~1 min ogni 500 comandi di movimento
    stats["estimated_time_min"] = round(stats["move_commands"] / 500, 1)
    
    return stats


if __name__ == "__main__":
    import sys
    gcode = sys.argv[1] if len(sys.argv) > 1 else "output/joint_output.gcode"
    
    stats = simulate_gcode_stats(gcode)
    print(f"\nStatistiche G-code: {gcode}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    open_gcode_for_preview(gcode)

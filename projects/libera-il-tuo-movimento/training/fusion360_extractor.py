"""
BLOCCO 3 — Training Extractor: Fusion 360
Legge i file .f3d / .step / .stl dalla libreria Fusion 360 dell'utente
ed estrae parametri geometrici per costruire il dataset di training.

SETUP:
  1. Installa Fusion 360 MCP: https://github.com/mycelia1/fusion360-mcp-server
  2. Configura il token in .env: FUSION360_TOKEN=...
  3. Lancia: python training/fusion360_extractor.py
"""

import json
import os
from pathlib import Path

# Il MCP server di Fusion 360 espone le API via socket locale
# Configurato via mycelia1/fusion360-mcp-server
FUSION_MCP_HOST = "localhost"
FUSION_MCP_PORT = 8765

OUTPUT_DIR = Path(__file__).parent / "data" / "fusion360"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_joint_parameters(f3d_path: str) -> dict:
    """
    Estrae parametri da un file Fusion 360.
    Richiede il MCP server attivo in Fusion 360.
    
    Returns: dict con geometria, parametri, dimensioni
    """
    # TODO: implementare connessione MCP
    # Il server MCP espone i parametri Fusion via JSON-RPC
    raise NotImplementedError(
        "Configura prima il Fusion 360 MCP server.\n"
        "Vedi: https://github.com/mycelia1/fusion360-mcp-server"
    )


def scan_fusion_library(library_path: str) -> list:
    """Scansiona la libreria Fusion 360 e raccoglie tutti i giunti."""
    joints = []
    library = Path(library_path)
    
    for f3d in library.rglob("*.f3d"):
        print(f"Trovato: {f3d.name}")
        joints.append({
            "file": str(f3d),
            "name": f3d.stem,
            "type": classify_joint_from_name(f3d.stem)
        })
    
    return joints


def classify_joint_from_name(name: str) -> str:
    """Classifica il tipo di giunto dal nome del file."""
    name_lower = name.lower()
    if any(k in name_lower for k in ['bb', 'bottom_bracket', 'movimento']):
        return 'bottom_bracket'
    if any(k in name_lower for k in ['head', 'sterzo', 'headtube']):
        return 'head_tube'
    if any(k in name_lower for k in ['seat', 'reggisella', 'seatstay']):
        return 'seat_cluster'
    if 'chainstay' in name_lower or 'carro' in name_lower:
        return 'chainstay_junction'
    return 'generic_junction'


def build_dataset_entry(joint_params: dict, gcode_path: str) -> dict:
    """Costruisce un entry del dataset: input params → output gcode."""
    with open(gcode_path) as f:
        gcode = f.read()
    
    return {
        "input": joint_params,
        "output": gcode,
        "metadata": {
            "source": "fusion360",
            "validated": False
        }
    }


if __name__ == "__main__":
    print("Fusion 360 Extractor — LIBERA IL TUO MOVIMENTO")
    print("Configura FUSION360_TOKEN in .env e avvia il MCP server in Fusion 360")
    print("Poi lancia: python training/fusion360_extractor.py /path/to/fusion/library")

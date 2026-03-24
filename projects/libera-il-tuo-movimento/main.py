#!/usr/bin/env python3
"""
LIBERA IL TUO MOVIMENTO
Entry point — lancia la pipeline completa da riga di comando
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Aggiungi agents/ al path
sys.path.insert(0, str(Path(__file__).parent / "agents"))
from orchestrator import run_pipeline

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        print("LIBERA IL TUO MOVIMENTO")
        print("Descrivi il nodo o il telaio che vuoi progettare.")
        print("Esempio: 'Nodo del movimento centrale per bici cargo con tre tubi in entrata, bambù 38mm'")
        print()
        user_input = input(">>> ")

    result = run_pipeline(user_input, verbose=True)
    print("\nPipeline completata. Output salvato in /output/joint_output.gcode")

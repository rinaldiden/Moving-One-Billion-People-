"""
LIBERA IL TUO MOVIMENTO — Dataset Builder
Costruisce coppie (3D geometry -> G-code) per il training degli agenti.

Workflow:
1. Metti i file .stl/.step/.3mf in training/data/joints_3d/
2. Metti i G-code corrispondenti in training/data/joints_gcode/
3. Lancia: python training/dataset_builder.py
4. Le coppie vengono salvate in training/data/pairs/
"""

import json
import struct
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
JOINTS_3D_DIR = DATA_DIR / "joints_3d"
GCODE_DIR = DATA_DIR / "joints_gcode"
PAIRS_DIR = DATA_DIR / "pairs"


def parse_stl_binary(filepath: Path) -> dict:
    """Estrae geometria base da un STL binario."""
    with open(filepath, "rb") as f:
        header = f.read(80)
        num_triangles = struct.unpack("<I", f.read(4))[0]

        vertices = []
        normals = []
        bbox = {
            "min": [float("inf")] * 3,
            "max": [float("-inf")] * 3,
        }

        for _ in range(num_triangles):
            normal = struct.unpack("<3f", f.read(12))
            normals.append(list(normal))
            for _ in range(3):
                vertex = struct.unpack("<3f", f.read(12))
                vertices.append(list(vertex))
                for axis in range(3):
                    bbox["min"][axis] = min(bbox["min"][axis], vertex[axis])
                    bbox["max"][axis] = max(bbox["max"][axis], vertex[axis])
            f.read(2)  # attribute byte count

    size = [bbox["max"][i] - bbox["min"][i] for i in range(3)]

    return {
        "file": filepath.name,
        "format": "stl",
        "triangles": num_triangles,
        "vertices": len(vertices),
        "bbox_mm": {
            "min": [round(v, 2) for v in bbox["min"]],
            "max": [round(v, 2) for v in bbox["max"]],
        },
        "size_mm": [round(s, 2) for s in size],
        "volume_approx_mm3": round(size[0] * size[1] * size[2], 1),
    }


def parse_stl_ascii(filepath: Path) -> dict:
    """Estrae geometria base da un STL ASCII."""
    text = filepath.read_text(errors="replace")
    lines = text.strip().split("\n")

    vertices = []
    bbox = {
        "min": [float("inf")] * 3,
        "max": [float("-inf")] * 3,
    }

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("vertex"):
            parts = stripped.split()
            vertex = [float(parts[1]), float(parts[2]), float(parts[3])]
            vertices.append(vertex)
            for axis in range(3):
                bbox["min"][axis] = min(bbox["min"][axis], vertex[axis])
                bbox["max"][axis] = max(bbox["max"][axis], vertex[axis])

    size = [bbox["max"][i] - bbox["min"][i] for i in range(3)]
    num_triangles = len(vertices) // 3

    return {
        "file": filepath.name,
        "format": "stl_ascii",
        "triangles": num_triangles,
        "vertices": len(vertices),
        "bbox_mm": {
            "min": [round(v, 2) for v in bbox["min"]],
            "max": [round(v, 2) for v in bbox["max"]],
        },
        "size_mm": [round(s, 2) for s in size],
        "volume_approx_mm3": round(size[0] * size[1] * size[2], 1),
    }


def parse_stl(filepath: Path) -> dict:
    """Rileva automaticamente STL binario vs ASCII."""
    with open(filepath, "rb") as f:
        header = f.read(80)
    if b"solid" in header[:10]:
        # Potrebbe essere ASCII, verifica
        text_start = filepath.read_text(errors="replace")[:200]
        if "facet normal" in text_start:
            return parse_stl_ascii(filepath)
    return parse_stl_binary(filepath)


def parse_gcode(filepath: Path) -> dict:
    """Estrae statistiche dal G-code."""
    lines = filepath.read_text().split("\n")
    total_lines = len(lines)

    g1_count = 0
    g0_count = 0
    max_z = 0
    filament_e = 0
    layers = set()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("G1"):
            g1_count += 1
        elif stripped.startswith("G0"):
            g0_count += 1

        z_match = None
        if "Z" in stripped:
            parts = stripped.split()
            for p in parts:
                if p.startswith("Z"):
                    try:
                        z_val = float(p[1:])
                        max_z = max(max_z, z_val)
                        layers.add(round(z_val, 2))
                    except ValueError:
                        pass

        if "E" in stripped:
            parts = stripped.split()
            for p in parts:
                if p.startswith("E"):
                    try:
                        filament_e = max(filament_e, float(p[1:]))
                    except ValueError:
                        pass

    return {
        "file": filepath.name,
        "total_lines": total_lines,
        "g0_moves": g0_count,
        "g1_moves": g1_count,
        "layers": len(layers),
        "max_z_mm": round(max_z, 2),
        "filament_mm": round(filament_e, 1),
    }


def match_pairs() -> list:
    """Cerca coppie 3D/G-code con nomi corrispondenti."""
    stl_files = {}
    for ext in ["*.stl", "*.step", "*.stp", "*.3mf"]:
        for f in JOINTS_3D_DIR.glob(ext):
            stl_files[f.stem.lower()] = f

    gcode_files = {}
    for f in GCODE_DIR.glob("*.gcode"):
        gcode_files[f.stem.lower()] = f

    pairs = []
    matched = set()

    for name, stl_path in stl_files.items():
        # Match esatto
        if name in gcode_files:
            pairs.append((stl_path, gcode_files[name]))
            matched.add(name)
            continue

        # Match parziale (nome_joint -> nome_joint_plate)
        for gname, gpath in gcode_files.items():
            if gname.startswith(name) or name.startswith(gname):
                if gname not in matched:
                    pairs.append((stl_path, gpath))
                    matched.add(gname)
                    break

    return pairs


def build_dataset():
    """Costruisce il dataset di coppie."""
    PAIRS_DIR.mkdir(parents=True, exist_ok=True)

    pairs = match_pairs()
    if not pairs:
        print("Nessuna coppia trovata.")
        print(f"  Metti i file 3D in: {JOINTS_3D_DIR}/")
        print(f"  Metti i G-code in:  {GCODE_DIR}/")
        print(f"  I nomi devono corrispondere (es. headtube.stl + headtube.gcode)")
        return

    print(f"Trovate {len(pairs)} coppie 3D/G-code\n")

    for stl_path, gcode_path in pairs:
        pair_name = stl_path.stem
        print(f"  [{pair_name}] {stl_path.name} <-> {gcode_path.name}")

        # Parse 3D
        if stl_path.suffix.lower() == ".stl":
            geo = parse_stl(stl_path)
        else:
            geo = {
                "file": stl_path.name,
                "format": stl_path.suffix.lower().lstrip("."),
                "note": "Parsing completo richiede libreria specifica",
            }

        # Parse G-code
        gcode_stats = parse_gcode(gcode_path)

        # Build pair record
        pair_record = {
            "name": pair_name,
            "created": datetime.now().isoformat(),
            "geometry_3d": geo,
            "gcode": gcode_stats,
            "gcode_content": gcode_path.read_text(),
            "metadata": {
                "source_3d": str(stl_path),
                "source_gcode": str(gcode_path),
            },
        }

        # Save
        out_path = PAIRS_DIR / f"{pair_name}.json"
        out_path.write_text(json.dumps(pair_record, indent=2, ensure_ascii=False))
        print(f"    -> {out_path}")

    print(f"\nDataset: {len(pairs)} coppie in {PAIRS_DIR}/")


def stats():
    """Mostra statistiche del dataset corrente."""
    pairs = list(PAIRS_DIR.glob("*.json"))
    stl_files = list(JOINTS_3D_DIR.glob("*.*")) if JOINTS_3D_DIR.exists() else []
    gcode_files = list(GCODE_DIR.glob("*.gcode")) if GCODE_DIR.exists() else []

    print("=== TRAINING DATASET ===")
    print(f"  File 3D:      {len(stl_files)}")
    print(f"  File G-code:  {len(gcode_files)}")
    print(f"  Coppie:       {len(pairs)}")

    if pairs:
        print("\nCoppie disponibili:")
        for p in sorted(pairs):
            data = json.loads(p.read_text())
            geo = data.get("geometry_3d", {})
            gc = data.get("gcode", {})
            size = geo.get("size_mm", [0, 0, 0])
            print(f"  {p.stem}: {size[0]}x{size[1]}x{size[2]}mm, "
                  f"{gc.get('layers', '?')} layers, {gc.get('filament_mm', '?')}mm filamento")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        stats()
    else:
        build_dataset()

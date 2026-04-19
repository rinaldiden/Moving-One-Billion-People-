"""
LIBERA IL TUO MOVIMENTO — Joint Trainer
Usa le coppie 3D/G-code per arricchire il contesto degli agenti.

Approccio: few-shot learning con le coppie reali.
Ogni coppia diventa un esempio nel system prompt degli agenti 5 e 7.
"""

import json
import yaml
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PAIRS_DIR = BASE_DIR / "training" / "data" / "pairs"
CONFIG_PATH = BASE_DIR / "config" / "agents_config.yaml"
EXAMPLES_DIR = BASE_DIR / "training" / "data" / "examples"


def build_few_shot_examples() -> dict:
    """Costruisce esempi few-shot dalle coppie di training."""
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    pairs = sorted(PAIRS_DIR.glob("*.json"))
    if not pairs:
        print("Nessuna coppia di training trovata. Lancia prima dataset_builder.py")
        return {}

    examples = {"joint_generator": [], "gcode_translator": []}

    for pair_path in pairs:
        data = json.loads(pair_path.read_text())
        name = data["name"]
        geo = data["geometry_3d"]
        gc = data["gcode"]

        # Esempio per Agente 5 (Joint Generator)
        joint_example = {
            "name": name,
            "input": {
                "description": f"Giunto '{name}'",
                "size_mm": geo.get("size_mm", []),
                "triangles": geo.get("triangles", 0),
                "bbox": geo.get("bbox_mm", {}),
            },
            "output_hint": (
                f"Giunto con {geo.get('triangles', '?')} triangoli, "
                f"dimensioni {geo.get('size_mm', '?')}mm"
            ),
        }
        examples["joint_generator"].append(joint_example)

        # Esempio per Agente 7 (G-code Translator)
        # Prendi le prime 50 righe significative del G-code
        gcode_content = data.get("gcode_content", "")
        gcode_lines = gcode_content.split("\n")
        significant = [l for l in gcode_lines if l.strip() and not l.strip().startswith(";")][:50]

        gcode_example = {
            "name": name,
            "input": {
                "geometry_size_mm": geo.get("size_mm", []),
                "target_layers": gc.get("layers", 0),
                "max_z_mm": gc.get("max_z_mm", 0),
            },
            "output_sample": "\n".join(significant[:20]),
            "stats": {
                "layers": gc.get("layers", 0),
                "g1_moves": gc.get("g1_moves", 0),
                "filament_mm": gc.get("filament_mm", 0),
            },
        }
        examples["gcode_translator"].append(gcode_example)

        print(f"  [{name}] esempio generato")

    # Salva esempi
    for agent_type, agent_examples in examples.items():
        out_path = EXAMPLES_DIR / f"{agent_type}_examples.json"
        out_path.write_text(json.dumps(agent_examples, indent=2, ensure_ascii=False))
        print(f"\n  {agent_type}: {len(agent_examples)} esempi -> {out_path}")

    return examples


def inject_examples_into_config(dry_run: bool = False):
    """Aggiunge gli esempi few-shot ai system prompt degli agenti."""

    joint_examples_path = EXAMPLES_DIR / "joint_generator_examples.json"
    gcode_examples_path = EXAMPLES_DIR / "gcode_translator_examples.json"

    if not joint_examples_path.exists() or not gcode_examples_path.exists():
        print("Esempi non trovati. Lancia prima: python joint_trainer.py --build")
        return

    joint_examples = json.loads(joint_examples_path.read_text())
    gcode_examples = json.loads(gcode_examples_path.read_text())

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    # Agente 5 — Joint Generator
    if "agent5_joint_generator" in config["agents"]:
        examples_text = format_joint_examples(joint_examples)
        marker = "\n\n---ESEMPI DAL TRAINING---\n"
        prompt = config["agents"]["agent5_joint_generator"]["system_prompt"]
        # Rimuovi esempi precedenti se ci sono
        if marker in prompt:
            prompt = prompt.split(marker)[0]
        prompt += marker + examples_text
        config["agents"]["agent5_joint_generator"]["system_prompt"] = prompt

    # Agente 7 — G-code Translator
    if "agent7_gcode" in config["agents"]:
        examples_text = format_gcode_examples(gcode_examples)
        marker = "\n\n---ESEMPI DAL TRAINING---\n"
        prompt = config["agents"]["agent7_gcode"]["system_prompt"]
        if marker in prompt:
            prompt = prompt.split(marker)[0]
        prompt += marker + examples_text
        config["agents"]["agent7_gcode"]["system_prompt"] = prompt

    if dry_run:
        print("\n[DRY RUN] Ecco come sarebbero i prompt aggiornati:")
        for agent in ["agent5_joint_generator", "agent7_gcode"]:
            prompt = config["agents"][agent]["system_prompt"]
            print(f"\n{'='*60}\n[{agent}] ultimi 500 caratteri:\n{'='*60}")
            print(prompt[-500:])
    else:
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        print(f"\nConfig aggiornata: {CONFIG_PATH}")
        print("Gli agenti 5 e 7 ora hanno gli esempi dal training.")


def format_joint_examples(examples: list) -> str:
    """Formatta gli esempi per il prompt dell'Agente 5."""
    parts = ["Ecco giunti reali gia' stampati e verificati. Usa queste dimensioni e proporzioni come riferimento:\n"]
    for ex in examples:
        inp = ex["input"]
        parts.append(
            f"- **{ex['name']}**: {inp.get('size_mm', '?')}mm, "
            f"{inp.get('triangles', '?')} triangoli. {ex.get('output_hint', '')}"
        )
    return "\n".join(parts)


def format_gcode_examples(examples: list) -> str:
    """Formatta gli esempi per il prompt dell'Agente 7."""
    parts = ["Ecco G-code reali gia' stampati con successo. Usa questi pattern come riferimento:\n"]
    for ex in examples:
        stats = ex["stats"]
        parts.append(
            f"- **{ex['name']}**: {stats.get('layers', '?')} layers, "
            f"{stats.get('g1_moves', '?')} movimenti G1, "
            f"{stats.get('filament_mm', '?')}mm filamento"
        )
        if ex.get("output_sample"):
            parts.append(f"  Prime righe G-code:\n  ```\n  {ex['output_sample'][:300]}\n  ```")
    return "\n".join(parts)


if __name__ == "__main__":
    if "--build" in sys.argv:
        print("=== Building few-shot examples ===\n")
        build_few_shot_examples()
    elif "--inject" in sys.argv:
        print("=== Injecting examples into agent config ===\n")
        inject_examples_into_config(dry_run="--dry-run" in sys.argv)
    elif "--all" in sys.argv:
        print("=== Full training pipeline ===\n")
        build_few_shot_examples()
        print()
        inject_examples_into_config()
    else:
        print("Uso:")
        print("  python joint_trainer.py --build      Costruisce esempi dalle coppie")
        print("  python joint_trainer.py --inject      Inietta esempi nei prompt agenti")
        print("  python joint_trainer.py --inject --dry-run   Preview senza scrivere")
        print("  python joint_trainer.py --all          Build + inject")

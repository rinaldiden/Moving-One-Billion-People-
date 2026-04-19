"""
Async wrapper per la pipeline — invia aggiornamenti via WebSocket.
"""

import asyncio
import subprocess
import json
import yaml
from pathlib import Path
from typing import Optional
from fastapi import WebSocket

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "agents_config.yaml"
OUTPUT_DIR = BASE_DIR / "output"

AGENTS_ORDER = [
    "agent1_architect",
    "agent2_structural",
    "agent3_pilot",
    "agent4_dimensioner",
    "agent4b_components",
    "agent5_joint_generator",
    "agent6_visual_reviewer",
    "agent7_gcode",
]

AGENT_LABELS = {
    "agent1_architect": "Architetto del Telaio",
    "agent2_structural": "Strutturista da Campo",
    "agent3_pilot": "Il Pilota",
    "agent4_dimensioner": "Dimensionatore Sezioni",
    "agent4b_components": "Geometra dei Componenti",
    "agent5_joint_generator": "Generatore Giunti",
    "agent6_visual_reviewer": "Revisore Visivo",
    "agent7_gcode": "Traduttore G-code",
}


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def call_agent_sync(config, agent_name: str, user_message: str, context: dict = None) -> str:
    system = config["agents"][agent_name]["system_prompt"]
    if context:
        context_str = "\n\n---CONTESTO PIPELINE---\n" + json.dumps(context, indent=2, ensure_ascii=False)
        full_message = user_message + context_str
    else:
        full_message = user_message

    prompt = f"{system}\n\n---\n\n{full_message}"

    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed for {agent_name}: {result.stderr[:500]}")

    if not result.stdout.strip():
        raise RuntimeError(f"claude -p returned empty output for {agent_name}")

    return result.stdout.strip()


def extract_gcode(text: str) -> str:
    lines = text.split("\n")
    gcode_lines = [l for l in lines if l.strip().startswith((";", "G", "M", "T", "F", "E", "X", "Y", "Z"))]
    return "\n".join(gcode_lines) if gcode_lines else text


async def run_pipeline_async(user_input: str, ws: Optional[WebSocket] = None) -> dict:
    config = load_config()
    pipeline_context = {}
    OUTPUT_DIR.mkdir(exist_ok=True)

    async def send(msg: dict):
        if ws:
            await ws.send_json(msg)

    await send({"type": "start", "prompt": user_input})

    for i, agent_name in enumerate(AGENTS_ORDER):
        label = AGENT_LABELS[agent_name]
        await send({
            "type": "agent_start",
            "agent": agent_name,
            "label": label,
            "step": i + 1,
            "total": len(AGENTS_ORDER),
        })

        # Build context based on agent dependencies
        context = _build_context(agent_name, pipeline_context)

        # Run in thread to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            output = await loop.run_in_executor(
                None, call_agent_sync, config, agent_name, user_input, context
            )
        except Exception as e:
            await send({"type": "agent_error", "agent": agent_name, "error": str(e)})
            raise

        pipeline_context[agent_name] = output

        # Save intermediate output
        output_path = OUTPUT_DIR / f"{agent_name}.json"
        output_path.write_text(json.dumps({"output": output}, indent=2, ensure_ascii=False))

        await send({
            "type": "agent_done",
            "agent": agent_name,
            "label": label,
            "step": i + 1,
            "output_preview": output[:500],
        })

    # Save final G-code
    gcode_path = OUTPUT_DIR / "joint_output.gcode"
    gcode_path.write_text(extract_gcode(pipeline_context["agent7_gcode"]))

    await send({"type": "pipeline_done", "gcode_ready": True})
    return pipeline_context


def _build_context(agent_name: str, ctx: dict) -> dict:
    """Costruisce il contesto per ogni agente in base alle dipendenze."""
    deps = {
        "agent1_architect": {},
        "agent2_structural": {"wireframe": "agent1_architect"},
        "agent3_pilot": {"wireframe": "agent1_architect", "structural": "agent2_structural"},
        "agent4_dimensioner": {
            "wireframe": "agent1_architect",
            "structural": "agent2_structural",
            "pilot_feedback": "agent3_pilot",
        },
        "agent4b_components": {"wireframe": "agent1_architect", "sections": "agent4_dimensioner"},
        "agent5_joint_generator": {
            "wireframe": "agent1_architect",
            "structural": "agent2_structural",
            "sections": "agent4_dimensioner",
            "clearances": "agent4b_components",
        },
        "agent6_visual_reviewer": {
            "joint_geometry": "agent5_joint_generator",
            "pilot_feedback": "agent3_pilot",
        },
        "agent7_gcode": {
            "joint_geometry": "agent5_joint_generator",
            "visual_approval": "agent6_visual_reviewer",
        },
    }
    agent_deps = deps.get(agent_name, {})
    return {key: ctx[source] for key, source in agent_deps.items() if source in ctx}


def get_training_stats() -> dict:
    data_dir = BASE_DIR / "training" / "data"
    pairs_dir = data_dir / "pairs"
    stl_dir = data_dir / "joints_3d"
    gcode_dir = data_dir / "joints_gcode"

    return {
        "pairs": len(list(pairs_dir.glob("*.json"))) if pairs_dir.exists() else 0,
        "stl_files": len(list(stl_dir.glob("*.*"))) if stl_dir.exists() else 0,
        "gcode_files": len(list(gcode_dir.glob("*.gcode"))) if gcode_dir.exists() else 0,
    }

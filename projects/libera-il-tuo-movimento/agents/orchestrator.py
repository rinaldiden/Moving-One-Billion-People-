"""
LIBERA IL TUO MOVIMENTO
Orchestrator — coordina tutti gli agenti in sequenza
"""

import anthropic
import json
import yaml
import os
from pathlib import Path

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"

CONFIG_PATH = Path(__file__).parent.parent / "config" / "agents_config.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)


def call_agent(agent_name: str, user_message: str, context: dict = {}) -> str:
    system = CONFIG["agents"][agent_name]["system_prompt"]
    if context:
        context_str = "\n\n---CONTESTO PIPELINE---\n" + json.dumps(context, indent=2, ensure_ascii=False)
        full_message = user_message + context_str
    else:
        full_message = user_message

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": full_message}]
    )
    return response.content[0].text


def run_pipeline(user_input: str, verbose: bool = True) -> dict:
    pipeline_context = {}

    def log(agent, output):
        if verbose:
            print(f"\n{'='*60}\n[{agent.upper()}]\n{'='*60}")
            print(output)
        pipeline_context[agent] = output

    print(f"\n LIBERA IL TUO MOVIMENTO — Pipeline avviata")
    print(f"Input: {user_input}\n")

    out1 = call_agent("agent1_architect", user_input)
    log("agent1_architect", out1)

    out2 = call_agent("agent2_structural", user_input, {"wireframe": out1})
    log("agent2_structural", out2)

    out3 = call_agent("agent3_pilot", user_input, {"wireframe": out1, "structural": out2})
    log("agent3_pilot", out3)

    out4 = call_agent("agent4_dimensioner", user_input, {
        "wireframe": out1, "structural": out2, "pilot_feedback": out3
    })
    log("agent4_dimensioner", out4)

    out4b = call_agent("agent4b_components", user_input, {"wireframe": out1, "sections": out4})
    log("agent4b_components", out4b)

    out5 = call_agent("agent5_joint_generator", user_input, {
        "wireframe": out1, "structural": out2, "sections": out4, "clearances": out4b
    })
    log("agent5_joint_generator", out5)

    out6 = call_agent("agent6_visual_reviewer", user_input, {
        "joint_geometry": out5, "pilot_feedback": out3
    })
    log("agent6_visual_reviewer", out6)

    out7 = call_agent("agent7_gcode", user_input, {
        "joint_geometry": out5, "visual_approval": out6
    })
    log("agent7_gcode", out7)

    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    gcode_path = output_dir / "joint_output.gcode"

    with open(gcode_path, "w") as f:
        f.write(extract_gcode(out7))

    print(f"\n G-code salvato: {gcode_path}")
    print(f" Apri con OrcaSlicer: File → Import → Import G-code per verifica visiva")
    return pipeline_context


def extract_gcode(text: str) -> str:
    lines = text.split('\n')
    gcode_lines = [l for l in lines if l.strip().startswith((';', 'G', 'M', 'T', 'F', 'E', 'X', 'Y', 'Z'))]
    return '\n'.join(gcode_lines) if gcode_lines else text


if __name__ == "__main__":
    import sys
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Descrivi il giunto: ")
    run_pipeline(user_input)

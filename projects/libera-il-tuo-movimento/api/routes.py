"""
API routes — REST + WebSocket
"""

import json
import asyncio
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from .pipeline_runner import run_pipeline_async, get_training_stats

router = APIRouter()

OUTPUT_DIR = Path(__file__).parent.parent / "output"
TRAINING_DIR = Path(__file__).parent.parent / "training" / "data"


class PipelineRequest(BaseModel):
    prompt: str


@router.post("/pipeline")
async def start_pipeline(req: PipelineRequest):
    """Lancia la pipeline (sincrono, per test)."""
    result = await run_pipeline_async(req.prompt)
    return result


@router.websocket("/pipeline/ws")
async def pipeline_ws(websocket: WebSocket):
    """WebSocket per streaming live della pipeline."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        prompt = data.get("prompt", "")
        if not prompt:
            await websocket.send_json({"type": "error", "message": "Prompt vuoto"})
            await websocket.close()
            return

        await run_pipeline_async(prompt, ws=websocket)
        await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@router.get("/output/gcode")
async def get_gcode():
    """Scarica l'ultimo G-code generato."""
    gcode_path = OUTPUT_DIR / "joint_output.gcode"
    if not gcode_path.exists():
        raise HTTPException(404, "Nessun G-code generato")
    return {"gcode": gcode_path.read_text()}


@router.get("/output/agents")
async def get_agent_outputs():
    """Tutti gli output degli agenti dell'ultimo run."""
    outputs = {}
    for f in OUTPUT_DIR.glob("agent*.json"):
        outputs[f.stem] = json.loads(f.read_text())
    return outputs


@router.get("/training/stats")
async def training_stats():
    """Statistiche del dataset di training."""
    return get_training_stats()


@router.get("/health")
async def health():
    return {"status": "ok", "project": "libera-il-tuo-movimento"}

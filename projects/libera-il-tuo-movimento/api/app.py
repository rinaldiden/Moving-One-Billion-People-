"""
LIBERA IL TUO MOVIMENTO — API Server
FastAPI + WebSocket per streaming della pipeline multi-agente.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from .routes import router

app = FastAPI(
    title="Libera il tuo Movimento",
    description="Pipeline multi-agente per giunti organici — dal linguaggio naturale al G-code",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Serve frontend
WEB_DIR = Path(__file__).parent.parent / "web"
app.mount("/css", StaticFiles(directory=WEB_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=WEB_DIR / "js"), name="js")


@app.get("/")
async def serve_index():
    return FileResponse(WEB_DIR / "index.html")


def main():
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()

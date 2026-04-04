"""FastAPI backend for AI text detector and paraphraser."""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from app.detector import detect
from app.paraphraser import paraphrase
from app.llm import get_client

app = FastAPI(title="ReWrite — AI Detector & Paraphraser")


# --- Request / Response models ---

class DetectRequest(BaseModel):
    text: str


class ParaphraseRequest(BaseModel):
    text: str
    intensity: str = "medium"  # light | medium | aggressive
    model: str = "openai"


# --- API routes ---

@app.post("/api/detect")
def api_detect(req: DetectRequest):
    if not req.text.strip():
        raise HTTPException(400, "Text is empty")
    if len(req.text) < 50:
        raise HTTPException(400, "Text too short — need at least 50 characters for meaningful analysis")
    return detect(req.text)


@app.post("/api/paraphrase")
def api_paraphrase(req: ParaphraseRequest):
    if not req.text.strip():
        raise HTTPException(400, "Text is empty")
    if req.intensity not in ("light", "medium", "aggressive"):
        raise HTTPException(400, "Intensity must be light, medium, or aggressive")
    return paraphrase(req.text, intensity=req.intensity, model=req.model)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- Serve frontend ---

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

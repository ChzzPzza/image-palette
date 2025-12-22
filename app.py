# app.py
from __future__ import annotations

from fastapi import FastAPI, File, UploadFile, Body
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from palette.extract import extract_palette
from palette.region import Rect, crop_region

app = FastAPI(title="Image → Harmonized Palette")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Simple in-memory storage for the latest uploaded image bytes.
# Good enough for local use; replace with session storage later if needed.
LATEST_IMAGE: bytes | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/palette")
async def api_palette(file: UploadFile = File(...)) -> dict:
    global LATEST_IMAGE
    data = await file.read()
    LATEST_IMAGE = data

    return extract_palette(
        image_bytes=data,
        max_k=10,
        support_max=4,
        merge_delta_e=0.06,
        distinct_min_delta_e=0.09,
        stevens_exp=0.33,
        sample_max=60000,
        downscale_max=512,
    )


@app.post("/api/palette/region")
async def api_palette_region(payload: dict = Body(...)) -> dict:
    """
    payload:
      {
        "x": <int>, "y": <int>, "w": <int>, "h": <int>
      }
    Rectangle coordinates are in *original image pixels*.
    """
    if LATEST_IMAGE is None:
        return {"error": "No image uploaded yet."}

    try:
        rect = Rect(
            x=int(payload["x"]),
            y=int(payload["y"]),
            w=int(payload["w"]),
            h=int(payload["h"]),
        )
        cropped = crop_region(LATEST_IMAGE, rect)
    except Exception as e:
        return {"error": f"Invalid region: {e}"}

    return extract_palette(
        image_bytes=cropped,
        max_k=10,
        support_max=4,
        merge_delta_e=0.06,
        distinct_min_delta_e=0.09,
        stevens_exp=0.33,
        sample_max=60000,
        downscale_max=512,
    )


# Optional: stop IDE probes from 404'ing
@app.get("/v1/models")
def v1_models() -> dict:
    return {"object": "list", "data": []}

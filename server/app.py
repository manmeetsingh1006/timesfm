from __future__ import annotations

import os
from typing import List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File
from pydantic import BaseModel
import numpy as np

import timesfm

app = FastAPI(title="TimesFM Forecast API")

# Enable CORS for local frontend development
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model holder
MODEL = None
API_KEY = os.environ.get("TIMESFM_API_KEY")


def validate_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    if API_KEY is None:
        return None

    key = x_api_key
    if not key and authorization:
        if authorization.startswith("Bearer "):
            key = authorization.split("Bearer ", 1)[1].strip()
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


class ForecastRequest(BaseModel):
    horizon: int
    series: List[float]


@app.on_event("startup")
def load_model():
    global MODEL
    if MODEL is None:
        # Load pretrained model (may download weights on first run).
        MODEL = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
            "google/timesfm-2.5-200m-pytorch",
            local_files_only=False,
        )
        MODEL.compile(
            timesfm.ForecastConfig(
                max_context=1024,
                max_horizon=256,
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                force_flip_invariance=True,
                infer_is_positive=True,
                fix_quantile_crossing=True,
            )
        )


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": MODEL is not None}


@app.post("/forecast")
def forecast(req: ForecastRequest, api_key: Optional[str] = Depends(validate_api_key)):
    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if req.horizon <= 0:
        raise HTTPException(status_code=400, detail="Invalid horizon")
    if len(req.series) == 0:
        raise HTTPException(status_code=400, detail="Series must contain at least one value")
    arr = np.array(req.series, dtype=np.float32)
    point, quantiles = MODEL.forecast(req.horizon, [arr])
    return {
        "point": point[0].tolist(),
        "quantiles": quantiles[0].tolist(),
    }


@app.post("/forecast_csv")
async def forecast_csv(
    file: UploadFile = File(...),
    horizon: int = 12,
    api_key: Optional[str] = Depends(validate_api_key),
):
    content = await file.read()
    import io
    import pandas as pd

    try:
        df = pd.read_csv(io.BytesIO(content), parse_dates=[0])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to parse CSV: {exc}")

    if df.shape[1] < 2:
        raise HTTPException(status_code=400, detail="CSV must have at least 2 columns")
    series = df.iloc[:, 1].dropna().astype(float).to_numpy()
    if series.size == 0:
        raise HTTPException(status_code=400, detail="CSV file contains no numeric series values")
    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    point, quantiles = MODEL.forecast(horizon, [series])
    return {"point": point[0].tolist(), "quantiles": quantiles[0].tolist()}

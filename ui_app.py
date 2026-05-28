#!/usr/bin/env python3
"""
Simple TimesFM Streamlit UI (lightweight prototype).

- If `streamlit` is available this file serves the web UI.
- Otherwise running this file as a script runs a quick smoke test that
  loads the pretrained model and prints a sample forecast.

Run UI:
  PYTHONPATH=src streamlit run ui_app.py

Run smoke test:
  PYTHONPATH=src .venv/bin/python ui_app.py
"""

from __future__ import annotations

import sys
import json
import numpy as np
from pathlib import Path

try:
  import streamlit as st
  import plotly.graph_objects as go
  HAVE_STREAMLIT = True
except Exception:
  HAVE_STREAMLIT = False

import timesfm


def load_model():
  # Load pretrained TimesFM model (may download weights on first run).
  model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
      "google/timesfm-2.5-200m-pytorch",
      local_files_only=False,
  )
  model.compile(
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
  return model


def run_smoke_test():
  print("Running smoke test: load pretrained model and forecast a dummy series")
  m = load_model()
  a = np.linspace(0, 1, 100)
  b = np.sin(np.linspace(0, 20, 67))
  p, q = m.forecast(12, [a, b])
  print("point forecast shape", p.shape)
  print("quantile forecast shape", q.shape)
  print("sample point forecast:", p[0, :5].tolist())


if HAVE_STREAMLIT:
  st.set_page_config(page_title="TimesFM Forecast UI", layout="wide")
  st.title("TimesFM Forecast UI (Prototype)")

  with st.sidebar:
    uploaded = st.file_uploader("Upload CSV with date,value columns", type="csv")
    horizon = st.number_input("Horizon", min_value=1, max_value=1024, value=12)
    run_button = st.button("Run forecast")

  @st.cache_resource
  def cached_model():
    return load_model()

  if uploaded is not None:
    import pandas as pd

    df = pd.read_csv(uploaded, parse_dates=[0])
    st.write(df.tail())
    series = df.iloc[:, 1].dropna().astype(float).to_numpy()

    if run_button:
      with st.spinner("Running forecast..."):
        model = cached_model()
        point, quantiles = model.forecast(horizon, [series])
        point = np.asarray(point)
        q = np.asarray(quantiles)[0]
        x = list(range(1, horizon + 1))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=point[0], name="Point"))
        fig.add_trace(go.Scatter(x=x, y=q[:, 1], name="Q20", line=dict(dash="dash")))
        fig.add_trace(go.Scatter(x=x, y=q[:, 8], name="Q80", line=dict(dash="dash")))
        st.plotly_chart(fig, use_container_width=True)
        st.download_button("Download JSON", data=json.dumps({"point": point[0].tolist(), "quantiles": q.tolist()}), file_name="forecast.json")


if __name__ == "__main__":
  if HAVE_STREAMLIT:
    print("Streamlit is installed — run with: PYTHONPATH=src streamlit run ui_app.py")
  else:
    run_smoke_test()

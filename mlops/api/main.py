"""
FastAPI service exposing the 3 champion models from the MLflow Model Registry.

Run locally with:
    uvicorn mlops.api.main:app --reload --port 8000

All three models are loaded once at startup via the `@champion` alias --
retraining and promoting a new champion never requires touching this file.
"""

from contextlib import asynccontextmanager
from typing import Optional
import os

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException
from mlflow import MlflowClient
from pydantic import BaseModel

# Defaults to localhost for running the API directly on your Mac.
# Inside Docker Compose, this gets set to http://mlflow:5000 (the service name).
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5002")

MODEL_NAMES = {
    "delivery_delay": "delivery_delay_classifier",
    "review_negative": "review_negative_classifier",
    "demand_forecast": "weekly_demand_forecaster",
}

# Populated at startup; each entry holds {"model": ..., "columns": [...]}
models: dict = {}


def load_champion(name: str) -> dict:
    """Load a model's champion version plus its feature_columns.json artifact."""
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    version = client.get_model_version_by_alias(name, "champion")
    model = mlflow.sklearn.load_model(f"models:/{name}@champion")
    columns = mlflow.artifacts.load_dict(f"runs:/{version.run_id}/feature_columns.json")["columns"]
    return {"model": model, "columns": columns, "version": version.version}


@asynccontextmanager
async def lifespan(app: FastAPI):
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    for key, name in MODEL_NAMES.items():
        try:
            models[key] = load_champion(name)
            print(f"Loaded {name} -- champion v{models[key]['version']}")
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not load {name}: {exc}")
    yield
    models.clear()


app = FastAPI(title="Olist ML Serving API", lifespan=lifespan)


def align_features(raw: dict, categorical_cols: list[str], expected_columns: list[str]) -> pd.DataFrame:
    """
    Reconstruct the exact one-hot-encoded row the model was trained on.
    `raw` has plain values (e.g. customer_state="SP"); this turns that into
    the same dummy-column layout produced by pd.get_dummies() at train time.
    """
    row = {col: 0 for col in expected_columns}

    for key, value in raw.items():
        if key in categorical_cols:
            dummy_col = f"{key}_{value}"
            if dummy_col in row:
                row[dummy_col] = 1
            # if the category wasn't in the training set's dummy columns,
            # it's silently treated as the reference (dropped) category --
            # matches pd.get_dummies(..., drop_first=True) behavior.
        elif key in row:
            row[key] = value

    return pd.DataFrame([row], columns=expected_columns)


# ---------------------------------------------------------------------------
# Delivery delay
# ---------------------------------------------------------------------------


class DeliveryDelayRequest(BaseModel):
    customer_state: str
    seller_state: str
    product_category_name_en: str
    month: int
    day_of_week: int
    is_weekend: bool
    seller_customer_distance_km: float
    order_price: float
    order_freight_value: float
    item_count: int
    order_total_payment_value: float
    payment_methods_count: int
    max_installments: int


@app.post("/predict/delivery-delay")
def predict_delivery_delay(payload: DeliveryDelayRequest):
    if "delivery_delay" not in models:
        raise HTTPException(503, "Model not loaded")

    bundle = models["delivery_delay"]
    X = align_features(
        payload.model_dump(),
        categorical_cols=["customer_state", "seller_state", "product_category_name_en"],
        expected_columns=bundle["columns"],
    )
    proba = bundle["model"].predict_proba(X)[0, 1]
    return {
        "model_version": bundle["version"],
        "is_late_probability": float(proba),
        "is_late_prediction": bool(proba >= 0.5),
    }


# ---------------------------------------------------------------------------
# Negative review
# ---------------------------------------------------------------------------


class ReviewNegativeRequest(BaseModel):
    customer_state: str
    seller_state: str
    product_category_name_en: str
    month: int
    day_of_week: int
    is_weekend: bool
    seller_customer_distance_km: float
    order_price: float
    order_freight_value: float
    item_count: int
    order_total_payment_value: float
    payment_methods_count: int
    max_installments: int
    delivery_days: float
    delivery_delta_days: float
    was_late: int


@app.post("/predict/review-negative")
def predict_review_negative(payload: ReviewNegativeRequest):
    if "review_negative" not in models:
        raise HTTPException(503, "Model not loaded")

    bundle = models["review_negative"]
    X = align_features(
        payload.model_dump(),
        categorical_cols=["customer_state", "seller_state", "product_category_name_en"],
        expected_columns=bundle["columns"],
    )
    proba = bundle["model"].predict_proba(X)[0, 1]
    return {
        "model_version": bundle["version"],
        "negative_review_probability": float(proba),
        "negative_review_prediction": bool(proba >= 0.5),
    }


# ---------------------------------------------------------------------------
# Weekly demand forecast
# ---------------------------------------------------------------------------


class DemandForecastRequest(BaseModel):
    product_category_name_en: str
    lag_1: float
    lag_2: float
    lag_3: float
    lag_4: float
    rolling_mean_4: float
    month: int
    week_of_year: int


@app.post("/predict/demand-forecast")
def predict_demand_forecast(payload: DemandForecastRequest):
    if "demand_forecast" not in models:
        raise HTTPException(503, "Model not loaded")

    bundle = models["demand_forecast"]
    X = align_features(
        payload.model_dump(),
        categorical_cols=["product_category_name_en"],
        expected_columns=bundle["columns"],
    )
    prediction = max(0.0, float(bundle["model"].predict(X)[0]))
    return {
        "model_version": bundle["version"],
        "predicted_items_sold": prediction,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": {key: bundle["version"] for key, bundle in models.items()},
    }
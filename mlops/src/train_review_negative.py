"""
Train a negative-review classifier from the OLAP feature table
(analytics.ml_review_features) and log everything to MLflow.

Usage:
    python mlops/src/train_review_negative.py                        # uses .env (local Postgres)
    python mlops/src/train_review_negative.py --env-file .env.supabase   # trains from Supabase
"""

import argparse
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import pandas as pd
from dotenv import load_dotenv
from mlflow import MlflowClient
from mlflow_utils import promote_if_better
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MLFLOW_TRACKING_URI = "http://localhost:5002"
EXPERIMENT_NAME = "review_negative_classification"

CATEGORICAL_COLS = ["customer_state", "seller_state", "product_category_name_en"]
NUMERIC_COLS = [
    "month",
    "day_of_week",
    "is_weekend",
    "seller_customer_distance_km",
    "order_price",
    "order_freight_value",
    "item_count",
    "order_total_payment_value",
    "payment_methods_count",
    "max_installments",
    "delivery_days",
    "delivery_delta_days",
    "was_late",
]
TARGET_COL = "is_negative_review"


def load_data(env_file: str) -> pd.DataFrame:
    load_dotenv(PROJECT_ROOT / env_file, override=True)

    db_host = os.environ.get("POSTGRES_HOST", "localhost")
    sslmode = os.environ.get("POSTGRES_SSLMODE")

    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=db_host,
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
        query={"sslmode": sslmode} if sslmode else {},
    )
    engine = create_engine(url)

    print(f"Loading features from {db_host} ...")
    df = pd.read_sql("SELECT * FROM analytics.ml_review_features", engine)
    print(f"Loaded {len(df):,} rows")
    return df


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    before = len(df)
    df = df.dropna(subset=NUMERIC_COLS + CATEGORICAL_COLS)
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped:,} rows with missing values ({dropped / before:.1%})")

    X = pd.get_dummies(df[CATEGORICAL_COLS + NUMERIC_COLS], columns=CATEGORICAL_COLS, drop_first=True)
    y = df[TARGET_COL]
    return X, y


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    df = load_data(args.env_file)
    X, y = prepare_features(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    params = {
        "n_estimators": 200,
        "max_depth": 12,
        "min_samples_leaf": 5,
        "class_weight": "balanced",
        "random_state": 42,
    }

    with mlflow.start_run(run_name="random_forest_baseline"):
        mlflow.log_params(params)
        mlflow.log_dict({"columns": list(X.columns)}, "feature_columns.json")
        mlflow.log_param("env_file", args.env_file)
        mlflow.log_param("n_features", X.shape[1])
        mlflow.log_param("train_rows", len(X_train))
        mlflow.log_param("test_rows", len(X_test))

        model = RandomForestClassifier(**params)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred),
            "recall": recall_score(y_test, y_pred),
            "f1": f1_score(y_test, y_pred),
            "roc_auc": roc_auc_score(y_test, y_proba),
        }
        mlflow.log_metrics(metrics)

        print("\nTest set metrics:")
        for name, value in metrics.items():
            print(f"  {name:>10}: {value:.4f}")

        fig, ax = plt.subplots(figsize=(5, 5))
        ConfusionMatrixDisplay.from_predictions(y_test, y_pred, ax=ax, cmap="Blues")
        ax.set_title("Negative review -- confusion matrix")
        fig.tight_layout()
        cm_path = "/tmp/review_confusion_matrix.png"
        fig.savefig(cm_path)
        mlflow.log_artifact(cm_path)

        importances = pd.Series(model.feature_importances_, index=X.columns).sort_values()
        fig2, ax2 = plt.subplots(figsize=(6, 8))
        importances.tail(15).plot.barh(ax=ax2)
        ax2.set_title("Top 15 feature importances")
        fig2.tight_layout()
        fi_path = "/tmp/review_feature_importances.png"
        fig2.savefig(fi_path)
        mlflow.log_artifact(fi_path)

        model_info = mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name="review_negative_classifier",
        )

        client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
        promote_if_better(
            client=client,
            model_name="review_negative_classifier",
            new_version=model_info.registered_model_version,
            new_metric_value=metrics["roc_auc"],
            metric_key="roc_auc",
            higher_is_better=True,
        )

        print(f"\nRun logged to MLflow at {MLFLOW_TRACKING_URI}")


if __name__ == "__main__":
    main()
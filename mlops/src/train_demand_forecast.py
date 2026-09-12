"""
Train a weekly demand forecasting model from the OLAP feature table
(analytics.ml_weekly_demand_features) and log everything to MLflow.

Approach: frame forecasting as supervised regression using lag features
(items sold 1/2/3/4 weeks ago + a rolling mean) instead of a dedicated
time-series library -- keeps the same sklearn + MLflow stack as the other
two models in this project.

Usage:
    python mlops/src/train_demand_forecast.py                        # uses .env (local Postgres)
    python mlops/src/train_demand_forecast.py --env-file .env.supabase   # trains from Supabase
"""

import argparse
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from mlflow import MlflowClient
from mlflow_utils import promote_if_better
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MLFLOW_TRACKING_URI = "http://localhost:5002"
EXPERIMENT_NAME = "weekly_demand_forecast"

N_LAGS = 4
MIN_TOTAL_ITEMS = 200  # drop categories too sparse to model meaningfully
TEST_WEEKS = 8  # last 8 weeks held out as the test set, chronologically


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
    df = pd.read_sql("SELECT * FROM analytics.ml_weekly_demand_features", engine)
    df["week_start"] = pd.to_datetime(df["week_start"])
    print(f"Loaded {len(df):,} rows")
    return df


def build_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    # Keep only categories with enough volume to model meaningfully
    totals = df.groupby("product_category_name_en")["items_sold"].sum()
    keep_categories = totals[totals >= MIN_TOTAL_ITEMS].index
    df = df[df["product_category_name_en"].isin(keep_categories)].copy()
    print(f"Keeping {len(keep_categories)} categories with >= {MIN_TOTAL_ITEMS} total items sold")

    # Fill gaps: not every category sells something every week. Reindex each
    # category's series to a continuous weekly range, filling missing weeks
    # with 0 -- otherwise lag features would silently skip missing weeks.
    all_weeks = pd.date_range(df["week_start"].min(), df["week_start"].max(), freq="W-MON")
    filled = []
    for category, group in df.groupby("product_category_name_en"):
        group = group.set_index("week_start").reindex(all_weeks, fill_value=0)
        group["product_category_name_en"] = category
        group.index.name = "week_start"
        filled.append(group.reset_index())
    df = pd.concat(filled, ignore_index=True)

    df = df.sort_values(["product_category_name_en", "week_start"])
    for lag in range(1, N_LAGS + 1):
        df[f"lag_{lag}"] = df.groupby("product_category_name_en")["items_sold"].shift(lag)
    df["rolling_mean_4"] = (
        df.groupby("product_category_name_en")["items_sold"]
        .shift(1)
        .rolling(4)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["month"] = df["week_start"].dt.month
    df["week_of_year"] = df["week_start"].dt.isocalendar().week.astype(int)

    # Drop the first N_LAGS weeks of each category -- not enough history yet
    df = df.dropna(subset=[f"lag_{lag}" for lag in range(1, N_LAGS + 1)] + ["rolling_mean_4"])
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    df = load_data(args.env_file)
    df = build_lag_features(df)

    feature_cols = [f"lag_{lag}" for lag in range(1, N_LAGS + 1)] + [
        "rolling_mean_4",
        "month",
        "week_of_year",
    ]
    categorical_cols = ["product_category_name_en"]
    target_col = "items_sold"

    X = pd.get_dummies(df[feature_cols + categorical_cols], columns=categorical_cols, drop_first=True)
    y = df[target_col]

    # Chronological split: last TEST_WEEKS weeks are the test set.
    cutoff_date = df["week_start"].max() - pd.Timedelta(weeks=TEST_WEEKS)
    train_mask = df["week_start"] <= cutoff_date
    X_train, X_test = X[train_mask], X[~train_mask]
    y_train, y_test = y[train_mask], y[~train_mask]

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    params = {
        "n_estimators": 300,
        "max_depth": 4,
        "learning_rate": 0.05,
        "random_state": 42,
    }

    with mlflow.start_run(run_name="gradient_boosting_baseline"):
        mlflow.log_params(params)
        mlflow.log_dict({"columns": list(X.columns)}, "feature_columns.json")
        mlflow.log_param("env_file", args.env_file)
        mlflow.log_param("n_lags", N_LAGS)
        mlflow.log_param("test_weeks", TEST_WEEKS)
        mlflow.log_param("n_categories", df["product_category_name_en"].nunique())
        mlflow.log_param("train_rows", len(X_train))
        mlflow.log_param("test_rows", len(X_test))

        model = GradientBoostingRegressor(**params)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_pred = np.clip(y_pred, 0, None)  # demand can't be negative

        metrics = {
            "mae": mean_absolute_error(y_test, y_pred),
            "rmse": mean_squared_error(y_test, y_pred) ** 0.5,
            # WAPE (Weighted Absolute Percentage Error) = sum of absolute errors
            # divided by sum of actuals. Unlike MAPE, it doesn't explode on
            # individual near-zero-demand weeks -- the standard metric for
            # intermittent/low-volume demand forecasting.
            "wape": float(np.sum(np.abs(y_test - y_pred)) / np.sum(y_test)),
        }
        mlflow.log_metrics(metrics)

        print("\nTest set metrics:")
        for name, value in metrics.items():
            print(f"  {name:>6}: {value:.4f}")
        print(f"  (wape as %: {metrics['wape'] * 100:.1f}%)")

        # Actual vs predicted for the single highest-volume category, as a sanity check plot
        top_category = df.groupby("product_category_name_en")["items_sold"].sum().idxmax()
        mask = df.loc[~train_mask, "product_category_name_en"] == top_category
        plot_df = df.loc[~train_mask][mask].copy()
        plot_df["predicted"] = y_pred[mask.values]

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(plot_df["week_start"], plot_df["items_sold"], label="actual", marker="o")
        ax.plot(plot_df["week_start"], plot_df["predicted"], label="predicted", marker="o")
        ax.set_title(f"Actual vs predicted weekly demand -- {top_category}")
        ax.legend()
        fig.autofmt_xdate()
        fig.tight_layout()
        plot_path = "/tmp/demand_forecast_actual_vs_predicted.png"
        fig.savefig(plot_path)
        mlflow.log_artifact(plot_path)

        importances = pd.Series(model.feature_importances_, index=X.columns).sort_values()
        fig2, ax2 = plt.subplots(figsize=(6, 8))
        importances.tail(15).plot.barh(ax=ax2)
        ax2.set_title("Top 15 feature importances")
        fig2.tight_layout()
        fi_path = "/tmp/demand_feature_importances.png"
        fig2.savefig(fi_path)
        mlflow.log_artifact(fi_path)

        model_info = mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name="weekly_demand_forecaster",
        )

        client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
        promote_if_better(
            client=client,
            model_name="weekly_demand_forecaster",
            new_version=model_info.registered_model_version,
            new_metric_value=metrics["wape"],
            metric_key="wape",
            higher_is_better=False,  # lower WAPE is better
        )

        print(f"\nRun logged to MLflow at {MLFLOW_TRACKING_URI}")


if __name__ == "__main__":
    main()
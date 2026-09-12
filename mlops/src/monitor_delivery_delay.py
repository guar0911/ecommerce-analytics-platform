"""
Generate a drift + performance monitoring report for the delivery delay
classifier, comparing the data it was trained on (reference) against its
test set (current, standing in for "new" data since there's no live
production traffic yet).

Usage:
    python mlops/src/monitor_delivery_delay.py --env-file .env.supabase
"""

import argparse
import sys
from pathlib import Path

import mlflow
from evidently import ColumnMapping
from evidently.metric_preset import ClassificationPreset, DataDriftPreset
from evidently.report import Report

# Reuse the exact same data loading / feature prep / split used at training
# time, so "reference" here is truly the data the champion model was fit on.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_delivery_delay import (  # noqa: E402
    MLFLOW_TRACKING_URI,
    TARGET_COL,
    load_data,
    prepare_features,
)
from sklearn.model_selection import train_test_split  # noqa: E402

REPORTS_DIR = Path(__file__).resolve().parent.parent / "monitoring_reports"


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
    model = mlflow.sklearn.load_model("models:/delivery_delay_classifier@champion")

    reference = X_train.copy()
    reference[TARGET_COL] = y_train.values
    reference["prediction"] = model.predict(X_train)

    current = X_test.copy()
    current[TARGET_COL] = y_test.values
    current["prediction"] = model.predict(X_test)

    column_mapping = ColumnMapping(target=TARGET_COL, prediction="prediction")

    report = Report(
        metrics=[
            DataDriftPreset(),
            ClassificationPreset(),
        ]
    )
    report.run(
        reference_data=reference,
        current_data=current,
        column_mapping=column_mapping,
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    output_path = REPORTS_DIR / "delivery_delay_drift_report.html"
    report.save_html(str(output_path))
    print(f"Report saved to {output_path}")


if __name__ == "__main__":
    main()
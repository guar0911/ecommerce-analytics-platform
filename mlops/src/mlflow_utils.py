"""
Shared helper: compare a newly trained model version against the current
`champion` alias in the MLflow Model Registry, and promote it only if it's
actually better. This way, serving code always points to
`models:/<name>@champion` and never needs to change when you retrain --
only the alias target moves.
"""

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException


def promote_if_better(
    client: MlflowClient,
    model_name: str,
    new_version: str,
    new_metric_value: float,
    metric_key: str,
    higher_is_better: bool = True,
) -> None:
    try:
        champion = client.get_model_version_by_alias(model_name, "champion")
        champion_run = client.get_run(champion.run_id)
        champion_metric_value = champion_run.data.metrics.get(metric_key)
    except MlflowException:
        champion = None
        champion_metric_value = None

    if champion is None or champion_metric_value is None:
        should_promote = True
        reason = "no champion exists yet"
    elif higher_is_better:
        should_promote = new_metric_value > champion_metric_value
        reason = f"{new_metric_value:.4f} vs current champion {champion_metric_value:.4f}"
    else:
        should_promote = new_metric_value < champion_metric_value
        reason = f"{new_metric_value:.4f} vs current champion {champion_metric_value:.4f}"

    if should_promote:
        client.set_registered_model_alias(model_name, "champion", new_version)
        print(f"[champion] Promoted version {new_version} ({reason})")
    else:
        print(f"[champion] Kept existing champion -- new version did not improve ({reason})")
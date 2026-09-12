"""
Orchestrates the dbt star schema pipeline: dbt run, then dbt test.

Reads OLTP connection details from Airflow Variables (set once via
`airflow variables set`) instead of hardcoding credentials here.
"""

import pendulum
from airflow.decorators import dag
from airflow.models import Variable
from airflow.operators.bash import BashOperator

DBT_PROJECT_DIR = "/opt/airflow/dbt_project"

# Read once at DAG parse time. Values are set via:
#   airflow variables set oltp_postgres_host ...
DBT_ENV = {
    "POSTGRES_HOST": Variable.get("oltp_postgres_host", default_var="host.docker.internal"),
    "POSTGRES_USER": Variable.get("oltp_postgres_user"),
    "POSTGRES_PASSWORD": Variable.get("oltp_postgres_password"),
    "POSTGRES_DB": Variable.get("oltp_postgres_db"),
    "POSTGRES_PORT": Variable.get("oltp_postgres_port", default_var="5432"),
}


@dag(
    dag_id="olist_dbt_pipeline",
    description="Run and test the dbt star schema transformations for the Olist OLTP.",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["dbt", "olist"],
)
def olist_dbt_pipeline():
    # append_env=True keeps PATH (and everything else) intact -- without it,
    # passing `env` REPLACES the whole environment and the `dbt` binary
    # can't even be found.
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"dbt run --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}",
        env=DBT_ENV,
        append_env=True,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"dbt test --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}",
        env=DBT_ENV,
        append_env=True,
    )

    dbt_run >> dbt_test


olist_dbt_pipeline()
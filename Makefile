.PHONY: up down up-oltp up-etl up-mlops down-oltp down-etl down-mlops ps rag-ui dbt-run dbt-test logs-api

## Levanta las 3 piezas de infraestructura Docker (OLTP, Airflow, MLOps)
up: up-oltp up-etl up-mlops
	@echo ""
	@echo "Todo arriba:"
	@echo "  Airflow  -> http://localhost:8080  (admin/admin)"
	@echo "  MLflow   -> http://localhost:5002"
	@echo "  ML API   -> http://localhost:8000/docs"

down: down-mlops down-etl down-oltp

up-oltp:
	docker compose -f infra/docker-compose.yml --env-file .env up -d

down-oltp:
	docker compose -f infra/docker-compose.yml --env-file .env down

up-etl:
	docker compose -f etl/docker-compose.yml up -d

down-etl:
	docker compose -f etl/docker-compose.yml down

up-mlops:
	docker compose -f mlops/docker-compose.yml up -d --build

down-mlops:
	docker compose -f mlops/docker-compose.yml down

## Muestra el estado de los 3 stacks
ps:
	@echo "--- OLTP (infra/) ---"
	@docker compose -f infra/docker-compose.yml ps
	@echo "--- Airflow (etl/) ---"
	@docker compose -f etl/docker-compose.yml ps
	@echo "--- MLOps (mlops/) ---"
	@docker compose -f mlops/docker-compose.yml ps

logs-api:
	docker compose -f mlops/docker-compose.yml logs -f api

## Corre el proyecto dbt completo (requiere las variables POSTGRES_* cargadas en el shell)
dbt-run:
	cd etl/olist_analytics && dbt run

dbt-test:
	cd etl/olist_analytics && dbt test

## Levanta la interfaz de chat del sistema LLM + RAG
rag-ui:
	streamlit run llm_rag/app.py
# E-commerce Analytics Platform

An end-to-end data and AI project built around the public [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

The goal of this project was to go beyond training a model in a notebook. I wanted to build a realistic analytics platform where transactional data is loaded into a normalized database, transformed into a warehouse, used by machine learning services, and finally explored through a natural-language chat interface.

The platform covers the full lifecycle:

- A transactional PostgreSQL database (OLTP)
- An Airflow and dbt pipeline that builds an analytics warehouse (OLAP)
- Three machine learning use cases tracked and served with MLflow and FastAPI
- A text-to-SQL assistant powered by Claude and a schema-aware RAG pipeline
- Data quality checks, model monitoring, Docker-based services, and CI validation

## What can this platform answer?

Once the pipeline is running, the warehouse can be used to explore questions such as:

- Which product categories generate the most revenue?
- Which states have the longest delivery times?
- Are delivery delays associated with lower customer review scores?
- How is weekly order demand expected to evolve?
- Which orders are more likely to be delivered late?

The LLM interface allows users to ask many of these questions in plain English. It translates the question into safe, read-only SQL, runs it against the warehouse, and returns a clear response based on the result.

## Architecture

```text
Olist raw data
      │
      ▼
OLTP PostgreSQL (3NF)
      │
      ▼
Airflow + dbt
      │
      ▼
OLAP PostgreSQL / Supabase
Star schema: facts and dimensions
      │
      ├─────────────────────────────┐
      ▼                             ▼
MLOps services                  LLM + RAG assistant
MLflow + FastAPI                Claude + ChromaDB + Streamlit
```

## Project components

### 1. Transactional data layer

The project starts with a normalized PostgreSQL database based on the Olist dataset. The schema follows third normal form (3NF) and represents the operational side of the business: customers, orders, items, payments, sellers, products, reviews, and geolocation data.

The database can run locally through Docker or in Supabase for the cloud version of the project.

### 2. Analytics pipeline and data warehouse

Apache Airflow orchestrates the transformation process, while dbt manages the SQL models and tests.

The dbt project follows a layered approach:

```text
Raw sources
   ↓
Staging models
   ↓
Intermediate models
   ↓
Analytics marts
```

The final warehouse uses a star-schema design, making it easier to analyze orders, revenue, customer behavior, product performance, delivery performance, and reviews.

The project includes 49 automated dbt tests to catch issues such as null keys, invalid relationships, duplicate records, and unexpected values before they reach the reporting layer.

### 3. Machine learning and MLOps

The platform includes three machine learning use cases built from warehouse data:

| Model                      | Type                    | Business purpose                                                  |
| -------------------------- | ----------------------- | ----------------------------------------------------------------- |
| Delivery delay prediction  | Classification          | Estimate whether an order is likely to be delivered late          |
| Negative review prediction | Classification          | Identify orders with a higher risk of receiving a negative review |
| Weekly demand forecast     | Time series forecasting | Forecast order demand for future weeks                            |

Each model is trained and tracked in MLflow. Parameters, metrics, artifacts, and model versions are logged so experiments can be compared and reproduced.

The best approved version of each model is assigned the `champion` alias in the MLflow Model Registry. The FastAPI service loads models through this alias, which means a newer model can be promoted without changing the serving code.

The project also includes Evidently AI checks to monitor data drift and model performance over time.

### 4. Natural-language analytics with LLM + RAG

The LLM component lets users query the warehouse without manually writing SQL.

It uses:

- Anthropic Claude for language understanding and SQL generation
- ChromaDB for schema and documentation retrieval
- `sentence-transformers` for embeddings
- A read-only PostgreSQL role to keep database access limited
- Streamlit for the chat interface

The RAG pipeline indexes the warehouse schema, table descriptions, columns, relationships, and example business definitions. When a user asks a question, the system retrieves this context and sends it to the LLM before generating SQL.

For example:

```text
Which product categories had the highest revenue in 2018?
```

The assistant identifies the relevant fact and dimension tables, generates a read-only query, executes it, and explains the result in natural language.

## Technology stack

| Layer                  | Technologies                                          |
| ---------------------- | ----------------------------------------------------- |
| Transactional database | PostgreSQL 16, Supabase                               |
| Orchestration          | Apache Airflow 2.10                                   |
| Transformations        | dbt 1.12                                              |
| Machine learning       | scikit-learn                                          |
| Experiment tracking    | MLflow 3.11                                           |
| Model serving          | FastAPI, Docker                                       |
| LLM and RAG            | Anthropic Claude API, ChromaDB, sentence-transformers |
| Chat interface         | Streamlit                                             |
| Monitoring             | Evidently AI                                          |
| CI/CD                  | GitHub Actions                                        |

## Repository structure

```text
.
├── oltp/                   # 3NF schema and scripts to load Olist data
├── infra/                  # Local PostgreSQL Docker setup
├── etl/
│   ├── dags/               # Airflow DAGs
│   ├── docker-compose.yml  # Airflow services
│   └── olist_analytics/    # dbt project: staging, intermediate, marts
├── mlops/
│   ├── src/                # Training, evaluation, and drift-monitoring scripts
│   ├── api/                # FastAPI application serving champion models
│   └── docker-compose.yml  # MLflow and model-serving services
├── llm_rag/
│   ├── sql/                # Read-only database role and permissions
│   ├── src/                # Schema catalog, embeddings, retrieval, text-to-SQL
│   └── app.py              # Streamlit chat application
├── .github/workflows/      # CI checks
├── Makefile                # Common project commands
└── requirements.txt
```

## Getting started

### Prerequisites

Before running the project, make sure you have:

- Docker Desktop
- Python 3.10 or newer
- A Supabase account, if you want to use the cloud database version
- An Anthropic API key for the LLM assistant

### 1. Configure environment variables

Create the required environment files:

```bash
cp .env.example .env
cp .env.supabase.example .env.supabase
cp etl/.env.example etl/.env
cp llm_rag/.env.example llm_rag/.env
```

Then update each file with your own credentials and connection details.

The `llm_rag/.env` file requires the Anthropic API key and the credentials for the read-only database role.

### 2. Create a Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with:

```bash
.venv\Scripts\activate
```

### 3. Start the infrastructure

Use the Makefile to start the local services:

```bash
make up
```

This starts the PostgreSQL, Airflow, MLflow, and related Docker services configured for the project.

### 4. Load the transactional data and build the warehouse

Load the Olist dataset into the normalized PostgreSQL database:

```bash
python oltp/load_data.py
```

Then run the dbt transformations and tests:

```bash
make dbt-run
make dbt-test
```

At this point, the warehouse tables should be available for analytics, ML features, and the RAG system.

### 5. Train and register the models

Run the training scripts for each ML use case:

```bash
python mlops/src/train_delivery_delay.py
python mlops/src/train_review_negative.py
python mlops/src/train_demand_forecast.py
```

Each run logs its parameters, metrics, and model artifacts to MLflow. After evaluating a run, the selected model can be registered and promoted as the `champion` version.

### 6. Build the schema catalog and start the chat interface

First, generate the warehouse documentation and vector store:

```bash
python llm_rag/src/build_schema_catalog.py
python llm_rag/src/build_vector_store.py
```

Then launch the Streamlit application:

```bash
make rag-ui
```

Open the URL shown in the terminal to start asking questions about the warehouse.

## Technical decisions and lessons learned

### Why PostgreSQL instead of BigQuery?

BigQuery was considered for the warehouse layer. However, I decided to keep PostgreSQL and Supabase during the first version of the project because it reduced infrastructure complexity and allowed the same SQL engine to be used across the transactional and analytics layers.

This also made it easier to focus on the data modeling, dbt pipeline, ML services, and LLM integration before introducing another warehouse-specific dialect.

### Why use the complete schema context for RAG?

The star schema currently contains a small number of core analytics tables. Because the schema is compact, the assistant receives the complete relevant catalog instead of relying only on a strict top-k retrieval strategy.

This avoids cases where a necessary table, such as the orders fact table, is accidentally excluded from the LLM context. As the schema grows, retrieval can become more selective without changing the overall architecture.

### Why use a `champion` alias in MLflow?

The API does not point to a hardcoded model version. Instead, it loads the model currently assigned to the `champion` alias in MLflow.

This makes model updates safer: a newly trained version can be evaluated, registered, and promoted without editing or redeploying the application code just to update a version number.

### Production issues documented during development

This project also helped me work through practical issues that do not usually appear in a simple notebook workflow, including:

- Supabase IPv6 connectivity issues and migration to the Supavisor pooler
- MLflow DNS rebinding security changes introduced after a patched CVE
- Scikit-learn version mismatches between training and serving environments
- dbt orphaned relations created by backup models such as `__dbt_backup`

These issues reinforced the importance of reproducible environments, explicit dependencies, database permissions, and operational documentation.

## Future improvements

- Add automated model promotion rules based on validation thresholds
- Add a BI dashboard for executive-level metrics
- Add scheduled drift reports and alerts
- Introduce role-based access to the analytics interface
- Expand the RAG evaluation set with business questions and expected SQL outputs
- Move the warehouse layer to a dedicated cloud analytics engine as data volume grows

## Author

Built by **Geovanny Guareño** as a portfolio project combining data engineering, analytics engineering, MLOps, backend development, and applied LLM systems.

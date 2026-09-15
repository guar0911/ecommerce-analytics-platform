"""
Text-to-SQL RAG pipeline over the OLAP star schema.

Flow:
  question -> embed -> retrieve relevant tables from Chroma
           -> Claude generates SQL grounded in that schema
           -> SQL is validated (read-only, single statement, LIMIT enforced)
           -> executed against Postgres via the llm_readonly role
           -> Claude turns the result rows into a natural-language answer

Usage:
    python llm_rag/src/query_engine.py "¿Cuáles son las 5 categorías más vendidas?"
"""

import os
import re
import sys
from pathlib import Path

import anthropic
import chromadb
import pandas as pd
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHROMA_DIR = PROJECT_ROOT / "llm_rag" / "chroma_db"
COLLECTION_NAME = "schema_catalog"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CLAUDE_MODEL = "claude-sonnet-5"
TOP_K_TABLES = 6  # small schema (6 tables total) -- always include everything,
# no real need for selective retrieval here, and it removes the risk of a
# relevant table (like fact_orders) being left out of context.
DEFAULT_ROW_LIMIT = 200

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "grant", "revoke", "create", "exec", "copy", "call",
]

SQL_SYSTEM_PROMPT = """You are a PostgreSQL expert. Given a natural-language question \
and a description of the relevant tables (with real column names and types), \
write ONE single read-only SQL query that answers the question.

IMPORTANT business context:
- Actual sales/orders/transactions/revenue live ONLY in fact_orders (one row per
  order line item). "Most sold", "top revenue", "best selling" etc. must be
  computed from fact_orders (e.g. COUNT(*) or SUM(price) grouped by a joined
  dimension attribute), never by counting rows in a dimension table.
- Dimension tables (dim_product, dim_customer, dim_seller, dim_geography,
  dim_date) only describe catalog/reference attributes. Counting rows in a
  dimension table tells you how many distinct entities exist -- it does NOT
  represent sales, demand, or activity of any kind.
- If the question is about volume/popularity/revenue, join fact_orders to the
  relevant dimension and aggregate from fact_orders, not from the dimension alone.

Rules:
- Only use tables and columns from the schema provided below. Never invent column names.
- Only SELECT statements (CTEs with WITH are fine). Never modify data.
- Always include a LIMIT clause (unless the query is an aggregate returning one row).
- Return ONLY the raw SQL query. No markdown code fences, no explanation, no comments.

Schema:
{schema_context}
"""

ANSWER_SYSTEM_PROMPT = """You answer business questions about an e-commerce dataset, \
in Spanish, based on SQL query results. Be concise and direct -- 1-3 sentences. \
Reference actual numbers from the results. Do not mention SQL or databases in your answer."""


def extract_text(response) -> str:
    """Find the actual text block in the response, regardless of position --
    newer models can prepend a 'thinking' block before the text block."""
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    raise ValueError("No text block found in Claude's response.")


class QueryEngine:
    def __init__(self, env_file: str = ".env"):
        load_dotenv(PROJECT_ROOT / "llm_rag" / ".env", override=True)

        self.claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)

        chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = chroma_client.get_collection(COLLECTION_NAME)

        db_url = URL.create(
            "postgresql+psycopg2",
            username=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]),
            database=os.environ["POSTGRES_DB"],
            query={"sslmode": os.environ["POSTGRES_SSLMODE"]}
            if os.environ.get("POSTGRES_SSLMODE")
            else {},
        )
        self.engine = create_engine(db_url)

    # -- Step 1: retrieval -------------------------------------------------

    def retrieve_schema_context(self, question: str) -> str:
        query_embedding = self.embedder.encode([question]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding, n_results=TOP_K_TABLES
        )
        chunks = results["documents"][0]
        return "\n\n".join(chunks)

    # -- Step 2: SQL generation ---------------------------------------------

    def generate_sql(self, question: str, schema_context: str) -> str:
        response = self.claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=SQL_SYSTEM_PROMPT.format(schema_context=schema_context),
            messages=[{"role": "user", "content": question}],
        )
        sql = extract_text(response)
        # Strip markdown fences in case the model adds them despite instructions
        sql = re.sub(r"^```sql\s*|```$", "", sql, flags=re.MULTILINE).strip()
        return sql

    # -- Step 3: safety validation -------------------------------------------

    def validate_sql(self, sql: str) -> str:
        normalized = sql.strip().rstrip(";")
        lowered = normalized.lower()

        if not (lowered.startswith("select") or lowered.startswith("with")):
            raise ValueError("Generated query is not a SELECT/WITH statement -- rejected.")

        if ";" in normalized:
            raise ValueError("Multiple statements detected -- rejected.")

        for keyword in FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{keyword}\b", lowered):
                raise ValueError(f"Forbidden keyword '{keyword}' detected -- rejected.")

        if "limit" not in lowered:
            normalized += f" LIMIT {DEFAULT_ROW_LIMIT}"

        return normalized

    # -- Step 4: execution ----------------------------------------------------

    def execute_sql(self, sql: str) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    # -- Step 5: natural-language answer --------------------------------------

    def generate_answer(self, question: str, df: pd.DataFrame) -> str:
        results_text = df.head(20).to_string(index=False)
        response = self.claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=ANSWER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nQuery results:\n{results_text}",
                }
            ],
        )
        return extract_text(response)

    # -- Orchestration ---------------------------------------------------------

    def ask(self, question: str) -> dict:
        schema_context = self.retrieve_schema_context(question)
        raw_sql = self.generate_sql(question, schema_context)
        safe_sql = self.validate_sql(raw_sql)
        df = self.execute_sql(safe_sql)
        answer = self.generate_answer(question, df)
        return {"question": question, "sql": safe_sql, "results": df, "answer": answer}


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "¿Cuáles son las 5 categorías más vendidas?"
    engine = QueryEngine()
    result = engine.ask(question)

    print(f"\nPregunta: {result['question']}")
    print(f"\nSQL generado:\n{result['sql']}")
    print(f"\nResultados ({len(result['results'])} filas):")
    print(result["results"].head(10).to_string(index=False))
    print(f"\nRespuesta: {result['answer']}")
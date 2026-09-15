"""
Build a schema catalog for the RAG system, combining:
- manifest.json: column/table descriptions written in schema.yml
- catalog.json: the REAL list of columns and their types, from introspecting
  the actual database (manifest.json only lists columns you explicitly
  documented, which is often a subset of the real columns).

Only dim_* and fact_* models under models/marts/ are included -- the
ml_*_features tables are internal MLOps artifacts, not meant for the
business Q&A chat.

Usage:
    cd etl/olist_analytics && dbt docs generate   # regenerate if models changed
    python llm_rag/src/build_schema_catalog.py
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_DIR = PROJECT_ROOT / "etl" / "olist_analytics" / "target"
MANIFEST_PATH = TARGET_DIR / "manifest.json"
CATALOG_PATH = TARGET_DIR / "catalog.json"
OUTPUT_PATH = PROJECT_ROOT / "llm_rag" / "schema_catalog.json"


def build_catalog() -> list[dict]:
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    with open(CATALOG_PATH) as f:
        db_catalog = json.load(f)

    catalog = []
    for node_id, node in manifest["nodes"].items():
        if node["resource_type"] != "model":
            continue
        if "marts" not in node["fqn"]:
            continue
        # Exclude internal ML feature tables -- those are for MLOps, not
        # for the general business Q&A chat.
        if node["name"].startswith("ml_"):
            continue

        documented_columns = node.get("columns", {})  # descriptions live here
        db_node = db_catalog.get("nodes", {}).get(node_id, {})
        real_columns = db_node.get("columns", {})  # the actual columns + types

        columns = [
            {
                "name": col_name,
                "type": col_info.get("type", ""),
                "description": documented_columns.get(col_name, {}).get("description", ""),
            }
            for col_name, col_info in real_columns.items()
        ]

        catalog.append(
            {
                "table_name": node["name"],
                "schema": node["schema"],
                "description": node.get("description", ""),
                "columns": columns,
            }
        )

    return catalog


def to_text_chunk(table: dict) -> str:
    """Render one table's metadata as a text block, suitable for embedding."""
    lines = [
        f"Table: {table['schema']}.{table['table_name']}",
        f"Description: {table['description'] or '(no description)'}",
        "Columns:",
    ]
    for col in table["columns"]:
        desc = f" -- {col['description']}" if col["description"] else ""
        lines.append(f"  - {col['name']} ({col['type']}){desc}")
    return "\n".join(lines)


def main() -> None:
    for path in (MANIFEST_PATH, CATALOG_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run `dbt docs generate` inside etl/olist_analytics first."
            )

    catalog = build_catalog()
    for table in catalog:
        table["text_chunk"] = to_text_chunk(table)

    OUTPUT_PATH.write_text(json.dumps(catalog, indent=2))
    print(f"Extracted {len(catalog)} tables from marts/ -> {OUTPUT_PATH}")
    for table in catalog:
        print(f"  - {table['schema']}.{table['table_name']} ({len(table['columns'])} columns)")


if __name__ == "__main__":
    main()
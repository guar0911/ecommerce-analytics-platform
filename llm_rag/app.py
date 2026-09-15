"""
Chat UI for the text-to-SQL RAG system.

Run with:
    streamlit run llm_rag/app.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from query_engine import QueryEngine  # noqa: E402

EXAMPLE_QUESTIONS = [
    "¿Cuáles son las 5 categorías con más ventas?",
    "¿Cuál es el ingreso total por mes en 2018?",
    "¿Qué estado tiene más clientes?",
    "¿Cuál es el tiempo promedio de entrega por categoría?",
]

st.set_page_config(page_title="Pregúntale a tu Data Warehouse", page_icon="📊")
st.title("📊 Pregúntale a tu Data Warehouse")
st.caption(
    "RAG + Text-to-SQL sobre el esquema estrella de Olist (dim_customer, dim_product, "
    "dim_seller, dim_geography, dim_date, fact_orders) -- respuestas generadas por Claude."
)


@st.cache_resource
def get_engine() -> QueryEngine:
    return QueryEngine()


engine = get_engine()

with st.sidebar:
    st.subheader("Preguntas de ejemplo")
    for example in EXAMPLE_QUESTIONS:
        if st.button(example, use_container_width=True):
            st.session_state["pending_question"] = example

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "sql" in message:
            with st.expander("Ver SQL generado y resultados"):
                st.code(message["sql"], language="sql")
                st.dataframe(message["results"])

question = st.chat_input("Escribe tu pregunta sobre las ventas...")
if not question and "pending_question" in st.session_state:
    question = st.session_state.pop("pending_question")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Consultando el data warehouse..."):
            try:
                result = engine.ask(question)
                st.markdown(result["answer"])
                with st.expander("Ver SQL generado y resultados"):
                    st.code(result["sql"], language="sql")
                    st.dataframe(result["results"])
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result["answer"],
                        "sql": result["sql"],
                        "results": result["results"],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                error_msg = f"No pude responder esa pregunta: {exc}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
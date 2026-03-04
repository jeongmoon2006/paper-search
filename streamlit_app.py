import os

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Scholar Research Assistant", layout="wide")
st.title("Google Scholar Research Assistant")
st.caption("Retrieves real-time Google Scholar data and summarizes fetched papers.")

query = st.text_input("Research query", value="graph neural networks for drug discovery")
recency = st.selectbox(
    "Up-to-date filter",
    options=["any", "past_year", "past_3_years", "past_5_years"],
    index=2,
)
max_results = st.slider("Max results", min_value=3, max_value=20, value=10)
summary_mode = st.selectbox(
    "Summarization mode",
    options=["map_reduce", "single_call"],
    index=0,
    help="single_call uses one LLM request for all papers to reduce quota usage.",
)

if st.button("Search"):
    if len(query.strip()) < 3:
        st.error("Please enter at least 3 characters.")
    else:
        try:
            response = requests.post(
                f"{BACKEND_URL}/search",
                json={
                    "query": query,
                    "recency": recency,
                    "max_results": max_results,
                    "summary_mode": summary_mode,
                },
                timeout=90,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            st.error(f"Backend request failed: {exc}")
        else:
            st.subheader("Refined Query")
            st.json(data["refined_query"])

            st.subheader("Fetched Papers (Google Scholar)")
            for index, paper in enumerate(data["scholar_results"], start=1):
                st.markdown(f"**{index}. {paper['title']}**")
                if paper["link"]:
                    st.markdown(f"[Open paper]({paper['link']})")
                st.write(paper["snippet"])

            st.subheader("Per-Paper Summaries")
            for index, item in enumerate(data["paper_summaries"], start=1):
                st.markdown(f"**{index}. {item['title']}**")
                st.write(item["summary"])

            st.subheader("Synthesis")
            st.write(data["final_synthesis"])

            guardrail = data["guardrail"]
            if guardrail["hallucination_check_passed"]:
                st.success("Guardrail passed: summaries map to fetched Scholar results.")
            else:
                st.error("Guardrail failed: potential fabricated paper references detected.")
                st.json(guardrail)

# Design Doc: Google Scholar Research Assistant

## Requirements

### Product Goal
Help users discover relevant, recent academic papers from **Google Scholar only**, then provide reliable AI summaries based strictly on fetched Scholar results.

### User Stories
1. **Search papers**
   - As a researcher, I enter a natural-language query and receive a list of relevant papers from Google Scholar.
   - Acceptance criteria:
     - Results include `title`, `snippet`, and `link` from Scholar.
     - No paper is shown unless it was fetched by the Scholar tool.

2. **Filter by up-to-date (recency)**
   - As a researcher, I can request up-to-date papers (for example, past year or latest few years) so I can focus on recent work.
   - Acceptance criteria:
     - Recency preference is translated into Scholar query constraints (for example, year filters when available).
     - If strict recency yields too few results, system explains this and offers fallback widening.

3. **View summaries**
   - As a researcher, I view concise summaries of each result and a synthesized overview to decide what to read first.
   - Acceptance criteria:
     - Per-paper summaries are grounded only in each paper's fetched snippet/title metadata.
     - Final synthesis references only fetched results, with no invented titles or claims.

### Non-Functional Requirements
- Real-time Scholar fetch at request time (no stale hardcoded paper list).
- Clear provenance: every summary item must map to a fetched source link.
- Deterministic guardrail checks to block fabricated titles.

## Flow Design

### Applicable Design Pattern
1. **Agentic Workflow** for orchestration and adaptive decisions.
2. **Map-Reduce** inside summarization:
   - **Map**: summarize each fetched paper independently.
   - **Reduce**: synthesize all per-paper summaries into a ranked overview.

### Flow High-Level Design
1. **Node 1: Query Refinement Agent**
   - Optimizes user query for Google Scholar retrieval quality and recency intent.
   - Converts user intent into search-ready query + optional year constraint.

2. **Node 2: Google Scholar Search Tool Node**
   - Executes Scholar retrieval using external tool/API.
   - Returns only real Scholar records (`title`, `snippet`, `link`) and metadata.

3. **Node 3: Summary Engine (Map-Reduce)**
   - Map step: generate one grounded summary per fetched paper.
   - Reduce step: generate cross-paper synthesis and highlight top relevant items.

### Agentic Control Logic
- Agent can loop from Node 2 back to Node 1 when:
  - result count is too low,
  - recency filter is too strict,
  - query quality appears weak.
- Agent stops when minimum quality threshold is met (for example, enough relevant results).

```mermaid
flowchart TD
    UI[Frontend: React/Streamlit Input] --> BFF[Backend API: FastAPI]
    BFF --> Q[Node 1: Query Refinement Agent]
    Q --> S[Node 2: Google Scholar Search Tool]
    S -->|few/low-quality results| Q
    S --> M[Node 3: Summary Engine (Map)]
    M --> R[Node 3: Summary Engine (Reduce)]
    R --> OUT[Backend Response: papers + summaries + synthesis]
    OUT --> UI
```

## Utility Functions

1. **Call LLM** (`utils/call_llm.py`)
   - *Input*: prompt (str)
   - *Output*: response (str)
   - Used only for query refinement and summarization of fetched text.

2. **Google Scholar Search** (`utils/google_scholar_search.py`)
   - *Input*: refined_query (str), optional filters (`year_from`, `max_results`)
   - *Output*: list of dict objects:
     - `title`: str
     - `snippet`: str
     - `link`: str
   - Necessity: single source of truth for external paper retrieval.
   - Constraint: this function must return only data fetched from Scholar in real time.

## Node Design

### System Boundary Separation
1. **Frontend Layer (React or Streamlit)**
   - Collects user query and recency preference.
   - Displays fetched papers, per-paper summaries, and final synthesis.
   - Does not call Scholar directly.

2. **Backend Layer (FastAPI + Python orchestration)**
   - Runs the agentic flow (Node 1 -> Node 2 -> Node 3).
   - Enforces guardrails and schema validation.
   - Returns structured response to frontend.

3. **External Search Tool Layer (Google Scholar)**
   - Accessed only through `utils/google_scholar_search.py`.
   - Treated as authoritative source for paper metadata.

### Shared Store

```python
shared = {
    "user_input": {
        "query": "",
        "recency": "any"  # e.g., any | past_year | past_3_years
    },
    "refined_query": {
        "query_text": "",
        "year_from": None,
        "rationale": ""
    },
    "scholar_results": [
        {
            "title": "",
            "snippet": "",
            "link": ""
        }
    ],
    "paper_summaries": [
        {
            "title": "",
            "link": "",
            "summary": ""
        }
    ],
    "final_synthesis": "",
    "guardrail": {
        "hallucination_check_passed": False,
        "violations": []
    }
}
```

### Node Steps

1. **Node 1: Query Refinement (Regular Node, Agentic Decisioning)**
   - *Purpose*: optimize user query for Scholar retrieval relevance and recency.
   - *prep*: read `shared["user_input"]`.
   - *exec*: call LLM to produce refined Scholar-oriented query terms and year constraint.
   - *post*: write `shared["refined_query"]`; return action `search`.

2. **Node 2: Google Scholar Scraper/API Tool (Regular Node, External I/O)**
   - *Purpose*: fetch real Scholar results only.
   - *prep*: read `shared["refined_query"]`.
   - *exec*: call `google_scholar_search()`.
   - *post*: write `shared["scholar_results"]`; return:
     - `refine_again` if too few/poor results,
     - `summarize` if quality threshold met.

3. **Node 3: Summary Engine (Map-Reduce; Batch + Reduce Node)**
   - *Purpose*: generate paper-level summaries then cross-paper synthesis.
   - *Map prep*: read `shared["scholar_results"]`.
   - *Map exec*: summarize each paper using only `{title, snippet, link}`.
   - *Map post*: write `shared["paper_summaries"]`.
   - *Reduce prep*: read `shared["paper_summaries"]`.
   - *Reduce exec*: synthesize major themes and highlight most relevant papers.
   - *Reduce post*: write `shared["final_synthesis"]` and finalize response.

## Guardrails (Strict Anti-Hallucination)

1. The LLM must process **fetched Scholar fields only** (`title`, `snippet`, `link`).
2. The system must **never invent paper titles**, authors, links, or publication details.
3. Every summarized item must have a 1:1 mapping to an entry in `shared["scholar_results"]`.
4. If validation detects an unknown title/link in summaries, mark violation and regenerate from source data.
5. If Scholar returns no results, the system must say so explicitly instead of fabricating alternatives.

## Reliability Notes
- Prefer fail-fast behavior when Scholar tool errors or returns invalid schema.
- Log all retrieval inputs/outputs for traceability.
- Keep summarization prompts constrained with explicit source-grounding instructions.


from flow import create_research_flow


def build_shared_state(
    query: str,
    recency: str = "any",
    max_results: int = 10,
    min_results: int = 3,
    max_refinements: int = 2,
    summary_mode: str = "map_reduce",
) -> dict:
    return {
        "user_input": {
            "query": query,
            "recency": recency,
        },
        "refined_query": {
            "query_text": "",
            "year_from": None,
            "rationale": "",
        },
        "scholar_results": [],
        "paper_summaries": [],
        "final_synthesis": "",
        "guardrail": {
            "hallucination_check_passed": False,
            "violations": [],
        },
        "search_config": {
            "max_results": max_results,
            "min_results": min_results,
            "max_refinements": max_refinements,
            "summary_mode": summary_mode,
        },
        "refinement_attempts": 0,
    }


def run_research(
    query: str,
    recency: str = "any",
    max_results: int = 10,
    min_results: int = 3,
    max_refinements: int = 2,
    summary_mode: str = "map_reduce",
) -> dict:
    shared = build_shared_state(
        query=query,
        recency=recency,
        max_results=max_results,
        min_results=min_results,
        max_refinements=max_refinements,
        summary_mode=summary_mode,
    )
    research_flow = create_research_flow()
    research_flow.run(shared)
    return shared

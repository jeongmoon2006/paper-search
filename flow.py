from pocketflow import Flow

from nodes import (
    PaperSummaryMapNode,
    QueryRefinementNode,
    ScholarSearchNode,
    SynthesisNode,
)


def create_research_flow():
    query_refinement_node = QueryRefinementNode(max_retries=2)
    scholar_search_node = ScholarSearchNode(max_retries=2)
    paper_summary_map_node = PaperSummaryMapNode(max_retries=2)
    synthesis_node = SynthesisNode(max_retries=2)

    query_refinement_node - "search" >> scholar_search_node
    scholar_search_node - "refine_again" >> query_refinement_node
    scholar_search_node - "summarize" >> paper_summary_map_node
    paper_summary_map_node >> synthesis_node

    return Flow(start=query_refinement_node)


research_flow = create_research_flow()
from service import run_research


def main():
    print("Q: What paper topic do you want to retrieve from Google Scholar?")
    user_query = input("A: ").strip()
    if not user_query:
        user_query = "graph neural networks for drug discovery"

    print("\nRecency options: any | past_year | past_3_years | past_5_years")
    recency = input("Q: Recency filter? (default: past_3_years)\nA: ").strip() or "past_3_years"

    print("\nSummary mode options: map_reduce | single_call")
    summary_mode = input("Q: Summary mode? (default: single_call)\nA: ").strip() or "single_call"

    shared = run_research(
        query=user_query,
        recency=recency,
        max_results=10,
        summary_mode=summary_mode,
    )

    print("Refined Query:", shared["refined_query"])
    print("Fetched Results:", len(shared["scholar_results"]))
    for index, paper in enumerate(shared["scholar_results"], start=1):
        print(f"[{index}] {paper['title']}")
        print(f"    Link: {paper['link']}")
        print(f"    Snippet: {paper['snippet'][:140]}\n")

    print("Per-Paper Summaries:")
    for index, summary in enumerate(shared["paper_summaries"], start=1):
        print(f"[{index}] {summary['title']}")
        print(f"    {summary['summary']}\n")

    print("Final Synthesis:")
    print(shared["final_synthesis"])
    print("Guardrail:", shared["guardrail"])

if __name__ == "__main__":
    main()

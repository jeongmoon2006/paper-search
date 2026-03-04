import json

from pocketflow import BatchNode, Node

from utils.call_llm import call_llm
from utils.google_scholar_search import google_scholar_search


def _year_from_recency(recency: str) -> int | None:
    if recency == "past_year":
        return 2025
    if recency == "past_3_years":
        return 2023
    if recency == "past_5_years":
        return 2021
    return None


def _fallback_reason(exc: Exception) -> str:
    message = str(exc).lower()
    if "quota" in message or "rate limit" in message:
        return "llm_quota_or_rate_limit"
    if "authentication" in message or "api_key" in message:
        return "llm_authentication_failed"
    return "llm_unavailable"


def _extract_json_object(text: str) -> dict:
    content = text.strip()
    if content.startswith("```"):
        content = content.replace("```json", "").replace("```", "").strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return json.loads(content[start : end + 1])


class QueryRefinementNode(Node):
    def prep(self, shared):
        return shared["user_input"]

    def exec(self, user_input):
        query = user_input.get("query", "").strip()
        recency = user_input.get("recency", "any")
        year_from = _year_from_recency(recency)

        prompt = f"""
You optimize search queries for Google Scholar.
Return JSON with keys: refined_query, rationale.

Constraints:
- Keep author-provided intent unchanged.
- Add high-value academic keywords only.
- Do not add fake titles, authors, or venues.

User query: {query}
Recency preference: {recency}
""".strip()
        response = call_llm(prompt)
        parsed = json.loads(response)
        refined_query = parsed.get("refined_query", query).strip() or query
        rationale = parsed.get("rationale", "")
        return {
            "query_text": refined_query,
            "year_from": year_from,
            "rationale": rationale,
        }

    def exec_fallback(self, prep_res, exc):
        query = prep_res.get("query", "").strip()
        recency = prep_res.get("recency", "any")
        return {
            "query_text": query,
            "year_from": _year_from_recency(recency),
            "rationale": f"fallback_due_to_error: {_fallback_reason(exc)}",
        }

    def post(self, shared, prep_res, exec_res):
        shared["refined_query"] = exec_res
        shared["refinement_attempts"] = shared.get("refinement_attempts", 0) + 1
        return "search"


class ScholarSearchNode(Node):
    def prep(self, shared):
        return shared["refined_query"], shared.get("search_config", {})

    def exec(self, prep_res):
        refined, config = prep_res
        return google_scholar_search(
            refined_query=refined["query_text"],
            year_from=refined.get("year_from"),
            max_results=config.get("max_results", 10),
        )

    def post(self, shared, prep_res, exec_res):
        shared["scholar_results"] = exec_res
        min_results = shared.get("search_config", {}).get("min_results", 3)
        max_refinements = shared.get("search_config", {}).get("max_refinements", 2)
        attempts = shared.get("refinement_attempts", 1)

        if len(exec_res) < min_results and attempts < max_refinements:
            return "refine_again"
        return "summarize"


class PaperSummaryMapNode(BatchNode):
    def prep(self, shared):
        self.summary_mode = shared.get("search_config", {}).get("summary_mode", "map_reduce")
        return shared.get("scholar_results", [])

    def exec(self, paper):
        title = paper.get("title", "").strip()
        snippet = paper.get("snippet", "").strip()
        link = paper.get("link", "").strip()

        if self.summary_mode == "single_call":
            summary = snippet if snippet else "No snippet available from Google Scholar for this paper."
            return {"title": title, "link": link, "summary": summary}

        prompt = f"""
Summarize this Google Scholar result in 2 concise sentences.
Use only the provided fields and do not invent any detail.

Title: {title}
Snippet: {snippet}
Link: {link}
""".strip()
        summary = call_llm(prompt).strip()
        return {"title": title, "link": link, "summary": summary}

    def exec_fallback(self, paper, exc):
        title = paper.get("title", "").strip()
        snippet = paper.get("snippet", "").strip()
        link = paper.get("link", "").strip()
        fallback_summary = (
            snippet
            if snippet
            else "No snippet available from Google Scholar for this paper."
        )
        return {"title": title, "link": link, "summary": fallback_summary}

    def post(self, shared, prep_res, exec_res_list):
        shared["paper_summaries"] = exec_res_list
        return "default"


class SynthesisNode(Node):
    def prep(self, shared):
        return (
            shared.get("paper_summaries", []),
            shared.get("scholar_results", []),
            shared.get("search_config", {}).get("summary_mode", "map_reduce"),
        )

    def exec(self, prep_res):
        paper_summaries, scholar_results, summary_mode = prep_res
        if not paper_summaries:
            return "No Google Scholar results found for this query."

        if summary_mode == "single_call":
            lines = []
            for idx, item in enumerate(scholar_results, start=1):
                lines.append(
                    f"{idx}. Title: {item.get('title', '')}\\n"
                    f"   Link: {item.get('link', '')}\\n"
                    f"   Snippet: {item.get('snippet', '')}"
                )
            joined = "\n\n".join(lines)
            prompt = f"""
You are a research assistant.
Using only the provided Google Scholar records, return JSON with:
- paper_summaries: list of objects {{title, link, summary}} (1-2 sentences each)
- synthesis: one concise multi-paper synthesis paragraph

Rules:
- Never invent titles, links, authors, venues, years, or findings.
- Only use provided fields.
- Keep title and link exactly as given.

Output JSON only.

Records:
{joined}
""".strip()
            raw = call_llm(prompt)
            parsed = _extract_json_object(raw)
            paper_summaries_out = parsed.get("paper_summaries", [])
            synthesis_out = str(parsed.get("synthesis", "")).strip()
            if not isinstance(paper_summaries_out, list):
                raise ValueError("paper_summaries must be a list")
            return {
                "paper_summaries": paper_summaries_out,
                "synthesis": synthesis_out,
            }

        lines = []
        for idx, item in enumerate(paper_summaries, start=1):
            lines.append(
                f"{idx}. Title: {item['title']}\\n"
                f"   Link: {item['link']}\\n"
                f"   Summary: {item['summary']}"
            )
        joined = "\n\n".join(lines)

        prompt = f"""
You are a research assistant. Produce a short synthesis over these paper summaries.
Rules:
- Use only listed papers.
- Do not invent titles, links, authors, or findings.
- If uncertain, explicitly say the snippet is insufficient.

Papers:
{joined}
""".strip()
        return call_llm(prompt).strip()

    def exec_fallback(self, prep_res, exc):
        paper_summaries, scholar_results, summary_mode = prep_res
        if not paper_summaries:
            return "No Google Scholar results found for this query."

        if summary_mode == "single_call":
            deterministic = []
            for item in scholar_results:
                deterministic.append(
                    {
                        "title": item.get("title", "").strip(),
                        "link": item.get("link", "").strip(),
                        "summary": item.get("snippet", "").strip()
                        or "No snippet available from Google Scholar for this paper.",
                    }
                )
            return {
                "paper_summaries": deterministic,
                "synthesis": (
                    "Synthesis fallback (LLM unavailable). Top papers:\n"
                    + "\n".join(f"- {item['title']}" for item in deterministic[:5])
                    + f"\nReason: {_fallback_reason(exc)}"
                ),
            }

        return (
            "Synthesis fallback (LLM unavailable). Top papers:\n"
            + "\n".join(f"- {item['title']}" for item in paper_summaries[:5])
            + f"\nReason: {_fallback_reason(exc)}"
        )

    def post(self, shared, prep_res, exec_res):
        _, scholar_results, summary_mode = prep_res

        if summary_mode == "single_call" and isinstance(exec_res, dict):
            llm_summaries = exec_res.get("paper_summaries", [])
            if isinstance(llm_summaries, list):
                shared["paper_summaries"] = llm_summaries
            shared["final_synthesis"] = str(exec_res.get("synthesis", "")).strip()
        else:
            shared["final_synthesis"] = exec_res

        allowed_pairs = {
            (item.get("title", "").strip(), item.get("link", "").strip())
            for item in scholar_results
        }
        violations = []
        for item in shared.get("paper_summaries", []):
            pair = (item.get("title", "").strip(), item.get("link", "").strip())
            if pair not in allowed_pairs:
                violations.append(
                    {
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "reason": "summary_item_not_in_scholar_results",
                    }
                )

        shared["guardrail"] = {
            "hallucination_check_passed": len(violations) == 0,
            "violations": violations,
        }
        return "default"
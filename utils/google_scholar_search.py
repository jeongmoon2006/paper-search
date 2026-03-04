from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


def google_scholar_search(refined_query: str, year_from: int | None = None, max_results: int = 10) -> list[dict]:
    query = refined_query.strip()
    if not query:
        return []

    params = [f"q={quote_plus(query)}", "hl=en"]
    if year_from is not None:
        params.append(f"as_ylo={year_from}")
    search_url = f"https://scholar.google.com/scholar?{'&'.join(params)}"

    response = requests.get(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        },
        timeout=20,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict] = []

    for item in soup.select("div.gs_r.gs_or.gs_scl"):
        title_block = item.select_one("h3.gs_rt")
        snippet_block = item.select_one("div.gs_rs")
        if title_block is None:
            continue

        link_block = title_block.select_one("a")
        title = title_block.get_text(" ", strip=True)
        snippet = snippet_block.get_text(" ", strip=True) if snippet_block else ""
        link = link_block["href"].strip() if link_block and link_block.has_attr("href") else ""

        if not title:
            continue

        results.append({"title": title, "snippet": snippet, "link": link})
        if len(results) >= max_results:
            break

    return results


if __name__ == "__main__":
    papers = google_scholar_search("graph neural networks chemistry", year_from=2023, max_results=5)
    for paper in papers:
        print(f"- {paper['title']}\n  {paper['link']}\n  {paper['snippet'][:140]}\n")

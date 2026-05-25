---
name: web-research
description: Deep web research — search multiple engines, fetch full pages, and synthesize findings into comprehensive answers.
triggers:
  - researching a topic
  - finding current information
  - looking up documentation
  - comparing products or technologies
---

# Web Research Skill

You are performing deep web research. Follow this workflow for best results.

## Workflow

1. **Plan the search** — What exactly do you need to find? Break complex questions into 2-3 specific search queries.

2. **Search broadly first** — Use `search_web` with 5 results per query. The search tries Google first, falls back to DuckDuckGo. Note which results look promising.

3. **Fetch the best pages** — For the most relevant results, call `fetch_url` to get the full page content. Do NOT just rely on search snippets — they miss critical details.

4. **Cross-reference** — If information from one source seems incomplete or uncertain, search again with adjusted terms. Verify key claims across at least two independent sources.

5. **Synthesize** — Combine findings into a clear, well-organized answer. Cite sources by URL. Distinguish between facts, opinions, and documentation.

## Search Strategy

- **Code/docs questions** → search `site:github.com <topic>` or `site:docs.python.org <topic>`
- **Current events** → search with year/month for recency: `<topic> 2026`
- **Comparisons** → search `X vs Y` or `X alternative`
- **How-to** → search the specific error message or task name

## Important

- Always `notify` the user when starting a research task: "Let me research that for you..."
- If Google is blocked (check `source` field in results), note it but DuckDuckGo results are still valid
- `fetch_url` truncates at 10k chars — for very long pages, search for subsections

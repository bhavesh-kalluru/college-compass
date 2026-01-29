import json
import logging
from typing import Any, Dict, List

from pydantic import ValidationError

from services.perplexity_client import PerplexityClient
from services.openai_client import OpenAIClient, OpenAIRankingError
from utils.schemas import QueryInputs, CandidateSchool, CollegeCompassResponse
from utils.formatters import sanitize_url, dedupe_preserve_order

LOGGER = logging.getLogger("college_compass.ranker")


class CollegeRanker:
    def __init__(self, perplexity_client: PerplexityClient, openai_client: OpenAIClient):
        self.perplexity = perplexity_client
        self.openai = openai_client

    def _parse_perplexity_candidates(self, perplexity_raw: Dict[str, Any]) -> List[CandidateSchool]:
        content = perplexity_raw.get("content", "") or ""
        citations = perplexity_raw.get("citations", []) or []
        search_results = perplexity_raw.get("search_results", []) or []

        try:
            data = json.loads(content)
            candidates = data.get("candidates", []) if isinstance(data, dict) else []
            parsed: List[CandidateSchool] = []
            for c in candidates:
                if not isinstance(c, dict):
                    continue
                name = (c.get("name") or "").strip()
                location = (c.get("location") or "").strip()
                official = sanitize_url(c.get("official_website") or "")
                ev = c.get("evidence") or []
                sources = []
                for e in ev:
                    if isinstance(e, dict):
                        u = sanitize_url(e.get("source_url") or "")
                        if u:
                            sources.append(u)
                if official:
                    sources.insert(0, official)
                sources = dedupe_preserve_order([s for s in sources if s])
                if not sources:
                    sources = dedupe_preserve_order([sanitize_url(u) for u in citations if sanitize_url(u)])

                if name:
                    parsed.append(
                        CandidateSchool(
                            name=name,
                            location=location or "Unknown",
                            official_website=official,
                            sources=sources[:6],
                            notes=[
                                (e.get("claim") or "").strip()
                                for e in ev
                                if isinstance(e, dict) and e.get("claim")
                            ],
                        )
                    )
            if parsed:
                return parsed
        except Exception:
            pass

        parsed: List[CandidateSchool] = []
        for sr in search_results[:20]:
            if not isinstance(sr, dict):
                continue
            title = (sr.get("title") or "").strip()
            url = sanitize_url(sr.get("url") or "")
            if title and url:
                parsed.append(
                    CandidateSchool(
                        name=title,
                        location="Unknown",
                        official_website=None,
                        sources=[url],
                        notes=[],
                    )
                )

        if not parsed and citations:
            for u in citations[:15]:
                su = sanitize_url(u)
                if su:
                    parsed.append(
                        CandidateSchool(
                            name="Unknown (see source)",
                            location="Unknown",
                            official_website=None,
                            sources=[su],
                            notes=[],
                        )
                    )
        return parsed

    def rank_top_colleges(self, query: QueryInputs, perplexity_raw: Dict[str, Any]) -> CollegeCompassResponse:
        candidates = self._parse_perplexity_candidates(perplexity_raw)
        if len(candidates) < 5:
            raise OpenAIRankingError(
                "Not enough credible candidates returned from research. Try a more specific region or major."
            )

        candidate_payload = [c.model_dump() for c in candidates[:25]]

        schema_instructions = """
Return STRICT JSON only (no markdown), matching this schema:

{
  "query": {"major": "...", "region": "...", "degree_level": "...", "preferences": {...}},
  "results": [
    {
      "rank": 1,
      "name": "University Name",
      "location": "City, State/Country",
      "program_strength": "Short statement",
      "why_fit": ["bullet1", "bullet2", "bullet3"],
      "selectivity": "Low/Medium/High/Very High/Unknown",
      "estimated_cost_tier": "Low/Medium/High (optional)",
      "official_website": "https://...",
      "sources": ["https://source1...", "https://source2..."]
    }
  ]
}

Rules:
- Rank based on major fit + region + user preferences.
- Use candidate sources for claims; include at least 2 sources per school when possible.
- If selectivity/cost isn't supported by sources, set to "Unknown" (do not guess).
- Normalize college names (remove duplicates, ensure consistent naming).
- Return exactly 10 results, ranked 1..10.
"""

        prompt = f"""
You are an expert admissions strategist.

User query:
{json.dumps(query.model_dump(), indent=2)}

Perplexity research candidates (web-grounded):
{json.dumps(candidate_payload, indent=2)}

{schema_instructions}
"""

        ranked = self.openai.rank(prompt=prompt)
        try:
            ranked = CollegeCompassResponse.model_validate(ranked.model_dump())
        except ValidationError as e:
            LOGGER.warning("Validation error after rank: %s", str(e))
            raise OpenAIRankingError("Model output didn't match the required schema. Please retry.")

        return ranked

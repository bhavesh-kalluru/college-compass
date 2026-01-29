import os
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

LOGGER = logging.getLogger("college_compass.perplexity")


class PerplexityAPIError(Exception):
    def __init__(self, user_message: str, status_code: Optional[int] = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


@dataclass
class PerplexityConfig:
    api_key: str
    base_url: str = "https://api.perplexity.ai"
    model: str = "sonar-pro"
    timeout_s: int = 45


def _safe_err_msg(resp: requests.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            return str(data["error"])
        return json.dumps(data)[:500]
    except Exception:
        return (resp.text or "")[:500]


class PerplexityClient:
    """
    Minimal Perplexity Chat Completions client:
      - POST /chat/completions
      - Bearer auth
      - Returns content + citations/search_results when present
    """

    def __init__(self, config: Optional[PerplexityConfig] = None):
        api_key = os.getenv("PERPLEXITY_API_KEY", "")
        if not api_key and config is None:
            raise PerplexityAPIError("PERPLEXITY_API_KEY is not set.")
        self.config = config or PerplexityConfig(api_key=api_key)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((requests.RequestException, PerplexityAPIError)),
    )
    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        try:
            resp = self.session.post(url, json=payload, timeout=self.config.timeout_s)
        except requests.RequestException as e:
            LOGGER.warning("Network error calling Perplexity: %s", str(e))
            raise

        if resp.status_code == 429:
            raise PerplexityAPIError("Rate limited by Perplexity (429). Please retry shortly.", 429)
        if resp.status_code >= 500:
            raise PerplexityAPIError("Perplexity is having trouble (5xx). Please retry shortly.", resp.status_code)
        if resp.status_code >= 400:
            raise PerplexityAPIError(f"Perplexity request failed: {_safe_err_msg(resp)}", resp.status_code)

        return resp.json()

    def research_candidates(self, query_payload: Dict[str, Any]) -> Dict[str, Any]:
        major = query_payload.get("major", "")
        region = query_payload.get("region", "")
        degree = query_payload.get("degree_level", "")
        preferences = query_payload.get("preferences", {})

        pref_lines = []
        if preferences.get("strong_scholarships"):
            pref_lines.append("Strong scholarships / funding")
        if preferences.get("research_focused"):
            pref_lines.append("Research-focused programs")
        if preferences.get("high_acceptance_chances"):
            pref_lines.append("Higher acceptance chances (less selective)")
        if preferences.get("top_ranked_only"):
            pref_lines.append("Top-ranked programs only")
        budget = preferences.get("budget_sensitivity")

        pref_text = "; ".join(pref_lines) if pref_lines else "No special preferences"
        if budget:
            pref_text += f"; Budget sensitivity: {budget}"

        system = (
            "You are a meticulous academic program researcher. "
            "Return ONLY valid JSON. No markdown. No commentary."
        )

        user = f"""
Find strong colleges/universities for:
- Major: {major}
- Region/Area: {region}
- Degree level: {degree}
Preferences: {pref_text}

Requirements:
1) Prefer authoritative sources: official program pages and credible rankings (e.g., major-specific rankings).
2) Include citations/URLs for each candidate.
3) Include at least 15 candidates if possible (to give the ranker options).
4) If region is broad, include top options located in/near the region.
5) Return STRICT JSON exactly in this structure:

{{
  "query": {{
    "major": "...",
    "region": "...",
    "degree_level": "...",
    "preferences_summary": "..."
  }},
  "candidates": [
    {{
      "name": "University Name",
      "location": "City, State/Country",
      "official_website": "https://...",
      "evidence": [
        {{
          "claim": "Why it is strong for the major",
          "source_url": "https://..."
        }}
      ]
    }}
  ]
}}

Important:
- Only include URLs that you are reasonably confident are correct.
- If unsure, omit official_website and include a source_url instead.
"""

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 2200,
        }

        data = self._post("/chat/completions", payload)

        content = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            content = ""

        return {
            "raw": data,
            "content": content,
            "citations": data.get("citations") or [],
            "search_results": data.get("search_results") or [],
            "model": data.get("model"),
        }

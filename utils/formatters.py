import html
from typing import List, Optional
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from utils.schemas import CollegeResult


def sanitize_url(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        u = url.strip()
        parsed = urlparse(u)
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None
        return u
    except Exception:
        return None


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def inject_global_css() -> None:
    st.markdown(
        """
<style>
:root{
  --cc-bg: #0b1220;
  --cc-card: rgba(255,255,255,0.06);
  --cc-card2: rgba(255,255,255,0.09);
  --cc-border: rgba(255,255,255,0.12);
  --cc-text: rgba(255,255,255,0.92);
  --cc-muted: rgba(255,255,255,0.72);
  --cc-accent: #7c3aed; /* violet */
  --cc-accent2: #22c55e; /* green */
}

section.main > div { padding-top: 1.2rem; }
.block-container { padding-top: 1.2rem !important; }

.cc-hero {
  background: radial-gradient(1200px 300px at 15% 10%, rgba(124,58,237,0.35), transparent 60%),
              radial-gradient(1000px 350px at 80% 0%, rgba(34,197,94,0.20), transparent 60%),
              linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
  border: 1px solid var(--cc-border);
  border-radius: 20px;
  padding: 18px 18px;
  margin-bottom: 14px;
}

.cc-title {
  font-size: 2.0rem;
  font-weight: 780;
  letter-spacing: -0.02em;
  color: var(--cc-text);
  margin: 0 0 4px 0;
}
.cc-tagline {
  color: var(--cc-muted);
  margin: 0;
  font-size: 1.0rem;
}

.microcopy {
  color: rgba(255,255,255,0.72);
  font-size: 0.92rem;
  line-height: 1.3rem;
  padding-top: 0.35rem;
}

.cc-card {
  background: linear-gradient(180deg, var(--cc-card), var(--cc-card2));
  border: 1px solid var(--cc-border);
  border-radius: 18px;
  padding: 14px 14px 12px 14px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.25);
  margin-bottom: 14px;
}

.cc-card h3 {
  margin: 0 0 6px 0;
  font-size: 1.15rem;
  color: var(--cc-text);
}

.cc-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 6px 0 8px 0;
}
.cc-badge {
  border: 1px solid var(--cc-border);
  background: rgba(255,255,255,0.06);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 0.82rem;
  color: rgba(255,255,255,0.82);
}

.cc-why li { margin-bottom: 4px; color: rgba(255,255,255,0.82); }
.cc-label { color: rgba(255,255,255,0.70); font-size: 0.86rem; }
.cc-value { color: rgba(255,255,255,0.90); }

.cc-sources a {
  color: rgba(255,255,255,0.85);
  text-decoration: none;
  border-bottom: 1px dotted rgba(255,255,255,0.25);
}
.cc-sources a:hover { border-bottom-color: rgba(255,255,255,0.70); }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
<div class="cc-hero">
  <div class="cc-title">🧭 College Compass</div>
  <p class="cc-tagline">Web-grounded research + reasoned ranking to find your best-fit universities.</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def _safe(s: str) -> str:
    return html.escape(s or "")


def render_result_card(r: CollegeResult) -> str:
    official = sanitize_url(r.official_website or "") or ""
    sources = [sanitize_url(u) for u in (r.sources or [])]
    sources = [u for u in sources if u]

    why = "".join([f"<li>{_safe(x)}</li>" for x in (r.why_fit or [])[:3]])

    badges = [
        f"🏅 Rank #{r.rank}",
        f"📍 {_safe(r.location)}",
        f"🎯 {_safe(r.selectivity)} selectivity" if r.selectivity else "🎯 Selectivity: Unknown",
    ]
    if r.estimated_cost_tier:
        badges.append(f"💸 Cost: {_safe(r.estimated_cost_tier)}")

    badge_html = "".join([f'<span class="cc-badge">{b}</span>' for b in badges])

    sources_html = ""
    if sources:
        source_links = []
        for u in sources[:6]:
            source_links.append(f'<a href="{_safe(u)}" target="_blank" rel="noopener noreferrer">{_safe(u)}</a>')
        sources_html = "<br/>".join(source_links)

    official_html = ""
    if official:
        official_html = f'<a href="{_safe(official)}" target="_blank" rel="noopener noreferrer">Official website</a>'

    return f"""
<div class="cc-card">
  <h3>{_safe(r.name)}</h3>
  <div class="cc-badges">{badge_html}</div>

  <div style="margin-top:6px;">
    <div class="cc-label">Strength for the major</div>
    <div class="cc-value">🧠 {_safe(r.program_strength)}</div>
  </div>

  <div style="margin-top:10px;">
    <div class="cc-label">Why it fits</div>
    <ul class="cc-why">{why}</ul>
  </div>

  <div style="margin-top:8px;">
    <div class="cc-label">Links</div>
    <div class="cc-sources">{official_html}</div>
  </div>

  <div style="margin-top:10px;">
    <div class="cc-label">Sources</div>
    <div class="cc-sources" style="font-size:0.85rem;">{sources_html or "No sources provided."}</div>
  </div>
</div>
"""


def results_to_dataframe(results: List[CollegeResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append(
            {
                "rank": r.rank,
                "name": r.name,
                "location": r.location,
                "program_strength": r.program_strength,
                "why_fit": " | ".join((r.why_fit or [])[:3]),
                "selectivity": r.selectivity,
                "estimated_cost_tier": r.estimated_cost_tier or "",
                "official_website": sanitize_url(r.official_website or "") or "",
                "sources": " | ".join([u for u in (r.sources or []) if sanitize_url(u)][:6]),
            }
        )
    return pd.DataFrame(rows).sort_values("rank")


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

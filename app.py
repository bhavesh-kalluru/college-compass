import os
import time
import logging
from typing import Dict, Any, Optional

import streamlit as st
import pandas as pd

from services.perplexity_client import PerplexityClient, PerplexityAPIError
from services.openai_client import OpenAIClient, OpenAIRankingError
from services.ranker import CollegeRanker
from utils.schemas import PreferenceInputs, QueryInputs
from utils.formatters import (
    inject_global_css,
    render_header,
    render_result_card,
    sanitize_url,
    results_to_dataframe,
    dataframe_to_csv_bytes,
)

LOGGER = logging.getLogger("college_compass")


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _env_ok() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and bool(os.getenv("PERPLEXITY_API_KEY"))


@st.cache_data(ttl=15 * 60, show_spinner=False)
def cached_perplexity_candidates(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cache Perplexity responses for short duration to reduce cost + rate limit risk.
    Payload is a JSON-serializable dict (major/region/degree/preferences).
    """
    client = PerplexityClient()
    return client.research_candidates(payload)


def _reset_session_results() -> None:
    st.session_state.pop("cc_response", None)
    st.session_state.pop("cc_df", None)


def main() -> None:
    _setup_logging()

    st.set_page_config(
        page_title="College Compass",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_global_css()
    render_header()

    if not _env_ok():
        st.warning(
            "🔐 API keys not detected yet. Add **OPENAI_API_KEY** and **PERPLEXITY_API_KEY** "
            "as environment variables to enable recommendations."
        )

    with st.sidebar:
        st.markdown("### 🎯 Your Study Plan")
        major = st.text_input(
            "Intended major *",
            placeholder="e.g., Computer Science, Nursing, Data Science, Mechanical Engineering",
        )
        region = st.text_input(
            "Region / Area *",
            placeholder="e.g., California, USA • Toronto, Canada • Germany • Southeast Asia",
            help="You can type a country, state, city, or broad region.",
        )
        degree_level = st.selectbox("Degree level", ["Bachelor’s", "Master’s", "PhD"], index=0)

        budget = st.select_slider(
            "Budget sensitivity (optional)",
            options=["Low", "Medium", "High"],
            value="Medium",
            help="Used as a soft preference when costs are mentioned by sources.",
        )

        st.markdown("### ✅ Preferences")
        strong_scholarships = st.checkbox("Strong scholarships", value=False)
        research_focused = st.checkbox("Research-focused", value=False)
        high_acceptance = st.checkbox("High acceptance chances", value=False)
        top_ranked_only = st.checkbox("Top-ranked only", value=False)

        st.caption("Tip: Combine preferences for sharper recommendations.")

        if st.button("🧹 Clear results", use_container_width=True):
            _reset_session_results()
            st.rerun()

    st.markdown("### 🧭 Find your best-fit colleges")
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        find_clicked = st.button("🚀 Find colleges", type="primary", use_container_width=True)
    with c2:
        st.markdown(
            "<div class='microcopy'>We’ll use web-grounded research + reasoning to rank results.</div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            "<div class='microcopy'>Top 10 results • Cards + CSV • Compare 2–3 schools</div>",
            unsafe_allow_html=True,
        )

    if find_clicked:
        if not major.strip() or not region.strip():
            st.error("Please enter **both** an intended major and a region/area.")
            st.stop()

        if not _env_ok():
            st.error(
                "Missing API keys. Set **OPENAI_API_KEY** and **PERPLEXITY_API_KEY** in your environment."
            )
            st.stop()

        prefs = PreferenceInputs(
            budget_sensitivity=budget,
            strong_scholarships=strong_scholarships,
            research_focused=research_focused,
            high_acceptance_chances=high_acceptance,
            top_ranked_only=top_ranked_only,
        )
        query = QueryInputs(
            major=major.strip(),
            region=region.strip(),
            degree_level=degree_level,
            preferences=prefs,
        )

        perplexity_payload = query.model_dump()

        progress = st.progress(0, text="Searching sources…")
        time.sleep(0.15)

        try:
            with st.spinner("🔎 Searching web-grounded sources via Perplexity…"):
                perplexity_raw = cached_perplexity_candidates(perplexity_payload)

            progress.progress(35, text="Ranking candidates…")
            time.sleep(0.15)

            with st.spinner("🧠 Ranking & summarizing via OpenAI…"):
                perplexity_client = PerplexityClient()
                openai_client = OpenAIClient()
                ranker = CollegeRanker(perplexity_client=perplexity_client, openai_client=openai_client)
                cc_response = ranker.rank_top_colleges(query=query, perplexity_raw=perplexity_raw)

            progress.progress(70, text="Summarizing & formatting…")
            time.sleep(0.15)

            df = results_to_dataframe(cc_response.results)
            st.session_state["cc_response"] = cc_response
            st.session_state["cc_df"] = df

            progress.progress(100, text="Done ✅")
            st.balloons()

        except PerplexityAPIError as e:
            LOGGER.exception("Perplexity error")
            st.error(f"Perplexity request failed: {e.user_message}")
            st.info("Try again in a moment, or refine the region to be more specific.")
            st.stop()
        except OpenAIRankingError as e:
            LOGGER.exception("OpenAI ranking error")
            st.error(f"OpenAI ranking failed: {e.user_message}")
            st.info("Try again, or reduce preferences if they’re too restrictive.")
            st.stop()
        except Exception:
            LOGGER.exception("Unexpected error")
            st.error("Something unexpected happened. Please retry.")
            st.stop()

    cc_response = st.session_state.get("cc_response")
    df: Optional[pd.DataFrame] = st.session_state.get("cc_df")

    if cc_response and df is not None and not df.empty:
        st.markdown("---")
        st.markdown("## 🎓 Top matches (Top 10)")

        cols = st.columns(2, gap="large")
        for idx, r in enumerate(cc_response.results):
            with cols[idx % 2]:
                st.markdown(render_result_card(r), unsafe_allow_html=True)

        st.markdown("### ⬇️ Download results")
        csv_bytes = dataframe_to_csv_bytes(df)
        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name="college_compass_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.markdown("### 🆚 Compare 2–3 colleges")
        name_to_row = {row["name"]: row for _, row in df.iterrows()}
        selected = st.multiselect(
            "Select colleges to compare",
            options=list(name_to_row.keys()),
            default=list(name_to_row.keys())[:2],
            max_selections=3,
        )

        if len(selected) >= 2:
            comp_df = df[df["name"].isin(selected)].copy()
            comp_df = comp_df[
                ["rank", "name", "location", "program_strength", "selectivity", "estimated_cost_tier", "official_website"]
            ].sort_values("rank")
            comp_df["official_website"] = comp_df["official_website"].apply(lambda u: sanitize_url(u) or "")
            st.dataframe(comp_df, use_container_width=True, hide_index=True)
        else:
            st.info("Pick at least **2** colleges to compare side-by-side.")

        st.markdown(
            "<div class='microcopy'>Reminder: Always verify details (cost, admissions, scholarships) on official sites.</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()

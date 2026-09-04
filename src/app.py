"""Streamlit UI for Dubai Property Investor Q&A Bot."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from rag import rag_query, health_check, structured_search

# Page config
st.set_page_config(
    page_title="Dubai Property Investor Bot",
    page_icon="🏠",
    layout="wide",
)

# --- Health Check ---
if "health_checked" not in st.session_state:
    checks = health_check()
    st.session_state.health_checked = True
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        st.error(f"Health check failed: {', '.join(failed)}. Run `make setup` first.")
        st.stop()

# --- Header ---
st.title("🏠 Dubai Property Investment Assistant")
st.caption("AI-powered investment scoring and Q&A — backed by DLD-style transaction data and market reports")

# --- Disclaimer ---
st.info(
    "**Disclaimer:** This is an AI assistant for informational purposes only, not financial advice. "
    "Data is from a Q1 2024 mock dataset. Verify all information with the Dubai Land Department (DLD) "
    "and consult a RERA-licensed advisor before making investment decisions."
)

# --- Sidebar ---
st.sidebar.header("🔍 Search Filters")

# Community filter
COMMUNITIES = [
    "Any", "Downtown Dubai", "Dubai Marina", "Palm Jumeirah",
    "Dubai Hills Estate", "JVC (Jumeirah Village Circle)", "Business Bay",
    "Arabian Ranches", "Sports City", "Discovery Gardens",
    "JLT (Jumeirah Lake Towers)", "The Springs", "Al Barsha",
    "Deira", "Bur Dubai", "International City", "Dubai Silicon Oasis",
    "Tilal Al Ghaf", "DAMAC Hills 2", "Dubai Creek Harbour",
    "Bluewaters Island", "Meydan", "Al Furjan", "Dubai South", "Town Square",
]
selected_community = st.sidebar.selectbox("Community", COMMUNITIES, index=0)

budget_range = st.sidebar.slider(
    "Budget (AED)", min_value=300_000, max_value=15_000_000,
    value=(500_000, 5_000_000), step=100_000,
)

bedroom_options = ["Any", "Studio", "1", "2", "3", "4", "5"]
selected_bedrooms = st.sidebar.selectbox("Bedrooms", bedroom_options, index=0)

property_types = ["Any", "Apartment", "Villa", "Penthouse"]
selected_type = st.sidebar.selectbox("Property Type", property_types, index=0)

# Build filters
filters = {}
if selected_community != "Any":
    filters["community"] = selected_community
if budget_range[0] > 300_000:
    filters["min_price"] = budget_range[0]
if budget_range[1] < 15_000_000:
    filters["max_price"] = budget_range[1]
if selected_bedrooms != "Any":
    filters["bedrooms"] = 0 if selected_bedrooms == "Studio" else int(selected_bedrooms)
if selected_type != "Any":
    filters["property_type"] = selected_type

# --- Investment Leaderboard ---
st.sidebar.markdown("---")
st.sidebar.header("📊 Quick Scores")

if st.sidebar.button("Show Investment Leaderboard"):
    result = structured_search("", filters=None)
    scores = result["community_scores"][:10]

    st.subheader("🏆 Investment Leaderboard")
    st.caption("Based on 7 metrics: yield, net yield, price/sqft, service charges, supply pipeline, occupancy, developer")

    for cs in scores:
        rec_color = {"INVEST": "🟢", "HOLD": "🟡", "AVOID": "🔴"}.get(cs["recommendation"], "⚪")
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.write(f"**{cs['community']}**")
        with col2:
            st.write(f"Net: {cs['avg_net_yield_pct']:.1f}%")
        with col3:
            st.write(f"Score: {cs['composite_score']:.0f}/100")
        with col4:
            st.write(f"{rec_color} {cs['recommendation']}")

# --- Chat Interface ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("scores"):
            with st.expander("📊 Community Scores"):
                for cs in msg["scores"][:5]:
                    st.write(
                        f"**{cs['community']}**: {cs['recommendation']} "
                        f"(Score: {cs['composite_score']:.0f}/100, "
                        f"Net Yield: {cs['avg_net_yield_pct']:.2f}%)"
                    )

if query := st.chat_input("Ask about Dubai real estate investments..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Searching transactions, scores, and market reports..."):
            try:
                result = rag_query(query, filters=filters if filters else None)
                st.markdown(result["answer"])

                # Show top community scores
                if result["structured"]["community_scores"]:
                    with st.expander("📊 Relevant Community Scores"):
                        for cs in result["structured"]["community_scores"][:5]:
                            rec_icon = {"INVEST": "🟢", "HOLD": "🟡", "AVOID": "🔴"}.get(cs["recommendation"], "⚪")
                            st.markdown(
                                f"**{cs['community']}** {rec_icon} {cs['recommendation']}\n"
                                f"- Composite Score: {cs['composite_score']:.0f}/100\n"
                                f"- Net Yield: {cs['avg_net_yield_pct']:.2f}% | Gross: {cs['avg_roi_pct']:.1f}%\n"
                                f"- Price/sqft: AED {cs['avg_price_per_sqft']:,.0f} | Service Charge: AED {cs['avg_service_charge']:.1f}/sqft\n"
                                f"- Supply Risk: {cs['supply_risk']} | Pipeline: {cs['pipeline_pct_of_stock']:.1f}%\n"
                                f"- Occupancy: {cs['occupancy_rate']:.0%}"
                            )

                # Show matching transactions
                if result["structured"]["transactions"]:
                    with st.expander("🏘️ Matching Properties"):
                        for tx in result["structured"]["transactions"][:5]:
                            st.markdown(
                                f"**{tx['transaction_id']}** — {tx['community']}, "
                                f"{tx['bedrooms']}BR {tx['property_type']}\n"
                                f"- Price: AED {tx['price_aed']:,} | Size: {tx['size_sqft']}sqft\n"
                                f"- Net Yield: {tx['net_yield_pct']:.2f}% | Gross: {tx['roi_pct']}%\n"
                                f"- Floor: {tx['floor_level']} | View: {tx['view_type']}\n"
                                f"- Developer: {tx['developer']} | {tx['handover_status']}"
                            )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "scores": result["structured"]["community_scores"],
                })

            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {str(e)}"})

# --- Footer ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Architecture:** DuckDB (structured analytics) + ChromaDB (semantic search) + LLM (generation)\n\n"
    "**Data:** 60+ mock DLD transactions, 25 communities, 4 market reports\n\n"
    "**Metrics:** 7-factor investment scoring (yield, net yield, price/sqft, service charges, supply pipeline, occupancy, developer)"
)

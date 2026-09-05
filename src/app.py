"""Streamlit UI for Dubai Property Investor Q&A Bot."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import tempfile
import os
from datetime import datetime
from rag import rag_query, health_check, structured_search
from calculators import calculate_mortgage, calculate_str
from price_trends import get_price_trend, get_all_trends, get_top_gainers, get_top_volume, HISTORICAL_DATA
from export import generate_excel_report, generate_pdf_report
from config import REC_ICONS, MIN_BUDGET, MAX_BUDGET

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
    "Budget (AED)", min_value=MIN_BUDGET, max_value=MAX_BUDGET,
    value=(500_000, 5_000_000), step=100_000,
)

bedroom_options = ["Any", "Studio", "1", "2", "3", "4", "5"]
selected_bedrooms = st.sidebar.selectbox("Bedrooms", bedroom_options, index=0)

property_types = ["Any", "Apartment", "Villa", "Penthouse"]
selected_type = st.sidebar.selectbox("Property Type", property_types, index=0)

# Mortgage sidebar
st.sidebar.markdown("---")
st.sidebar.header("🏦 Mortgage Settings")
is_resident = st.sidebar.checkbox("UAE Resident", value=True)
is_first = st.sidebar.checkbox("First Property", value=True)
interest_rate = st.sidebar.slider("Interest Rate (%)", 3.0, 7.0, 4.5, 0.1)
tenure = st.sidebar.slider("Tenure (years)", 5, 25, 25)
down_payment_pct = st.sidebar.slider("Down Payment (%)", 10, 50, 20)

# Build filters
filters = {}
if selected_community != "Any":
    filters["community"] = selected_community
if budget_range[0] > MIN_BUDGET:
    filters["min_price"] = budget_range[0]
if budget_range[1] < MAX_BUDGET:
    filters["max_price"] = budget_range[1]
if selected_bedrooms != "Any":
    filters["bedrooms"] = 0 if selected_bedrooms == "Studio" else int(selected_bedrooms)
if selected_type != "Any":
    filters["property_type"] = selected_type


def render_property_card(tx: dict, show_mortgage: bool = True):
    """Render a property card with optional mortgage info."""
    rec_icon = REC_ICONS.get("HOLD", "⚪")

    # Mortgage calculation
    mortgage = None
    str_est = None
    if show_mortgage:
        try:
            mortgage = calculate_mortgage(
                property_price=tx["price_aed"],
                down_payment_pct=down_payment_pct / 100,
                interest_rate=interest_rate,
                tenure_years=tenure,
                service_charge_sqft=tx.get("service_charge_aed_sqft", 15),
                size_sqft=tx["size_sqft"],
                is_resident=is_resident,
                is_first_property=is_first,
            )
        except Exception:
            pass

        try:
            str_est = calculate_str(
                community=tx["community"],
                bedrooms=tx["bedrooms"],
                property_price=tx["price_aed"],
                size_sqft=tx["size_sqft"],
                service_charge_sqft=tx.get("service_charge_aed_sqft", 15),
            )
        except Exception:
            pass

    # Main card
    st.markdown(f"### {tx['transaction_id']} — {tx['community']}")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"**Price:** AED {tx['price_aed']:,}")
        st.markdown(f"**Size:** {tx['size_sqft']} sqft")
        st.markdown(f"**Price/sqft:** AED {tx.get('price_per_sqft', tx['price_aed'] / tx['size_sqft']):,.0f}")
        st.markdown(f"**Type:** {tx['bedrooms']}BR {tx['property_type']}")

    with col2:
        st.markdown(f"**Gross Yield:** {tx['roi_pct']}%")
        st.markdown(f"**Net Yield:** {tx['net_yield_pct']:.2f}%")
        st.markdown(f"**Floor:** {tx.get('floor_level', 'N/A')}")
        st.markdown(f"**View:** {tx.get('view_type', 'N/A')}")

    with col3:
        st.markdown(f"**Developer:** {tx.get('developer', 'N/A')}")
        st.markdown(f"**Status:** {tx.get('handover_status', 'N/A')}")
        st.markdown(f"**Parking:** {tx.get('parking_spots', 'N/A')} spots")
        st.markdown(f"**Furnishing:** {tx.get('furnishing', 'N/A')}")

    # Mortgage breakdown
    if mortgage:
        with st.expander(f"🏦 Mortgage — AED {mortgage.monthly_payment:,}/month"):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                st.metric("Down Payment", f"AED {mortgage.down_payment:,}", f"{mortgage.down_payment_pct}%")
                st.metric("Loan Amount", f"AED {mortgage.loan_amount:,}")
            with mc2:
                st.metric("Monthly Payment", f"AED {mortgage.monthly_payment:,}")
                st.metric("Total Interest", f"AED {mortgage.total_interest:,}")
            with mc3:
                st.metric("DLD Transfer Fee", f"AED {mortgage.dld_transfer_fee:,}")
                st.metric("Total Acquisition", f"AED {mortgage.total_acquisition_cost:,}")

    # STR estimate
    if str_est and str_est.annual_revenue > 0:
        with st.expander(f"🏖️ Short-Term Rental Potential"):
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.metric("Avg Daily Rate", f"AED {str_est.avg_daily_rate}")
                st.metric("Occupancy", f"{str_est.occupancy_rate:.0%}")
            with sc2:
                st.metric("Annual Revenue", f"AED {str_est.annual_revenue:,}")
                st.metric("Gross Yield", f"{str_est.gross_yield:.1f}%")
            with sc3:
                st.metric("Net Revenue", f"AED {str_est.net_revenue:,}")
                st.metric("Net Yield", f"{str_est.net_yield:.1f}%")

            st.caption(
                f"vs Long-term: AED {str_est.long_term_monthly_rent:,}/mo "
                f"({str_est.str_premium_pct:+.1f}% STR premium)"
            )

    st.divider()


# --- Tabs ---
tab_chat, tab_leaderboard, tab_compare, tab_trends, tab_map = st.tabs(
    ["💬 Ask", "🏆 Leaderboard", "⚖️ Compare", "📈 Trends", "🗺️ Map"]
)

# --- Chat Tab ---
with tab_chat:
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

                    if result["structured"]["community_scores"]:
                        with st.expander("📊 Relevant Community Scores"):
                            for cs in result["structured"]["community_scores"][:5]:
                                rec_icon = REC_ICONS.get(cs["recommendation"], "⚪")
                                st.markdown(
                                    f"**{cs['community']}** {rec_icon} {cs['recommendation']}\n"
                                    f"- Composite Score: {cs['composite_score']:.0f}/100\n"
                                    f"- Net Yield: {cs['avg_net_yield_pct']:.2f}% | Gross: {cs['avg_roi_pct']:.1f}%\n"
                                    f"- Price/sqft: AED {cs['avg_price_per_sqft']:,.0f} | Service Charge: AED {cs['avg_service_charge']:.1f}/sqft\n"
                                    f"- Supply Risk: {cs['supply_risk']} | Pipeline: {cs['pipeline_pct_of_stock']:.1f}%\n"
                                    f"- Occupancy: {cs['occupancy_rate']:.0%}"
                                )

                    if result["structured"]["transactions"]:
                        with st.expander("🏘️ Matching Properties"):
                            for tx in result["structured"]["transactions"][:5]:
                                render_property_card(tx)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "scores": result["structured"]["community_scores"],
                    })

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {str(e)}"})

# --- Leaderboard Tab ---
with tab_leaderboard:
    st.subheader("🏆 Investment Leaderboard")
    st.caption("Ranked by composite score across 7 metrics")

    result = structured_search("", filters=None)
    scores = result["community_scores"]

    for i, cs in enumerate(scores, 1):
        rec_icon = REC_ICONS.get(cs["recommendation"], "⚪")
        col1, col2, col3, col4, col5 = st.columns([1, 3, 1.5, 1.5, 1])
        with col1:
            st.markdown(f"**#{i}**")
        with col2:
            st.markdown(f"**{cs['community']}**")
        with col3:
            st.metric("Net Yield", f"{cs['avg_net_yield_pct']:.1f}%")
        with col4:
            st.metric("Score", f"{cs['composite_score']:.0f}/100")
        with col5:
            st.markdown(f"{rec_icon} {cs['recommendation']}")

        # Quick mortgage preview
        mc1, mc2 = st.columns(2)
        with mc1:
            mortgage = calculate_mortgage(
                property_price=int(cs["avg_price"]),
                down_payment_pct=down_payment_pct / 100,
                interest_rate=interest_rate,
                tenure_years=tenure,
                size_sqft=800,
            )
            st.caption(f"Est. mortgage: AED {mortgage.monthly_payment:,}/mo")
        with mc2:
            str_est = calculate_str(
                community=cs["community"],
                bedrooms=1,
                property_price=int(cs["avg_price"]),
                size_sqft=800,
            )
            if str_est and str_est.annual_revenue > 0:
                st.caption(f"STR potential: AED {str_est.net_yield:.1f}% net yield")
            else:
                st.caption("STR: N/A")

        if i < len(scores):
            st.divider()

# --- Compare Tab ---
with tab_compare:
    st.subheader("⚖️ Property Comparison")
    st.caption("Select up to 3 properties to compare side by side")

    result = structured_search("", filters=filters if filters else None)
    txs = result["transactions"][:10]

    if len(txs) < 2:
        st.warning("Need at least 2 properties to compare. Adjust your filters.")
    else:
        options = [f"{t['transaction_id']} — {t['community']}, {t['bedrooms']}BR, AED {t['price_aed']:,}" for t in txs]
        selected = st.multiselect("Select properties to compare", options, max_selections=3)

        if len(selected) >= 2:
            cols = st.columns(len(selected))
            for i, sel in enumerate(selected):
                tx_idx = options.index(sel)
                tx = txs[tx_idx]
                with cols[i]:
                    st.markdown(f"### {tx['transaction_id']}")
                    st.markdown(f"**{tx['community']}**")
                    st.markdown(f"{tx['bedrooms']}BR {tx['property_type']}")

                    st.markdown("---")
                    st.markdown(f"**Price:** AED {tx['price_aed']:,}")
                    st.markdown(f"**Size:** {tx['size_sqft']} sqft")
                    st.markdown(f"**Price/sqft:** AED {tx.get('price_per_sqft', 0):,.0f}")

                    st.markdown("---")
                    st.markdown(f"**Gross Yield:** {tx['roi_pct']}%")
                    st.markdown(f"**Net Yield:** {tx['net_yield_pct']:.2f}%")
                    st.markdown(f"**Service Charge:** AED {tx.get('service_charge_aed_sqft', 0)}/sqft")

                    st.markdown("---")
                    mortgage = calculate_mortgage(
                        property_price=tx["price_aed"],
                        down_payment_pct=down_payment_pct / 100,
                        interest_rate=interest_rate,
                        tenure_years=tenure,
                        size_sqft=tx["size_sqft"],
                        service_charge_sqft=tx.get("service_charge_aed_sqft", 15),
                        is_resident=is_resident,
                        is_first_property=is_first,
                    )
                    st.markdown(f"**Monthly Payment:** AED {mortgage.monthly_payment:,}")
                    st.markdown(f"**Total Acquisition:** AED {mortgage.total_acquisition_cost:,}")

                    str_est = calculate_str(
                        community=tx["community"],
                        bedrooms=tx["bedrooms"],
                        property_price=tx["price_aed"],
                        size_sqft=tx["size_sqft"],
                        service_charge_sqft=tx.get("service_charge_aed_sqft", 15),
                    )
                    if str_est and str_est.annual_revenue > 0:
                        st.markdown(f"**STR Revenue:** AED {str_est.annual_revenue:,}/yr")
                        st.markdown(f"**STR Premium:** {str_est.str_premium_pct:+.1f}% vs long-term")

# --- Trends Tab ---
with tab_trends:
    st.subheader("📈 Price Trends")
    st.caption("Historical price per sqft and transaction volume by community")

    # Top gainers
    st.markdown("### 🚀 Top Price Gainers (YoY)")
    gainers = get_top_gainers(5)
    cols = st.columns(5)
    for i, g in enumerate(gainers):
        with cols[i]:
            st.metric(
                g.community,
                f"AED {g.prices[-1]:,}/sqft",
                f"{g.yoy_change_pct:+.1f}%",
            )

    st.markdown("---")

    # Community selector for detailed view
    all_communities = sorted(HISTORICAL_DATA.keys())
    selected_comm = st.selectbox("Select community for detailed trend", all_communities)

    if selected_comm:
        trend = get_price_trend(selected_comm)

        if trend.prices:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Price per Sqft")
                price_df = pd.DataFrame({
                    "Quarter": trend.quarters,
                    "AED/sqft": trend.prices,
                })
                st.line_chart(price_df.set_index("Quarter"))

            with col2:
                st.markdown("### Transaction Volume")
                vol_df = pd.DataFrame({
                    "Quarter": trend.quarters,
                    "Transactions": trend.volumes,
                })
                st.bar_chart(vol_df.set_index("Quarter"))

            # Summary stats
            st.markdown("### Summary")
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Current Price", f"AED {trend.prices[-1]:,}/sqft")
            with sc2:
                st.metric("YoY Change", f"{trend.yoy_change_pct:+.1f}%")
            with sc3:
                st.metric("Latest Volume", f"{trend.volumes[-1]} txns")
            with sc4:
                trend_icon = {"up": "📈", "down": "📉", "stable": "➡️"}
                st.metric("Trend", f"{trend_icon.get(trend.trend_direction, '')} {trend.trend_direction.title()}")

    # All communities comparison
    st.markdown("---")
    st.markdown("### All Communities — Q1 2024 Snapshot")
    all_trends = get_all_trends()
    snapshot_data = []
    for comm, t in sorted(all_trends.items(), key=lambda x: x[1].prices[-1] if x[1].prices else 0, reverse=True):
        if t.prices:
            snapshot_data.append({
                "Community": comm,
                "Price/sqft (Q1 2024)": t.prices[-1],
                "YoY Change": f"{t.yoy_change_pct:+.1f}%",
                "Volume": t.volumes[-1] if t.volumes else 0,
                "Trend": t.trend_direction,
            })
    st.dataframe(snapshot_data, use_container_width=True)

# --- Map Tab ---
with tab_map:
    st.subheader("🗺️ Community Map")
    st.caption("Community locations with investment scores")

    # Community coordinates (hardcoded)
    COMMUNITY_COORDS = {
        "Downtown Dubai": (25.1972, 55.2744),
        "Dubai Marina": (25.0800, 55.1340),
        "Palm Jumeirah": (25.1120, 55.1390),
        "Dubai Hills Estate": (25.1560, 55.2490),
        "JVC (Jumeirah Village Circle)": (25.0580, 55.2040),
        "Business Bay": (25.1850, 55.2640),
        "Arabian Ranches": (25.0580, 55.3360),
        "Sports City": (25.0440, 55.2280),
        "Discovery Gardens": (25.0580, 55.1440),
        "JLT (Jumeirah Lake Towers)": (25.0780, 55.1410),
        "The Springs": (25.0580, 55.1580),
        "Al Barsha": (25.1180, 55.2000),
        "Deira": (25.2580, 55.3040),
        "Bur Dubai": (25.2330, 55.2920),
        "International City": (25.1600, 55.4040),
        "Dubai Silicon Oasis": (25.1180, 55.3880),
        "Tilal Al Ghaf": (25.0780, 55.2840),
        "DAMAC Hills 2": (25.0280, 55.2580),
        "Dubai Creek Harbour": (25.2180, 55.3380),
        "Bluewaters Island": (25.0780, 55.1180),
        "Meydan": (25.1780, 55.2840),
        "Al Furjan": (25.0580, 55.1180),
        "Dubai South": (24.9180, 55.1680),
        "Town Square": (25.0780, 55.2580),
    }

    result = structured_search("", filters=None)
    scores = {s["community"]: s for s in result["community_scores"]}

    # Build map data
    map_data = []
    for comm, (lat, lng) in COMMUNITY_COORDS.items():
        if comm in scores:
            s = scores[comm]
            map_data.append({
                "community": comm,
                "lat": lat,
                "lng": lng,
                "net_yield": s["avg_net_yield_pct"],
                "composite_score": s["composite_score"],
                "recommendation": s["recommendation"],
                "avg_price": s["avg_price"],
            })

    import pandas as pd
    df = pd.DataFrame(map_data)

    st.map(df, latitude="lat", longitude="lng", size=20000, color="composite_score")

    # Legend
    st.markdown("**Color:** Composite score (brighter = higher score)")
    st.markdown("**Size:** Fixed (zoom to see individual communities)")

    # Community list
    st.subheader("All Communities")
    for s in sorted(scores.values(), key=lambda x: x["composite_score"], reverse=True):
        rec_icon = REC_ICONS.get(s["recommendation"], "⚪")
        st.markdown(
            f"{rec_icon} **{s['community']}** — Score: {s['composite_score']:.0f}/100 | "
            f"Net Yield: {s['avg_net_yield_pct']:.1f}% | Avg Price: AED {s['avg_price']:,.0f}"
        )

# --- Export Section ---
st.sidebar.markdown("---")
st.sidebar.header("📥 Export Report")

if st.sidebar.button("Generate Excel Report"):
    with st.spinner("Generating Excel report..."):
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        generate_excel_report(tmp.name, interest_rate, tenure, down_payment_pct)
        with open(tmp.name, "rb") as f:
            st.sidebar.download_button(
                label="Download Excel",
                data=f.read(),
                file_name=f"dubai_investment_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        os.unlink(tmp.name)

if st.sidebar.button("Generate PDF Report"):
    with st.spinner("Generating PDF report..."):
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        generate_pdf_report(tmp.name, interest_rate, tenure, down_payment_pct)
        with open(tmp.name, "rb") as f:
            st.sidebar.download_button(
                label="Download PDF",
                data=f.read(),
                file_name=f"dubai_investment_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
            )
        os.unlink(tmp.name)

# --- Footer ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Architecture:** DuckDB (analytics) + ChromaDB (semantic) + LLM (generation)\n\n"
    "**Features:** Investment scoring, mortgage calculator, STR estimator, comparison tool, map view\n\n"
    "**Data:** 73 mock DLD transactions, 25 communities, 4 market reports"
)

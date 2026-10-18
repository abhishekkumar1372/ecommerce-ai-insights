"""AI Insights app.  Run:  streamlit run app/streamlit_app.py"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import ui

from ecom.ai import anomalies, db, insights, text_to_sql
from ecom.ai.llm import provider

st.set_page_config(page_title="E-commerce AI Insights", page_icon="📊", layout="wide")
ui.setup()

EXAMPLES = [
    "Which 5 categories made the most revenue?",
    "Which states have the worst late-delivery rate?",
    "How did monthly revenue change in 2017?",
    "What is the average review score for late vs on-time orders?",
]

has_key = provider() is not None
with st.sidebar:
    st.markdown("### 📊 AI Insights")
    if has_key:
        st.markdown(ui.pill(f"● Model: {provider().title()}", "ok"), unsafe_allow_html=True)
    else:
        st.markdown(ui.pill("● No model key", "warn"), unsafe_allow_html=True)
        st.caption("Add GEMINI_API_KEY (free) or ANTHROPIC_API_KEY to `.env` to generate new insights.")
    st.divider()
    st.markdown("**How it stays honest**")
    st.caption("1. KPIs come from SQL, not the model.\n\n"
               "2. The model must cite a fact for every number.\n\n"
               "3. Numbers that don't match the database are flagged.\n\n"
               "4. Generated SQL runs read-only, on approved tables only.")
    st.divider()
    st.caption("Olist Brazilian e-commerce data · PostgreSQL + pgvector · dbt")

ui.hero("E-commerce AI Insights",
        "Sales KPIs and AI-written analysis, with every number checked against the database.")

overview_tab, summary_tab, ask_tab, anomaly_tab, ops_tab = st.tabs(
    ["📈 Overview", "📝 Executive summary", "💬 Ask your data", "🚨 Anomalies", "⚙️ LLM usage"])


def badge(passed: bool) -> None:
    st.markdown(ui.check_pill(passed), unsafe_allow_html=True)


with overview_tab:
    monthly = pd.DataFrame(db.query("select * from kpi.kpi_monthly_sales order by month"))
    if monthly.empty:
        st.info("No data yet. Run the pipeline first.")
    else:
        monthly["month"] = pd.to_datetime(monthly["month"])
        # The last months of the dataset are partial, so compare the latest month with real volume
        full = monthly[monthly["orders"] >= 0.25 * monthly["orders"].median()]
        cur, prev = full.iloc[-1], full.iloc[-2] if len(full) > 1 else None

        def delta(col):
            return None if prev is None or not prev[col] else float(cur[col]) / float(prev[col]) - 1

        st.caption(f"Latest full month: **{cur['month']:%B %Y}**")
        cols = st.columns(5)
        with cols[0]:
            ui.kpi("Revenue", ui.money(cur["revenue"]), delta("revenue"))
        with cols[1]:
            ui.kpi("Orders", f"{int(cur['orders']):,}", delta("orders"))
        with cols[2]:
            ui.kpi("Avg order value", ui.money(cur["avg_order_value"]), delta("avg_order_value"))
        with cols[3]:
            ui.kpi("Avg review", f"{float(cur['avg_review_score']):.2f} ★", delta("avg_review_score"))
        with cols[4]:
            ui.kpi("Late deliveries", f"{float(cur['late_delivery_rate'] or 0):.1%}",
                   delta("late_delivery_rate"), good_when_up=False)

        st.write("")
        left, right = st.columns([3, 2])
        with left:
            st.markdown("#### Monthly revenue")
            base = alt.Chart(monthly).encode(x=alt.X("month:T", title=None))
            area = base.mark_area(opacity=.18, color=ui.BLUE, line={"color": ui.BLUE}).encode(
                y=alt.Y("revenue:Q", title="Revenue (R$)"),
                tooltip=[alt.Tooltip("month:T", format="%b %Y"), alt.Tooltip("revenue:Q", format=",.0f")])
            ma = base.mark_line(color=ui.TEAL, strokeDash=[5, 4]).encode(y="revenue_3m_moving_avg:Q")
            st.altair_chart((area + ma).properties(height=320), width="stretch")
            st.caption("Solid: revenue · Dashed: 3-month moving average")
        with right:
            st.markdown("#### Top categories")
            cats = pd.DataFrame(db.query(
                "select replace(category, '_', ' ') as category, revenue from kpi.kpi_category_pareto order by revenue_rank limit 8"))
            bars = alt.Chart(cats).mark_bar(cornerRadiusEnd=4, color=ui.BLUE).encode(
                x=alt.X("revenue:Q", title="Revenue (R$)"),
                y=alt.Y("category:N", sort="-x", title=None),
                tooltip=["category", alt.Tooltip("revenue:Q", format=",.0f")])
            st.altair_chart(bars.properties(height=320), width="stretch")

with summary_tab:
    top = st.columns([4, 1])
    with top[1]:
        if st.button("✨ Generate new", disabled=not has_key, width="stretch", type="primary"):
            with st.spinner("Querying KPIs and writing the summary..."):
                insights.generate()
    rows = db.query("select * from ai.ai_insights where kind = 'executive_summary' order by created_at desc limit 1")
    if not rows:
        st.info("No summary yet. Click **Generate new**.")
    else:
        r = rows[0]
        body = r["body"]
        with top[0]:
            st.markdown(f"### {body['headline']['text']}")
            badge(r["passed"])
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="card"><h4>✅ Wins</h4>' +
                        "".join(f"<p>{p['text']}</p>" for p in body["wins"]) + "</div>", unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card"><h4>⚠️ Risks</h4>' +
                        "".join(f"<p>{p['text']}</p>" for p in body["risks"]) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="card"><h4>🎯 Recommended actions</h4>' +
                    "".join(f"<p><b>{i}. {a['text']}</b><br>{a['rationale']}</p>"
                            for i, a in enumerate(body["actions"], 1)) + "</div>", unsafe_allow_html=True)
        with st.expander("Facts and the SQL behind them"):
            st.dataframe(pd.DataFrame(r["facts"])[["id", "label", "display", "source_sql"]],
                         width="stretch", hide_index=True)
        with st.expander("Fact-check report"):
            st.json(r["fact_check"])

with ask_tab:
    st.session_state.setdefault("chat", [])
    if not st.session_state.chat:
        st.markdown("**Try one of these:**")
        ex_cols = st.columns(len(EXAMPLES))
        for col, q in zip(ex_cols, EXAMPLES):
            if col.button(q, width="stretch", disabled=not has_key):
                st.session_state.pending = q

    def show(question, res):
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(res["answer"])
            if res["ok"]:
                badge(res["fact_check"]["passed"])
                df = pd.DataFrame(res["rows"])
                if res.get("chart") in ("bar", "line") and df.shape[1] >= 2:
                    chart_df = df.set_index(df.columns[0]).select_dtypes("number")
                    (st.bar_chart if res["chart"] == "bar" else st.line_chart)(chart_df, color=ui.BLUE
                                                                               if chart_df.shape[1] == 1 else None)
                st.dataframe(df, width="stretch", hide_index=True)
                for c in res.get("caveats", []):
                    st.caption(f"Note: {c}")
            with st.expander(f"SQL ({len(res['attempts'])} attempt(s))"):
                for a in res["attempts"]:
                    st.code(a["sql"], language="sql")
                    if a["error"]:
                        st.error(a["error"])

    for q, res in st.session_state.chat:
        show(q, res)
    question = st.chat_input("Ask a question about the sales data", disabled=not has_key)
    question = question or st.session_state.pop("pending", None)
    if question:
        with st.spinner("Writing and checking SQL..."):
            res = text_to_sql.ask(question)
        st.session_state.chat.append((question, res))
        st.rerun()

with anomaly_tab:
    found = anomalies.detect()
    daily = pd.DataFrame(db.query(
        "select purchased_at::date as day, sum(revenue) as revenue from marts.fct_order_items "
        "where order_status not in ('canceled', 'unavailable') group by 1 order by 1"
    ))
    m = st.columns(3)
    with m[0]:
        ui.kpi("Anomalous days", str(len(found)))
    with m[1]:
        ui.kpi("Threshold", f"{anomalies.Z_THRESHOLD}σ")
    with m[2]:
        ui.kpi("Baseline window", "28 days")
    st.write("")
    if not daily.empty:
        daily["day"] = pd.to_datetime(daily["day"])
        line = alt.Chart(daily).mark_line(color=ui.BLUE, strokeWidth=1.2).encode(
            x=alt.X("day:T", title=None), y=alt.Y("revenue:Q", title="Daily revenue (R$)"))
        layers = line
        if found:
            pts = pd.DataFrame(found)
            pts["day"] = pd.to_datetime(pts["date_day"])
            pts = pts.merge(daily, on="day")
            layers += alt.Chart(pts).mark_circle(size=110, color=ui.RED).encode(
                x="day:T", y="revenue:Q", tooltip=[alt.Tooltip("day:T"), alt.Tooltip("revenue:Q", format=",.0f")])
        st.altair_chart(layers.properties(height=300), width="stretch")
        st.caption("Red dots are days more than "
                   f"{anomalies.Z_THRESHOLD} standard deviations from their 28-day baseline.")
    st.dataframe(pd.DataFrame(found), width="stretch", hide_index=True)
    if found:
        c = st.columns([3, 1])
        day = c[0].selectbox("Explain a day", [a["date_day"] for a in found])
        c[1].write("")
        if c[1].button("✨ Explain with AI", disabled=not has_key, width="stretch", type="primary"):
            with st.spinner("Drilling down and writing the explanation..."):
                r = anomalies.explain(next(a for a in found if a["date_day"] == day))
            st.markdown(f"### {r['title']}")
            badge(r["passed"])
            st.write(r["body"]["explanation"])
            st.markdown(ui.pill(f"Hypothesis: {r['body']['likely_cause']}"), unsafe_allow_html=True)
            dims = list(r["body"]["drill_down"].items())
            for col, (dim, rows) in zip(st.columns(len(dims) or 1), dims):
                col.markdown(f"**By {dim}**")
                col.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

with ops_tab:
    usage = pd.DataFrame(db.query(
        "select purpose, model, count(*) as calls, sum(input_tokens) as input_tokens, "
        "sum(output_tokens) as output_tokens, round(avg(latency_ms)) as avg_latency_ms, "
        "sum(cost_usd) as cost_usd from ai.llm_calls group by 1, 2 order by 3 desc"
    ))
    if usage.empty:
        st.info("No model calls logged yet.")
    else:
        m = st.columns(4)
        with m[0]:
            ui.kpi("Model calls", f"{int(usage['calls'].sum()):,}")
        with m[1]:
            ui.kpi("Tokens", f"{int(usage['input_tokens'].sum() + usage['output_tokens'].sum()):,}")
        with m[2]:
            ui.kpi("Avg latency", f"{usage['avg_latency_ms'].astype(float).mean() / 1000:.1f}s")
        with m[3]:
            ui.kpi("Total cost", f"${float(usage['cost_usd'].sum() or 0):.4f}")
        st.write("")
        st.dataframe(usage, width="stretch", hide_index=True)

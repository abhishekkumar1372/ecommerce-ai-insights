"""AI Insights app.  Run:  streamlit run app/streamlit_app.py"""
import pandas as pd
import streamlit as st

from ecom.ai import anomalies, db, insights, text_to_sql
from ecom.ai.llm import provider

st.set_page_config(page_title="E-commerce AI Insights", layout="wide")
st.title("E-commerce AI Insights")
st.caption("Every number the AI writes is checked against the database. Hover the SQL to see where it came from.")

has_key = provider() is not None
if has_key:
    st.caption(f"Model provider: {provider()}")
else:
    st.warning("Set GEMINI_API_KEY (free) or ANTHROPIC_API_KEY to generate new insights. Saved insights still show below.")

summary_tab, ask_tab, anomaly_tab, ops_tab = st.tabs(["Executive summary", "Ask your data", "Anomalies", "LLM usage"])


def badge(passed: bool) -> str:
    return "✅ All numbers verified against the database" if passed else "⚠️ Some numbers could not be verified"


with summary_tab:
    if st.button("Generate new summary", disabled=not has_key):
        with st.spinner("Querying KPIs and writing the summary..."):
            insights.generate()
    rows = db.query("select * from ai.ai_insights where kind = 'executive_summary' order by created_at desc limit 1")
    if not rows:
        st.info("No summary yet.")
    else:
        r = rows[0]
        body = r["body"]
        st.subheader(body["headline"]["text"])
        st.write(badge(r["passed"]))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Wins**\n" + "\n".join(f"- {p['text']}" for p in body["wins"]))
        with c2:
            st.markdown("**Risks**\n" + "\n".join(f"- {p['text']}" for p in body["risks"]))
        st.markdown("**Recommended actions**")
        for i, a in enumerate(body["actions"], 1):
            st.markdown(f"{i}. **{a['text']}** {a['rationale']}")
        with st.expander("Facts and the SQL behind them"):
            st.dataframe(pd.DataFrame(r["facts"])[["id", "label", "display", "source_sql"]], use_container_width=True)
        with st.expander("Fact-check report"):
            st.json(r["fact_check"])

with ask_tab:
    question = st.chat_input("Ask a question, e.g. Which states have the worst late-delivery rate?")
    if question and has_key:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"), st.spinner("Writing SQL..."):
            res = text_to_sql.ask(question)
            st.write(res["answer"])
            if res["ok"]:
                st.caption(badge(res["fact_check"]["passed"]))
                df = pd.DataFrame(res["rows"])
                if res.get("chart") in ("bar", "line") and df.shape[1] >= 2:
                    chart_df = df.set_index(df.columns[0]).select_dtypes("number")
                    (st.bar_chart if res["chart"] == "bar" else st.line_chart)(chart_df)
                st.dataframe(df, use_container_width=True)
                for c in res.get("caveats", []):
                    st.caption(f"Note: {c}")
            with st.expander(f"SQL ({len(res['attempts'])} attempt(s))"):
                for a in res["attempts"]:
                    st.code(a["sql"], language="sql")
                    if a["error"]:
                        st.error(a["error"])

with anomaly_tab:
    found = anomalies.detect()
    daily = db.query(
        "select purchased_at::date as day, sum(revenue) as revenue from marts.fct_order_items "
        "where order_status not in ('canceled', 'unavailable') group by 1 order by 1"
    )
    st.line_chart(pd.DataFrame(daily).set_index("day"))
    st.write(f"{len(found)} days are more than {anomalies.Z_THRESHOLD} standard deviations from their 28-day baseline.")
    st.dataframe(pd.DataFrame(found), use_container_width=True)
    if found:
        day = st.selectbox("Explain a day", [a["date_day"] for a in found])
        if st.button("Explain with AI", disabled=not has_key):
            r = anomalies.explain(next(a for a in found if a["date_day"] == day))
            st.subheader(r["title"])
            st.write(r["body"]["explanation"])
            st.caption(f"Hypothesis: {r['body']['likely_cause']}  ·  {badge(r['passed'])}")
            for dim, rows in r["body"]["drill_down"].items():
                st.markdown(f"**By {dim}**")
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

with ops_tab:
    usage = db.query(
        "select purpose, model, count(*) as calls, sum(input_tokens) as input_tokens, "
        "sum(output_tokens) as output_tokens, round(avg(latency_ms)) as avg_latency_ms, "
        "sum(cost_usd) as cost_usd from ai.llm_calls group by 1, 2 order by 3 desc"
    )
    st.dataframe(pd.DataFrame(usage), use_container_width=True)

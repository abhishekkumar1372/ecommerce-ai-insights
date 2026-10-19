"""Shared styling for the Streamlit app: CSS, KPI cards, badges and chart theme."""
import altair as alt
import streamlit as st

BLUE, TEAL, AMBER, RED, GREY = "#2F6FEB", "#14A38B", "#F2A33A", "#D9534F", "#5B6B7F"

CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 1300px;}
.hero {background: linear-gradient(120deg, #1E3A8A 0%, #2F6FEB 60%, #14A38B 100%);
       color: #fff; border-radius: 16px; padding: 1.6rem 2rem; margin-bottom: 1.2rem;}
.hero h1 {color: #fff; font-size: 1.9rem; margin: 0 0 .3rem 0; padding: 0;}
.hero p {color: rgba(255,255,255,.85); margin: 0; font-size: 1rem;}
.kpi {background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1rem 1.2rem;
      box-shadow: 0 1px 2px rgba(16,24,40,.05); height: 100%;}
.kpi .label {color: #5B6B7F; font-size: .8rem; text-transform: uppercase; letter-spacing: .04em;}
.kpi .value {color: #1F2937; font-size: 1.7rem; font-weight: 650; margin: .2rem 0;}
.kpi .delta {font-size: .85rem; font-weight: 600;}
.up {color: #14A38B;} .down {color: #D9534F;} .flat {color: #5B6B7F;}
.card {background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1.1rem 1.3rem;
       margin-bottom: 1rem;}
.card h4 {margin-top: 0;}
.pill {display: inline-block; border-radius: 999px; padding: .2rem .7rem; font-size: .8rem; font-weight: 600;}
.pill.ok {background: #E3F6F2; color: #0E7A68;} .pill.warn {background: #FDF1E1; color: #A3610B;}
.pill.info {background: #E6EEFD; color: #1E4FBF;}
.stTabs [data-baseweb="tab-list"] {gap: .4rem;}
.stTabs [data-baseweb="tab"] {background: #fff; border: 1px solid #E5E7EB; border-radius: 10px;
                              padding: .5rem 1rem;}
.stTabs [aria-selected="true"] {border-color: #2F6FEB; color: #2F6FEB;}
</style>
"""


def setup() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    alt.theme.register("ecom", enable=True)(lambda: {"config": {
        "range": {"category": [BLUE, TEAL, AMBER, RED, "#7A5AF8", GREY]},
        "axis": {"labelColor": GREY, "titleColor": GREY, "gridColor": "#EEF1F5", "domain": False},
        "view": {"stroke": None},
        "font": "sans-serif",
    }})


def hero(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def kpi(label: str, value: str, delta: float | None = None, good_when_up: bool = True) -> None:
    if delta is None:
        d = '<div class="delta flat">&nbsp;</div>'
    else:
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "■"
        cls = "flat" if delta == 0 else "up" if (delta > 0) == good_when_up else "down"
        d = f'<div class="delta {cls}">{arrow} {abs(delta):.1%} vs last month</div>'
    st.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div>{d}</div>',
                unsafe_allow_html=True)


def pill(text: str, kind: str = "info") -> str:
    return f'<span class="pill {kind}">{text}</span>'


def check_pill(passed: bool) -> str:
    return pill("✓ All numbers verified", "ok") if passed else pill("⚠ Some numbers unverified", "warn")


def money(x) -> str:
    x = float(x or 0)
    return f"R${x / 1e6:.2f}M" if x >= 1e6 else f"R${x / 1e3:.1f}K" if x >= 1e4 else f"R${x:,.2f}"

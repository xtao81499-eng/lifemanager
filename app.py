"""
Life Manager — Dashboard
Apple-inspired Light Clean Design
"""
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta

from core.calendar_sync import fetch_all_events
from core.data_processing import (
    events_to_dataframe,
    daily_summary,
    category_summary,
    sleep_work_correlation,
)
from core.gdrive import get_reflection_insights
from core.manual_habits import get_checked_dates, toggle as toggle_habit

from pathlib import Path as _Path
_heatmap_component = components.declare_component(
    "habit_heatmap",
    path=str(_Path(__file__).parent / "st_heatmap_frontend"),
)

# ─── Page Config ─────────────────────────────────────────────
st.set_page_config(
    page_title="Life Manager",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── Access Gate（仅公网/云端启用） ──────────────────────────
def _login_gate() -> None:
    """密码门：仅当 secrets 里配了 app_password 时生效。

    本地桌面版没有 secrets → 直接放行，不影响使用。
    云端公网访问 → 必须输入正确密码才能看到数据，挡住陌生人。
    """
    try:
        password = st.secrets.get("app_password")
    except Exception:
        password = None
    if not password:
        return  # 未配置密码（本地）→ 放行

    if st.session_state.get("_authed"):
        return

    st.markdown(
        "<div style='max-width:360px;margin:15vh auto 0;text-align:center;'>"
        "<h1 style='font-weight:600;'>Life Manager</h1>"
        "<p style='color:#86868B;'>请输入访问密码</p></div>",
        unsafe_allow_html=True,
    )
    with st.container():
        _, mid, _ = st.columns([1, 1.4, 1])
        with mid:
            entered = st.text_input(
                "密码", type="password", label_visibility="collapsed",
                placeholder="密码",
            )
            if entered:
                if entered == password:
                    st.session_state["_authed"] = True
                    st.rerun()
                else:
                    st.error("密码错误")
    st.stop()


_login_gate()

# ─── iOS "Add to Home Screen" (PWA) meta tags ────────────────
# Streamlit owns <head>, so inject from a component into the parent document.
_ICON_URL = "./app/static/apple-touch-icon.png"
components.html(
    f"""
    <script>
    (function() {{
        const doc = window.parent.document;
        const head = doc.head;
        function upsert(selector, make) {{
            if (!head.querySelector(selector)) head.appendChild(make());
        }}
        // Home-screen icon
        upsert('link[rel="apple-touch-icon"]', () => {{
            const l = doc.createElement('link');
            l.rel = 'apple-touch-icon';
            l.href = '{_ICON_URL}';
            return l;
        }});
        // Launch full-screen (no Safari chrome) once added to home screen
        upsert('meta[name="apple-mobile-web-app-capable"]', () => {{
            const m = doc.createElement('meta');
            m.name = 'apple-mobile-web-app-capable';
            m.content = 'yes';
            return m;
        }});
        // App name under the icon
        upsert('meta[name="apple-mobile-web-app-title"]', () => {{
            const m = doc.createElement('meta');
            m.name = 'apple-mobile-web-app-title';
            m.content = 'Life Manager';
            return m;
        }});
        // Status bar style
        upsert('meta[name="apple-mobile-web-app-status-bar-style"]', () => {{
            const m = doc.createElement('meta');
            m.name = 'apple-mobile-web-app-status-bar-style';
            m.content = 'default';
            return m;
        }});
    }})();
    </script>
    """,
    height=0,
)

# ─── Apple Light CSS ─────────────────────────────────────────
# Design tokens (locked — Apple-clean light)
#   Accent:  #0A84FF   single accent, used identically everywhere
#   Surface: #FFFFFF    Tile: #F5F5F7
#   Text:    #1D1D1F    muted #86868B    faint #AEAEB2
#   Radius:  compact 12px (buttons/inputs/info) · cards 18px · pills 999px
#   Shadow:  cool-tinted rgba(60,60,67,·) — never pure black
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

    .stApp { background: #FFFFFF; }

    .block-container {
        padding: 2rem 3rem !important;
        max-width: 1400px;
    }

    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }

    .app-header {
        padding: 1.5rem 0 0.5rem 0;
    }
    .app-header h1 {
        font-size: 2rem;
        font-weight: 700;
        color: #1D1D1F;
        letter-spacing: -0.03em;
        margin: 0;
    }
    .app-header p {
        font-size: 0.9rem;
        color: #86868B;
        font-weight: 400;
        margin-top: 0.2rem;
    }

    .card {
        background: #F5F5F7;
        border-radius: 18px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #FFFFFF;
        border: 1px solid rgba(60,60,67,0.06);
        border-radius: 18px;
        padding: 1.3rem 1.5rem;
        text-align: left;
        box-shadow: 0 1px 3px rgba(60,60,67,0.04), 0 6px 16px rgba(60,60,67,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 2px 6px rgba(60,60,67,0.06), 0 12px 28px rgba(60,60,67,0.09);
    }

    /* Mobile collapse: 4 → 2 → 1 */
    @media (max-width: 900px) {
        .metric-grid { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 520px) {
        .metric-grid { grid-template-columns: 1fr; }
    }
    .metric-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #86868B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.4rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1D1D1F;
        letter-spacing: -0.02em;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #86868B;
        margin-top: 0.2rem;
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1D1D1F;
        margin: 1.5rem 0 0.8rem 0;
        letter-spacing: -0.01em;
    }

    .stDateInput > div > div {
        border-radius: 12px !important;
    }
    .stButton button {
        background: #F5F5F7 !important;
        border: none !important;
        border-radius: 12px !important;
        color: #1D1D1F !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
    }
    .stButton button:hover {
        background: #E8E8ED !important;
    }
    .stButton button:active {
        transform: scale(0.97);
    }

    .insight-text {
        color: #86868B;
        font-size: 0.8rem;
        text-align: center;
        margin-top: 0.3rem;
    }

    .stInfo, .stWarning {
        background: #F5F5F7 !important;
        border: none !important;
        border-radius: 12px !important;
        color: #86868B !important;
    }

    .habit-card {
        background: #F5F5F7;
        border-radius: 18px;
        padding: 1.2rem;
        text-align: center;
    }
    .habit-name {
        font-size: 0.7rem;
        font-weight: 600;
        color: #86868B;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.4rem;
    }
    .habit-value {
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .habit-sub {
        font-size: 0.65rem;
        color: #86868B;
        margin-top: 0.15rem;
    }

    .quick-btn {
        display: inline-block;
        padding: 0.35rem 0.9rem;
        background: #F5F5F7;
        border-radius: 999px;
        color: #1D1D1F;
        font-size: 0.8rem;
        font-weight: 500;
        cursor: pointer;
        margin-right: 0.4rem;
        text-decoration: none;
    }
    .quick-btn-active {
        background: #1D1D1F;
        color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)

# ─── Color Palette (from Google Calendar API backgroundColor) ──
COLORS = {
    "工作": "#f83a22",
    "学习": "#16a765",
    "运动": "#039be5",
    "睡眠": "#3f51b5",
    "社交": "#9a9cff",
    "餐饮": "#f4511e",
    "生活": "#b99aff",
    "通勤": "#b4b8b1",
    "拖延": "#fbd14a",
    "家庭": "#f4511e",
    "基础/洗漱": "#33b679",
    "深度复盘/灵感": "#9fe1e7",
}

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, -apple-system, sans-serif", color="#86868B", size=12),
    margin=dict(l=20, r=20, t=30, b=30),
)


# ─── Data Loading ────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data(start_date: date, end_date: date):
    days_back = (date.today() - start_date).days + 1
    events = fetch_all_events(days=days_back)
    df = events_to_dataframe(events)
    if df.empty:
        return df
    df = df[df["category"].isin(COLORS.keys())]
    mask = (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
    return df[mask].reset_index(drop=True)


# ─── Header ──────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>Life Manager</h1>
    <p>Personal Performance Analytics</p>
</div>
""", unsafe_allow_html=True)

# ─── Date Controls ───────────────────────────────────────────
today = date.today()

if "start_date" not in st.session_state:
    st.session_state.start_date = today - timedelta(days=6)
if "end_date" not in st.session_state:
    st.session_state.end_date = today

ctrl1, ctrl2, ctrl3, ctrl4, ctrl5, ctrl6 = st.columns([1.2, 1.2, 0.6, 0.6, 0.6, 2.4])

with ctrl1:
    start_date = st.date_input("开始", st.session_state.start_date, key="start_input", label_visibility="collapsed")
    st.session_state.start_date = start_date
with ctrl2:
    end_date = st.date_input("结束", st.session_state.end_date, key="end_input", label_visibility="collapsed")
    st.session_state.end_date = end_date
with ctrl3:
    if st.button("今天"):
        st.session_state.start_date = today
        st.session_state.end_date = today
        st.rerun()
with ctrl4:
    if st.button("本周"):
        st.session_state.start_date = today - timedelta(days=today.weekday())
        st.session_state.end_date = today
        st.rerun()
with ctrl5:
    if st.button("本月"):
        st.session_state.start_date = today.replace(day=1)
        st.session_state.end_date = today
        st.rerun()

df = load_data(start_date, end_date)

date_span = (end_date - start_date).days + 1

if df.empty:
    st.markdown(f"""
    <div class="card" style="text-align:center; padding:3rem;">
        <p style="color:#86868B; margin:0; font-size:0.9rem;">{start_date.strftime('%m/%d')} — {end_date.strftime('%m/%d')} 暂无数据</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ─── KPI Metrics ─────────────────────────────────────────────
daily = daily_summary(df)
cat = category_summary(df)

total_hours = df["duration_hours"].sum()
avg_score = df["score"].dropna().mean()
total_events = len(df)
top_category = cat.iloc[0]["category"] if not cat.empty else "—"
active_days = daily["date"].nunique() if not daily.empty else 0

st.markdown(f"""
<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-label">记录时长</div>
        <div class="metric-value">{total_hours:.0f}<span style="font-size:1rem;color:#86868B">h</span></div>
        <div class="metric-sub">{active_days} 个活跃日</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">平均评分</div>
        <div class="metric-value">{avg_score:.1f}<span style="font-size:1rem;color:#86868B">/10</span></div>
        <div class="metric-sub">基于 {len(df['score'].dropna())} 次评价</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">事件总数</div>
        <div class="metric-value">{total_events}</div>
        <div class="metric-sub">日均 {total_events/max(active_days,1):.1f} 条</div>
    </div>
    <div class="metric-card">
        <div class="metric-label">最投入</div>
        <div class="metric-value" style="font-size:1.5rem;">{top_category}</div>
        <div class="metric-sub">{cat.iloc[0]['total_hours']:.1f}h / {cat.iloc[0]['count']:.0f} 次</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Global Two-Column Layout ─────────────────────────────────
_col_main, _col_habit = st.columns([3, 1], gap="medium")

with _col_habit:
    st.markdown('<div class="section-title">习惯追踪</div>', unsafe_allow_html=True)

    manual_habits = ["睡前护肤"]
    heatmap_cats = ["运动", "学习", "深度复盘/灵感"]
    heatmap_data = df[df["category"].isin(heatmap_cats)].copy()
    date_range = pd.date_range(start=start_date, end=max(end_date, today), freq="D")

    habit_rows = []
    for cat_name in heatmap_cats:
        cat_events = heatmap_data[heatmap_data["category"] == cat_name]
        daily_scores = cat_events.groupby("date")["score"].mean()
        daily_details = cat_events.groupby("date")["detail"].apply(
            lambda x: "\n".join(s.strip() for s in x if str(s).strip())
        ) if "detail" in cat_events.columns else pd.Series(dtype=str)
        cells = []
        for d in date_range:
            if d in daily_scores.index:
                raw = daily_scores[d]
                score_val = f"{raw:.1f}" if pd.notna(raw) else ""
                detail_text = str(daily_details.get(d, "")).strip() if d in daily_details.index else ""
                cells.append({"active": True, "score": score_val, "detail": detail_text})
            else:
                cells.append({"active": False, "score": "", "detail": ""})
        habit_rows.append({"label": cat_name, "cells": cells, "manual": False})

    for habit_name in manual_habits:
        checked_dates = get_checked_dates(habit_name)
        cells = []
        for d in date_range:
            date_iso = d.strftime("%Y-%m-%d")
            cells.append({"active": date_iso in checked_dates, "score": "", "detail": ""})
        habit_rows.append({"label": habit_name, "cells": cells, "manual": True})

    from datetime import datetime as _dt
    _today_str = _dt.now().strftime("%Y-%m-%d")
    _dates_list = [{"iso": d.strftime("%Y-%m-%d"), "display": d.strftime("%m/%d"), "weekday": ["一","二","三","四","五","六","日"][d.weekday()]} for d in date_range]

    _vert_data = {"dates": _dates_list, "habits": habit_rows, "today_iso": _today_str}
    _vert_height = 120 + len(date_range) * 32
    toggle_result = _heatmap_component(grid_data=_vert_data, today_iso=_today_str, height=_vert_height, key="habit_heatmap", default=None)
    if toggle_result and toggle_result != st.session_state.get("_last_toggle"):
        st.session_state["_last_toggle"] = toggle_result
        parts = toggle_result.split("|")
        if len(parts) >= 3:
            habit, date_str, action = parts[0], parts[1], parts[2]
            if action == "check":
                checked = get_checked_dates(habit)
                if date_str not in checked:
                    toggle_habit(habit, date_str)
            elif action == "uncheck":
                checked = get_checked_dates(habit)
                if date_str in checked:
                    toggle_habit(habit, date_str)
            st.rerun()

with _col_main:
    # ─── Time Distribution ─────────────────────────────────────
    st.markdown('<div class="section-title">时间分布</div>', unsafe_allow_html=True)

    r1c1, r1c2 = st.columns([3, 2])

    with r1c1:
        if not cat.empty:
            fig_bar = go.Figure()
            for _, row in cat.iterrows():
                color = COLORS.get(row["category"], "#8E8E93")
                fig_bar.add_trace(go.Bar(
                    y=[row["category"]],
                    x=[row["total_hours"]],
                    orientation="h",
                    marker=dict(color=color, cornerradius=6),
                    text=f'{row["total_hours"]:.1f}h',
                    textposition="outside",
                    textfont=dict(color="#1D1D1F", size=11),
                    showlegend=False,
                ))
            fig_bar.update_layout(
                **PLOT_LAYOUT,
                height=300,
                barmode="stack",
                yaxis=dict(categoryorder="total ascending", showgrid=False, color="#1D1D1F"),
                xaxis=dict(showgrid=False, showticklabels=False),
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    with r1c2:
        if not cat.empty:
            _pie_total = cat["total_hours"].sum()
            _pie_text = [
                f"{v / _pie_total * 100:.0f}%" if _pie_total and v / _pie_total >= 0.04 else ""
                for v in cat["total_hours"]
            ]
            fig_pie = go.Figure(data=[go.Pie(
                labels=cat["category"],
                values=cat["total_hours"],
                hole=0.65,
                marker=dict(colors=[COLORS.get(c, "#8E8E93") for c in cat["category"]]),
                text=_pie_text,
                textinfo="text",
                textposition="outside",
                textfont=dict(size=11, color="#1D1D1F"),
                hovertemplate="%{label}<br>%{value:.1f}h · %{percent}<extra></extra>",
            )])
            fig_pie.update_layout(**PLOT_LAYOUT, height=300, showlegend=False)
            fig_pie.add_annotation(
                text=f"<b>{total_hours:.0f}h</b>",
                font=dict(size=20, color="#1D1D1F"),
                showarrow=False,
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

    # ─── Score Trend ───────────────────────────────────────────
    if date_span > 1:
        st.markdown('<div class="section-title">评分趋势</div>', unsafe_allow_html=True)

        if not daily.empty and "avg_score" in daily.columns:
            fig_trend = go.Figure()

            fig_trend.add_trace(go.Scatter(
                x=daily["date"],
                y=daily["avg_score"],
                mode="lines",
                line=dict(color="#0A84FF", width=2.5, shape="spline"),
                fill="tozeroy",
                fillcolor="rgba(10, 132, 255, 0.06)",
                hovertemplate="%{x|%m/%d}<br>评分: %{y:.1f}<extra></extra>",
            ))

            fig_trend.add_trace(go.Scatter(
                x=daily["date"],
                y=daily["avg_score"],
                mode="markers",
                marker=dict(size=7, color="#0A84FF", line=dict(width=2, color="#FFF")),
                showlegend=False,
                hoverinfo="skip",
            ))

            fig_trend.add_hline(
                y=avg_score, line_dash="dot", line_color="rgba(142,142,147,0.3)", line_width=1,
                annotation_text=f"平均 {avg_score:.1f}",
                annotation_font=dict(color="#86868B", size=11),
                annotation_position="right",
            )

            fig_trend.update_layout(
                **PLOT_LAYOUT,
                height=280,
                yaxis=dict(range=[0, 10], showgrid=True, gridcolor="rgba(0,0,0,0.04)",
                           zeroline=False, dtick=2, color="#1D1D1F"),
                xaxis=dict(showgrid=False, tickformat="%m/%d", color="#1D1D1F"),
                showlegend=False,
            )
            st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

    # ─── Reflection Insights ──────────────────────────────────
    st.markdown('<div class="section-title">反思洞察</div>', unsafe_allow_html=True)

    @st.cache_data(ttl=600)
    def _load_insights():
        try:
            return get_reflection_insights()
        except Exception:
            return {"title": "", "date": "", "suggestions": [], "is_today": False}

    insights = _load_insights()

    if insights["suggestions"]:
        items_html = ""
        for i, s in enumerate(insights["suggestions"]):
            items_html += f"""
            <div class="ri-item" style="animation-delay: {i * 0.06}s">
                <div class="ri-bullet"></div>
                <span>{s}</span>
            </div>"""

        date_label = "今日" if insights["is_today"] else insights["date"]

        reflection_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
            * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }}
            body {{ background: transparent; }}
            .ri-card {{
                background: #FFFFFF;
                border-radius: 18px;
                padding: 1.8rem 2rem;
                box-shadow: 0 1px 12px rgba(60,60,67,0.05), 0 0 1px rgba(60,60,67,0.10);
            }}
            .ri-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 1.2rem;
            }}
            .ri-title {{
                font-size: 0.95rem;
                font-weight: 600;
                color: #0A84FF;
            }}
            .ri-date {{
                font-size: 0.7rem;
                font-weight: 500;
                color: #86868B;
                background: #F5F5F7;
                padding: 0.25rem 0.7rem;
                border-radius: 999px;
            }}
            .ri-source {{
                font-size: 0.7rem;
                color: #AEAEB2;
                margin-bottom: 1rem;
                font-weight: 400;
            }}
            .ri-item {{
                display: flex;
                align-items: flex-start;
                gap: 0.75rem;
                padding: 0.65rem 0;
                border-bottom: 1px solid rgba(0,0,0,0.03);
                opacity: 0;
                animation: fadeIn 0.35s ease forwards;
            }}
            .ri-item:last-child {{ border-bottom: none; }}
            .ri-bullet {{
                width: 7px;
                height: 7px;
                min-width: 7px;
                border-radius: 50%;
                background: #0A84FF;
                margin-top: 0.45rem;
            }}
            .ri-item span {{
                font-size: 0.82rem;
                font-weight: 400;
                color: #1D1D1F;
                line-height: 1.55;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(4px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
        </style>
        </head>
        <body>
        <div class="ri-card">
            <div class="ri-header">
                <div class="ri-title">Reflection Insights</div>
                <div class="ri-date">{date_label}</div>
            </div>
            <div class="ri-source">来源：{insights['title']}</div>
            {items_html}
        </div>
        </body>
        </html>
        """
        ri_height = 120 + len(insights["suggestions"]) * 42
        components.html(reflection_html, height=ri_height, scrolling=False)

    else:
        empty_html = """
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }
            body { background: transparent; }
            .ri-card {
                background: #FFFFFF;
                border-radius: 18px;
                padding: 2.5rem 2rem;
                box-shadow: 0 1px 12px rgba(60,60,67,0.05), 0 0 1px rgba(60,60,67,0.10);
                text-align: center;
            }
            .ri-empty-icon {
                font-size: 2rem;
                margin-bottom: 0.6rem;
                opacity: 0.4;
            }
            .ri-empty-text {
                font-size: 0.85rem;
                color: #AEAEB2;
                font-weight: 400;
            }
        </style>
        </head>
        <body>
        <div class="ri-card">
            <div class="ri-empty-icon">◇</div>
            <div class="ri-empty-text">等待今日系统补丁记录...</div>
        </div>
        </body>
        </html>
        """
        components.html(empty_html, height=140, scrolling=False)

    # ─── Correlation ───────────────────────────────────────────
    st.markdown('<div class="section-title">睡眠 × 工作效率</div>', unsafe_allow_html=True)

    corr_data = sleep_work_correlation(df)
    if not corr_data.empty and len(corr_data) >= 3:
        fig_corr = go.Figure()

        fig_corr.add_trace(go.Scatter(
            x=corr_data["sleep_hours"],
            y=corr_data["work_score"],
            mode="markers",
            marker=dict(
                size=12,
                color=corr_data["work_score"],
                colorscale=[[0, "#FF3B30"], [0.5, "#FF9500"], [1, "#34C759"]],
                cmin=0, cmax=10,
                line=dict(width=1.5, color="#FFFFFF"),
            ),
            hovertemplate="睡眠: %{x:.1f}h<br>工作评分: %{y:.1f}<extra></extra>",
        ))

        if len(corr_data) >= 2:
            z = np.polyfit(corr_data["sleep_hours"], corr_data["work_score"], 1)
            p = np.poly1d(z)
            x_line = np.linspace(corr_data["sleep_hours"].min(), corr_data["sleep_hours"].max(), 50)
            fig_corr.add_trace(go.Scatter(
                x=x_line, y=p(x_line),
                mode="lines",
                line=dict(color="rgba(142,142,147,0.4)", dash="dot", width=1.5),
                showlegend=False,
                hoverinfo="skip",
            ))

        r_value = corr_data["sleep_hours"].corr(corr_data["work_score"])
        fig_corr.update_layout(
            **PLOT_LAYOUT,
            height=300,
            xaxis=dict(title="睡眠时长 (h)", showgrid=True, gridcolor="rgba(0,0,0,0.04)",
                       zeroline=False, color="#1D1D1F"),
            yaxis=dict(title="次日工作评分", showgrid=True, gridcolor="rgba(0,0,0,0.04)",
                       range=[0, 10], zeroline=False, color="#1D1D1F"),
            showlegend=False,
        )
        st.plotly_chart(fig_corr, use_container_width=True, config={"displayModeBar": False})

        if r_value > 0.3:
            insight = "睡眠充足时工作表现明显更好"
        elif r_value < -0.3:
            insight = "过多睡眠似乎降低了工作效率"
        else:
            insight = "睡眠时长与工作效率暂无明显关联"

        st.markdown(f'<p class="insight-text">r = {r_value:.2f} · {insight} · {len(corr_data)} 天数据</p>', unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="card" style="text-align:center;">
            <p style="color:#86868B; margin:0; font-size:0.85rem;">需要至少 3 天睡眠+工作数据才能分析</p>
        </div>
        """, unsafe_allow_html=True)

# ─── Footer ──────────────────────────────────────────────────
st.markdown('<br><p style="color:#D1D1D6; text-align:center; font-size:0.7rem;">Life Manager v0.2 · 界面精修</p>', unsafe_allow_html=True)

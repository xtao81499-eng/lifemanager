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

# ─── Color Palette (matching Google Calendar) ────────────────
COLORS = {
    "工作": "#f83a22",
    "学习": "#16a765",
    "运动": "#039be5",
    "睡眠": "#3f51b5",
    "社交": "#9a9cff",
    "餐饮": "#33b679",
    "生活": "#fbd14a",
    "通勤": "#b4b8b1",
    "拖延": "#b99aff",
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

# ─── Row 1: Time Distribution ───────────────────────────────
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
        # Only label slices >= 4%; blank the rest to avoid leader-line clutter
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

# ─── Row 2: Score Trend ─────────────────────────────────────
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

# ─── Row 3: Habit Heatmap (iOS-style grid) ──────────────────
st.markdown('<div class="section-title">习惯追踪</div>', unsafe_allow_html=True)

# Handle manual habit toggle via query params
_toggle_param = st.query_params.get("_habit_toggle")
if _toggle_param:
    parts = _toggle_param.split("|", 1)
    if len(parts) == 2:
        toggle_habit(parts[0], parts[1])
    st.query_params.clear()
    st.rerun()

manual_habits = ["睡前护肤"]

# Manual habit toggle — today's check-in (above heatmap for visibility)
def _do_toggle(habit, d):
    toggle_habit(habit, d)

for habit_name in manual_habits:
    today_iso = date.today().strftime("%Y-%m-%d")
    checked_dates = get_checked_dates(habit_name)
    is_checked = today_iso in checked_dates
    st.toggle(
        f"{habit_name} · 今日打卡",
        value=is_checked,
        key=f"htoggle_{habit_name}",
        on_change=_do_toggle,
        args=(habit_name, today_iso),
    )

heatmap_cats = ["运动", "学习", "深度复盘/灵感"]
heatmap_data = df[df["category"].isin(heatmap_cats)].copy()
date_range = pd.date_range(start=start_date, end=end_date, freq="D")
weekday_labels = ["一", "二", "三", "四", "五", "六", "日"]

# Build grid data: for each habit × each date, check if active & get score
import html as _html
import json as _json
grid_rows_html = ""
for cat_name in heatmap_cats:
    cat_events = heatmap_data[heatmap_data["category"] == cat_name]
    daily_scores = cat_events.groupby("date")["score"].mean()
    daily_details = cat_events.groupby("date")["detail"].apply(
        lambda x: "\n".join(s.strip() for s in x if str(s).strip())
    ) if "detail" in cat_events.columns else pd.Series(dtype=str)

    cells_html_parts = []
    for d in date_range:
        if d in daily_scores.index:
            date_str = d.strftime("%m月%d日")
            score_val = f"{daily_scores[d]:.1f}" if pd.notna(daily_scores[d]) else ""
            detail_text = str(daily_details.get(d, "")).strip() if d in daily_details.index else ""
            attrs = f'data-date="{date_str}" data-score="{score_val}" data-detail="{_html.escape(detail_text)}"'
            cells_html_parts.append(f'<div class="hm-cell hm-active" {attrs}></div>')
        else:
            date_str = d.strftime("%m月%d日")
            cells_html_parts.append(f'<div class="hm-cell hm-empty" data-date="{date_str}"></div>')
    cells_all = "".join(cells_html_parts)
    active_count = sum(1 for d in date_range if d in daily_scores.index)
    streak_text = f"{active_count}/{len(date_range)}"
    grid_rows_html += f"""
        <div class="hm-label">{cat_name}</div>
        {cells_all}
        <div class="hm-streak">{streak_text}</div>
    """

# Manual habit rows (clickable, local storage)
for habit_name in manual_habits:
    checked_dates = get_checked_dates(habit_name)
    manual_cells_parts = []
    manual_active = 0
    for d in date_range:
        date_iso = d.strftime("%Y-%m-%d")
        date_display = d.strftime("%m月%d日")
        if date_iso in checked_dates:
            manual_cells_parts.append(
                f'<div class="hm-cell hm-active hm-manual" data-habit="{habit_name}" data-iso="{date_iso}" data-date="{date_display}"></div>'
            )
            manual_active += 1
        else:
            manual_cells_parts.append(
                f'<div class="hm-cell hm-empty hm-manual" data-habit="{habit_name}" data-iso="{date_iso}" data-date="{date_display}"></div>'
            )
    manual_cells_all = "".join(manual_cells_parts)
    manual_streak = f"{manual_active}/{len(date_range)}"
    grid_rows_html += f"""
        <div class="hm-label">{habit_name}</div>
        {manual_cells_all}
        <div class="hm-streak">{manual_streak}</div>
    """

# Date header row
date_header_html = ""
for d in date_range:
    wd = d.weekday()
    date_header_html += f'<div class="hm-date-label">{d.strftime("%d")}<br><span>{weekday_labels[wd]}</span></div>'

num_days = len(date_range)
cell_size = max(16, min(28, 700 // num_days))
grid_width = 88 + num_days * (cell_size + 3) + 60
grid_height = 80 + (len(heatmap_cats) + len(manual_habits)) * (cell_size + 12) + 20
needs_scroll = grid_width > 900

heatmap_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }}
    body {{ background: transparent; overflow: hidden; }}
    .hm-container {{
        background: #FFFFFF;
        border-radius: 18px;
        padding: 1.5rem 1.8rem;
        box-shadow: 0 2px 20px rgba(60,60,67,0.06), 0 0 1px rgba(60,60,67,0.12);
        overflow-x: {"auto" if needs_scroll else "hidden"};
    }}
    .hm-grid {{
        display: inline-grid;
        grid-template-columns: 5.5rem repeat({num_days}, {cell_size}px) auto;
        column-gap: 3px;
        row-gap: 4px;
        align-items: center;
        min-width: {"{}px".format(grid_width) if needs_scroll else "100%"};
    }}
    .hm-date-label {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-size: {max(9, min(12, cell_size // 2))}px;
        font-weight: 600;
        color: #1D1D1F;
        line-height: 1.2;
    }}
    .hm-date-label span {{
        font-size: {max(7, min(10, cell_size // 3))}px;
        font-weight: 400;
        color: #86868B;
    }}
    .hm-label {{
        font-size: 0.78rem;
        font-weight: 500;
        color: #1D1D1F;
        text-align: right;
        padding-right: 0.8rem;
        white-space: nowrap;
    }}
    .hm-cell {{
        width: {cell_size}px;
        height: {cell_size}px;
        border-radius: {max(3, cell_size // 7)}px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        cursor: default;
        position: relative;
        justify-self: center;
    }}
    .hm-cell:hover {{
        transform: scale(1.2);
        box-shadow: 0 4px 12px rgba(60,60,67,0.14);
        z-index: 10;
    }}
    .hm-active {{ background: #34C759; }}
    .hm-empty {{ background: #E5E5EA; }}
    .hm-manual {{ cursor: pointer; }}
    .hm-streak {{
        font-size: 0.65rem;
        color: #86868B;
        font-weight: 500;
        padding-left: 0.5rem;
        white-space: nowrap;
    }}
    .hm-spacer {{ pointer-events: none; }}
    #hm-popup {{
        display: none;
        position: fixed;
        background: #1D1D1F;
        color: #FFFFFF;
        border-radius: 10px;
        padding: 0.6rem 0.9rem;
        font-size: 0.72rem;
        z-index: 9999;
        pointer-events: none;
        min-width: 100px;
        max-width: 200px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }}
    #hm-popup .pop-date {{
        font-weight: 600;
        margin-bottom: 0.2rem;
    }}
    #hm-popup .pop-score {{
        color: #34C759;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }}
    #hm-popup .pop-detail {{
        border-top: 1px solid rgba(255,255,255,0.15);
        padding-top: 0.35rem;
        margin-top: 0.2rem;
    }}
    #hm-popup .pop-detail-line {{
        color: #E5E5EA;
        line-height: 1.5;
        font-size: 0.68rem;
    }}
    #hm-popup .pop-empty {{
        color: #86868B;
        font-style: italic;
    }}
</style>
</head>
<body>
<div class="hm-container">
    <div class="hm-grid">
        <div class="hm-spacer"></div>
        {date_header_html}
        <div class="hm-spacer"></div>
        {grid_rows_html}
    </div>
</div>
<div id="hm-popup"></div>
<script>
const popup = document.getElementById('hm-popup');
document.querySelectorAll('.hm-cell').forEach(cell => {{
    cell.addEventListener('mouseenter', e => {{
        const date = cell.dataset.date || '';
        const score = cell.dataset.score || '';
        const detail = cell.dataset.detail || '';
        if (!date) return;
        let html = '<div class="pop-date">' + date + '</div>';
        if (score) html += '<div class="pop-score">' + score + '/10</div>';
        else if (cell.classList.contains('hm-active')) html += '<div class="pop-score">已完成</div>';
        else html += '<div class="pop-empty">未记录</div>';
        if (detail) {{
            const lines = detail.split('\\n').filter(l => l.trim());
            html += '<div class="pop-detail">' + lines.map(l => '<div class="pop-detail-line">' + l + '</div>').join('') + '</div>';
        }}
        popup.innerHTML = html;
        popup.style.display = 'block';
        const rect = cell.getBoundingClientRect();
        popup.style.left = (rect.left + rect.width/2 - popup.offsetWidth/2) + 'px';
        popup.style.top = (rect.bottom + 8) + 'px';
    }});
    cell.addEventListener('mouseleave', () => {{
        popup.style.display = 'none';
    }});
    if (cell.classList.contains('hm-manual')) {{
        cell.style.cursor = 'pointer';
    }}
}});
</script>
</body>
</html>
"""

components.html(heatmap_html, height=grid_height + 60 + (20 if needs_scroll else 0), scrolling=False)


# ─── Row 4: Reflection Insights ────────────────────────────
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

# ─── Row 5: Correlation ─────────────────────────────────────
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

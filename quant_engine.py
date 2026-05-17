# quant_engine.py
"""
五大品种 20日ROC 动量轮动策略
────────────────────────────
步骤一：每日收盘前比较五个品种的20日ROC，选出涨幅最大的品种
步骤二：若最强品种ROC > 0 → 买入/持有；若ROC <= 0 → 全部空仓
"""

import streamlit as st
import altair as alt
import pandas as pd
from engine_cn import get_monitor_data

# 与 engine_cn.display_names 保持一致
UNIVERSE = ["沪深300 ETF", "创成长 ETF", "中证2000 ETF", "黄金 ETF", "纳指 ETF"]

# 对应颜色（与 engine_cn 的 range_colors 一致）
COLOR_MAP = {
    "沪深300 ETF": "#1E90FF",
    "创成长 ETF":  "#32CD32",
    "中证2000 ETF": "#FF4500",
    "黄金 ETF":    "#FFD700",
    "纳指 ETF":    "#FF8C00",
}


def get_rotation_signal(raw_data: list) -> dict:
    """
    从 get_monitor_data() 的返回值计算轮动信号。

    返回：
        {
            "target":    str,    # 选中品种名（空仓时为 None）
            "roc20":     float,  # 选中品种的20日ROC
            "action":    str,    # "BUY" | "CASH"
            "roc_table": list,   # [{"name", "curr", "roc20_val"}, ...]，按ROC降序
        }
    """
    rows = []
    for item in raw_data:
        if item["name"] in UNIVERSE:
            rows.append({
                "name":     item["name"],
                "curr":     item["curr"],
                "roc20":    item["roc20_val"],
            })

    if not rows:
        return None

    # 按20日ROC降序排列
    rows.sort(key=lambda x: x["roc20"], reverse=True)
    best = rows[0]

    if best["roc20"] > 0:
        action = "BUY"
    else:
        action = "CASH"

    return {
        "target":    best["name"] if action == "BUY" else None,
        "roc20":     best["roc20"],
        "action":    action,
        "roc_table": rows,
    }


def render_rotation_strategy():
    """
    在 Streamlit 页面中渲染轮动策略信号面板。
    在主 app 文件中调用：
        from quant_engine import render_rotation_strategy
        render_rotation_strategy()
    """
    st.subheader("🔄 五大品种 20日ROC 动量轮动策略")

    raw_data = get_monitor_data()
    if not raw_data:
        st.warning("尚未获取到数据，请点击侧边栏的「强制同步」按钮。")
        return

    signal = get_rotation_signal(raw_data)
    if signal is None:
        st.error("轮动池品种在数据中均未匹配，请检查 engine_cn 的 display_names 配置。")
        return

    # ── 操作信号横幅 ──────────────────────────────────────────
    if signal["action"] == "BUY":
        st.success(
            f"**【今日信号：买入 / 持有】** &nbsp;▶&nbsp; **{signal['target']}**"
            f"　　20日ROC = **{signal['roc20']:+.2f}%**",
            icon="✅",
        )
    else:
        st.warning(
            f"**【今日信号：空仓】** &nbsp;▶&nbsp; 最强品种20日ROC = **{signal['roc20']:+.2f}%** ≤ 0，清仓观望",
            icon="⚠️",
        )

    st.markdown("---")

    # ── 各品种ROC指标卡（按ROC降序排列）──────────────────────
    cols = st.columns(5)
    for i, row in enumerate(signal["roc_table"]):
        is_winner = (row["name"] == signal["target"])
        label = ("🏆 " if is_winner else "") + row["name"]
        cols[i].metric(
            label=label,
            value=f"{row['curr']:.3f}",
            delta=f"{row['roc20']:+.2f}%",
        )

    st.markdown("---")

    # ── 柱状图：五大品种20日ROC对比 ─────────────────────────
    bar_df = pd.DataFrame(signal["roc_table"])
    bar_df["正负"] = bar_df["roc20"].apply(lambda x: "正收益" if x > 0 else "负收益")
    bar_df["是否选中"] = bar_df["name"] == signal["target"]

    bar = (
        alt.Chart(bar_df)
        .mark_bar()
        .encode(
            x=alt.X("name:N", sort="-y", title=None,
                    axis=alt.Axis(labelAngle=0)),
            y=alt.Y("roc20:Q", title="20日ROC (%)"),
            color=alt.Color(
                "正负:N",
                scale=alt.Scale(
                    domain=["正收益", "负收益"],
                    range=["#26a69a", "#ef5350"],
                ),
                legend=alt.Legend(title=None),
            ),
            opacity=alt.condition(
                alt.datum["是否选中"],
                alt.value(1.0),
                alt.value(0.55),
            ),
            tooltip=[
                alt.Tooltip("name:N",  title="品种"),
                alt.Tooltip("roc20:Q", title="20日ROC (%)", format="+.2f"),
                alt.Tooltip("curr:Q",  title="最新价",      format=".3f"),
            ],
        )
        .properties(height=300, title="📊 五大 ETF 20日ROC 对比（选中品种高亮）")
        .interactive()
    )
    st.altair_chart(bar, use_container_width=True)

    # ── 历史ROC走势图（复用 full_df 中已算好的 roc20 列）────
    plot_list = []
    for item in raw_data:
        if item["name"] in UNIVERSE:
            plot_list.append(item["full_df"])

    if plot_list:
        days_opt = st.select_slider(
            "📅 历史走势跨度",
            options=[20, 50, 100, 250, "全部"],
            value=50,
            key="quant_days_slider",
        )
        combined = pd.concat(
            [d.tail(int(days_opt)) if days_opt != "全部" else d for d in plot_list]
        ).dropna()

        domain = list(COLOR_MAP.keys())
        colors = list(COLOR_MAP.values())

        line = (
            alt.Chart(combined)
            .mark_line()
            .encode(
                x=alt.X("date:T", title="日期",
                         axis=alt.Axis(format="%Y-%m-%d", labelAngle=-45)),
                y=alt.Y("roc20:Q", title="20日ROC (%)", scale=alt.Scale(zero=True)),
                color=alt.Color(
                    "name:N",
                    title="资产",
                    legend=alt.Legend(orient="top"),
                    scale=alt.Scale(domain=domain, range=colors),
                ),
                tooltip=[
                    alt.Tooltip("date:T",  title="日期",  format="%Y-%m-%d"),
                    alt.Tooltip("name:N",  title="资产"),
                    alt.Tooltip("roc20:Q", title="ROC20 (%)", format=".2f"),
                ],
            )
            .properties(height=380, title="📈 五大 ETF 20日ROC 历史走势")
            .interactive()
        )
        st.altair_chart(line, use_container_width=True)

    st.caption("⚠️ 本策略仅供参考，不构成投资建议。每日收盘前参考信号操作。")

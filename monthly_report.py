# -*- coding: utf-8 -*-
"""
monthly_report.py —— 月度战记页（量化交易页里的一个 tab）
=========================================================
数据来源：STOCK_alarm 仓库的 monthly-report workflow 每月 1 号自动生成
上个月的 YYYY-MM.json，并 push 到本仓库 data/monthly/ 下。本页只读展示，
样式沿用 quant_engine 的 dashboard。
"""
import os
import glob
import json

import streamlit as st
import streamlit.components.v1 as components

from quant_engine import CSS, _pct, _esc, _stat, svg_hist

MONTHLY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "monthly")


def list_months() -> list:
    """['2026-09', '2026-08', ...]，新的在前。"""
    files = glob.glob(os.path.join(MONTHLY_DIR, "*.json"))
    return sorted((os.path.splitext(os.path.basename(f))[0] for f in files), reverse=True)


def load_month(month: str) -> dict:
    with open(os.path.join(MONTHLY_DIR, f"{month}.json"), encoding="utf-8") as f:
        return json.load(f)


def _sgn(v):
    return "" if v is None else ("pos" if v >= 0 else "neg")


def _rate(v):
    return f"{v*100:.0f}%" if v is not None else "—"


def _horizon_panel(title, s):
    stats = (
        _stat("平均收益", _pct(s["avg"]), _sgn(s["avg"])) +
        _stat("中位数", _pct(s["median"]), _sgn(s["median"])) +
        _stat("上涨率", _rate(s["up_rate"])) +
        _stat("跑赢沪深300", _rate(s["beat_rate"])) +
        _stat("平均超额", _pct(s["avg_exc"]), _sgn(s["avg_exc"])) +
        _stat("沪深300同期", _pct(s["bench"])))
    pend = (f'<span class="pill wait">未到期 {s["pending"]}</span>'
            if s["pending"] else '<span class="pill ok">全部到期</span>')
    return (f'<div class="cohort"><div class="chead"><div class="ctitle">{title}'
            f'　<span class="muted">样本 {s["valid"]}/{s["n"]}</span>{pend}</div></div>'
            f'<div class="statbar">{stats}</div></div>')


def _group_table(rows):
    if not rows:
        return '<div class="ph">暂无数据</div>'
    trs = "".join(
        f'<tr><td>{_esc(r["name"])}</td><td class="num">{r["n"]}</td>'
        f'<td class="num {_sgn(r["avg"])}">{_pct(r["avg"])}</td>'
        f'<td class="num">{_rate(r["up_rate"])}</td>'
        f'<td class="num {_sgn(r["avg_exc"])}">{_pct(r["avg_exc"])}</td></tr>'
        for r in rows)
    return ('<table><thead><tr><th>名称</th><th class="num">次数</th>'
            '<th class="num">T+7 平均</th><th class="num">上涨率</th>'
            '<th class="num">平均超额</th></tr></thead>'
            f'<tbody>{trs}</tbody></table>')


def _rank_rows(items, key, top=True, n=10):
    v = [x for x in items if x.get(key) is not None]
    v.sort(key=lambda x: x[key], reverse=top)
    if not v:
        return '<div class="ph">暂无到期样本</div>'
    v = v[:n]
    maxabs = max(abs(x[key]) for x in v) or 1.0
    out = ""
    for x in v:
        pos = x[key] >= 0
        w = abs(x[key]) / maxabs * 50
        out += (f'<div class="row"><div class="nm">{_esc(x["name"])}'
                f'<span class="code">{_esc(x["code"])}</span></div>'
                f'<div class="bar"><div class="axis"></div>'
                f'<div class="fill {"p" if pos else "n"}" style="width:{w:.1f}%"></div></div>'
                f'<div class="ret {"pos" if pos else "neg"}">{_pct(x[key])}</div>'
                f'<div class="exc">{_esc(x["date"][5:])}</div>'
                f'<div class="sig">{_esc(x.get("signals") or "")}</div></div>')
    return f'<div class="rows">{out}</div>'


def _daily_table(daily):
    trs = "".join(
        f'<tr><td>{_esc(d["date"])}</td><td class="num">{d["n"]}</td>'
        f'<td class="num {_sgn(d["avg7"])}">{_pct(d["avg7"])}</td>'
        f'<td class="num">{_rate(d["up_rate7"])}</td>'
        f'<td class="num {_sgn(d["avg_me"])}">{_pct(d["avg_me"])}</td></tr>'
        for d in daily)
    return ('<table><thead><tr><th>推荐日</th><th class="num">只数</th>'
            '<th class="num">T+7 平均</th><th class="num">T+7 上涨率</th>'
            '<th class="num">持有到月末</th></tr></thead>'
            f'<tbody>{trs}</tbody></table>')


def build_monthly_html(rep: dict) -> str:
    k = rep["kpi"]; h = rep["horizons"]
    h7, h14, hme = h["7"], h["14"], h["me"]

    def kpi(label, val, cls=""):
        return (f'<div class="kpi"><div class="k">{label}</div>'
                f'<div class="v {cls}">{val}</div></div>')

    kpis = "".join([
        kpi("推荐次数", k["picks"]),
        kpi("交易日", k["days"]),
        kpi("涉及标的", k["codes"]),
        kpi("重复推荐", k["repeat_codes"]),
        kpi("T+7 平均", _pct(h7["avg"]), _sgn(h7["avg"])),
        kpi("T+7 上涨率", _rate(h7["up_rate"]),
            "pos" if (h7["up_rate"] or 0) >= .5 else ""),
        kpi("T+14 平均", _pct(h14["avg"]), _sgn(h14["avg"])),
        kpi("月末平均", _pct(hme["avg"]), _sgn(hme["avg"])),
    ])

    items = rep["items"]
    hist = svg_hist([x["ret7"] for x in items])

    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style></head><body><div class="wrap">
<div class="top"><div class="left"><h1><span class="dot">●</span> {_esc(rep["month"])} 月度战记</h1>
<span class="asof">行情截至 {_esc(rep.get("as_of") or "—")} · 生成于 {_esc(rep.get("generated_at") or "—")}</span></div></div>
<div class="kpis">{kpis}</div>
<div class="card"><h2>各持有期表现</h2>
<div class="grid-mid">{_horizon_panel("持有 T+7", h7)}{_horizon_panel("持有 T+14", h14)}</div>
<div style="height:12px"></div>{_horizon_panel("持有到月末", hme)}
<div class="foot">推荐日收盘 → 其后第 7/14 个交易日收盘 / 当月最后一个交易日收盘（前复权），未计手续费滑点。
超额 = 收益 − 同期沪深300。月底推的票月初时 T+7/T+14 可能尚未到期。仅回顾信号有效性，非投资建议。</div></div>
{f'<div class="card"><h2>T+7 收益分布（样本 {h7["valid"]}）</h2>{hist}</div>' if hist else ""}
<div class="grid-mid">
  <div class="card"><h2>T+7 涨幅榜 Top 10</h2>{_rank_rows(items, "ret7", True)}</div>
  <div class="card"><h2>T+7 跌幅榜 Bottom 10</h2>{_rank_rows(items, "ret7", False)}</div>
</div>
<div class="grid-mid">
  <div class="card"><h2>按信号类型</h2>{_group_table(rep["by_signal"])}</div>
  <div class="card"><h2>按行业（推荐次数 Top 15）</h2>{_group_table(rep["by_industry"])}</div>
</div>
<div class="card"><h2>逐日推荐表现</h2>{_daily_table(rep["daily"])}</div>
</div></body></html>"""


def render_monthly_ui():
    months = list_months()
    if not months:
        st.info("还没有月报。STOCK_alarm 的 monthly-report workflow 会在每月 1 号自动上传上个月的战记。")
        return

    month = st.selectbox("选择月份", months, index=0)
    try:
        rep = load_month(month)
        html = build_monthly_html(rep)
    except Exception as e:
        st.error(f"读取/渲染 {month} 月报失败：{e}")
        return
    components.html(html, height=2600, scrolling=True)

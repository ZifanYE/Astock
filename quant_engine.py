# -*- coding: utf-8 -*-
"""
quant_engine.py —— 量化选股 Dashboard（自包含 Streamlit 页面）
==============================================================
替换原来带登录/Kalman 的量化页。render_quant_ui() 直接读取由另一项目
(WeCom) 的 dashboard.py 产出的 review.db，渲染成与独立预览完全一致的整页
dashboard（KPI / 活跃度 / 信号 / T+7·T+14 绩效 / 排行榜 / 行业 / 最新选股），
用 components.html 嵌入。不依赖任何外部脚本，只需指向 review.db。

用法：
    from quant_engine import render_quant_ui
    render_quant_ui()

配置：把下面 REVIEW_DB_PATH 改成你 WeCom 项目里 data/review.db 的绝对路径。
（也可用环境变量 REVIEW_DB 覆盖。）数据更新：在 WeCom 项目重跑
python dashboard.py；本页只读展示，刷新浏览器即最新。
"""
import os
import sqlite3
import math
import html as _html

import streamlit as st
import streamlit.components.v1 as components

# ══════════════════════════════════════════════════════════════════════════
# 配置：review.db 的绝对路径（改成你的真实路径）
# ══════════════════════════════════════════════════════════════════════════
REVIEW_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "review.db")


def _review_db() -> str:
    return os.environ.get("REVIEW_DB", "") or REVIEW_DB_PATH


# ══════════════════════════════════════════════════════════════════════════
# 渲染层（内联自 WeCom/dashboard.py，逻辑一致，勿改）
# ══════════════════════════════════════════════════════════════════════════
def _clean_ind(s):
    import re
    return re.sub(r"^[A-Z]\d+", "", s or "") or "未分类"


def load_dashboard(conn) -> dict:
    picks = conn.execute("SELECT date,code,name,close,signals,score,industry "
                         "FROM pick_all").fetchall()
    d = {"picks": picks}

    # 描述性聚合
    from collections import Counter, defaultdict
    daily = defaultdict(int); sig = Counter(); ind = Counter()
    codes = set(); dates = set()
    for date, code, name, close, signals, score, industry in picks:
        daily[date] += 1; sig[signals] += 1; ind[_clean_ind(industry)] += 1
        codes.add(code); dates.add(date)
    d["daily"] = sorted(daily.items())
    d["sig"] = sig.most_common()
    d["ind"] = ind.most_common(10)
    d["kpi"] = {"n": len(picks), "days": len(dates), "codes": len(codes),
                "latest": max(dates) if dates else "—"}
    latest = d["kpi"]["latest"]
    d["latest_rows"] = sorted(
        [(c, n, cl, s, _clean_ind(i))
         for (dt, c, n, cl, s, sc, i) in picks if dt == latest],
        key=lambda r: r[0])

    # ---- 绩效：从 review_pick 读，按 T+7 / T+14 组织 ----
    row = conn.execute("SELECT as_of FROM run ORDER BY run_id DESC "
                       "LIMIT 1").fetchone()
    d["as_of"] = row[0] if row else None

    rp = conn.execute(
        "SELECT date,code,name,signals,industry,ret7,ret14,bench7,bench14,"
        "exc7,exc14 FROM review_pick").fetchall()
    d["flat"] = [{"date": dt, "code": c, "name": n, "signals": s,
                  "ret7": r7, "ret14": r14, "exc7": e7, "exc14": e14}
                 for dt, c, n, s, i, r7, r14, b7, b14, e7, e14 in rp]

    def perf(h):
        ri = 5 if h == 7 else 6            # ret7/ret14 位置
        ei = 9 if h == 7 else 10           # exc7/exc14
        bi = 7 if h == 7 else 8            # bench7/bench14
        items = [{"name": x[2], "code": x[1], "signals": x[3],
                  "ret": x[ri], "exc": x[ei], "bench": x[bi]}
                 for x in rp if x[ri] is not None]
        exc = [y["exc"] for y in items if y["exc"] is not None]
        bench_vals = [y["bench"] for y in items if y["bench"] is not None]
        items.sort(key=lambda y: -y["ret"])
        return {
            "h": h, "valid": len(items),
            "up": sum(1 for y in items if y["ret"] > 0),
            "beat": sum(1 for y in exc if y > 0), "n_exc": len(exc),
            "avg": (sum(y["ret"] for y in items) / len(items)) if items else None,
            "avg_exc": (sum(exc) / len(exc)) if exc else None,
            "bench": (sum(bench_vals) / len(bench_vals)) if bench_vals else None,
            "items": items,
        }

    d["perf"] = {7: perf(7), 14: perf(14)}
    return d


PAL = ["#2dd4bf", "#60a5fa", "#f472b6", "#fbbf24", "#a78bfa", "#34d399",
       "#f87171", "#38bdf8", "#fb923c", "#c084fc"]


def _pct(v): return f"{v*100:+.1f}%" if v is not None else "—"


def _esc(s): return _html.escape(str(s))


def svg_area(daily, w=1040, h=170):
    if not daily:
        return '<div class="ph">暂无数据</div>'
    pad_l, pad_b, pad_t = 34, 22, 12
    xs = [d for d, _ in daily]; ys = [c for _, c in daily]
    ymax = max(ys) or 1
    n = len(xs)
    def X(i): return pad_l + (w - pad_l - 8) * (i / max(n - 1, 1))
    def Y(v): return pad_t + (h - pad_t - pad_b) * (1 - v / ymax)
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ys))
    area = (f"{pad_l},{Y(0):.1f} " + pts + f" {X(n-1):.1f},{Y(0):.1f}")
    grid = ""
    for gv in (0, ymax / 2, ymax):
        gy = Y(gv)
        grid += (f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w-8}" y2="{gy:.1f}" '
                 f'class="grid"/><text x="4" y="{gy+3:.1f}" class="axl">{int(gv)}</text>')
    labs = ""
    step = max(n // 8, 1)
    for i in range(0, n, step):
        labs += (f'<text x="{X(i):.1f}" y="{h-6}" class="axl" '
                 f'text-anchor="middle">{xs[i][5:]}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" preserveAspectRatio="none">'
            f'{grid}<polygon points="{area}" fill="url(#ag)"/>'
            f'<polyline points="{pts}" class="ln"/>'
            f'<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#2dd4bf" stop-opacity=".35"/>'
            f'<stop offset="1" stop-color="#2dd4bf" stop-opacity="0"/>'
            f'</linearGradient></defs>{labs}</svg>')


def svg_donut(sig, size=150):
    if not sig:
        return '<div class="ph">暂无数据</div>'
    total = sum(c for _, c in sig) or 1
    r = 52; cx = cy = size / 2; circ = 2 * math.pi * r
    off = 0.0; arcs = ""
    for i, (label, c) in enumerate(sig):
        frac = c / total; seg = circ * frac
        arcs += (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                 f'stroke="{PAL[i%len(PAL)]}" stroke-width="18" '
                 f'stroke-dasharray="{seg:.2f} {circ-seg:.2f}" '
                 f'stroke-dashoffset="{-off:.2f}" '
                 f'transform="rotate(-90 {cx} {cy})"/>')
        off += seg
    leg = "".join(
        f'<div class="lg"><span class="dot" style="background:{PAL[i%len(PAL)]}"></span>'
        f'{_esc(l)} <b>{c}</b></div>' for i, (l, c) in enumerate(sig))
    return (f'<div class="donutwrap"><svg viewBox="0 0 {size} {size}" class="donut">'
            f'{arcs}<text x="{cx}" y="{cy-2}" class="dc" text-anchor="middle">{total}</text>'
            f'<text x="{cx}" y="{cy+14}" class="dcs" text-anchor="middle">总计</text>'
            f'</svg><div class="legend">{leg}</div></div>')


def hbar(items):
    if not items:
        return '<div class="ph">暂无数据</div>'
    mx = max(c for _, c in items) or 1
    rows = ""
    for i, (label, c) in enumerate(items):
        rows += (f'<div class="hb"><div class="hbl" title="{_esc(label)}">{_esc(label)}</div>'
                 f'<div class="hbt"><div class="hbf" style="width:{c/mx*100:.1f}%;'
                 f'background:{PAL[i%len(PAL)]}"></div></div>'
                 f'<div class="hbn">{c}</div></div>')
    return f'<div class="hbars">{rows}</div>'


def _stat(label, val, cls=""):
    return (f'<div class="st"><div class="stk">{label}</div>'
            f'<div class="stv {cls}">{val}</div></div>')


def perf_panel(p):
    """单个持有期(T+7 或 T+14)面板：统计条 + 涨幅榜前/后各 8 只。"""
    h = p["h"]; nv = p["valid"]
    pending = nv == 0
    avg_cls = "" if pending else ("pos" if p["avg"] >= 0 else "neg")
    up_rate = f'{p["up"]/nv*100:.0f}%' if nv else "—"
    if p["n_exc"]:
        beat_txt = f'{p["beat"]}/{p["n_exc"]}（{p["beat"]/p["n_exc"]*100:.0f}%）'
    else:
        beat_txt = "—"
    exc_txt = _pct(p["avg_exc"]); exc_cls = "" if p["avg_exc"] is None else (
        "pos" if p["avg_exc"] >= 0 else "neg")

    stats = (
        _stat("平均每次变化", _pct(p["avg"]), avg_cls) +
        _stat("命中次数", f'{p["up"]}/{nv}' if nv else "—") +
        _stat("上涨率", up_rate) +
        _stat("跑赢沪深300", beat_txt) +
        _stat("平均超额", exc_txt, exc_cls) +
        _stat("沪深300同期", _pct(p["bench"])))

    if pending:
        body = ('<div class="ph">该持有期暂无到期样本'
                '（最近的票还没满 %d 个交易日）。</div>' % h)
    else:
        items = p["items"]
        maxabs = max((abs(y["ret"]) for y in items), default=0.0) or 1.0
        top = items[:8]; bot = items[-8:][::-1] if len(items) > 8 else []

        def line(y):
            pos = y["ret"] >= 0; wpct = abs(y["ret"]) / maxabs * 50
            exc = (f'<div class="exc {"pos" if y["exc"]>=0 else "neg"}">'
                   f'超额{_pct(y["exc"])}</div>' if y.get("exc") is not None
                   else '<div class="exc"></div>')
            return (f'<div class="row"><div class="nm">{_esc(y["name"])}'
                    f'<span class="code">{_esc(y["code"])}</span></div>'
                    f'<div class="bar"><div class="axis"></div>'
                    f'<div class="fill {"p" if pos else "n"}" style="width:{wpct:.1f}%"></div></div>'
                    f'<div class="ret {"pos" if pos else "neg"}">{_pct(y["ret"])}</div>'
                    f'{exc}<div class="sig">{_esc(y.get("signals") or "")}</div></div>')

        body = '<div class="subttl">涨幅榜 Top 8</div><div class="rows">'
        body += "".join(line(y) for y in top) + "</div>"
        if bot:
            body += '<div class="subttl">跌幅榜 Bottom 8</div><div class="rows">'
            body += "".join(line(y) for y in bot) + "</div>"

    return (f'<div class="cohort"><div class="chead">'
            f'<div class="ctitle">持有 T+{h}　<span class="muted">样本 {nv}</span></div>'
            f'</div><div class="statbar">{stats}</div>{body}</div>')


def svg_hist(rets, w=1040, h=160):
    vals = [r for r in rets if r is not None]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    if hi == lo: hi = lo + 0.01
    bins = 24; step = (hi - lo) / bins
    counts = [0] * bins
    for v in vals:
        k = min(int((v - lo) / step), bins - 1); counts[k] += 1
    cmax = max(counts) or 1
    pad_b, pad_t = 20, 8; bw = (w - 16) / bins
    bars = ""
    for i, c in enumerate(counts):
        bh = (h - pad_b - pad_t) * (c / cmax)
        x = 8 + i * bw
        mid = lo + (i + .5) * step
        col = "#2dd4bf" if mid >= 0 else "#f87171"
        bars += (f'<rect x="{x:.1f}" y="{h-pad_b-bh:.1f}" width="{bw-2:.1f}" '
                 f'height="{bh:.1f}" fill="{col}" opacity=".85"/>')
    zx = 8 + (0 - lo) / (hi - lo) * (w - 16)
    zero = (f'<line x1="{zx:.1f}" y1="{pad_t}" x2="{zx:.1f}" y2="{h-pad_b}" '
            f'class="zero"/>') if lo < 0 < hi else ""
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" preserveAspectRatio="none">'
            f'{bars}{zero}<text x="8" y="{h-4}" class="axl">{_pct(lo)}</text>'
            f'<text x="{w-8}" y="{h-4}" class="axl" text-anchor="end">{_pct(hi)}</text></svg>')


CSS = """
:root{--bg:#0b0e14;--card:#141a24;--card2:#0f141d;--line:#232c3b;--fg:#e6edf3;
--muted:#8b98a9;--pos:#2dd4bf;--neg:#f87171;--accent:#60a5fa;}
*{box-sizing:border-box;}
body{margin:0;background:radial-gradient(1400px 700px at 15% -10%,#13202b,var(--bg));
color:var(--fg);font-family:-apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;}
.wrap{max-width:1560px;margin:0 auto;padding:26px 30px 70px;}
.top{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:20px;}
.top .left{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;}
h1{font-size:22px;margin:0;letter-spacing:.5px;} h1 .dot{color:var(--pos);}
.asof{color:var(--muted);font-size:13px;}
.btn{background:linear-gradient(180deg,#1b2635,#141c28);color:var(--fg);
border:1px solid #2b384a;border-radius:10px;padding:9px 16px;font-size:14px;
cursor:pointer;font-weight:600;transition:.15s;}
.btn:hover{border-color:var(--accent);box-shadow:0 0 0 3px rgba(96,165,250,.12);}
.kpis{display:grid;grid-template-columns:repeat(8,1fr);gap:12px;margin-bottom:18px;}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:13px 15px;}
.kpi .k{color:var(--muted);font-size:12px;margin-bottom:6px;white-space:nowrap;}
.kpi .v{font-size:21px;font-weight:700;font-variant-numeric:tabular-nums;}
.kpi .v.pos{color:var(--pos);} .kpi .v.neg{color:var(--neg);} .kpi .v.accent{color:var(--accent);}
.grid-top{display:grid;grid-template-columns:1.7fr 1fr;gap:16px;}
.grid-mid{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;}
.card{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:18px 20px;margin-bottom:16px;}
.card h2{font-size:14px;margin:0 0 14px;color:#cbd5e1;font-weight:600;letter-spacing:.3px;
display:flex;justify-content:space-between;align-items:center;}
.chart{width:100%;height:auto;display:block;}
.chart .grid{stroke:#1e2735;stroke-width:1;}
.chart .axl{fill:var(--muted);font-size:10px;}
.chart .ln{fill:none;stroke:var(--pos);stroke-width:2;}
.chart .zero{stroke:#3a4658;stroke-dasharray:3 3;}
.donutwrap{display:flex;gap:16px;align-items:center;}
.donut{width:150px;height:150px;flex:none;}
.donut .dc{fill:var(--fg);font-size:22px;font-weight:700;}
.donut .dcs{fill:var(--muted);font-size:10px;}
.legend{display:flex;flex-direction:column;gap:7px;font-size:13px;}
.lg{display:flex;align-items:center;gap:7px;color:#cbd5e1;}
.lg b{margin-left:auto;color:var(--fg);} .lg .dot{width:9px;height:9px;border-radius:2px;display:inline-block;}
.hbars{display:flex;flex-direction:column;gap:9px;}
.hb{display:grid;grid-template-columns:190px 1fr 34px;gap:10px;align-items:center;font-size:12px;}
.hbl{color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.hbt{height:14px;background:#0b0f17;border-radius:4px;overflow:hidden;}
.hbf{height:100%;border-radius:4px;}
.hbn{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums;}
.cohort{background:var(--card2);border:1px solid var(--line);border-radius:12px;
padding:14px 16px;}
.chead{margin-bottom:10px;}
.ctitle{font-size:15px;font-weight:600;display:flex;align-items:center;gap:10px;}
.pill{font-size:11px;font-weight:600;padding:2px 9px;border-radius:20px;}
.pill.ok{background:rgba(45,212,191,.15);color:var(--pos);}
.pill.wait{background:rgba(139,152,169,.15);color:var(--muted);}
.statbar{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:14px;
padding:12px;background:#0b0f17;border-radius:9px;}
.st{text-align:center;} .stk{color:var(--muted);font-size:11px;margin-bottom:4px;}
.stv{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums;}
.stv.pos{color:var(--pos);} .stv.neg{color:var(--neg);}
.muted{color:var(--muted);} .pos{color:var(--pos);} .neg{color:var(--neg);}
.rows{display:flex;flex-direction:column;gap:6px;}
.row{display:grid;grid-template-columns:140px 1fr 64px 88px 110px;gap:11px;align-items:center;font-size:13px;}
.nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.nm .code{color:var(--muted);font-size:11px;margin-left:5px;}
.bar{position:relative;height:15px;background:#0b0f17;border-radius:4px;}
.bar .axis{position:absolute;left:50%;top:0;bottom:0;width:1px;background:#2b3444;}
.fill{position:absolute;top:2px;bottom:2px;border-radius:3px;opacity:.9;}
.fill.p{left:50%;background:var(--pos);} .fill.n{right:50%;background:var(--neg);}
.ret{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;}
.ret .star{color:var(--muted);} .exc{text-align:right;font-size:11px;color:var(--muted);}
.nodata{grid-column:2/6;color:var(--muted);}
.sig{color:var(--muted);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);}
th{color:var(--muted);font-weight:500;font-size:12px;}
td.num{text-align:right;font-variant-numeric:tabular-nums;}
.ph{color:var(--muted);text-align:center;padding:30px 0;font-size:13px;}
.foot{color:var(--muted);font-size:12px;margin-top:16px;line-height:1.7;}
/* 排行榜 overlay */
.overlay{position:fixed;inset:0;background:rgba(5,8,12,.78);backdrop-filter:blur(4px);
display:none;align-items:flex-start;justify-content:center;z-index:50;padding:40px 20px;}
.overlay.show{display:flex;}
.lbpanel{background:var(--card);border:1px solid var(--line);border-radius:16px;
width:100%;max-width:900px;max-height:86vh;overflow:auto;padding:22px 24px;}
.lbhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;}
.lbhead h2{margin:0;font-size:18px;}
.close{background:none;border:none;color:var(--muted);font-size:24px;cursor:pointer;line-height:1;}
.ctrls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;}
.chip{background:#0f141d;border:1px solid var(--line);color:var(--muted);
border-radius:8px;padding:6px 13px;font-size:13px;cursor:pointer;}
.chip.on{background:rgba(96,165,250,.15);border-color:var(--accent);color:var(--fg);}
.rank{width:34px;color:var(--muted);text-align:center;font-variant-numeric:tabular-nums;}
.medal{font-size:15px;}
.subttl{font-size:12px;color:var(--muted);margin:12px 0 7px;font-weight:600;}
@media(max-width:1200px){.kpis{grid-template-columns:repeat(4,1fr);}
.grid-top,.grid-mid{grid-template-columns:1fr;}.statbar{grid-template-columns:repeat(3,1fr);}}
@media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr);}
.row{grid-template-columns:110px 1fr 58px 80px;}.sig{display:none;}
.statbar{grid-template-columns:repeat(2,1fr);}}
"""


JS_TMPL = """
const LB = __DATA__;
let lbH = 7, lbSort = 'ret_desc';
function openLB(){document.getElementById('ov').classList.add('show');renderLB();}
function closeLB(){document.getElementById('ov').classList.remove('show');}
function setH(h,el){lbH=h;document.querySelectorAll('.hc').forEach(c=>c.classList.remove('on'));el.classList.add('on');renderLB();}
function setSort(s,el){lbSort=s;document.querySelectorAll('.sc').forEach(c=>c.classList.remove('on'));el.classList.add('on');renderLB();}
function fmt(v){return v==null?'—':(v>=0?'+':'')+(v*100).toFixed(1)+'%';}
function renderLB(){
  const rk = 'ret'+lbH, ek = 'exc'+lbH;
  const key = lbSort.startsWith('exc')?ek:rk;
  const dir = lbSort.endsWith('asc')?1:-1;
  let rows = LB.filter(x=>x[key]!=null).sort((a,b)=>dir*(b[key]-a[key]));
  rows.forEach((x,i)=>x.rank=i+1);
  const body = document.getElementById('lbbody');
  if(!rows.length){body.innerHTML='<tr><td colspan="6" class="ph">该持有期暂无到期样本（最近的票还没满 '+lbH+' 个交易日）</td></tr>';return;}
  const medal=r=>r===1?'🥇':r===2?'🥈':r===3?'🥉':r;
  body.innerHTML = rows.map(x=>{
    const rc = x[rk]>=0?'pos':'neg';
    const ec = x[ek]==null?'':(x[ek]>=0?'pos':'neg');
    return `<tr><td class="rank"><span class="medal">${medal(x.rank)}</span></td>
      <td>${x.name}</td><td class="muted">${x.code}</td>
      <td class="muted">${x.date}</td>
      <td class="num ${rc}">${fmt(x[rk])}</td>
      <td class="num ${ec}">${fmt(x[ek])}</td></tr>`;
  }).join('');
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeLB();});
"""


def build_dashboard_html(db_path: str) -> str:
    """读 review.db，返回整页 dashboard 的 HTML 字符串（供写文件或 Streamlit 嵌入）。"""
    conn = sqlite3.connect(db_path)
    try:
        d = load_dashboard(conn)
    finally:
        conn.close()

    k = d["kpi"]; p7 = d["perf"][7]; p14 = d["perf"][14]

    def kpi(label, val, cls=""):
        return (f'<div class="kpi"><div class="k">{label}</div>'
                f'<div class="v {cls}">{val}</div></div>')

    def sgn(v):
        return "" if v is None else ("pos" if v >= 0 else "neg")

    def urate(pp):
        return f'{pp["up"]/pp["valid"]*100:.0f}%' if pp["valid"] else "—"

    kpis = "".join([
        kpi("累计选股", k["n"]),
        kpi("覆盖交易日", k["days"]),
        kpi("涉及标的", k["codes"]),
        kpi("最新选股日", k["latest"], "accent"),
        kpi("T+7 平均", _pct(p7["avg"]), sgn(p7["avg"])),
        kpi("T+7 上涨率", urate(p7),
            "pos" if p7["valid"] and p7["up"] / p7["valid"] >= .5 else ""),
        kpi("T+14 平均", _pct(p14["avg"]), sgn(p14["avg"])),
        kpi("T+14 上涨率", urate(p14),
            "pos" if p14["valid"] and p14["up"] / p14["valid"] >= .5 else ""),
    ])

    # 绩效面板（T+7 / T+14 并排）
    if p7["valid"] or p14["valid"]:
        perf_body = (f'<div class="grid-mid">{perf_panel(p7)}{perf_panel(p14)}</div>')
    else:
        perf_body = ('<div class="ph">review_pick 里还没有到期收益。装好 baostock 后重跑 '
                     '<b>python dashboard.py</b>；最近 7/14 个交易日内的票尚未到期属正常。</div>')

    # 收益分布（T+7 / T+14 各一张）
    def hist_block(pp):
        hh = svg_hist([y["ret"] for y in pp["items"]])
        return (f'<div class="card"><h2>收益分布 · T+{pp["h"]}（样本 {pp["valid"]}）</h2>'
                f'{hh}</div>') if hh else ""
    hist_card = hist_block(p7) + hist_block(p14)

    bench_line = ""
    bparts = [f'T+{pp["h"]} {_pct(pp["bench"])}' for pp in (p7, p14)
              if pp["bench"] is not None]
    if bparts:
        bench_line = "沪深300同期均值：" + "　".join(bparts) + "<br>"

    # 最新选股表
    trs = "".join(
        f'<tr><td>{_esc(c)}</td><td>{_esc(n)}</td><td class="num">{cl}</td>'
        f'<td>{_esc(s)}</td><td>{_esc(i)}</td></tr>'
        for c, n, cl, s, i in d["latest_rows"]) or \
        '<tr><td colspan="5" class="ph">无</td></tr>'

    # 排行榜数据 + JS
    import json
    js = JS_TMPL.replace("__DATA__", json.dumps(d["flat"], ensure_ascii=False))
    overlay = """
<div class="overlay" id="ov"><div class="lbpanel">
<div class="lbhead"><h2>🏆 个股收益排行榜</h2>
<button class="close" onclick="closeLB()">×</button></div>
<div class="ctrls">
  <span class="chip hc on" onclick="setH(7,this)">T+7</span>
  <span class="chip hc" onclick="setH(14,this)">T+14</span>
  <span style="width:14px"></span>
  <span class="chip sc on" onclick="setSort('ret_desc',this)">收益↓</span>
  <span class="chip sc" onclick="setSort('ret_asc',this)">收益↑</span>
  <span class="chip sc" onclick="setSort('exc_desc',this)">超额↓</span>
</div>
<table><thead><tr><th class="rank">#</th><th>名称</th><th>代码</th><th>推荐日</th>
<th class="num">收益</th><th class="num">超额</th></tr></thead>
<tbody id="lbbody"></tbody></table>
<div class="foot">收益 = 推荐日 → 其后第 7/14 个交易日（前复权）。超额 = 收益 − 同期沪深300。</div>
</div></div>"""

    doc = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>量化选股 Dashboard{" · " + d["as_of"] if d["as_of"] else ""}</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="top">
  <div class="left"><h1><span class="dot">●</span> 量化选股 Dashboard</h1>
  <span class="asof">{"复盘基准日 " + d["as_of"] if d["as_of"] else "选股快照"} · 固定持有 T+7 / T+14 · 数据源 data/review.db</span></div>
  <button class="btn" onclick="openLB()">🏆 排行榜</button>
</div>
<div class="kpis">{kpis}</div>
<div class="grid-top">
  <div class="card"><h2>每日选股活跃度</h2>{svg_area(d["daily"])}</div>
  <div class="card"><h2>信号类型</h2>{svg_donut(d["sig"])}</div>
</div>
<div class="card"><h2>历史推荐复盘 · 固定持有 T+7 / T+14</h2>{perf_body}
<div class="foot">{bench_line}推荐当日收盘 → 其后第 7/14 个交易日收盘（前复权），未计手续费滑点。仅回顾信号有效性，非投资建议。</div></div>
{hist_card}
<div class="grid-mid">
  <div class="card"><h2>行业分布 (Top 10)</h2>{hbar(d["ind"])}</div>
  <div class="card"><h2>最新选股 · {k["latest"]}</h2>
  <table><thead><tr><th>代码</th><th>名称</th><th class="num">选股价</th><th>信号</th><th>行业</th></tr></thead>
  <tbody>{trs}</tbody></table></div>
</div>
</div>{overlay}
<script>{js}</script>
</body></html>"""

    return doc


# ══════════════════════════════════════════════════════════════════════════
# Streamlit 页面入口
# ══════════════════════════════════════════════════════════════════════════
def render_quant_ui():
    db = _review_db()

    if not os.path.exists(db):
        st.warning(
            "还没找到 review.db。\n\n"
            f"（本页查找的路径：`{db}`）\n\n"
            "请把本文件顶部的 **REVIEW_DB_PATH** 改成你 WeCom 项目里 "
            "`data/review.db` 的绝对路径，并确保已在 WeCom 项目下运行过 "
            "`python dashboard.py` 生成该库。")
        return

    try:
        html = build_dashboard_html(db)
    except Exception as e:
        st.error(f"读取/渲染 review.db 失败：{e}")
        return

    components.html(html, height=2400, scrolling=True)
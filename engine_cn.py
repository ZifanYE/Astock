# engine_cn.py
import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import calendar
import os
import json
import time
import altair as alt
import trade_test as trade  # 请确保你的 trade_test.py 文件在同级目录
from proxy_provider import fetcher # 👈 引入外部防御层

# =============================================================================
# 0. 离线快照系统 (物理兜底，防止接口彻底失效时报错)
# =============================================================================
SNAPSHOT_FILE = "market_snapshot.json"

def get_snapshot(key):
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get(key)
        except: return None
    return None

def set_snapshot(key, value):
    data = {}
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except: pass
    data[key] = value
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =============================================================================
# 1. 用户管理系统
# =============================================================================

def load_all_users():
    """读取所有用户信息"""
    db_path = "user_data.json"
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return {}
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_all_users(all_users):
    """保存所有用户字典"""
    with open("user_data.json", "w", encoding="utf-8") as f:
        json.dump(all_users, f, indent=4, ensure_ascii=False)

def get_default_profile(nickname):
    return {
        "nickname": nickname,
        "color": "#FF4B4B",
        "balance": 100000.0,
        "holdings": {},
        "history": [],    
        "asset_log": [],  
        "avatar": "👩‍💻"
    }

# =============================================================================
# 2. 核心行情函数 (集成外部 Proxy + 双接口平替 + 快照兜底)
# =============================================================================

@st.cache_data(ttl=3600)
def get_stock_data(symbol, start_date, end_date):
    """日次データ取得。集成外部防御层与本地平替逻辑"""
    snap_key = f"stock_{symbol}_{start_date}"
    
    # 路径 A: 尝试通过外部 fetcher 防御层获取 (含 Proxy 和 UA 伪装)
    try:
        df = fetcher.safe_get_stock_hist(symbol, start_date, end_date)
        if df is not None and not df.empty:
            # 统一列名映射，防止回测逻辑失效
            df = df.rename(columns={'close': '收盘', 'date': '日期'})
            df['日期'] = pd.to_datetime(df['日期'])
            set_snapshot(snap_key, df.to_json())
            return df[['日期', '收盘']]
    except: pass

    # 路径 B: 如果 fetcher 失败，尝试本地 Akshare 平替接口 (Sina 源)
    try:
        df = ak.stock_zh_a_daily(symbol=f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}", 
                                start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            df = df.rename(columns={'close': '收盘'})
            df['日期'] = pd.to_datetime(df.index)
            set_snapshot(snap_key, df.to_json())
            return df[['日期', '收盘']]
    except: pass
    
    # 路径 C: 物理离线快照兜底 (保证不报错)
    cached_json = get_snapshot(snap_key)
    if cached_json:
        df = pd.read_json(cached_json)
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    return None

@st.cache_data(ttl=600)
def get_monitor_data():
    """主流监控。集成防御层抓取。"""
    snap_key = "monitor_list"
    assets = {"510300": "沪深300 ETF", "159949": "创业板50 ETF", "563300": "中证2000 ETF", "518880": "黄金 ETF"}
    
    # 路径 A: 尝试防御层 fetcher
    try:
        results = fetcher.safe_get_etf_snapshot(assets)
        if results:
            set_snapshot(snap_key, results)
            return results
    except: pass

    # 路径 B: 失败时自动加载最后一次成功的离线快照
    offline = get_snapshot(snap_key)
    if offline: return offline
    
    # 彻底空值时返回 0 数据防止 UI 崩溃
    return [{"name": v, "curr": 0.0, "roc": 0.0} for v in assets.values()]

def render_mainstream_monitor():
    data = get_monitor_data()
    cols = st.columns(4)
    for i, item in enumerate(data):
        cols[i].metric(label=item["name"], value=f"{item['curr']:.3f}", delta=f"{item['roc']:.2f}%")

# =============================================================================
# 3. 辅助计算逻辑
# =============================================================================

def get_nearest_price_info(target_date, df):
    if df is None or df.empty: return None, None, ""
    nearest_idx = (df['日期'] - target_date).abs().idxmin()
    actual_date = df.loc[nearest_idx, '日期']
    price = df.loc[nearest_idx, '收盘']
    diff_days = (actual_date - target_date).days
    note = "当日" if diff_days == 0 else (f"延后{diff_days}天" if diff_days > 0 else f"提前{abs(diff_days)}天")
    return actual_date, price, note

def get_futures_delivery(year, month):
    c = calendar.monthcalendar(year, month)
    fridays = [week[4] for week in c if week[4] != 0]
    return datetime.datetime(year, month, fridays[2]) if len(fridays) >= 3 else None

def get_option_delivery(year, month):
    c = calendar.monthcalendar(year, month)
    wednesdays = [week[2] for week in c if week[2] != 0]
    return datetime.datetime(year, month, wednesdays[3]) if len(wednesdays) >= 4 else None

def get_month_end(year, month):
    _, last_day = calendar.monthrange(year, month)
    return datetime.datetime(year, month, last_day)

def get_mid_month(year, month):
    return datetime.datetime(year, month, 15)

# =============================================================================
# 4. メインUI渲染逻辑
# =============================================================================

def render_cn_ui():
    st.markdown("#### 🚀 主流今日监测 (ROC 25D)")
    monitor_placeholder = st.empty()
    with monitor_placeholder.container():
        render_mainstream_monitor()

    st.markdown("### 📈 A股量化分析工具箱")
    tab1, tab2, tab3, tab4 = st.tabs(["💼 模拟交易", "🔍 基础查询 (特定日期股价)", "📊 策略回测 (波段 vs 长持)", "🏆 排行榜"])

    with tab1: render_trade_ui()

    with tab2:
        col1_in, col1_res = st.columns([1, 3], gap="large")
        with col1_in:
            with st.container(border=True):
                st.caption("查询设置")
                t1_code = st.text_input("股票代码", value="600519", key="t1_code")
                t1_year = st.number_input("年份", 2000, 2026, 2025, key="t1_year")
                t1_mode_sel = st.radio("日期模式", ("A: 月中(15日) & 月底", "B: 期货(第3周五) & 期权(第4周三)"), key="t1_mode")
                t1_run = st.button("查询股价", type="primary", use_container_width=True)

        with col1_res:
            if t1_run:
                with st.spinner('正在获取数据...'):
                    df = get_stock_data(t1_code, f"{t1_year}0101", f"{t1_year}1231")
                    if df is not None:
                        target_list = []
                        mode = "A" if "A:" in t1_mode_sel else "B"
                        for m in range(1, 13):
                            today = datetime.datetime.now()
                            dates_to_check = [("月中", get_mid_month(t1_year, m)), ("月底", get_month_end(t1_year, m))] if mode == "A" else [("期货交割", get_futures_delivery(t1_year, m)), ("期权交割", get_option_delivery(t1_year, m))]
                            for type_name, dt in dates_to_check:
                                if dt and dt <= today:
                                    act_date, price, note = get_nearest_price_info(dt, df)
                                    if price is not None:
                                        target_list.append({"月份": f"{m}月", "类型": type_name, "目标日期": dt.strftime("%Y-%m-%d"), "实际交易日": act_date.strftime("%Y-%m-%d"), "收盘价": f"{price:.2f}", "说明": note})
                        if target_list:
                            res_df = pd.DataFrame(target_list)
                            st.dataframe(res_df, use_container_width=True)
                        else: st.info("没有符合的数据。")
                    else: st.error("行情接口已受限且无历史快照。")

    with tab3:
        col2_in, col2_res = st.columns([1, 3], gap="large")
        with col2_in:
            t2_code = st.text_input("股票代码", value="600519", key="t2_code")
            t2_year = st.number_input("回测年份", 2010, 2026, 2024, key="t2_year")
            t2_run = st.button("开始回测", type="primary", use_container_width=True)
        if t2_run:
            df = get_stock_data(t2_code, f"{t2_year}0101", f"{t2_year+1}0228")
            if df is not None and not df.empty:
                trades = []
                df['Y'], df['M'] = df['日期'].dt.year, df['日期'].dt.month
                for m in range(1, 13):
                    curr_m_df = df[(df['Y'] == t2_year) & (df['M'] == m)]
                    if not curr_m_df.empty:
                        target_buy = get_futures_delivery(t2_year, m)
                        if target_buy:
                            idx = (curr_m_df['日期'] - target_buy).abs().idxmin()
                            b_date, b_price = curr_m_df.loc[idx, '日期'], curr_m_df.loc[idx, '收盘']
                            ny, nm = (t2_year, m+1) if m < 12 else (t2_year+1, 1)
                            next_m_df = df[(df['Y'] == ny) & (df['M'] == nm)]
                            if not next_m_df.empty:
                                idx_s = (next_m_df['日期'] - datetime.datetime(ny, nm, 1)).abs().idxmin()
                                s_date, s_price = next_m_df.loc[idx_s, '日期'], next_m_df.loc[idx_s, '收盘']
                                if s_date > b_date:
                                    trades.append({"月份": f"{m}月", "买入": b_date.date(), "买入价": b_price, "卖出": s_date.date(), "卖出价": s_price, "收益": round(s_price-b_price, 2)})
                if trades: st.dataframe(pd.DataFrame(trades), use_container_width=True)
                else: st.warning("未捕捉到有效交易点对。")

    with tab4:
        st.info("💡 展示本地扫描记录。")
        if os.path.exists("CSI300_Scan_2024.csv"):
            st.dataframe(pd.read_csv("CSI300_Scan_2024.csv").head(15))

# =============================================================================
# 5. 模拟交易界面逻辑 (修复完整闭合)
# =============================================================================

def render_trade_ui():
    if "current_user" not in st.session_state: st.session_state.current_user = None
    all_users = load_all_users()

    if st.session_state.current_user is None:
        login_name = st.text_input("登录账户", key="login_box")
        if st.button("进入系统", type="primary"):
            if login_name:
                if login_name not in all_users:
                    all_users[login_name] = get_default_profile(login_name)
                    save_all_users(all_users)
                st.session_state.current_user = login_name
                st.rerun()
        return

    curr_name = st.session_state.current_user
    user = all_users[curr_name]
    user = trade.update_asset_log(user)
    all_users[curr_name] = user
    save_all_users(all_users)

    # UI 账户看板
    c1, c2, c3, c4 = st.columns([0.6, 2, 4, 1], vertical_alignment="center")
    c1.markdown(f"## {user['avatar']}")
    c2.write(f"**{user['nickname']}**\n\n¥{user['balance']:,.2f}")
    with c3:
        if user.get('asset_log') and len(user['asset_log']) > 1:
            df_log = pd.DataFrame(user['asset_log'])
            chart = alt.Chart(df_log).mark_area(
                line={'color': user['color']},
                color=alt.Gradient(gradient='linear', stops=[
                    alt.GradientStop(color=user['color'], offset=1),
                    alt.GradientStop(color='white', offset=0)], x1=1, x2=1, y1=1, y2=0)
            ).encode(x=alt.X('time:N', axis=alt.Axis(labels=False, title=None)),
                     y=alt.Y('total:Q', scale=alt.Scale(zero=False), title=None))
            st.altair_chart(chart, use_container_width=True)
    if c4.button("退出"):
        st.session_state.current_user = None
        st.rerun()

    st.divider()

    # 交易操作区
    tc1, tc2, tc3 = st.columns(3)
    t_code = tc1.text_input("代码", value="510300", key="tr_code")
    t_qty = tc2.number_input("数量", min_value=100, step=100, key="tr_qty")
    op_b, op_s = tc3.columns(2)
    
    if op_b.button("买入", type="primary", use_container_width=True):
        s, m, u = trade.process_buy(user, t_code, t_qty)
        if s: 
            all_users[curr_name] = u
            save_all_users(all_users)
            st.rerun()
        else: st.error(m)

    if op_s.button("卖出", type="primary", use_container_width=True):
        s, m, u = trade.process_sell(user, t_code, t_qty)
        if s: 
            all_users[curr_name] = u
            save_all_users(all_users)
            st.rerun()
        else: st.error(m)

    # 持仓与历史
    st.subheader("📦 当前持仓明细")
    if user['holdings']:
        st.dataframe(pd.DataFrame([{"代码": k, "数量": v} for k, v in user['holdings'].items()]), use_container_width=True, hide_index=True)
    else: st.caption("暂无持仓")

    with st.expander("🕒 查看交易历史"):
        if user['history']:
            st.dataframe(pd.DataFrame(user['history']).iloc[::-1], use_container_width=True, hide_index=True)
        else: st.write("暂无成交记录")
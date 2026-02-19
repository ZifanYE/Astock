# engine_cn.py
import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import calendar
import os

# =============================================================================
# 核心ツール関数ライブラリ (Core Utility Functions)
# =============================================================================

@st.cache_data(ttl=3600) # キャッシュを有効化し、リクエストの重複を避ける
def get_stock_data(symbol, start_date, end_date):
    """
    日次データを取得する関数
    引数: symbol(銘柄コード), start_date(開始日), end_date(終了日)
    戻り値: 日付と終値を含むDataFrame
    """
    try:
        # adjust="qfq" は前復権（株式分割等の調整済み価格）を意味する
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return None
        df['日期'] = pd.to_datetime(df['日期'])
        return df[['日期', '收盘']]
    except Exception as e:
        return None

def render_mainstream_monitor():
    assets = {
        "510300": "沪深300 ETF",
        "159949": "创业板50 ETF",
        "563300": "中证2000 ETF",
        "518880": "黄金 ETF"
    }
    cols = st.columns(4)
    for i, (code, name) in enumerate(assets.items()):
        # 获取ETF前复权历史数据
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="qfq")
        if not df.empty and len(df) >= 26:
            curr = df['收盘'].iloc[-1]
            prev = df['收盘'].iloc[-26]
            roc = ((curr / prev) - 1) * 100
            cols[i].metric(label=name, value=f"{curr:.3f}", delta=f"{roc:.2f}%")


def get_nearest_price_info(target_date, df):
    """
    ターゲット日に最も近い取引日の情報を検索する
    戻り値: (実際の取引日, 終値, 差分日数の説明)
    """
    if df is None or df.empty:
        return None, None, ""
        
    # 時間差の絶対値が最小のインデックスを検索
    nearest_idx = (df['日期'] - target_date).abs().idxmin()
    actual_date = df.loc[nearest_idx, '日期']
    price = df.loc[nearest_idx, '收盘']
    
    diff_days = (actual_date - target_date).days
    
    # 差分日数に基づいたラベル付け
    note = "当日"
    if diff_days > 0: note = f"延后{diff_days}天"
    elif diff_days < 0: note = f"提前{abs(diff_days)}天"
    
    return actual_date, price, note

# --- 日付ルールの計算ロジック (Date Rule Calculations) ---

def get_futures_delivery(year, month):
    """先物交割日：第3金曜日"""
    c = calendar.monthcalendar(year, month)
    fridays = [week[4] for week in c if week[4] != 0]
    return datetime.datetime(year, month, fridays[2]) if len(fridays) >= 3 else None

def get_option_delivery(year, month):
    """期权交割日：第4水曜日"""
    c = calendar.monthcalendar(year, month)
    wednesdays = [week[2] for week in c if week[2] != 0]
    return datetime.datetime(year, month, wednesdays[3]) if len(wednesdays) >= 4 else None

def get_month_end(year, month):
    """月末の最終日"""
    _, last_day = calendar.monthrange(year, month)
    return datetime.datetime(year, month, last_day)

def get_mid_month(year, month):
    """月中の15日"""
    return datetime.datetime(year, month, 15)

# =============================================================================
# メインUIレンダリングロジック (Main UI Rendering Logic)
# =============================================================================

def render_cn_ui():
    """
    中国市場（A株）向けのメインUI。UI上の表記はすべて中国語を維持する。
    """
    st.markdown("#### 🚀 主流今日监测 (ROC 25D)")
    #render_mainstream_monitor()
    # 1. 在最上方创建一个占位符
    monitor_placeholder = st.empty()
    
    # 2. 占位符先显示一个“加载中”的状态，避免顶部空出一块很奇怪
    with monitor_placeholder.container():
        st.caption("正在实时获取市场动量数据... ⏳")

    st.markdown("### 📈 A股量化分析工具箱")

    # タブによる機能モジュールの分離
    tab1, tab2, tab3 = st.tabs(["🔍 基础查询 (特定日期股价)", "📊 策略回测 (波段 vs 长持)", "🏆 排行榜"])

    # ----------------------------------------------------------------
    # 機能1：基礎照会 (Original Functionality)
    # ----------------------------------------------------------------
    with tab1:
        col1_input, col1_result = st.columns([1, 3], gap="large")
        
        with col1_input:
            with st.container(border=True):
                st.caption("查询设置")
                t1_code = st.text_input("股票代码", value="600519", key="t1_code")
                cur_year = datetime.datetime.now().year
                t1_year = st.number_input("年份", min_value=2000, max_value=cur_year, value=cur_year, key="t1_year")
                
                t1_mode_sel = st.radio(
                    "日期模式",
                    ("A: 月中(15日) & 月底", "B: 期货(第3周五) & 期权(第4周三)"),
                    key="t1_mode"
                )
                t1_run = st.button("查询股价", type="primary", use_container_width=True, key="t1_btn")

        with col1_result:
            if t1_run and t1_code:
                with st.spinner('正在查询...'):
                    df = get_stock_data(t1_code, f"{t1_year}0101", f"{t1_year}1231")
                    if df is not None:
                        target_list = []
                        mode = "A" if "A:" in t1_mode_sel else "B"
                        
                        for m in range(1, 13):
                            today = datetime.datetime.now()
                            dates_to_check = []
                            
                            if mode == "A":
                                dates_to_check = [("月中", get_mid_month(t1_year, m)), ("月底", get_month_end(t1_year, m))]
                            else:
                                f_day, o_day = get_futures_delivery(t1_year, m), get_option_delivery(t1_year, m)
                                if f_day: dates_to_check.append(("期货交割日", f_day))
                                if o_day: dates_to_check.append(("期权交割日", o_day))
                            
                            for type_name, dt in dates_to_check:
                                if dt <= today:
                                    act_date, price, note = get_nearest_price_info(dt, df)
                                    if price is not None:
                                        target_list.append({
                                            "月份": f"{dt.strftime('%m')}月", "类型": type_name, "目标日期": dt.strftime("%Y-%m-%d"),
                                            "实际交易日": act_date.strftime("%Y-%m-%d"), "收盘价": f"{price:.2f}", "说明": note
                                        })
                        
                        if target_list:
                            res_df = pd.DataFrame(target_list)
                            st.dataframe(res_df, use_container_width=True)
                            csv = res_df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 导出CSV", csv, f"{t1_code}_{t1_year}_基础查询.csv", "text/csv")
                        else:
                            st.info("没有符合日期的历史数据。")
                    else:
                        st.error("数据获取失败，请检查代码。")

    # ----------------------------------------------------------------
    # 機能2：策略バックテスト (Strict Monthly Validation)
    # ----------------------------------------------------------------
    with tab2:
        col2_input, col2_result = st.columns([1, 3], gap="large")
        
        with col2_input:
            with st.container(border=True):
                st.caption("回测参数")
                t2_code = st.text_input("股票代码", value="600519", key="t2_code")
                t2_year = st.number_input("回测年份", min_value=2010, max_value=cur_year, value=cur_year-1, key="t2_year")
                st.divider()
                buy_rule = st.selectbox("🔵 买入点", ["本月期货交割日(第3周五)", "本月期权交割日(第4周三)", "本月最后交易日"], key="buy_rule")
                sell_rule = st.selectbox("🔴 卖出点", ["下月第1个交易日", "下月15日(或最近交易日)"], key="sell_rule")
                t2_run = st.button("开始回测", type="primary", use_container_width=True, key="t2_btn")

        with col2_result:
            if t2_run and t2_code:
                with st.spinner('正在计算跨年收益...'):
                    # 決済期間をまたぐため、翌年3月までのデータを取得
                    df = get_stock_data(t2_code, f"{t2_year}0101", f"{t2_year+1}0301")
                    if df is not None:
                        trades = []
                        df['Year'] = df['日期'].dt.year
                        df['Month'] = df['日期'].dt.month
                        
                        for m in range(1, 13):
                            b_date, b_price, s_date, s_price = None, None, None, None
                            # 1. 【買入】日の確定 (対象月内に厳格限定)
                            curr_month_df = df[(df['Year'] == t2_year) & (df['Month'] == m)]
                            if not curr_month_df.empty:
                                if "最后交易日" in buy_rule:
                                    row = curr_month_df.iloc[-1]
                                    b_date, b_price = row['日期'], row['收盘']
                                else:
                                    target_buy = get_futures_delivery(t2_year, m) if "期货" in buy_rule else get_option_delivery(t2_year, m)
                                    if target_buy:
                                        nearest_idx = (curr_month_df['日期'] - target_buy).abs().idxmin()
                                        b_date, b_price = curr_month_df.loc[nearest_idx, '日期'], curr_month_df.loc[nearest_idx, '收盘']
                            
                            # 2. 【売出】日の確定 (翌月内に厳格限定)
                            if b_date: 
                                n_y, n_m = (t2_year, m + 1) if m < 12 else (t2_year + 1, 1)
                                next_month_df = df[(df['Year'] == n_y) & (df['Month'] == n_m)]
                                if not next_month_df.empty:
                                    if "第1个" in sell_rule:
                                        row = next_month_df.iloc[0]
                                        s_date, s_price = row['日期'], row['收盘']
                                    else:
                                        target_sell = datetime.datetime(n_y, n_m, 15)
                                        nearest_idx = (next_month_df['日期'] - target_sell).abs().idxmin()
                                        s_date, s_price = next_month_df.loc[nearest_idx, '日期'], next_month_df.loc[nearest_idx, '收盘']
                                
                                # 3. トレードの記録
                                if s_date and s_price and s_date > b_date:
                                    trades.append({
                                        "月份": f"{m}月", "买入日期": b_date.strftime("%Y-%m-%d"), "买入价": b_price,
                                        "卖出日期": s_date.strftime("%Y-%m-%d"), "卖出价": s_price, "收益": s_price - b_price
                                    })
                        
                        if trades:
                            t_df = pd.DataFrame(trades)
                            first_buy, last_sell, total_profit = t_df.iloc[0]['买入价'], t_df.iloc[-1]['卖出价'], t_df['收益'].sum()
                            st.success(f"回测完成：{t2_code} ({t2_year})")
                            k1, k2, k3 = st.columns(3)
                            k1.metric("初始投入", f"{first_buy:.2f}")
                            k2.metric("策略收益率 (波段)", f"{(total_profit/first_buy)*100:.2f}%", delta=f"{total_profit:.2f}元")
                            k3.metric("长持收益率 (死拿)", f"{(last_sell/first_buy-1)*100:.2f}%", delta=f"{last_sell-first_buy:.2f}元")
                            st.dataframe(t_df, use_container_width=True, hide_index=True)
                        else:
                            st.warning(f"该年份 ({t2_year}) 数据不足。")

    # ----------------------------------------------------------------
    # 功能3：ランキング (CSV Reader)
    # ----------------------------------------------------------------
    with tab3:
        st.info("💡 说明：此页面仅展示本地已生成的扫描文件。")
        col3_left, col3_right = st.columns([1, 4])
        with col3_left:
            dataset = st.radio("📊 选择数据集", ["上证50 (SSE50)", "沪深300 (CSI300)"])
            scan_year = st.number_input("扫描年份", 2020, 2026, 2024, step=1)
            target_file = f"{'SSE50' if '50' in dataset else 'CSI300'}_Scan_{scan_year}.csv"
        with col3_right:
            if os.path.exists(target_file):
                try:
                    df_rank = pd.read_csv(target_file)
                    st.success(f"✅ 成功读取文件，共包含 {len(df_rank)} 只股票数据。")
                    st.dataframe(df_rank.head(10), use_container_width=True)
                except Exception as e:
                    st.error(f"文件读取出错: {e}")
            else:
                st.warning(f"⚠️ 未找到文件 `{target_file}`。")

    with monitor_placeholder.container():
        # 这里放置你的标题和 render_mainstream_monitor 逻辑
        render_mainstream_monitor()
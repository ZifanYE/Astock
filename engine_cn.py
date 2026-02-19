# engine_cn.py
import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import calendar
import os
import json
import trade_test as trade

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
        "history": [],    # 新增：记录每一笔买卖
        "asset_log": [],  # 新增：记录每日总资产 [日期, 金额]
        "avatar": "👩‍💻"
    }
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

# 1. 专门把数据获取和计算逻辑抽离出来，并加缓存
@st.cache_data(ttl=600) # 缓存10分钟，10分钟内点击查询不会重测
def get_monitor_data():
    assets = {"510300": "沪深300 ETF", "159949": "创业板50 ETF", "563300": "中证2000 ETF", "518880": "黄金 ETF"}
    results = []
    for code, name in assets.items():
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="qfq")
        if not df.empty and len(df) >= 26:
            curr = df['收盘'].iloc[-1]
            prev = df['收盘'].iloc[-26]
            roc = ((curr / prev) - 1) * 100
            results.append({"name": name, "curr": curr, "roc": roc})
    return results

# 2. 修改渲染函数
def render_mainstream_monitor():
    data = get_monitor_data() # 这里会触发缓存机制
    cols = st.columns(4)
    for i, item in enumerate(data):
        cols[i].metric(label=item["name"], value=f"{item['curr']:.3f}", delta=f"{item['roc']:.2f}%")


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
    #tab1, tab2, tab3, tab4 = st.tabs(["🔍 基础查询 (特定日期股价)", "📊 策略回测 (波段 vs 长持)", "🏆 排行榜", "💼 模拟交易"])
    tab1, tab2, tab3, tab4 = st.tabs(["💼 模拟交易", "🔍 基础查询 (特定日期股价)","📊 策略回测 (波段 vs 长持)", "🏆 排行榜"])
    # ----------------------------------------------------------------
    # 機能1：基礎照会 (Original Functionality)
    # ----------------------------------------------------------------
    with tab1:
        render_trade_ui()

    with tab2:
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
    with tab3:
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
    with tab4:
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

def render_trade_ui():
    # 使用 session_state 记录当前登录状态
    if "current_user" not in st.session_state:
        st.session_state.current_user = None

    all_users = load_all_users()

    # --- 1. 登录/注册界面 ---
    if st.session_state.current_user is None:
        st.markdown("#### 👤 登录量化账户")
        login_name = st.text_input("请输入您的昵称", placeholder="例如: Zifan_Quant")
        if st.button("进入账户", type="primary"):
            if login_name:
                if login_name in all_users:
                    st.success(f"欢迎回来，{login_name}！已继承您的账户余额。")
                else:
                    all_users[login_name] = get_default_profile(login_name)
                    save_all_users(all_users)
                    st.info(f"已为您创建新账户：{login_name}，初始资金 ¥100,000.00")
                
                st.session_state.current_user = login_name
                st.rerun()
            else:
                st.warning("昵称不能为空")
        return # 登录前不显示后续交易内容

    # --- 2. 交易看板 (已登录) ---
    curr_name = st.session_state.current_user
    user = all_users[curr_name]

    user = trade.update_asset_log(user) 
    all_users[curr_name] = user
    save_all_users(all_users)

# 1. 重新定义四列布局 [头像, 昵称余额, 资产曲线, 退出按钮]
    # 比例建议：0.6 (头像) : 2 (信息) : 4 (图表) : 1 (退出)
    col_p1, col_p2, col_p3, col_p4 = st.columns([0.6, 2, 4, 1], vertical_alignment="center")

    with col_p1:
        st.markdown(f"<h1 style='text-align: center; margin:0;'>{user['avatar']}</h1>", unsafe_allow_html=True)

    with col_p2:
        st.markdown(f"**{user['nickname']}**", unsafe_allow_html=True)
        st.write(f"💰 ¥{user['balance']:,.2f}")

    with col_p3:
        if user.get('asset_log') and len(user['asset_log']) > 1:
            df_log = pd.DataFrame(user['asset_log'])
            
            # --- 1. 修复报错：color 必须是列表 ---
            chart_color = [user.get('color', '#FF4B4B')]
            
            # --- 2. 进阶：使用 Altair 实现真正的“金融自适应” ---
            # 原生 st.area_chart 无法关闭“包含0”，导致波动看不见。
            # 我们用 Streamlit 内置的 altair 库来画，效果秒杀原生。
            import altair as alt
            
            chart = alt.Chart(df_log).mark_area(
                line={'color': chart_color[0]},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color=chart_color[0], offset=1),
                           alt.GradientStop(color='white', offset=0)],
                    x1=1, x2=1, y1=1, y2=0
                )
            ).encode(
                x=alt.X('time:N', axis=alt.Axis(labels=False, ticks=False, title=None)),
                y=alt.Y('total:Q', scale=alt.Scale(zero=False), title=None), # zero=False 是自适应的关键
                tooltip=['time', 'total']
            ).properties(height=100)

            st.altair_chart(chart, use_container_width=True)
            
        else:
            st.caption("📈 待交易数据入场...")
            st.progress(0.1)

    with col_p4:
        if st.button("退出", use_container_width=True, key="logout_btn"):
            st.session_state.current_user = None
            st.rerun()
    st.divider()

# --- B. 交易操作 (保持原有代码) ---
# --- 3. 交易操作与持仓 ---
    c1, c2, c3 = st.columns(3)
    t_code = c1.text_input("标的代码", value="510300")
    t_qty = c2.number_input("交易数量", min_value=100, step=100)
    
    op_c1, op_c2 = c3.columns(2)
    st.write(" ") # 占位
    
    if op_c1.button("买入", type="primary", width="stretch"):
        # 1. 创建状态容器
        with st.status("正在撮合交易...", expanded=True) as status:
            st.write("📡 正在连接行情接口...")
            # 这里调用你的接口
            success, msg, updated_user = trade.process_buy(user, t_code, t_qty)
            
            if success:
                st.write("💰 正在进行资金清算...")
                updated_user = trade.update_asset_log(updated_user) 
                all_users[curr_name] = updated_user
                save_all_users(all_users)
                st.write("📝 正在同步本地账本...")
                status.update(label="✅ 交易已撮合成功", state="complete", expanded=False)
                st.toast(msg) # 小弹窗提示
                st.rerun()
            else:
                status.update(label="❌ 交易失败", state="error", expanded=True)
                st.error(msg)

    if op_c2.button("卖出", type="primary", width="stretch"):
        # 1. 创建状态容器
        with st.status("正在撮合交易...", expanded=True) as status:
            st.write("📡 正在连接行情接口...")
            # 这里调用你的接口
            success, msg, updated_user = trade.process_sell(user, t_code, t_qty)
            
            if success:
                st.write("💰 正在进行资金清算...")
                updated_user = trade.update_asset_log(updated_user) 
                all_users[curr_name] = updated_user
                save_all_users(all_users)
                st.write("📝 正在同步本地账本...")
                status.update(label="✅ 交易已撮合成功", state="complete", expanded=False)
                st.toast(msg) # 小弹窗提示
                st.rerun()
            else:
                status.update(label="❌ 交易失败", state="error", expanded=True)
                st.error(msg)

    # 显示持仓表
    st.subheader("📦 当前持仓明细")
    if user['holdings']:
        # 使用 st.dataframe 效果比 st.table 更专业，支持排序
        st.dataframe(
            pd.DataFrame([{"代码": k, "数量": v} for k, v in user['holdings'].items()]),
            width="stretch",
            hide_index=True
        )
    else:
        st.caption("暂无持仓")
    
    # --- C. 交易历史明细 ---
    with st.expander("🕒 查看交易历史记录", expanded=False):
        if user['history']:
            # 倒序显示，最新的在上面
            history_df = pd.DataFrame(user['history']).iloc[::-1]
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.write("暂无成交记录")
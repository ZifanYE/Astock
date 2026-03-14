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
        "history": [],    # 记录买卖明细
        "asset_log": [],  # 记录每日总资产 [日期, 金额]
        "avatar": "👩‍💻"
    }

# =============================================================================
# 2. 核心行情函数 (解决 IP 被 Ban 的平替方案)
# =============================================================================

@st.cache_data(ttl=3600)
def get_stock_data(symbol, start_date, end_date):
    """日次データ取得。EM接口被封时自动切换到Sina接口"""
    try:
        # 路径 A: 东方财富接口
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            df['日期'] = pd.to_datetime(df['日期'])
            return df[['日期', '收盘']]
    except:
        try:
            # 路径 B: 新浪源平替（封锁限制极少）
            df = ak.stock_zh_a_daily(symbol=f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}", 
                                    start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = df.rename(columns={'close': '收盘'})
                df['日期'] = pd.to_datetime(df.index)
                return df[['日期', '收盘']]
        except:
            return None
    return None

import random


@st.cache_data(ttl=3600)
def get_monitor_data():
    """全家共享的‘懒加载’函数：数据存在 data/ 文件夹，缺几天补几天"""
    assets = {"510300": "hs300_etf", "159949": "cyb50_etf", "563300": "zz2000_etf", "518880": "gold_etf"}
    display_names = {"510300": "沪深300 ETF", "159949": "创业板50 ETF", "563300": "中证2000 ETF", "518880": "黄金 ETF"}
    
    # 确保 data 文件夹存在
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # 统一使用北京时间判定，避免云端服务器时区坑
    now_bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    today = now_bj.date()
    current_hour = now_bj.hour
    results = []

    for code, file_name in assets.items():
        csv_path = f"data/{file_name}.csv"
        df = pd.DataFrame()
        need_update = False
        
        # 1. 检查本地 CSV 状态
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                df['date'] = pd.to_datetime(df['date']).dt.date # 统一为 date 类型
                last_date = df['date'].max()
                
                # 逻辑优化：
                # A: 如果最后日期落后今天超过 1 天（如周一查上周五），直接补课
                # B: 如果最后日期是昨天，且今天已经收盘（16点后），触发补课
                if (today - last_date).days > 1:
                    need_update = True
                elif last_date < today and current_hour >= 16:
                    need_update = True
            except:
                need_update = True 
        else:
            need_update = True 

        # 2. 执行“补课”爬虫
        if need_update:
            try:
                full_code = f"sh{code}" if code.startswith('5') else f"sz{code}"
                new_data = ak.fund_etf_hist_sina(symbol=full_code)
                if new_data is not None and not new_data.empty:
                    new_data['date'] = pd.to_datetime(new_data['date']).dt.date
                    # 合并、去重、排序
                    df = pd.concat([df, new_data]).drop_duplicates(subset=['date']).sort_values('date')
                    df.to_csv(csv_path, index=False)
                time.sleep(random.uniform(1.5, 2.5))
            except Exception as e:
                st.sidebar.error(f"数据同步失败({code}): {e}")

        # 3. 提取展示数据
        if not df.empty:
            df = df.sort_values('date').reset_index(drop=True)
            
            # 计算 ROC25
            df['roc25'] = df['close'].pct_change(25) * 100 
            
            curr_price = float(df['close'].iloc[-1])
            curr_roc25 = float(df['roc25'].iloc[-1]) if not pd.isna(df['roc25'].iloc[-1]) else 0.0
            
            # 这里的 full_df 建议转换回 datetime 方便绘图组件识别
            plot_df = df[['date', 'roc25']].copy()
            plot_df['name'] = display_names[code]
            
            results.append({
                "name": display_names[code],
                "curr": curr_price,
                "roc25_val": curr_roc25,
                "full_df": plot_df
            })

    return results

def render_mainstream_monitor():
    # --- 1. 数据同步按钮逻辑 ---
    if st.sidebar.button("🔄 强制同步最新数据"):
        # 第一步：清除所有 @st.cache_data 装饰的函数缓存
        st.cache_data.clear()
        
        # 第二步：显示加载动画并执行更新
        with st.spinner("正在获取最新行情并更新本地 CSV..."):
            # 由于缓存已清，此处调用会触发函数内部的 need_update 逻辑
            get_monitor_data()
            st.sidebar.success("同步完成！")
        
        # 第三步：立即刷新页面，使 get_monitor_data() 重新运行并读取更新后的 CSV
        st.rerun()

    # --- 2. 正常获取数据 ---
    # 无论是否点击按钮，页面加载时都会走这一步
    raw_data = get_monitor_data()

    # --- 3. 截断处理 ---
    if not raw_data:
        st.warning("尚未获取到数据，请点击上方按钮同步。")
        st.stop() # 替代原来的 return，在 streamlit 中更安全

    # --- 新增/修改：定义 ETF 名称与颜色的映射关系 ---
    # 确保这里的名称与 get_monitor_data 传出的 display_names 一致
    domain_names = ["沪深300 ETF", "创业板50 ETF", "中证2000 ETF", "黄金 ETF"]
    # 对应颜色：蓝色(沪深)、绿色(创业)、红色(中证)、金色(黄金)
    range_colors = ["#1E90FF", "#32CD32", "#FF4500", "#FFD700"] 

    cols = st.columns(4)
    plot_list = []
    days_option = st.select_slider("📅 选择趋势跨度", options=[20, 50, 100, 250, "全部"], value=50)
    for i, item in enumerate(raw_data):
        cols[i].metric(label=item["name"], value=f"{item['curr']:.3f}", delta=f"{item['roc25_val']:.2f}%")
        
        df_p = item["full_df"].tail(int(days_option)) if days_option != "全部" else item["full_df"]
        plot_list.append(df_p)

    if plot_list:
        combined_df = pd.concat(plot_list).dropna() 
        st.markdown("---")
        
        chart = alt.Chart(combined_df).mark_line().encode(
            x=alt.X('date:T', title='日期', axis=alt.Axis(format='%Y-%m-%d', labelAngle=-45)),
            y=alt.Y('roc25:Q', title='25日动量 (ROC %)', scale=alt.Scale(zero=True)), 
            
            # --- 核心修改：在 color 中加入 scale 参数 ---
            color=alt.Color('name:N', 
                title='资产', 
                legend=alt.Legend(orient='top'),
                # 新加入 scale 属性，手动绑定名称与颜色
                scale=alt.Scale(domain=domain_names, range=range_colors)
            ),
            
            tooltip=[
                alt.Tooltip('date:T', title='日期', format='%Y-%m-%d'),
                alt.Tooltip('name:N', title='资产'),
                alt.Tooltip('roc25:Q', title='ROC25', format='.2f')
            ]
        ).properties(height=400, title="🚀 四大 ETF 25日动量对比图").interactive()
        
        st.altair_chart(chart, use_container_width=True)

# =============================================================================
# 3. 辅助计算逻辑
# =============================================================================

def get_nearest_price_info(target_date, df):
    if df is None or df.empty:
        return None, None, ""
    nearest_idx = (df['日期'] - target_date).abs().idxmin()
    actual_date = df.loc[nearest_idx, '日期']
    price = df.loc[nearest_idx, '收盘']
    diff_days = (actual_date - target_date).days
    note = "当日"
    if diff_days > 0: note = f"延后{diff_days}天"
    elif diff_days < 0: note = f"提前{abs(diff_days)}天"
    return actual_date, price, note

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

    # ----------------------------------------------------------------
    # Tab 1: 模拟交易
    # ----------------------------------------------------------------
    with tab1:
        render_trade_ui()

    # ----------------------------------------------------------------
    # Tab 2: 基础查询
    # ----------------------------------------------------------------
    with tab2:
        col1_input, col1_result = st.columns([1, 3], gap="large")
        with col1_input:
            with st.container(border=True):
                st.caption("查询设置")
                t1_code = st.text_input("股票代码", value="600519", key="t1_code")
                cur_year = datetime.datetime.now().year
                t1_year = st.number_input("年份", min_value=2000, max_value=cur_year, value=cur_year, key="t1_year")
                t1_mode_sel = st.radio("日期模式", ("A: 月中(15日) & 月底", "B: 期货(第3周五) & 期权(第4周三)"), key="t1_mode")
                t1_run = st.button("查询股价", type="primary", use_container_width=True, key="t1_btn")

        with col1_result:
            if t1_run and t1_code:
                with st.spinner('正在获取数据...'):
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
                            st.download_button("📥 导出CSV", res_df.to_csv(index=False).encode('utf-8-sig'), f"{t1_code}_股价.csv", "text/csv")
                        else: st.info("没有符合日期的历史数据。")
                    else: st.error("数据获取失败，请尝试更换代码或稍后再试。")

    # ----------------------------------------------------------------
    # Tab 3: 策略回测
    # ----------------------------------------------------------------
    with tab3:
        col2_input, col2_result = st.columns([1, 3], gap="large")
        with col2_input:
            with st.container(border=True):
                st.caption("回测参数")
                t2_code = st.text_input("股票代码", value="600519", key="t2_code")
                cur_y = datetime.datetime.now().year
                t2_year = st.number_input("回测年份", min_value=2010, max_value=cur_y, value=cur_y-1, key="t2_year")
                st.divider()
                buy_rule = st.selectbox("🔵 买入点", ["本月期货交割日(第3周五)", "本月期权交割日(第4周三)", "本月最后交易日"], key="buy_rule")
                sell_rule = st.selectbox("🔴 卖出点", ["下月第1个交易日", "下月15日(或最近交易日)"], key="sell_rule")
                t2_run = st.button("开始回测", type="primary", use_container_width=True, key="t2_btn")

        with col2_result:
            if t2_run and t2_code:
                with st.spinner('正在计算策略收益...'):
                    df = get_stock_data(t2_code, f"{t2_year}0101", f"{t2_year+1}0301")
                    if df is not None:
                        trades = []
                        df['Year'] = df['日期'].dt.year
                        df['Month'] = df['日期'].dt.month
                        for m in range(1, 13):
                            b_date, b_price, s_date, s_price = None, None, None, None
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
                                if s_date and s_price and s_date > b_date:
                                    trades.append({"月份": f"{m}月", "买入日期": b_date.strftime("%Y-%m-%d"), "买入价": b_price, "卖出日期": s_date.strftime("%Y-%m-%d"), "卖出价": s_price, "收益": s_price - b_price})
                        if trades:
                            t_df = pd.DataFrame(trades)
                            first_buy, last_sell, total_profit = t_df.iloc[0]['买入价'], t_df.iloc[-1]['卖出价'], t_df['收益'].sum()
                            st.success(f"回测完成：{t2_code}")
                            k1, k2, k3 = st.columns(3)
                            k1.metric("初始买入价", f"{first_buy:.2f}")
                            k2.metric("波段策略收益率", f"{(total_profit/first_buy)*100:.2f}%", delta=f"{total_profit:.2f}")
                            k3.metric("年度持有收益率", f"{(last_sell/first_buy-1)*100:.2f}%", delta=f"{last_sell-first_buy:.2f}")
                            st.dataframe(t_df, use_container_width=True, hide_index=True)
                        else: st.warning("该年份数据不足以回测。")

    # ----------------------------------------------------------------
    # Tab 4: 排行榜
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
                    st.success(f"✅ 成功读取 {len(df_rank)} 只股票数据。")
                    st.dataframe(df_rank.head(15), use_container_width=True)
                except Exception as e: st.error(f"读取出错: {e}")
            else: st.warning(f"⚠️ 未找到文件 `{target_file}`。")

# =============================================================================
# 5. 模拟交易界面逻辑 (由 Tab 1 调用)
# =============================================================================

def render_trade_ui():
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    all_users = load_all_users()

    if st.session_state.current_user is None:
        st.markdown("#### 👤 登录量化账户")
        login_name = st.text_input("请输入您的昵称", placeholder="例如: Zifan_Quant")
        if st.button("进入账户", type="primary"):
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

    # 重新定义四列布局 [头像, 信息, 曲线, 退出]
    col_p1, col_p2, col_p3, col_p4 = st.columns([0.6, 2, 4, 1], vertical_alignment="center")
    with col_p1: st.markdown(f"<h1 style='text-align: center; margin:0;'>{user['avatar']}</h1>", unsafe_allow_html=True)
    with col_p2:
        st.markdown(f"**{user['nickname']}**", unsafe_allow_html=True)
        st.write(f"💰 ¥{user['balance']:,.2f}")
    with col_p3:
        if user.get('asset_log') and len(user['asset_log']) > 1:
            df_log = pd.DataFrame(user['asset_log'])
            chart_color = [user.get('color', '#FF4B4B')]
            chart = alt.Chart(df_log).mark_area(
                line={'color': chart_color[0]},
                color=alt.Gradient(gradient='linear', stops=[
                    alt.GradientStop(color=chart_color[0], offset=1),
                    alt.GradientStop(color='white', offset=0)], x1=1, x2=1, y1=1, y2=0)
            ).encode(
                x=alt.X('time:N', axis=alt.Axis(labels=False, ticks=False, title=None)),
                y=alt.Y('total:Q', scale=alt.Scale(zero=False), title=None),
                tooltip=['time', 'total']
            ).properties(height=100)
            st.altair_chart(chart, use_container_width=True)
        else: st.progress(0.1)
    with col_p4:
        if st.button("退出", use_container_width=True, key="logout_btn"):
            st.session_state.current_user = None
            st.rerun()
    st.divider()

    # 交易区
    c1, c2, c3 = st.columns(3)
    t_code = c1.text_input("标的代码", value="510300")
    t_qty = c2.number_input("交易数量", min_value=100, step=100)
    op_c1, op_c2 = c3.columns(2)
    if op_c1.button("买入", type="primary", use_container_width=True):
        with st.status("正在撮合交易...") as status:
            success, msg, u = trade.process_buy(user, t_code, t_qty)
            if success:
                all_users[curr_name] = trade.update_asset_log(u)
                save_all_users(all_users); status.update(label="✅ 成功", state="complete"); st.rerun()
            else: status.update(label="❌ 失败", state="error"); st.error(msg)
    if op_c2.button("卖出", type="primary", use_container_width=True):
        with st.status("正在撮合交易...") as status:
            success, msg, u = trade.process_sell(user, t_code, t_qty)
            if success:
                all_users[curr_name] = trade.update_asset_log(u)
                save_all_users(all_users); status.update(label="✅ 成功", state="complete"); st.rerun()
            else: status.update(label="❌ 失败", state="error"); st.error(msg)

    st.subheader("📦 当前持仓明细")
    if user['holdings']:
        st.dataframe(pd.DataFrame([{"代码": k, "数量": v} for k, v in user['holdings'].items()]), use_container_width=True, hide_index=True)
    else: st.caption("暂无持仓")
    with st.expander("🕒 查看交易历史记录"):
        if user['history']: st.dataframe(pd.DataFrame(user['history']).iloc[::-1], use_container_width=True, hide_index=True)
        else: st.write("暂无成交记录")
import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import calendar

# 1. 页面配置
st.set_page_config(page_title="A股分析工具箱", layout="wide")

# ==========================================
#              核心工具函数库
# ==========================================

@st.cache_data(ttl=3600) # 增加简单的缓存，避免重复请求
def get_stock_data(symbol, start_date, end_date):
    """获取日线数据"""
    try:
        # adjust="qfq" 前复权
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return None
        df['日期'] = pd.to_datetime(df['日期'])
        return df[['日期', '收盘']]
    except Exception as e:
        return None

def get_nearest_price_info(target_date, df):
    """
    寻找最近交易日信息
    返回: (实际日期, 收盘价, 差异天数说明)
    """
    if df is None or df.empty:
        return None, None, ""
        
    # 找绝对值最小的时间差
    nearest_idx = (df['日期'] - target_date).abs().idxmin()
    actual_date = df.loc[nearest_idx, '日期']
    price = df.loc[nearest_idx, '收盘']
    
    diff_days = (actual_date - target_date).days
    
    note = "当日"
    if diff_days > 0: note = f"延后{diff_days}天"
    elif diff_days < 0: note = f"提前{abs(diff_days)}天"
    
    return actual_date, price, note

# --- 日期规则计算 ---

def get_futures_delivery(year, month):
    """期货交割日：第3个周五"""
    c = calendar.monthcalendar(year, month)
    fridays = [week[4] for week in c if week[4] != 0]
    return datetime.datetime(year, month, fridays[2]) if len(fridays) >= 3 else None

def get_option_delivery(year, month):
    """期权交割日：第4个周三"""
    c = calendar.monthcalendar(year, month)
    wednesdays = [week[2] for week in c if week[2] != 0]
    return datetime.datetime(year, month, wednesdays[3]) if len(wednesdays) >= 4 else None

def get_month_end(year, month):
    """月末最后一天"""
    _, last_day = calendar.monthrange(year, month)
    return datetime.datetime(year, month, last_day)

def get_mid_month(year, month):
    """月中15号"""
    return datetime.datetime(year, month, 15)

# ==========================================
#                主界面逻辑
# ==========================================

st.markdown("### 📈 A股量化分析工具箱")

# 使用标签页区分两个功能模块
tab1, tab2 = st.tabs(["🔍 基础查询 (特定日期股价)", "📊 策略回测 (波段 vs 长持)"])

# ----------------------------------------------------------------
# 功能一：基础查询 (保留原功能)
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
                            dates_to_check = [
                                ("月中", get_mid_month(t1_year, m)), 
                                ("月底", get_month_end(t1_year, m))
                            ]
                        else:
                            f_day = get_futures_delivery(t1_year, m)
                            o_day = get_option_delivery(t1_year, m)
                            if f_day: dates_to_check.append(("期货交割日", f_day))
                            if o_day: dates_to_check.append(("期权交割日", o_day))
                        
                        for type_name, dt in dates_to_check:
                            if dt <= today:
                                act_date, price, note = get_nearest_price_info(dt, df)
                                if price is not None:
                                    target_list.append({
                                        "月份": f"{dt.strftime('%m')}月",
                                        "类型": type_name,
                                        "目标日期": dt.strftime("%Y-%m-%d"),
                                        "实际交易日": act_date.strftime("%Y-%m-%d"),
                                        "收盘价": f"{price:.2f}",
                                        "说明": note
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
# 功能二：策略回测 (升级版功能)
# ----------------------------------------------------------------
with tab2:
    col2_input, col2_result = st.columns([1, 3], gap="large")
    
    with col2_input:
        with st.container(border=True):
            st.caption("回测参数")
            t2_code = st.text_input("股票代码", value="600519", key="t2_code")
            t2_year = st.number_input("回测年份", min_value=2010, max_value=cur_year, value=cur_year-1, key="t2_year")
            
            st.divider()
            
            buy_rule = st.selectbox("🔵 买入点", 
                ["本月期货交割日(第3周五)", "本月期权交割日(第4周三)", "本月最后交易日"], key="buy_rule")
            
            sell_rule = st.selectbox("🔴 卖出点", 
                ["下月第1个交易日", "下月15日(或最近交易日)"], key="sell_rule")
            
            t2_run = st.button("开始回测", type="primary", use_container_width=True, key="t2_btn")

    with col2_result:
        if t2_run and t2_code:
            with st.spinner('正在计算跨年收益...'):
                # 跨年数据
                df = get_stock_data(t2_code, f"{t2_year}0101", f"{t2_year+1}0228")
                
                if df is not None:
                    trades = []
                    for m in range(1, 13):
                        # 1. 确定买入目标
                        if "期货" in buy_rule: target_buy = get_futures_delivery(t2_year, m)
                        elif "期权" in buy_rule: target_buy = get_option_delivery(t2_year, m)
                        else: target_buy = get_month_end(t2_year, m)
                        
                        # 2. 确定卖出目标 (下个月)
                        next_y = t2_year if m < 12 else t2_year + 1
                        next_m = m + 1 if m < 12 else 1
                        
                        if "第1个" in sell_rule:
                            target_sell = datetime.datetime(next_y, next_m, 1)
                        else:
                            target_sell = datetime.datetime(next_y, next_m, 15)
                            
                        # 3. 获取价格
                        if target_buy:
                            b_date, b_price, _ = get_nearest_price_info(target_buy, df)
                            s_date, s_price, _ = get_nearest_price_info(target_sell, df)
                            
                            if b_price and s_price and s_date > b_date:
                                trades.append({
                                    "月份": f"{m}月",
                                    "买入日期": b_date.strftime("%Y-%m-%d"),
                                    "买入价": b_price,
                                    "卖出日期": s_date.strftime("%Y-%m-%d"),
                                    "卖出价": s_price,
                                    "收益": s_price - b_price
                                })
                    
                    if trades:
                        t_df = pd.DataFrame(trades)
                        
                        # 计算指标
                        first_buy = t_df.iloc[0]['买入价']
                        last_sell = t_df.iloc[-1]['卖出价']
                        total_profit = t_df['收益'].sum()
                        
                        yield_strategy = (total_profit / first_buy) * 100
                        yield_hold = (last_sell / first_buy) * 100
                        yield_hold_real = yield_hold - 100
                        
                        # 展示结果
                        st.success(f"回测完成：{t2_code} ({t2_year})")
                        
                        k1, k2, k3 = st.columns(3)
                        k1.metric("初始投入", f"{first_buy:.2f}")
                        k2.metric("策略收益率 (波段)", f"{yield_strategy:.2f}%", delta=f"{total_profit:.2f}元")
                        k3.metric("长持收益率 (死拿)", f"{yield_hold:.2f}%", delta=f"{yield_hold_real:.2f}% (涨幅)")
                        
                        st.markdown("---")
                        
                        # 格式化表格
                        display_df = t_df.copy()
                        cols = ['买入价', '卖出价', '收益']
                        for c in cols: display_df[c] = display_df[c].apply(lambda x: f"{x:.2f}")
                        
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                        csv = display_df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("📥 导出回测结果", csv, f"{t2_code}_策略回测.csv", "text/csv")
                    else:
                        st.warning("该年份没有足够的交易日数据。")
                else:
                    st.error("数据获取失败。")
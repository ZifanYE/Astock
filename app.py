import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import calendar

# 1. 页面配置
st.set_page_config(page_title="A股交易策略回测", layout="wide")

# --- 核心工具函数 ---

def get_stock_data(symbol, start_date, end_date):
    """获取日线数据，带缓存提示"""
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return None
        df['日期'] = pd.to_datetime(df['日期'])
        return df[['日期', '收盘']]
    except Exception as e:
        st.error(f"API接口报错: {e}")
        return None

def get_nearest_price(target_date, df):
    """
    在数据中寻找离 target_date 最近的交易日和价格
    返回: (实际日期, 收盘价, 差异天数)
    """
    if df is None or df.empty:
        return None, None, None
        
    dates = df['日期']
    # 找绝对值最小的索引
    dt_diff = (dates - target_date).abs()
    nearest_idx = dt_diff.idxmin()
    
    actual_date = dates[nearest_idx]
    price = df.loc[nearest_idx, '收盘']
    diff_days = (actual_date - target_date).days
    
    return actual_date, price, diff_days

# --- 日期计算规则函数 ---

def get_futures_delivery(year, month):
    """期货交割日：第3个周五"""
    c = calendar.monthcalendar(year, month)
    fridays = [week[4] for week in c if week[4] != 0]
    if len(fridays) >= 3:
        return datetime.datetime(year, month, fridays[2])
    return datetime.datetime(year, month, fridays[-1]) # 兜底

def get_option_delivery(year, month):
    """期权交割日：第4个周三"""
    c = calendar.monthcalendar(year, month)
    wednesdays = [week[2] for week in c if week[2] != 0]
    if len(wednesdays) >= 4:
        return datetime.datetime(year, month, wednesdays[3])
    return datetime.datetime(year, month, wednesdays[-1])

def get_month_end(year, month):
    """月末最后一天"""
    _, last_day = calendar.monthrange(year, month)
    return datetime.datetime(year, month, last_day)

def get_next_month_first(year, month):
    """下月1号"""
    if month == 12:
        return datetime.datetime(year + 1, 1, 1)
    return datetime.datetime(year, month + 1, 1)

def get_next_month_15th(year, month):
    """下月15号"""
    if month == 12:
        return datetime.datetime(year + 1, 1, 15)
    return datetime.datetime(year, month + 1, 15)

# --- 策略执行逻辑 ---

def run_strategy(df, year, buy_rule, sell_rule):
    trades = []
    
    # 我们遍历 1月 到 12月
    for month in range(1, 13):
        # 1. 计算【买入】的目标日期
        if buy_rule == "本月期货交割日(第3个周五)":
            target_buy_date = get_futures_delivery(year, month)
        elif buy_rule == "本月期权交割日(第4个周三)":
            target_buy_date = get_option_delivery(year, month)
        else: # 本月最后交易日
            target_buy_date = get_month_end(year, month)
            
        # 2. 计算【卖出】的目标日期 (基于下个月)
        if sell_rule == "下月第1个交易日":
            target_sell_date = get_next_month_first(year, month)
        else: # 下月15日
            target_sell_date = get_next_month_15th(year, month)

        # 3. 获取实际价格
        b_date, b_price, b_diff = get_nearest_price(target_buy_date, df)
        s_date, s_price, s_diff = get_nearest_price(target_sell_date, df)

        # 4. 数据有效性检查
        # 必须都有数据，且 卖出日期 必须在 买入日期 之后
        if b_price is not None and s_price is not None:
            if s_date > b_date:
                profit = s_price - b_price
                trades.append({
                    "月份": f"{month}月",
                    "买入日期": b_date.strftime("%Y-%m-%d"),
                    "买入价": b_price,
                    "卖出日期": s_date.strftime("%Y-%m-%d"),
                    "卖出价": s_price,
                    "单次盈亏": profit
                })
    
    return pd.DataFrame(trades)

# --- UI 界面 ---

st.markdown("### 📊 A股定投/波段策略回测工具")

col_input, col_result = st.columns([1, 3], gap="large")

with col_input:
    with st.container(border=True):
        st.caption("策略设置")
        stock_code = st.text_input("股票代码", value="600519")
        
        cur_year = datetime.datetime.now().year
        year = st.number_input("回测年份", min_value=2010, max_value=cur_year, value=cur_year-1)
        
        st.divider()
        
        # 下拉框选择
        buy_rule = st.selectbox(
            "🔵 买入时机", 
            ["本月期货交割日(第3个周五)", "本月期权交割日(第4个周三)", "本月最后交易日"]
        )
        
        sell_rule = st.selectbox(
            "🔴 卖出时机", 
            ["下月第1个交易日", "下月15日(或最近交易日)"]
        )
        
        run_btn = st.button("开始回测", type="primary", use_container_width=True)

with col_result:
    if run_btn and stock_code:
        with st.spinner('正在拉取跨年数据计算...'):
            # 为了计算12月的"下月卖出"，我们需要拉取到次年2月的数据
            start_dt = f"{year}0101"
            end_dt = f"{year + 1}0228" 
            
            df_hist = get_stock_data(stock_code, start_dt, end_dt)
            
            if df_hist is not None and not df_hist.empty:
                # 运行策略
                res_df = run_strategy(df_hist, year, buy_rule, sell_rule)
                
                if not res_df.empty:
                    # --- 计算核心指标 ---
                    
                    # 1. 基础数据
                    first_buy_price = res_df.iloc[0]['买入价']
                    last_sell_price = res_df.iloc[-1]['卖出价']
                    total_profit = res_df['单次盈亏'].sum()
                    
                    # 2. 策略收益率 (累计盈亏 / 1月买入价)
                    strategy_yield = (total_profit / first_buy_price) * 100
                    
                    # 3. 长持收益率 (12月卖出价 / 1月买入价 * 100%)
                    # 注意：用户要求是"卖/买*100%"，这通常表示总资产变成多少
                    # 如果要看涨幅，通常需要减1。这里严格按用户公式展示。
                    hold_ratio = (last_sell_price / first_buy_price) * 100
                    hold_yield_real = hold_ratio - 100 # 这是实际涨跌幅
                    
                    # --- 展示结果卡片 ---
                    st.success(f"回测完成：{stock_code} ({year}年)")
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("初始成本 (1月买入)", f"{first_buy_price:.2f}")
                    m2.metric("策略总收益率 (盈亏/本金)", f"{strategy_yield:.2f}%", delta=f"{total_profit:.2f}元")
                    m3.metric("长持收益率 (期末/期初)", f"{hold_ratio:.2f}%", delta=f"{hold_yield_real:.2f}% (实际涨幅)")
                    
                    st.markdown("---")
                    
                    # --- 格式化表格显示 ---
                    display_df = res_df.copy()
                    display_df['买入价'] = display_df['买入价'].apply(lambda x: f"{x:.2f}")
                    display_df['卖出价'] = display_df['卖出价'].apply(lambda x: f"{x:.2f}")
                    display_df['单次盈亏'] = display_df['单次盈亏'].apply(lambda x: f"{x:.2f}")
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    # 下载
                    csv = display_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 导出回测单", csv, f"{stock_code}_{year}_策略回测.csv", "text/csv")
                    
                else:
                    st.warning("该时间段内无法生成有效的买卖对（可能数据不足或年份未到）。")
            else:
                st.error("数据获取失败，请检查代码或网络。")
    elif not run_btn:
        st.info("👈 请在左侧配置买卖点并运行")
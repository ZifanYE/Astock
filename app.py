import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import calendar

# 1. 页面布局配置
st.set_page_config(page_title="A股收盘价查询", layout="wide")

# --- 核心逻辑函数 ---

def get_trading_data(symbol, start_date, end_date):
    """获取日线数据"""
    try:
        # adjust="qfq" 前复权
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df.empty: return None
        df['日期'] = pd.to_datetime(df['日期'])
        return df[['日期', '收盘']]
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return None

def get_nearest_date(target_date, available_dates):
    """寻找最近交易日"""
    nearest_idx = (available_dates - target_date).abs().idxmin()
    nearest_date = available_dates[nearest_idx]
    diff_days = (nearest_date - target_date).days
    return nearest_date, diff_days

def get_special_dates(year, month):
    """
    获取当月特殊的两个交割日：
    1. 股指期货交割日：第3个周五
    2. ETF期权交割日：第4个周三
    """
    special_days = []
    c = calendar.monthcalendar(year, month)
    
    # --- 1. 计算第3个周五 (索引4) ---
    fridays = [week[4] for week in c if week[4] != 0]
    if len(fridays) >= 3:
        special_days.append({
            "type": "期货交割日(第3周五)",
            "date": datetime.datetime(year, month, fridays[2])
        })
        
    # --- 2. 计算第4个周三 (索引2) ---
    wednesdays = [week[2] for week in c if week[2] != 0]
    if len(wednesdays) >= 4:
        special_days.append({
            "type": "期权交割日(第4周三)",
            "date": datetime.datetime(year, month, wednesdays[3])
        })
        
    return special_days

def generate_target_dates(year, mode):
    """根据模式生成目标日期列表"""
    targets = []
    today = datetime.datetime.now()
    
    for month in range(1, 13):
        # --- 模式 A: 月中 + 月末 ---
        if mode == "A":
            # 1. 月中
            mid_date = datetime.datetime(year, month, 15)
            if mid_date <= today:
                targets.append({"type": "月中", "date": mid_date})
            
            # 2. 月末
            _, last_day = calendar.monthrange(year, month)
            end_date = datetime.datetime(year, month, last_day)
            if end_date <= today:
                targets.append({"type": "月底", "date": end_date})

        # --- 模式 B: 期货交割日 + 期权交割日 ---
        elif mode == "B":
            special_days = get_special_dates(year, month)
            for day_info in special_days:
                if day_info['date'] <= today:
                    targets.append(day_info)

    # 按日期排序，防止错乱
    targets.sort(key=lambda x: x['date'])
    return targets

# --- 页面 UI ---

st.markdown("### A股特定日期收盘价查询")

col_input, col_result = st.columns([1, 3], gap="large")

with col_input:
    with st.container(border=True):
        st.caption("查询设置")
        
        stock_code = st.text_input("股票代码", value="600519")
        
        current_year = datetime.datetime.now().year
        year = st.number_input("年份", min_value=2000, max_value=current_year, value=current_year)
        
        # 模式选择
        mode_select = st.radio(
            "选择日期模式",
            ("A: 月中(15日) & 月底", "B: 期货(第3周五) & 期权(第4周三)"),
            index=0
        )
        mode = "A" if "A:" in mode_select else "B"

        run_btn = st.button("开始查询", type="primary", use_container_width=True)

with col_result:
    if run_btn and stock_code:
        with st.spinner('正在计算...'):
            start_date_str = f"{year}0101"
            end_date_str = f"{year}1231"
            
            df_hist = get_trading_data(stock_code, start_date_str, end_date_str)
            
            if df_hist is not None and not df_hist.empty:
                trading_dates = df_hist['日期']
                
                target_list = generate_target_dates(year, mode)
                
                result_data = []
                
                for item in target_list:
                    t_date = item['date']
                    
                    actual_date, diff = get_nearest_date(t_date, trading_dates)
                    
                    price_rows = df_hist.loc[df_hist['日期'] == actual_date, '收盘']
                    if not price_rows.empty:
                        price = price_rows.values[0]
                        
                        note = "当日"
                        if diff > 0: note = f"延后{diff}天"
                        elif diff < 0: note = f"提前{abs(diff)}天"

                        result_data.append({
                            "月份": f"{t_date.strftime('%m')}月",
                            "类型": item['type'],
                            "目标日期": t_date.strftime("%Y-%m-%d"),
                            "实际交易日": actual_date.strftime("%Y-%m-%d"),
                            "收盘价": f"{price:.2f}",
                            "说明": note
                        })
                
                if result_data:
                    res_df = pd.DataFrame(result_data)
                    st.success(f"查询完成：{stock_code} ({year}年 模式{mode})")
                    st.dataframe(res_df, use_container_width=True)
                    
                    csv = res_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 导出 CSV",
                        data=csv,
                        file_name=f"{stock_code}_{year}_模式{mode}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.info("所选年份尚未到达该日期节点。")
            else:
                st.warning("未找到数据，请检查股票代码。")
    elif not run_btn:
        st.info("👈 请在左侧选择模式并查询")